#!/bin/bash

uv run manage.py makemigrations
uv run manage.py migrate --noinput
# use uvicorn to run the server in production
echo "Migrations completed successfully!"
uv run manage.py runserver 0.0.0.0:8000
