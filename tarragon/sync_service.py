"""Sync service to pull data from MakerWorld."""

import asyncio
from typing import Optional
from .db import get_connection, init_db
from .models import Account, Collection, Model
from .makerworld_client import MakerWorldClient


class SyncService:
    """Service for syncing MakerWorld data."""
    
    def __init__(self, token: Optional[str] = None):
        """Initialize the sync service.
        
        Args:
            token: MakerWorld API token (optional)
        """
        self.client = MakerWorldClient(token=token)
        self._init_db()
    
    def _init_db(self):
        """Initialize database if needed."""
        try:
            init_db()
        except Exception:
            pass
    
    async def sync(self) -> dict[str, int]:
        """Sync all data from MakerWorld.
        
        Returns a summary of synced items.
        """
        summary = await self.client.sync_all()
        
        if not summary["collections"]:
            return summary
        
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Get or create account
            cursor.execute("SELECT id, makerworld_token FROM accounts LIMIT 1")
            row = cursor.fetchone()
            
            if row:
                account_id = row["id"]
                # Update token if provided
                if self.client.token:
                    cursor.execute(
                        "UPDATE accounts SET makerworld_token = ? WHERE id = ?",
                        (self.client.token, account_id)
                    )
            else:
                cursor.execute(
                    "INSERT INTO accounts (makerworld_token) VALUES (?)",
                    (self.client.token,)
                )
                account_id = cursor.lastrowid
            
            # Sync collections
            for coll in self.client._load_fixture("collections").get("collections", []):
                cursor.execute(
                    """
                    INSERT INTO collections (account_id, name, external_id)
                    VALUES (?, ?, ?)
                    ON CONFLICT(external_id) DO UPDATE SET name = excluded.name
                    """,
                    (account_id, coll["name"], coll["external_id"])
                )
            
            # Sync models
            for model in self.client._load_fixture("models").get("models", []):
                # Find collection_id for this model
                collection_external_id = model.get("collection_external_id", model.get("collection_id"))
                cursor.execute(
                    "SELECT id FROM collections WHERE external_id = ?",
                    (collection_external_id,)
                )
                coll_row = cursor.fetchone()
                
                if coll_row:
                    collection_id = coll_row["id"]
                    cursor.execute(
                        """
                        INSERT INTO models (collection_id, external_id, name, thumbnail_url, mesh_file_path)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(collection_id, external_id) DO UPDATE SET name = excluded.name
                        """,
                        (
                            collection_id,
                            model["external_id"],
                            model["name"],
                            model.get("thumbnail_url"),
                            model.get("mesh_file_path")
                        )
                    )
            
            conn.commit()
        
        return summary


async def run_real_sync(handle: str, token: Optional[str] = None) -> dict[str, int]:
    """Sync real MakerWorld data for a user handle via Next.js data routes.

    Public collections sync without a token; likes and private collections
    need the auth-cookie token.
    """
    from .makerworld_web import MakerWorldWebClient

    init_db()
    client = MakerWorldWebClient(handle=handle, token=token)
    collections = await client.get_collections()
    likes = await client.get_likes()

    n_models = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM accounts LIMIT 1")
        row = cursor.fetchone()
        if row:
            account_id = row["id"]
            cursor.execute(
                "UPDATE accounts SET makerworld_token = ?, handle = ? WHERE id = ?",
                (token, handle, account_id),
            )
        else:
            cursor.execute(
                "INSERT INTO accounts (makerworld_token, handle) VALUES (?, ?)",
                (token, handle),
            )
            account_id = cursor.lastrowid

        async def upsert_collection(name: str, external_id: str, models: list[dict]) -> int:
            nonlocal n_models
            cursor.execute(
                """
                INSERT INTO collections (account_id, name, external_id)
                VALUES (?, ?, ?)
                ON CONFLICT(external_id) DO UPDATE SET name = excluded.name
                """,
                (account_id, name, external_id),
            )
            cursor.execute("SELECT id FROM collections WHERE external_id = ?", (external_id,))
            collection_id = cursor.fetchone()["id"]
            for m in models:
                cursor.execute(
                    """
                    INSERT INTO models (collection_id, external_id, name, thumbnail_url, mesh_file_path)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(collection_id, external_id) DO UPDATE SET
                        name = excluded.name, thumbnail_url = excluded.thumbnail_url
                    """,
                    (collection_id, m["external_id"], m["name"],
                     m.get("thumbnail_url"), m.get("mesh_file_path")),
                )
                n_models += 1
            return collection_id

        for coll in collections:
            models = await client.get_collection_models(coll["external_id"], coll["slug"])
            await upsert_collection(coll["name"], coll["external_id"], models)

        if likes:
            await upsert_collection("Likes", f"likes-{handle}", likes)

        conn.commit()

    return {"likes": len(likes), "collections": len(collections), "models": n_models}


async def run_sync(token: Optional[str] = None, handle: Optional[str] = None) -> dict[str, int]:
    """Run the sync service.

    With a handle, syncs real MakerWorld data (token optional — enables
    likes/private collections). Without a handle, falls back to fixture mode.
    """
    if handle and handle.strip():
        return await run_real_sync(handle.strip(), token=token)
    service = SyncService(token=token)
    return await service.sync()


if __name__ == "__main__":
    asyncio.run(run_sync())
