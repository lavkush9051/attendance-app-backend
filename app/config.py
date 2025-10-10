# app/config.py
import os

UPLOAD_ROOT = os.getenv("UPLOAD_ROOT", "/app/uploads")  # mount a volume here
os.makedirs(UPLOAD_ROOT, exist_ok=True)