## 1. Network Troubleshooting

### No IP Address

Check the interface state:

```bash
ip -br link
```

Inspect the active network management service and configuration.

Confirm that the VirtualBox network adapter is connected.

### Incorrect Default Gateway

Check:

```bash
ip route
```

The lab gateway should be:

```text
10.0.2.1
```

### Cannot Reach Another VM

Verify:

1. Both VMs are running.
2. Both use the same NAT Network.
3. Their IP addresses and subnet masks are correct.
4. There are no duplicate addresses.
5. Firewall rules permit the required traffic.

### IP Connectivity Works, DNS Fails

Check the resolver configuration:

```bash
cat /etc/resolv.conf
```

Test hostname resolution:

```bash
getent hosts debian.org
```

Then inspect the DNS settings managed by the system's network manager.

### Service Reachability Fails

Check whether the service is running:

```bash
sudo systemctl status SERVICE_NAME
```

Inspect listening sockets:

```bash
sudo ss -tlnp
```

Check firewall status:

```bash
sudo ufw status
```

`ufw` is relevant only where it is installed and used; Debian installations may use other firewall management tools.

---
## 2. Storage Troubleshooting

### RAID Array Degraded

Inspect:

```bash
cat /proc/mdstat
sudo mdadm --detail /dev/md0
```

A degraded RAID 1 array may show:

```text
[U_]
```

or:

```text
[_U]
```

This indicates that one expected member is unavailable.

Do not immediately run disk replacement or array rebuild commands.

First identify the failed member, review the array state, and ensure that recoverable backups exist.

### LVM Volume Missing

Check:

```bash
sudo pvs
sudo vgs
sudo lvs
```

Verify that `/dev/md0` is assembled and recognized as a physical volume.

### Filesystem Not Mounted

Check:

```bash
findmnt /srv/company-data
sudo blkid /dev/app/docs
```

Inspect:

```bash
cat /etc/fstab
```

Confirm that the configured UUID matches the filesystem.

### Permission Denied

Check:

```bash
ls -ldn /srv/company-data/documents
```

Compare ownership with the application UID/GID on `web01`.

Also inspect NFS export restrictions and mount state.

### Disk Space Running Low

Check:

```bash
df -h /srv/company-data
sudo vgs
sudo lvs
```

There may be unused capacity in the volume group, but extending storage requires adequate available space and a verified procedure.

Avoid making filesystem changes without checking the current state and protecting important data.

---
## 3. NFS Troubleshooting

### Permission Denied

On both hosts:

```bash
id companyportal
ls -ldn /srv/company-data/documents
```

On `web01`, use the corresponding mounted path:

```bash
ls -ldn /mnt/company-documents/documents
```

Confirm ownership, parent-directory permissions, export rules, and mount status.

### Mount Fails

On `web01`:

```bash
ping -c 3 10.0.2.12
findmnt /mnt/company-documents
```

On `storage01`:

```bash
sudo systemctl status nfs-kernel-server
sudo exportfs -v
sudo ss -tlnp | grep 2049
```

### Application Cannot Access Documents

Check the actual mount:

```bash
findmnt /mnt/company-documents
```

Inspect the service:

```bash
sudo systemctl status company-portal
sudo journalctl -u company-portal -n 50 --no-pager
```

A healthy Flask process does not necessarily mean NFS is available.

---
## Log & Monitoring Troubleshooting

The combined monitoring and logging environment supports a structured incident investigation process.

For example, if the company portal becomes unavailable:

1. Prometheus detects a failed HTTP probe.
2. The `CompanyPortalDown` rule may begin pending and then firing.
3. The administrator checks server health in Grafana.
4. Centralized Nginx and application logs provide details about the failed requests.
5. Storage and NFS logs can help identify dependency-related failures.
6. After recovery, the HTTP probe returns to a healthy state and the alert resolves.

This approach demonstrates how metrics, logs, and alerts complement each other.

## Operational Benefits

### Centralized Visibility

Multiple Linux machines can be observed from one operations server.

### Proactive Incident Detection

Alert rules surface defined abnormal conditions instead of relying exclusively on manual inspection.

### Cross-Server Troubleshooting

Centralized logs support investigation across different infrastructure components.

### Infrastructure Performance Analysis

Grafana dashboards make it easier to identify resource trends and compare system behavior.

### Separation of Responsibilities

Application, storage, backup, and operations workloads remain on dedicated virtual machines.

