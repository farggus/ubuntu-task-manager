"""Processes collector."""

import psutil
import datetime
from typing import Dict, Any, List
from .base import BaseCollector
from utils.logger import get_logger

logger = get_logger("processes_collector")


class ProcessesCollector(BaseCollector):
    """Collects detailed information about running processes."""

    def collect(self) -> Dict[str, Any]:
        """Collect processes information and statistics."""
        processes = self._get_processes()
        
        stats = {
            'total': len(processes),
            'running': 0,
            'sleeping': 0,
            'zombies': 0,
            'other': 0
        }
        
        for p in processes:
            status = p.get('status')
            
            # Use if/elif/else to prevent double counting
            if status == psutil.STATUS_RUNNING or (p.get('cpu', 0.0) > 0.0 and status == psutil.STATUS_SLEEPING):
                stats['running'] += 1
            elif status == psutil.STATUS_SLEEPING:
                stats['sleeping'] += 1
            elif status == psutil.STATUS_ZOMBIE:
                stats['zombies'] += 1
            else:
                stats['other'] += 1

        return {
            'processes': processes,
            'stats': stats
        }

    def _get_processes(self) -> List[Dict[str, Any]]:
        """Get list of running processes."""
        processes = []
        try:
            # Fetch all useful attributes at once
            attrs = [
                'pid', 'name', 'username', 'status', 
                'cpu_percent', 'memory_percent', 'memory_info',
                'create_time', 'cmdline', 'ppid'
            ]
            
            for p in psutil.process_iter(attrs):
                try:
                    p_info = p.info
                    
                    # Format time
                    create_time = datetime.datetime.fromtimestamp(p_info['create_time'])
                    time_str = create_time.strftime("%H:%M:%S")
                    
                    # Format command
                    cmd = " ".join(p_info['cmdline']) if p_info['cmdline'] else p_info['name']
                    
                    # Memory in MB
                    mem_mb = (p_info['memory_info'].rss / 1024 / 1024) if p_info['memory_info'] else 0
                    
                    # Try to get parent name (might be expensive for all, but useful)
                    parent_name = '?'
                    if p_info['ppid']:
                        try:
                            parent = psutil.Process(p_info['ppid'])
                            parent_name = parent.name()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass

                    processes.append({
                        'pid': p_info['pid'],
                        'name': p_info['name'],
                        'user': p_info['username'] or 'unknown',
                        'status': p_info['status'],
                        'cpu': p_info['cpu_percent'] or 0.0,
                        'mem_pct': p_info['memory_percent'] or 0.0,
                        'mem_mb': mem_mb,
                        'time': time_str,
                        'command': cmd,
                        'ppid': p_info['ppid'],
                        'parent_name': parent_name
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                    
        except Exception as e:
            self.errors.append(f"Error listing processes: {e}")
            
        # Sort by CPU usage descending by default
        return sorted(processes, key=lambda x: x['cpu'], reverse=True)

    def _get_summary(self) -> Dict[str, int]:
        """Get process summary counts."""
        summary = {'total': 0, 'running': 0, 'sleeping': 0, 'stopped': 0, 'zombie': 0}
        try:
            for p in psutil.process_iter(['status']):
                status = p.info['status']
                summary['total'] += 1
                if status in summary:
                    summary[status] += 1
        except:
            pass
        return summary
