#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Set environment variables
export REDIS_ENABLED=true
export REDIS_URL=redis://localhost:6379/0

# Install Gunicorn if not already installed
pip install gunicorn uvicorn

# Run with Gunicorn
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:12000