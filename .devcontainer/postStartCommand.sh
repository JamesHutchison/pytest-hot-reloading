#!/usr/bin/env bash

# run in the background at startup
nohup bash -c '.devcontainer/postStartBackground.sh &' > .dev_container_logs/postStartBackground.out

docker compose -f tests/workarounds/pytest_django/docker-compose.yml up -d postgres
