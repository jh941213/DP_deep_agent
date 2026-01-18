from typing import Optional
import json

import httpx
from deepagents.graph import AgentMiddleware
from langchain_core.tools import tool

from shopping_agent.config import ShippingAddress, config
from shopping_agent.exchange_rate import compute_exchange_rate, get_daily_rates
from shopping_agent.shipping import load_shipping_address, save_shipping_address
from shopping_agent.tools.ucp import (
    build_line_item_from_handle,
    get_ucp_capabilities,
    ucp_cancel_checkout,
    ucp_complete_checkout,
    ucp_create_checkout,
    ucp_create_checkout_from_handle,
    ucp_get_checkout,
    ucp_update_checkout,
)


def _normalize_image_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    if url.startswith("//"):
        return f"https:{url}"
    return url


def _fetch_product_image(product_handle: str, store_url: str) -> Optional[str]:
    product_url = f"{store_url.rstrip('/')}/products/{product_handle}.js"
    try:
        response = httpx.get(product_url, timeout=10.0)
        if response.status_code != 200:
            return None
        data = response.json()
        featured = data.get("featured_image")
        if featured:
            return _normalize_image_url(featured)
        images = data.get("images") or []
        if images:
            return _normalize_image_url(images[0])
    except Exception:
        return None
    return None


def _search_product_logic(query: str, store_url: str, limit: int = 5) -> str:
    """Shopify Search API를 사용하여 실제 상품을 검색합니다."""
    search_url = f"{store_url.rstrip('/')}/search/suggest.json"
    params = {
        "q": query,
        "resources[type]": "product",
        "resources[options][unavailable_products]": "last",
        "resources[options][fields]": "title,product_type,variants.title"
    }

    try:
        response = httpx.get(search_url, params=params, timeout=10.0)
        if response.status_code == 200:
            data = response.json()
            products = data.get("resources", {}).get("results", {}).get("products", [])

            if not products:
                return f"🌐 '{query}'에 대한 실시간 검색 결과가 해당 상점에 없습니다."

            display_count = min(limit, len(products))
            output = f"🌐 **실시간 검색 결과 ({len(products)}개 중 {display_count}개 표시):**\n\n"
            product_cards = []
            for p in products[:limit]:
                title = p.get("title", "Unknown")
                handle = p.get("handle")
                url_path = p.get("url") or ""
                absolute_url = f"{store_url.rstrip('/')}{url_path}" if url_path else store_url
                raw_image = p.get("image") or p.get("featured_image")
                image_url = _normalize_image_url(raw_image)
                if not image_url and handle:
                    image_url = _fetch_product_image(handle, store_url)
                price = p.get("price", "N/A")

                output += f"- **{title}**\n"
                output += f"  - 가격: ${price}\n"
                output += f"  - URL: {absolute_url}\n"
                if p.get("id"):
                    output += f"  - ID: `{p.get('id')}`\n"
                if handle:
                    output += f"  - Handle: `{handle}`\n"
                output += "\n"

                product_cards.append({
                    "id": p.get("id"),
                    "title": title,
                    "handle": handle,
                    "url": absolute_url,
                    "price": price,
                    "image": image_url,
                    "store_url": store_url,
                })

            output += "<products>\n"
            output += json.dumps({"products": product_cards}, ensure_ascii=True)
            output += "\n</products>"
            return output
    except Exception as e:
        print(f"Search API Error: {e}")

    return f"'{query}'에 대한 검색 결과를 가져올 수 없습니다."


@tool
def search_product(query: str, store_url: str = "https://monos.com", limit: int = 5) -> str:
    """
    Shopify 기반 쇼핑몰에서 상품을 검색합니다.

    Args:
        query: 검색어 (영문 추천)
        store_url: 상점 베이스 URL (예: 'https://www.everlane.com')
        limit: 반환할 최대 상품 개수 (기본값: 5)

    Returns:
        str: 검색된 상품 목록 또는 에러 메시지
    """
    result = _search_product_logic(query, store_url, limit)

    if "결과가 해당 상점에 없습니다" in result and len(query.split()) > 1:
        broad_query = query.split()[0]
        if broad_query.lower() not in ["the", "a", "an"]:
            result = _search_product_logic(broad_query, store_url, limit)
        elif len(query.split()) > 1:
            result = _search_product_logic(query.split()[1], store_url, limit)

    return result


@tool
def check_product_stock(product_handle: str, store_url: str, size: Optional[str] = None) -> str:
    """
    특정 상품의 실시간 재고와 사이즈 정보를 확인합니다.

    Args:
        product_handle: 상품의 handle (search_product 결과에서 획득)
        store_url: 상점 베이스 URL (예: 'https://www.everlane.com')
        size: 확인하고 싶은 사이즈 (선택 사항)
    """
    product_url = f"{store_url.rstrip('/')}/products/{product_handle}.js"
    try:
        response = httpx.get(product_url, timeout=10.0)
        if response.status_code == 200:
            data = response.json()
            title = data.get("title", product_handle)
            variants = data.get("variants", [])

            if not variants:
                return f"⚠️ **{title}**의 상세 정보를 가져올 수 없습니다."

            options = []
            available_variants = []
            for v in variants:
                if v.get("available"):
                    options.append(v.get("title"))
                    available_variants.append(v)

            if not available_variants:
                return f"❌ **{title}**은(는) 현재 모든 옵션이 품절입니다."

            if size:
                matched = [v for v in available_variants if size.lower() in v["title"].lower()]
                if matched:
                    v = matched[0]
                    price = v.get("price", 0) / 100.0
                    return f"✅ **{title}**의 '{v['title']}' 옵션은 구매 가능합니다. (가격: ${price:.2f})"
                else:
                    return f"⚠️ '{size}' 사이즈는 현재 품절이거나 없습니다. 가능한 옵션: {', '.join(options[:10])}"

            return f"✅ **{title}**은(는) 구매 가능합니다. 가능한 옵션: {', '.join(options[:10])}"

    except Exception as e:
        print(f"Stock Check Error: {e}")

    return f"상품 '{product_handle}'의 재고 정보를 실시간으로 확인할 수 없습니다."


def _format_exchange_rate(rate: float, currency: str) -> str:
    code = currency.upper()
    if code == "KRW":
        return f"{rate:,.1f}"
    if rate >= 100:
        return f"{rate:,.2f}"
    return f"{rate:,.4f}"


@tool
def get_exchange_rate(from_currency: str = "USD", to_currency: str = "KRW") -> str:
    """한국수출입은행 일환율을 조회합니다."""
    auth_key = config.exim_auth_key
    if not auth_key:
        return "환율 API 인증키(EXIM_AUTH_KEY)가 설정되어 있지 않습니다."

    rates, meta = get_daily_rates(auth_key)
    if not rates:
        return "환율 정보를 가져올 수 없습니다."

    rate = compute_exchange_rate(rates, from_currency, to_currency)
    if rate is None:
        return f"환율 정보를 찾을 수 없습니다: {from_currency} → {to_currency}"

    label = "일환율"
    requested_date = meta.get("requested_date")
    data_date = meta.get("date")
    if meta.get("stale"):
        label = f"일환율(캐시 {data_date})"
    elif requested_date and data_date and requested_date != data_date:
        label = f"일환율(최근 영업일 {data_date})"
    elif meta.get("cached"):
        label = "일환율(캐시)"

    formatted = _format_exchange_rate(rate, to_currency)
    payload = {
        "rate": rate,
        "from": from_currency.upper(),
        "to": to_currency.upper(),
        "label": label,
        "date": data_date,
    }
    return (
        f"💱 현재 환율({label}): 1 {from_currency.upper()} = {formatted} {to_currency.upper()}\n"
        f"<exchange_rate>{json.dumps(payload, ensure_ascii=True)}</exchange_rate>"
    )


@tool
def calculate_customs(
    product_price_usd: float,
    shipping_cost_usd: float = 0.0,
    category: str = "general",
    exchange_rate: Optional[float] = None,
) -> str:
    """한국 관세 및 부가세를 예상 계산합니다."""
    if exchange_rate is None:
        return (
            "환율 정보가 필요합니다. 먼저 get_exchange_rate를 호출한 뒤 "
            "<exchange_rate> JSON의 rate 값을 exchange_rate로 전달해 주세요."
        )
    try:
        exchange_rate = float(exchange_rate)
    except (TypeError, ValueError):
        return "exchange_rate 값이 올바르지 않습니다. get_exchange_rate 결과의 rate 값을 사용해 주세요."

    total_usd = product_price_usd + shipping_cost_usd
    total_krw = total_usd * exchange_rate

    if category in ["footwear", "apparel"]:
        duty_free_limit = 200 * exchange_rate
        duty_rate = 0.13
    else:
        duty_free_limit = 150 * exchange_rate
        duty_rate = 0.08

    if total_krw <= duty_free_limit:
        return (
            f"사용 환율: 1 USD = {exchange_rate:,.2f} KRW\n"
            f"합계: ${total_usd:.2f} (₩{total_krw:,.0f})\n"
            "✅ 면세 대상입니다!"
        )

    duty = total_krw * duty_rate
    vat = (total_krw + duty) * 0.10
    return (
        f"사용 환율: 1 USD = {exchange_rate:,.2f} KRW\n"
        f"합계: ${total_usd:.2f} (₩{total_krw:,.0f})\n"
        f"⚠️ 관세: ₩{duty:,.0f}, 부가세: ₩{vat:,.0f}"
    )


@tool
def get_shipping_address_info() -> str:
    """배대지 정보를 반환합니다."""
    address = load_shipping_address()
    return (
        "📍 현재 설정된 배대지: "
        f"{address.street}, {address.city}, {address.state} {address.zip_code}, {address.country}"
    )


@tool
def set_shipping_address(
    street: str,
    city: str,
    state: str,
    zip_code: str,
    country: str = "US",
) -> str:
    """배대지 정보를 저장합니다."""
    address = ShippingAddress(
        street=street,
        city=city,
        state=state,
        zip_code=zip_code,
        country=country,
    )
    save_shipping_address(address)
    return (
        "✅ 배대지 정보가 저장되었습니다: "
        f"{address.street}, {address.city}, {address.state} {address.zip_code}, {address.country}"
    )


class ShoppingToolsMiddleware(AgentMiddleware):
    """직구 쇼핑 관련 도구를 제공하는 미들웨어"""
    tools = [
        search_product,
        check_product_stock,
        get_exchange_rate,
        calculate_customs,
        get_shipping_address_info,
        set_shipping_address,
        get_ucp_capabilities,
        build_line_item_from_handle,
        ucp_create_checkout,
        ucp_create_checkout_from_handle,
        ucp_get_checkout,
        ucp_update_checkout,
        ucp_complete_checkout,
        ucp_cancel_checkout,
    ]
