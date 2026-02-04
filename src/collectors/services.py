"""Services collector for systemd and Docker."""

import subprocess
from typing import Any, Dict, List, Optional

from utils.binaries import PS, SYSTEMCTL
from utils.logger import get_logger

from .base import BaseCollector

logger = get_logger("services_collector")


class ServicesCollector(BaseCollector):
    """Collects information about systemd services and Docker containers."""

    def collect(self) -> Dict[str, Any]:
        """
        Collect services information.

        Returns:
            Dictionary with services data
        """
        return {
            "systemd": self._get_systemd_services(),
            "docker": self._get_docker_containers() if self.config.get("docker", {}).get("enabled", True) else None,
        }

    def _get_systemd_services(self) -> Dict[str, Any]:
        """Get systemd services information."""
        services = []

        # Get specific services from config or all if monitor_all is True
        monitor_all = self.config.get("services", {}).get("monitor_all", False)
        specific_services = self.config.get("services", {}).get("specific_services", [])

        if monitor_all:
            # Get all services
            services = self._list_all_services()
        elif specific_services:
            # Get specific services
            for service_name in specific_services:
                service_info = self._get_service_info(service_name)
                if service_info:
                    services.append(service_info)

        return {
            "services": services,
            "total": len(services),
            "active": sum(1 for s in services if s.get("active") == "active"),
            "running": sum(1 for s in services if s.get("state") == "running"),
            "failed": sum(1 for s in services if s.get("active") == "failed" or s.get("state") == "failed"),
        }

    def _get_service_users_map(self) -> Dict[str, str]:
        """Get a mapping of service names to users using ps."""
        user_map = {}
        try:
            # List unit and user for all processes
            result = subprocess.run([PS, "-eo", "unit,user", "--no-headers"], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        unit = parts[0]
                        user = parts[1]

                        if unit != "-" and unit.endswith(".service"):
                            service_name = unit.replace(".service", "")
                            # Only store if not already found (prioritize first found?)
                            # or just overwrite. ps might show multiple processes.
                            # Usually the main process is enough.
                            if service_name not in user_map:
                                user_map[service_name] = user
        except Exception as e:
            logger.debug(f"Failed to get service users map: {e}")
        return user_map

    def _list_all_services(self) -> List[Dict[str, Any]]:
        """List all systemd services."""
        try:
            # Get users mapping first
            users_map = self._get_service_users_map()

            result = subprocess.run(
                [SYSTEMCTL, "list-units", "--type=service", "--all", "--no-pager", "--no-legend"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            services = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue

                # Handle bullet points systemd sometimes adds
                if line.startswith("●") or line.startswith("*"):
                    line = line[1:].strip()

                parts = line.split(None, 4)
                if len(parts) >= 4:
                    service_name = parts[0].replace(".service", "")

                    # Filter out obviously bad names
                    if not service_name or service_name in ["●", "*", "-"]:
                        continue

                    # Look up user
                    user = users_map.get(service_name, "")

                    # If active but no user found in ps, likely root (kernel threads or quick tasks)
                    # But better leave empty or 'root?' if unsure. Let's leave empty.

                    services.append(
                        {
                            "name": service_name,
                            "load": parts[1],
                            "active": parts[2],
                            "state": parts[3],
                            "description": parts[4] if len(parts) > 4 else "",
                            "user": user,
                        }
                    )

            return services
        except Exception as e:
            logger.error(f"Failed to list services: {e}")
            return [{"error": f"Failed to list services: {str(e)}"}]

    def _get_service_info(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific service."""
        try:
            # Ensure service name ends with .service
            if not service_name.endswith(".service"):
                service_name += ".service"

            result = subprocess.run(
                [SYSTEMCTL, "show", service_name, "--no-pager"], capture_output=True, text=True, timeout=5
            )

            properties = {}
            for line in result.stdout.splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    properties[key] = value

            return {
                "name": service_name.replace(".service", ""),
                "state": properties.get("ActiveState", "unknown"),
                "sub_state": properties.get("SubState", "unknown"),
                "load_state": properties.get("LoadState", "unknown"),
                "description": properties.get("Description", ""),
                "pid": properties.get("MainPID", "0"),
                "memory": properties.get("MemoryCurrent", "0"),
                "cpu_usage": properties.get("CPUUsageNSec", "0"),
            }
        except Exception as e:
            logger.error(f"Failed to get service info for {service_name}: {e}")
            return {"name": service_name, "error": str(e)}

    def _get_docker_containers(self) -> Optional[Dict[str, Any]]:
        """Get Docker containers information."""
        try:
            import docker

            client = docker.from_env()

            containers = []
            for container in client.containers.list(all=True):
                # Extract IP address
                ip_address = "N/A"
                if container.attrs.get("NetworkSettings", {}).get("Networks"):
                    networks = container.attrs["NetworkSettings"]["Networks"]
                    for net_name, net_info in networks.items():
                        ip = net_info.get("IPAddress")
                        if ip:
                            ip_address = ip
                            break

                stack_name = container.labels.get("com.docker.compose.project", "")

                containers.append(
                    {
                        "id": container.short_id,
                        "name": container.name,
                        "image": container.image.tags[0] if container.image.tags else container.image.short_id,
                        "status": container.status,
                        "state": container.attrs["State"]["Status"],
                        "created": container.attrs["Created"],
                        "ports": container.ports,
                        "labels": container.labels,
                        "ip_address": ip_address,
                        "stack": stack_name,
                    }
                )

            return {
                "containers": containers,
                "total": len(containers),
                "running": sum(1 for c in containers if c["status"] == "running"),
                "stopped": sum(1 for c in containers if c["status"] == "exited"),
            }
        except ImportError:
            logger.debug("Docker library not available")
            return {"error": "Docker library not installed", "error_type": "not_installed"}
        except Exception as e:
            error_str = str(e)
            if "Permission denied" in error_str:
                logger.warning("Docker permission denied")
                return {"error": 'Permission denied (add user to "docker" group)', "error_type": "permission"}
            if "Connection refused" in error_str or "connection refused" in error_str:
                logger.warning("Docker daemon not running")
                return {"error": "Docker daemon not running", "error_type": "not_running"}
            if "FileNotFoundError" in error_str or "No such file" in error_str:
                logger.warning("Docker not installed")
                return {"error": "Docker not installed", "error_type": "not_installed"}
            logger.error(f"Failed to get Docker containers: {e}")
            return {"error": f"Docker error: {error_str}", "error_type": "unknown"}
