"""Local staging, isolated from indexes."""
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
STORE = Path(os.environ.get("UI_DATA_DIR", ROOT / "data" / "ui")).resolve()
if os.name == "nt" and STORE.drive.lower() != "d:":
    raise RuntimeError("UI_DATA_DIR должен находиться на диске D:")
MAX_BYTES = 20 * 1024 * 1024
EXTENSIONS = {".pdf", ".docx", ".xlsx"}


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def stage_file(name, content, owner):
    name = re.split(r"[/\\]", name)[-1]
    suffix = Path(name).suffix.lower()
    if suffix not in EXTENSIONS:
        raise ValueError("Поддерживаются только PDF, DOCX и XLSX.")
    if not content or len(content) > MAX_BYTES:
        raise ValueError("Файл должен быть непустым и не больше 20 МБ.")
    if not re.fullmatch(r"[a-f0-9]{32}", owner):
        raise ValueError("Некорректная сессия")
    digest = hashlib.sha256(content).hexdigest()
    directory = STORE / "staging" / owner
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (digest + suffix)
    path.write_bytes(content)
    return {"id": digest + suffix, "name": name, "type": suffix[1:].upper(),
            "size": len(content), "added": datetime.now(timezone.utc).isoformat(),
            "status": "Загружен · ожидает обновления базы", "owner": owner}


def delete_file(item):
    owner, identifier = item["owner"], item["id"]
    if not re.fullmatch(r"[a-f0-9]{32}", owner) or not re.fullmatch(r"[a-f0-9]{64}\.(pdf|docx|xlsx)", identifier):
        raise ValueError("Некорректный идентификатор файла")
    path = STORE / "staging" / owner / identifier
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Ссылки в staging не поддерживаются")
    path.unlink(missing_ok=True)


def valid_url(value):
    try:
        parsed = urlsplit(value)
        return (parsed.scheme in {"https", "http"} and bool(parsed.hostname)
                and not parsed.username and not parsed.password and not any(c.isspace() for c in value))
    except ValueError:
        return False
