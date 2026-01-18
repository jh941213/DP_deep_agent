from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import uuid
from urllib.parse import urlparse
import json

import httpx

from shopping_agent.config import config

_MANIFEST_CACHE_PREFIX = "ucp_manifest_"
_SCHEMA_CACHE_PREFIX = "ucp_schema_"


def _cache_dir(base: Optional[Path] = None) -> Path:
    return base or (Path(__file__).resolve().parent / ".cache")


def _cache_path(prefix: str, key: str, base: Optional[Path] = None) -> Path:
    safe_key = key.replace(":", "_").replace("/", "_")
    return _cache_dir(base) / f"{prefix}{safe_key}.json"


def _read_cache(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cache(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _manifest_url_for_store(store_url: str) -> str:
    base = store_url.rstrip("/")
    return f"{base}{config.ucp.ucp_manifest_path}"


def fetch_ucp_manifest(
    store_url: str,
    cache_dir: Optional[Path] = None,
    timeout: float = 10.0,
) -> tuple[Optional[dict], dict]:
    manifest_url = _manifest_url_for_store(store_url)
    host = urlparse(store_url).netloc or store_url
    cache_path = _cache_path(_MANIFEST_CACHE_PREFIX, host, cache_dir)
    meta = {
        "url": manifest_url,
        "cached": False,
        "stale": False,
    }

    cached = _read_cache(cache_path)
    if cached:
        meta["cached"] = True
        return cached, meta

    try:
        response = httpx.get(manifest_url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected manifest format")
        _write_cache(cache_path, payload)
        return payload, meta
    except Exception as exc:
        meta["error"] = str(exc)

    if cached:
        meta["stale"] = True
        meta["cached"] = True
        return cached, meta

    return None, meta


def extract_ucp_shopping_mcp(manifest: dict) -> tuple[Optional[str], Optional[str]]:
    ucp = manifest.get("ucp", {})
    services = ucp.get("services", {})
    shopping = services.get("dev.ucp.shopping") or services.get("ucp.shopping")
    if not isinstance(shopping, dict):
        return None, None
    mcp = shopping.get("mcp")
    if not isinstance(mcp, dict):
        return None, None
    return mcp.get("endpoint"), mcp.get("schema")


def resolve_ucp_endpoint(store_url: str, cache_dir: Optional[Path] = None) -> tuple[Optional[str], dict]:
    manifest, meta = fetch_ucp_manifest(store_url, cache_dir=cache_dir)
    if not manifest:
        return None, meta

    endpoint, schema_url = extract_ucp_shopping_mcp(manifest)
    if not endpoint:
        meta["error"] = "UCP MCP endpoint not found"
        return None, meta

    if endpoint.startswith("http://"):
        endpoint = "https://" + endpoint[len("http://"):]

    meta["schema_url"] = schema_url
    meta["ucp_version"] = manifest.get("ucp", {}).get("version")
    meta["capabilities"] = manifest.get("ucp", {}).get("capabilities", [])
    return endpoint, meta


def build_ucp_auth_headers(
    auth_token: Optional[str] = None,
    auth_header: Optional[str] = None,
    auth_scheme: Optional[str] = None,
) -> dict[str, str]:
    token = auth_token or config.ucp_auth_token
    if not token:
        return {}
    header = auth_header or config.ucp_auth_header or "Authorization"
    scheme = auth_scheme or config.ucp_auth_scheme or ""
    if header.lower() == "authorization" and scheme:
        value = f"{scheme} {token}"
    else:
        value = token
    return {header: value}


def ucp_jsonrpc_call(
    endpoint: str,
    method: str,
    params: dict,
    headers: Optional[dict[str, str]] = None,
    timeout: float = 15.0,
) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params,
    }
    response = httpx.post(endpoint, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and "error" in data:
        return {"error": data.get("error"), "raw": data}
    return {"result": data.get("result"), "raw": data}


def build_checkout_payload(
    line_items: list[dict],
    currency: str,
    ucp_version: Optional[str] = None,
    capabilities: Optional[list] = None,
    checkout_id: Optional[str] = None,
    status: str = "incomplete",
) -> dict:
    checkout_id = checkout_id or str(uuid.uuid4())
    ucp_version = ucp_version or "2026-01-11"
    capabilities = capabilities or [{"name": "dev.ucp.shopping.checkout", "version": ucp_version}]

    total_amount = 0
    normalized_items = []
    for item in line_items:
        quantity = int(item.get("quantity", 1))
        price = 0
        item_data = item.get("item", {})
        raw_price = item_data.get("price", 0)
        try:
            price = int(raw_price)
        except (TypeError, ValueError):
            price = 0
        subtotal = max(price * max(quantity, 1), 0)
        total_amount += subtotal
        totals = item.get("totals") or [{"type": "subtotal", "amount": subtotal}]
        normalized = {
            **item,
            "quantity": max(quantity, 1),
            "totals": totals,
        }
        normalized_items.append(normalized)

    totals = [
        {"type": "subtotal", "amount": total_amount},
        {"type": "total", "amount": total_amount},
    ]

    return {
        "ucp": {
            "version": ucp_version,
            "capabilities": capabilities,
        },
        "id": checkout_id,
        "line_items": normalized_items,
        "status": status,
        "currency": currency,
        "totals": totals,
        "links": [],
        "payment": {"handlers": []},
    }

def fetch_ucp_schema(
    schema_url: str,
    cache_dir: Optional[Path] = None,
    timeout: float = 10.0,
) -> tuple[Optional[dict], dict]:
    cache_path = _cache_path(_SCHEMA_CACHE_PREFIX, schema_url, cache_dir)
    meta = {"url": schema_url, "cached": False, "stale": False}

    cached = _read_cache(cache_path)
    if cached:
        meta["cached"] = True
        return cached, meta

    def _attempt(url: str) -> tuple[Optional[dict], Optional[str]]:
        response = httpx.get(url, timeout=timeout)
        if response.status_code == 404:
            return None, "404"
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected schema format")
        return payload, None

    fallback_url = None
    if schema_url.endswith("/openrpc.json"):
        fallback_url = schema_url.replace("/openrpc.json", "/mcp.openrpc.json")
    elif schema_url.endswith("openrpc.json"):
        fallback_url = schema_url.replace("openrpc.json", "mcp.openrpc.json")

    try:
        payload, err = _attempt(schema_url)
        if err == "404" and fallback_url:
            payload, err = _attempt(fallback_url)
            if not err:
                meta["url"] = fallback_url
        if payload is None:
            raise ValueError("Schema not found")
        _write_cache(cache_path, payload)
        return payload, meta
    except Exception as exc:
        meta["error"] = str(exc)

    if cached:
        meta["cached"] = True
        meta["stale"] = True
        return cached, meta

    return None, meta


def list_ucp_methods(schema: dict) -> list[str]:
    methods = schema.get("methods", [])
    names = []
    if isinstance(methods, list):
        for method in methods:
            if isinstance(method, dict) and method.get("name"):
                names.append(str(method["name"]))
    return names


def ucp_supports_product_listing(schema: dict) -> bool:
    names = [name.lower() for name in list_ucp_methods(schema)]
    for name in names:
        if any(keyword in name for keyword in ("catalog", "product", "search", "list", "browse", "collection", "item")):
            return True
    return False
