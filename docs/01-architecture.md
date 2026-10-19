# Infrastructure Architecture

[← Back to Main README](../README.md)

## 1. Overview

This project implements a multi-server Linux infrastructure designed to simulate the operation of a small enterprise IT environment.

The infrastructure is deployed on **Oracle VirtualBox**, using **Ubuntu Server 24.04** and **Debian 13**.

Five virtual machines are assigned separate responsibilities for application hosting, storage management, backup and disaster recovery, monitoring and logging, and client access.

The main architectural objective is to build an interconnected environment in which different Linux services depend on and communicate with each other, rather than operating as isolated demonstrations.

![Image Descritpion](architecture.png)

## 2. Infrastructure Inventory

| Hostname | Operating System | IP Address | Primary Role |
|---|---|---|---|
| `web01` | Ubuntu Server 24.04 | `10.0.2.11` | Application hosting and reverse proxy |
| `storage01` | Debian 13 | `10.0.2.12` | RAID 1, LVM, ext4, NFS |
| `ops01` | Ubuntu Server 24.04 | `10.0.2.13` | Monitoring, alerting, centralized logging |
| `backup01` | Debian 13 | `10.0.2.14` | Encrypted Restic backup repository |

All machines share a VirtualBox NAT Network in the `10.0.2.0/24` subnet.

Default gateway: `10.0.2.1`

The environment is hosted on a computer with 16 GB of physical RAM, so the virtual machines are designed to operate with relatively modest resource allocations.

## 3. Logical Architecture

```text
                  VirtualBox NAT Network
                       10.0.2.0/24
                             |
                       +----------+
                       |  web01   |
                       |  .11     |
                       |----------|
                       | Nginx    |
                       | Gunicorn |
                       | Flask    |
                       +----------+
                             |
                         NFS Storage
                             |
                             v
                       +----------+
                       |storage01 |
                       |  .12     |
                       |----------|
                       | RAID 1   |
                       | LVM      |
                       | ext4     |
                       | NFS      |
                       +----------+
                             |
                        Restic / SFTP
                             |
                             v
                       +----------+
                       | backup01 |
                       |  .14     |
                       |----------|
                       | Encrypted|
                       | Backups  |
                       +----------+


                      +-------------+
                      |    ops01    |
                      |     .13     |
                      |-------------|
                      | Prometheus  |
                      | Grafana     |
                      | Alertmanager|
                      | Blackbox    |
                      | rsyslog     |
                      +-------------+
                             ^
                             |
                    Metrics and Log Data
                             |
              web01 / storage01 / backup01
```

`ops01` also monitors its own operating system using Node Exporter.

The operations server monitors the company portal over HTTP using Blackbox Exporter.

## 4. Server Roles and Responsibilities

### 4.1 web01 — Application Server

**OS:** Ubuntu Server 24.04  
**IP:** `10.0.2.11`

The application server hosts an internal company document portal.

The application stack consists of:

- Nginx as the HTTP reverse proxy.
- Gunicorn as the WSGI application server.
- Python Flask as the application framework.
- systemd to manage application execution.
- NFS client functionality to access remote documents.

Application processing and persistent document storage are separated.

The Flask application runs under a dedicated non-privileged account named `companyportal`, with UID/GID `2500`.

Relevant paths:

```text
/opt/company-portal
/etc/company-portal/portal.env
/var/lib/company-portal
/mnt/company-documents
```

The web application listens internally through Gunicorn on `127.0.0.1:8000`, while Nginx accepts incoming HTTP requests on port `80`.

### 4.2 storage01 — Storage Server

**OS:** Debian 13  
**IP:** `10.0.2.12`

The storage server provides persistent shared storage for application documents.

Storage layers:

```text
Physical Disks
      |
      v
  mdadm RAID 1
      |
      v
   /dev/md0
      |
      v
 LVM Physical Volume
      |
      v
 Volume Group: app
      |
      v
 Logical Volume: docs
      |
      v
 ext4 Filesystem
      |
      v
 /srv/company-data
      |
      v
    NFS
      |
      v
   web01
```

Two 10 GB virtual disks provide the RAID 1 members.

The LVM logical volume is approximately 7 GiB.

The document directory is located at:

```text
/srv/company-data/documents
```

Storage is exported over NFS with client restrictions and `root_squash`.

### 4.3 backup01 — Backup Server

**OS:** Debian 13  
**IP:** `10.0.2.14`

The backup server receives encrypted backup data from `storage01`.

The repository is stored on a dedicated ext4 filesystem mounted at:

```text
/srv/backups
```

Repository path:

```text
/srv/backups/restic
```

Backup transport uses SSH/SFTP and a dedicated user named `backupsvc`.

Restic encrypts backup contents before transmitting them to the backup server.

Backup scheduling:

- Daily backup: 02:00.
- Weekly retention and maintenance: Sunday at 04:00.

The backup server is logically independent of the primary storage VM, but it remains on the same virtualization host.

### 4.4 ops01 — Operations Server

**OS:** Ubuntu Server 24.04  
**IP:** `10.0.2.13`

This machine centralizes operational visibility.

Installed services include:

- Prometheus
- Grafana
- Prometheus Node Exporter
- Prometheus Blackbox Exporter
- Alertmanager
- rsyslog

**Monitoring workflow:**

```text
Linux Servers
      |
      v
 Node Exporter
      |
      v
  Prometheus
      |
      +----> Grafana
      |
      +----> Alertmanager
```

**Centralized logging workflow:**

```text
web01 --------+
storage01 ----+---- TCP 514 ----> ops01
backup01 -----+                   rsyslog
```

Monitoring, log collection, and alert management are logically separated from application hosting and storage.


## 5. Service Communication

| Source | Destination | Service | Port / Protocol |
|---|---|---|---|
| `web01` | Document portal | TCP 80 |
| `web01` | `storage01` | NFS shared storage | TCP 2049 (plus any required NFS ancillary services) |
| `storage01` | `backup01` | Encrypted backup transfer | TCP 22 |
| `ops01` | Managed servers | Node Exporter | TCP 9100 |
| `ops01` | `web01` | HTTP availability probe | TCP 80 |
| `web01`, `storage01`, `backup01` | `ops01` | rsyslog forwarding | TCP 514 |

The following services are hosted locally on `ops01`:

| Service | Port |
|---|---|
| Prometheus | TCP 9090 |
| Grafana | TCP 3000 |
| Alertmanager | TCP 9093 |
| Blackbox Exporter | TCP 9115 |

These ports describe the lab's service communication. Administrative interfaces should only be exposed to trusted machines.

## 6. Application and Data Flow

When a user accesses the company document portal:

1. The client sends an HTTP request to `web01`.
2. Nginx receives the request.
3. Nginx forwards the request to Gunicorn.
4. Gunicorn executes the Flask application.
5. The application accesses documents through the NFS mount.
6. `storage01` stores the files on the RAID-backed ext4 filesystem.

Backup operations follow a separate path:

1. A systemd timer starts the backup service on `storage01`.
2. The backup script checks the required storage conditions.
3. Restic reads the source documents.
4. Restic encrypts and transfers backup data via SSH/SFTP.
5. `backup01` stores the encrypted repository.

Monitoring runs independently:

1. Node Exporter exposes Linux metrics.
2. Prometheus scrapes metrics at configured intervals.
3. Grafana visualizes the collected data.
4. Prometheus evaluates alert rules.
5. Alertmanager receives firing and resolved alerts.

## 7. Architecture Design Decisions

### Separation of Responsibilities

Each major responsibility has its own virtual machine.

This makes service dependencies easier to understand and prevents application, backup, storage, and monitoring configurations from being unnecessarily mixed together.

### Shared Storage

The application server does not store uploaded documents solely on its own system disk.

NFS provides centralized storage that can be independently administered and backed up.

### RAID and Backups

RAID 1 provides redundancy against a member disk failure.

Restic provides encrypted backup snapshots for data recovery.

Both mechanisms serve different purposes and are used together.

### Dedicated Operations Server

Monitoring and centralized logging run on `ops01`, rather than on the application server.

This allows operational data to be collected from multiple infrastructure machines in one location.

## 8. Architecture Verification

On each Linux server, confirm the hostname:

```bash
hostnamectl
```

Inspect network addresses:

```bash
ip -br addr
```

Inspect routing:

```bash
ip route
```

From `web01`, test storage connectivity:

```bash
ping -c 3 10.0.2.12
```

Verify the NFS mount:

```bash
findmnt /mnt/company-documents
```

Verify the portal:

```bash
curl -I http://10.0.2.11
```

On `ops01`, verify monitoring services:

```bash
systemctl is-active prometheus
systemctl is-active prometheus-alertmanager
systemctl is-active grafana-server
systemctl is-active rsyslog
```

A complete infrastructure health check should also confirm backups, RAID condition, NFS access, and monitoring targets.

## 10. Related Documentation

- [Networking](02-networking.md)
- [Storage — RAID 1, LVM & ext4](03-storage-raid-lvm.md)
- [NFS Shared Storage](04-nfs.md)
- [Web Server](05-web-server.md)
- [Backup & Disaster Recovery](06-backup-disaster-recovery.md)
- [Prometheus Monitoring](08-prometheus.md)
- [Centralized Logging](07-centralized-logging.md)

---

**Next:** [Networking Configuration →](02-networking.md)