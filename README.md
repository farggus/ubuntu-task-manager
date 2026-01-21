# Ubuntu Task Manager (UTM) v2.0

Full-featured TUI dashboard for monitoring and managing Ubuntu/Linux servers directly from the terminal.

## Features

### 9 Monitoring Tabs

| Key | Tab | Description |
|-----|-----|-------------|
| `1` | **Processes** | Process monitoring with filtering and management |
| `2` | **Services** | Systemd services with management (start/stop/restart) |
| `3` | **Packages** | Installed packages and available apt updates |
| `4` | **Containers** | Docker containers with management and log viewing |
| `5` | **Tasks** | Cron jobs and Systemd timers |
| `6` | **Network** | Interfaces, ports, firewall, routes |
| `7` | **Users** | Active sessions and all system users |
| `8` | **Disks** | Disk partitions with hierarchy |
| `0` | **Logging** | Live application log tail |

### Compact System Panel (Always Visible)

Displayed in 3 columns with live data:

- **Overview**: Hostname, IP, Kernel, Uptime, Cores, Temperature, Users, Processes, Services, Packages
- **Sparkline Charts**: CPU Load (60 points history), RAM Usage, SWAP Usage with color indication
- **Disk Usage**: Table of main partitions with usage stats

### Interactive Controls (Hotkeys)

**Processes Tab:**
- `A` - All processes, `Z` - Zombies only
- `C` - Send SIGCHLD to parent, `K` - SIGTERM (kill zombie)

**Services Tab:**
- `R` - Restart, `S` - Start, `K` - Stop service

**Packages Tab:**
- `A` - Toggle all/updates only
- `U` - Update package, `Shift+U` - Update all

**Containers Tab:**
- `A` - All, `R` - Running, `S` - Stopped
- `X` - Start, `K` - Stop, `Shift+R` - Restart
- `L` - Show container logs

**Global:**
- `Ctrl+Q` - Quit
- `Ctrl+R` - Refresh all data
- `Ctrl+S` - Export snapshot to JSON

### Architecture
- **Modular Collector System**: 6 collectors (System, Services, Network, Tasks, Processes, Users)
- **Extensible Widgets**: Each tab is a separate widget with hotkeys
- **Configurable**: Setup via YAML file
- **Logging**: RotatingFileHandler with live tail
- **Export**: JSON snapshot of system state

## Installation

### 1. Clone and Install Dependencies

```bash
# Install dependencies
pip install -r requirements.txt

# Or using virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Permissions Setup (Optional)

Some functions require root privileges:
- Open ports info with processes
- Firewall rules (iptables)
- System cron files
- Service management (start/stop/restart)
- Docker container management
- Apt upgrade

You can run with `sudo` or configure sudo without password for specific commands.

## Usage

### Basic Start
```bash
python main.py
```

### With Custom Configuration
```bash
python main.py --config /path/to/custom-config.yaml
```

### Hotkeys

**Navigation:**
- `1-8, 0` - Switch tabs
- `Tab` / `Shift+Tab` - Next/Previous tab

**Global:**
- `Ctrl+Q` - Quit
- `Ctrl+R` - Refresh all data
- `Ctrl+S` - Export snapshot to JSON

**In Tables:**
- `↑↓` - Row navigation
- `Enter` - Select/Action

### Data Export

`Ctrl+S` creates a JSON file with all information:

```json
{
  "timestamp": "2026-01-17T12:00:00",
  "hostname": "server",
  "system": {...},
  "services": {...},
  "network": {...},
  "tasks": {...},
  "processes": {...},
  "users": {...}
}
```

### Task View (CLI)

To view all cron/timer tasks in detail:

```bash
python src/list_tasks.py
# or with sudo for all users
sudo python src/list_tasks.py
```

See detailed documentation: [CRON_MONITORING.md](docs/CRON_MONITORING.md)

## Configuration

Edit `config/config.yaml` to configure:

```yaml
# Refresh intervals (in seconds)
refresh_intervals:
  system: 5
  services: 10
  network: 15
  tasks: 30

# Enabled collectors
collectors:
  - system
  - services
  - network
  - tasks

# Docker settings
docker:
  enabled: true
  socket: unix:///var/run/docker.sock

# Network monitoring
network:
  interfaces: all  # or list: [eth0, wlan0]
  check_firewall: true
  check_open_ports: true

# Services monitoring (systemd)
services:
  monitor_all: false  # if true, shows all services
  specific_services:
    - nginx
    - postgresql
    - redis
    - ssh
    # Add your services here
```

## Project Structure

```
utm/
├── src/                    # Source code
│   ├── main.py             # Entry point
│   ├── const.py            # App constants
│   ├── collectors/         # Data collectors
│   ├── dashboard/          # UI logic
│   └── utils/              # Utilities
├── config/                 # Configuration
│   └── config.yaml         # Main config
├── scripts/                # Helper scripts
│   ├── install.sh
│   └── run.sh
├── docs/                   # Documentation
│   ├── QUICKSTART.md
│   └── ...
├── logs/                   # Log files
├── tests/                  # Tests
├── requirements.txt        # Dependencies
└── Dockerfile              # Docker build
```

## Extending Functionality

### Adding a New Collector

1. Create a new file in `src/collectors/`:

```python
from .base import BaseCollector

class MyCustomCollector(BaseCollector):
    def collect(self) -> Dict[str, Any]:
        return {
            'my_data': self._get_my_data()
        }

    def _get_my_data(self):
        # Your data collection logic
        pass
```

2. Add to `src/collectors/__init__.py`:

```python
from .my_custom import MyCustomCollector
__all__ = [..., 'MyCustomCollector']
```

3. Create a widget in `src/dashboard/widgets/`:

```python
from textual.widgets import Static

class MyCustomWidget(Static):
    def __init__(self, collector):
        super().__init__()
        self.collector = collector

    def render(self):
        data = self.collector.get_data()
        # Your display logic
```

4. Add to `src/dashboard/app.py`

### Adding Custom Scripts

You can add custom scripts for data collection:

1. Create directory `scripts/custom/` (or similar)
2. Add executable scripts
3. Enable in `config/config.yaml`:

```yaml
custom_checks:
  enabled: true
  scripts_dir: ./scripts/custom
```

## Roadmap

**Implemented in v2.0:**
- [x] Data Export (JSON snapshot)
- [x] Metrics History (Sparkline charts)
- [x] Log Monitoring (Live tail)
- [x] Service Management (start/stop/restart)
- [x] Container Management (start/stop/restart, logs)
- [x] CPU Temperature (via psutil)
- [x] Package Management (apt upgrade)
- [x] Process Management (kill zombies)

**Planned:**
- [ ] Web GUI (Flask/FastAPI) for remote access
- [ ] CSV Export
- [ ] Alerts and Notifications
- [ ] Prometheus/Grafana Integration
- [ ] LXC/LXD Container Support
- [ ] ZFS/RAID Monitoring
- [ ] GPU Monitoring (nvidia-smi)
- [ ] UPS Monitoring (NUT)

## Requirements

- Python 3.8+
- Linux system (tested on Ubuntu/Debian)
- Systemd (for service monitoring)
- Docker (optional, for container monitoring)

## Dependencies

- `textual` - TUI framework
- `rich` - Terminal formatting
- `psutil` - System info
- `pyyaml` - Config parsing
- `docker` - Docker API (optional)
- `croniter` - Cron parsing
- `python-dateutil` - Date utilities
- `pytest` - Testing (dev)

## License

MIT

## Author

Created for convenient home server management.