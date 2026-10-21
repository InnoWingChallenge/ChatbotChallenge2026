"""Collect the permitted InnoWing web corpus.

The two sites are WordPress installations with public sitemaps. The sitemap is
the primary URL source; a small same-site crawler is retained as a fallback.
Running this module writes ``data/pages.json`` and ``data/images.json`` and
keeps gzip-compressed source HTML under ``data/raw_pages`` for reproducibility.

Run from any directory with::

    python build/scrape.py
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SITES = [
    "https://innowings.engg.hku.hk/innowing1/",
    "https://innoacademy.engg.hku.hk/",
]

USER_AGENT = "InnoWingChallengeCorpusBuilder/1.0 (HKU student project)"
TIMEOUT = 30
DEFAULT_MAX_PAGES = 2_000
DEFAULT_DELAY = 0.15

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw_pages"

# These belong to Innovation Wing Two, which is outside the permitted Wing One
# knowledge source. Query strings, feeds, author archives and WordPress internals
# are discovery noise rather than evidence pages.
WING_TWO_MARKERS = (
    "/innowing-two",
    "/innowing2",
    "/innovation-wing-two",
    "/category/innovation-wing-two",
)
SKIP_PATH_MARKERS = (
    "/wp-admin",
    "/wp-json",
    "/wp-login",
    "/author/",
    "/tag/",
    "/feed/",
)
CONTENT_SELECTORS = (
    ".entry-content",
    "article .elementor-widget-theme-post-content",
    "article",
    "main",
    "#content",
    ".site-main",
)
REMOVE_SELECTORS = (
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    ".cookie-notice-container",
    ".sharedaddy",
    ".post-navigation",
    ".comments-area",
)
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff")
TEXT_BLOCK_TAGS = {"p", "li", "td", "th", "figcaption", "blockquote"}
HEADING_TAGS = {"h1", "h2", "h3", "h4"}


def build_session() -> requests.Session:
    """Return a polite HTTP session with retry handling for transient errors."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": USER_AGENT})
    return session


SESSION = build_session()


def canonicalize_url(url: str, base: str | None = None) -> str:
    """Make an HTTP URL absolute and remove fragments and tracking queries."""
    absolute = urljoin(base or url, url)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return ""
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if not Path(path).suffix and not path.endswith("/"):
        path += "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", ""))


def is_allowed_url(url: str, site_url: str) -> bool:
    """Return whether *url* is an in-scope content page for *site_url*."""
    parsed = urlparse(url)
    site = urlparse(site_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != site.netloc.lower():
        return False
    path = parsed.path.lower()
    if any(marker in path for marker in SKIP_PATH_MARKERS):
        return False
    if parsed.netloc.lower() == "innowings.engg.hku.hk":
        if any(marker in path for marker in WING_TWO_MARKERS):
            return False
    suffix = Path(path).suffix.lower()
    return not suffix or suffix in {".htm", ".html", ".php"}


def _fetch(url: str) -> requests.Response:
    response = SESSION.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response


def _robots_for(site_url: str) -> RobotFileParser:
    robots_url = urljoin(site_url, "/robots.txt")
    parser = RobotFileParser(robots_url)
    try:
        parser.parse(_fetch(robots_url).text.splitlines())
    except requests.RequestException as exc:
        # A missing robots file must not silently forbid the public site. We
        # still constrain requests to the official hosts and known content URLs.
        print(f"robots unavailable: {robots_url} ({exc})")
        parser.parse([])
    return parser


def _sitemap_urls(site_url: str) -> list[str]:
    """Read page/post URLs recursively from a WordPress sitemap index."""
    root_url = urljoin(site_url, "/wp-sitemap.xml")
    pending = [root_url]
    seen_sitemaps: set[str] = set()
    pages: list[str] = []

    while pending:
        sitemap_url = pending.pop(0)
        if sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)
        response = _fetch(sitemap_url)
        root = ElementTree.fromstring(response.content)
        locations = [node.text.strip() for node in root.findall(".//{*}loc") if node.text]

        if root.tag.rsplit("}", 1)[-1] == "sitemapindex":
            # Author and taxonomy sitemaps duplicate the same posts. Their URLs
            # are useful for browsing but should not become retrieval evidence.
            pending.extend(
                loc for loc in locations
                if "wp-sitemap-posts-post-" in loc or "wp-sitemap-posts-page-" in loc
            )
        else:
            pages.extend(locations)

    return pages


def _fallback_crawl(start_url: str, max_pages: int) -> list[str]:
    """Discover same-site links when a sitemap cannot be read."""
    seen: set[str] = set()
    start = canonicalize_url(start_url)
    queued = {start}
    queue = [start]
    output: list[str] = []

    while queue and len(output) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        if not is_allowed_url(url, start_url):
            continue
        try:
            response = _fetch(url)
        except requests.RequestException as exc:
            print(f"discovery skipped: {url} ({exc})")
            continue
        output.append(url)
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select("a[href]"):
            link = canonicalize_url(anchor.get("href", ""), url)
            if link and link not in seen and link not in queued and is_allowed_url(link, start_url):
                queue.append(link)
                queued.add(link)

    return output


def crawl(start_url: str, max_pages: int = DEFAULT_MAX_PAGES) -> list[str]:
    """Return permitted page URLs, preferring the site's WordPress sitemap."""
    robots = _robots_for(start_url)
    try:
        candidates = _sitemap_urls(start_url)
    except (requests.RequestException, ElementTree.ParseError) as exc:
        print(f"sitemap unavailable for {start_url}; using link discovery ({exc})")
        candidates = _fallback_crawl(start_url, max_pages)

    output: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = canonicalize_url(candidate)
        if not url or url in seen or not is_allowed_url(url, start_url):
            continue
        if not robots.can_fetch(USER_AGENT, url):
            print(f"robots excluded: {url}")
            continue
        seen.add(url)
        output.append(url)
        if len(output) >= max_pages:
            break
    return output


def _content_root(soup: BeautifulSoup) -> Tag:
    for selector in CONTENT_SELECTORS:
        node = soup.select_one(selector)
        if node and node.get_text(" ", strip=True):
            return node
    return soup.body or soup


def _legacy_clean_text(root: Tag) -> str:
    """Extract readable text while retaining useful list/table boundaries."""
    for selector in REMOVE_SELECTORS:
        for node in root.select(selector):
            node.decompose()
    for br in root.select("br"):
        br.replace_with("\n")

    lines: list[str] = []
    previous = ""
    for raw_line in root.get_text("\n", strip=True).splitlines():
        # Some legacy WordPress records contain a replacement character plus
        # "C" where an en dash was intended.
        line = re.sub(r"\s+", " ", raw_line).replace("�C", "–").strip()
        if line and line != previous:
            lines.append(line)
            previous = line
    return "\n".join(lines)


def _srcset_largest(srcset: str) -> str:
    choices: list[tuple[float, str]] = []
    for item in srcset.split(","):
        parts = item.strip().split()
        if not parts:
            continue
        score = 0.0
        if len(parts) > 1:
            descriptor = parts[-1].lower()
            try:
                score = float(descriptor[:-1]) if descriptor.endswith(("w", "x")) else 0.0
            except ValueError:
                score = 0.0
        choices.append((score, parts[0]))
    return max(choices, default=(0.0, ""), key=lambda choice: choice[0])[1]


def _image_source(img: Tag, page_url: str) -> str:
    """Choose the original/largest image URL exposed by a WordPress page."""
    linked = img.find_parent("a", href=True)
    linked_url = linked.get("href", "") if linked else ""
    candidates = [
        img.get("data-orig-file", ""),
        linked_url if urlparse(linked_url).path.lower().endswith(IMAGE_EXTENSIONS) else "",
        _srcset_largest(img.get("srcset", "")),
        img.get("data-src", ""),
        img.get("data-lazy-src", ""),
        img.get("data-original", ""),
        img.get("src", ""),
    ]
    for candidate in candidates:
        candidate = candidate.strip()
        if candidate and not candidate.startswith("data:"):
            return urljoin(page_url, candidate)
    return ""


def _image_records(root: Tag, page_url: str) -> list[dict]:
    images: list[dict] = []
    seen: set[str] = set()
    for position, img in enumerate(root.select("img")):
        src = _image_source(img, page_url)
        if not src or src in seen:
            continue
        width = img.get("width", "")
        height = img.get("height", "")
        if str(width).isdigit() and str(height).isdigit() and int(width) <= 2 and int(height) <= 2:
            continue
        seen.add(src)
        figure = img.find_parent("figure")
        caption_node = figure.select_one("figcaption") if figure else None
        images.append({
            "src": src,
            "alt": re.sub(r"\s+", " ", img.get("alt", "")).strip(),
            "caption": caption_node.get_text(" ", strip=True) if caption_node else "",
            "title": img.get("title", "").strip(),
            "width": int(width) if str(width).isdigit() else None,
            "height": int(height) if str(height).isdigit() else None,
            "page": page_url,
            "position": position,
        })
    return images


def _meta_content(soup: BeautifulSoup, *selectors: str) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node and node.get("content"):
            return node["content"].strip()
    return ""


def _legacy_clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).replace("�C", "–").strip()
    return re.sub(
        r"\s+(?:–|—|-|\|)\s+(?:Innovation Academy|Innovation Wing)$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()


def _normalise_text(value: str) -> str:
    """Normalise whitespace and common legacy WordPress encoding damage."""
    value = unicodedata.normalize("NFKC", value)
    for broken, replacement in {
        "\ufffdC": "\u2013",
        "\ufffd\ufffds": "'s",
        "\u951f\u7dba": "\u2013",
    }.items():
        value = value.replace(broken, replacement)
    return re.sub(r"\s+", " ", value).strip()


def _clean_content_copy(root: Tag) -> Tag:
    """Return a disposable copy with navigation and executable content removed."""
    copy = BeautifulSoup(str(root), "html.parser")
    clean = copy.find()
    if clean is None:
        return copy
    for selector in REMOVE_SELECTORS:
        for node in clean.select(selector):
            node.decompose()
    return clean


def _clean_text(root: Tag) -> str:
    """Extract readable text while retaining useful list/table boundaries."""
    for br in root.select("br"):
        br.replace_with("\n")
    lines: list[str] = []
    previous = ""
    for raw_line in root.get_text("\n", strip=True).splitlines():
        line = _normalise_text(raw_line)
        if line and line != previous:
            lines.append(line)
            previous = line
    return "\n".join(lines)


def _clean_title(title: str) -> str:
    title = _normalise_text(title)
    return re.sub(
        r"\s+(?:[-\u2013\u2014|])\s+(?:Innovation Academy|Innovation Wing)$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()


def _section_records(root: Tag) -> list[dict]:
    """Preserve semantic heading boundaries for retrieval-time chunking."""
    sections: list[dict] = []
    current: dict = {"heading": "", "level": 0, "text": []}

    def flush() -> None:
        text = "\n".join(current["text"]).strip()
        if text:
            sections.append({
                "heading": current["heading"],
                "level": current["level"],
                "text": text,
            })

    for node in root.find_all([*HEADING_TAGS, *TEXT_BLOCK_TAGS]):
        if node.name in TEXT_BLOCK_TAGS and node.find_parent(TEXT_BLOCK_TAGS):
            continue
        value = _normalise_text(node.get_text(" ", strip=True))
        if not value:
            continue
        if node.name in HEADING_TAGS:
            flush()
            current = {"heading": value, "level": int(node.name[1]), "text": []}
        elif not current["text"] or current["text"][-1] != value:
            current["text"].append(value)
    flush()
    return sections


def _json_ld_dates(soup: BeautifulSoup) -> tuple[str, str]:
    """Return publication and modification dates found in JSON-LD metadata."""
    published = ""
    modified = ""

    def visit(value: object) -> None:
        nonlocal published, modified
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            if not published and isinstance(value.get("datePublished"), str):
                published = value["datePublished"].strip()
            if not modified and isinstance(value.get("dateModified"), str):
                modified = value["dateModified"].strip()
            for item in value.values():
                if isinstance(item, (dict, list)):
                    visit(item)

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            visit(json.loads(script.string or script.get_text()))
        except (json.JSONDecodeError, TypeError):
            continue
    return published, modified


def _is_wing_two_page(page: dict) -> bool:
    if page["site"] != "innowings.engg.hku.hk":
        return False
    evidence = " ".join([page["title"], *page["categories"], page["text"]]).lower()
    return (
        "innovation wing two" in evidence
        or "tam wing fan innovation wing two" in evidence
    )


def extract(html: str, url: str, retrieved_at: str | None = None) -> dict:
    """Extract clean text, provenance metadata and original image references."""
    soup = BeautifulSoup(html, "html.parser")
    canonical_node = soup.select_one('link[rel="canonical"][href]')
    canonical_url = canonicalize_url(canonical_node["href"] if canonical_node else url, url)
    root = _content_root(soup)

    # Collect images before removing forms/navigation from the selected content.
    images = _image_records(root, canonical_url)
    heading = root.select_one("h1")
    title = heading.get_text(" ", strip=True) if heading else ""
    if not title:
        title = _meta_content(soup, 'meta[property="og:title"]')
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)

    categories = []
    for anchor in soup.select(
        'a[rel~="category"], a[rel~="tag"], a[href*="/category/"]'
    ):
        label = anchor.get_text(" ", strip=True)
        if label and label not in categories:
            categories.append(label)

    clean_root = _clean_content_copy(root)
    sections = _section_records(clean_root)
    text = _clean_text(clean_root)
    json_published, json_modified = _json_ld_dates(soup)
    published = _meta_content(
        soup, 'meta[property="article:published_time"]', 'meta[name="date"]'
    ) or json_published
    modified = _meta_content(soup, 'meta[property="article:modified_time"]') or json_modified

    return {
        "url": canonical_url,
        "title": _clean_title(title),
        "text": text,
        "sections": sections,
        "images": images,
        "site": urlparse(canonical_url).netloc,
        "content_type": (
            "post" if _meta_content(soup, 'meta[property="og:type"]') == "article" else "page"
        ),
        "categories": categories,
        "published_at": published,
        "modified_at": modified,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
        "raw_id": hashlib.sha256(canonical_url.encode("utf-8")).hexdigest(),
    }


def _raw_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return RAW_DIR / f"{digest}.html.gz"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def scrape(max_pages: int = DEFAULT_MAX_PAGES, delay: float = DEFAULT_DELAY,
           save_raw: bool = True) -> tuple[list[dict], list[dict]]:
    """Fetch the configured sites and return deduplicated pages and images."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if save_raw:
        RAW_DIR.mkdir(parents=True, exist_ok=True)

    urls: list[str] = []
    for site in SITES:
        found = crawl(site, max_pages=max_pages)
        print(f"discovered {len(found)} pages from {urlparse(site).netloc}")
        urls.extend(found)

    pages: list[dict] = []
    seen_pages: set[str] = set()
    for number, url in enumerate(urls, start=1):
        try:
            response = _fetch(url)
            content_type = response.headers.get("Content-Type", "")
            if "html" not in content_type.lower():
                print(f"skipped non-HTML: {url} ({content_type})")
                continue
            retrieved_at = datetime.now(timezone.utc).isoformat()
            page = extract(response.text, url, retrieved_at)
            if page["url"] in seen_pages or not page["text"]:
                continue
            # Bare WordPress posts can belong to Wing Two. Category metadata is
            # a stronger signal than the slug, so exclude them after parsing.
            if _is_wing_two_page(page):
                print(f"excluded Wing Two page: {url}")
                continue
            seen_pages.add(page["url"])
            pages.append(page)
            if save_raw:
                with gzip.open(_raw_path(page["url"]), "wt", encoding="utf-8") as handle:
                    handle.write(response.text)
            if number % 25 == 0:
                print(f"processed {number}/{len(urls)} URLs")
            if delay:
                time.sleep(delay)
        except (requests.RequestException, OSError, UnicodeError) as exc:
            print(f"skipped: {url} ({type(exc).__name__}: {exc})")

    images: list[dict] = []
    seen_images: set[tuple[str, str]] = set()
    for page in pages:
        for image in page["images"]:
            key = (image["src"], image["page"])
            if key not in seen_images:
                images.append(image)
                seen_images.add(key)

    _write_json(DATA_DIR / "pages.json", pages)
    _write_json(DATA_DIR / "images.json", images)
    print(f"wrote {len(pages)} pages and {len(images)} image records to {DATA_DIR}")
    return pages, images


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                        help="maximum pages per site (default: %(default)s)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help="seconds between page requests (default: %(default)s)")
    parser.add_argument("--no-raw", action="store_true",
                        help="do not save gzip-compressed source HTML")
    args = parser.parse_args()
    scrape(max_pages=args.max_pages, delay=max(0.0, args.delay), save_raw=not args.no_raw)


if __name__ == "__main__":
    main()
