import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from zipfile import ZipFile
import pypdfium2 as pdfium
from docx import Document as WordDocument
from docx.table import Table
from docx.text.paragraph import Paragraph
from openpyxl import load_workbook
from .settings import ROOT, DATA

FORMATS = {".pdf", ".docx", ".xlsx"}


def input_files(raw):
    return sorted(path for path in raw.rglob("*") if path.is_file()
                  and path.name.lower() not in {".ds_store", "thumbs.db", "desktop.ini"}
                  and not path.name.startswith("~$"))


def units(path, *, digest=None):
    """Yield content and exact source locator, in original order."""
    if path.suffix.lower() in {".docx", ".xlsx"}:
        with ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > 10000 or sum(item.file_size for item in entries) > 256 * 1024**2:
                raise ValueError("Превышен лимит распаковки документа")
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
            if len(doc) > 1500:
                raise ValueError("PDF содержит больше 1500 страниц")
            for i, page in enumerate(doc):
                text = page.get_textpage().get_text_bounded()
                ocr = len(text.strip()) < 80
                if ocr:
                    if not exe: raise RuntimeError(f"Для страницы {i+1} нужен Tesseract rus+eng")
                    digest = digest or hashlib.sha256(path.read_bytes()).hexdigest()
                    cache = DATA / "ocr" / (digest + f"-{i+1}.txt")
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
                paragraph = Paragraph(child, doc)
                text = paragraph.text
                properties = child.pPr
                numbering = None
                if properties is not None and properties.numPr is not None:
                    numbering = {"num_id": properties.numPr.numId.val if properties.numPr.numId is not None else None, "level": properties.numPr.ilvl.val if properties.numPr.ilvl is not None else 0}
                yield text, {"locator": f"абзац {i+1}", "parent_id": f"block-{i+1}", "style": paragraph.style.name if paragraph.style else None, "numbering": numbering}
            elif child.tag.endswith("}tbl"):
                table = Table(child, doc)
                for j, row in enumerate(table.rows):
                    text = " | ".join(cell.text for cell in row.cells)
                    yield text, {"locator": f"таблица в блоке {i+1}, строка {j+1}", "parent_id": f"table-{i+1}"}
    elif path.suffix.lower() == ".xlsx":
        book = load_workbook(path, data_only=False)
        values = None
        try:
            if sum(sheet.max_row * sheet.max_column for sheet in book) > 2_000_000:
                raise ValueError("Превышен лимит области ячеек XLSX")
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
        finally:
            book.close()
            if values is not None:
                values.close()
    else:
        raise ValueError(f"Неподдерживаемый формат: {path.suffix}")


def ingest(raw=None, output=None):
    docs, manifest, errors, source_documents = [], [], [], []
    raw = Path(raw) if raw is not None else DATA / "raw"
    output = Path(output) if output is not None else DATA
    if not raw.exists(): raise RuntimeError("Нет data/raw. Сначала скачайте документы.")
    for path in input_files(raw):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        date = re.search(r"\b\d{2}\.\d{2}\.\d{4}\b", path.name)
        relative_path = path.relative_to(raw).as_posix()
        base = {"name": path.name, "relative_path": relative_path, "document_id": relative_path, "document_version_id": digest, "sha256": digest, "date_hint": date.group() if date else None, "validity": "не подтверждена"}
        count = 0
        section = ""
        source_parts = []
        source_offset = 0
        try:
            if path.suffix.lower() not in FORMATS:
                raise ValueError(f"Неподдерживаемый формат: {path.suffix or 'без расширения'}")
            pending = []
            for text, meta in units(path, digest=digest):
                text = re.sub(r"[ \t]+", " ", text).strip()
                if not text: continue
                unit_start = source_offset
                unit_end = unit_start + len(text)
                source_parts.append(text)
                source_offset = unit_end + 2
                from .structure import heading_from_text
                if meta.get("sheet"):
                    section = f"Лист: {meta['sheet']}"
                else:
                    for line in text.splitlines():
                        heading = heading_from_text(line, meta.get("style"), meta.get("numbering"))
                        if heading:
                            section = heading["title"]
                            meta["heading"] = heading
                            break
                words = list(re.finditer(r"\S+", text))
                # Conservative 110-word windows stay below multilingual tokenizer limit in most cases.
                for start in range(0, len(words), 90):
                    selected = words[start:start+110]
                    content = " ".join(word.group() for word in selected)
                    char_start = unit_start + selected[0].start()
                    char_end = unit_start + selected[-1].end()
                    span = {"document_id": relative_path, "start": char_start, "end": char_end}
                    m = dict(base, **meta, section=section, word_start=start, chunk_id=None, source_span=span, unit_source_span={"start": unit_start, "end": unit_end}, original_content=content)
                    identity = [digest, meta["locator"], start, relative_path]
                    cid = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:24]
                    m["chunk_id"] = cid
                    pending.append({"id": cid, "content": content, "meta": m})
            docs.extend(pending); count = len(pending)
            source_documents.append({"document_id": relative_path, "name": path.name, "sha256": digest, "text": "\n\n".join(source_parts)})
        except Exception as exc:
            errors.append({"name": path.name, "error": str(exc)})
        manifest.append(dict(base, chunks=count))
        print(path.name, count, flush=True)
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps({"files": manifest, "errors": errors}, ensure_ascii=False, indent=2), encoding="utf-8")
    if errors:
        first = errors[0]
        raise RuntimeError(f"Ошибка обработки {first['name']}: {first['error']}")
    if not docs: raise RuntimeError("Нет извлечённого текста")
    tmp = output / "chunks.tmp"
    tmp.write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
    tmp.replace(output / "chunks.json")
    tmp = output / "source_documents.tmp"
    tmp.write_text(json.dumps(source_documents, ensure_ascii=False), encoding="utf-8")
    tmp.replace(output / "source_documents.json")
    return docs
