"""Daily SQLite database backup script.

Usage:
    python scripts/backup.py          # manual backup
    python scripts/backup.py --restore data/backups/portfolio_20260521.db  # restore from backup
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "portfolio.db"
BACKUP_DIR = PROJECT_ROOT / "data" / "backups"


def backup() -> Path:
    """Create a timestamped backup of the database."""
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"portfolio_{timestamp}.db"

    shutil.copy2(DB_PATH, backup_path)

    # Keep only last 30 backups
    backups = sorted(BACKUP_DIR.glob("portfolio_*.db"))
    for old in backups[:-30]:
        old.unlink()

    print(f"Backup created: {backup_path}")
    print(f"Database size: {DB_PATH.stat().st_size / 1024:.1f} KB")
    print(f"Total backups: {len(backups[-30:])}")
    return backup_path


def restore(backup_path: Path) -> None:
    """Restore database from a backup file."""
    if not backup_path.exists():
        print(f"Backup not found: {backup_path}")
        sys.exit(1)

    # Safety: keep current db as .db.bak before overwriting
    if DB_PATH.exists():
        bak_path = DB_PATH.with_suffix(".db.bak")
        shutil.copy2(DB_PATH, bak_path)
        print(f"Current DB saved to: {bak_path}")

    shutil.copy2(backup_path, DB_PATH)
    print(f"Restored from: {backup_path}")
    print(f"Database size: {DB_PATH.stat().st_size / 1024:.1f} KB")


def main():
    parser = argparse.ArgumentParser(description="Database backup/restore")
    parser.add_argument("--restore", type=Path, help="Restore from backup file")
    args = parser.parse_args()

    if args.restore:
        restore(args.restore)
    else:
        backup()


if __name__ == "__main__":
    main()
