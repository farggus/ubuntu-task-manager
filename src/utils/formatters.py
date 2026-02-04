"""Formatting utilities for UI display."""

from datetime import datetime, timedelta

from rich.text import Text

from const import ORG_DISPLAY_MAX_LEN, SECONDS_IN_DAY, SECONDS_IN_HOUR, SECONDS_IN_MINUTE, SECONDS_IN_YEAR


def format_attempts(attempts: int) -> Text:
    """Format attempts count with color coding.

    Args:
        attempts: Number of attempts

    Returns:
        Rich Text object with appropriate styling
    """
    text = Text(str(attempts))
    if attempts >= 100:
        text.style = "bold red"
    elif attempts >= 20:
        text.style = "yellow"
    return text


def format_bantime(seconds: int) -> str:
    """Format bantime as human readable with expiry date.

    Args:
        seconds: Ban duration in seconds

    Returns:
        Formatted string like "7d (til 25.01.26)", "3Y (til 26.01.29)" or "-" if no ban
    """
    if seconds <= 0:
        return "-"

    expiry = datetime.now() + timedelta(seconds=seconds)
    expiry_str = expiry.strftime("%d.%m.%y")

    if seconds >= SECONDS_IN_YEAR:
        years = seconds // SECONDS_IN_YEAR
        return f"{years}Y (til {expiry_str})"
    elif seconds >= SECONDS_IN_DAY:
        days = seconds // SECONDS_IN_DAY
        return f"{days}d (til {expiry_str})"
    elif seconds >= SECONDS_IN_HOUR:
        hours = seconds // SECONDS_IN_HOUR
        return f"{hours}h (til {expiry_str})"
    else:
        mins = seconds // SECONDS_IN_MINUTE
        return f"{mins}m"


def format_org(org: str, max_len: int = ORG_DISPLAY_MAX_LEN) -> str:
    """Truncate organization name if too long.

    Args:
        org: Organization name
        max_len: Maximum display length

    Returns:
        Truncated org name with ellipsis if needed
    """
    if not org or org == "-":
        return "-"
    if len(org) > max_len:
        return org[: max_len - 3] + "..."
    return org


def format_status(status: str) -> Text:
    """Format EVASION/CAUGHT status with colors.

    Args:
        status: Status string (EVASION, CAUGHT, etc.)

    Returns:
        Rich Text object with appropriate styling
    """
    text = Text(status)
    if "EVASION" in status:
        text.style = "bold red"
    elif "CAUGHT" in status:
        text.style = "bold yellow"
    return text


def format_interval(seconds: float) -> str:
    """Format interval as human readable.

    Args:
        seconds: Interval in seconds

    Returns:
        Formatted string like "2h", "30m", or "45s"
    """
    if seconds < SECONDS_IN_MINUTE:
        return f"{int(seconds)}s"
    elif seconds < SECONDS_IN_HOUR:
        return f"{int(seconds // SECONDS_IN_MINUTE)}m"
    else:
        return f"{int(seconds // SECONDS_IN_HOUR)}h"


def format_jail_status(currently_banned: int) -> Text:
    """Format jail status indicator.

    Args:
        currently_banned: Number of currently banned IPs

    Returns:
        Rich Text with ACTIVE (red) or OK (green)
    """
    if currently_banned > 0:
        return Text("ACTIVE", style="bold red")
    return Text("OK", style="green")


def format_banned_count(count: int) -> Text:
    """Format banned count with color coding.

    Args:
        count: Number of banned IPs

    Returns:
        Rich Text object (red if > 0, green otherwise)
    """
    if count > 0:
        return Text(str(count), style="bold red")
    return Text(str(count), style="green")
