from __future__ import annotations
from typing import Optional
from pydantic import BaseModel

from starter.model.project import Project
from starter.store import JsonFileProjectStore

_STORE = JsonFileProjectStore("./data")

class SaveProjectArgs(BaseModel):
    project: Project

def save_project(args: SaveProjectArgs) -> str:
    _STORE.save_project(args.project)
    return f"Saved project {args.project.pid}"

class LoadProjectArgs(BaseModel):
    pid: str

def load_project(args: LoadProjectArgs) -> Project:
    return _STORE.load_project(args.pid)

class CreateProjectArgs(BaseModel):
    pid: str
    title: Optional[str] = ""

def create_project(args: CreateProjectArgs) -> Project:
    return Project(pid=args.pid, title=args.title or "")