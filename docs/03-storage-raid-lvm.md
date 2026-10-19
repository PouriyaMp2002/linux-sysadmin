# Storage Management — RAID 1, LVM & ext4

[← Back to Main README](../README.md)

## 1. Overview

The storage infrastructure is deployed on `storage01`, running Debian 13.

Its purpose is to provide dedicated, persistent storage for the internal document management application hosted on `web01`.

The configuration combines three storage technologies:

- **mdadm RAID 1:** Disk-level mirroring.
- **LVM:** Logical volume management.
- **ext4:** Linux filesystem for persistent document data.

The resulting filesystem is made available to the application server through NFS.

This separation allows storage administration, filesystem management, and backup operations to be handled independently from the web application.

## 2. Storage Server Information

| Parameter | Value |
|---|---|
| Hostname | `storage01` |
| Operating System | Debian 13 |
| IP Address | `10.0.2.12` |
| RAID technology | Linux mdadm |
| RAID level | RAID 1 |
| RAID device | `/dev/md0` |
| RAID member disks | Two 10 GB virtual disks |
| LVM physical volume | `/dev/md0` |
| Volume group | `app` |
| Logical volume | `docs` |
| Logical volume size | 7 GiB |
| Filesystem | ext4 |
| Mount point | `/srv/company-data` |
| Shared documents | `/srv/company-data/documents` |

## 3. Storage Architecture

```text
             storage01
           Debian 13 Linux
                  |
       +----------+----------+
       |                     |
   Virtual Disk 1        Virtual Disk 2
       |                     |
    Partition              Partition
       |                     |
       +----------+----------+
                  |
             mdadm RAID 1
                  |
               /dev/md0
                  |
           LVM Physical Volume
                  |
            Volume Group: app
                  |
          Logical Volume: docs
                  |
                ext4
                  |
          /srv/company-data
                  |
         /documents Directory
                  |
             NFS Export
                  |
                  v
                web01
```

RAID 1, LVM, and ext4 operate at different layers of the storage stack.

Each layer provides a separate capability.

## 4. Why RAID 1?

RAID 1 mirrors the same data across multiple disk members.

In this project, two virtual disks are used as a mirrored pair.

### Benefits

- Can tolerate a single disk-member failure.
- Allows the array to continue operating in a degraded state while a healthy member remains.
- Can support rebuilding after replacing a failed member.
- Provides a practical environment for learning Linux software RAID administration.

## 5. Install Storage Management Tools

On `storage01`:

```bash
sudo apt update
sudo apt install -y mdadm lvm2
```

Verify the tools:

```bash
mdadm --version
sudo pvs
```

## 6. Identify the Storage Disks

List all block devices:

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
```

Inspect individual disks:

```bash
sudo fdisk -l
```

Identify the two dedicated 10 GB disks.

During the original lab setup, the RAID member partitions were associated with:

```text
/dev/sdb1
/dev/sdd1
```

**Important:** Linux device names can change between installations or reboots. Always identify the correct disks by size, identity, and existing filesystem information before running partitioning or RAID creation commands.

Never run destructive storage commands against the operating system disk.

## 7. Partition the RAID Disks

This section illustrates the original storage layout and the procedure for reproducing it on new, empty virtual disks.

**Warning:** The partitioning and RAID creation commands below can permanently overwrite data. Do not execute them when you have data on your disk. 

Example using `fdisk`:

```
sudo fdisk /dev/sdb ==> create GPT partition ==> Create new partition
==> Change its type to Linux RAID (43) ==> See preview ==> Write 
Do this with /dev/sdd too
```

This example assumes `/dev/sdb` and `/dev/sdd` are the two correct, empty data disks.

Verify:

```bash
lsblk -f
```

The new RAID partitions should appear as:

```text
/dev/sdb1
/dev/sdd1
```

## 8. Create the RAID 1 Array

For a new deployment only:

```bash
sudo mdadm --create /dev/md0 \
  --level=1 \
  --raid-devices=2 \
  /dev/sdb1 /dev/sdd1
```

The command creates a two-member software RAID 1 array.

Inspect synchronization:

```bash
cat /proc/mdstat
```

Example healthy output:

```text
md0 : active raid1 sdd1[1] sdb1[0]
      10475520 blocks super 1.2 [2/2] [UU]
```

`[UU]` means that both expected RAID members are active.

During synchronization or rebuilding, `/proc/mdstat` may show progress information.

### Inspect the Array

```bash
sudo mdadm --detail /dev/md0
```

Review:

- RAID level.
- Number of RAID devices.
- Active member count.
- Array state.
- Rebuild or synchronization status.
- Member device information.

### Persist the RAID Configuration

On Debian:

```bash
sudo mdadm --detail --scan
```

For a newly created array, add the appropriate ARRAY definition to `/etc/mdadm/mdadm.conf`.

Avoid appending duplicate definitions when rebuilding or reconfiguring the array.

Then update the initramfs if required:

```bash
sudo update-initramfs -u
```

This helps the operating system assemble the array consistently after reboot.

## 9. Configure LVM

LVM introduces a flexible logical storage layer above the RAID device.

### Storage Layout

```text
/dev/md0
    |
    v
Physical Volume
    |
    v
Volume Group: app
    |
    v
Logical Volume: docs
    |
    v
/dev/app/docs
```

### Create the Physical Volume

For a new deployment:

```bash
sudo pvcreate /dev/md0
```

### Create the Volume Group

```bash
sudo vgcreate app /dev/md0
```

### Create the Logical Volume

```bash
sudo lvcreate -L 7G -n docs app
```

The resulting logical volume is:

```text
/dev/app/docs
```

### Verify LVM

```bash
sudo pvs
sudo vgs
sudo lvs
```

For detailed logical volume information:

```bash
sudo lvdisplay /dev/app/docs
```

### Why LVM?

LVM provides:

- Logical storage abstraction.
- Flexible volume allocation.
- Ability to expand logical volumes when sufficient space is available.
- Separation of filesystem allocation from individual physical disk identities.

In this lab, the logical volume is deliberately smaller than the available RAID capacity.

The unallocated volume group space provides room for future storage management exercises.

## 10. Create the ext4 Filesystem

For a new deployment, create an ext4 filesystem:

```bash
sudo mkfs.ext4 /dev/app/docs
```

**Warning:** Formatting destroys an existing filesystem on the target logical volume.

Create the mount directory:

```bash
sudo mkdir -p /srv/company-data
```

Mount the filesystem:

```bash
sudo mount /dev/app/docs /srv/company-data
```

Verify:

```bash
findmnt /srv/company-data
df -h /srv/company-data
```

## 11. Configure Persistent Mounting

To make the filesystem mount automatically after reboot, use `/etc/fstab`.

Determine the filesystem UUID:

```bash
sudo blkid /dev/app/docs
```

Example:

```text
/dev/mapper/app-docs: UUID="EXAMPLE-UUID" TYPE="ext4"
```

Edit:

```bash
sudo nano /etc/fstab
```

Add a line using the actual filesystem UUID:

```fstab
UUID=YOUR-ACTUAL-UUID /srv/company-data ext4 defaults 0 2
```

Validate the configuration:

```bash
sudo findmnt --verify
```

For a freshly configured mount, test carefully:

```bash
sudo mount -a
```

Verify:

```bash
findmnt /srv/company-data
```

Using a filesystem UUID is preferable to relying on storage device naming that may change.

## 12. Configure Document Storage Permissions

The shared document directory is:

```text
/srv/company-data/documents
```

Create it:

```bash
sudo mkdir -p /srv/company-data/documents
```

The application uses the dedicated account `companyportal`, with UID/GID `2500`.

For a fresh deployment, ensure the storage server has a corresponding account and group with the required numeric IDs.

Then apply ownership:

```bash
sudo chown -R 2500:2500 /srv/company-data/documents
sudo chmod 750 /srv/company-data/documents
```

The `750` permission mode means:

- Owner: read, write, execute.
- Group: read, execute.
- Others: no permissions.

The execute permission on a directory is necessary to traverse it.

Matching numeric ownership across the NFS server and client is important because traditional NFS access checks are based on numeric user and group identities.

Detailed NFS export and client configuration are documented separately.

See: [NFS Shared Storage](04-nfs.md).

## 13. Storage Verification

### RAID Status

```bash
cat /proc/mdstat
```

Expected for a healthy two-member mirror:

```text
[UU]
```

### RAID Details

```bash
sudo mdadm --detail /dev/md0
```

Verify that the array is healthy and the expected members are present.

### LVM Status

```bash
sudo pvs
sudo vgs
sudo lvs
```

### Filesystem Status

```bash
df -h /srv/company-data
findmnt /srv/company-data
```

### Complete Block Device Layout

```bash
lsblk -f
```

### Directory Ownership

```bash
ls -ldn /srv/company-data/documents
```

Expected numeric ownership:

```text
2500 2500
```

## 14. RAID Monitoring with Prometheus

Node Exporter can expose Linux software RAID metrics.

On `storage01`, inspect the available MD metrics:

```bash
curl -s http://127.0.0.1:9100/metrics | grep '^node_md_'
```

Depending on the installed Node Exporter version, metrics can report array membership, disk state, or synchronization information.

The lab includes an alert category for RAID degradation.

The monitoring rule should compare the active and required member counts using metric names that are actually exposed by the installed exporter.

Do not assume the RAID alert works merely because its Prometheus YAML passes syntax validation.

Verify the relevant metric series and expression in Prometheus.

## 15. Backup Integration

The storage server is the source of the encrypted backup process.

Backup source:

```text
/srv/company-data/documents
```

Restic transfers encrypted backup data to `backup01` over SSH/SFTP.

The repository is stored at:

```text
/srv/backups/restic
```

Backup scheduling is managed through systemd services and timers.

This architecture combines:

- RAID 1 for redundancy.
- LVM for storage management.
- ext4 for persistent files.
- NFS for shared access.
- Restic for encrypted backup snapshots.

See: [Backup & Disaster Recovery](06-backup-disaster-recovery.md).


## 17. Security Considerations

- Restrict direct administration of storage devices to privileged accounts.
- Limit NFS exports to authorized clients.
- Use consistent numeric identities for shared files.
- Avoid world-writable document directories.
- Monitor RAID health and filesystem capacity.
- Keep backup repositories independent from the primary storage filesystem.
- Verify backups and practice restoration.
- Do not publish real sensitive file contents or credentials.

## 18. Design Summary

The storage configuration follows this sequence:

```text
Two Dedicated Disks
        |
     RAID 1
        |
       LVM
        |
      ext4
        |
 Centralized Documents
        |
       NFS
        |
      web01
```

The layered design demonstrates practical Linux storage administration, disk redundancy, volume management, filesystem configuration, and shared data access.

The backup system complements this architecture by providing encrypted recovery snapshots outside the primary storage VM.

## 19. Related Documentation

- [Infrastructure Architecture](01-architecture.md)
- [Networking](02-networking.md)
- [NFS Shared Storage](04-nfs.md)
- [Backup & Disaster Recovery](06-backup-disaster-recovery.md)
- [Logging and monitoring](07-Logging-Monitoring-Alerting.md)
- [Troubleshooting](08-Troubleshooting.md)

---

**Previous:** [← Networking](02-networking.md)  
**Next:** [NFS Shared Storage →](04-nfs.md)