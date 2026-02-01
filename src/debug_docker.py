# Setup logging for console output
import logging

from rich import print

from collectors.services import ServicesCollector

logging.basicConfig(level=logging.DEBUG)


def debug():
    print("Initializing ServicesCollector...")
    # Emulate config as in config.yaml
    config = {
        'docker': {
            'enabled': True,
            'socket': 'unix:///var/run/docker.sock'
        }
    }

    collector = ServicesCollector(config)

    print("Starting data update...")
    data = collector.collect()

    docker_data = data.get('docker', {})
    print("\n--- Docker Result ---")

    if docker_data.get('error'):
        print(f"ERROR: {docker_data['error']}")

    print(f"Containers found: {docker_data.get('total', 0)}")

    if docker_data.get('containers') is None:
        print("Docker data missing (None)")
    else:
        for c in docker_data['containers']:
            print(f"- {c['name']} ({c['status']}) IP: {c.get('ip_address')}")


if __name__ == "__main__":
    try:
        debug()
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
