#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Set environment variables
export REDIS_ENABLED=true
export REDIS_URL=redis://localhost:6379/0

# Run the application
python run.py