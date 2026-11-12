from pathlib import Path

from huggingface_hub import snapshot_download


MODELS = Path(__file__).resolve().parent.parent / "models"


REVISION = "5617a9f61b028005a4858fdac845db406aefb181"


def main():
    path = snapshot_download("BAAI/bge-m3", revision=REVISION, local_dir=MODELS / "bge-m3")
    print(path)


if __name__ == "__main__":
    main()
