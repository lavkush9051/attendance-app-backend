# app/storage.py
from sqlalchemy.orm import Session
from app.models import Employee
import os, uuid
from pathlib import Path, PurePosixPath
from typing import Tuple
from fastapi import UploadFile

SAFE_CHARS = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


stored_faces = {}  # {username: [descriptors]}

def save_user(name, descriptors):
    stored_faces[name] = descriptors

def get_all_users():
    return stored_faces.items()

def get_all_employees(db: Session):
    return db.query(Employee).all()

def _safe_filename(name: str) -> str:
    base = ''.join(c for c in name if c in SAFE_CHARS).strip()
    return base or f"file_{uuid.uuid4().hex}"

async def save_upload_to_disk(upload: UploadFile, upload_root: str, subdir: str) -> Tuple[str, int, str]:
    safe_name = _safe_filename(upload.filename or "file")
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"

    # where to write physically
    abs_dir = Path(upload_root) / subdir
    abs_dir.mkdir(parents=True, exist_ok=True)

    abs_path = abs_dir / unique_name
    content = await upload.read()
    abs_path.write_bytes(content)

    # ALWAYS store forward-slash relative path in DB
    rel_path = str(PurePosixPath(subdir) / unique_name)

    size = len(content)
    mime = upload.content_type or "application/octet-stream"

    # helpful debug
    print(f"[UPLOAD] wrote={abs_path} ({size} bytes) rel='{rel_path}' mime='{mime}'")
    return rel_path, size, mime

