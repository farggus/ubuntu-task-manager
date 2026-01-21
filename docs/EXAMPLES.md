# Usage Examples and Extension

## Configuration Examples

### Minimal Configuration
```yaml
collectors:
  - system
  - services

services:
  specific_services:
    - nginx
    - postgresql
```

### Full Configuration for Home Media Server
```yaml
refresh_intervals:
  system: 5
  services: 10
  network: 15
  tasks: 30

collectors:
  - system
  - services
  - network
  - tasks

docker:
  enabled: true

network:
  interfaces: all
  check_firewall: true
  check_open_ports: true

services:
  monitor_all: false
  specific_services:
    - nginx
    - plex
    - transmission
    - sonarr
    - radarr
    - jackett
    - postgresql
    - redis
    - samba
    - ssh
```

### For NAS Server
```yaml
collectors:
  - system
  - services
  - network
  - tasks

services:
  specific_services:
    - samba
    - nfs-server
    - ssh
    - cockpit
    - smartd

network:
  interfaces: all
  check_firewall: true
```

## Custom Collector Examples

### 1. Temperature Monitoring (lm-sensors)

Create `collectors/temperature.py`:

```python
from .base import BaseCollector
import subprocess
import shlex
import re

class TemperatureCollector(BaseCollector):
    def collect(self):
        try:
            result = subprocess.run(
                shlex.split("sensors -A"),
                capture_output=True,
                text=True,
                timeout=5
            )

            temps = []
            current_device = None

            for line in result.stdout.splitlines():
                if line and not line.startswith(' '):
                    current_device = line.strip(':')
                elif '+' in line and '°C' in line:
                    match = re.search(r'(\d+\.\d+)°C', line)
                    if match:
                        temp = float(match.group(1))
                        label = line.split(':')[0].strip()
                        temps.append({
                            'device': current_device,
                            'label': label,
                            'temperature': temp
                        })

            return {
                'sensors': temps,
                'max_temp': max((t['temperature'] for t in temps), default=0)
            }
        except Exception as e:
            return {'error': str(e)}
```

### 2. ZFS Disk Space Monitoring

Create `collectors/zfs.py`:

```python
from .base import BaseCollector
import subprocess
import shlex

class ZFSCollector(BaseCollector):
    def collect(self):
        try:
            result = subprocess.run(
                shlex.split("zfs list -o name,used,avail,refer,mountpoint"),
                capture_output=True,
                text=True,
                timeout=5
            )

            datasets = []
            lines = result.stdout.splitlines()[1:]  # Skip header

            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    datasets.append({
                        'name': parts[0],
                        'used': parts[1],
                        'available': parts[2],
                        'referenced': parts[3],
                        'mountpoint': parts[4]
                    })

            return {
                'datasets': datasets,
                'total': len(datasets)
            }
        except Exception as e:
            return {'error': str(e)}
```

### 3. SSL Certificate Monitoring

Create `collectors/ssl.py`:

```python
from .base import BaseCollector
import subprocess
import shlex
from datetime import datetime
import ssl
import socket

class SSLCollector(BaseCollector):
    def collect(self):
        domains = self.config.get('ssl', {}).get('domains', [])
        certificates = []

        for domain in domains:
            try:
                context = ssl.create_default_context()
                with socket.create_connection((domain, 443), timeout=5) as sock:
                    with context.wrap_socket(sock, server_hostname=domain) as ssock:
                        cert = ssock.getpeercert()

                        expiry = datetime.strptime(
                            cert['notAfter'],
                            '%b %d %H:%M:%S %Y %Z'
                        )

                        days_left = (expiry - datetime.now()).days

                        certificates.append({
                            'domain': domain,
                            'expiry': expiry.isoformat(),
                            'days_left': days_left,
                            'issuer': cert.get('issuer'),
                            'valid': days_left > 0
                        })
            except Exception as e:
                certificates.append({
                    'domain': domain,
                    'error': str(e)
                })

        return {
            'certificates': certificates,
            'expiring_soon': [c for c in certificates if c.get('days_left', 999) < 30]
        }
```

## Custom Scripts Examples

### Update Check (Ubuntu/Debian)
Create `custom_scripts/check_updates.sh`:

```bash
#!/bin/bash
apt update -qq
updates=$(apt list --upgradable 2>/dev/null | grep -c upgradable)
security=$(apt list --upgradable 2>/dev/null | grep -c security)

echo "Total updates: $updates"
echo "Security updates: $security"
```

### Backup Status Check
Create `custom_scripts/check_backups.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/mnt/backups"
LAST_BACKUP=$(ls -t $BACKUP_DIR | head -1)
LAST_BACKUP_DATE=$(stat -c %Y "$BACKUP_DIR/$LAST_BACKUP")
CURRENT_DATE=$(date +%s)
DIFF=$(( ($CURRENT_DATE - $LAST_BACKUP_DATE) / 86400 ))

echo "Last backup: $LAST_BACKUP"
echo "Days since last backup: $DIFF"
```

## Run as systemd service

Create `/etc/systemd/system/utm.service`:

```ini
[Unit]
Description=Ubuntu Task Manager (UTM)
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/utm
ExecStart=/usr/bin/python3 /path/to/utm/main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable utm
sudo systemctl start utm
```

## Export Data to JSON

Add to `main.py`:

```python
@app.command()
def export_json(output: str = "utm.json"):
    """Export current utm to JSON."""
    collectors = {
        'system': SystemCollector(),
        'services': ServicesCollector(),
        'network': NetworkCollector(),
        'tasks': TasksCollector()
    }

    data = {}
    for name, collector in collectors.items():
        data[name] = collector.update()

    with open(output, 'w') as f:
        json.dump(data, f, indent=2, default=str)

    print(f"UTM exported to {output}")
```

## Integration with Monitoring

### Prometheus exporter
You can create a simple HTTP endpoint for Prometheus:

```python
from flask import Flask, Response
import prometheus_client as prom

app = Flask(__name__)

# Metrics
cpu_usage = prom.Gauge('system_cpu_usage', 'CPU Usage')
memory_usage = prom.Gauge('system_memory_usage', 'Memory Usage')

@app.route('/metrics')
def metrics():
    collector = SystemCollector()
    data = collector.update()

    cpu_usage.set(data['cpu']['usage_total'])
    memory_usage.set(data['memory']['percent'])

    return Response(
        prom.generate_latest(),
        mimetype='text/plain'
    )
```

## Alerts

Create `alerts.py`:

```python
def check_alerts(data):
    alerts = []

    # CPU usage
    if data['system']['cpu']['usage_total'] > 90:
        alerts.append({
            'level': 'warning',
            'message': f"High CPU usage: {data['system']['cpu']['usage_total']}%"
        })

    # Memory usage
    if data['system']['memory']['percent'] > 90:
        alerts.append({
            'level': 'critical',
            'message': f"High memory usage: {data['system']['memory']['percent']}%"
        })

    # Failed services
    failed = data['services']['systemd']['failed']
    if failed > 0:
        alerts.append({
            'level': 'error',
            'message': f"{failed} failed services"
        })

    return alerts
```