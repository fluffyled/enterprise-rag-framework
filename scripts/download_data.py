from pathlib import Path
import gdown
root = Path(__file__).resolve().parent.parent
out = root / "data/raw"
out.mkdir(parents=True, exist_ok=True)
result = gdown.download_folder(id="1aiZJAAns_mM5amYpxwfflWu64ZE7KIcy", output=str(out), quiet=False)
if not result:
    raise SystemExit("Не удалось скачать датасет. Проверьте доступ Google Drive.")
print(f"Скачано {len(result)} файлов. Не публикуйте их без разрешения владельца.")
