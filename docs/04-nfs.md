# NFS Shared Storage

[← Back to Main README](../README.md)

## 1. Overview

The infrastructure uses **Network File System (NFS)** to provide centralized document storage to the internal company portal.

The storage server (`storage01`) hosts the actual filesystem, while the application server (`web01`) accesses the shared directory over the network.

This separates application execution from persistent document storage.

### Infrastructure

| Component | Server | Details |
|---|---|---|
| NFS server | `storage01` | Debian 13 — `10.0.2.12` |
| NFS client | `web01` | Ubuntu Server 24.04 — `10.0.2.11` |
| Server mount point | `storage01` | `/srv/company-data` |
| Exported directory | `storage01` | `/srv/company-data` |
| Client mount point | `web01` | `/mnt/company-documents` |
| Document directory | Both | `documents/` |
| Application account | Both | `companyportal`, UID/GID `2500` |

## 2. Architecture

```text
                 web01
               10.0.2.11
                   |
             Flask Portal
                   |
    /mnt/company-documents/documents
                   |
                NFSv4
                   |
                   v
                storage01
               10.0.2.12
                   |
       /srv/company-data/documents
                   |
             ext4 Filesystem
                   |
              LVM: docs
                   |
            mdadm RAID 1
                   |
             Two Disk Members
```

The Flask portal uses the mounted NFS directory to read and store documents.

The NFS server provides access to the filesystem but does not manage the web application's HTTP requests.

## 3. Install NFS Packages

### On storage01

```bash
sudo apt update
sudo apt install -y nfs-kernel-server
```

Enable the NFS server:

```bash
sudo systemctl enable --now nfs-kernel-server
```

Verify:

```bash
sudo systemctl status nfs-kernel-server
```

### On web01

```bash
sudo apt update
sudo apt install -y nfs-common
```

The `nfs-common` package provides the NFS client utilities.

## 4. Verify the Storage Filesystem

Before configuring NFS, ensure that the underlying filesystem is mounted correctly on `storage01`.

```bash
findmnt /srv/company-data
df -h /srv/company-data
```

Verify the storage layers:

```bash
cat /proc/mdstat
sudo pvs
sudo vgs
sudo lvs
```

**Important:** The NFS share should not be exported from an unmounted fallback directory if the intended ext4 filesystem is unavailable.

Verify the mount before writing or serving production-style data.

## 5. Configure Directory Ownership

The Flask application runs under a dedicated Linux account:

```text
Username: companyportal
UID:      2500
GID:      2500
```

Traditional NFS file permission checks use numeric user and group identities.

The server and client therefore require consistent numeric ownership.

On `storage01`, confirm the account and group:

```bash
getent passwd companyportal
getent group companyportal
id companyportal
```

For a fresh installation where the identities do not already exist:

```bash
sudo groupadd -g 2500 companyportal
sudo useradd -u 2500 -g 2500 \
  -M -s /usr/sbin/nologin companyportal
```

Do not recreate the account if it already exists.

Create the documents directory:

```bash
sudo mkdir -p /srv/company-data/documents
```

Set ownership and permissions:

```bash
sudo chown -R 2500:2500 /srv/company-data/documents
sudo chmod 750 /srv/company-data/documents
```

Verify:

```bash
ls -ldn /srv/company-data/documents
```

Expected ownership:

```text
2500:2500
```

The `750` permissions allow the owner to read, write, and traverse the directory, while group members can read and traverse it.

Parent-directory permissions must also allow the NFS client to traverse the exported path.

## 6. Configure NFS Exports

NFS exports are defined in:

```text
/etc/exports
```

On `storage01`:

```bash
sudo nano /etc/exports
```

An export entry for this lab is:

```exports
/srv/company-data 10.0.2.11(rw,sync,root_squash,no_subtree_check)
```

### Export Options

| Option | Purpose |
|---|---|
| `rw` | Permits read/write operations subject to filesystem permissions |
| `sync` | Requests synchronous handling of storage writes |
| `root_squash` | Maps remote root operations to an unprivileged identity |
| `no_subtree_check` | Disables subtree checking for the exported directory |

The export is restricted to `10.0.2.11`, rather than the entire subnet.

`root_squash` does not prevent access by every privileged or impersonated identity in all threat models. NFS with AUTH_SYS should be used only on a trusted and appropriately restricted network.

Apply the export configuration:

```bash
sudo exportfs -ra
```

Verify active exports:

```bash
sudo exportfs -v
```

Check the server:

```bash
sudo systemctl is-active nfs-kernel-server
```

## 7. Mount NFS on web01

Create the client mount directory:

```bash
sudo mkdir -p /mnt/company-documents
```

Mount the shared filesystem:

```bash
sudo mount -t nfs4 10.0.2.12:/srv/company-data \
  /mnt/company-documents
```

Verify:

```bash
findmnt /mnt/company-documents
```

Check the filesystem:

```bash
df -h /mnt/company-documents
```

List the shared documents:

```bash
ls -la /mnt/company-documents/documents
```

The mounted directory exposes the remote filesystem from `storage01`.

## 8. Configure a Persistent NFS Mount

To mount the share automatically, configure `/etc/fstab` on `web01`.

First, back up the existing file:

```bash
sudo cp /etc/fstab /etc/fstab.bak
```

Edit:

```bash
sudo nano /etc/fstab
```

Add the entry once:

```fstab
10.0.2.12:/srv/company-data /mnt/company-documents nfs4 defaults,_netdev,nofail 0 0
```

### Mount Options

- `defaults`: Standard mount behavior.
- `_netdev`: Marks the filesystem as network-dependent.
- `nofail`: Prevents the unavailable share from being treated as a fatal boot mount failure.

`nofail` does not make application storage available when the NFS server is down.

Validate:

```bash
sudo findmnt --verify
```

Test the configuration:

```bash
sudo mount -a
```

Verify:

```bash
findmnt /mnt/company-documents
```

For an application that must not start without mounted storage, service dependency configuration and application readiness checks are also important.

## 9. Verify Read and Write Access

The most meaningful test is a file operation using the same numeric identity as the Flask application.

On `web01`:

```bash
sudo -u companyportal \
  touch /mnt/company-documents/documents/nfs-test.txt
```

Verify the file:

```bash
ls -ln /mnt/company-documents/documents/nfs-test.txt
```

On `storage01`, check that the same file exists:

```bash
ls -ln /srv/company-data/documents/nfs-test.txt
```

Delete the temporary test file:

```bash
sudo -u companyportal \
  rm /mnt/company-documents/documents/nfs-test.txt
```

This verifies that writes performed through the client are visible on the storage server.

## 10. Application Integration

The web application stores its shared files under:

```text
/mnt/company-documents/documents
```

This path is backed by:

```text
storage01:/srv/company-data/documents
```

The application must:

- Have permission to access the mounted directory.
- Use an appropriate non-root account.
- Handle storage unavailability without corrupting application state.
- Avoid writing documents to the underlying local directory when NFS is not mounted.

The NFS mount and Flask application service should be coordinated through systemd dependencies or application-level readiness checks.

## 11. Security Considerations

- Restrict NFS exports to authorized clients.
- Use `root_squash`.
- Maintain consistent UID/GID ownership.
- Avoid permissive modes such as `777`.
- Restrict NFS traffic at the network/firewall level.
- Avoid exporting storage to untrusted networks.
- Do not confuse NFS permissions with encrypted network transport.

This lab uses NFS on a private VirtualBox network. Production environments may require stronger authentication and network controls.

## Related Documentation

- [Storage — RAID 1, LVM & ext4](03-storage-raid-lvm.md)
- [Web Server](05-web-server.md)
- [Backup & Disaster Recovery](06-backup-disaster-recovery.md)
- [Troubleshooting](08-Troubleshooting.md)

---

**Previous:** [← Storage Management](03-storage-raid-lvm.md)  
**Next:** [Web Server →](05-web-server.md)