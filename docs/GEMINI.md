# Ubuntu Task Manager (UTM) (v2.0)

## Project Overview
**Ubuntu Task Manager (UTM)** is a terminal-based (TUI) application designed for monitoring and managing Ubuntu/Linux servers. It provides real-time visibility into system resources, services, containers, networks, and more, all from a text interface.

### Key Features
*   **System Monitoring:** CPU, RAM, Swap, Disk usage, and temperatures.
*   **Process Management:** View and kill processes (including zombies).
*   **Service Control:** Monitor and manage (start/stop/restart) systemd services.
*   **Docker Integration:** View, start, stop, and inspect logs of Docker containers.
*   **Network & Security:** Monitor interfaces, open ports, and firewall rules.
*   **Package Management:** View installed packages and available updates (apt).
*   **Cron/Task Monitoring:** List and inspect cron jobs and systemd timers.

### Technologies
*   **Language:** Python 3.8+
*   **TUI Framework:** `textual`
*   **UI Styling:** `rich`
*   **System Info:** `psutil`
*   **Container Mgmt:** `docker` (Python SDK)
*   **Config:** `pyyaml`
*   **Testing:** `pytest`

## Architecture

The application follows a modular architecture separating data collection from presentation.

*   **`src/main.py`**: The entry point. Handles argument parsing, logging setup, and initializes the dashboard application.
*   **`config/config.yaml`**: Configuration file for refresh intervals, enabled collectors, and specific service monitoring.
*   **`src/collectors/`**: Contains classes responsible for gathering system data.
    *   `base.py`: Abstract base class for all collectors.
    *   Specific collectors: `system.py`, `services.py`, `network.py`, `tasks.py`, `processes.py`, `users.py`.
*   **`src/dashboard/`**: Contains the Textual application logic and UI components.
    *   `app.py`: Main `App` class (`UTMDashboard`) that manages the layout and screens.
    *   `widgets/`: Individual UI components (widgets) for each tab/section (e.g., `services.py`, `containers.py`).
    *   `style.tcss`: CSS-like styling for the Textual interface.
*   **`src/utils/`**: Helper functions and shared utilities (e.g., logging).

## Setup and Usage

### Installation
The project includes a helper script for installation:
```bash
./scripts/install.sh
```
This script checks for Python 3, creates a virtual environment (`venv`), and installs dependencies from `requirements.txt` and `requirements-dev.txt`.

### Running the Application
To start the dashboard using the helper script:
```bash
./scripts/run.sh
```

Alternatively, manually:
```bash
source venv/bin/activate
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
python src/main.py
```

### Docker Support
A `Dockerfile` is provided for production deployment.
```bash
docker build -t utm .
docker run -it --pid=host -v /var/run/docker.sock:/var/run/docker.sock utm
```

### Configuration
The application looks for `config/config.yaml` relative to the project root. You can specify a custom config path:
```bash
python src/main.py --config /path/to/config.yaml
```

**Environment Variables:**
Configuration can be overridden using environment variables (or a `.env` file):
- `UTM_DOCKER_ENABLED=true`
- `UTM_DOCKER_SOCKET=/var/run/docker.sock`
- `LOG_FORMAT=json` (default: text)
- `LOG_DEST=stdout` (default: file)
- `SENTRY_DSN=...` (for error tracking)

## Development Conventions

*   **Code Style:** Follows standard Python PEP 8 conventions.
*   **Logging:** Uses a custom logger setup (`utils/logger.py`). Configurable for JSON output and stdout.
*   **Testing:** Tests are located in `tests/` and run via `pytest`.
    ```bash
    pytest
    ```
*   **CI/CD:** GitHub Actions workflow (`.github/workflows/ci.yml`) runs tests and security checks (`bandit`) on push.
*   **Dependencies:**
    *   `requirements.txt`: Production dependencies.
    *   `requirements-dev.txt`: Development dependencies (testing, linting).

*   **Extensibility:**
    *   **New Collectors:** Inherit from `collectors.base.BaseCollector` and implement `collect` and `_get_my_data`. Register in `collectors/__init__.py`.
    *   **New Widgets:** Create a Textual `Static` or `Widget` in `dashboard/widgets/` that consumes data from a collector. Add to `dashboard/app.py`.