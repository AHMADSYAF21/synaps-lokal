"""
Web Search Engine — DuckDuckGo (no API key needed)
Search → fetch → extract → summarise → return clean results
Falls back to SearXNG or Brave Search if DDG fails
"""

import asyncio
import json
import logging
import re
import time
import urllib.parse
from typing import Dict, List, Optional

import httpx

log = logging.getLogger("synapse.websearch")

DDG_URL  = "https://api.duckduckgo.com/"
DDG_HTML = "https://html.duckduckgo.com/html/"
UA       = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"

SEARCH_SUMMARISE_SYSTEM = """You are a search result synthesiser.
Given web search results, produce a concise, factual summary.
Cite sources by number [1], [2] etc. Be direct and informative.
If results are contradictory, note both views."""


class SearchResult:
    def __init__(self, title: str, url: str, snippet: str, source: str = ""):
        self.title   = title
        self.url     = url
        self.snippet = snippet
        self.source  = source


class WebSearchEngine:
    def __init__(self, llm):
        self.llm     = llm
        self._client = httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": UA},
            follow_redirects=True,
        )
        self._cache: Dict[str, Dict] = {}  # query → results
        self._cache_ttl = 300              # 5 min cache

    # ── Main Search Entry ─────────────────────────────────────────────────────
    async def search(self, query: str, n: int = 8,
                     summarise: bool = True) -> Dict:
        """Search the web, optionally summarise with LLM."""
        # Cache check
        cache_key = f"{query}:{n}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached["ts"] < self._cache_ttl:
                return cached["data"]

        results = await self._ddg_search(query, n)
        if not results:
            results = await self._ddg_html_search(query, n)

        formatted = [{"title": r.title, "url": r.url,
                      "snippet": r.snippet, "source": r.source}
                     for r in results]

        summary = ""
        if summarise and formatted:
            summary = await self._summarise(query, formatted)

        data = {"query": query, "results": formatted,
                "summary": summary, "count": len(formatted)}

        self._cache[cache_key] = {"ts": time.time(), "data": data}
        return data

    # ── Streaming Search + Summarise ──────────────────────────────────────────
    async def search_stream(self, query: str, n: int = 6):
        """Yield search results then summarise in stream."""
        results = await self._ddg_search(query, n)
        if not results:
            results = await self._ddg_html_search(query, n)

        # First yield: raw results as JSON event
        formatted = [{"title": r.title, "url": r.url,
                      "snippet": r.snippet} for r in results]
        yield f"[SEARCH_RESULTS]{json.dumps(formatted[:6])}\n\n"

        if not results:
            yield "No results found for this query."
            return

        # Build context
        context = "\n".join(
            f"[{i+1}] {r.title}\nURL: {r.url}\n{r.snippet}"
            for i, r in enumerate(results[:6])
        )
        prompt = (f"Search query: {query}\n\nResults:\n{context}\n\n"
                  f"Provide a comprehensive answer citing sources:")

        async for token in self.llm.stream(prompt, role="general",
                                           system=SEARCH_SUMMARISE_SYSTEM):
            yield token

    # ── Fetch & Read a URL ────────────────────────────────────────────────────
    async def fetch_page(self, url: str, max_chars: int = 6000) -> Dict:
        """Fetch and clean the text content of a URL."""
        try:
            resp = await self._client.get(url, timeout=10.0)
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}"}
            ct   = resp.headers.get("content-type", "")
            if "text" not in ct and "json" not in ct:
                return {"success": False, "error": "Non-text content"}
            text = self._strip_html(resp.text)
            return {"success": True, "url": url, "content": text[:max_chars],
                    "length": len(text)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── DDG Instant Answer API ────────────────────────────────────────────────
    async def _ddg_search(self, query: str, n: int) -> List[SearchResult]:
        try:
            params = {"q": query, "format": "json",
                      "no_redirect": "1", "no_html": "1",
                      "skip_disambig": "1"}
            resp = await self._client.get(DDG_URL, params=params, timeout=8.0)
            data = resp.json()

            results = []

            # Abstract (instant answer)
            if data.get("Abstract"):
                results.append(SearchResult(
                    title   = data.get("Heading", query),
                    url     = data.get("AbstractURL", ""),
                    snippet = data["Abstract"][:400],
                    source  = data.get("AbstractSource", "DuckDuckGo"),
                ))

            # Related topics
            for topic in data.get("RelatedTopics", [])[:n]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append(SearchResult(
                        title   = topic.get("Text", "")[:60],
                        url     = topic.get("FirstURL", ""),
                        snippet = topic.get("Text", "")[:300],
                        source  = "DuckDuckGo",
                    ))

            return results[:n]
        except Exception as e:
            log.debug(f"DDG API error: {e}")
            return []

    # ── DDG HTML Scrape (fallback) ────────────────────────────────────────────
    async def _ddg_html_search(self, query: str, n: int) -> List[SearchResult]:
        try:
            params = {"q": query, "b": ""}
            headers = {
                "User-Agent": UA,
                "Accept": "text/html",
                "Accept-Language": "en-US,en;q=0.9",
            }
            resp = await self._client.post(
                DDG_HTML, data=params, headers=headers, timeout=10.0
            )
            html = resp.text

            results = []
            # Parse result blocks
            blocks = re.findall(
                r'class="result__body".*?class="result__snippet".*?>(.*?)</a>',
                html, re.DOTALL
            )

            # Simpler extraction
            titles   = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html)
            urls     = re.findall(r'class="result__url"[^>]*>(.*?)</span>', html)
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html)

            for i, (t, u, s) in enumerate(zip(titles, urls, snippets)):
                if i >= n:
                    break
                results.append(SearchResult(
                    title   = re.sub(r"<[^>]+>", "", t).strip()[:80],
                    url     = u.strip(),
                    snippet = re.sub(r"<[^>]+>", "", s).strip()[:300],
                    source  = "DuckDuckGo",
                ))

            return results[:n]
        except Exception as e:
            log.debug(f"DDG HTML error: {e}")
            return []

    # ── Summarise search results ──────────────────────────────────────────────
    async def _summarise(self, query: str, results: List[Dict]) -> str:
        if not results:
            return ""
        context = "\n".join(
            f"[{i+1}] {r['title']}\n{r['snippet']}"
            for i, r in enumerate(results[:6])
        )
        prompt = (f"Search query: {query}\n\nResults:\n{context}\n\n"
                  f"Synthesise a factual answer:")
        try:
            return await self.llm.complete(
                prompt, role="general",
                system=SEARCH_SUMMARISE_SYSTEM, temperature=0.3
            )
        except Exception:
            return ""

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _strip_html(self, html: str) -> str:
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>",  "", text,  flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;",  "&", text)
        text = re.sub(r"&lt;",   "<", text)
        text = re.sub(r"&gt;",   ">", text)
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip()

    async def close(self):
        await self._client.aclose()
