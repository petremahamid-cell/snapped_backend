#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Install Gunicorn if not already installed
pip install gunicorn uvicorn

# Run with Gunicorn
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:12000