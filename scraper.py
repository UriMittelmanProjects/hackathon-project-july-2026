import os
import re
from dataclasses import dataclass
from typing import Optional

import httpx

APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
APIFY_BASE_URL = "https://api.apify.com/v2"

# sian.agency/instagram-ai-transcript-extractor gives richer output (captions,
# engagement metrics, word-level timestamps) and runs faster, but is a
# pay-per-event actor that started requiring payment authorization on Apify's
# console after its free trial allotment ran out (HTTP 402 x402-payment-required).
# Using crawlerbros/instagram-transcript-scraper instead since it works on the
# free tier - switch back to sian.agency once billing is set up for it.
INSTAGRAM_ACTOR = "crawlerbros~instagram-transcript-scraper"


class ScrapeError(Exception):
    """Raised when a scraper actor fails outright (bad URL, private post, actor error)."""


class UnsupportedPlatformError(Exception):
    """Raised when the URL's platform doesn't have a scraper wired up yet."""


@dataclass
class ScrapeResult:
    platform: str
    content: Optional[str]  # transcript or post text; None if nothing usable found
    no_content_reason: Optional[str]  # set when content is None
    raw: dict


_PLATFORM_PATTERNS = [
    ("instagram", re.compile(r"instagram\.com", re.I)),
    ("facebook", re.compile(r"facebook\.com|fb\.watch", re.I)),
    ("tiktok", re.compile(r"tiktok\.com", re.I)),
    ("x", re.compile(r"(?:twitter|x)\.com", re.I)),
    ("youtube", re.compile(r"youtube\.com|youtu\.be", re.I)),
]


def detect_platform(url: str) -> Optional[str]:
    for platform, pattern in _PLATFORM_PATTERNS:
        if pattern.search(url):
            return platform
    return None


async def scrape(url: str) -> ScrapeResult:
    platform = detect_platform(url)
    if platform is None:
        raise UnsupportedPlatformError(
            "Could not determine the platform for this URL. Supported platforms: "
            "Instagram, Facebook, TikTok, X, YouTube."
        )

    if platform == "instagram":
        return await _scrape_instagram(url)

    raise UnsupportedPlatformError(
        f"The scraper for {platform} is not configured yet. Currently only "
        f"Instagram posts are supported."
    )


async def _scrape_instagram(url: str) -> ScrapeResult:
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"{APIFY_BASE_URL}/acts/{INSTAGRAM_ACTOR}/run-sync-get-dataset-items",
            params={"token": APIFY_API_TOKEN},
            json={"videoUrls": [url]},
        )

    if resp.status_code != 201:
        raise ScrapeError(f"Apify actor call failed with status {resp.status_code}: {resp.text[:500]}")

    items = resp.json()
    if not items:
        raise ScrapeError("Apify actor returned no results for this URL.")

    item = items[0]

    if item.get("status") == "error" or item.get("errMsg"):
        raise ScrapeError(item.get("errMsg", "Unknown scraper error."))

    transcript = (item.get("fullText") or "").strip()
    description = (item.get("postDescription") or "").strip()

    sections = []
    if description:
        sections.append(f"Post caption/description:\n{description}")
    if transcript:
        sections.append(f"Spoken transcript:\n{transcript}")
    content = "\n\n".join(sections) or None

    if content is None:
        return ScrapeResult(
            platform="instagram",
            content=None,
            no_content_reason="no_content",
            raw=item,
        )

    return ScrapeResult(
        platform="instagram",
        content=content,
        no_content_reason=None,
        raw=item,
    )
