"""Playwright-backed browser controls with DOM snapshots and stable element refs."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_playwright = None
_browser = None
_page = None
_DEFAULT_TIMEOUT_MS = 10_000
_REF_PATTERN = re.compile(r"^E(\d+)$", re.IGNORECASE)
_INTERACTIVE_SELECTOR = (
    "a, button, input, textarea, select, [role='button'], [role='link'], "
    "[role='textbox'], [role='checkbox'], [role='radio'], [role='menuitem'], "
    "[role='option'], [contenteditable='true'], [tabindex]:not([tabindex='-1'])"
)
_VISIBLE_INTERACTIVE_SELECTOR = f":is({_INTERACTIVE_SELECTOR}):visible"


class BrowserUnavailableError(RuntimeError):
    """Raised when Playwright or its browser executable cannot be started."""


def _configure_browser_cache() -> None:
    """Prefer an installed Playwright cache even when LOCALAPPDATA is redirected."""
    configured_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if configured_path:
        return

    candidates = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "ms-playwright")
    candidates.append(Path.home() / "AppData" / "Local" / "ms-playwright")

    for candidate in candidates:
        if candidate.is_dir() and any(candidate.glob("chromium-*")):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(candidate)
            return


def _ensure_page():
    global _playwright, _browser, _page
    _configure_browser_cache()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserUnavailableError(
            "ยังไม่ได้ติดตั้ง Playwright ใน Python environment นี้: "
            "รัน `python -m pip install -r requirements.txt` แล้ว `python -m playwright install chromium`"
        ) from exc

    if _browser is not None and not _browser.is_connected():
        _browser = None
        _page = None
    if _playwright is None:
        _playwright = sync_playwright().start()
    if _browser is None:
        try:
            _browser = _playwright.chromium.launch(headless=False)
        except Exception as exc:
            raise BrowserUnavailableError(
                "เปิด Chromium ของ Playwright ไม่ได้: ติดตั้ง browser ด้วย "
                "`python -m playwright install chromium`"
            ) from exc
    if _page is None or _page.is_closed():
        _page = _browser.new_page()
        _page.set_default_timeout(_DEFAULT_TIMEOUT_MS)
    return _page


def _ref_index(target: str) -> int | None:
    match = _REF_PATTERN.fullmatch(target.strip())
    return int(match.group(1)) if match else None


def _target_locator(page, target: str):
    """Resolve a snapshot ref (E0...) or an explicit CSS selector."""
    index = _ref_index(target)
    if index is not None:
        return page.locator(_VISIBLE_INTERACTIVE_SELECTOR).nth(index)
    if not target.strip():
        raise ValueError("ต้องระบุ element ref เช่น E0 หรือ CSS selector")
    return page.locator(target).first


def open_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("URL ต้องขึ้นต้นด้วย http:// หรือ https://")
    page = _ensure_page()
    page.goto(url, wait_until="domcontentloaded")
    return snapshot()


def snapshot() -> str:
    page = _ensure_page()
    body_text = page.locator("body").inner_text(timeout=5000)[:10_000]
    elements: list[dict[str, Any]] = page.locator(_VISIBLE_INTERACTIVE_SELECTOR).evaluate_all(
        """els => els.slice(0, 120).map((el, i) => {
            const text = (el.innerText || el.value || '').trim().replace(/\\s+/g, ' ').slice(0, 180);
            return {
                ref: `E${i}`,
                tag: el.tagName.toLowerCase(),
                role: el.getAttribute('role') || '',
                text,
                label: el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('title') || '',
                type: el.getAttribute('type') || '',
                href: el.getAttribute('href') || ''
            };
        })"""
    )
    lines = ["PAGE TEXT:", body_text or "(ไม่มีข้อความ)", "", "INTERACTIVE ELEMENTS (ใช้ ref เช่น E0 เป็น selector):"]
    for item in elements:
        details = [f"{item['ref']} <{item['tag']}>"]
        if item["role"]:
            details.append(f"role={item['role']}")
        if item["type"]:
            details.append(f"type={item['type']}")
        if item["label"]:
            details.append(f"label={item['label']!r}")
        if item["text"]:
            details.append(f"text={item['text']!r}")
        if item["href"]:
            details.append(f"href={item['href']!r}")
        lines.append("- " + " ".join(details))
    if not elements:
        lines.append("(ไม่พบ element ที่โต้ตอบได้)")
    return "\n".join(lines)[:16_000]


def click(selector: str) -> str:
    page = _ensure_page()
    _target_locator(page, selector).click()
    return snapshot()


def fill(selector: str, value: str) -> str:
    page = _ensure_page()
    _target_locator(page, selector).fill(value)
    return snapshot()


def press(selector: str, key: str) -> str:
    page = _ensure_page()
    _target_locator(page, selector).press(key)
    return snapshot()


def close() -> None:
    global _playwright, _browser, _page
    if _browser is not None and _browser.is_connected():
        _browser.close()
    if _playwright is not None:
        _playwright.stop()
    _playwright = _browser = _page = None
