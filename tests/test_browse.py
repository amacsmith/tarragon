"""Pytest fixtures and tests for Tarragon browse endpoints."""

import pytest
from fastapi.testclient import TestClient

from tarragon.app import app
from tarragon.db import get_connection, init_db, get_db_path
from tarragon.fixtures import seed_fixture_data


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Point DB_PATH at an isolated test database, then init + seed fixtures."""
    import tarragon.db
    test_db_path = get_db_path().parent / "test_browse_tarragon.db"
    original_path = tarragon.db.DB_PATH
    tarragon.db.DB_PATH = test_db_path

    init_db()
    seed_fixture_data()

    yield test_db_path

    tarragon.db.DB_PATH = original_path
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class TestCollectionsRoute:
    """Tests for GET /collections endpoint."""
    
    def test_collections_route_returns_200(self, client):
        """Test that /collections returns HTTP 200."""
        response = client.get("/collections")
        assert response.status_code == 200
    
    def test_collections_route_shows_fixture_data(self, client):
        """Test that /collections displays fixture collection data."""
        response = client.get("/collections")
        assert response.status_code == 200
        
        content = response.text
        # Check for fixture collection
        assert "Fixture Collection" in content
        assert "fixture-001" in content
        # Check for fixture meshes
        assert "Cube Primitive" in content
        assert "Sphere Primitive" in content
        assert "Cylinder Primitive" in content
    
    def test_collections_route_has_model_links(self, client):
        """Test that /collections has links to model detail pages."""
        response = client.get("/collections")
        assert response.status_code == 200
        
        content = response.text
        # Check for links to model detail pages
        assert 'href="/models/1"' in content or "/models/1" in content
        assert 'href="/models/2"' in content or "/models/2" in content
        assert 'href="/models/3"' in content or "/models/3" in content


class TestModelDetailRoute:
    """Tests for GET /models/{id} endpoint."""
    
    def test_model_detail_route_returns_200(self, client):
        """Test that /models/1 returns HTTP 200."""
        response = client.get("/models/1")
        assert response.status_code == 200
    
    def test_model_detail_route_shows_model_data(self, client):
        """Test that /models/1 displays model metadata."""
        response = client.get("/models/1")
        assert response.status_code == 200
        
        content = response.text
        # Check for model data
        assert "Cube Primitive" in content
        assert "cube-001" in content
        # Check for collection link
        assert "Fixture Collection" in content
    
    def test_model_detail_route_shows_stl_viewer(self, client):
        """Test that /models/1 includes STLLoader script."""
        response = client.get("/models/1")
        assert response.status_code == 200
        
        content = response.text
        # Check for three.js and STLLoader
        assert 'src="/static/vendor/three.min.js"' in content
        assert 'src="/static/vendor/STLLoader.js"' in content
    
    def test_model_detail_route_returns_404_for_missing_model(self, client):
        """Test that /models/999 returns HTTP 404."""
        response = client.get("/models/999")
        assert response.status_code == 404


class TestFixtureGeneration:
    """Tests for fixture mesh generation."""
    
    def test_fixture_meshes_exist(self):
        """Test that fixture meshes are generated and exist."""
        seed_fixture_data()
        
        from tarragon.fixtures import FIXTURES_DIR, get_fixture_meshes
        meshes = get_fixture_meshes()
        
        assert len(meshes) == 3
        assert "cube" in meshes
        assert "sphere" in meshes
        assert "cylinder" in meshes
        
        # Check files exist
        assert meshes["cube"]["path"].endswith(".stl")
        assert meshes["sphere"]["path"].endswith(".stl")
        assert meshes["cylinder"]["path"].endswith(".stl")
    
    def test_fixture_meshes_are_valid_stl(self):
        """Test that generated STL files are valid."""
        import trimesh
        
        seed_fixture_data()
        from tarragon.fixtures import get_fixture_meshes
        meshes = get_fixture_meshes()
        
        for name, mesh_info in meshes.items():
            mesh = trimesh.load(mesh_info["path"])
            assert mesh is not None
            assert hasattr(mesh, "vertices")
            assert len(mesh.vertices) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
