"""Real MakerWorld sync via Next.js data routes.

MakerWorld has no official API. Its Next.js frontend exposes JSON data routes
(`/_next/data/{buildId}/en/...json`) that mirror what the pages render:

- `@{handle}/collections.json` -> pageProps.favoritesList (public collections;
  private ones appear only with an auth cookie)
- `collections/{id}-{slug}.json` -> pageProps.favoriteDesigns.hits (designs in
  a collection; public)
- `@{handle}/likes.json` -> pageProps.designs (requires auth cookie, redirects
  anonymously)

The buildId changes on every MakerWorld deploy, so it is scraped from the
homepage's __NEXT_DATA__ on each sync. The optional `token` is the value of the
httpOnly `token` cookie from a logged-in browser session; without it, public
collections still sync.

Cloudflare blocks plain httpx/requests by TLS fingerprint, so requests go
through curl_cffi with Chrome impersonation.

Endpoint research: docs/makerworld-api.md.
"""

import re
from typing import Optional

from curl_cffi.requests import AsyncSession

BASE = "https://makerworld.com"
_BUILD_ID_RE = re.compile(r'"buildId":"([^"]+)"')


class MakerWorldWebClient:
    """Fetch collections/likes from makerworld.com Next.js data routes."""

    def __init__(self, handle: str, token: Optional[str] = None):
        self.handle = handle.lstrip("@")
        self.token = (token or "").strip() or None
        self._build_id: Optional[str] = None

    def _session(self) -> AsyncSession:
        cookies = {"token": self.token} if self.token else {}
        return AsyncSession(impersonate="chrome", cookies=cookies, timeout=30)

    async def _get_build_id(self, session: AsyncSession) -> str:
        if self._build_id:
            return self._build_id
        resp = await session.get(f"{BASE}/en")
        resp.raise_for_status()
        match = _BUILD_ID_RE.search(resp.text)
        if not match:
            raise RuntimeError("Could not find Next.js buildId on makerworld.com")
        build_id = match.group(1)
        self._build_id = build_id
        return build_id

    async def _data_route(self, session: AsyncSession, path: str) -> Optional[dict]:
        """GET a /_next/data route; returns pageProps or None on redirect/error."""
        build_id = await self._get_build_id(session)
        resp = await session.get(
            f"{BASE}/_next/data/{build_id}/en{path}", allow_redirects=False
        )
        if resp.status_code != 200:
            return None
        page_props = resp.json().get("pageProps", {})
        if "__N_REDIRECT" in page_props and "favoritesList" not in page_props:
            redirect = page_props["__N_REDIRECT"]
            if redirect.startswith("/en/collections/"):
                # collection id-only URL redirecting to its slug form
                return await self._data_route(session, redirect[len("/en"):])
            return None  # auth-required page bounced us (e.g. likes w/o token)
        return page_props

    async def get_collections(self) -> list[dict]:
        """List the user's collections (public; + private when token set)."""
        async with self._session() as session:
            props = await self._data_route(session, f"/@{self.handle}/collections.json")
            if not props:
                return []
            return [
                {
                    "external_id": str(c["id"]),
                    "name": c.get("title") or f"Collection {c['id']}",
                    "slug": c.get("slug") or "",
                    "design_count": c.get("designCnt", 0),
                }
                for c in props.get("favoritesList", [])
            ]

    async def get_collection_models(self, external_id: str, slug: str = "") -> list[dict]:
        """List designs in a collection."""
        async with self._session() as session:
            suffix = f"{external_id}-{slug}" if slug else external_id
            props = await self._data_route(session, f"/collections/{suffix}.json")
            if not props:
                return []
            hits = (props.get("favoriteDesigns") or {}).get("hits", [])
            return [self._design_to_model(d) for d in hits]

    async def get_likes(self) -> list[dict]:
        """List liked designs. Requires token (auth cookie); [] without it."""
        if not self.token:
            return []
        async with self._session() as session:
            props = await self._data_route(session, f"/@{self.handle}/likes.json")
            if not props:
                return []
            return [self._design_to_model(d) for d in props.get("designs", [])]

    @staticmethod
    def _design_to_model(design: dict) -> dict:
        return {
            "external_id": str(design["id"]),
            "name": design.get("title") or f"Design {design['id']}",
            "thumbnail_url": design.get("cover") or "",
            "mesh_file_path": None,  # mesh download requires auth'd POST; future work
        }
