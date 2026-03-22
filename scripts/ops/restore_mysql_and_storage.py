from __future__ import annotations

import argparse
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.parse import urlsplit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore a MySQL dump plus storage archive backup set.")
    parser.add_argument("--database-url", required=True, help="MySQL SQLAlchemy URL")
    parser.add_argument("--mysql", required=True, help="Path to mysql.exe")
    parser.add_argument("--backup-dir", required=True, help="Backup directory created by backup_mysql_and_storage.py")
    parser.add_argument("--storage-dir", default="backend/storage", help="Target storage directory")
    parser.add_argument("--clean-storage", action="store_true", help="Delete current storage directory contents before restore")
    return parser.parse_args()


def parse_database_url(database_url: str) -> dict[str, str]:
    parsed = urlsplit(database_url)
    if not parsed.scheme.startswith("mysql"):
        raise ValueError("Only MySQL URLs are supported by this restore script.")
    return {
        "username": parsed.username or "",
        "password": parsed.password or "",
        "hostname": parsed.hostname or "127.0.0.1",
        "port": str(parsed.port or 3306),
        "database": parsed.path.lstrip("/"),
    }


def main() -> int:
    args = parse_args()
    backup_dir = Path(args.backup_dir).resolve()
    dump_path = backup_dir / "database.sql"
    storage_archive = backup_dir / "storage.zip"
    storage_dir = Path(args.storage_dir).resolve()
    db = parse_database_url(args.database_url)

    if not dump_path.exists():
        raise FileNotFoundError(f"Missing database dump: {dump_path}")
    if not storage_archive.exists():
        raise FileNotFoundError(f"Missing storage archive: {storage_archive}")

    restore_database(args.mysql, db, dump_path)
    restore_storage(storage_archive, storage_dir, clean_storage=args.clean_storage)
    print(str(backup_dir))
    return 0


def restore_database(mysql_path: str, db: dict[str, str], dump_path: Path) -> None:
    command = [
        mysql_path,
        f"--host={db['hostname']}",
        f"--port={db['port']}",
        f"--user={db['username']}",
        f"--password={db['password']}",
        "--default-character-set=utf8mb4",
        db["database"],
    ]
    with dump_path.open("rb") as input_file:
        subprocess.run(command, check=True, stdin=input_file)


def restore_storage(archive_path: Path, storage_dir: Path, *, clean_storage: bool) -> None:
    if clean_storage and storage_dir.exists():
        shutil.rmtree(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(storage_dir)


if __name__ == "__main__":
    raise SystemExit(main())
