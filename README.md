<!-- x-release-please-start-version -->
# Ubuntu Task Manager (UTM) v2.1.0
<!-- x-release-please-end-version -->

Full-featured TUI dashboard for monitoring and managing Ubuntu/Linux servers directly from the terminal.

## Features

### 11 Monitoring Tabs

| Key | Tab | Description |
|-----|-----|-------------|
| `1` | **Processes** | Process monitoring with filtering and management |
| `2` | **Services** | Systemd services with management (start/stop/restart) |
| `3` | **Packages** | Installed packages and available apt updates |
| `4` | **Containers** | Docker containers with management and log viewing |
| `5` | **Tasks** | Cron jobs and Systemd timers |
| `6` | **Network** | Interfaces, ports, firewall, routes |
| `F` | **Fail2ban** | Active bans, jail status, IP management |
| `Shift+F` | **Fail2ban+** | Attack history, slow brute-force detection, analytics |
| `7` | **Users** | Active sessions and all system users |
| `8` | **Disks** | Disk partitions with hierarchy, SMART status |
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
- Click on column header to sort (click again to toggle asc/desc)

**Services Tab:**
- `R` - Restart, `S` - Start, `K` - Stop service

**Packages Tab:**
- `A` - Toggle all/updates only
- `U` - Update package, `Shift+U` - Update all

**Containers Tab:**
- `A` - All, `R` - Running, `S` - Stopped
- `X` - Start, `K` - Stop, `Shift+R` - Restart
- `L` - Show container logs

**Fail2ban Tab:**
- `A` - Analyze fail2ban logs
- `Ctrl+U` - Unban selected IP
- `Ctrl+W` - Manage whitelist
- `Ctrl+B` - Ban IP manually
- `Ctrl+M` - Migrate bans to 3Y

**Fail2ban+ Tab:**
- `D` - Database manager
- `R` - Refresh data

**Global:**
- `Ctrl+Q` - Quit
- `Ctrl+R` - Refresh current tab
- `Ctrl+S` - Toggle system info panel
- `Ctrl+E` - Export snapshot to JSON

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

### 2. Running With or Without Sudo

UTM can run **both with and without root privileges**. Without sudo, some tabs will show limited information:

| Tab | Without sudo | With sudo |
|-----|--------------|-----------|
| `1` Processes | ✅ Full access | ✅ Full access |
| `2` Services | ✅ View only | ✅ View + manage (start/stop/restart) |
| `3` Packages | ✅ View only | ✅ View + upgrade |
| `4` Containers | ⚠️ Requires `docker` group | ✅ Full access |
| `5` Tasks | ⚠️ Current user cron only | ✅ All users cron + system cron |
| `6` Network | ⚠️ No process info on ports, no firewall rules | ✅ Full access (ports, iptables/nftables) |
| `F` Fail2ban | ❌ No access | ✅ Full access |
| `Shift+F` Fail2ban+ | ❌ No access | ✅ Full access |
| `7` Users | ✅ Full access | ✅ Full access |
| `8` Disks | ⚠️ No SMART data | ✅ Full access (SMART via smartctl) |
| `0` Logging | ✅ Full access | ✅ Full access |

**Recommendations:**
- For **full monitoring**: run with `sudo ./scripts/run.sh`
- For **basic monitoring** (processes, services view, users): run without sudo
- For **Docker without sudo**: add your user to the `docker` group: `sudo usermod -aG docker $USER`

## Usage

### Basic Start (Limited Mode)
```bash
source venv/bin/activate
python src/main.py
```
Runs with current user privileges. Some tabs will have limited data (see permissions table above).

### Full Access (Recommended)
```bash
sudo ./scripts/run.sh
```
Runs with root privileges for complete system monitoring.

### With Custom Configuration
```bash
python src/main.py --config /path/to/custom-config.yaml
# or with sudo
sudo ./scripts/run.sh --config /path/to/custom-config.yaml
```

### Logging to stdout (useful without sudo)
```bash
LOG_DEST=stdout python src/main.py
```

### Helper Scripts
Use the scripts in `scripts/` for convenience:
- `scripts/run.sh`: Run the application (use with `sudo` for full access)
- `scripts/install.sh`: Install dependencies
- `scripts/reinstall.sh`: Reinstall venv
- `scripts/uninstall.sh`: Uninstall

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

## Project Architecture

### File Structure

```
utm/
├── src/                        # Application Source Code
│   ├── main.py                 # Entry point, initializes Dashboard
│   ├── const.py                # Application constants and paths
│   ├── list_tasks.py           # Standalone CLI for task monitoring
│   ├── collectors/             # Data Collection Modules (Model)
│   │   ├── base.py             # Abstract base class for collectors
│   │   ├── system.py           # CPU, RAM, Disk, Uptime
│   │   ├── services.py         # Systemd services & Docker containers
│   │   ├── network.py          # Interfaces, Ports, Firewall
│   │   ├── tasks.py            # Cron jobs & Systemd timers
│   │   ├── processes.py        # Process management
│   │   ├── users.py            # Active sessions
│   │   └── fail2ban.py         # Fail2ban bans & jails
│   ├── dashboard/              # UI Modules (View/Controller)
│   │   ├── app.py              # Main Textual App class
│   │   ├── style.tcss          # Stylesheet
│   │   └── widgets/            # Individual UI components
│   │       ├── system_info.py  # Top panel
│   │       ├── services.py     # Services tab
│   │       ├── ...
│   └── utils/                  # Shared Utilities
│       └── logger.py           # Logging configuration
├── config/                     # Configuration
│   └── config.yaml             # Main configuration file
├── scripts/                    # Helper Shell Scripts
├── docs/                       # Documentation
├── logs/                       # Application Logs
├── tests/                      # Unit Tests
└── Dockerfile                  # Docker build configuration
```

### Architectural Patterns

- **MVC (Model-View-Controller)**:
    - **Model**: `src/collectors` are responsible for gathering raw data from the system (using `psutil`, `docker` SDK, `systemctl`, etc.).
    - **View**: `src/dashboard/widgets` are the visual components that display the data.
    - **Controller**: `src/dashboard/app.py` acts as the controller, initializing collectors, handling user input (hotkeys), and orchestrating data updates.
- **Template Method**: `BaseCollector` defines the standard `collect()` and `update()` methods that all specific collectors implement.
- **Event-Driven**: The UI is built on `textual`, which is an event-driven framework handling timer ticks for data refresh and user keypresses.

### Dependency Graph

```
src/main.py
  ├── src/const.py
  ├── src/utils/logger.py
  └── src/dashboard/app.py (Textual App)
       ├── src/collectors/ (Data Gathering)
       │    ├── system.py (psutil)
       │    ├── services.py (systemd, docker)
       │    ├── network.py (psutil)
       │    ├── tasks.py (croniter, dateutil)
       │    ├── processes.py (psutil)
       │    ├── users.py (psutil)
       │    └── fail2ban.py (fail2ban-client)
       └── src/dashboard/widgets/ (UI Components)
            ├── system_info.py
            ├── services.py
            ├── fail2ban.py, fail2ban_plus.py
            └── ...
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

## Requirements

- Python 3.10+
- Linux system (tested on Ubuntu/Debian)
- Systemd (for service monitoring)
- Docker (optional, for container monitoring)
- Fail2ban (optional, for intrusion detection monitoring)

## Dependencies

- `textual` - TUI framework
- `rich` - Terminal formatting
- `psutil` - System info
- `pyyaml` - Config parsing
- `docker` - Docker API (optional)
- `croniter` - Cron parsing
- `python-dateutil` - Date utilities
- `pytest` - Testing (dev)

## Development

### Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Setup pre-commit hooks
pre-commit install
```

### Pre-commit Hooks

The project uses pre-commit to run checks before each commit:
- **black** - Code formatting
- **isort** - Import sorting
- **flake8** - Linting
- **bandit** - Security checks

```bash
# Run manually on all files
pre-commit run --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

### Testing

```bash
pytest tests/ -v
pytest tests/ -v --cov=src --cov-report=term-missing
```

## License

MIT

## Author

Created for convenient home server management.
