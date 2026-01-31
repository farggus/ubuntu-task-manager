import pytest
from unittest.mock import patch

from collectors.services import ServicesCollector


@pytest.fixture
def collector():
    return ServicesCollector({})


def test_list_all_services(collector):
    """Test parsing of systemctl list-units output."""
    # Mock subprocess output for 'systemctl list-units'
    # Format: UNIT LOAD ACTIVE SUB DESCRIPTION
    mock_output = (
        "ssh.service loaded active running OpenBSD Secure Shell server\n"
        "nginx.service loaded active running A high performance web server"
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = mock_output
        mock_run.return_value.returncode = 0

        services = collector._list_all_services()

        assert len(services) == 2
        assert services[0]['name'] == 'ssh'
        assert services[0]['state'] == 'running'  # The 4th column in standard output is SUB, 3rd is ACTIVE.
        # Wait, let's check collectors/services.py logic.
        # parts = line.split(None, 4)
        # parts[0]=name, parts[1]=load, parts[2]=active, parts[3]=sub/state

        # My mock string: "ssh.service loaded active running ..."
        # parts: ['ssh.service', 'loaded', 'active', 'running', 'OpenBSD...']
        # code: 'state': parts[3] -> 'running'

        assert services[0]['state'] == 'running'
        assert services[1]['description'] == 'A high performance web server'


def test_get_service_info_success(collector):
    """Test parsing of systemctl show output."""
    mock_output = (
        "ActiveState=active\n"
        "SubState=running\n"
        "LoadState=loaded\n"
        "Description=My Service\n"
        "MainPID=1234\n"
        "MemoryCurrent=1024\n"
        "CPUUsageNSec=5000"
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = mock_output
        mock_run.return_value.returncode = 0

        info = collector._get_service_info("myservice")

        assert info['state'] == 'active'
        assert info['sub_state'] == 'running'
        assert info['pid'] == '1234'
        assert info['name'] == 'myservice'


def test_get_service_info_error(collector):
    """Test error handling when systemctl fails."""
    with patch("subprocess.run", side_effect=Exception("Command failed")):
        info = collector._get_service_info("badservice")
        assert "error" in info
        assert "Command failed" in info['error']
