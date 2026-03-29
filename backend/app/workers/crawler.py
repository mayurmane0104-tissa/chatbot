"""
app/workers/crawler.py
Synchronous website crawler for the TissaTech knowledge base pipeline.

IMPORTANT: This module is intentionally synchronous (no async/await).
Celery workers run in a prefork multiprocessing pool. Using asyncio.run()
inside a Celery task causes silent failures and broken DB connections.
httpx.Client (sync) is used instead of httpx.AsyncClient.

Requirements (add to requirements.txt):
    httpx>=0.27.0
    beautifulsoup4>=4.12.0
    lxml>=5.0.0
    playwright>=1.45.0  (optional but recommended for SPA rendering)
"""
import re
import time
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse, urldefrag

import httpx
import structlog
from bs4 import BeautifulSoup

from app.core.metrics import (
    crawl_duration_seconds,
    crawl_jobs_total,
    crawl_pages_crawled_total,
    crawl_rendered_pages_total,
    crawl_request_errors_total,
)

log = structlog.get_logger()

_STRIP_TAGS = {
    "script", "style", "nav", "header", "footer", "aside",
    "noscript", "iframe", "svg", "form", "button",
}

_SKIP_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".zip", ".tar", ".gz", ".mp4", ".mp3", ".wav", ".csv",
    ".xlsx", ".xls", ".docx", ".doc", ".xml", ".json", ".rss",
    ".ico", ".woff", ".woff2", ".ttf", ".eot",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

MIN_TEXT_LENGTH = 20
MIN_TEXT_BEFORE_RENDER = 80


@dataclass
class CrawledPage:
    url: str
    title: str
    text: str

    @property
    def char_count(self) -> int:
        return len(self.text)


class _PlaywrightRenderer:
    """Lazy Playwright renderer for SPA pages."""

    def __init__(self, timeout_ms: int = 20000):
        self.timeout_ms = timeout_ms
        self._playwright = None
        self._browser = None
        self._context = None
        self._disabled = False

    def _ensure_browser(self) -> bool:
        if self._disabled:
            return False
        if self._browser is not None:
            return True

        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            log.warning("crawler.playwright_not_installed", error=str(exc))
            self._disabled = True
            return False

        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--no-sandbox"],
            )
            self._context = self._browser.new_context(
                user_agent=USER_AGENT,
                ignore_https_errors=True,
            )
            return True
        except Exception as exc:
            log.warning("crawler.playwright_unavailable", error=str(exc))
            self._disabled = True
            self.close()
            return False

    def render(self, url: str) -> Optional[dict]:
        if not self._ensure_browser():
            return None

        page = None
        try:
            page = self._context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            page.wait_for_timeout(450)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(150)

            html = page.content()
            title = page.title() or ""
            links = page.eval_on_selector_all("a[href]", "els => els.map(el => el.href)")
            links = [l for l in links if isinstance(l, str)]
            return {"html": html, "title": title, "links": links}
        except Exception as exc:
            log.warning("crawler.render_failed", url=url, error=str(exc))
            return None
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass

    def close(self) -> None:
        try:
            if self._context is not None:
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass
        self._context = None
        self._browser = None
        self._playwright = None


def _extract_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()

    root = soup.find("main") or soup.find("article") or soup.body or soup

    lines = []
    seen = set()
    for el in root.descendants:
        if el.name in {
            "p", "h1", "h2", "h3", "h4", "h5", "h6",
            "li", "td", "th", "blockquote", "pre",
            "figcaption", "caption", "dt", "dd",
        }:
            text = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
            if len(text) < 12:
                continue
            key = text.lower()
            if key not in seen:
                seen.add(key)
                lines.append(text)

    # Fallback for JS-heavy sites whose meaningful text is not in semantic tags.
    if not lines:
        # Prefer useful metadata before falling back to raw text.
        meta_chunks: list[str] = []
        for meta in soup.find_all("meta"):
            key = (meta.get("name") or meta.get("property") or "").strip().lower()
            if key in {"description", "og:description", "twitter:description", "og:title", "twitter:title"}:
                val = re.sub(r"\s+", " ", (meta.get("content") or "")).strip()
                if len(val) >= 20:
                    meta_chunks.append(val)
        for chunk in meta_chunks:
            k = chunk.lower()
            if k not in seen:
                seen.add(k)
                lines.append(chunk)

        raw_text = root.get_text("\n", strip=True)
        for chunk in raw_text.splitlines():
            text = re.sub(r"\s+", " ", chunk).strip()
            if len(text) < 20:
                continue
            key = text.lower()
            if key not in seen:
                seen.add(key)
                lines.append(text)
            if len(lines) >= 250:
                break

    return title, "\n\n".join(lines)


def _extract_links_from_html(base_url: str, html: str, domain_base: str) -> list[str]:
    links: list[str] = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for a_tag in soup.find_all("a", href=True):
            href = _normalise_url(base_url, a_tag["href"])
            if href and _same_domain(domain_base, href):
                links.append(href)
    except Exception:
        pass
    return links


def _looks_like_spa_shell(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    root_div = soup.find("div", id=re.compile(r"(root|app|__next)", re.I))
    script_count = len(soup.find_all("script"))
    body_text = (soup.body.get_text(" ", strip=True) if soup.body else soup.get_text(" ", strip=True)).strip()
    # A lot of scripts with very little body text usually indicates JS-only shell.
    return bool(root_div) and script_count >= 3 and len(body_text) < 300


def _fetch_urlset_from_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
    """
    Returns (sitemaps, urls)
    """
    sitemaps: list[str] = []
    urls: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return sitemaps, urls

    tag = root.tag.lower()
    locs = [el.text.strip() for el in root.findall(".//{*}loc") if el.text and el.text.strip()]
    if "sitemapindex" in tag:
        sitemaps.extend(locs)
    elif "urlset" in tag:
        urls.extend(locs)
    return sitemaps, urls


def _discover_sitemap_urls(client: httpx.Client, start_url: str, max_urls: int = 200) -> list[str]:
    parsed = urlparse(start_url)
    raw_host = parsed.netloc.lower()
    bare_host = raw_host.lstrip("www.")
    origins = {
        f"{parsed.scheme}://{raw_host}",
        f"https://{bare_host}",
        f"https://www.{bare_host}",
        f"http://{bare_host}",
        f"http://www.{bare_host}",
    }

    sitemap_candidates: list[str] = []
    for origin in origins:
        sitemap_candidates.append(f"{origin}/sitemap.xml")
        try:
            robots = client.get(f"{origin}/robots.txt")
            if robots.status_code == 200 and robots.text:
                for line in robots.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        loc = line.split(":", 1)[1].strip()
                        if loc.startswith("http"):
                            sitemap_candidates.append(loc)
        except Exception as exc:
            log.warning("crawler.robots_fetch_failed", error=str(exc), url=f"{origin}/robots.txt")

    seen_sitemaps: set[str] = set()
    pending_sitemaps: deque[str] = deque(sitemap_candidates)
    urls: list[str] = []

    while pending_sitemaps and len(urls) < max_urls:
        sm_url = pending_sitemaps.popleft()
        if sm_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sm_url)
        try:
            resp = client.get(sm_url)
            if resp.status_code != 200:
                continue
            child_sitemaps, sm_urls = _fetch_urlset_from_sitemap_xml(resp.text)
            for child in child_sitemaps:
                if child not in seen_sitemaps:
                    pending_sitemaps.append(child)
            for u in sm_urls:
                if _same_domain(start_url, u):
                    urls.append(u)
                    if len(urls) >= max_urls:
                        break
        except Exception as exc:
            log.warning("crawler.sitemap_fetch_failed", url=sm_url, error=str(exc))

    deduped = []
    seen = set()
    for u in urls:
        n = _normalise_url(start_url, u)
        if n and n not in seen:
            seen.add(n)
            deduped.append(n)
    return deduped


def _create_http_client(timeout_per_page: float) -> httpx.Client:
    client_kwargs = {
        "headers": {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
        "follow_redirects": True,
        "timeout": httpx.Timeout(connect=8.0, read=timeout_per_page, write=8.0, pool=5.0),
        "limits": httpx.Limits(max_connections=8, max_keepalive_connections=4),
    }
    try:
        return httpx.Client(http2=True, **client_kwargs)
    except ImportError as exc:
        log.warning("crawler.http2_unavailable_fallback_http1", error=str(exc))
        return httpx.Client(http2=False, **client_kwargs)


def _normalise_url(base: str, href: str) -> Optional[str]:
    try:
        full = urljoin(base, href)
        full, _ = urldefrag(full)
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https"):
            return None
        path = parsed.path.lower().rstrip("/")
        if any(path.endswith(ext) for ext in _SKIP_EXTENSIONS):
            return None
        if len(parsed.query) > 200:
            return None
        return full
    except Exception:
        return None


def _same_domain(base_url: str, href: str) -> bool:
    base_host = urlparse(base_url).netloc.lower().lstrip("www.")
    link_host = urlparse(href).netloc.lower().lstrip("www.")
    return base_host == link_host


def _url_visit_key(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().lstrip("www.")
    path = (parsed.path or "/").rstrip("/") or "/"
    query = parsed.query
    return f"{host}{path}?{query}" if query else f"{host}{path}"


def crawl_website(
    start_url: str,
    max_pages: int = 100,
    timeout_per_page: float = 15.0,
    delay_between_requests: float = 0.05,
) -> list[CrawledPage]:
    """
    Synchronously crawl start_url and all internal links up to max_pages.
    Returns list of CrawledPage. Returns [] (does not raise) on connection failure.
    """
    if not start_url.startswith("http"):
        start_url = f"https://{start_url}"

    visited_keys: set[str] = set()
    queued_keys: set[str] = set()
    queue: deque[str] = deque()
    results: list[CrawledPage] = []
    skip_count = 0
    timeout_count = 0
    request_error_count = 0
    rendered_count = 0

    crawl_started_at = time.time()
    log.info("crawler.starting", url=start_url, max_pages=max_pages)

    renderer = _PlaywrightRenderer(timeout_ms=max(int(timeout_per_page * 1000), 10000))

    with _create_http_client(timeout_per_page) as client:
        def enqueue(candidate_url: str) -> None:
            normalized = _normalise_url(start_url, candidate_url)
            if not normalized:
                return
            key = _url_visit_key(normalized)
            if key in visited_keys or key in queued_keys:
                return
            queue.append(normalized)
            queued_keys.add(key)

        enqueue(start_url)

        # Seed from sitemap(s) so SPAs with sparse shell HTML still have page routes to crawl.
        sitemap_urls = _discover_sitemap_urls(client, start_url, max_urls=min(max_pages * 5, 300))
        for s_url in sitemap_urls:
            enqueue(s_url)
        if sitemap_urls:
            log.info("crawler.sitemap_seeded", count=len(sitemap_urls))

        while queue and len(results) < max_pages:
            url = queue.popleft()
            key = _url_visit_key(url)
            queued_keys.discard(key)
            if key in visited_keys:
                continue
            visited_keys.add(key)

            try:
                if len(results) > 0:
                    time.sleep(delay_between_requests)

                resp = client.get(url)
                content_type = resp.headers.get("content-type", "").lower()

                preview = (resp.text[:500] if hasattr(resp, "text") else "").lower()
                looks_html = (
                    "text/html" in content_type
                    or "application/xhtml+xml" in content_type
                    or "<html" in preview
                    or "<!doctype html" in preview
                )
                if resp.status_code != 200 or not looks_html:
                    log.warning("crawler.skip", url=url, status=resp.status_code, ct=content_type)
                    skip_count += 1
                    continue

                html = resp.text
                title, text = _extract_text(html)
                discovered_links = _extract_links_from_html(url, html, start_url)
                visited_keys.add(_url_visit_key(str(resp.url)))

                script_heavy = html.lower().count("<script") >= 4
                needs_render = _looks_like_spa_shell(html) or (
                    len(text.strip()) < MIN_TEXT_BEFORE_RENDER and script_heavy
                )
                if needs_render:
                    rendered = renderer.render(url)
                    if rendered and rendered.get("html"):
                        rendered_count += 1
                        r_title, r_text = _extract_text(rendered["html"])
                        if len(r_text.strip()) > len(text.strip()):
                            text = r_text
                            title = r_title or title
                        for l in rendered.get("links", []):
                            n = _normalise_url(url, l)
                            if n and _same_domain(start_url, n):
                                discovered_links.append(n)

                if len(text.strip()) >= MIN_TEXT_LENGTH:
                    results.append(CrawledPage(url=str(resp.url), title=title or str(resp.url), text=text))
                    log.info("crawler.page_crawled", url=url, chars=len(text), total=len(results))
                else:
                    log.warning("crawler.page_text_too_short", url=url, chars=len(text))
                    skip_count += 1

                # Always discover links, even from sparse pages
                if len(results) < max_pages:
                    for href in discovered_links:
                        enqueue(href)

            except httpx.TimeoutException:
                log.warning("crawler.timeout", url=url)
                timeout_count += 1
            except httpx.RequestError as exc:
                log.warning("crawler.request_error", url=url, error=str(exc))
                request_error_count += 1
            except Exception as exc:
                log.error("crawler.unexpected_error", url=url, error=str(exc), exc_info=True)
                crawl_request_errors_total.labels(kind="unexpected").inc()

    renderer.close()
    crawl_duration_seconds.observe(max(time.time() - crawl_started_at, 0.0))
    crawl_pages_crawled_total.inc(len(results))
    if rendered_count:
        crawl_rendered_pages_total.inc(rendered_count)
    if timeout_count:
        crawl_request_errors_total.labels(kind="timeout").inc(timeout_count)
    if request_error_count:
        crawl_request_errors_total.labels(kind="request_error").inc(request_error_count)
    crawl_jobs_total.labels(status="success" if results else "empty").inc()

    log.info(
        "crawler.finished",
        start_url=start_url,
        pages_crawled=len(results),
        visited=len(visited_keys),
        skipped=skip_count,
        timeouts=timeout_count,
        request_errors=request_error_count,
        rendered=rendered_count,
    )
    return results
