# Networking Configuration

[← Back to Main README](../README.md)

## 1. Overview

Networking is the foundation of the Linux infrastructure lab.

The four virtual machines communicate through a dedicated **VirtualBox NAT Network** using static IPv4 addresses.

The network allows servers to exchange application data, access NFS storage, transfer encrypted backups, forward logs, and expose monitoring metrics.

This guide covers the network architecture, addressing plan, VirtualBox configuration, Linux network management, connectivity verification, and common troubleshooting procedures.

## 2. Network Design

### Network Parameters

| Parameter | Value |
|---|---|
| Virtualization platform | Oracle VirtualBox |
| Network type | NAT Network |
| Subnet | `10.0.2.0/24` |
| Subnet mask | `255.255.255.0` |
| Default gateway | `10.0.2.1` |
| Addressing | Static IPv4 |
| DNS | Configured separately on each guest |

### IP Addressing Plan

| Hostname | IP Address | Role |
|---|---|---|
| `web01` | `10.0.2.11` | Application server |
| `storage01` | `10.0.2.12` | Storage server |
| `ops01` | `10.0.2.13` | Monitoring and logging |
| `backup01` | `10.0.2.14` | Backup server |

Static addresses allow infrastructure services to use predictable destinations.

For example, Prometheus can scrape Node Exporter on known IP addresses, and NFS exports can restrict access to the expected application server.

## 3. Why VirtualBox NAT Network?

VirtualBox supports several network attachment modes, including NAT, NAT Network, Bridged, and Host-only networking.

A **NAT Network** was selected because it allows virtual machines attached to the same virtual network to communicate with each other while also supporting outbound connectivity through VirtualBox's network translation.

Unlike ordinary per-VM NAT attachment, NAT Network supports communication between the attached virtual machines.

### Communication Model

```text
                      Internet
                         |
                  Physical Host
                         |
                  VirtualBox NAT
                         |
                    10.0.2.1
                         |
                 10.0.2.0/24
                         |
       +---------+-------+-------+-----
       |         |       |       |     
     web01   storage01  ops01  backup01
      .11       .12      .13     .14   
```

NAT Network does not automatically make every guest service reachable from the physical host or external network. Port forwarding or another explicitly configured access path may be needed.

## 4. Configure the VirtualBox NAT Network

The following settings describe the lab configuration.

In VirtualBox:

1. Open the network management interface.
2. Create a NAT Network.
3. Assign the network range `10.0.2.0/24`.
4. Enable the network.
5. Configure DHCP according to the addressing plan, avoiding conflicts with the static addresses.
6. Attach every VM to the same NAT Network.

For each virtual machine:

**Settings → Network → Adapter 1**

Configure:

```text
Enable Network Adapter: Yes
Attached to: NAT Network
Name: Your configured NAT Network
Cable Connected: Yes
```

The NAT Network name is a local VirtualBox setting and may differ between installations.

## 5. Identify Network Interfaces

Before configuring networking, identify the actual interface name on each VM:

```bash
ip -br link
```

or:

```bash
ip -br addr
```

Example:

```text
lo      UNKNOWN  127.0.0.1/8
enp0s3  UP       10.0.2.11/24
```

The example uses `enp0s3`, but interface names may differ.

**Never assume the interface name without verifying it.**

Check the existing network configuration before modifying it.

## 6. Static IP on Ubuntu Server 24.04

Ubuntu Server 24.04 commonly uses **Netplan** for network configuration.

Example for `web01`:

Create or edit an appropriate Netplan file:

```bash
sudo nano /etc/netplan/50-cloud-init.yaml
```

Your actual configuration filename may differ.

Example:

```yaml
network:
  version: 2
  ethernets:
    enp0s3:
      dhcp4: false
      addresses:
        - 10.0.2.11/24
      routes:
        - to: default
          via: 10.0.2.1
      nameservers:
        addresses:
          - 1.1.1.1
          - 8.8.8.8
```

Replace `enp0s3` with the actual interface name.

The DNS addresses are examples, not a requirement. Use reachable, appropriate DNS servers for the environment.

Validate the Netplan configuration:

```bash
sudo netplan generate
```

If applying changes over an SSH connection, prefer:

```bash
sudo netplan try
```

This provides an opportunity to revert changes if connectivity is lost.

For direct console access, the configuration can be applied with:

```bash
sudo netplan apply
```

### Ubuntu Server Addresses

Use the appropriate static address for each Ubuntu server:

```text
web01   10.0.2.11/24
ops01   10.0.2.13/24
```

Both use the default gateway `10.0.2.1`.

## 7. Static IP on Debian 13

Debian can use different network managers depending on the installation.

A minimal server may use traditional ifupdown configuration, while another installation may use NetworkManager or systemd-networkd.

Identify which service manages networking before making changes.

Useful commands:

```bash
systemctl is-active networking
systemctl is-active NetworkManager
systemctl is-active systemd-networkd
```

### Example: ifupdown Configuration

If the system uses ifupdown, edit:

```bash
sudo nano /etc/network/interfaces
```

Example for `storage01`:

```text
auto lo
iface lo inet loopback

auto enp0s3
iface enp0s3 inet static
    address 10.0.2.12
    netmask 255.255.255.0
    gateway 10.0.2.1
```

DNS settings depend on the installed resolver configuration and should be managed through the system's active DNS management mechanism.

A network restart can interrupt SSH access. Prefer using the VirtualBox console when changing the management interface.

### Debian Server Addresses

```text
storage01   10.0.2.12/24
backup01    10.0.2.14/24
```

All use the same default gateway.

The configuration shown above is an example for hosts using ifupdown. Do not copy it unchanged onto machines managed by NetworkManager or systemd-networkd.

## 8. Configure Hostnames

Assign each VM its intended hostname.

Example on the web server:

```bash
sudo hostnamectl set-hostname web01
```

For the other machines:

```bash
sudo hostnamectl set-hostname storage01
sudo hostnamectl set-hostname ops01
sudo hostnamectl set-hostname backup01
```

Run only the command appropriate to the VM being configured.

Verify:

```bash
hostnamectl
```

### Local Hostname Resolution

For a small lab without internal DNS, `/etc/hosts` can provide basic hostname resolution.

Example entries:

```text
10.0.2.11  web01
10.0.2.12  storage01
10.0.2.13  ops01
10.0.2.14  backup01
```

These mappings can be added to `/etc/hosts` on machines that need name-based access.

Preserve the existing loopback entries.

Verify:

```bash
getent hosts storage01
```

## 9. Verify the Network Configuration

### Check IP Addresses

```bash
ip -br addr
```

Confirm that each VM has the expected address.

### Check the Default Gateway

```bash
ip route
```

Expected default route:

```text
default via 10.0.2.1 dev enp0s3
```

The interface name may differ.

### Test Local Connectivity

From `web01`:

```bash
ping -c 3 10.0.2.12
ping -c 3 10.0.2.13
ping -c 3 10.0.2.14
```

From `storage01`:

```bash
ping -c 3 10.0.2.11
ping -c 3 10.0.2.14
```

ICMP reachability verifies basic connectivity but does not prove that application ports are available.

### Verify SSH

For example, from an authorized client:

```bash
ssh username@10.0.2.12
```

Use an existing permitted account rather than assuming a particular administrative username.

### Check Listening Ports

```bash
sudo ss -tlnp
```

Useful ports include:

```text
22     SSH
80     HTTP
2049   NFS
514    rsyslog TCP
9100   Node Exporter
9090   Prometheus
3000   Grafana
9093   Alertmanager
9115   Blackbox Exporter
```

Not all ports should listen on all VMs.

### Verify an HTTP Service

From a machine with permitted access:

```bash
curl -I http://10.0.2.11
```

### Verify Monitoring Connectivity

From `ops01`:

```bash
curl -s http://10.0.2.11:9100/metrics | head
```

A successful response containing Prometheus-format metrics confirms access to the Node Exporter endpoint.

## 10. Security Considerations

This is a private homelab network, but network access should still be restricted.

Recommended practices include:

- Permit SSH only from authorized management systems.
- Restrict NFS access to the intended client.
- Keep Prometheus, Grafana, and Alertmanager administration interfaces accessible only to trusted machines.
- Restrict rsyslog TCP reception to infrastructure senders.
- Avoid exposing Node Exporter to untrusted networks.
- Review firewall rules before enabling external access.
- Avoid unnecessary VirtualBox port forwarding.

**NAT Network is not a substitute for a properly designed security boundary.**


## 11. Related Documentation

- [Architecture](01-architecture.md)
- [Storage — RAID 1, LVM & ext4](03-storage-raid-lvm.md)
- [NFS Shared Storage](04-nfs.md)
- [Web Server](05-web-server.md)
- [Logging and monitoring](07-Logging-Monitoring-Alerting.md)
- [Troubleshooting](08-Troubleshooting.md)

---

**Previous:** [← Infrastructure Architecture](01-architecture.md)  
**Next:** [Storage Management →](03-storage-raid-lvm.md)