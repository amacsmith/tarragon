"""Models for the application."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Account:
    id: Optional[int]
    makerworld_token: Optional[str]
    created_at: str


@dataclass
class Collection:
    id: Optional[int]
    account_id: int
    name: str
    external_id: str


@dataclass
class Model:
    id: Optional[int]
    collection_id: int
    external_id: str
    name: str
    thumbnail_url: Optional[str]
    mesh_file_path: Optional[str]


@dataclass
class SCADJob:
    id: Optional[int]
    model_id: int
    status: str
    scad_code: Optional[str]
    params_json: Optional[str]
    created_at: str
