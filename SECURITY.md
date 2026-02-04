# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in UTM (Ubuntu Task Manager), please report it responsibly.

### How to Report

1. **Do NOT** create a public GitHub issue for security vulnerabilities
2. Send an email to the repository owner with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

### What to Expect

- Acknowledgment within 48 hours
- Status update within 7 days
- Fix timeline depends on severity:
  - **Critical**: 24-48 hours
  - **High**: 7 days
  - **Medium**: 30 days
  - **Low**: Next release

## Security Considerations

UTM runs with elevated privileges (sudo) to access system information. The following security measures are in place:

### Input Validation
- IP addresses validated via `ipaddress` module before use in subprocess calls
- No `shell=True` in subprocess calls (prevents command injection)

### File Operations
- Atomic writes (temp file + rename) for cache files
- JSON-only data storage (no pickle/eval)

### External Commands
- Absolute paths for all binaries (`/usr/bin/systemctl`, not `systemctl`)
- Hardcoded command arguments (no user input in commands)

### Known Limitations
- Requires root/sudo for full functionality
- Stores IP geolocation data locally (privacy consideration)
- Reads system logs which may contain sensitive information

## Security Tools

The project uses automated security scanning:

```bash
# Run security scan
bandit -r src/ -c pyproject.toml

# Check dependencies
pip-audit
```

## Dependencies

Security-relevant dependencies are regularly updated. Check `requirements.txt` for current versions.
