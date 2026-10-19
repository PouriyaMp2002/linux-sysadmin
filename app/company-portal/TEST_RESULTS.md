# Executed checks

Date: 2026-10-17. Checks ran in the build workspace, not on your VirtualBox VMs.

| Check | Result | Scope |
| --- | --- | --- |
| Python compile (`python3 -m py_compile app.py`) | PASS | Application syntax |
| `python3 -m unittest -v test_app.py` | PASS: 29 tests | Flask test client, temporary local storage, simulated I/O failures |
| Gunicorn `--check-config` with `app:app` | PASS | Import and CLI configuration; temporary existing worker directory substituted for `/run/company-portal` |
| Live Gunicorn HTTP test under an unprivileged account | NOT RUN | Workspace cannot assign files to the test UID and parent directories restrict access; no server was started as root |
| `systemd-analyze verify` | NOT VERIFIED | Sandbox tool failed before unit validation: `Failed to setup working directory: No such file or directory` |
| `nginx -t` | NOT RUN | Nginx not installed in the build workspace |
| Real NFS mount, ownership and storage01 persistence | NOT RUN | Requires your VMs |
| Real service startup, crash recovery, reboot persistence | NOT RUN | Requires web01/systemd and existing persistent mount |
| Real NFS outage/network disconnection | NOT RUN | Requires planned VM outage test |

Final local versions: Python 3.12; Flask 3.1.3; Werkzeug 3.1.9; Gunicorn 23.0.0.
Dependencies were installed into a separate build-only directory. They and
test logs are not bundled in the deliverable.

The automated tests cover homepage/listing, upload/download/delete content,
delete confirmation, duplicate protection, invalid names and traversal,
CSRF rejection and session separation, supported extensions and spaces,
empty files, missing/multiple files, upload-size rejection, a 700 KB upload
without the default local tempfile spool, staging cleanup, symlinks, special
files, missing storage, non-NFS rejection and mount identity mismatch,
directory symlink rejection, readiness write/read/delete, simulated write
permission/disk-full/publish failures, and browser security headers/cookies.

These tests do not establish real NFS hard-link/durability behavior, resource
usage, Nginx streaming, service hardening compatibility or boot behavior.
Run TESTING.md on your homelab to verify those integrations.
