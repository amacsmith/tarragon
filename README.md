# Tarragon

Tarragon is a web-based 3D model parametrization tool that connects to MakerWorld to sync your liked models and collections, then analyzes mesh data and generates OpenSCAD parametric code using Ollama. It provides a FastAPI web interface with a three.js 3D viewer, SQLite storage, and a trimesh-based pipeline for primitive fitting and SCAD generation.

## Setup

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Run the development server:
   ```bash
   uv run uvicorn tarragon.app:app --reload
   ```

3. Open http://localhost:8000 in your browser

## MakerWorld Token

To sync your MakerWorld likes and collections, you need to provide an API token:

1. Visit https://makerworld.com and log in
2. Open browser DevTools → Application → Local Storage → find the session token
3. Paste the token into the `/settings` page

**Note:** This is an unofficial, reverse-engineered integration with MakerWorld's API. The token is stored locally in SQLite and is not shared with any third party. The API may break if MakerWorld changes their authentication or endpoints.

See `docs/makerworld-api.md` for details on the discovered API endpoints.

## Running Tests

```bash
uv run pytest
```

## Known Limitations

- **Mesh-to-parametric is best-effort**: The pipeline uses primitive fitting (box, cylinder, sphere) to approximate meshes - it does not perform perfect reconstruction of complex models
- **OpenSCAD rendering not wired up**: The generated SCAD code is produced but not rendered via the OpenSCAD CLI - code-only workflow for now
- **Unofficial API**: MakerWorld's authentication may change, breaking the integration
- **Ollama dependency**: Parametrize requires a local Ollama server running `qwen3-coder-next:q4_K_M`
