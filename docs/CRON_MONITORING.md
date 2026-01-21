# Detailed Cron and Scheduled Tasks Monitoring

## Features

The system collects **ALL** scheduled tasks from all sources:

### Cron Jobs
- ✅ **All users** - crontab of every user in the system
- ✅ **/etc/crontab** - system crontab
- ✅ **/etc/cron.d/** - all files in cron.d directory
- ✅ **/etc/cron.hourly/** - scripts executed hourly
- ✅ **/etc/cron.daily/** - scripts executed daily
- ✅ **/etc/cron.weekly/** - scripts executed weekly
- ✅ **/etc/cron.monthly/** - scripts executed monthly

### Detailed Information for Each Task

For each cron job, the following is displayed:

- **User** - who executes the task
- **Schedule** - human-readable description (e.g., "Daily at 6:25 AM")
- **Next Run** - exact date and time of the next execution
- **Time Until Run** - "in 2h 15m", "in 5d 3h", etc.
- **Command** - what exactly is executed
- **Source** - where the task is taken from (user:root, /etc/crontab, /etc/cron.d/backup, etc.)
- **Line Number** - for quick search in the file

### Systemd Timers

- All timers in the system (enabled/disabled)
- What they trigger
- Next run
- Last run
- Timer description

### Anacron

- All anacron tasks
- Execution period
- Delay
- Commands

## Usage

### 1. In Dashboard (TUI)

```bash
./run.sh
```

The dashboard shows the first 10 cron tasks with main info:
- User
- Schedule (human-readable)
- Next Run
- Command

### 2. Detailed View of All Tasks (CLI)

To view **ALL** tasks use:

```bash
python list_tasks.py
```

or

```bash
./list_tasks.py
```

This command will show **full** tables with all tasks:

```
╭─ Cron Jobs Summary ─────────────────────╮
│ Total Cron Jobs: 24                     │
│ By Source:                              │
│   • user:root: 5                        │
│   • /etc/cron.daily: 12                 │
│   • /etc/cron.d/backup: 3               │
│   • user:postgres: 4                    │
╰─────────────────────────────────────────╯

┏━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ User     ┃ Source        ┃ Schedule           ┃ Next Run       ┃ Command              ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ root     │ user:root     │ Daily at 2:00 AM   │ 2026-01-11     │ /opt/backup.sh       │
│          │               │                    │ 02:00:00       │                      │
│          │               │                    │ in 5h 23m      │                      │
├──────────┼───────────────┼────────────────────┼────────────────┼──────────────────────┤
│ postgres │ user:postgres │ Every hour         │ 2026-01-10     │ pg_dump mydb > ...   │
│          │               │                    │ 21:00:00       │                      │
│          │               │                    │ in 23m         │                      │
└──────────┴───────────────┴────────────────────┴────────────────┴──────────────────────┘
```

### 3. Viewing with sudo (all users)

Some crontabs may require sudo for access:

```bash
sudo python list_tasks.py
```

## How It Works

### Parsing Cron Expressions

The system understands:
- **Standard expressions**: `30 2 * * *` → "at 2:30"
- **Special**: `@daily`, `@hourly`, `@reboot`, etc.
- **Intervals**: `*/5 * * * *` → "every 5 minutes"
- **Lists**: `0 9,17 * * *` → "at 9:00 and 17:00"
- **Ranges**: `0 9-17 * * *` → "at hours 9-17"

### Next Run Calculation

Uses `croniter` library for precise calculation:
- Accounts for current time
- Correctly handles months with different number of days
- Accounts for leap years
- Shows human-readable time until run

### Data Sources

#### User crontabs
For each user in `/etc/passwd` the system attempts to execute:
```bash
crontab -l -u username
```

#### System crontabs
- Reads `/etc/crontab` considering format with user field
- Scans all files in `/etc/cron.d/`
- Finds scripts in `/etc/cron.{hourly,daily,weekly,monthly}/`

#### Systemd timers
```bash
systemctl list-timers --all
systemctl show timer-name
```

## Task Examples

### Daily Backup at 2 AM
```
0 2 * * * /opt/backup.sh
```
Displayed as: "Daily at 2:00 AM"

### Every 5 Minutes
```
*/5 * * * * /usr/bin/check_service.sh
```
Displayed as: "every 5 minutes"

### Mondays at 9:00
```
0 9 * * 1 /usr/local/bin/weekly_report.sh
```
Displayed as: "at 9:00 on Mon"

### First Day of Every Month
```
0 0 1 * * /usr/local/bin/monthly_cleanup.sh
```
Displayed as: "at 0:00 on day 1"

### Special Schedule
```
@reboot /usr/local/bin/startup.sh
@daily /usr/local/bin/daily_job.sh
@hourly /usr/local/bin/hourly_check.sh
```

## Filtering and Search

### Find all tasks for a specific user
```bash
python list_tasks.py | grep "user:postgres"
```

### Find tasks executed at night
```bash
python list_tasks.py | grep -E "(0[0-5]:[0-9]{2}|at [0-5]:[0-9]{2})"
```

### Export to file
```bash
python list_tasks.py > all_cron_tasks.txt
```

## Troubleshooting

### Some user crontabs are not shown
**Problem**: Access denied to other users' crontabs
**Solution**: Run with sudo:
```bash
sudo python list_tasks.py
```

### "Install croniter" Error
**Problem**: croniter library is not installed
**Solution**:
```bash
pip install croniter python-dateutil
```
or
```bash
./install.sh
```

### System crontabs are not shown
**Problem**: No read permission for `/etc/crontab` or `/etc/cron.d/`
**Solution**: Run with sudo

## Alerting Integration

You can create a script to monitor "forgotten" or inactive tasks:

```python
from collectors import TasksCollector
from datetime import datetime, timedelta

collector = TasksCollector()
data = collector.update()

# Find tasks that haven't run for more than a week
week_ago = datetime.now() - timedelta(days=7)

for timer in data['systemd_timers']['timers']:
    last_trigger = timer.get('last_trigger')
    if last_trigger != 'never':
        # Check last run date logic here...
        pass
```

## Extension

### Add Ignored Tasks
Edit `config.yaml`:
```yaml
tasks:
  ignore_users:
    - systemd-timesync
    - _apt
  ignore_patterns:
    - ".*test.*"
    - ".*tmp.*"
```

### Add alerting on specific tasks
Create a custom script:

```python
from collectors import TasksCollector

def check_critical_jobs():
    collector = TasksCollector()
    data = collector.update()

    critical_jobs = [
        'backup.sh',
        'postgres_dump.sh',
        'health_check.sh'
    ]

    all_commands = [j['command'] for j in data['cron']['all_jobs']]

    for critical in critical_jobs:
        found = any(critical in cmd for cmd in all_commands)
        if not found:
            print(f"WARNING: Critical job '{critical}' not found!")
```
