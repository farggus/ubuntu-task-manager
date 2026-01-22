#!/usr/bin/env python3
"""
List all scheduled tasks with detailed information.
Run this to see ALL cron jobs, systemd timers, and anacron jobs.
"""

import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from collectors import TasksCollector


def main():
    """Main entry point for listing all tasks."""
    console = Console()

    # Load config
    config = {}
    config_path = Path('config.yaml')
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

    console.print("[bold cyan]Collecting all scheduled tasks...[/bold cyan]\n")

    # Collect data
    collector = TasksCollector(config)
    data = collector.update()

    if collector.has_errors():
        console.print(f"[red]Errors occurred:[/red] {collector.errors}")

    # Display Cron Jobs
    display_cron_jobs(console, data.get('cron', {}))

    # Display Systemd Timers
    display_systemd_timers(console, data.get('systemd_timers', {}))

    # Display Anacron Jobs
    display_anacron_jobs(console, data.get('anacron', {}))


def display_cron_jobs(console: Console, cron_data: dict):
    """Display all cron jobs in detail."""
    all_jobs = cron_data.get('all_jobs', [])
    total = cron_data.get('total', 0)
    by_source = cron_data.get('by_source', {})

    if total == 0:
        console.print("[yellow]No cron jobs found[/yellow]\n")
        return

    # Summary
    summary = Text()
    summary.append(f"Total Cron Jobs: {total}", style="bold green")
    if by_source:
        summary.append("\nBy Source: ", style="bold")
        for source, count in by_source.items():
            summary.append(f"\n  • {source}: {count}", style="cyan")

    console.print(Panel(summary, title="[bold]Cron Jobs Summary[/bold]", border_style="green"))
    console.print()

    # Detailed table
    table = Table(show_header=True, header_style="bold magenta", show_lines=True)
    table.add_column("User", style="cyan", width=12)
    table.add_column("Source", style="dim", width=20)
    table.add_column("Schedule", style="yellow", width=30)
    table.add_column("Next Run", style="green", width=20)
    table.add_column("Command", style="white")

    for job in all_jobs:
        user = job.get('user', 'unknown')
        source = job.get('source', 'unknown')

        schedule_info = job.get('schedule', {})
        schedule_human = schedule_info.get('human', 'N/A')

        next_run = job.get('next_run', 'N/A')
        next_run_human = job.get('next_run_human', 'N/A')
        next_run_display = f"{next_run}\n{next_run_human}"

        command = job.get('command', '')

        # Truncate command if very long
        if len(command) > 80:
            command = command[:77] + '...'

        table.add_row(user, source, schedule_human, next_run_display, command)

    console.print(table)
    console.print()


def display_systemd_timers(console: Console, timers_data: dict):
    """Display systemd timers in detail."""
    if timers_data.get('error'):
        console.print(f"[red]Systemd timers error:[/red] {timers_data['error']}\n")
        return

    timers = timers_data.get('timers', [])
    total = timers_data.get('total', 0)
    enabled = timers_data.get('enabled', 0)
    active = timers_data.get('active', 0)

    if total == 0:
        console.print("[yellow]No systemd timers found[/yellow]\n")
        return

    # Summary
    summary = Text()
    summary.append(f"Total Timers: {total}", style="bold green")
    summary.append(f"\nEnabled: {enabled}", style="cyan")
    summary.append(f"\nActive: {active}", style="green")

    console.print(Panel(summary, title="[bold]Systemd Timers Summary[/bold]", border_style="yellow"))
    console.print()

    # Detailed table
    table = Table(show_header=True, header_style="bold magenta", show_lines=True)
    table.add_column("Timer", style="cyan", width=30)
    table.add_column("State", style="yellow", width=12)
    table.add_column("Triggers", style="green", width=25)
    table.add_column("Next Run", style="white", width=15)
    table.add_column("Last", style="dim", width=15)

    for timer in timers:
        name = timer.get('name', 'unknown')
        state = timer.get('state', 'unknown')

        # Color code state
        if 'enabled' in state:
            state_display = f"[green]{state}[/green]"
        elif 'disabled' in state:
            state_display = f"[red]{state}[/red]"
        else:
            state_display = state

        triggers = timer.get('triggers', 'unknown')
        if len(triggers) > 25:
            triggers = triggers[:22] + '...'

        next_run = timer.get('left', 'n/a')
        last = timer.get('last_trigger', 'never')
        if last == 'never' or not last:
            last = 'never'

        table.add_row(name, state_display, triggers, next_run, last)

    console.print(table)
    console.print()


def display_anacron_jobs(console: Console, anacron_data: dict):
    """Display anacron jobs in detail."""
    status = anacron_data.get('status', 'not_installed')

    if status == 'not_installed':
        console.print("[dim]Anacron not installed[/dim]\n")
        return

    if anacron_data.get('error'):
        console.print(f"[red]Anacron error:[/red] {anacron_data['error']}\n")
        return

    jobs = anacron_data.get('jobs', [])
    count = anacron_data.get('count', 0)

    if count == 0:
        console.print("[yellow]No anacron jobs configured[/yellow]\n")
        return

    # Summary
    summary = Text()
    summary.append(f"Total Anacron Jobs: {count}", style="bold green")

    console.print(Panel(summary, title="[bold]Anacron Jobs[/bold]", border_style="blue"))
    console.print()

    # Detailed table
    table = Table(show_header=True, header_style="bold magenta", show_lines=True)
    table.add_column("Period", style="cyan", width=20)
    table.add_column("Delay", style="yellow", width=12)
    table.add_column("Job ID", style="green", width=20)
    table.add_column("Command", style="white")

    for job in jobs:
        period = job.get('period_human', job.get('period', 'unknown'))
        delay = job.get('delay', 'N/A')
        job_id = job.get('job_id', 'unknown')
        command = job.get('command', '')

        if len(command) > 60:
            command = command[:57] + '...'

        table.add_row(period, delay, job_id, command)

    console.print(table)
    console.print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
