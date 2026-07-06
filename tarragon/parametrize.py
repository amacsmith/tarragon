"""Mesh parametrization using trimesh and OpenSCAD generation via Ollama."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import trimesh
import httpx


def analyze_mesh(path: str) -> Dict[str, Any]:
    """Analyze a mesh file and extract key properties.
    
    Args:
        path: Path to the mesh file (STL, etc.)
        
    Returns:
        Dictionary with mesh analysis including:
        - bounding_box: dimensions [width, height, depth]
        - volume: mesh volume
        - is_watertight: whether the mesh is watertight
        - primitive_fit: detected primitive type and confidence
    """
    mesh = trimesh.load(path)
    
    # Get bounding box dimensions
    bbox = mesh.bounds
    dimensions = bbox[1] - bbox[0]  # [width, height, depth]
    
    # Get volume
    volume = float(mesh.volume) if mesh.is_watertight else 0.0
    
    # Check if watertight
    is_watertight = bool(mesh.is_watertight)
    
    # Primitive fit detection
    primitive_fit = _detect_primitive_fit(mesh, dimensions)
    
    return {
        "dimensions": dimensions.tolist(),
        "volume": volume,
        "is_watertight": is_watertight,
        "primitive_fit": primitive_fit,
        "mesh_path": str(path),
    }


def _detect_primitive_fit(mesh: trimesh.Trimesh, dimensions: list) -> Dict[str, Any]:
    """Detect which primitive best fits the mesh.
    
    Compares mesh volume to primitive volumes with same bounding dimensions.
    Returns the closest fit with confidence score.
    """
    width, height, depth = dimensions
    
    # Cuboid (box) - volume = width * height * depth
    cuboid_volume = width * height * depth
    
    # Cylinder - volume = pi * r^2 * h
    # Approximate radius from bounding box
    radius = max(width, depth) / 2
    cylinder_volume = 3.14159 * (radius ** 2) * height
    
    # Sphere - volume = 4/3 * pi * r^3
    # Approximate radius from average dimension
    avg_dim = (width + height + depth) / 3
    sphere_radius = avg_dim / 2
    sphere_volume = (4/3) * 3.14159 * (sphere_radius ** 3)
    
    # Calculate confidence for each primitive
    def calc_confidence(mesh_vol: float, prim_vol: float) -> float:
        if prim_vol == 0:
            return 0.0
        ratio = mesh_vol / prim_vol
        # Cap ratio to [0, 1] for confidence calculation
        ratio = max(0.0, min(1.0, ratio))
        return ratio  # Higher is better (closer to primitive)
    
    cube_conf = calc_confidence(mesh.volume, cuboid_volume)
    cyl_conf = calc_confidence(mesh.volume, cylinder_volume)
    sph_conf = calc_confidence(mesh.volume, sphere_volume)
    
    # Determine best fit
    confidences = {
        "box": cube_conf,
        "cylinder": cyl_conf,
        "sphere": sph_conf,
    }
    best_fit = max(confidences, key=confidences.get)
    
    return {
        "type": best_fit,
        "confidence": round(confidences[best_fit], 4),
        "volumes": {
            "mesh": round(mesh.volume, 4),
            "box": round(cuboid_volume, 4),
            "cylinder": round(cylinder_volume, 4),
            "sphere": round(sphere_volume, 4),
        }
    }


def generate_scad(mesh_analysis: Dict[str, Any], model_name: str) -> tuple[str, dict]:
    """Generate OpenSCAD code using Ollama API.
    
    Args:
        mesh_analysis: Result from analyze_mesh()
        model_name: Name of the model (for context in SCAD)
        
    Returns:
        Tuple of (scad_code, params_dict)
    """
    primitive_type = mesh_analysis["primitive_fit"]["type"]
    dimensions = mesh_analysis["dimensions"]
    
    prompt = f"""Generate OpenSCAD code for a {primitive_type} shape that approximates a 3D model.
    
Mesh Analysis:
- Model name: {model_name}
- Dim (W x H x D): {dimensions[0]:.2f} x {dimensions[1]:.2f} x {dimensions[2]:.2f}
- Volume: {mesh_analysis['volume']:.4f}
- Primitive Fit: {primitive_type} (confidence: {mesh_analysis['primitive_fit']['confidence']})

Requirements:
1. Use at least 3 named parameters for tuning (e.g., width, height, depth, radius, etc.)
2. Use the translate() function to center the shape at origin
3. Use the module name {model_name.replace(' ', '_').replace('-', '_')}
4. Return ONLY the OpenSCAD code, no other text

Format the output with a ```scad code block.
"""
    
    # POST to Ollama API
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen3-coder-next:q4_K_M",
                    "prompt": prompt,
                    "stream": False,
                },
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()
            
            # Extract SCAD code from response
            full_response = result.get("response", "")
            scad_code = _extract_scad_code(full_response)
            
    except (httpx.RequestError, httpx.TimeoutException) as e:
        # Fallback if Ollama is unavailable (for testing scenarios)
        scad_code = _fallback_scad(primitive_type, dimensions, model_name)
    
    # Extract parameters from SCAD code
    params = _extract_scad_params(scad_code, mesh_analysis)
    
    return scad_code, params


def _extract_scad_code(text: str) -> str:
    """Extract SCAD code from response text."""
    if "```scad" in text:
        start = text.find("```scad") + 7
        end = text.find("```", start)
        if end == -1:
            end = start + 5000  # Fallback
        return text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end == -1:
            end = start + 5000
        return text[start:end].strip()
    return text.strip()


def _extract_scad_params(scad_code: str, mesh_analysis: Dict[str, Any]) -> dict:
    """Extract parameter values from SCAD code.
    
    Looks for parameter definitions in the format: param_name = value;
    """
    params = {}
    
    # Parse dimension-based defaults from mesh analysis
    width, height, depth = mesh_analysis["dimensions"]
    
    # Extract parameter lines (lines with = but not function definitions)
    for line in scad_code.split("\n"):
        line = line.strip()
        if "=" in line and not line.startswith("//") and not line.startswith("$"):
            parts = line.split("=")
            if len(parts) == 2:
                param_name = parts[0].strip().rstrip(",")
                try:
                    param_value = float(parts[1].strip().rstrip(";"))
                    params[param_name] = param_value
                except ValueError:
                    # Non-numeric param, skip for now
                    pass
    
    # If no params found, create dimension-based defaults
    if not params:
        params = {
            "width": round(width, 2),
            "height": round(height, 2),
            "depth": round(depth, 2),
        }
    
    return params


def _fallback_scad(primitive_type: str, dimensions: list, model_name: str) -> str:
    """Generate fallback SCAD code if Ollama is unavailable."""
    width, height, depth = dimensions
    
    if primitive_type == "box":
        return f"""// Fallback: Box shape
width = {width:.2f};
height = {height:.2f};
depth = {depth:.2f};

module {model_name.replace(' ', '_')}_primitive() {{
    translate([-width/2, -height/2, -depth/2])
        cube([width, height, depth]);
}}"""
    
    elif primitive_type == "cylinder":
        radius = max(width, depth) / 2
        return f"""// Fallback: Cylinder shape
radius = {radius:.2f};
height = {height:.2f};

module {model_name.replace(' ', '_')}_primitive() {{
    cylinder(h=height, r=radius, center=true);
}}"""
    
    else:  # sphere
        radius = max(dimensions) / 2
        return f"""// Fallback: Sphere shape
radius = {radius:.2f};

module {model_name.replace(' ', '_')}_primitive() {{
    sphere(r=radius);
}}"""
