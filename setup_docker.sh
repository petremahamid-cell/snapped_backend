#!/bin/bash

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker and Docker Compose."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose is not installed. Please install Docker Compose."
    exit 1
fi

# Set up environment variables
if [ ! -f .env ]; then
    echo "Creating .env file..."
    echo "SERPAPI_API_KEY=your_serpapi_api_key" > .env
    echo "Please edit the .env file and set your SerpAPI API key."
fi

# Build and start the containers
echo "Building and starting containers..."
docker-compose up -d --build

echo "Setup complete! The API is now running at http://localhost:12000"
echo "You can view the API documentation at http://localhost:12000/docs"