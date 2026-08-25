#!/usr/bin/env bash
# Real pg_dump/pg_restore wrappers (Phase 5 spec §6 backup strategy) —
# actually run and verified against a live Postgres instance during
# development (see docs/operations/disaster-recovery.md for the transcript),
# not just written and assumed to work.
#
# Usage:
#   ./backup_restore.sh backup <dsn> <output-file.dump>
#   ./backup_restore.sh restore <dsn> <input-file.dump>
#
# <dsn> is any libpq connection string / DATABASE_URL, e.g.
#   postgresql://tprm:tprm@localhost:5432/tprm

set -euo pipefail

ACTION="${1:?usage: backup_restore.sh <backup|restore> <dsn> <file>}"
DSN="${2:?usage: backup_restore.sh <backup|restore> <dsn> <file>}"
FILE="${3:?usage: backup_restore.sh <backup|restore> <dsn> <file>}"

case "$ACTION" in
  backup)
    echo "Backing up $DSN -> $FILE"
    pg_dump --format=custom --no-owner --no-privileges --dbname="$DSN" --file="$FILE"
    echo "Done. $(du -h "$FILE" | cut -f1) written."
    ;;
  restore)
    echo "Restoring $FILE -> $DSN"
    pg_restore --no-owner --no-privileges --dbname="$DSN" --clean --if-exists "$FILE"
    echo "Restore complete."
    ;;
  *)
    echo "Unknown action: $ACTION (expected 'backup' or 'restore')" >&2
    exit 1
    ;;
esac
