# Web Server & Internal Company Portal

[← Back to Main README](../README.md)

## Overview

The `web01` server hosts a lightweight internal company document management portal, designed to simulate a practical application workload in a small enterprise Linux environment.

The application is built with **Python Flask**, served through **Gunicorn**, and exposed using **Nginx as a reverse proxy**.

Unlike a traditional standalone web application, the portal stores its documents on a separate Linux storage server using NFS. This allows the project to demonstrate how application hosting, shared storage, system services, filesystem permissions, and infrastructure monitoring work together.

The primary objective is not complex application development, but the administration and operation of the underlying Linux infrastructure.

## Server Information

| Property | Value |
|---|---|
| Hostname | `web01` |
| Operating System | Ubuntu Server 24.04 |
| IP Address | `10.0.2.11` |
| Web Server | Nginx |
| Application Server | Gunicorn |
| Framework | Python Flask |
| Service Manager | systemd |
| Application User | `companyportal` |
| UID/GID | `2500:2500` |
| Shared Storage | NFS from `storage01` |

## Application Architecture

```text
             Client / Employee
                     |
                  HTTP :80
                     |
                     v
                +---------+
                |  Nginx  |
                +---------+
                     |
                Reverse Proxy
                     |
                     v
             +----------------+
             |    Gunicorn    |
             | 127.0.0.1:8000 |
             +----------------+
                     |
                     v
             +----------------+
             |  Flask Portal  |
             +----------------+
                     |
              File Operations
                     |
                     v
          /mnt/company-documents
                     |
                    NFS
                     |
                     v
                storage01
                     |
              RAID 1 + LVM
                     |
                   ext4
```

### Request Flow

1. An employee accesses the portal through the internal network.
2. Nginx receives the HTTP request on port 80.
3. Nginx forwards the request to Gunicorn on the local loopback interface.
4. Gunicorn executes the Flask application.
5. The portal processes the requested document operation.
6. Uploaded documents are written to the NFS filesystem hosted by `storage01`.
7. The application returns the response through Nginx to the client.

This architecture separates HTTP handling, application processing, and persistent document storage.

## Technology Selection

### Nginx — Reverse Proxy

Nginx provides the HTTP entry point for the application.

Its responsibilities include:

- Accepting incoming HTTP requests.
- Forwarding requests to the Gunicorn backend.
- Managing HTTP access and error logs.
- Controlling request and upload size limits.
- Separating the externally accessible endpoint from the internal application process.

The Gunicorn listener is restricted to `127.0.0.1:8000`, avoiding unnecessary direct exposure of the Python application server.

### Gunicorn — WSGI Application Server

Gunicorn runs the Flask application as a managed server process.

It provides the application execution layer between Nginx and Flask.

Running the portal through Gunicorn instead of Flask's development server provides an appropriate deployment model for this infrastructure lab.

### Flask — Internal Document Portal

Flask provides the application functionality used to test the infrastructure.

The portal acts as a realistic workload for:

- HTTP request processing.
- Document upload and retrieval.
- Remote filesystem operations.
- Application service monitoring.
- Access and error logging.
- Backup and recovery operations involving application documents.

The application is intentionally lightweight to keep the project focused on Linux administration.

## Application Directory Structure

| Path | Purpose |
|---|---|
| `/opt/company-portal` | Application source code and Python environment |
| `/etc/company-portal/portal.env` | Application environment configuration |
| `/var/lib/company-portal` | Persistent local application state |
| `/mnt/company-documents` | NFS mount point |
| `/mnt/company-documents/documents` | Shared document storage |
| `/var/log/nginx/company-portal-access.log` | Nginx access logs |
| `/var/log/nginx/company-portal-error.log` | Nginx error logs |

The separation of application code, configuration, state, and documents makes administration and troubleshooting more manageable.

## systemd Service Management

The Flask application is managed through a dedicated systemd service named `company-portal.service`.

This provides:

- Controlled application startup and shutdown.
- Integration with Linux service management.
- Automatic restart behavior when configured.
- Centralized service status inspection.
- Application logs accessible through journald.
- Execution under a dedicated service identity.

Using systemd allows the application to be managed consistently alongside other Linux infrastructure services.

## Service Account & Permissions

The application runs using the dedicated `companyportal` account rather than root.

The account uses numeric UID/GID `2500:2500`, consistent with the document ownership on `storage01`.

This is particularly important for NFS, where file permissions commonly depend on numeric Linux user and group identities.

The application requires access to its own persistent state and the shared document directory, but it does not require unrestricted administrative privileges.

This demonstrates practical Linux permission management and the principle of least privilege.

## Integration with NFS Storage

The application uses NFS to access documents stored on `storage01`.

| Component | Location |
|---|---|
| Storage server | `storage01` — `10.0.2.12` |
| Server-side directory | `/srv/company-data/documents` |
| Client-side directory | `/mnt/company-documents/documents` |
| Underlying storage | mdadm RAID 1 → LVM → ext4 |

This design keeps the document data separate from the web server's operating system disk.

It also creates an infrastructure dependency: if the storage server or NFS mount becomes unavailable, document operations may fail even while Nginx and Gunicorn remain running.

Understanding and monitoring these dependencies is an important part of the project.

## Logging & Monitoring Integration

The web application is integrated with the centralized operations server, `ops01`.

### Centralized Logging

Relevant logs are forwarded through rsyslog, including:

- Nginx HTTP access events.
- Nginx error messages.
- Application-related log events.
- System events.

Centralizing these logs allows administrators to investigate web application problems without relying exclusively on local logs.

### Infrastructure Monitoring

Node Exporter exposes Linux operating system metrics such as CPU, memory, disk, and network activity.

Prometheus collects these metrics, and Grafana presents them in an infrastructure dashboard.

### Application Availability

Blackbox Exporter monitors the portal's HTTP `/health` endpoint.

This allows Prometheus to distinguish between basic server reachability and application HTTP availability.

A successful `/health` response does not necessarily confirm NFS storage readiness. A separate dependency-aware readiness check would improve the monitoring coverage.

## Verification & Testing

The application and infrastructure integration were evaluated through:

- Nginx and application service status checks.
- HTTP access to the portal.
- Document upload and retrieval.
- File visibility on the NFS storage server.
- Application service and Nginx log inspection.
- File ownership and access permission checks.
- Prometheus infrastructure metrics.
- HTTP availability monitoring.

A notable troubleshooting case involved browser-side permissions: an upload could fail because the selected local file was not readable by the desktop user running Firefox, even though the server and NFS storage were functioning correctly.

This demonstrated the importance of investigating the entire request path rather than assuming every upload failure originates on the server.

## Security Considerations

The deployment incorporates several security-related practices:

- Dedicated non-root application account.
- Restrictive filesystem ownership and permissions.
- Gunicorn bound to the local loopback interface.
- NFS access restricted to an authorized client.
- `root_squash` on the NFS export.
- Application secrets stored separately from the source code.
- Centralized operational logging.

The portal is designed for a trusted internal lab network.

A production deployment would additionally require HTTPS, appropriate user authentication and authorization, upload security controls, and further application hardening.

## Design Decisions & Lessons Learned

The most important design decision was to separate application hosting from persistent document storage.

This made it possible to work with Nginx, Gunicorn, Flask, systemd, NFS, RAID, and Linux permissions as interconnected infrastructure components.

The project also highlighted several operational concepts:

- A running service is not necessarily a healthy service.
- Application permissions and NFS filesystem permissions must work together.
- Centralized logging simplifies troubleshooting across multiple systems.
- HTTP health checks and storage readiness are different concerns.
- Application availability depends on networking, storage, and service management.

## Related Documentation

- [Infrastructure Architecture](01-architecture.md)
- [Networking](02-networking.md)
- [NFS Shared Storage](04-nfs.md)
- [Backup & Disaster Recovery](06-backup-disaster-recovery.md)
- [Logging and monitoring](07-Logging-Monitoring-Alerting.md)


## Configuration Files

The actual deployment configurations are maintained separately from this document:

- [Nginx configurations](../configs/nginx/)
- [systemd service configurations](../configs/systemd/)
- [Application source](../app/company-portal/)

These links refer to the intended repository layout and will work when the corresponding files or directories are committed.

---

**Previous:** [← NFS Shared Storage](04-nfs.md)  
**Next:** [Backup & Disaster Recovery →](06-backup-disaster-recovery.md)