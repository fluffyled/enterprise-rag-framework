"""Explicit public URL ingestion with DNS pinning, bounded reads, no cookies/proxy."""
import hashlib
import http.client
import ipaddress
import socket
import ssl
from datetime import datetime, timezone
from urllib.parse import urlsplit, urljoin, urldefrag
from .contracts import Fragment

MAX_BYTES = 5 * 1024 * 1024


def public_target(url):
    u = urlsplit(url)
    if u.scheme not in {"http", "https"} or not u.hostname or u.username or u.password:
        raise ValueError("Нужна открытая HTTP(S) ссылка без логина и пароля")
    port = u.port or (443 if u.scheme == "https" else 80)
    if port not in {80, 443}: raise ValueError("Разрешены только порты 80 и 443")
    host = u.hostname.encode("idna").decode("ascii")
    addresses = list(dict.fromkeys(x[4][0] for x in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError("Локальные, служебные и частные адреса недоступны")
    return u, host, port, addresses[0]


def fetch_public(url):
    url = urldefrag(url.strip())[0]
    for _ in range(5):
        u, host, port, address = public_target(url)
        conn = http.client.HTTPConnection(host, port, timeout=15)
        sock = socket.create_connection((address, port), timeout=15)
        try:
            conn.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host) if u.scheme == "https" else sock
            path = u.path or "/"
            if u.query: path += "?" + u.query
            conn.request("GET", path, headers={"User-Agent": "MIPT-Regulation-Navigator/1.0", "Accept-Encoding": "identity"})
            response = conn.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location: raise ValueError("Перенаправление без адреса")
                next_url = urljoin(url, location)
                if u.scheme == "https" and urlsplit(next_url).scheme != "https": raise ValueError("Переход с HTTPS на HTTP запрещен")
                url = next_url
                continue
            if response.status != 200: raise ValueError(f"Источник вернул HTTP {response.status}")
            if response.getheader("Content-Encoding", "identity").lower() != "identity": raise ValueError("Сжатый ответ источника не поддерживается")
            length = response.getheader("Content-Length")
            if length and int(length) > MAX_BYTES: raise ValueError("Документ превышает 5 MiB")
            body = response.read(MAX_BYTES+1)
            if len(body) > MAX_BYTES: raise ValueError("Документ превышает 5 MiB")
            return body, response.getheader("Content-Type", "").split(";")[0].lower(), url
        finally:
            conn.close(); sock.close()
    raise ValueError("Слишком много перенаправлений")


def extract_page(body, content_type, url):
    if content_type == "application/pdf" or body.startswith(b"%PDF-"):
        import pypdfium2
        document = pypdfium2.PdfDocument(body)
        try:
            if len(document) > 80: raise ValueError("Внешний PDF длиннее 80 страниц")
            blocks = [(page.get_textpage().get_text_bounded(), f"стр. {i+1}") for i, page in enumerate(document)]
            if not any(len(text.strip()) >= 80 for text, _ in blocks): raise ValueError("PDF является сканом; передайте его в обработку документов с OCR")
        finally: document.close()
        return urlsplit(url).path.rsplit("/", 1)[-1] or "PDF", blocks
    if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}: raise ValueError("Поддерживаются HTML, текст и PDF с текстовым слоем")
    if content_type == "text/plain": return urlsplit(url).hostname, [(body.decode("utf-8-sig"), "текст страницы")]
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(body, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else urlsplit(url).hostname
    for tag in soup.select("script,style,nav,header,footer,noscript,template,form"): tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    blocks=[]
    for node in main.select("tr,p,li,h1,h2,h3,h4"):
        if node.find_parent(["tr","p","li"]): continue
        cells=node.find_all(["td","th"],recursive=False) if node.name=="tr" else []
        text=" | ".join(c.get_text(" ",strip=True) for c in cells) if cells else node.get_text(" ",strip=True)
        if text: blocks.append((text,f"блок {len(blocks)+1}"))
    return title, blocks or [(main.get_text(" ",strip=True),"текст страницы")]


def load_url(url):
    body, content_type, final_url = fetch_public(url)
    title, blocks = extract_page(body, content_type, final_url)
    if sum(len(text) for text, _ in blocks) > 120000: raise ValueError("Слишком много текста; укажите отдельный раздел")
    doc_id = "web:" + hashlib.sha256(final_url.encode()).hexdigest()[:24]
    revision = hashlib.sha256(body).hexdigest()
    fragments = []
    for number, (text, locator) in enumerate(blocks):
        words = text.split()
        for start in range(0, len(words), 120):
            content = " ".join(words[start:start+160])
            if len(content) < 30: continue
            fid = hashlib.sha256(f"{doc_id}:{revision}:{number}:{start}".encode()).hexdigest()[:24]
            fragments.append(Fragment(fid, doc_id, content, title, locator, url=final_url, order=number*100000+start,complete=(start==0 and len(words)<=160)))
    if not fragments: raise ValueError("На странице нет доступного текста; JavaScript и авторизация не выполняются")
    info = {"document_id": doc_id, "title": title, "url": final_url, "sha256": revision,
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "fragments": len(fragments)}
    return fragments, info
