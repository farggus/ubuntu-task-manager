# Quick Start

## Installation in 3 Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

Or with a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. (Optional) Configure config.yaml
Edit `config.yaml` and add your services for monitoring:

```yaml
services:
  specific_services:
    - nginx          # your web server
    - postgresql     # your database
    - docker         # if using Docker
    # add your services here
```

### 3. Run Dashboard
```bash
python main.py
```

or

```bash
./main.py
```

## Controls

- **q** - Quit
- **r** - Manual refresh
- **Ctrl+C** - Quit

## What's Next?

### Add to Autostart
Create an alias in `.bashrc` or `.zshrc`:
```bash
echo "alias utm='cd /path/to/utm && ./main.py'" >> ~/.bashrc
```

Now you can start it with the `utm` command.

### Run with sudo (for full info)
Some data requires root privileges:
```bash
sudo python main.py
```

### Configure sudo without password
Add to `/etc/sudoers.d/utm`:
```
youruser ALL=(ALL) NOPASSWD: /path/to/utm/main.py
```

## Troubleshooting?

### Docker not showing
- Ensure Docker is installed: `docker --version`
- Check user is in docker group: `groups`
- Install library: `pip install docker`

### No port/firewall info
- Run with sudo: `sudo python main.py`

### "Module not found" error
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check if you are in the virtual environment (if using one)

## Extension

- See `EXAMPLES.md` for custom collector examples
- See `README.md` for full documentation