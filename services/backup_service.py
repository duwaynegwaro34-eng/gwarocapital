from datetime import datetime, timezone
from pathlib import Path
import shutil


class BackupService:
    def __init__(self, backup_dir):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, sqlite_file_path):
        source = Path(sqlite_file_path)
        if not source.exists():
            return {
                "ok": False,
                "message": "Database file not found.",
                "path": None,
            }

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        destination = self.backup_dir / f"gwaro_backup_{stamp}.db"
        shutil.copy2(source, destination)
        return {
            "ok": True,
            "message": "Backup created.",
            "path": str(destination),
        }

    def restore_backup(self, backup_file_path, sqlite_file_path):
        backup = Path(backup_file_path)
        destination = Path(sqlite_file_path)

        if not backup.exists():
            return {
                "ok": False,
                "message": "Backup file not found.",
            }

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, destination)
        return {
            "ok": True,
            "message": "Database restored from backup.",
            "path": str(destination),
        }

    def list_backups(self):
        backups = sorted(self.backup_dir.glob("*.db"), reverse=True)
        return [str(path) for path in backups]
