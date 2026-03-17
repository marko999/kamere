#!/bin/bash
# Setup script for Kamere on Azure VM (Ubuntu 22.04/24.04)
# Run as root: sudo bash setup.sh

set -euo pipefail

APP_USER="kamere"
APP_DIR="/opt/kamere"
REPO="https://github.com/marko999/kamere.git"

echo "=== Installing system dependencies ==="
apt-get update
apt-get install -y python3 python3-venv python3-pip ffmpeg nginx git

echo "=== Creating app user ==="
id -u $APP_USER &>/dev/null || useradd -r -s /bin/bash -m -d /home/$APP_USER $APP_USER

echo "=== Cloning repo ==="
if [ -d "$APP_DIR" ]; then
    cd $APP_DIR && git pull
else
    git clone $REPO $APP_DIR
fi
chown -R $APP_USER:$APP_USER $APP_DIR

echo "=== Setting up Python venv ==="
cd $APP_DIR
sudo -u $APP_USER python3 -m venv venv
sudo -u $APP_USER venv/bin/pip install --upgrade pip
sudo -u $APP_USER venv/bin/pip install -r requirements.txt

echo "=== Installing systemd services ==="
cp deploy/kamere-pipeline.service /etc/systemd/system/
cp deploy/kamere-web.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable kamere-pipeline kamere-web
systemctl start kamere-pipeline kamere-web

echo "=== Configuring nginx ==="
cp deploy/nginx.conf /etc/nginx/sites-available/kamere
ln -sf /etc/nginx/sites-available/kamere /etc/nginx/sites-enabled/kamere
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "=== Done ==="
echo "Pipeline: systemctl status kamere-pipeline"
echo "Web:      systemctl status kamere-web"
echo "Nginx:    systemctl status nginx"
echo "Logs:     journalctl -u kamere-pipeline -f"
