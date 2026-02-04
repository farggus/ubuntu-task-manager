# Contributing to Ubuntu Task Manager (UTM)

Thank you for your interest in contributing to UTM! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.10+
- Linux system (Ubuntu/Debian recommended)
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/farggus/ubuntu-task-manager.git
cd ubuntu-task-manager

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Setup pre-commit hooks
pre-commit install
```

### Running the Application

```bash
# Standard run
python src/main.py

# With sudo (for full functionality)
sudo ./scripts/run.sh

# With custom config
python src/main.py --config /path/to/config.yaml
```

## Code Style

We use the following tools to maintain code quality:

| Tool | Purpose | Config File |
|------|---------|-------------|
| **flake8** | Linting | `.flake8` |
| **isort** | Import sorting | `pyproject.toml` |
| **black** | Code formatting | `pyproject.toml` |
| **mypy** | Type checking | `pyproject.toml` |
| **bandit** | Security linting | `pyproject.toml` |

### Style Guidelines

- **Line length**: 120 characters max
- **Imports**: Use `isort` with `black` profile
- **Type hints**: Required for public methods
- **Docstrings**: Required for classes and public methods

### Language Requirements

> **IMPORTANT**: All code, comments, documentation, commit messages, and PR descriptions **MUST** be written in **English**.

This is an international open-source project. Using English ensures:
- ✅ All contributors can understand and review code
- ✅ Documentation is accessible worldwide
- ✅ Issue discussions are inclusive
- ✅ The project maintains professional standards

**What must be in English:**
- ✅ Code comments (`# This is correct`)
- ✅ Docstrings (function/class documentation)
- ✅ Variable and function names (`get_user_data` not `получить_данные_пользователя`)
- ✅ Log messages (`logger.info("User logged in")`)
- ✅ Documentation files (README, CONTRIBUTING, etc.)
- ✅ Commit messages (`feat: add user authentication`)
- ✅ Issues and Pull Request titles/descriptions
- ✅ Code reviews and comments

**Example - Correct:**
```python
def get_jail_info(jail_name: str) -> Optional[Dict[str, Any]]:
    """Get detailed information about a specific jail.
    
    Args:
        jail_name: Name of the fail2ban jail
        
    Returns:
        Dictionary with jail information or None if not found
    """
    logger.debug(f"Processing jail '{jail_name}'")
    # Check if jail exists
    if not jail_name:
        return None
    return jail_data
```

### Pre-commit Hooks

We use pre-commit to automatically run checks before each commit:

```bash
# Install hooks (one-time setup)
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

Pre-commit runs: black, isort, flake8, bandit, and general checks (trailing whitespace, YAML/JSON validation).

### Running Linters Manually

```bash
# Run all linters
flake8 src/
isort --check-only src/
mypy src/

# Auto-fix imports
isort src/

# Auto-format code
black src/
```

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_services.py -v
```

### Writing Tests

- Place tests in `tests/` directory
- Use `pytest` fixtures for common setup
- Mock external dependencies (subprocess, network calls)
- Test file naming: `test_<module>.py`

Example:
```python
import pytest
from collectors.system import SystemCollector

class TestSystemCollector:
    def test_cpu_info(self):
        collector = SystemCollector()
        data = collector.collect()
        assert 'cpu' in data
        assert data['cpu']['total_cores'] > 0
```

## Project Structure

```
src/
├── main.py              # Entry point
├── const.py             # Constants
├── collectors/          # Data collection (Model)
│   ├── base.py          # Abstract base class
│   ├── system.py        # CPU, RAM, Disk
│   ├── services.py      # Systemd, Docker
│   ├── network.py       # Network, Fail2ban
│   ├── tasks.py         # Cron, Timers
│   ├── processes.py     # Processes
│   └── users.py         # Users
├── dashboard/           # UI (View/Controller)
│   ├── app.py           # Main Textual App
│   └── widgets/         # Tab widgets
└── utils/               # Utilities
    └── logger.py        # Logging setup
```

## Adding New Features

### Adding a New Collector

1. Create `src/collectors/my_collector.py`:

```python
from typing import Any, Dict
from .base import BaseCollector

class MyCollector(BaseCollector):
    """Collects my custom data."""

    def collect(self) -> Dict[str, Any]:
        return {
            'my_data': self._get_my_data()
        }

    def _get_my_data(self) -> dict:
        # Implementation
        pass
```

2. Add to `src/collectors/__init__.py`:

```python
from .my_collector import MyCollector
__all__ = [..., 'MyCollector']
```

3. Create corresponding widget in `src/dashboard/widgets/`

4. Register in `src/dashboard/app.py`

### Adding a New Widget

1. Create `src/dashboard/widgets/my_widget.py`:

```python
from textual.widgets import Static

class MyWidget(Static):
    def __init__(self, collector):
        super().__init__()
        self.collector = collector

    def compose(self):
        # Build UI
        yield ...

    def update_data(self):
        data = self.collector.get_data()
        # Update display
```

## Pull Request Process

### Before Submitting

1. **Run pre-commit**: `pre-commit run --all-files` (runs linters + security checks)
2. **Run tests**: `pytest tests/ -v`
3. **Update documentation** if needed

### PR Guidelines

- Create feature branch from `main`
- Use descriptive commit messages (Conventional Commits)
- Keep PRs focused on a single feature/fix
- Include tests for new functionality
- Update README.md if adding user-facing features

### Commit Message Format

```
<type>: <description>

[optional body]
```

Types:
- `Feat`: New feature
- `Fix`: Bug fix
- `Docs`: Documentation
- `Refactor`: Code refactoring
- `Test`: Adding tests
- `CI`: CI/CD changes
- `Perf`: Performance improvements
- `Security`: Security fixes

Example:
```
Feat: Add memory usage sparkline to system panel

- Add sparkline widget for memory history
- Store last 60 data points
- Update every 5 seconds
```

## Security

- **Never** use `shell=True` in subprocess calls
- **Always** validate user input and external data
- Use `ipaddress` module for IP validation
- Report security issues privately to maintainers

## Getting Help

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones
- Use discussions for questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
