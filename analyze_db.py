#!/usr/bin/env python3
"""Test unbanned count logic from header."""
import json

d = json.load(open('data/attacks.db.json'))

print('=== Testing Unbanned Logic ===')
all_ips = d.get('ips', {})

unbanned_count = 0
for ip, data in all_ips.items():
    bans = data.get('bans', {})
    # Unbanned = IPs with bans.total > 0 but not currently active
    if bans.get('total', 0) > 0 and not bans.get('active'):
        unbanned_count += 1

print(f'Unbanned count (bans.total > 0 and not active): {unbanned_count}')

# Check how many have active=True
active_count = 0
for ip, data in all_ips.items():
    bans = data.get('bans', {})
    if bans.get('active'):
        active_count += 1

print(f'Active count (bans.active=True): {active_count}')

# Check how many have bans.total > 0
with_bans_total = 0
for ip, data in all_ips.items():
    bans = data.get('bans', {})
    if bans.get('total', 0) > 0:
        with_bans_total += 1

print(f'IPs with bans.total > 0: {with_bans_total}')
