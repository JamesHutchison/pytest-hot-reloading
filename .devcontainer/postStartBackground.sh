#!/usr/bin/env bash
poetry run pytest --daemon &
poetry run dmypy start

ptyme-track --standalone
