"""Step 1 - get the raw data: download the UCI zip (skipped if present) and unzip it.

The zip is saved under data/raw/uci_online_retail_ii/ and only the one expected
workbook is extracted from it (member names are checked, so nothing can be written
outside that folder). Checksums are compared with the files used for this analysis;
a mismatch is reported but does not stop the run (UCI may re-publish the file).

Run:  python -I src/download.py
"""
import hashlib
import sys
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check(path: Path, expected: str) -> None:
    actual = sha256(path)
    status = "matches" if actual == expected else f"DIFFERS from the analysed file ({expected[:12]}...)"
    print(f"  {path.name}: sha256 {actual[:12]}... {status}")


def ensure_raw() -> None:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    if config.ZIP_PATH.exists():
        print(f"  {config.ZIP_PATH.name} already downloaded - skipping")
    else:
        print(f"  downloading {config.DATA_URL}")
        part = config.ZIP_PATH.with_suffix(".part")
        with requests.get(config.DATA_URL, stream=True, timeout=120) as response:
            response.raise_for_status()
            with open(part, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    handle.write(chunk)
        part.replace(config.ZIP_PATH)
    check(config.ZIP_PATH, config.ZIP_SHA256)

    if not config.XLSX_PATH.exists():
        with zipfile.ZipFile(config.ZIP_PATH) as archive:
            names = archive.namelist()
            if names != [config.XLSX_NAME]:
                raise ValueError(f"unexpected zip contents: {names}")
            archive.extract(config.XLSX_NAME, config.RAW_DIR)
        print(f"  extracted {config.XLSX_NAME}")
    check(config.XLSX_PATH, config.XLSX_SHA256)


if __name__ == "__main__":
    ensure_raw()
