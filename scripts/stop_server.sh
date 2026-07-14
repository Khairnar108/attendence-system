#!/bin/bash
set -e

if systemctl list-units --full -all | grep -q "attendance-app.service"; then
  sudo systemctl stop attendance-app || true
fi
