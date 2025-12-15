# Deployment (Linux + systemd + GitHub Actions self-hosted runner)

This document describes how to deploy the Taskmanagement App backend to a Linux server using:

- systemd (Gunicorn + Uvicorn workers)
- CI-built wheel artifacts from GitHub Actions
- a self-hosted GitHub Actions runner (behind NAT is fine)

It also includes the required OS-level setup for:

- PDF printing output directory permissions
- USB thermal printer permissions (udev rule)

## 1) Server layout

The deployment workflow assumes the following layout on the server:

- `/opt/taskmanagement-app/`
  - `shared/.env` (environment file, not committed, see .env.example)
  - `venv/` (Python virtualenv used by systemd)
  - `deploy/deploy-wheel.sh` (deployment script invoked by GitHub Actions)

## 2) Create a dedicated service user

```bash
sudo useradd --system --create-home --home-dir /home/taskapp --shell /usr/sbin/nologin taskapp || true
```

Ensure the install directory is owned by `taskapp`:

```bash
sudo mkdir -p /opt/taskmanagement-app
sudo chown -R taskapp:taskapp /opt/taskmanagement-app
```

## 3) Create the production virtualenv

Use Python 3.13 and create a venv:

```bash
sudo -u taskapp python3.13 -m venv /opt/taskmanagement-app/venv
sudo -u taskapp /opt/taskmanagement-app/venv/bin/python -m pip install --upgrade pip
```

Note: the deploy script installs the CI-produced wheel into this venv.

## 4) Environment file

Create `/opt/taskmanagement-app/shared/.env`:

```bash
sudo mkdir -p /opt/taskmanagement-app/shared
sudo nano /opt/taskmanagement-app/shared/.env
```

Guidance:

- Do not commit this file.
- Use `.env.example` in the repo as a reference.
- Do not store secrets in GitHub repo files.

## 5) systemd service

Create `/etc/systemd/system/taskmanagement-app.service`.

Important:

- `WorkingDirectory=/opt/taskmanagement-app` ensures relative paths (like `./output/pdf`) resolve to a writable location under `/opt/taskmanagement-app/`.

Example service unit:

```ini
[Unit]
Description=Taskmanagement App (FastAPI)
After=network.target

[Service]
Type=simple
User=taskapp
Group=taskapp
WorkingDirectory=/opt/taskmanagement-app
EnvironmentFile=/opt/taskmanagement-app/shared/.env
ExecStart=/opt/taskmanagement-app/venv/bin/gunicorn --preload taskmanagement_app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --access-logfile - \
  --error-logfile -
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable taskmanagement-app
sudo systemctl restart taskmanagement-app
sudo systemctl status taskmanagement-app --no-pager
```

## 6) PDF printing: output directory permissions

The default PDF printer config (`config/printers.ini`) uses:

- `output_dir = ./output/pdf`

With the `WorkingDirectory` set as above, this resolves to:

- `/opt/taskmanagement-app/output/pdf`

Create and grant ownership:

```bash
sudo mkdir -p /opt/taskmanagement-app/output/pdf
sudo chown -R taskapp:taskapp /opt/taskmanagement-app/output
```

Alternative:

- Set an absolute path in your server-side `printers.ini` (if you override it), e.g. `output_dir=/opt/taskmanagement-app/output/pdf`.

## 7) USB printing: permissions (udev rule)

If the API returns an error like:

- `Access denied (insufficient permissions)`

…it means the service user cannot open the USB device node.

### 7.1 Confirm vendor/product IDs

```bash
lsusb
```

For the GDMicroelectronics micro-printer the IDs are:

- `28e9:0289`

### 7.2 Add a udev rule

Create `/etc/udev/rules.d/99-gdmicro-printer.rules`:

```bash
sudo tee /etc/udev/rules.d/99-gdmicro-printer.rules > /dev/null <<'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="28e9", ATTR{idProduct}=="0289", MODE="0660", GROUP="taskapp"
EOF
```

Reload rules and replug the printer:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
# unplug/replug the printer
sudo systemctl restart taskmanagement-app
```

## 8) GitHub Actions: CI wheel artifact + self-hosted deploy runner

The repository has two workflows:

- `.github/workflows/ci.yml`
  - runs checks and builds a wheel
  - uploads the wheel as an artifact named `wheel`
- `.github/workflows/deploy.yml`
  - triggers when CI completes successfully on `main`
  - downloads the wheel artifact
  - runs: `sudo /opt/taskmanagement-app/deploy/deploy-wheel.sh "$WHEEL_PATH"`

### 8.1 Runner requirements

- Linux machine with outbound internet access to GitHub
- A user account to run the GitHub Actions runner
- `sudo` permission to run `/opt/taskmanagement-app/deploy/deploy-wheel.sh`

Runner labels required by `deploy.yml`:

- `self-hosted`
- `linux`
- `deploy`

### 8.2 Install the self-hosted runner

In GitHub:

- Repository Settings
- Actions
- Runners
- New self-hosted runner

Follow GitHub’s instructions for Linux.

Make sure the runner is configured with labels including `deploy`.

### 8.3 sudo permissions for deployment

The deploy job runs the server-side script with `sudo`:

- `/opt/taskmanagement-app/deploy/deploy-wheel.sh`

Configure sudo so the runner user can run that script non-interactively.

## 9) Server-side deploy script contract

The deploy workflow expects a script at:

- `/opt/taskmanagement-app/deploy/deploy-wheel.sh`

The script must:

- accept one argument: a path to a wheel file
- install/upgrade the wheel into `/opt/taskmanagement-app/venv`
- restart the `taskmanagement-app` systemd service

Minimal outline (adapt to your environment):

```bash
#!/usr/bin/env bash
set -euo pipefail

WHEEL_PATH="$1"
VENV_DIR="/opt/taskmanagement-app/venv"

"$VENV_DIR/bin/pip" install --upgrade --force-reinstall "$WHEEL_PATH"

sudo systemctl restart taskmanagement-app
```

## 10) Post-deploy verification

```bash
sudo systemctl status taskmanagement-app --no-pager
curl -f http://127.0.0.1:8000/openapi.json
```

If you are debugging printing:

- PDF output directory exists and is owned by `taskapp`
- USB printer has the udev rule applied (replug after rule changes)
