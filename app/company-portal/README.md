# Company Document Portal

A lightweight internal document management web application built with **Python Flask**, designed as a practical application workload for the [Linux System Administration Homelab](../../README.md).

The portal demonstrates how a Python web application can be deployed and managed within a multi-server Linux infrastructure using **Gunicorn, Nginx, systemd, and NFS**.

## Overview

The Company Document Portal simulates a basic internal company service for managing shared documents.

Rather than being developed as a large production application, it was intentionally kept lightweight to support infrastructure administration, monitoring, centralized logging, backup automation, and disaster recovery exercises.

Its primary purpose is to provide a functional application that interacts with the underlying Linux infrastructure.

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, Flask |
| WSGI Server | Gunicorn |
| Reverse Proxy | Nginx |
| Service Management | systemd |
| Document Storage | NFS |
| Operating System | Ubuntu Server 24.04 |
| Monitoring | Prometheus, Blackbox Exporter |
| Logging | journald, Nginx, rsyslog |
| Backup | Restic |

## Application Architecture

```text
                   Client / Browser
                          |
                       HTTP :80
                          |
                          v
                    +-----------+
                    |   Nginx   |
                    +-----------+
                          |
                     Reverse Proxy
                          |
                          v
                    +-----------+
                    | Gunicorn  |
                    | Port 8000 |
                    +-----------+
                          |
                          v
                    +-----------+
                    |   Flask   |
                    |  Portal   |
                    +-----------+
                          |
                    Document Storage
                          |
                          v
                 NFS Mounted Directory
                          |
                          v
                      storage01
                          |
                    RAID 1 + LVM
                          |
                         ext4
```

The application runs on `web01`, while uploaded documents are stored on a dedicated storage server.

## Features

The portal provides a lightweight interface for working with internal company documents.

Its infrastructure-related capabilities include:

- Web-based access to shared document storage.
- Document upload and retrieval.
- Integration with a remotely mounted NFS directory.
- Persistent application data storage.
- HTTP health endpoint for availability monitoring.
- Execution as a managed systemd service.
- Integration with centralized logging and backup services.

The exact available document-management actions depend on the application version included in this repository.

## Application Environment

| Property | Value |
|---|---|
| Application Host | `web01` |
| Operating System | Ubuntu Server 24.04 |
| Server Address | `10.0.2.11` |
| Application Directory | `/opt/company-portal` |
| Application Service | `company-portal.service` |
| Gunicorn Address | `127.0.0.1:8000` |
| Nginx HTTP Port | `80` |
| Environment File | `/etc/company-portal/portal.env` |
| Persistent Application Data | `/var/lib/company-portal` |
| Document Storage | `/mnt/company-documents/documents` |

These paths represent the deployment within the homelab. A local development environment may use different paths and storage settings.

## Deployment Overview

The application is deployed through the following components:

**Flask** handles application requests and document-management operations.

**Gunicorn** serves the Flask application using the WSGI interface.

**Nginx** acts as the HTTP reverse proxy and forwards requests to Gunicorn on the local loopback interface.

**systemd** manages the application process, including startup, restart behavior, and service logging.

**NFS** provides access to documents stored on `storage01`, keeping shared files separate from the web server's local application code.

Detailed server configurations are available in the main infrastructure repository:

- [Web Server Documentation](../../docs/05-web-server.md)
- [NFS Documentation](../../docs/04-nfs.md)
- [Nginx Configuration](../../configs/nginx/)
- [systemd Configuration](../../configs/systemd/)

## Python Dependencies

Application dependencies should be installed using a Python virtual environment.

The project's `requirements.txt` file defines the Python packages required by the application.

Flask provides the application framework, while Gunicorn is used to serve the application in the Linux deployment.

Other dependencies should be documented directly in the dependency file rather than installed globally.

## Application Configuration

The application uses an external environment file to keep deployment settings separate from application code.

In the homelab, this file is located at:

`/etc/company-portal/portal.env`

A persistent `PORTAL_SECRET_KEY` is used for Flask session and security-related functionality.

Actual secret values are not included in this repository.

A local or new deployment should generate its own cryptographically random secret key and configure the environment according to the application requirements.

## Document Storage

In the infrastructure deployment, documents are stored at:

`/mnt/company-documents/documents`

This location is mounted from the storage server:

`storage01:/srv/company-data`

The underlying storage infrastructure uses:

- mdadm RAID 1 for disk mirroring.
- LVM for logical volume management.
- ext4 for persistent file storage.
- NFS for remote document access.

The application uses a dedicated non-privileged Linux service account named `companyportal`, with UID/GID `2500:2500`.

Consistent file ownership between the NFS client and server is important for successful document operations.

### Storage Dependency

The application depends on the availability of the NFS mount for its document operations.

If the storage server becomes unavailable, the Flask process may remain operational while document access fails.

This distinction is important for application readiness monitoring and troubleshooting.

## Health Monitoring

The application exposes an HTTP health endpoint:

`/health`

Prometheus Blackbox Exporter checks this endpoint from the operations server.

The monitoring system can detect when the portal stops responding successfully to HTTP requests.

Application availability is monitored separately from basic server-level metrics such as CPU, memory, and disk usage.

The HTTP health endpoint does not necessarily verify every backend dependency, including NFS accessibility.

## Logging

The application is integrated with Linux service logging and centralized rsyslog collection.

Relevant log sources include:

- Application process logs managed through systemd/journald.
- Nginx HTTP access logs.
- Nginx error logs.
- Application-related operational messages.

The centralized logging receiver on `ops01` organizes relevant events by host and service.

This supports troubleshooting across the web and storage servers.

## Backup & Disaster Recovery

Documents uploaded through the portal are stored on the shared NFS filesystem.

The storage server runs an automated Restic backup process that creates encrypted snapshots and transfers them to `backup01` using SSH/SFTP.

The backup infrastructure includes daily backup scheduling and weekly repository maintenance.

This protects the shared document dataset independently of the web application's process.

Application-local state, configuration, and secret recovery require separate consideration and are not automatically covered by the document backup job.

See [Backup & Disaster Recovery](../../docs/06-backup-disaster-recovery.md).

## Security Considerations

The homelab deployment incorporates several infrastructure-level controls:

- Dedicated non-root application account.
- Restricted application and document directory permissions.
- Gunicorn bound to the local loopback interface.
- Nginx as the single HTTP entry point.
- NFS access restricted to the authorized web server.
- External storage of application secrets.
- Centralized operational logging.

This application is intended for a private infrastructure lab.

It should not be treated as production-ready without further review of authentication, authorization, file upload security, HTTPS, dependency vulnerabilities, and application error handling.

## Testing & Verification

The application can be evaluated through several functional and infrastructure checks:

| Test | Expected Result |
|---|---|
| Portal availability | Application responds over HTTP |
| Application health | `/health` returns a successful response |
| Document upload | File is stored in the configured document directory |
| Document retrieval | Stored file can be accessed through the portal |
| NFS integration | Uploaded documents are visible on `storage01` |
| Filesystem permissions | Application account can access authorized documents |
| Service management | systemd manages the Gunicorn process |
| Logging | Relevant requests and errors appear in the appropriate logs |
| Monitoring | Blackbox Exporter collects HTTP availability information |
| Backups | Shared document data is included in the storage server's backup scope |

## Known Limitations

The Company Document Portal is intended as an internal infrastructure test application.

It does not attempt to provide a full enterprise document management platform.

Limitations include:

- Dependence on a single application VM.
- Dependence on a single NFS server.
- HTTP-only access within the lab.
- Basic availability monitoring rather than full dependency-aware readiness testing.
- No demonstrated high-availability application deployment.
- Document backups do not automatically cover all application-local state.

## Related Documentation

- [Main Infrastructure README](../../README.md)
- [Infrastructure Architecture](../../docs/01-architecture.md)
- [Networking](../../docs/02-networking.md)
- [Storage Management](../../docs/03-storage-raid-lvm.md)
- [NFS Shared Storage](../../docs/04-nfs.md)
- [Web Server](../../docs/05-web-server.md)
- [Backup & Disaster Recovery](../../docs/06-backup-disaster-recovery.md)
- [Centralized Logging, Monitoring & Alerting](../../docs/07-centralized-logging.md)

---
