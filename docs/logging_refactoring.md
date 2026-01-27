# Fail2Ban Logging Refactoring

## Changes Made

### Goal
Migrate Fail2Ban debug logs to proper logging levels (DEBUG/INFO/WARNING) instead of using INFO with `[BAN DEBUG]` prefix.

### Modified Files
1. `src/collectors/fail2ban.py` - Fail2Ban data collector
2. `src/dashboard/widgets/fail2ban.py` - Fail2Ban UI widget

## New Logging Structure

### DEBUG (detailed steps)
```python
logger.debug("Starting Fail2Ban data collection")
logger.debug(f"Processed jail '{jail_name}' in {duration:.3f}s")
logger.debug("IP validation passed for {ip}")
```

**When to use:**
- Operation start (without timing)
- Processing individual items (jails, IPs)
- Intermediate steps

### INFO (important events)
```python
logger.info(f"Banning IP {ip} in jail '{jail}'")
logger.info(f"Fail2Ban collection completed: {total_banned} banned IPs, ...")
logger.info(f"Successfully banned IP {ip} in {time:.2f}s")
```

**When to use:**
- User actions (ban/unban)
- Operation summaries with metrics
- Successful completion of important operations

### WARNING (slow operations)
```python
if duration > 5.0:
    logger.warning(f"Slow jail processing: '{jail_name}' took {duration:.2f}s")
if duration > 10.0:
    logger.warning(f"Slow collector update took {duration:.2f}s")
```

**When to use:**
- Operations > 5 seconds (jail processing)
- Operations > 10 seconds (collector update)
- Unexpected situations

### ERROR (errors)
```python
logger.error(f"Invalid IP address for ban: {ip}")
logger.error(f"Failed to ban IP {ip}: {e}")
```

**When to use:**
- Invalid input data
- Exceptions and execution errors

## Usage

### Default (production)
```bash
python src/main.py
```
**Result:** Only INFO, WARNING, ERROR logs (no DEBUG)

### With debugging (development)
```bash
python src/main.py --debug
```
**Result:** All log levels (DEBUG, INFO, WARNING, ERROR)

### Output Examples

**Without `--debug`:**
```
2026-01-27 20:35:05 - INFO - [utm.fail2ban_collector] - Fail2Ban collection completed: 185 banned IPs, 7 jails, duration=42.89s
2026-01-27 20:35:10 - INFO - [utm.fail2ban_tab] - Banning IP 192.168.1.100 in jail 'recidive'
2026-01-27 20:35:11 - INFO - [utm.fail2ban_collector] - Successfully banned IP 192.168.1.100 in 0.85s
```

**With `--debug`:**
```
2026-01-27 20:35:05 - DEBUG - [utm.fail2ban_collector] - Starting Fail2Ban data collection
2026-01-27 20:35:05 - DEBUG - [utm.fail2ban_collector] - fail2ban-client status executed in 0.123s
2026-01-27 20:35:05 - DEBUG - [utm.fail2ban_collector] - Found 7 active jails: ['recidive', 'sshd', 'samba', ...]
2026-01-27 20:35:18 - WARNING - [utm.fail2ban_collector] - Slow jail processing: 'recidive' took 12.86s
2026-01-27 20:35:29 - WARNING - [utm.fail2ban_collector] - Slow jail processing: 'sshd' took 10.95s
2026-01-27 20:35:46 - WARNING - [utm.fail2ban_collector] - Slow unban history parsing took 17.67s
2026-01-27 20:35:47 - INFO - [utm.fail2ban_collector] - Fail2Ban collection completed: 185 banned IPs, 7 jails, duration=42.89s
```

## Benefits

✅ **Standard Python practice** - using built-in logging levels
✅ **Easy control** - enable/disable via `--debug` flag
✅ **Clean logs** - removed redundant `[BAN DEBUG]` prefix
✅ **Automatic warnings** - slow operations highlighted with WARNING
✅ **Compatibility** - works with all standard logging tools

## Backward Compatibility

All changes are fully backward compatible:
- Existing configs work without modifications
- No changes required to startup scripts
- Default behavior unchanged
