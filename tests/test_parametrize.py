"""Tests for the parametrize pipeline."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from tarragon.app import app
from tarragon.db import get_connection, init_db, get_db_path
from tarragon.fixtures import seed_fixture_data
from tarragon.parametrize import analyze_mesh, generate_scad


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Point DB_PATH at an isolated test database, then init + seed fixtures."""
    import tarragon.db
    test_db_path = get_db_path().parent / "test_parametrize_tarragon.db"
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


def test_analyze_mesh_cube():
    """Test analyze_mesh gives sane bbox numbers for cube fixture."""
    # Get the path to cube.stl
    seed_fixture_data()
    from tarragon.fixtures import get_fixture_meshes
    meshes = get_fixture_meshes()
    
    cube_info = meshes["cube"]
    analysis = analyze_mesh(cube_info["path"])
    
    # Cube is 1x1x1, so dimensions should be close to that
    dimensions = analysis["dimensions"]
    assert len(dimensions) == 3
    
    # Each dimension should be approximately 1.0 (with some tolerance)
    for dim in dimensions:
        assert 0.9 <= dim <= 1.1, f"Expected dim ~1.0, got {dim}"
    
    # Volume should be approximately 1.0 for a unit cube
    assert 0.9 <= analysis["volume"] <= 1.1, f"Expected volume ~1.0, got {analysis['volume']}"
    
    # Should be watertight (closed mesh)
    assert analysis["is_watertight"] is True
    
    # Primitive fit should detect something
    assert "type" in analysis["primitive_fit"]
    assert "confidence" in analysis["primitive_fit"]
    assert 0 < analysis["primitive_fit"]["confidence"] <= 1


def test_generate_scad_parameters():
    """Test that generated code has >= 3 parameters."""
    seed_fixture_data()
    from tarragon.fixtures import get_fixture_meshes
    meshes = get_fixture_meshes()
    
    cube_info = meshes["cube"]
    analysis = analyze_mesh(cube_info["path"])
    
    # Mock httpx client to avoid actual Ollama call
    with patch("tarragon.parametrize.httpx.Client") as mock_client:
        # Create a mock response with OpenSCAD code
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": """```scad
// Cube parametrization
width = 1.0;
height = 1.0;
depth = 1.0;

module cube_primitive() {
    translate([-width/2, -height/2, -depth/2])
        cube([width, height, depth]);
}
```
"""
        }
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        
        scad_code, params = generate_scad(analysis, "Cube Primitive")
    
    # Check that we got code back
    assert "scad" in scad_code.lower() or "module" in scad_code.lower() or len(scad_code) > 0
    
    # Check that we have >= 3 parameters
    assert len(params) >= 3, f"Expected >=3 params, got {len(params)}: {params}"
    
    # Should have dimension-based parameters
    assert "width" in params or "height" in params or "depth" in params


def test_parametrize_route_returns_200(client):
    """Test that parametrize route returns 200."""
    # First ensure we have a model with mesh
    seed_fixture_data()

    with patch("tarragon.parametrize.httpx.Client") as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": """```scad
width = 1.0;
height = 1.0;
depth = 1.0;

module cube_primitive() {
    translate([-width/2, -height/2, -depth/2])
        cube([width, height, depth]);
}
```
"""
        }
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response

        response = client.post("/models/1/parametrize")

    # Should succeed
    assert response.status_code == 200

    # Should return JSON
    data = response.json()
    assert data is not None
    assert "status" in data
    assert data["status"] == "done"


def test_parametrize_route_creates_scad_job(client):
    """Test that parametrize route creates a scad_jobs row."""
    seed_fixture_data()
    
    # Check no job exists yet
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM scad_jobs WHERE model_id = 1")
        count_before = cursor.fetchone()[0]
    
    # Call parametrize
    with patch("tarragon.parametrize.httpx.Client") as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": """```scad
width = 1.0;
height = 1.0;
depth = 1.0;

module cube_primitive() {
    translate([-width/2, -height/2, -depth/2])
        cube([width, height, depth]);
}
```
"""
        }
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        
        response = client.post("/models/1/parametrize")
    
    assert response.status_code == 200
    
    # Check job was created
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM scad_jobs WHERE model_id = 1")
        count_after = cursor.fetchone()[0]
    
    assert count_after == count_before + 1, "Expected a new scad_jobs row"


def test_parametrize_route_returns_scad_code(client):
    """Test that parametrize route returns scad code in response."""
    seed_fixture_data()
    
    with patch("tarragon.parametrize.httpx.Client") as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": """```scad
width = 1.0;
height = 1.0;
depth = 1.0;

modulecube_primitive() {
    translate([-width/2, -height/2, -depth/2])
        cube([width, height, depth]);
}
```
"""
        }
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        
        response = client.post("/models/1/parametrize")
    
    data = response.json()
    
    # Should have scad_code
    assert "scad_code" in data
    assert len(data["scad_code"]) > 0
    
    # Should have parameters
    assert "params_json" in data
    assert isinstance(data["params_json"], dict)
    assert len(data["params_json"]) >= 3
