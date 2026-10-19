# Centralized Logging, Monitoring & Alerting

[← Back to Main README](../README.md)

## Overview

The `ops01` server provides a centralized platform for **Linux infrastructure monitoring, log aggregation, visualization, and alert management**.

The environment integrates:

- **rsyslog** for centralized log collection.
- **Prometheus** for time-series metrics and alert evaluation.
- **Node Exporter** for Linux server metrics.
- **Blackbox Exporter** for HTTP application availability.
- **Grafana** for infrastructure dashboards.
- **Alertmanager** for managing and routing alerts.

The objective is to simulate the operational responsibilities of a Linux System Administrator: maintaining visibility into server health, identifying failures, analyzing resource usage, and investigating incidents across several Linux machines.

## Operations Server

| Property | Value |
|---|---|
| Hostname | `ops01` |
| Operating System | Ubuntu Server 24.04 |
| IP Address | `10.0.2.13` |
| Metrics Collection | Prometheus |
| System Metrics | Node Exporter |
| Application Probing | Blackbox Exporter |
| Visualization | Grafana |
| Alert Management | Alertmanager |
| Centralized Logging | rsyslog |

### Managed Infrastructure

| Server | IP Address | Monitoring | Log Forwarding |
|---|---|---|---|
| `web01` | `10.0.2.11` | Node Exporter + HTTP probe | System, Nginx, application |
| `storage01` | `10.0.2.12` | Node Exporter + RAID metrics | System, NFS, backup |
| `backup01` | `10.0.2.14` | Node Exporter | System, authentication |
| `ops01` | `10.0.2.13` | Node Exporter | Local logging |

## Observability Architecture

```text
                  LINUX INFRASTRUCTURE

        web01      storage01      backup01
           \           |             /
            \          |            /
             +---------+-----------+
                       |
              +--------+--------+
              |                 |
         System Metrics     System & Service Logs
              |                 |
         Node Exporter         rsyslog
              |                 |
              v                 v
        +------------+    +----------------+
        | Prometheus |    | Central Logs   |
        |            |    | /var/log/remote|
        +------------+    +----------------+
              |
       +------+-------+
       |              |
       v              v
    Grafana       Alert Rules
                      |
                      v
                 Alertmanager

           All services hosted on ops01

       Company Portal HTTP /health
                    |
                    v
             Blackbox Exporter
                    |
                    v
                Prometheus
```

The logging and monitoring systems have different purposes.

**Logs** provide detailed information about events and failures.

**Metrics** provide numerical measurements of system and application behavior over time.

**Alerts** notify or surface conditions that require administrative attention.

Combining all three improves infrastructure visibility.

---

# Part I — Centralized Logging

## Why Centralized Logging?

In an environment with multiple Linux machines, analyzing logs separately on each server makes troubleshooting more complicated.

For example, an application failure may involve both the web server and the storage server.

Centralized logging makes relevant messages available in one location, reducing the need to switch between machines during incident investigation.

The lab uses **rsyslog over TCP** to forward selected Linux system and service logs to `ops01`.

## Logging Data Flow

```text
web01 ---------------------+
  Nginx access/error       |
  Application logs         |
  System events            |
                           |
storage01 -----------------+---- TCP 514 ----> ops01
  NFS events               |                   |
  Backup events            |                   v
  System events            |            Central rsyslog
                           |                   |
backup01 ------------------+                   v
  Authentication events                 /var/log/remote
  System events
```

TCP is used to transport log messages between the sender and receiver.

Sender-side forwarding queues provide additional resilience when the central log receiver is temporarily unreachable.

The current design does not include TLS encryption for log transport.

## Central Log Organization

Logs are organized according to their source server and service.

```text
/var/log/remote/
├── web01/
│   ├── system.log
│   ├── nginx-access.log
│   ├── nginx-error.log
│   └── company-portal.log
├── storage01/
│   ├── system.log
│   ├── nfs.log
│   └── backup.log
└── backup01/
    ├── system.log
    └── ssh.log
```

### Web Server Logs

The web server provides:

- General system events.
- Nginx access logs.
- Nginx error logs.
- Application-related messages.

This supports HTTP request troubleshooting and investigation of application failures.

### Storage Server Logs

The storage server provides:

- System events.
- NFS-related messages.
- Backup execution messages.

These logs help investigate remote storage access, backup execution, and service-level errors.

### Backup Server Logs

The backup server provides:

- General system events.
- SSH and authentication-related activity.

The `ssh.log` stream may contain other authentication events, depending on the applied routing rules.

## Log Routing & Reliability

The rsyslog implementation separates events by server identity and log category.

The sender configuration uses forwarding queues to reduce the impact of temporary network interruptions.

Important characteristics include:

- Central TCP log reception.
- Per-host log organization.
- Dedicated service-specific log files.
- File-based ingestion for Nginx access and error logs.
- Queued log forwarding between machines.
- Separate local and centralized log locations.

These features demonstrate practical multi-server log administration.

## Logging Verification

The centralized logging pipeline was tested by generating syslog messages from infrastructure servers and confirming that they appeared in the expected destinations on `ops01`.

Service-specific routing was also checked for Nginx, NFS, backup, and authentication-related categories.

Synthetic test messages confirm that matching and routing rules work; verifying the delivery of actual service-generated events is a separate operational check.

## Centralized Logging Limitations

The current system uses plain TCP forwarding and structured files.

It does not provide:

- TLS encryption for remote log transport.
- Indexed or full-text log search across all servers.
- Grafana-based log exploration.
- Automatic correlation of logs with metrics.
- A highly available log receiver.

Possible future improvements include rsyslog TLS, log rotation and retention policies, and integration with Grafana Loki.

---

# Part II — Infrastructure Monitoring with Prometheus

## Why Prometheus?

System logs are useful for detailed event investigation, but they are less convenient for continuously measuring resource utilization.

Prometheus provides numerical time-series data that can be queried, visualized, and used for alert evaluation.

The infrastructure uses Prometheus to collect Linux system metrics across four servers.

## Metrics Collection Architecture

```text
web01:9100 -----------+
                      |
storage01:9100 -------+
                      |
backup01:9100 --------+----> Prometheus
                      |      ops01:9090
ops01:9100 -----------+
                             |
                       Time-Series Data
                             |
                      +------+------+
                      |             |
                      v             v
                   Grafana     Alert Rules
```

Node Exporter runs on each managed Linux server and exposes operating system metrics through an HTTP endpoint.

Prometheus collects these metrics every 15 seconds.

The servers are assigned readable labels so that monitoring dashboards can distinguish between `web01`, `storage01`, `backup01`, and `ops01`.

## Collected Infrastructure Metrics

| Category | Metrics |
|---|---|
| CPU | Usage and CPU time by mode |
| Memory | Total and available system memory |
| Storage | Filesystem capacity and free space |
| Availability | Prometheus scrape success |
| Uptime | Time since server boot |
| RAID | Software RAID information where exposed by Node Exporter |

These measurements allow resource usage to be compared across servers over time.

## Storage and RAID Monitoring

The storage server uses an mdadm RAID 1 array named `md0`.

Node Exporter's software RAID metrics are intended to provide information about array condition and membership.

Prometheus includes a RAID degradation alert designed to detect when the number of active RAID members falls below the expected count.

The exact alert behavior depends on the metric names and labels supported by the installed Node Exporter version.

A healthy Node Exporter endpoint alone does not guarantee that the RAID condition has been verified.

## Prometheus Role

Prometheus is responsible for:

- Periodically scraping exporter endpoints.
- Storing time-series monitoring data.
- Evaluating PromQL expressions.
- Making metrics available to Grafana.
- Evaluating alert rules.
- Forwarding firing and resolved alerts to Alertmanager.

Prometheus operates independently of the rsyslog log collection pipeline.

---

# Part III — Application Availability Monitoring

## Blackbox Exporter

Server-level metrics do not necessarily indicate whether a hosted application is accessible.

For example, the Linux operating system might remain healthy while Nginx or Gunicorn stops serving the portal.

To address this, the lab uses **Prometheus Blackbox Exporter**.

Blackbox Exporter checks the portal's HTTP health endpoint:

`http://10.0.2.11/health`

### Monitoring Flow

```text
          Prometheus
               |
         HTTP Probe Job
               |
               v
        Blackbox Exporter
               |
               v
         Company Portal
           web01:80
               |
               v
       HTTP Success / Failure
               |
               v
           Prometheus
```

The primary result is represented by the `probe_success` metric.

A successful HTTP probe normally produces `1`, while a failed probe produces `0`.

This monitoring provides an additional level of visibility beyond basic server availability.

### Health vs. Readiness

The `/health` endpoint confirms that the portal responds to an HTTP request.

It does not necessarily verify that remote document storage is accessible.

A more complete availability assessment would include storage dependency checks, such as confirming that the NFS-backed document directory is mounted and usable.

---

# Part IV — Grafana Dashboards

## Grafana Overview

Grafana provides a visual representation of the infrastructure metrics collected by Prometheus.

The dashboard was designed to help identify abnormal resource usage, monitor system performance, and compare the operational state of multiple Linux servers.

Grafana connects to the local Prometheus service on `ops01`.

### Dashboard Components

| Dashboard Panel | Purpose |
|---|---|
| CPU Utilization | Shows CPU usage by server |
| RAM Usage | Displays memory consumption |
| Used Disk Space | Tracks occupied filesystem capacity |
| Available Disk Space | Displays remaining filesystem space |
| Server Availability | Shows whether monitoring targets are reachable |
| System Uptime | Displays time since the last boot |

### Dashboard Design

Readable server labels are used to distinguish metrics from different hosts.

For filesystem-specific panels, server names and mount points are displayed together so that individual filesystems can be identified.

The dashboard provides a centralized operational overview without requiring administrators to inspect each Linux machine individually.

### Grafana's Role in This Lab

Grafana is primarily a **metrics visualization interface**.

The centralized rsyslog logs are stored as files on `ops01`, not indexed into Grafana.

Adding Loki or a similar log backend could provide integrated log visualization in a future iteration.

---

# Part V — Prometheus Alerting & Alertmanager

## Alerting Overview

Monitoring provides visibility into infrastructure conditions, but an administrator should not need to watch dashboards continuously.

Prometheus alert rules evaluate conditions such as high resource consumption or service unavailability.

Alertmanager receives alerts from Prometheus and handles grouping, routing, and notification integrations.

## Alerting Architecture

```text
       Node Exporter
             +
       Blackbox Exporter
             |
             v
         Prometheus
             |
      Alert Rule Evaluation
             |
             v
        Alertmanager
             |
      Alert Routing & Grouping
             |
      Notification Receiver
```

## Infrastructure Alert Categories

| Alert | Trigger | Severity |
|---|---|---|
| ServerDown | Node Exporter unavailable for 2 minutes | Critical |
| HighCPU | CPU usage above 85% for 10 minutes | Warning |
| HighRAM | Memory usage above 90% for 5 minutes | Warning |
| LowDiskSpace | Filesystem usage above 85% for 5 minutes | Warning |
| CompanyPortalDown | Failed or missing HTTP health probe for 2 minutes | Critical |
| RAIDDegraded | Insufficient active RAID members for 1 minute | Critical |

The alert thresholds are intended for a small educational infrastructure and may require adjustment for production systems.

### Alert States

Prometheus rules can appear in several states:

- **Inactive:** The alert expression is not currently satisfied.
- **Pending:** The expression is satisfied, but the configured duration has not elapsed.
- **Firing:** The condition has remained true long enough to trigger the alert.

Alertmanager manages received firing and resolved alerts.

It can also group related alerts, suppress notifications using silences, and route different severities to different receivers.

## Alert Validation

The alert rules and Prometheus configuration were checked using Prometheus's configuration validation tools.

The monitoring design also includes a safe synthetic alert test that does not require deliberately shutting down a virtual machine or degrading the RAID array.

There are multiple levels of verification:

1. Configuration validation confirms supported syntax.
2. Metric inspection confirms that the relevant measurements exist.
3. Rule evaluation confirms that alerts enter the expected state.
4. Alertmanager reception confirms that Prometheus forwards alerts.
5. External notification testing confirms delivery to a configured destination.

These should be treated as separate checks rather than assuming one proves the others.

## Notification Limitations

Alertmanager can integrate with external notification systems such as SMTP email.

However, an Alertmanager receiver without a configured delivery integration does not automatically send external notifications.

The repository should distinguish between alert rule configuration, Alertmanager integration, and any independently verified notification delivery.

---

## Troubleshooting Workflow

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

## Security & Operational Limitations

The operations stack is deployed in a private lab environment.

Important considerations include:

- Prometheus and Node Exporter endpoints should be restricted to authorized monitoring traffic.
- Grafana and Alertmanager administrative interfaces should not be publicly exposed.
- rsyslog over plain TCP does not encrypt log content.
- Logs require appropriate file permissions and retention policies.
- Alert rules depend on the availability and correctness of their underlying metrics.
- Centralizing operations services on one VM introduces a single point of failure.
- Both monitoring and logging are affected if the physical VirtualBox host fails.


## Skills Demonstrated

**Centralized Logging**
- rsyslog server/client architecture
- TCP forwarding
- Log routing and classification
- Queue-based forwarding
- Multi-server troubleshooting

**Infrastructure Monitoring**
- Prometheus
- Node Exporter
- PromQL
- CPU, memory, filesystem, and network monitoring
- RAID health monitoring

**Application Monitoring**
- Blackbox Exporter
- HTTP health checks
- Service availability monitoring

**Visualization**
- Grafana dashboards
- Prometheus data source integration
- Time-series analysis
- Infrastructure performance monitoring

**Alert Management**
- Prometheus alert rules
- Threshold-based alerting
- Alertmanager
- Alert severity and grouping
- Alert validation and testing

## Related Documentation

- [Infrastructure Architecture](01-architecture.md)
- [Networking](02-networking.md)
- [Storage Management](03-storage-raid-lvm.md)
- [NFS Shared Storage](04-nfs.md)
- [Web Server](05-web-server.md)
- [Backup & Disaster Recovery](06-backup-disaster-recovery.md)

## Configuration Files

The implementation files are organized separately from this documentation.

- [rsyslog configurations](../configs/rsyslog/)
- [Prometheus configurations](../configs/prometheus/)
- [Grafana configurations](../configs/grafana/)
- [Alertmanager configurations](../configs/alertmanager/)
- [systemd configurations](../configs/systemd/)

These directories are intended to hold sanitized copies of the actual deployed configurations.

---

**Previous:** [← Backup & Disaster Recovery](06-backup-disaster-recovery.md)  
**Back to:** [Main README](../README.md)