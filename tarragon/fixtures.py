"""Fixture data and mesh generation for testing."""

import trimesh
import os
from pathlib import Path
from .db import get_connection, init_db
from .models import Collection, Model


FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "meshes"

MESH_NAMES = {
    "cube": "Cube Primitive",
    "sphere": "Sphere Primitive",
    "cylinder": "Cylinder Primitive",
}


def generate_fixture_meshes():
    """Generate simple fixture meshes (cube, sphere, cylinder)."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    
    meshes = {}
    
    # Cube
    cube = trimesh.creation.box(extents=[1, 1, 1])
    cube_path = FIXTURES_DIR / "cube.stl"
    cube.export(str(cube_path))
    meshes["cube"] = {
        "path": str(cube_path),
        "name": "Cube Primitive",
        "external_id": "cube-001"
    }
    
    # Sphere
    sphere = trimesh.creation.icosphere(radius=0.5)
    sphere_path = FIXTURES_DIR / "sphere.stl"
    sphere.export(str(sphere_path))
    meshes["sphere"] = {
        "path": str(sphere_path),
        "name": "Sphere Primitive",
        "external_id": "sphere-001"
    }
    
    # Cylinder
    cylinder = trimesh.creation.cylinder(radius=0.5, height=1.0)
    cylinder_path = FIXTURES_DIR / "cylinder.stl"
    cylinder.export(str(cylinder_path))
    meshes["cylinder"] = {
        "path": str(cylinder_path),
        "name": "Cylinder Primitive",
        "external_id": "cylinder-001"
    }
    
    return meshes


def get_fixture_meshes():
    """Get paths to fixture meshes, generating if needed."""
    if not any(FIXTURES_DIR.glob("*.stl")):
        generate_fixture_meshes()
    
    return {
        f.stem: {
            "path": str(f),
            "name": MESH_NAMES.get(f.stem, f.stem.title()),
            "external_id": f.stem + "-001",
        }
        for f in FIXTURES_DIR.glob("*.stl")
    }


def load_fixture_data():
    """Load fixture collections and models."""
    meshes = get_fixture_meshes()
    
    # Create a fixture collection
    collection = Collection(
        id=None,
        account_id=1,
        name="Fixture Collection",
        external_id="fixture-001"
    )
    
    # Create fixture models
    models = []
    for i, (name, mesh_info) in enumerate(meshes.items(), 1):
        models.append(Model(
            id=i,
            collection_id=1,
            external_id=mesh_info["external_id"],
            name=mesh_info["name"],
            thumbnail_url=None,
            mesh_file_path=mesh_info["path"]
        ))
    
    return collection, models


def seed_fixture_data():
    """Seed the database with fixture data if empty."""
    init_db()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if we already have fixture data
        cursor.execute("SELECT COUNT(*) FROM collections WHERE external_id = ?", ("fixture-001",))
        if cursor.fetchone()[0] > 0:
            return
        
        # Create fixture collection
        cursor.execute(
            "INSERT INTO collections (account_id, name, external_id) VALUES (?, ?, ?)",
            (1, "Fixture Collection", "fixture-001")
        )
        collection_id = cursor.lastrowid
        
        # Generate and add fixture meshes
        meshes = get_fixture_meshes()
        for i, (name, mesh_info) in enumerate(meshes.items(), 1):
            cursor.execute(
                """INSERT INTO models (collection_id, external_id, name, thumbnail_url, mesh_file_path)
                   VALUES (?, ?, ?, ?, ?)""",
                (collection_id, mesh_info["external_id"], mesh_info["name"], None, mesh_info["path"])
            )
        
        conn.commit()


if __name__ == "__main__":
    seed_fixture_data()
