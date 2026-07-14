#!/bin/bash
set -e

cd /home/ec2-user/attendance-app

if ! command -v python3 &> /dev/null; then
  echo "python3 not found - install it first (see README step 4)"
  exit 1
fi

# Create the virtualenv only if it doesn't already exist so re-deploys are fast
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
deactivate
