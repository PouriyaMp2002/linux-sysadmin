#!/bin/bash
# Directory: /usr/local/sbin/company-backup.sh
REPOSITORY="sftp:backup01:/srv/backups/restic"
PASSWORD_FILE="/etc/restic/password"
SOURCE="/srv/company-data/documents"

echo "Starting company documents backup"

findmnt -M /srv/company-data >/dev/null

ssh backup01 \
    'test "$(findmnt -n -o TARGET -M /srv/backups)" = "/srv/backups" &&
     test -w /srv/backups/restic'

restic -r "$REPOSITORY" \
    --password-file "$PASSWORD_FILE" \
    backup "$SOURCE"

echo "Company documents backup completed successfully."
