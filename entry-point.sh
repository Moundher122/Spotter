#!/bin/bash

# Run Django migrations
uv run manage.py makemigrations logger
uv run manage.py migrate --noinput

echo "Migrations completed successfully!"
# Start the Django development server
uv run manage.py runserver 0.0.0.0:8000
