"""Binary path resolution for subprocess calls.

This module provides absolute paths to system binaries to improve security
by avoiding PATH-based command resolution (bandit B607).
"""

import shutil
from typing import Optional

# Cache for resolved binary paths
_binary_cache: dict = {}

# Default paths for common binaries (fallback if shutil.which fails)
_DEFAULT_PATHS = {
    'dpkg-query': '/usr/bin/dpkg-query',
    'apt': '/usr/bin/apt',
    'apt-get': '/usr/bin/apt-get',
    'systemctl': '/usr/bin/systemctl',
    'lsblk': '/usr/bin/lsblk',
    'smartctl': '/usr/sbin/smartctl',
    'sudo': '/usr/bin/sudo',
    'ufw': '/usr/sbin/ufw',
    'firewall-cmd': '/usr/bin/firewall-cmd',
    'iptables': '/usr/sbin/iptables',
    'ip': '/usr/sbin/ip',
    'fail2ban-client': '/usr/bin/fail2ban-client',
    'grep': '/usr/bin/grep',
    'tail': '/usr/bin/tail',
    'ps': '/usr/bin/ps',
    'crontab': '/usr/bin/crontab',
    'umount': '/usr/bin/umount',
    'mkdir': '/usr/bin/mkdir',
    'mount': '/usr/bin/mount',
    'which': '/usr/bin/which',
    'cp': '/usr/bin/cp',
    'nft': '/usr/sbin/nft',
}


def get_binary(name: str) -> Optional[str]:
    """Get absolute path to a binary.

    Args:
        name: The binary name (e.g., 'systemctl', 'lsblk')

    Returns:
        Absolute path to the binary, or None if not found
    """
    if name in _binary_cache:
        return _binary_cache[name]

    # Try to find using shutil.which (searches PATH)
    path = shutil.which(name)

    # Fallback to default path if which fails
    if path is None and name in _DEFAULT_PATHS:
        path = _DEFAULT_PATHS[name]

    # Cache the result
    _binary_cache[name] = path
    return path


def get_binary_or_raise(name: str) -> str:
    """Get absolute path to a binary, raising if not found.

    Args:
        name: The binary name

    Returns:
        Absolute path to the binary

    Raises:
        FileNotFoundError: If binary is not found
    """
    path = get_binary(name)
    if path is None:
        raise FileNotFoundError(f"Binary not found: {name}")
    return path


# Convenience constants for commonly used binaries
DPKG_QUERY = get_binary('dpkg-query')
APT = get_binary('apt')
APT_GET = get_binary('apt-get')
SYSTEMCTL = get_binary('systemctl')
LSBLK = get_binary('lsblk')
SMARTCTL = get_binary('smartctl')
SUDO = get_binary('sudo')
UFW = get_binary('ufw')
FIREWALL_CMD = get_binary('firewall-cmd')
IPTABLES = get_binary('iptables')
IP = get_binary('ip')
FAIL2BAN_CLIENT = get_binary('fail2ban-client')
GREP = get_binary('grep')
TAIL = get_binary('tail')
PS = get_binary('ps')
CRONTAB = get_binary('crontab')
UMOUNT = get_binary('umount')
MKDIR = get_binary('mkdir')
MOUNT = get_binary('mount')
WHICH = get_binary('which')
CP = get_binary('cp')
NFT = get_binary('nft')
