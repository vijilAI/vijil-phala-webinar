.PHONY: help clean build up down restart run benchmark push deploy

# Default target
help:
	@echo "Available targets:"
	@echo "  clean     - Remove Python cache files and Docker build cache"
	@echo "  build     - Build the Docker image locally"
	@echo "  up        - Start services with docker compose (with build)"
	@echo "  down      - Stop and remove services"
	@echo "  restart   - Stop, clean, and start services again"
	@echo "  run       - Run the agent locally (requires .env file)"
	@echo "  benchmark - Run performance benchmark (requires agent to be running)"
	@echo "  push      - Build and push to Public ECR (with patch bump)"
	@echo "  deploy    - Same as push"
	@echo "  help      - Show this help message"

# Clean all Python cache files
clean:
	@echo "Cleaning Python cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "Python cache cleaned successfully"

# Build Docker image
build:
	@echo "Building Docker image..."
	docker compose -f docker/dev-compose.yaml build

# Stop docker compose services
down:
	@echo "Stopping services..."
	docker compose -f docker/dev-compose.yaml down

# Start docker compose services
up:
	@echo "Starting services with docker compose..."
	docker compose -f docker/dev-compose.yaml up --build

# Restart services
restart: down clean up

# Run locally without Docker
run:
	@echo "Running agent locally..."
	uvicorn agent:app --host 0.0.0.0 --port 8000 --reload

# Run benchmark tests
benchmark:
	@echo "Running benchmark (make sure agent is running on localhost:8000)..."
	python3 benchmark.py

# Build and push to Public ECR
push:
	@echo "Building and pushing to Public ECR..."
	./scripts/build_and_push.sh

# Alias for push
deploy: push
