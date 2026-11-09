"""Small MediaWiki API client with an on-disk cache."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable, Optional

__all__ = ["WikiClient", "WikiError", "DEFAULT_API"]

DEFAULT_API = "https://sims.fandom.com/api.php"
_USER_AGENT = "sims4-sdk/0.3 (wiki validation)"


class WikiError(RuntimeError):
    """Raised when the wiki API cannot be reached or returns invalid JSON."""


class WikiClient:
    def __init__(
        self,
        *,
        api_url: str = DEFAULT_API,
        cache_dir: str | Path | None = None,
        delay: float = 0.15,
    ):
        self.api_url = api_url
        self.cache_dir = Path(cache_dir) if cache_dir is not None else Path(".cache/wiki")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self._last_request = 0.0

    # ------------------------------------------------------------------
    # transport + cache
    # ------------------------------------------------------------------
    def _cache_file(self, params: dict) -> Path:
        payload = json.dumps(params, sort_keys=True, ensure_ascii=False).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        return self.cache_dir / "requests" / f"{digest}.json"

    def _request(self, params: dict) -> dict:
        full = {**params, "format": "json", "formatversion": "2"}
        cache_file = self._cache_file(full)
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        url = self.api_url + "?" + urllib.parse.urlencode(full)
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise WikiError(f"wiki request failed: {exc}") from exc
        finally:
            self._last_request = time.monotonic()

        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    # ------------------------------------------------------------------
    # pages
    # ------------------------------------------------------------------
    def fetch_page(self, title: str) -> Optional[str]:
        """Fetch one page's wikitext, or ``None`` when it does not exist."""
        data = self._request(
            {
                "action": "parse",
                "page": title,
                "prop": "wikitext",
                "redirects": "1",
            }
        )
        if "parse" not in data:
            return None
        return data["parse"]["wikitext"]

    def fetch_pages(self, titles: Iterable[str], *, batch_size: int = 50) -> dict[str, str]:
        """Fetch many pages in batches; returns resolved title -> wikitext."""
        requested = [title for title in dict.fromkeys(titles) if title]
        result: dict[str, str] = {}
        for start in range(0, len(requested), batch_size):
            batch = requested[start : start + batch_size]
            data = self._request(
                {
                    "action": "query",
                    "prop": "revisions",
                    "rvprop": "content",
                    "rvslots": "main",
                    "titles": "|".join(batch),
                    "redirects": "1",
                }
            )
            pages = data.get("query", {}).get("pages", [])
            for page in pages:
                if page.get("missing"):
                    continue
                revisions = page.get("revisions") or []
                if not revisions:
                    continue
                content = revisions[0].get("slots", {}).get("main", {}).get("content")
                if content:
                    result[page.get("title", "")] = content
        return result

    # ------------------------------------------------------------------
    # listings
    # ------------------------------------------------------------------
    def category_members(
        self,
        category: str,
        *,
        include_subcategories: bool = True,
        limit: int = 500,
    ) -> list[str]:
        """Return page (and optionally subcategory) titles in a category."""
        if not category.lower().startswith("category:"):
            category = f"Category:{category}"
        cmtype = "page|subcat" if include_subcategories else "page"
        members: list[str] = []
        cont: dict = {}
        while len(members) < limit:
            data = self._request(
                {
                    "action": "query",
                    "list": "categorymembers",
                    "cmtitle": category,
                    "cmlimit": "max",
                    "cmtype": cmtype,
                    **cont,
                }
            )
            for member in data.get("query", {}).get("categorymembers", []):
                members.append(member["title"])
            cont = data.get("continue", {})
            if not cont:
                break
        return members[:limit]

    def category_tree_pages(self, category: str, *, limit: int = 5000) -> list[str]:
        """Recursively collect pages from a category and its subcategories."""
        seen_categories: set[str] = set()
        pages: list[str] = []
        queue = [category]
        while queue and len(pages) < limit:
            current = queue.pop(0)
            if current in seen_categories:
                continue
            seen_categories.add(current)
            for member in self.category_members(current, include_subcategories=True, limit=500):
                if member.lower().startswith("category:"):
                    queue.append(member)
                else:
                    pages.append(member)
        return pages[:limit]

    def page_links(self, title: str, *, namespace: int = 0, limit: int = 5000) -> list[str]:
        links: list[str] = []
        cont: dict = {}
        while len(links) < limit:
            data = self._request(
                {
                    "action": "query",
                    "prop": "links",
                    "titles": title,
                    "plnamespace": namespace,
                    "pllimit": "max",
                    **cont,
                }
            )
            pages = data.get("query", {}).get("pages", [])
            for page in pages:
                for link in page.get("links", []):
                    links.append(link["title"])
            cont = data.get("continue", {})
            if not cont:
                break
        return list(dict.fromkeys(links))[:limit]

    def search(self, query: str, *, limit: int = 10) -> list[str]:
        data = self._request(
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
            }
        )
        return [item["title"] for item in data.get("query", {}).get("search", [])]
