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
MAX_BYTES = 20 * 1024 * 1024
EXTENSIONS = {".pdf", ".docx", ".xlsx"}


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def load_workspace(path, defaults):
    from .services import validate_response

    saved = load_json(path, {})
    if not isinstance(saved, dict) or saved.get("schema_version", 1) != 1:
        raise ValueError("Некорректная версия рабочего пространства")
    owner = saved.get("owner")
    if not isinstance(owner, str) or not re.fullmatch(r"[a-f0-9]{32}", owner):
        raise ValueError("Некорректная сессия")
    chats, active, files = saved.get("chats"), saved.get("active"), saved.get("files")
    if not isinstance(chats, dict) or not isinstance(active, str) or active not in chats or not isinstance(files, list):
        raise ValueError("Некорректная история")
    for chat in chats.values():
        if not isinstance(chat, dict) or not isinstance(chat.get("title"), str) or not isinstance(chat.get("turns"), list):
            raise ValueError("Некорректный диалог")
        for turn in chat["turns"]:
            if not isinstance(turn, dict) or not isinstance(turn.get("question"), str) or not re.fullmatch(
                r"[a-f0-9]{32}", str(turn.get("id"))
            ):
                raise ValueError("Некорректный запрос")
            result = validate_response(turn.get("result"))
            if not isinstance(result.get("metadata"), dict):
                raise ValueError("Некорректные метаданные ответа")
    for item in files:
        if not isinstance(item, dict) or item.get("owner") != owner or not re.fullmatch(
            r"[a-f0-9]{64}\.(pdf|docx|xlsx)", str(item.get("id"))
        ) or any(not isinstance(item.get(k), str) for k in ("name", "type", "added")) or type(item.get("size")) is not int:
            raise ValueError("Некорректная запись о файле")
    settings = saved.get("settings")
    if not isinstance(settings, dict) or any(type(settings.get(k, val)) is not type(val) for k, val in defaults.items()):
        raise ValueError("Некорректные настройки")
    if settings.get("retrieval", "fast") not in ("fast", "quality") or settings.get("generation", "legacy") not in ("legacy", "g2"):
        raise ValueError("Некорректный профиль")
    snapshot = saved.get("snapshot")
    if snapshot is not None and (not isinstance(snapshot, str) or not Path(snapshot).resolve().is_relative_to(
        (STORE / "corpus" / owner).resolve()
    )):
        raise ValueError("Снимок вне рабочего пространства")
    rebuild_required = saved.get("rebuild_required", bool(files))
    if type(rebuild_required) is not bool:
        raise ValueError("Некорректное состояние индекса")
    mode = saved.get("mode")
    if mode is not None and mode not in ("Подключённый", "Демонстрационный"):
        raise ValueError("Некорректный источник ответов")
    return dict(settings={**defaults, **settings}, chats=chats, active=active,
                files=files, owner=owner, snapshot=snapshot, rebuild_required=rebuild_required,
                **({"mode": mode} if mode is not None else {}))


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
