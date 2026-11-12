"""Versioned boundary with developer 1; no Haystack or model dependency."""
from dataclasses import dataclass, asdict
from urllib.parse import urlsplit

@dataclass(frozen=True)
class Fragment:
    id: str
    document_id: str
    text: str
    title: str
    locator: str
    topic_ids: tuple[str, ...] = ()
    url: str | None = None
    date_hint: str | None = None
    order: int = 0
    complete: bool = False

    def __post_init__(self):
        for key in ("id", "document_id", "text", "title", "locator"):
            value = getattr(self, key)
            if not isinstance(value, str) or not value.strip(): raise ValueError(f"Пустое поле {key}")
        if len(self.text) > 16000: raise ValueError("Фрагмент слишком длинный; разделите его по пунктам")
        if not isinstance(self.topic_ids, (list, tuple)) or any(not isinstance(x, str) or not x for x in self.topic_ids):
            raise ValueError("topic_ids должен быть списком идентификаторов")
        if type(self.order) is not int: raise ValueError("order должен быть целым")
        if type(self.complete) is not bool: raise ValueError("complete должен быть boolean")
        if self.url:
            u = urlsplit(self.url)
            if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
                raise ValueError("Недопустимая ссылка источника")

    def to_dict(self): return asdict(self)


def read_bundle(payload):
    if not isinstance(payload, dict) or type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        raise ValueError("Поддерживается schema_version=1")
    items = payload.get("fragments")
    if not isinstance(items, list) or len(items) > 100: raise ValueError("Ожидается список до 100 найденных фрагментов")
    fragments = [Fragment(**item) for item in items]
    if len({x.id for x in fragments}) != len(fragments): raise ValueError("Повторяются ID фрагментов")
    return fragments
