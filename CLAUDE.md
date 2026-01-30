# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ubuntu Task Manager (UTM) — a TUI application for monitoring Linux servers. Built with Textual + Rich, requires Python 3.8+.

## Commands

```bash
# Run the application
python src/main.py
python src/main.py --config /path/to/config.yaml
python src/main.py --debug
sudo ./scripts/run.sh                # With full privileges

# Tests
pytest tests/ -v
pytest tests/ -v --cov=src --cov-report=term-missing
pytest tests/test_<module>.py -v     # Specific module

# Linting and formatting
flake8 src/
black src/
isort src/
mypy src/
bandit -r src/ -c pyproject.toml

# Docker
docker-compose up -d
docker attach utm
```

## Architecture

**Pattern: MVC + Event-Driven**

### Collectors (Model) — `src/collectors/`
Base class `BaseCollector` with `collect()` and `update()` methods. Collectors:
- `SystemCollector` — CPU, RAM, disks, uptime
- `ServicesCollector` — systemd services, Docker containers
- `NetworkCollector` — interfaces, ports, firewall
- `Fail2banCollector` — bans, geolocation, whitelist
- `ProcessesCollector`, `TasksCollector`, `UsersCollector`

### Dashboard (Controller) — `src/dashboard/app.py`
`UTMDashboard(App)` — main Textual application class:
- Initializes all collectors
- Manages tabs and hotkeys (Ctrl+Q, Ctrl+R, 0-8)
- Reactive `update_interval` (500ms–60s)

### Widgets (View) — `src/dashboard/widgets/`
Tab widgets: `ProcessesTab`, `ServicesTab`, `Fail2banTab`, `Fail2banPlusTab`, `LoggingTab`, etc.
Each widget has `update_data()` method for UI updates.

### Data Flow
```
main.py → UTMDashboard → Collectors → Widgets
                              ↓
                    get_data() → update_data() → render
```

## Key Files & Directories

- `src/main.py` — entry point
- `src/dashboard/app.py` — main controller
- `src/collectors/` — system data collection
- `src/dashboard/widgets/` — UI components
- `src/database/attacks_db.py` — attacks storage (JSON, thread-safe)
- `src/models/fail2ban.py` — dataclass models (`JailInfo`, `BannedIP`)
- `config/config.yaml` — configuration (intervals, Docker, network)

## Data Storage

- `data/attacks.db.json` — attack history (schema v2.0)
- `cache/bans_db.json` — active bans with geolocation
- `cache/whitelist.json` — IP whitelist
- `logs/utm.log` — application logs (1MB rotation)

## Configuration

YAML config + environment variable overrides:
- `UTM_DOCKER_ENABLED`, `UTM_DOCKER_SOCKET` — Docker settings
- `LOG_FORMAT` (json/text), `LOG_DEST` (file/stdout) — logging

## Code Patterns

**New collector:**
```python
class MyCollector(BaseCollector):
    def collect(self) -> Dict[str, Any]:
        return {'data': self._fetch()}
```

**New widget:**
```python
class MyWidget(Static):
    def __init__(self, collector):
        self.collector = collector
    def update_data(self):
        data = self.collector.get_data()
        # render
```

## External Tools

Called via subprocess (no `shell=True`):
- `systemctl`, `fail2ban-client`, `apt`, `dpkg-query`
- `docker`, `lsblk`, `smartctl`, `iptables`, `netstat`

## Security Notes

- IP validation via `ipaddress` module
- Bandit exceptions in pyproject.toml: B404, B603, B310
- Docker container runs as non-root (uid 1000)

## Style

- Black: line-length=120
- Flake8: max-line-length=120, max-complexity=15
- isort: black profile

## Development Guidelines

### Code & Comments
- Follow standard commenting practices (docstrings for modules, classes, methods)
- All comments must be in English
- All documentation must be in English

### Documentation
- Update documentation when making critical changes or adding new features
- Include documentation updates in task planning
- Keep `docs/CHANGELOG.md` up to date with all notable changes
- Keep `CONTRIBUTING.md` current as development practices evolve

### Testing
- Add tests for new functions, methods, and features
- Run `pytest tests/ -v` before committing

### Git Workflow
- Commit changes regularly with focused, atomic commits
- Avoid multi-task commits — one logical change per commit
- Push changes in a timely manner
- Use descriptive commit messages

### Security
- Never commit credentials, API keys, or tokens
- Keep sensitive files in `.gitignore`: `.env`, `logs/`, `cache/`, `data/`
- Review changes for accidental credential exposure before committing
