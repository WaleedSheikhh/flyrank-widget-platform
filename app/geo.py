import os
import httpx
from typing import Optional, Tuple

GEO_TIMEOUT_SECONDS = 3.0


def _use_mocks() -> bool:
    return os.getenv("GEO_USE_MOCKS", "true").lower() == "true"


def _provider_a_down() -> bool:
    return os.getenv("GEO_PROVIDER_A_DOWN", "false").lower() == "true"


def _provider_b_down() -> bool:
    return os.getenv("GEO_PROVIDER_B_DOWN", "false").lower() == "true"


async def _mock_provider_a(ip: str) -> dict:
    return {"country": "United States", "city": "Mountain View"}


async def _mock_provider_b(ip: str) -> dict:
    return {"country": "United States", "city": "San Francisco"}


async def _real_provider_a(ip: str) -> dict:
    # ip-api.com — free, no key, 45 req/min
    async with httpx.AsyncClient(timeout=GEO_TIMEOUT_SECONDS) as client:
        resp = await client.get(f"http://ip-api.com/json/{ip}")
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("status") != "success":
            raise ValueError(f"ip-api.com failed: {payload}")
        return {"country": payload.get("country"), "city": payload.get("city")}


async def _real_provider_b(ip: str) -> dict:
    # ipapi.co — free tier, ~1000/day, no key
    async with httpx.AsyncClient(timeout=GEO_TIMEOUT_SECONDS) as client:
        resp = await client.get(f"https://ipapi.co/{ip}/json/")
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("error"):
            raise ValueError(f"ipapi.co failed: {payload}")
        return {"country": payload.get("country_name"), "city": payload.get("city")}


async def enrich_ip(ip: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Try provider A, then provider B, then give up.
    Returns (country, city, provider_used) — all None if both fail or ip is missing.
    Never raises: a broken/timed-out provider degrades the submission, never breaks it.
    """
    if not ip:
        return None, None, None

    provider_a = _mock_provider_a if _use_mocks() else _real_provider_a
    provider_b = _mock_provider_b if _use_mocks() else _real_provider_b

    if not _provider_a_down():
        try:
            result = await provider_a(ip)
            return result.get("country"), result.get("city"), "A"
        except Exception:
            pass  # fall through to B

    if not _provider_b_down():
        try:
            result = await provider_b(ip)
            return result.get("country"), result.get("city"), "B"
        except Exception:
            pass  # fall through to no-geo

    return None, None, None