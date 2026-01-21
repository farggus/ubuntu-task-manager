# Changelog

## v2.0.0 - Project Renamed to Ubuntu Task Manager (UTM) (2026-01-21)

### Major Changes
- **Project Rename**: Renamed from "HomeServer Inventory" to "Ubuntu Task Manager (UTM)".
- **Localization**: Entire codebase and documentation migrated to English.
- **Refactoring**: Codebase refactored to remove old naming conventions.

### Features
- **Process Management**: Monitor and manage system processes.
- **Service Control**: Start/Stop/Restart systemd services.
- **Container Management**: Docker container monitoring and logs.
- **Network Monitoring**: Interfaces, ports, and firewall rules.
- **Task Scheduling**: Cron jobs and systemd timers monitoring.

### Architecture
- Modular collector system.
- Textual-based TUI.
- Configuration via `config.yaml`.