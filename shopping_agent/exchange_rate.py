from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
import json

import httpx

EXIM_API_URL = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"
_CACHE_FILENAME = "exchange_rates.json"


def _korea_today_str() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(timezone.utc).astimezone(kst).strftime("%Y%m%d")


def _default_cache_path(cache_dir: Optional[Path] = None) -> Path:
    base_dir = cache_dir or (Path(__file__).resolve().parent / ".cache")
    return base_dir / _CACHE_FILENAME


def _read_cache(cache_path: Path) -> Optional[dict]:
    if not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cache(cache_path: Path, date_str: str, rates: dict[str, float]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date_str,
        "rates": rates,
        "source": "koreaexim",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    tmp_path = cache_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    tmp_path.replace(cache_path)


def _parse_rate_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text == "0":
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _normalize_currency_unit(cur_unit: str) -> tuple[str, float]:
    unit = 1.0
    base = cur_unit.strip()
    if "(" in base and base.endswith(")"):
        start = base.find("(")
        unit_text = base[start + 1 : -1].strip()
        base = base[:start].strip()
        try:
            unit = float(unit_text.replace(",", ""))
        except ValueError:
            unit = 1.0
    return base.upper(), unit


def _fetch_rates_for_date(date_str: str, auth_key: str, timeout: float) -> dict[str, float]:
    response = httpx.get(
        EXIM_API_URL,
        params={"authkey": auth_key, "searchdate": date_str, "data": "AP01"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Unexpected response format")

    if payload and "result" in payload[0] and "cur_unit" not in payload[0]:
        raise ValueError(f"API error result: {payload[0].get('result')}")

    rates: dict[str, float] = {}
    for item in payload:
        cur_unit = item.get("cur_unit") or item.get("CUR_UNIT")
        deal_base = item.get("deal_bas_r") or item.get("DEAL_BAS_R")
        if not cur_unit:
            continue
        raw_rate = _parse_rate_value(deal_base)
        if raw_rate is None:
            continue
        code, unit = _normalize_currency_unit(cur_unit)
        if unit <= 0:
            continue
        rate = raw_rate / unit
        if rate > 0:
            rates[code] = rate

    if not rates:
        raise ValueError("No rate data")

    rates.setdefault("KRW", 1.0)
    return rates


def get_daily_rates(
    auth_key: str,
    date_str: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    timeout: float = 10.0,
    lookback_days: int = 7,
) -> tuple[Optional[dict[str, float]], dict]:
    requested_date = date_str or _korea_today_str()
    meta = {
        "requested_date": requested_date,
        "date": requested_date,
        "cached": False,
        "stale": False,
        "source": "koreaexim",
    }
    cache_path = _default_cache_path(cache_dir)
    cached = _read_cache(cache_path)

    if cached and cached.get("date") == requested_date and isinstance(cached.get("rates"), dict):
        meta["cached"] = True
        return cached["rates"], meta

    dates_to_try = [requested_date]
    if date_str is None and lookback_days > 0:
        base = datetime.strptime(requested_date, "%Y%m%d")
        for offset in range(1, lookback_days + 1):
            dates_to_try.append((base - timedelta(days=offset)).strftime("%Y%m%d"))

    last_error: Optional[str] = None
    for idx, candidate_date in enumerate(dates_to_try):
        if cached and cached.get("date") == candidate_date and isinstance(cached.get("rates"), dict):
            meta["cached"] = True
            meta["date"] = candidate_date
            if candidate_date != requested_date:
                meta["lookback_days"] = idx
            return cached["rates"], meta

        try:
            rates = _fetch_rates_for_date(candidate_date, auth_key, timeout)
            _write_cache(cache_path, candidate_date, rates)
            meta["date"] = candidate_date
            if candidate_date != requested_date:
                meta["lookback_days"] = idx
            return rates, meta
        except Exception as exc:
            last_error = str(exc)
            if str(exc) != "No rate data":
                break

    if cached and isinstance(cached.get("rates"), dict):
        meta["cached"] = True
        meta["stale"] = True
        meta["date"] = cached.get("date", requested_date)
        if meta["date"] != requested_date:
            try:
                base = datetime.strptime(requested_date, "%Y%m%d")
                cached_dt = datetime.strptime(meta["date"], "%Y%m%d")
                meta["lookback_days"] = (base - cached_dt).days
            except Exception:
                pass
        if last_error:
            meta["error"] = last_error
        return cached["rates"], meta

    if last_error:
        meta["error"] = last_error
    return None, meta


def compute_exchange_rate(
    rates: dict[str, float],
    from_currency: str,
    to_currency: str,
) -> Optional[float]:
    from_code = from_currency.strip().upper()
    to_code = to_currency.strip().upper()

    if from_code == to_code:
        return 1.0
    if from_code not in rates or to_code not in rates:
        return None
    from_rate = rates.get(from_code, 0.0)
    to_rate = rates.get(to_code, 0.0)
    if from_rate <= 0 or to_rate <= 0:
        return None
    return from_rate / to_rate
