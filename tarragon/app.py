"""FastAPI application for Tarragon."""

import json
import uvicorn
from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional
import sqlite3

from tarragon.db import get_connection, init_db, get_db_path
from tarragon.sync_service import run_sync
from tarragon.parametrize import analyze_mesh, generate_scad

app = FastAPI(title="Tarragon")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Import router after app/templates are defined (to avoid circular import)
from tarragon.browse import router as browse_router
app.include_router(browse_router, prefix="")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


def get_token_from_db() -> Optional[str]:
    """Get the stored MakerWorld token from the database."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT makerworld_token FROM accounts LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row["makerworld_token"] if row else None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Show the home page."""
    token = get_token_from_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM collections")
        n_collections = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM models")
        n_models = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM scad_jobs")
        n_scad_jobs = cursor.fetchone()[0]
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "has_token": bool(token),
            "n_collections": n_collections,
            "n_models": n_models,
            "n_scad_jobs": n_scad_jobs,
        },
    )


def get_account_from_db() -> dict:
    """Get stored MakerWorld handle + token."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT makerworld_token, handle FROM accounts LIMIT 1")
        row = cursor.fetchone()
    return {
        "token": row["makerworld_token"] if row else None,
        "handle": row["handle"] if row else None,
    }


@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """Show the settings page."""
    account = get_account_from_db()
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"token": account["token"] or "", "handle": account["handle"] or ""},
    )


@app.post("/settings")
async def settings_post(handle: str = Form(""), token: str = Form("")):
    """Save the MakerWorld handle + optional token."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO accounts (id, makerworld_token, handle, created_at) "
            "VALUES (1, ?, ?, datetime('now'))",
            (token.strip() or None, handle.strip().lstrip("@") or None)
        )
        conn.commit()
    return RedirectResponse(url="/settings", status_code=303)


@app.post("/sync")
async def sync_data():
    """Trigger a sync with MakerWorld (real sync when a handle is set)."""
    account = get_account_from_db()
    result = await run_sync(token=account["token"], handle=account["handle"])
    return result


@app.post("/models/{model_id}/parametrize")
async def parametrize_model(model_id: int):
    """Parametrize a model by analyzing its mesh and generating OpenSCAD.
    
    Returns the SCAD job with the generated code and parameters.
    """
    from tarragon.db import get_connection
    from tarragon.models import SCADJob
    
    # Get the model first
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, mesh_file_path FROM models WHERE id = ?", (model_id,))
        row = cursor.fetchone()
        
        if not row:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        
        model_name = row["name"]
        mesh_path = row["mesh_file_path"]
    
    # Analyze the mesh
    mesh_analysis = analyze_mesh(mesh_path)
    
    # Generate SCAD code
    scad_code, params = generate_scad(mesh_analysis, model_name)
    
    # Store the SCAD job
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO scad_jobs (model_id, status, scad_code, params_json, created_at)
               VALUES (?, 'done', ?, ?, datetime('now'))""",
            (model_id, scad_code, json.dumps(params))
        )
        conn.commit()
    
    # Return the job
    job_id = cursor.lastrowid
    from fastapi.responses import JSONResponse
    return JSONResponse({
        "id": job_id,
        "model_id": model_id,
        "status": "done",
        "scad_code": scad_code,
        "params_json": params,
    })


def main():
    """Run the uvicorn server."""
    uvicorn.run("tarragon.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
