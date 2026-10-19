#!/bin/bash
# Directory: /usr/local/sbin/company-backup-maintenance.sh

REPO="sftp:backup01-restic:/srv/backups/restic"
PASSWORD="/etc/restic/password"

echo "Checking backup destination..."

ssh backup01-restic \
  'test "$(findmnt -n -o TARGET -M /srv/backups)" = "/srv/backups" &&
   test -w /srv/backups/restic'

echo "Applying retention policy..."

restic -r "$REPO" \
  --password-file "$PASSWORD" \
  forget \
  --keep-daily 7 \
  --keep-weekly 4 \
  --keep-monthly 3

echo "Removing unreferenced backup data..."

restic -r "$REPO" \
  --password-file "$PASSWORD" \
  prune

echo "Maintenance completed successfully."
