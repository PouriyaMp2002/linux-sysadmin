# Backup Automation & Disaster Recovery

[← Back to Main README](../README.md)

## Overview

This project implements an automated, encrypted backup solution to protect documents stored on the primary Linux storage server.

The backup infrastructure uses **Restic, SSH/SFTP, Bash, and systemd timers** to create and maintain backup snapshots on a separate Debian virtual machine.

The system is designed to demonstrate essential Linux administration practices, including backup automation, secure data transfer, storage separation, retention management, and disaster recovery planning.

An important principle of this architecture is that **RAID redundancy and backups solve different problems**.

RAID 1 helps maintain storage availability after a single disk-member failure, while backups provide historical recovery points that can protect against accidental deletion, unwanted changes, and certain forms of data corruption.

## Infrastructure Overview

| Component | Details |
|---|---|
| Backup source server | `storage01` |
| Source operating system | Debian 13 |
| Source IP address | `10.0.2.12` |
| Backup destination server | `backup01` |
| Destination operating system | Debian 13 |
| Destination IP address | `10.0.2.14` |
| Backup software | Restic |
| Data transport | SSH/SFTP |
| Authentication | SSH key pair |
| Encryption | Restic repository encryption |
| Automation | Bash and systemd |
| Backup schedule | Daily at 02:00 |
| Maintenance schedule | Sunday at 04:00 |

## Backup Architecture

```text
                    PRIMARY STORAGE
                       storage01
                      10.0.2.12
                           |
                   mdadm RAID 1
                           |
                          LVM
                           |
                         ext4
                           |
                /srv/company-data
                           |
                        documents/
                           |
                           v
                    Backup Script
                           |
                  Pre-backup Checks
                           |
                           v
                         Restic
                           |
                    Data Encryption
                           |
                      SSH / SFTP
                           |
                           v
                     BACKUP SERVER
                       backup01
                      10.0.2.14
                           |
                  Dedicated Backup Disk
                           |
                       ext4
                           |
                     /srv/backups
                           |
                     Restic Repository
                           |
                   Encrypted Snapshots
```

The backup process is initiated from `storage01`.

Restic reads the source documents, creates an encrypted snapshot, and transfers the backup data to the repository hosted on `backup01`.

The backup server stores the repository without requiring access to the original plaintext documents.

## Backup Storage Design

### Primary Storage — storage01

The primary storage server hosts the company portal's document files.

Its storage stack consists of:

- Two virtual disks configured as mdadm RAID 1.
- An LVM volume group named `app`.
- A logical volume named `docs`.
- An ext4 filesystem.
- An NFS export used by the application server.

The documents are stored under:

`/srv/company-data/documents`

The same files are accessible to the web application through its NFS mount.

This directory serves as the source for Restic backups.

### Backup Destination — backup01

A separate Debian 13 virtual machine serves as the backup destination.

The machine uses a dedicated **20 GB virtual disk** formatted with ext4.

| Directory | Purpose |
|---|---|
| `/srv/backups` | Dedicated backup filesystem mount |
| `/srv/backups/restic` | Encrypted Restic repository |

A dedicated backup filesystem helps separate repository storage from the operating system filesystem.

It also allows backup capacity and filesystem health to be managed independently.

The backup repository is accessed using a dedicated Linux account named `backupsvc`.

## Why Restic?

Restic was selected because it provides several useful features for a small Linux infrastructure.

### Encryption

Restic encrypts repository contents before writing them to the destination.

This protects the confidentiality of stored backup data, provided that the encryption credentials remain secure.

### Incremental Backups

Restic identifies and reuses previously stored data.

After the initial backup, subsequent snapshots generally transfer only new or changed content, reducing redundant storage consumption and network traffic.

### Deduplication

Identical data can be stored efficiently instead of being duplicated unnecessarily across snapshots.

### Snapshot-Based Recovery

Each successful backup creates a snapshot representing a recoverable state of the selected files.

Snapshots allow data to be restored from different points in time, subject to the configured retention policy.

### Repository Verification

Restic provides repository consistency checks that can help detect integrity problems.

These checks complement, but do not replace, actual restore testing.

## Secure Backup Transport

The backup system transfers data from `storage01` to `backup01` using **SSH/SFTP**.

The connection uses a dedicated SSH key rather than interactive password authentication.

### Authentication Architecture

| Component | Value |
|---|---|
| SSH client | `storage01` |
| SSH destination | `backup01` |
| Remote account | `backupsvc` |
| Authentication method | SSH public-key authentication |
| Private key location | `/root/.ssh/restic_backup` |
| SSH host alias | `backup01-restic` |
| Destination protocol | SFTP |

The public key is authorized on the destination account, while the private key remains on the source server.

SSH provides encryption and authenticated communication during transport.

Restic independently encrypts the backup repository contents.

These mechanisms protect different parts of the backup process.

## Backup Automation

Manual backups are prone to being forgotten or performed inconsistently.

To address this, the infrastructure uses custom Bash scripts integrated with systemd services and timers.

### Backup Script

The primary backup script is located at:

`/usr/local/sbin/company-backup.sh`

The script manages the backup execution workflow.

Its main responsibilities include:

- Confirming that the source filesystem is mounted.
- Checking that the expected document directory exists.
- Verifying that the destination backup filesystem is mounted.
- Preventing backup execution when required storage is unavailable.
- Starting the Restic backup operation.
- Reporting execution results through system logging.

These checks are particularly important because the backup destination uses a dedicated mounted filesystem.

Without appropriate safeguards, an unavailable mount could cause backup operations to write into an unintended directory on the destination server's root filesystem.

### systemd Service

The backup operation is managed through:

`company-backup.service`

The service executes the backup script as a systemd oneshot job.

This allows execution status and logs to be inspected using standard Linux service management tools.

### Daily Backup Timer

The scheduled backup is managed by:

`company-backup.timer`

| Property | Value |
|---|---|
| Frequency | Daily |
| Scheduled time | 02:00 |
| Execution type | systemd oneshot service |
| Target service | `company-backup.service` |

The timer enables backups to run automatically without manual intervention.

The schedule follows the configured timezone of `storage01`.

## Backup Retention & Repository Maintenance

Maintaining every backup snapshot indefinitely would eventually consume unnecessary disk space.

The infrastructure therefore separates routine backup execution from repository maintenance.

### Maintenance Script

The maintenance workflow is managed by:

`/usr/local/sbin/company-backup-maintenance.sh`

Its responsibilities include applying the configured retention policy and performing repository maintenance.

### Maintenance Service & Timer

| Component | Name |
|---|---|
| Maintenance service | `company-backup-maintenance.service` |
| Maintenance timer | `company-backup-maintenance.timer` |
| Frequency | Weekly |
| Scheduled time | Sunday at 04:00 |

Restic's retention functionality determines which historical snapshots should remain available.

Repository pruning can then remove data that is no longer referenced by retained snapshots.

The exact retention periods are defined in the maintenance script rather than duplicated in this documentation.

### Why Separate Backup and Maintenance Jobs?

Separating these operations provides several advantages:

- Daily backup execution remains focused on creating recovery points.
- Repository maintenance can be scheduled less frequently.
- Each operation has its own systemd execution history.
- Failures can be investigated independently.
- Retention changes can be managed without changing the daily backup workflow.

Repository maintenance must be coordinated with normal backup execution to avoid unnecessary conflicts.

## Backup Workflow

The complete automated backup process follows these stages:

1. **Timer activation:** systemd starts the backup service at the scheduled time.
2. **Source verification:** The backup script confirms that the primary storage filesystem is mounted.
3. **Destination verification:** The script checks access to the dedicated backup filesystem on `backup01`.
4. **Repository access:** Restic connects to the encrypted repository over SSH/SFTP.
5. **Data processing:** Restic identifies the source files and creates the backup snapshot.
6. **Encrypted transfer:** Backup data is transferred securely to the destination.
7. **Completion logging:** The service records the execution result for later inspection.
8. **Repository maintenance:** A separate weekly job manages snapshot retention and pruning.

This workflow demonstrates how Linux storage, networking, secure authentication, backup software, and systemd automation operate together.

## Backup Verification

A successful backup command alone is not sufficient to establish a reliable disaster recovery system.

The backup infrastructure should be checked at several levels.

### Service Execution

The daily systemd service provides execution status and journal entries.

These records help identify failed backup attempts, connectivity problems, or unavailable storage.

### Backup Snapshots

Restic maintains metadata describing available recovery snapshots.

Snapshot inspection confirms that the repository contains backup records for the expected source paths.

### Repository Integrity

Restic supports repository consistency verification.

This can help identify repository problems before an actual recovery operation becomes necessary.

### Destination Storage

The dedicated backup filesystem must remain available and have sufficient free capacity.

The repository should not silently fall back to the backup VM's operating system disk.

### Recovery Testing

Restoring selected files into a separate test directory provides stronger evidence that the backed-up content is usable.

A restore test should be considered a distinct operational verification, not an automatic consequence of successfully creating a snapshot.

## Disaster Recovery Strategy

The recovery strategy focuses on restoring document data if files become unavailable or damaged on the primary storage server.

### Recovery Scenarios

| Scenario | Recovery approach |
|---|---|
| Accidental document deletion | Restore the required file from a suitable snapshot |
| Unwanted file modification | Restore an earlier known-good version |
| Document corruption | Recover data from a verified snapshot |
| Primary filesystem loss | Rebuild the filesystem and restore the backed-up documents |
| Primary storage VM failure | Recreate the required storage environment and recover data from the repository |
| Single RAID member failure | Repair the RAID array; a backup restore is not necessarily required |

The correct recovery procedure depends on the failure and the health of the remaining infrastructure.

### Recovery Process

A typical recovery workflow consists of:

1. Identify the affected files or filesystem.
2. Determine the appropriate recovery snapshot.
3. Verify access to the Restic repository and its encryption credentials.
4. Restore data into an isolated directory.
5. Verify file contents and integrity.
6. Confirm the expected ownership and permissions.
7. Return verified data to the appropriate application storage location.
8. Validate document access through the web portal.

Restoring into a separate directory first reduces the risk of overwriting working data unintentionally.

### Recovery Validation

A documented recovery test should record:

- The backup snapshot selected.
- The recovered data.
- The destination used for restoration.
- Whether file integrity checks passed.
- Whether expected Linux ownership and permissions were preserved or restored.
- Whether the application could use the recovered files.
- The time required to complete recovery, if measured.

The project distinguishes between **configured recovery capability** and **completed recovery testing**.

## Backup Security

The infrastructure uses several controls to protect backup data.

### Dedicated Service Account

The backup repository is accessed through the `backupsvc` user instead of unrestricted root access on the destination machine.

### SSH Key-Based Authentication

A dedicated key pair is used for backup transport, avoiding interactive password authentication in the automated workflow.

### Restic Encryption

Backup data is encrypted before being stored in the remote repository.

The encryption password is kept separately from the repository data.

### Restricted Filesystem Access

Repository directories and sensitive credential files use restricted Linux ownership and permissions.

### Storage Separation

Backup data is written to a separate VM and dedicated virtual disk.

This reduces dependence on the primary storage VM, although it does not provide physical independence.

### Security Limitations

A backup destination account with write and delete permissions may still be able to alter or remove repository data if compromised.

Stronger protection against destructive attacks would require additional controls, such as append-only repository access, immutable copies, or separately managed offsite backups.

### Shared Physical Host

Both `storage01` and `backup01` run on the same VirtualBox host.

A physical disk failure affecting the host, theft, hardware damage, or loss of the entire machine could affect both the original documents and their backups.

### Limited Backup Capacity

The destination repository uses a 20 GB virtual disk.

Retention settings and backup growth must therefore be managed according to available capacity.

### Document-Focused Scope

The backup workflow focuses on the shared document directory.

It is not a complete bare-metal backup of all virtual machines, operating system configurations, application dependencies, or locally stored application state.

Rebuilding the full environment may require separate system configuration backups and redeployment instructions.

### Recovery Objectives

Formal Recovery Point Objective (RPO) and Recovery Time Objective (RTO) guarantees have not been established.

The daily schedule provides a nominal backup interval, but the recoverable point in time depends on the latest successful and usable snapshot.

Actual recovery duration must be measured through testing.

**RAID is not a backup.** Disk mirroring can maintain availability after certain hardware failures, but it does not create historical recovery points.

**Backups need automation.** systemd timers provide predictable scheduling and standard service-level logging.

**Mount verification matters.** Backup scripts should verify storage availability to avoid writing data into unintended locations.

**Encryption and transport security serve different purposes.** SSH protects data during transfer, while Restic encrypts repository contents.

**Retention is part of backup engineering.** Backup growth must be controlled without unnecessarily eliminating useful recovery points.

**Recovery must be tested.** Successfully creating snapshots does not guarantee that applications or filesystems can be restored within an acceptable time.

## Configuration & Automation Files

The actual implementation is maintained separately from this documentation.

| Component | Repository location |
|---|---|
| Daily backup script | `scripts/company-backup.sh` |
| Retention and maintenance script | `scripts/company-backup-maintenance.sh` |
| Backup systemd service | `configs/systemd/company-backup.service` |
| Daily backup timer | `configs/systemd/company-backup.timer` |
| Maintenance service | `configs/systemd/company-backup-maintenance.service` |
| Maintenance timer | `configs/systemd/company-backup-maintenance.timer` |

These paths represent the intended repository organization. Configuration files and scripts should be sanitized before publication.

Sensitive files such as SSH private keys and Restic repository passwords must never be committed.

## Related Documentation

- [Infrastructure Architecture](01-architecture.md)
- [Storage — RAID 1, LVM & ext4](03-storage-raid-lvm.md)
- [NFS Shared Storage](04-nfs.md)
- [Web Server & Internal Company Portal](05-web-server.md)
- [Logging and monitoring](07-Logging-Monitoring-Alerting.md)
- [Troubleshooting](08-Troubleshooting.md)

---

**Previous:** [← Web Server](05-web-server.md)  
**Next:** [Logging and monitoring →](07-Logging-Monitoring-Alerting.md)
