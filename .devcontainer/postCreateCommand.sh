#!/usr/bin/env bash
set -e

# git settings
git config --global pull.rebase true
git config --global remote.origin.prune true

# if the .venv directory was mounted as a named volume, it needs the ownership changed
sudo chown vscode .venv || true

# make the python binary location predictable
poetry config virtualenvs.in-project true
poetry init -n --python=~3.11 || true
# mypy - static type checking
# ruff - fast flake8 and isort alternative
# black - opinionated formatting
# pytest - testing
poetry add mypy ruff black pytest --group=dev || true
poetry install --with=dev || true

mkdir -p .dev_container_logs
