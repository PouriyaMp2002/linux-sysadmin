# Verification commands

These VM checks are **not yet executed**. Expected results below are targets,
not claims of success. Use only a new test file you own and are authorized to
delete. Never delete an existing shared document to test this application.

## Automated local application tests

From the extracted source directory, in a virtual environment with
`requirements.txt` installed:

```bash
python3 -m unittest -v test_app.py
```

Uses Python's standard-library unittest, temporary local directories and
simulated failures. No third-party testing dependencies, real mounts, VM
changes or production files. Test mode temporarily disables the NFS
requirement only inside the test process. See TEST_RESULTS.md for scope.

## 1–5. Website, listing, upload, download, delete

On client01 (requires curl and Python 3), prepare a unique test document and
obtain a session cookie plus CSRF token from the same homepage:

```bash
base=http://10.0.2.11
lab_tmp=$(mktemp -d)
test_name="portal-lab-$(date +%s)-$$.txt"
printf 'Company portal NFS round trip\n' > "$lab_tmp/source.txt"
curl --fail --max-time 10 -c "$lab_tmp/cookies" "$base/" -o "$lab_tmp/page.html"
token=$(python3 -c 'import re,sys; print(re.search(r"name=\"csrf_token\" value=\"([a-f0-9]+)\"",sys.stdin.read())[1])' < "$lab_tmp/page.html")
printf 'Authorized test filename: %s\n' "$test_name"
curl --max-time 40 -b "$lab_tmp/cookies" -o "$lab_tmp/upload.html" -w '%{http_code}\n' \
  -F "csrf_token=$token" -F "file=@$lab_tmp/source.txt;filename=$test_name" "$base/upload"
curl --fail --max-time 10 -b "$lab_tmp/cookies" "$base/" -o "$lab_tmp/list.html"
grep -F "$test_name" "$lab_tmp/list.html"
curl --fail --max-time 10 "$base/download/$test_name" -o "$lab_tmp/download.txt"
cmp "$lab_tmp/source.txt" "$lab_tmp/download.txt"
```

Expected: homepage 200 contains `Company Internal Portal`; upload prints 303;
listing contains the name; download succeeds and cmp exits 0 (no output).
Do not use `curl -L` to hide the upload/delete status.

**Before deleting**, on storage01, set the exact filename printed above:

```bash
test_name='PASTE_THE_PRINTED_TEST_FILENAME'
sudo -u companyportal stat -c '%u:%g %a %n' "/srv/company-data/documents/$test_name"
sudo -u companyportal cat "/srv/company-data/documents/$test_name"
```

Expected: UID 2500, normally GID 2500 (an existing setgid parent can supply its
group), mode 600, correct content. This verifies the upload actually reached
storage01. Do not change the existing directory group policy for this test.

Back on client01, with the original shell variables intact:

```bash
# A confirmation GET must NOT delete anything.
curl --fail --max-time 10 "$base/delete/$test_name" -o "$lab_tmp/confirm.html"
grep -F 'Confirm delete' "$lab_tmp/confirm.html"
curl --max-time 10 -b "$lab_tmp/cookies" -o /dev/null -w '%{http_code}\n' \
  --data-urlencode "csrf_token=$token" "$base/delete/$test_name"
curl --max-time 10 -o /dev/null -w '%{http_code}\n' "$base/download/$test_name"
```

Expected: confirmation 200, deletion 303, subsequent download 404. On
storage01, `sudo -u companyportal test ! -e "/srv/company-data/documents/$test_name"`
should exit 0. The portal has no authentication, so "authorized" here means
only the uniquely named document you created and have permission to remove.

## 6. Invalid filenames, CSRF, and overwrite protection

On client01, reuse the cookie/token above:

```bash
curl --max-time 10 -b "$lab_tmp/cookies" -o /dev/null -w '%{http_code}\n' \
  -F "csrf_token=$token" -F "file=@$lab_tmp/source.txt;filename=../escape.txt" "$base/upload"
curl --max-time 10 -b "$lab_tmp/cookies" -o /dev/null -w '%{http_code}\n' \
  -F "file=@$lab_tmp/source.txt;filename=$test_name" "$base/upload"
```

Expected: both 400; no file published. For duplicate protection, repeat the
successful upload command twice for your unique test name: first 303, second
409. Download and compare to verify the original content is unchanged, then
remove that same test file with the valid CSRF delete command.

## 7. Upload limit

```bash
dd if=/dev/zero of="$lab_tmp/oversize.txt" bs=1M count=10 status=none
curl --max-time 40 -b "$lab_tmp/cookies" -o /dev/null -w '%{http_code}\n' \
  -F "csrf_token=$token" -F "file=@$lab_tmp/oversize.txt;filename=$test_name" "$base/upload"
```

Expected: 413, since a 10 MiB file plus multipart overhead exceeds Flask's
10 MiB request limit. No final test file should exist on storage01. Nginx
rejects requests above its separate 11 MiB ceiling with 413 as well.

## 8. Storage unavailable

First run a **controlled simulation** on web01. This changes only the app's
configured storage path temporarily, without unmounting or editing NFS,
exports, disks or storage permissions. The existing real NFS must remain
mounted so the service's startup checks succeed.

```bash
sudo install -d -m 0755 /etc/systemd/system/company-portal.service.d
# Choose a new filename; stop if this test override already exists.
sudo test ! -e /etc/systemd/system/company-portal.service.d/90-portal-storage-test.conf
# Run the following tee only if that test exited 0.
sudo tee /etc/systemd/system/company-portal.service.d/90-portal-storage-test.conf > /dev/null <<'UNIT'
[Service]
# Added after the main unit's environment file; this value takes precedence.
EnvironmentFile=/etc/company-portal/storage-failure-test.env
UNIT
sudo test ! -e /etc/company-portal/storage-failure-test.env
# Run this tee only if that test exited 0.
printf 'DOCUMENT_MOUNT=/run/company-portal-missing-nfs-test\n' | sudo tee /etc/company-portal/storage-failure-test.env > /dev/null
sudo systemctl daemon-reload
sudo systemctl restart company-portal
curl --max-time 5 -i http://10.0.2.11/health
curl --max-time 5 -i http://10.0.2.11/ready
curl --max-time 5 -i http://10.0.2.11/
```

Expected: health 200; ready and homepage 503 with a storage error. Upload
should also fail 503. Confirm no local fallback directory was created:
`test ! -e /run/company-portal-missing-nfs-test` should exit 0.

Remove only the two test files just created and restore:

```bash
sudo rm /etc/systemd/system/company-portal.service.d/90-portal-storage-test.conf
sudo rm /etc/company-portal/storage-failure-test.env
sudo systemctl daemon-reload
sudo systemctl restart company-portal
curl --fail --max-time 5 http://10.0.2.11/ready
```

Expected: ready 200. This tests application failure handling, **not a real
NFS network outage**. Unit tests also cover unwritable storage and an absent
NFS mount without changing VM mounts.

For an actual outage drill, use a planned lab maintenance window with no
uploads/deletes: temporarily disconnect storage01's VM network in VirtualBox,
query readiness with `curl --max-time 40 -i`, then reconnect and inspect both
servers' logs. With hard NFS, expect a timeout/504 or blocked request instead
of guaranteed 503. Do not alter mount options, force unmount, or change
`root_squash`. If stopping the mount unit intentionally, systemd may stop the
portal via the dependency, and Nginx may return 502. Restore the mount and
start the portal afterwards. These are infrastructure failures, distinct
from returned storage I/O errors handled with 503.

## 9. Service restart and crash recovery

On web01:

```bash
sudo systemctl restart company-portal
sudo systemctl is-active company-portal
curl --fail --max-time 5 http://10.0.2.11/health
curl --fail --max-time 5 http://10.0.2.11/ready
```

Expected: active and both endpoints 200. To test automatic crash recovery
when no writes are active:

```bash
sudo systemctl kill --kill-whom=main --signal=SIGKILL company-portal
# Wait at least RestartSec=5 seconds, then run:
sudo systemctl status company-portal --no-pager
curl --fail --max-time 5 http://10.0.2.11/health
sudo journalctl -u company-portal -n 40 --no-pager
```

Expected: a restart in the journal, a new Gunicorn master PID, and health 200.

## 10. Reboot persistence

On web01, during an agreed lab maintenance window:

```bash
systemctl is-enabled company-portal
sudo reboot
```

After web01 returns, reconnect:

```bash
findmnt --mountpoint /mnt/company-documents
systemctl is-active company-portal
systemctl is-enabled company-portal
curl --fail --max-time 5 http://10.0.2.11/health
curl --fail --max-time 5 http://10.0.2.11/ready
sudo journalctl -b -u company-portal --no-pager
```

Expected: original NFS mounted, service active/enabled, both endpoints 200.
If boot failed, check network-online, existing persistent mount configuration,
UID/GID permissions, and journald before changing application code.
