import hashlib
import json
import os
import re
import shutil
from pathlib import Path
import pypdfium2 as pdfium
from docx import Document as WordDocument
from docx.table import Table
from docx.text.paragraph import Paragraph
from openpyxl import load_workbook
from .settings import ROOT, DATA


def units(path):
    """Yield content and exact source locator, in original order."""
    if path.suffix.lower() == ".pdf":
        import pytesseract
        exe = os.environ.get("TESSERACT_CMD") or shutil.which("tesseract")
        local = ROOT / "tools/tesseract/tesseract.exe"
        if not exe and local.exists(): exe = str(local)
        alias = Path("D:/hackathon-work/tools/tesseract")
        if os.name == "nt" and alias.exists() and not os.environ.get("TESSDATA_PREFIX"):
            os.environ["TESSDATA_PREFIX"] = str(alias / "tessdata")
        if exe: pytesseract.pytesseract.tesseract_cmd = exe
        doc = pdfium.PdfDocument(path)
        try:
            for i, page in enumerate(doc):
                text = page.get_textpage().get_text_bounded()
                ocr = len(text.strip()) < 80
                if ocr:
                    if not exe: raise RuntimeError(f"Для страницы {i+1} нужен Tesseract rus+eng")
                    cache = DATA / "ocr" / (hashlib.sha256(path.read_bytes()).hexdigest() + f"-{i+1}.txt")
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    if cache.exists(): text = cache.read_text(encoding="utf-8")
                    else:
                        text = pytesseract.image_to_string(page.render(scale=2.5).to_pil(), lang="rus+eng", config="--psm 3", timeout=120)
                        cache.write_text(text, encoding="utf-8")
                yield text, {"locator": f"стр. {i+1}", "page": i+1, "ocr": ocr, "parent_id": f"page-{i+1}"}
        finally:
            doc.close()
    elif path.suffix.lower() == ".docx":
        doc = WordDocument(path)
        for i, child in enumerate(doc.element.body):
            if child.tag.endswith("}p"):
                text = Paragraph(child, doc).text
                yield text, {"locator": f"абзац {i+1}", "parent_id": f"block-{i+1}"}
            elif child.tag.endswith("}tbl"):
                table = Table(child, doc)
                for j, row in enumerate(table.rows):
                    text = " | ".join(dict.fromkeys(c.text for c in row.cells))
                    yield text, {"locator": f"таблица в блоке {i+1}, строка {j+1}", "parent_id": f"table-{i+1}"}
    elif path.suffix.lower() == ".xlsx":
        book = load_workbook(path, data_only=False)
        values = load_workbook(path, data_only=True)
        for sheet in book:
            for row in sheet:
                cells = []
                for cell in row:
                    if cell.value is None: continue
                    v = cell.value
                    if cell.data_type == "f":
                        cached = values[sheet.title][cell.coordinate].value
                        v = f"формула {v}; сохранённое значение: {cached if cached is not None else 'не вычислено'}"
                    cells.append(f"{cell.coordinate}: {v}")
                if cells:
                    yield " | ".join(cells), {"locator": f"лист {sheet.title}, строка {row[0].row}", "sheet": sheet.title, "parent_id": f"sheet-{sheet.title}-row-{row[0].row}", "merged_ranges": [str(r) for r in sheet.merged_cells.ranges if r.min_row <= row[0].row <= r.max_row]}
        book.close(); values.close()
    else:
        raise ValueError(f"Неподдерживаемый формат: {path.suffix}")


def ingest():
    docs, manifest, errors = [], [], []
    raw = DATA / "raw"
    if not raw.exists(): raise RuntimeError("Нет data/raw. Сначала скачайте документы.")
    for path in sorted(raw.rglob("*")):
        if not path.is_file(): continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        date = re.search(r"\b\d{2}\.\d{2}\.\d{4}\b", path.name)
        base = {"name": path.name, "relative_path": path.relative_to(raw).as_posix(), "sha256": digest, "date_hint": date.group() if date else None, "validity": "не подтверждена"}
        count = 0
        section = ""
        try:
            pending = []
            for text, meta in units(path):
                text = re.sub(r"[ \t]+", " ", text).strip()
                if not text: continue
                for line in text.splitlines():
                    if re.match(r"^\d+(?:\.\d+)*\.?\s+\S", line.strip()): section = line.strip()[:180]; break
                words = text.split()
                # Conservative 110-word windows stay below multilingual tokenizer limit in most cases.
                for start in range(0, len(words), 90):
                    content = " ".join(words[start:start+110])
                    m = dict(base, **meta, section=section, word_start=start)
                    cid = hashlib.sha256(json.dumps([digest, meta["locator"], start], ensure_ascii=False).encode()).hexdigest()[:24]
                    pending.append({"id": cid, "content": content, "meta": m})
            docs.extend(pending); count = len(pending)
        except Exception as exc:
            errors.append({"name": path.name, "error": str(exc)})
        manifest.append(dict(base, chunks=count))
        print(path.name, count, flush=True)
    DATA.mkdir(exist_ok=True)
    (DATA / "manifest.json").write_text(json.dumps({"files": manifest, "errors": errors}, ensure_ascii=False, indent=2), encoding="utf-8")
    if errors:
        raise RuntimeError("Индекс не заменён: ошибки обработки. См. data/manifest.json")
    if not docs: raise RuntimeError("Нет извлечённого текста")
    tmp = DATA / "chunks.tmp"
    tmp.write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
    tmp.replace(DATA / "chunks.json")
    return docs
