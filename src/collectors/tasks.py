"""Tasks and scheduled jobs collector with comprehensive cron parsing."""

import subprocess
import shlex
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from .base import BaseCollector
from utils.logger import get_logger

logger = get_logger("tasks_collector")

try:
    from croniter import croniter
    CRONITER_AVAILABLE = True
except ImportError:
    CRONITER_AVAILABLE = False


class TasksCollector(BaseCollector):
    """Collects information about scheduled tasks (cron, systemd timers)."""

    def collect(self) -> Dict[str, Any]:
        """
        Collect tasks information.

        Returns:
            Dictionary with tasks data
        """
        all_cron_data = self._get_all_cron_jobs()

        return {
            'cron': all_cron_data,
            'systemd_timers': self._get_systemd_timers_detailed(),
            'anacron': self._get_anacron_jobs(),
            'summary': self._get_summary(all_cron_data),
        }

    def _get_all_cron_jobs(self) -> Dict[str, Any]:
        """Get ALL cron jobs from all sources."""
        all_jobs = []

        # 1. Get crontabs from all users
        user_crontabs = self._get_all_users_crontabs()
        for user_data in user_crontabs:
            all_jobs.extend(user_data.get('jobs', []))

        # 2. Get system crontabs
        system_crontabs = self._get_system_crontabs()
        for system_data in system_crontabs:
            all_jobs.extend(system_data.get('jobs', []))

        # 3. Get cron.* directories (hourly, daily, weekly, monthly)
        period_jobs = self._get_period_cron_jobs()
        all_jobs.extend(period_jobs)

        # Count by source
        sources = {}
        for job in all_jobs:
            source = job.get('source', 'unknown')
            sources[source] = sources.get(source, 0) + 1

        return {
            'all_jobs': all_jobs,
            'total': len(all_jobs),
            'by_source': sources,
            'user_crontabs': user_crontabs,
            'system_crontabs': system_crontabs,
        }

    def _get_all_users_crontabs(self) -> List[Dict[str, Any]]:
        """Get crontabs for all users in the system."""
        users_with_crontabs = []

        # Get all users from /etc/passwd
        try:
            with open('/etc/passwd', 'r') as f:
                for line in f:
                    parts = line.strip().split(':')
                    if len(parts) >= 3:
                        username = parts[0]
                        uid = int(parts[2])

                        # Try to get crontab for this user
                        user_cron = self._get_user_crontab_for_user(username)
                        if user_cron and user_cron.get('jobs'):
                            users_with_crontabs.append(user_cron)
        except (PermissionError, FileNotFoundError):
            # Fallback to current user only
            current_user_cron = self._get_user_crontab_for_user(os.getenv('USER', 'root'))
            if current_user_cron and current_user_cron.get('jobs'):
                users_with_crontabs.append(current_user_cron)

        return users_with_crontabs

    def _get_user_crontab_for_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get crontab for a specific user."""
        try:
            result = subprocess.run(
                ['crontab', '-l', '-u', username],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                jobs = []
                for line_num, line in enumerate(result.stdout.splitlines(), 1):
                    original_line = line
                    line = line.strip()

                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue

                    # Skip variable definitions
                    if '=' in line and not line.startswith('@'):
                        continue

                    parsed = self._parse_cron_entry(line, username, f'user:{username}', line_num)
                    if parsed:
                        jobs.append(parsed)

                if jobs:
                    return {
                        'user': username,
                        'source': f'user:{username}',
                        'jobs': jobs,
                        'count': len(jobs),
                    }
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError, PermissionError):
            pass

        return None

    def _get_system_crontabs(self) -> List[Dict[str, Any]]:
        """Get system-wide crontabs with full parsing."""
        system_crontabs = []

        # /etc/crontab - system crontab with user field
        crontab_path = Path('/etc/crontab')
        if crontab_path.exists():
            try:
                jobs = []
                with open(crontab_path, 'r') as f:
                    for line_num, line in enumerate(f, 1):
                        original_line = line
                        line = line.strip()

                        if not line or line.startswith('#'):
                            continue

                        # Skip variable definitions
                        if '=' in line:
                            continue

                        # System crontab format: minute hour day month weekday user command
                        parts = line.split(None, 6)
                        if len(parts) >= 7:
                            minute, hour, day, month, weekday, user, command = parts
                            # Reconstruct without user field for parsing
                            cron_line = f"{minute} {hour} {day} {month} {weekday} {command}"
                            parsed = self._parse_cron_entry(cron_line, user, '/etc/crontab', line_num)
                            if parsed:
                                jobs.append(parsed)

                if jobs:
                    system_crontabs.append({
                        'file': '/etc/crontab',
                        'type': 'system',
                        'jobs': jobs,
                        'count': len(jobs),
                    })
            except PermissionError:
                pass

        # /etc/cron.d/ directory
        cron_d_path = Path('/etc/cron.d')
        if cron_d_path.exists() and cron_d_path.is_dir():
            try:
                for cron_file in sorted(cron_d_path.iterdir()):
                    if cron_file.is_file() and not cron_file.name.startswith('.'):
                        jobs = []
                        try:
                            with open(cron_file, 'r') as f:
                                for line_num, line in enumerate(f, 1):
                                    original_line = line
                                    line = line.strip()

                                    if not line or line.startswith('#'):
                                        continue

                                    if '=' in line and not line.startswith('@'):
                                        continue

                                    # Format: minute hour day month weekday user command
                                    parts = line.split(None, 6)
                                    if len(parts) >= 7:
                                        minute, hour, day, month, weekday, user, command = parts
                                        cron_line = f"{minute} {hour} {day} {month} {weekday} {command}"
                                        parsed = self._parse_cron_entry(cron_line, user, str(cron_file), line_num)
                                        if parsed:
                                            jobs.append(parsed)

                            if jobs:
                                system_crontabs.append({
                                    'file': str(cron_file),
                                    'type': 'cron.d',
                                    'jobs': jobs,
                                    'count': len(jobs),
                                })
                        except PermissionError:
                            pass
            except PermissionError:
                pass

        return system_crontabs

    def _get_period_cron_jobs(self) -> List[Dict[str, Any]]:
        """Get jobs from cron.hourly, cron.daily, etc."""
        period_jobs = []

        period_schedules = {
            'hourly': ('0 * * * *', 'Every hour'),
            'daily': ('25 6 * * *', 'Daily at 6:25 AM'),
            'weekly': ('47 6 * * 7', 'Weekly on Sunday at 6:47 AM'),
            'monthly': ('52 6 1 * *', 'Monthly on 1st at 6:52 AM'),
        }

        for period, (cron_expr, human_schedule) in period_schedules.items():
            cron_dir = Path(f'/etc/cron.{period}')
            if cron_dir.exists() and cron_dir.is_dir():
                try:
                    for script_file in sorted(cron_dir.iterdir()):
                        if script_file.is_file() and not script_file.name.startswith('.'):
                            is_executable = os.access(script_file, os.X_OK)

                            next_run, next_run_human = self._get_next_run(cron_expr)

                            period_jobs.append({
                                'command': str(script_file),
                                'script_name': script_file.name,
                                'user': 'root',
                                'source': f'/etc/cron.{period}',
                                'schedule': {
                                    'expression': cron_expr,
                                    'human': human_schedule,
                                    'period': period,
                                },
                                'next_run': next_run,
                                'next_run_human': next_run_human,
                                'executable': is_executable,
                                'raw_entry': f'{human_schedule}: {script_file.name}',
                            })
                except PermissionError:
                    pass

        return period_jobs

    def _parse_cron_entry(self, entry: str, user: str, source: str, line_num: int = 0) -> Optional[Dict[str, Any]]:
        """Parse a single cron entry with full details."""
        try:
            entry = entry.strip()

            # Handle special time strings (@reboot, @daily, etc)
            special_times = {
                '@reboot': ('n/a', 'At system reboot'),
                '@yearly': ('0 0 1 1 *', 'Yearly (January 1st at midnight)'),
                '@annually': ('0 0 1 1 *', 'Annually (January 1st at midnight)'),
                '@monthly': ('0 0 1 * *', 'Monthly (1st day at midnight)'),
                '@weekly': ('0 0 * * 0', 'Weekly (Sunday at midnight)'),
                '@daily': ('0 0 * * *', 'Daily (midnight)'),
                '@midnight': ('0 0 * * *', 'Daily (midnight)'),
                '@hourly': ('0 * * * *', 'Hourly'),
            }

            if entry.startswith('@'):
                special = entry.split(None, 1)
                if len(special) >= 2:
                    special_time = special[0]
                    command = special[1]

                    if special_time in special_times:
                        cron_expr, human_schedule = special_times[special_time]
                        next_run, next_run_human = self._get_next_run(cron_expr) if cron_expr != 'n/a' else ('At reboot', 'At reboot')

                        return {
                            'raw_entry': entry,
                            'line_number': line_num,
                            'schedule': {
                                'expression': cron_expr,
                                'human': human_schedule,
                                'special': special_time,
                            },
                            'command': command,
                            'user': user,
                            'source': source,
                            'next_run': next_run,
                            'next_run_human': next_run_human,
                        }

            # Parse regular cron format: minute hour day month weekday command
            parts = entry.split(None, 5)
            if len(parts) < 6:
                return None

            minute, hour, day, month, weekday, command = parts

            # Build cron expression
            cron_expr = f"{minute} {hour} {day} {month} {weekday}"

            # Calculate next run
            next_run, next_run_human = self._get_next_run(cron_expr)

            # Parse schedule to human readable
            schedule_human = self._cron_to_human(minute, hour, day, month, weekday)

            return {
                'raw_entry': entry,
                'line_number': line_num,
                'schedule': {
                    'minute': minute,
                    'hour': hour,
                    'day': day,
                    'month': month,
                    'weekday': weekday,
                    'expression': cron_expr,
                    'human': schedule_human,
                },
                'command': command,
                'user': user,
                'source': source,
                'next_run': next_run,
                'next_run_human': next_run_human,
            }
        except Exception as e:
            return {
                'raw_entry': entry,
                'command': entry,
                'user': user,
                'source': source,
                'error': f'Parse error: {str(e)}',
            }

    def _get_next_run(self, cron_expr: str) -> tuple:
        """Calculate next run time for a cron expression."""
        if not CRONITER_AVAILABLE:
            return 'Install croniter', 'Install croniter for schedule calculation'

        try:
            base_time = datetime.now()
            cron = croniter(cron_expr, base_time)
            next_run = cron.get_next(datetime)

            # Human readable time difference
            diff = next_run - base_time
            if diff.days > 0:
                human = f"in {diff.days}d {diff.seconds // 3600}h"
            elif diff.seconds >= 3600:
                human = f"in {diff.seconds // 3600}h {(diff.seconds % 3600) // 60}m"
            elif diff.seconds >= 60:
                human = f"in {diff.seconds // 60}m"
            else:
                human = f"in {diff.seconds}s"

            return next_run.strftime('%Y-%m-%d %H:%M:%S'), human
        except Exception as e:
            return 'N/A', f'Error: {str(e)}'

    def _cron_to_human(self, minute: str, hour: str, day: str, month: str, weekday: str) -> str:
        """Convert cron time fields to human readable format."""
        parts = []

        # Special case: all wildcards = every minute
        if minute == '*' and hour == '*' and day == '*' and month == '*' and weekday == '*':
            return "Every minute"

        # Build human readable string
        time_part = ""

        # Minute and hour
        if hour != '*' and minute != '*':
            time_part = f"at {hour}:{minute.zfill(2)}"
        elif hour != '*':
            if '/' in hour:
                parts.append(f"every {hour} hours")
            elif ',' in hour:
                time_part = f"at hours {hour}"
            else:
                time_part = f"at {hour}:00"
        elif minute != '*':
            if '/' in minute:
                interval = minute.split('/')[1]
                parts.append(f"every {interval} minutes")
            elif ',' in minute:
                parts.append(f"at minutes {minute}")
            else:
                parts.append(f"at minute {minute}")

        # Day of month
        if day != '*':
            if '/' in day:
                parts.append(f"every {day.split('/')[1]} days")
            elif ',' in day:
                parts.append(f"on days {day}")
            else:
                parts.append(f"on day {day}")

        # Month
        if month != '*':
            month_names = {
                '1': 'Jan', '2': 'Feb', '3': 'Mar', '4': 'Apr',
                '5': 'May', '6': 'Jun', '7': 'Jul', '8': 'Aug',
                '9': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'
            }
            if month.isdigit() and month in month_names:
                parts.append(f"in {month_names[month]}")
            else:
                parts.append(f"in month {month}")

        # Day of week
        if weekday != '*':
            weekday_names = {
                '0': 'Sun', '1': 'Mon', '2': 'Tue', '3': 'Wed',
                '4': 'Thu', '5': 'Fri', '6': 'Sat', '7': 'Sun'
            }
            if weekday.isdigit() and weekday in weekday_names:
                parts.append(f"on {weekday_names[weekday]}")
            else:
                parts.append(f"on {weekday}")

        if time_part:
            parts.insert(0, time_part)

        return ' '.join(parts) if parts else f"{minute} {hour} {day} {month} {weekday}"

    def _get_systemd_timers_detailed(self) -> Dict[str, Any]:
        """Get systemd timers with detailed information."""
        try:
            # Get active timers
            result = subprocess.run(
                shlex.split("systemctl list-timers --all --no-pager --no-legend"),
                capture_output=True,
                text=True,
                timeout=10
            )

            active_timers_map = {}
            for line in result.stdout.splitlines():
                # Format: NEXT LEFT LAST PASSED UNIT ACTIVATES
                parts = line.split()
                if len(parts) >= 5:
                    # Find UNIT column (usually contains .timer)
                    unit_idx = None
                    for i, part in enumerate(parts):
                        if '.timer' in part:
                            unit_idx = i
                            break

                    if unit_idx and unit_idx >= 4:
                        timer_name = parts[unit_idx]
                        next_time = f"{parts[0]} {parts[1]}" if parts[0] != 'n/a' else 'n/a'
                        left = parts[2]
                        last = f"{parts[3]}" if len(parts) > 3 else 'n/a'

                        active_timers_map[timer_name] = {
                            'next': next_time,
                            'left': left,
                            'last': last,
                        }

            # Get all timer unit files with details
            timer_list_result = subprocess.run(
                shlex.split("systemctl list-unit-files --type=timer --no-pager --no-legend"),
                capture_output=True,
                text=True,
                timeout=10
            )

            timer_details = []
            for line in timer_list_result.stdout.splitlines():
                parts = line.split(None, 1)
                if len(parts) >= 1:
                    timer_name = parts[0]
                    state = parts[1] if len(parts) > 1 else 'unknown'

                    # Get detailed info about this timer
                    show_result = subprocess.run(
                        ['systemctl', 'show', timer_name, '--no-pager'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                    properties = {}
                    if show_result.returncode == 0:
                        for prop_line in show_result.stdout.splitlines():
                            if '=' in prop_line:
                                key, value = prop_line.split('=', 1)
                                properties[key] = value

                    # Get timing info from active timers
                    timing = active_timers_map.get(timer_name, {})

                    timer_details.append({
                        'name': timer_name,
                        'state': state,
                        'triggers': properties.get('Triggers', 'unknown'),
                        'description': properties.get('Description', ''),
                        'next_run': timing.get('next', 'n/a'),
                        'left': timing.get('left', 'n/a'),
                        'last_trigger': timing.get('last', 'never'),
                        'on_calendar': properties.get('OnCalendar', ''),
                        'on_unit_active': properties.get('OnUnitActiveSec', ''),
                    })

            return {
                'timers': timer_details,
                'total': len(timer_details),
                'enabled': sum(1 for t in timer_details if 'enabled' in t.get('state', '')),
                'active': sum(1 for t in timer_details if t.get('next_run', 'n/a') != 'n/a'),
            }
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {'error': 'systemctl command not found or timed out'}

    def _get_anacron_jobs(self) -> Dict[str, Any]:
        """Get anacron jobs."""
        anacrontab_path = Path('/etc/anacrontab')

        if not anacrontab_path.exists():
            return {'jobs': [], 'count': 0, 'status': 'not_installed'}

        try:
            jobs = []
            with open(anacrontab_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    original_line = line
                    line = line.strip()

                    if not line or line.startswith('#'):
                        continue

                    # Skip variable definitions
                    if '=' in line:
                        continue

                    # Format: period delay job-identifier command
                    parts = line.split(None, 3)
                    if len(parts) >= 3:
                        period = parts[0]
                        delay = parts[1]
                        job_id = parts[2]
                        command = parts[3] if len(parts) > 3 else ''

                        # Period in days
                        period_human = f"Every {period} day(s)"
                        if period == '1':
                            period_human = "Daily"
                        elif period == '7':
                            period_human = "Weekly"
                        elif period == '@daily':
                            period_human = "Daily"
                        elif period == '@weekly':
                            period_human = "Weekly"
                        elif period == '@monthly':
                            period_human = "Monthly"

                        jobs.append({
                            'line_number': line_num,
                            'period': period,
                            'period_human': period_human,
                            'delay': f"{delay} min",
                            'job_id': job_id,
                            'command': command,
                            'raw_entry': original_line.strip(),
                        })

            return {
                'jobs': jobs,
                'count': len(jobs),
                'status': 'configured',
            }
        except PermissionError:
            return {'jobs': [], 'count': 0, 'error': 'Permission denied'}

    def _get_summary(self, cron_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary statistics."""
        total_cron = cron_data.get('total', 0)

        return {
            'total_cron_jobs': total_cron,
            'by_source': cron_data.get('by_source', {}),
        }
