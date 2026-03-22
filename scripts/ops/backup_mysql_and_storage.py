from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a MySQL dump plus storage archive backup set.")
    parser.add_argument("--database-url", required=True, help="MySQL SQLAlchemy URL")
    parser.add_argument("--mysqldump", required=True, help="Path to mysqldump.exe")
    parser.add_argument("--storage-dir", default="backend/storage", help="Storage directory to archive")
    parser.add_argument("--output-dir", default="backups", help="Output directory for backup sets")
    return parser.parse_args()


def parse_database_url(database_url: str) -> dict[str, str]:
    parsed = urlsplit(database_url)
    if not parsed.scheme.startswith("mysql"):
        raise ValueError("Only MySQL URLs are supported by this backup script.")
    username = parsed.username or ""
    password = parsed.password or ""
    hostname = parsed.hostname or "127.0.0.1"
    port = str(parsed.port or 3306)
    database = parsed.path.lstrip("/")
    return {
        "username": username,
        "password": password,
        "hostname": hostname,
        "port": port,
        "database": database,
    }


def main() -> int:
    args = parse_args()
    db = parse_database_url(args.database_url)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = Path(args.output_dir).resolve() / f"mysql_backup_{timestamp}"
    backup_root.mkdir(parents=True, exist_ok=True)

    dump_path = backup_root / "database.sql"
    storage_zip_base = backup_root / "storage"
    storage_dir = Path(args.storage_dir).resolve()

    run_dump(args.mysqldump, db, dump_path)
    archive_path = shutil.make_archive(str(storage_zip_base), "zip", root_dir=storage_dir)

    manifest = {
        "created_at": timestamp,
        "database": {
            "host": db["hostname"],
            "port": db["port"],
            "database": db["database"],
            "dump_file": dump_path.name,
        },
        "storage": {
            "source_dir": str(storage_dir),
            "archive_file": Path(archive_path).name,
        },
    }
    (backup_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(backup_root))
    return 0


def run_dump(mysqldump_path: str, db: dict[str, str], dump_path: Path) -> None:
    command = [
        mysqldump_path,
        f"--host={db['hostname']}",
        f"--port={db['port']}",
        f"--user={db['username']}",
        f"--password={db['password']}",
        "--single-transaction",
        "--no-tablespaces",
        "--default-character-set=utf8mb4",
        db["database"],
    ]
    with dump_path.open("wb") as output_file:
        subprocess.run(command, check=True, stdout=output_file)


if __name__ == "__main__":
    raise SystemExit(main())
