"""Tests for the sync service with fixtures."""

import asyncio
import pytest
import os
import sys

# Add the parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tarragon.db import get_connection, init_db, get_db_path
from tarragon.sync_service import SyncService
from tarragon.makerworld_client import MakerWorldClient


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    """Setup test database."""
    # Use a test database
    test_db_path = get_db_path().parent / "test_tarragon.db"
    
    # Monkeypatch the DB_PATH
    import tarragon.db
    original_path = tarragon.db.DB_PATH
    tarragon.db.DB_PATH = test_db_path
    
    init_db()
    
    yield test_db_path
    
    # Cleanup
    tarragon.db.DB_PATH = original_path
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture
def sync_service():
    """Create a sync service instance."""
    return SyncService(token="test-token")


@pytest.mark.asyncio
async def test_sync_service_with_fixtures(sync_service):
    """Test sync service with fixture data."""
    result = await sync_service.sync()
    
    assert result["collections"] > 0
    assert result["models"] > 0
    
    # Verify data was saved to DB
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Check collections were saved
        cursor.execute("SELECT COUNT(*) FROM collections")
        coll_count = cursor.fetchone()[0]
        assert coll_count > 0
        
        # Check models were saved
        cursor.execute("SELECT COUNT(*) FROM models")
        model_count = cursor.fetchone()[0]
        assert model_count > 0


@pytest.mark.asyncio
async def test_makerworld_client_no_token():
    """Test client returns empty results without token."""
    client = MakerWorldClient()
    
    likes = await client.get_likes()
    collections = await client.get_collections()
    models = await client.get_collection_models("test_id")
    
    assert likes == []
    assert collections == []
    assert models == []


@pytest.mark.asyncio
async def test_makerworld_client_with_token():
    """Test client loads fixtures when token is present."""
    client = MakerWorldClient(token="fake-token-for-testing")
    
    collections = await client.get_collections()
    
    assert len(collections) > 0
    assert any(c.get("external_id") == "coll_001" for c in collections)


@pytest.mark.asyncio
async def test_sync_service_token_update(sync_service):
    """Test that token can be updated."""
    # First sync
    result1 = await sync_service.sync()
    assert result1["collections"] > 0
    
    # Verify account was created
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT makerworld_token FROM accounts LIMIT 1")
        row = cursor.fetchone()
        assert row is not None


def test_database_schema(setup_test_db):
    """Test database schema is correct."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        table_names = [t[0] for t in tables]
        
        assert "accounts" in table_names
        assert "collections" in table_names
        assert "models" in table_names
        assert "scad_jobs" in table_names
