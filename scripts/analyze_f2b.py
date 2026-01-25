#!/usr/bin/env python3
import re
import os
import gzip
import glob
import argparse
import json
from datetime import datetime
from collections import defaultdict
import statistics

# Настройки
LOG_FILES = "/var/log/fail2ban.log*"
ANALYSIS_WINDOW = 86400 * 7  # Недельное окно
MIN_ATTEMPTS = 3
MIN_INTERVAL = 600

# Regex: [jail] Found/Ban IP
LOG_PATTERN = re.compile(r'\[([a-zA-Z0-9_-]+)\]\s+(Found|Ban)\s+([0-9a-f.:]+)')

def parse_date(date_str):
    try:
        return datetime.strptime(date_str.split(',')[0], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None

def process_file(filepath, ip_stats):
    print(f"Reading {filepath}...", flush=True)
    opener = gzip.open if filepath.endswith('.gz') else open
    
    try:
        with opener(filepath, 'rt', encoding='utf-8', errors='ignore') as f:
            for line in f:
                match = LOG_PATTERN.search(line)
                if match:
                    timestamp_str = line[:23] 
                    jail, action, ip = match.groups()
                    dt = parse_date(timestamp_str)
                    if not dt: continue
                    
                    if ip not in ip_stats:
                        ip_stats[ip] = {'found': [], 'bans': 0, 'jails': set(), 'first_seen': dt, 'last_seen': dt}
                    
                    if dt < ip_stats[ip]['first_seen']: ip_stats[ip]['first_seen'] = dt
                    if dt > ip_stats[ip]['last_seen']: ip_stats[ip]['last_seen'] = dt
                    
                    ip_stats[ip]['jails'].add(jail)
                    
                    if action == 'Found':
                        ip_stats[ip]['found'].append(dt)
                    elif action == 'Ban':
                        ip_stats[ip]['bans'] += 1
    except Exception as e:
        print(f"Error reading {filepath}: {e}")

def format_duration(seconds):
    if seconds < 60: return f"{int(seconds)}s"
    if seconds < 3600: return f"{int(seconds/60)}m"
    if seconds < 86400: return f"{int(seconds/3600)}h"
    return f"{int(seconds/86400)}d"

def analyze():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true', help='Output JSON to cache')
    args = parser.parse_args()

    files = sorted(glob.glob(LOG_FILES), reverse=True)
    ip_stats = {}

    for f in files:
        process_file(f, ip_stats)

    candidates = []
    
    for ip, data in ip_stats.items():
        found_times = sorted(data['found'])
        count = len(found_times)
        
        if count < MIN_ATTEMPTS:
            continue

        intervals = []
        for i in range(1, count):
            delta = (found_times[i] - found_times[i-1]).total_seconds()
            if delta < ANALYSIS_WINDOW: 
                intervals.append(delta)

        if not intervals:
            continue

        avg_interval = statistics.mean(intervals)
        duration = (data['last_seen'] - data['first_seen']).total_seconds()
        
        if avg_interval < MIN_INTERVAL:
            continue

        status = "BANNED"
        sort_prio = 0

        if data['bans'] == 0:
            status = "EVASION (ACTIVE)"
            sort_prio = 2
        elif data['bans'] > 0:
            status = "CAUGHT (History)"
            sort_prio = 1

        candidates.append({
            'ip': ip,
            'jail': ",".join(list(data['jails'])[:2]),
            'count': count,
            'bans': data['bans'],
            'avg_int': avg_interval,
            'duration': duration,
            'status': status,
            'prio': sort_prio
        })

    candidates.sort(key=lambda x: (x['prio'], x['count']), reverse=True)

    # Save to JSON if requested
    if args.json:
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        json_path = os.path.join(cache_dir, 'suspicious_ips.json')

        with open(json_path, 'w') as f:
            json.dump(candidates, f)

    # Always print the report table
    print(f"\nAnalyzed {len(ip_stats)} unique IPs.")
    print("\n[SLOW BRUTE-FORCE REPORT]")
    print("-" * 110)
    print(f"{'IP Address':<18} | {'Jail':<15} | {'Found':<5} | {'Bans':<4} | {'Avg Int':<8} | {'Duration':<8} | {'Status'}")
    print("-" * 110)

    for c in candidates:
        avg_str = format_duration(c['avg_int'])
        dur_str = format_duration(c['duration'])

        # Status display (no ANSI colors - will be rendered by RichLog)
        status_display = c['status']

        print(f"{c['ip']:<18} | {c['jail']:<15} | {c['count']:<5} | {c['bans']:<4} | {avg_str:<8} | {dur_str:<8} | {status_display}")

    print("-" * 110)
    print(f"Total Slow Attackers Found: {len(candidates)}")

    if candidates:
        evasion_count = sum(1 for c in candidates if "EVASION" in c['status'])
        if evasion_count:
            print(f"\n⚠ {evasion_count} IPs evading detection - consider banning permanently!")

if __name__ == "__main__":
    analyze()
