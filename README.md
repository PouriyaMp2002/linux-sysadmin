# Linux System Administration

**A multi-server Linux infrastructure focused on system administration, storage management, application hosting, backup automation, monitoring, and centralized logging.**

This project simulates a small enterprise IT environment using **Ubuntu Server 24.04, Debian 13, and Oracle VirtualBox**.

The goal was to design, deploy, and operate an interconnected Linux infrastructure where each server performs a dedicated role, rather than configuring individual services in isolation.

The environment combines RAID 1 storage, LVM, NFS, an internal web application, encrypted backups, centralized logging, and proactive monitoring into a functional system.

## Infrastructure Architecture

The infrastructure consists of four virtual machines connected through a private VirtualBox NAT Network (`10.0.2.0/24`).

```text
                     +-----------+
                     |   web01   |
                     | 10.0.2.11 |
                     |-----------|
                     | Nginx     |
                     | Gunicorn  |
                     | Flask     |
                     +-----------+
                           |
                           | NFS
                           v
                     +-----------+
                     | storage01 |
                     | 10.0.2.12 |
                     |-----------|
                     | RAID 1    |
                     | LVM       |
                     | ext4      |
                     | NFS       |
                     +-----------+
                           |
                           | Restic / SSH / SFTP
                           v
                     +-----------+
                     | backup01  |
                     | 10.0.2.14 |
                     |-----------|
                     | Encrypted |
                     | Backups   |
                     +-----------+


                    OPERATIONS SERVER
                        +-----------+
                        |   ops01   |
                        | 10.0.2.13 |
                        |-----------|
                        | Prometheus|
                        | Grafana   |
                        | Alertmgr  |
                        | rsyslog   |
                        +-----------+
                             ^
                             |
                  Metrics & Centralized Logs
                             |
                  web01 / storage01 / backup01
```

`ops01` also monitors its own metrics. Blackbox Exporter checks the web application's HTTP health endpoint.

### Server Inventory

| Server | Operating System | IP Address | Role |
|---|---|---|---|
| **web01** | Ubuntu Server 24.04 | `10.0.2.11` | Nginx, Gunicorn, Flask application |
| **storage01** | Debian 13 | `10.0.2.12` | RAID 1, LVM, ext4, NFS |
| **ops01** | Ubuntu Server 24.04 | `10.0.2.13` | Prometheus, Grafana, Alertmanager, rsyslog |
| **backup01** | Debian 13 | `10.0.2.14` | Restic encrypted backup repository |
| **client01** | Debian 13 Minimal | `10.0.2.21` | Employee/client simulation |

## Technology Stack

| Area | Technologies |
|---|---|
| **Virtualization** | Oracle VirtualBox |
| **Operating Systems** | Ubuntu Server 24.04, Debian 13 |
| **Networking** | IPv4, SSH, TCP/IP, NFS |
| **Storage** | mdadm RAID 1, LVM2, ext4 |
| **Web Application** | Python, Flask, Gunicorn, Nginx |
| **Backup & Recovery** | Restic, SSH/SFTP, systemd timers |
| **Monitoring** | Prometheus, Node Exporter, Blackbox Exporter |
| **Visualization** | Grafana |
| **Alerting** | Prometheus Alert Rules, Alertmanager |
| **Centralized Logging** | rsyslog |
| **Administration** | systemd, journalctl, Linux permissions, Bash |

## Key Features

### 1. Web Application Hosting

A lightweight internal company document portal is hosted on `web01`.

- **Nginx** acts as the reverse proxy.
- **Gunicorn** serves the Flask application.
- The application runs as a dedicated, non-privileged Linux user.
- **systemd** manages the application service.
- Uploaded documents are stored on an NFS share hosted by `storage01`.

This separates application processing from persistent document storage.

### 2. Centralized Storage — RAID 1, LVM & NFS

The storage server provides a dedicated shared filesystem.

```text
Two Virtual Disks
       |
   mdadm RAID 1
       |
      LVM
       |
     ext4
       |
   NFS Export
       |
     web01
```

- **RAID 1:** Disk mirroring for redundancy against a single member-disk failure.
- **LVM:** Logical volume management and storage flexibility.
- **ext4:** Linux filesystem for document storage.
- **NFS:** Remote filesystem access between the storage and web servers.
- **Linux permissions:** Consistent UID/GID ownership and `root_squash` for restricted NFS access.

### 3. Automated Encrypted Backups

A separate Debian server, `backup01`, stores backups of the documents hosted on `storage01`.

- Encrypted backups using **Restic**.
- Secure transfer over **SSH/SFTP** with key-based authentication.
- Dedicated backup user and storage volume.
- Automated daily backups using **systemd timers**.
- Weekly retention and repository maintenance.

RAID provides disk redundancy, while Restic provides recoverable historical copies of data.

### 4. Infrastructure Monitoring & Alerting

The operations server provides visibility into the infrastructure.

**Prometheus + Node Exporter**

Collects Linux system metrics, including CPU, RAM, disk usage, network activity, and uptime.

**Grafana**

Displays infrastructure dashboards to visualize system performance and resource utilization.

**Blackbox Exporter**

Checks whether the internal document portal responds successfully over HTTP.

**Alertmanager**

Receives and manages alerts generated by Prometheus.

Configured alert categories include:

- Server downtime
- High CPU utilization
- High memory utilization
- Low disk space
- Company portal unavailability
- RAID degradation

### 5. Centralized Logging

The infrastructure uses **rsyslog** to forward system and service logs to `ops01` over TCP.

Collected log categories include:

- Linux system events
- Nginx access and error logs
- Application logs
- NFS-related events
- Backup events
- Authentication logs

Logs are organized by source server and service to simplify investigation and troubleshooting.

## Documentation

Detailed implementation procedures, configuration explanations, verification commands, and troubleshooting guidance are separated into dedicated documentation files.

| Topic | Documentation |
|---|---|
| Infrastructure design and server roles | [Architecture](docs/01-architecture.md) |
| VirtualBox networking and SSH | [Networking](docs/02-networking.md) |
| mdadm RAID 1, LVM, and ext4 | [Storage Management](docs/03-storage-raid-lvm.md) |
| NFS server, client, and permissions | [NFS Configuration](docs/04-nfs.md) |
| Flask, Gunicorn, Nginx, and systemd | [Web Server](docs/05-web-server.md) |
| Restic, SSH/SFTP, backup automation, and recovery | [Backup & Disaster Recovery](docs/06-backup-disaster-recovery.md) |
| rsyslog forwarding and log management | [Centralized Logging](docs/07-centralized-logging.md) |
| Prometheus, Node Exporter, and Blackbox Exporter | [Prometheus Monitoring](docs/08-prometheus.md) |
| Dashboards, metrics, and PromQL | [Grafana](docs/09-grafana.md) |
| Infrastructure alerts and Alertmanager | [Alerting](docs/10-alertmanager.md) |
| Permissions, SSH, and security practices | [Security](docs/11-security.md) |
| Diagnostics and common infrastructure issues | [Troubleshooting](docs/12-troubleshooting.md) |

> Documentation links will become active as the corresponding Markdown files are added to the repository.


## Operational Workflow

The following sequence summarizes how the infrastructure works:

1. An employee accesses the document portal hosted on `web01`.
2. Nginx forwards requests to the Flask application through Gunicorn.
3. The application reads and writes documents through the NFS mount provided by `storage01`.
4. `storage01` stores documents on an ext4 filesystem backed by LVM and RAID 1.
5. Restic creates encrypted backups and transfers them to `backup01` using SSH/SFTP.
6. Prometheus collects metrics from the Linux servers and checks application availability.
7. Grafana displays infrastructure health and performance.
8. Prometheus evaluates alert rules and forwards firing alerts to Alertmanager.
9. rsyslog collects centralized logs on `ops01` to support troubleshooting.

This design demonstrates how multiple Linux services interact to provide a manageable infrastructure.

## Verification & Testing

The infrastructure has been configured and verified through operational checks, including:

- Network connectivity between Linux virtual machines.
- RAID 1 and LVM status inspection.
- NFS mounts and shared file operations.
- Access to the document portal through Nginx.
- Application file uploads to NFS-backed storage.
- Execution of encrypted Restic backup jobs.
- systemd timer scheduling.
- Centralized rsyslog message routing.
- Prometheus target and metrics collection.
- Grafana dashboard visualization.
- Prometheus alert configuration validation.

Backup restoration and external notification delivery should be documented as independently verified results once tested.

## Skills Demonstrated

This project provided practical experience in:

- Linux system administration and troubleshooting.
- Multi-server infrastructure design.
- Linux networking and SSH.
- Disk redundancy, filesystems, and logical volume management.
- NFS shared storage and permission management.
- Web application hosting and reverse proxy configuration.
- systemd service management and task automation.
- Encrypted backups and recovery planning.
- Centralized infrastructure monitoring.
- Alert configuration and operational visibility.
- Centralized log management.
- Bash scripting and command-line diagnostics.


## Project Purpose

This project was developed as part of my practical learning in **Linux System Administration, Infrastructure Engineering, and DevOps**.

Its primary objective is to connect theoretical Linux knowledge with real infrastructure tasks: configuring storage, managing services, controlling permissions, automating backups, monitoring systems, and troubleshooting interactions between servers.

The focus is not only on making services run, but also on understanding how to operate, maintain, and recover them.

---

**Project:** Linux System Administration 
**Repository:** `linux-sysadmin`  
**Environment:** Oracle VirtualBox · Ubuntu Server 24.04 · Debian 13  
**Focus:** Linux System Administration · Infrastructure Operations · Disaster Recovery