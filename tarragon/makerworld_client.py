"""MakerWorld client with fixture-based mocking for testing."""

import json
from pathlib import Path
from typing import Optional
from httpx import RequestError


class MakerWorldClient:
    """Client for MakerWorld API with fixture-based mock mode."""
    
    def __init__(self, api_url: Optional[str] = None, token: Optional[str] = None):
        """Initialize the client.
        
        Args:
            api_url: Base URL for MakerWorld API (defaults to production)
            token: API token for authentication
        """
        self.api_url = api_url or "https://api.makerworld.com/v1"
        self.token = token
        self._fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    
    def _load_fixture(self, name: str) -> dict:
        """Load a JSON fixture file."""
        fixture_path = self._fixtures_dir / f"{name}.json"
        if fixture_path.exists():
            with open(fixture_path, "r") as f:
                return json.load(f)
        raise FileNotFoundError(f"Fixture not found: {name}")
    
    def _has_valid_token(self) -> bool:
        """Check if we have a valid token."""
        return bool(self.token and self.token.strip())
    
    async def get_likes(self) -> list[dict]:
        """Get liked items from user account.
        
        Returns empty list if no token or fixture not found.
        """
        if not self._has_valid_token():
            return []
        
        try:
            fixture = self._load_fixture("likes")
            return fixture.get("likes", [])
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    async def get_collections(self) -> list[dict]:
        """Get user's collections.
        
        Returns empty list if no token or fixture not found.
        """
        if not self._has_valid_token():
            return []
        
        try:
            fixture = self._load_fixture("collections")
            return fixture.get("collections", [])
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    async def get_collection_models(self, collection_id: str) -> list[dict]:
        """Get models in a specific collection.
        
        Returns empty list if no token or fixture not found.
        """
        if not self._has_valid_token():
            return []
        
        try:
            fixture = self._load_fixture("models")
            return fixture.get("models", [])
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    async def sync_all(self) -> dict[str, int]:
        """Sync all data from MakerWorld.
        
        Returns a summary of synced items.
        """
        if not self._has_valid_token():
            return {"likes": 0, "collections": 0, "models": 0}
        
        likes = await self.get_likes()
        collections = await self.get_collections()
        
        models = []
        for collection in collections:
            collection_id = collection.get("external_id", collection.get("id"))
            models.extend(await self.get_collection_models(collection_id))
        
        return {
            "likes": len(likes),
            "collections": len(collections),
            "models": len(models),
        }
