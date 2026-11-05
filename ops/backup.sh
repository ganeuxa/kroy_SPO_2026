#!/bin/sh
# Run while application writes are stopped (see release runbook).
set -eu
umask 077
stamp=$(date -u +%Y%m%dT%H%M%SZ)
dest=/backups/$stamp
mkdir -p "$dest"
trap 'echo "Backup incomplete: $dest" >&2' EXIT
pg_dump -h db -U "$PGUSER" -d "$PGDATABASE" -Fc -f "$dest/database.dump"
pg_restore --list "$dest/database.dump" > "$dest/database.list"
tar -czf "$dest/media.tar.gz" -C /media .
tar -tzf "$dest/media.tar.gz" > "$dest/media.list"
(cd "$dest" && sha256sum database.dump media.tar.gz > SHA256SUMS)
printf '%s\n' "$RELEASE_REVISION" > "$dest/revision.txt"
touch "$dest/COMPLETE"
trap - EXIT
echo "Backup complete: $stamp"
