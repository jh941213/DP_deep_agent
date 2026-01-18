from __future__ import annotations

from pathlib import Path
from typing import Optional
import json

from shopping_agent.config import ShippingAddress, config

_CACHE_FILENAME = "shipping_address.json"


def _default_address_path(cache_dir: Optional[Path] = None) -> Path:
    base_dir = cache_dir or (Path(__file__).resolve().parent / ".cache")
    return base_dir / _CACHE_FILENAME


def _deserialize_address(data: dict) -> ShippingAddress:
    normalized = dict(data)
    if "zip" in normalized and "zip_code" not in normalized:
        normalized["zip_code"] = normalized.pop("zip")
    return ShippingAddress(**normalized)


def load_shipping_address(cache_dir: Optional[Path] = None) -> ShippingAddress:
    path = _default_address_path(cache_dir)
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            address = _deserialize_address(payload)
            config.shipping = address
            return address
        except Exception:
            pass
    return config.shipping


def save_shipping_address(
    address: ShippingAddress,
    cache_dir: Optional[Path] = None,
) -> Path:
    path = _default_address_path(cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = address.model_dump()
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    config.shipping = address
    return path
