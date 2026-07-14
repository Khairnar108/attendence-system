#!/bin/bash
set -e

cd /home/ec2-user/attendance-app

# Install/refresh the systemd unit in case it changed
sudo cp attendance-app.service /etc/systemd/system/attendance-app.service
sudo systemctl daemon-reload
sudo systemctl enable attendance-app
sudo systemctl restart attendance-app
