"""Browse UI endpoints for collections and models."""

import json
import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pathlib import Path

from tarragon.db import get_connection
from tarragon.fixtures import seed_fixture_data
from tarragon.app import templates

router = APIRouter()


def get_collections():
    """Get all collections with their models."""
    seed_fixture_data()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, external_id FROM collections ORDER BY name")
        coll_rows = cursor.fetchall()
        cursor.execute(
            "SELECT id, collection_id, name, thumbnail_url, mesh_file_path "
            "FROM models ORDER BY id"
        )
        models_by_coll: dict[int, list[dict]] = {}
        for m in cursor.fetchall():
            models_by_coll.setdefault(m["collection_id"], []).append({
                "id": m["id"],
                "name": m["name"],
                "thumbnail_url": m["thumbnail_url"],
                "mesh_path": m["mesh_file_path"],
            })

        collections = []
        for row in coll_rows:
            models = models_by_coll.get(row["id"], [])
            collections.append({
                "id": row["id"],
                "name": row["name"],
                "external_id": row["external_id"],
                "model_count": len(models),
                "models": models,
            })

        return collections


def get_model(model_id: int):
    """Get a single model by ID."""
    seed_fixture_data()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.name, m.external_id, m.thumbnail_url, m.mesh_file_path,
                   c.id as collection_id, c.name as collection_name
            FROM models m
            JOIN collections c ON m.collection_id = c.id
            WHERE m.id = ?
        """, (model_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        result = {
            "id": row["id"],
            "name": row["name"],
            "external_id": row["external_id"],
            "thumbnail_url": row["thumbnail_url"],
            "mesh_file_path": row["mesh_file_path"],
            "collection_id": row["collection_id"],
            "collection_name": row["collection_name"]
        }
        
        # Get SCAD job if exists
        cursor.execute("""
            SELECT id, status, scad_code, params_json, created_at
            FROM scad_jobs
            WHERE model_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (model_id,))
        scad_row = cursor.fetchone()
        
        if scad_row:
            result["scad_job"] = {
                "id": scad_row["id"],
                "status": scad_row["status"],
                "scad_code": scad_row["scad_code"],
                "params_json": json.loads(scad_row["params_json"]) if scad_row["params_json"] else {},
                "created_at": scad_row["created_at"],
            }
        
        return result


@router.get("/collections", response_class=HTMLResponse)
async def list_collections(request: Request):
    """Show all collections with their models."""
    collections = get_collections()
    return templates.TemplateResponse(
        request, "collections.html", {"collections": collections}
    )


@router.get("/meshes/{model_id}")
async def serve_mesh(model_id: int):
    """Serve a model's mesh file (STL) for the 3D viewer."""
    model = get_model(model_id)
    if not model or not model["mesh_file_path"]:
        raise HTTPException(status_code=404, detail="Mesh not found")
    path = Path(model["mesh_file_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Mesh file missing on disk")
    return FileResponse(path, media_type="model/stl", filename=path.name)


@router.get("/models/{model_id}", response_class=HTMLResponse)
async def show_model(request: Request, model_id: int):
    """Show a single model with 3D viewer."""
    model = get_model(model_id)
    if not model:
        return templates.TemplateResponse(
            request, "error.html", {"message": "Model not found"}, status_code=404
        )
    return templates.TemplateResponse(
        request, "model_detail.html", {"model": model}
    )
