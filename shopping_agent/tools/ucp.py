from langchain_core.tools import tool

from typing import Optional
import json
import uuid
import httpx

from shopping_agent.ucp import (
    build_checkout_payload,
    build_ucp_auth_headers,
    extract_ucp_shopping_mcp,
    fetch_ucp_manifest,
    fetch_ucp_schema,
    list_ucp_methods,
    resolve_ucp_endpoint,
    ucp_jsonrpc_call,
    ucp_supports_product_listing,
)


@tool
def get_ucp_capabilities(store_url: str) -> str:
    """
    UCP 매니페스트와 Shopping MCP 스키마를 조회하여 지원 기능을 요약합니다.
    """
    manifest, meta = fetch_ucp_manifest(store_url)
    if not manifest:
        return f"UCP 매니페스트를 가져오지 못했습니다: {meta.get('error', 'unknown')}"

    endpoint, schema_url = extract_ucp_shopping_mcp(manifest)
    if not endpoint or not schema_url:
        return "UCP Shopping MCP 정보를 찾을 수 없습니다."

    schema, schema_meta = fetch_ucp_schema(schema_url)
    if not schema:
        return f"UCP MCP 스키마를 가져오지 못했습니다: {schema_meta.get('error', 'unknown')}"

    methods = list_ucp_methods(schema)
    supports_catalog = ucp_supports_product_listing(schema)
    summary = [
        f"UCP MCP Endpoint: {endpoint}",
        f"Methods: {', '.join(methods) if methods else 'None'}",
        f"Catalog/List Support: {'yes' if supports_catalog else 'no'}",
    ]
    return "\n".join(summary)


def _normalize_image_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    if url.startswith("//"):
        return f"https:{url}"
    return url


def _fetch_product_data(product_handle: str, store_url: str) -> Optional[dict]:
    product_url = f"{store_url.rstrip('/')}/products/{product_handle}.js"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Attempt 1: With Headers (Robust)
    try:
        response = httpx.get(product_url, headers=headers, timeout=10.0, follow_redirects=True)
        if response.status_code == 200:
            return response.json()
        print(f"⚠️ [UCP] Fetch Attempt 1 failed: {response.status_code}")
    except Exception as e:
        print(f"⚠️ [UCP] Fetch Attempt 1 error: {e}")

    # Attempt 2: Simple (No Headers, mimic shopping.py)
    import time
    time.sleep(1.0)
    try:
        print(f"🔄 [UCP] Retrying fetch without headers for {product_url}...")
        response = httpx.get(product_url, timeout=10.0) # Default httpx behavior
        if response.status_code == 200:
            return response.json()
        print(f"❌ [UCP] Fetch Attempt 2 failed: {response.status_code}")
    except Exception as e:
        print(f"❌ [UCP] Fetch Attempt 2 error: {e}")
        
    return None


def _select_variant(product: dict, variant_id: Optional[str]) -> Optional[dict]:
    variants = product.get("variants", []) if product else []
    if variant_id:
        for variant in variants:
            if str(variant.get("id")) == str(variant_id):
                return variant
    for variant in variants:
        if variant.get("available"):
            return variant
    return variants[0] if variants else None


def _build_line_item_from_product(
    product: dict,
    variant: dict,
    quantity: int,
) -> dict:
    title = product.get("title", "Item")
    variant_title = variant.get("title", "")
    combined_title = f"{title} - {variant_title}".strip(" -")
    variant_id = str(variant.get("id"))
    price = int(variant.get("price", 0))
    image_url = _normalize_image_url(product.get("featured_image"))
    if not image_url:
        images = product.get("images") or []
        if images:
            image_url = _normalize_image_url(images[0])
    subtotal = max(price * max(quantity, 1), 0)
    return {
        "id": f"li-{variant_id}",
        "item": {
            "id": variant_id,
            "title": combined_title,
            "price": price,
            "image_url": image_url,
        },
        "quantity": max(quantity, 1),
        "totals": [{"type": "subtotal", "amount": subtotal}],
    }


def _build_line_item_from_handle(
    product_handle: str,
    store_url: str,
    quantity: int = 1,
    variant_id: Optional[str] = None,
) -> str:
    product = _fetch_product_data(product_handle, store_url)
    
    # Ultimate Fallback: If fetch fails but we have a variant_id, create a dummy item
    # This ensures we can still pass a valid object to _ucp_create_checkout,
    # which will then hit the Auth error and trigger the Cart Permalink fallback.
    if not product:
        if variant_id:
            print(f"⚠️ [UCP] Product fetch failed for {product_handle}, using dummy data for fallback flow.")
            dummy_line_item = {
                "id": f"li-{variant_id}",
                "item": {
                    "id": variant_id,
                    "title": f"Item ({product_handle})", # Fallback title
                    "price": 0, # Price will be zero, but Checkout Fallback will generate link anyway
                    "image_url": "",
                },
                "quantity": max(quantity, 1),
                "totals": [{"type": "subtotal", "amount": 0}],
            }
            return json.dumps(dummy_line_item, ensure_ascii=True)
            
        return f"상품 정보를 가져올 수 없습니다 (URL: {store_url}/products/{product_handle}.js). 잠시 후 다시 시도하거나, 핸들을 확인해주세요. (파일 시스템 검색 금지)"

    variant = _select_variant(product, variant_id)
    if not variant:
        return f"사용 가능한 옵션을 찾지 못했습니다: {product_handle}"

    line_item = _build_line_item_from_product(product, variant, quantity)
    return json.dumps(line_item, ensure_ascii=True)


@tool
def build_line_item_from_handle(
    product_handle: str,
    store_url: str,
    quantity: int = 1,
    variant_id: Optional[str] = None,
) -> str:
    """
    Shopify 상품 handle로 UCP 라인 아이템을 생성합니다.
    """
    return _build_line_item_from_handle(product_handle, store_url, quantity, variant_id)


def _ucp_create_checkout(
    store_url: str,
    line_items_json: str,
    currency: str = "USD",
    auth_token: Optional[str] = None,
) -> str:
    endpoint, meta = resolve_ucp_endpoint(store_url)
    if not endpoint:
        return f"UCP MCP endpoint를 찾을 수 없습니다: {meta.get('error', 'unknown')}"

    try:
        parsed = json.loads(line_items_json)
        if isinstance(parsed, dict):
            line_items = [parsed]
        elif isinstance(parsed, list):
            line_items = parsed
        else:
            return "line_items_json은 객체 또는 배열 JSON이어야 합니다."
    except json.JSONDecodeError:
        return "line_items_json 파싱에 실패했습니다."

    checkout = build_checkout_payload(
        line_items=line_items,
        currency=currency,
        ucp_version=meta.get("ucp_version"),
        capabilities=meta.get("capabilities"),
    )

    headers = build_ucp_auth_headers(auth_token=auth_token)
    try:
        result = ucp_jsonrpc_call(endpoint, "create_checkout", {"checkout": checkout}, headers=headers)
    except Exception as exc:
        return f"UCP 호출 실패: {exc}"

    if result.get("error"):
        error_msg = result["error"].get("message", "")
        error_data = result["error"].get("data", "")
        # Fallback to Cart Permalink for authentication errors
        if error_msg == "AuthenticationFailed" or "Unsupported" in str(error_data):
            try:
                cart_tokens = []
                total_price = 0
                for item in line_items:
                    variant_id = str(item.get("item", {}).get("id", ""))
                    # Remove 'gid://shopify/ProductVariant/' prefix if present
                    if "ProductVariant/" in variant_id:
                        variant_id = variant_id.split("/")[-1]
                    
                    quantity = item.get("quantity", 1)
                    if variant_id:
                        cart_tokens.append(f"{variant_id}:{quantity}")
                        
                        # Estimate total
                        try:
                            price = item.get("item", {}).get("price", 0)
                            total_price += int(price) * int(quantity)
                        except:
                            pass

                if cart_tokens:
                    # Upgrade HTTP to HTTPS for link construction if needed
                    base_url = store_url.rstrip('/')
                    if base_url.startswith("http://"):
                        base_url = "https://" + base_url[7:]
                        
                    fallback_url = f"{base_url}/cart/{','.join(cart_tokens)}"
                    
                    fallback_result = {
                        "id": f"fallback-{uuid.uuid4()}",
                        "url": fallback_url,
                        "currency": currency,
                        "totals": [
                            {"type": "subtotal", "amount": total_price},
                            {"type": "total", "amount": total_price}
                        ],
                        "status": "fallback",
                        "line_items": line_items
                    }
                    return json.dumps(fallback_result)
            except Exception:
                pass # Return original error if fallback fails

        return f"UCP 에러: {result['error']}"

    return json.dumps(result.get("result") or result.get("raw"), ensure_ascii=True)


@tool
def ucp_create_checkout(
    store_url: str,
    line_items_json: str,
    currency: str = "USD",
    auth_token: Optional[str] = None,
) -> str:
    """
    UCP MCP create_checkout 호출을 수행합니다.
    """
    return _ucp_create_checkout(store_url, line_items_json, currency, auth_token)


@tool
def ucp_create_checkout_from_handle(
    product_handle: str,
    store_url: str,
    quantity: int = 1,
    currency: str = "USD",
    variant_id: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> str:
    """
    Shopify handle로 라인 아이템을 만든 후 UCP 체크아웃을 생성합니다.
    """
    line_item_json = _build_line_item_from_handle(
        product_handle=product_handle,
        store_url=store_url,
        quantity=quantity,
        variant_id=variant_id,
    )
    try:
        json.loads(line_item_json)
    except json.JSONDecodeError:
        return line_item_json
    return _ucp_create_checkout(
        store_url=store_url,
        line_items_json=line_item_json,
        currency=currency,
        auth_token=auth_token,
    )


@tool
def ucp_get_checkout(
    store_url: str,
    checkout_id: str,
    auth_token: Optional[str] = None,
) -> str:
    """
    UCP MCP get_checkout 호출을 수행합니다.
    """
    endpoint, meta = resolve_ucp_endpoint(store_url)
    if not endpoint:
        return f"UCP MCP endpoint를 찾을 수 없습니다: {meta.get('error', 'unknown')}"

    headers = build_ucp_auth_headers(auth_token=auth_token)
    try:
        result = ucp_jsonrpc_call(endpoint, "get_checkout", {"id": checkout_id}, headers=headers)
    except Exception as exc:
        return f"UCP 호출 실패: {exc}"

    if result.get("error"):
        return f"UCP 에러: {result['error']}"

    return json.dumps(result.get("result") or result.get("raw"), ensure_ascii=True)


@tool
def ucp_update_checkout(
    store_url: str,
    checkout_id: str,
    checkout_json: str,
    auth_token: Optional[str] = None,
) -> str:
    """
    UCP MCP update_checkout 호출을 수행합니다.
    """
    endpoint, meta = resolve_ucp_endpoint(store_url)
    if not endpoint:
        return f"UCP MCP endpoint를 찾을 수 없습니다: {meta.get('error', 'unknown')}"

    try:
        checkout = json.loads(checkout_json)
        if not isinstance(checkout, dict):
            return "checkout_json은 객체 JSON이어야 합니다."
    except json.JSONDecodeError:
        return "checkout_json 파싱에 실패했습니다."

    headers = build_ucp_auth_headers(auth_token=auth_token)
    try:
        result = ucp_jsonrpc_call(endpoint, "update_checkout", {"id": checkout_id, "checkout": checkout}, headers=headers)
    except Exception as exc:
        return f"UCP 호출 실패: {exc}"

    if result.get("error"):
        return f"UCP 에러: {result['error']}"

    return json.dumps(result.get("result") or result.get("raw"), ensure_ascii=True)


@tool
def ucp_cancel_checkout(
    store_url: str,
    checkout_id: str,
    auth_token: Optional[str] = None,
) -> str:
    """
    UCP MCP cancel_checkout 호출을 수행합니다.
    """
    endpoint, meta = resolve_ucp_endpoint(store_url)
    if not endpoint:
        return f"UCP MCP endpoint를 찾을 수 없습니다: {meta.get('error', 'unknown')}"

    headers = build_ucp_auth_headers(auth_token=auth_token)
    params = {
        "id": checkout_id,
        "idempotency_key": str(uuid.uuid4()),
    }
    try:
        result = ucp_jsonrpc_call(endpoint, "cancel_checkout", params, headers=headers)
    except Exception as exc:
        return f"UCP 호출 실패: {exc}"

    if result.get("error"):
        return f"UCP 에러: {result['error']}"

    return json.dumps(result.get("result") or result.get("raw"), ensure_ascii=True)


def _ucp_complete_checkout(
    store_url: str,
    checkout_id: str,
    payment_json: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> str:
    endpoint, meta = resolve_ucp_endpoint(store_url)
    if not endpoint:
        return f"UCP MCP endpoint를 찾을 수 없습니다: {meta.get('error', 'unknown')}"

    payment_payload: Optional[dict] = None
    if payment_json:
        try:
            parsed = json.loads(payment_json)
            if isinstance(parsed, dict):
                payment_payload = parsed
        except json.JSONDecodeError:
            return "payment_json 파싱에 실패했습니다."

    headers = build_ucp_auth_headers(auth_token=auth_token)
    params = {
        "id": checkout_id,
        "idempotency_key": str(uuid.uuid4()),
    }
    if payment_payload is not None:
        params["payment"] = payment_payload

    try:
        result = ucp_jsonrpc_call(endpoint, "complete_checkout", params, headers=headers)
    except Exception as exc:
        return f"UCP 호출 실패: {exc}"

    if result.get("error"):
        return f"UCP 에러: {result['error']}"

    return json.dumps(result.get("result") or result.get("raw"), ensure_ascii=True)


@tool
def ucp_complete_checkout(
    store_url: str,
    checkout_id: str,
    payment_json: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> str:
    """
    UCP MCP complete_checkout 호출을 수행합니다.
    """
    return _ucp_complete_checkout(store_url, checkout_id, payment_json, auth_token)
