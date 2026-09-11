"""Scraper. STUB. Workshop 1 block 4.

Crawl both websites, extract the readable text, and collect image
records in the same pass. Run this file directly to (re)build
data/pages.json and data/images.json.

Check for /sitemap.xml before writing a crawler. If it exists it lists
every page and you can skip the crawl entirely.
"""
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SITES = [
    # TODO: the two Inno Wing sites you were given
]


def crawl(start_url: str, max_pages: int = 500) -> list[str]:
    """Return every page URL on the same site as start_url."""
    seen, queue, out = set(), [start_url], []
    domain = urlparse(start_url).netloc

    while queue and len(out) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            html = requests.get(url, timeout=20).text
        except Exception:
            continue
        out.append(url)

        # TODO find the links on this page and add the internal ones to
        # TODO queue, something like:
        # for a in BeautifulSoup(html, "html.parser").select("a[href]"):
        #     link = urljoin(url, a["href"]).split("#")[0]
        #     if urlparse(link).netloc == domain and link not in seen:
        #         queue.append(link)

    return out


def extract(html: str, url: str) -> dict:
    """Return {"url", "title", "text", "images": [...]} for one page.

    soup.get_text() on the whole page returns the navigation menu and
    footer on every page. Those near-identical fragments become chunks
    that look moderately similar to every query and crowd real results
    out of your top five. Open the site, right-click the content, choose
    Inspect, and find the element that actually wraps it.
    """
    soup = BeautifulSoup(html, "html.parser")

    # TODO replace this with the element that holds the content, e.g.
    # TODO soup.select_one("main") or soup.select_one("#content")
    body = soup

    images = []
    for img in soup.select("img"):
        src = img.get("src")
        if not src:
            continue
        fig = img.find_parent("figure")
        images.append({
            "src":     urljoin(url, src),     # relative -> absolute
            "alt":     img.get("alt", ""),
            "caption": (fig.find("figcaption").get_text(strip=True)
                        if fig and fig.find("figcaption") else ""),
            "page":    url,
        })

    return {
        "url":    url,
        "title":  soup.title.get_text(strip=True) if soup.title else "",
        "text":   body.get_text(" ", strip=True),
        "images": images,
    }


if __name__ == "__main__":
    pages = []
    for site in SITES:
        for url in crawl(site):
            try:
                pages.append(extract(requests.get(url, timeout=20).text, url))
            except Exception as exc:
                print("skipped", url, exc)

    Path("data").mkdir(exist_ok=True)
    Path("data/pages.json").write_text(json.dumps(pages, indent=1))

    images = [im for p in pages for im in p["images"]]
    Path("data/images.json").write_text(json.dumps(images, indent=1))

    print(f"{len(pages)} pages, {len(images)} images")
