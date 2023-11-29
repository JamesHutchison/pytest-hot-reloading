#!/usr/bin/env bash
poetry run pytest --daemon &

ptyme-track --standalone
