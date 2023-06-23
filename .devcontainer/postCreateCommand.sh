#!/usr/bin/env bash
set -e

# git settings
git config --global pull.rebase true
git config --global remote.origin.prune true

# if the .venv directory was mounted as a named volume, it needs the ownership changed
sudo chown vscode .venv || true

# make the python binary location predictable
poetry config virtualenvs.in-project true
poetry install --with=dev || true

mkdir -p .dev_container_logs
echo "*" > .dev_container_logs/.gitignore

pip install git+https://github.com/JamesHutchison/ptyme-track

ptyme-track --ensure-secret
