.PHONY: dev prod build logs logs-dev stop clean restart restart-dev restart-prod health

# Development environment
dev:
	@echo "Starting development environment..."
	docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev up -d --build

# Production environment
prod:
	@echo "Starting production environment..."
	docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d --build

# Build images
build:
	@echo "Building Docker images..."
	docker compose build

build-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml build

build-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# View logs
logs:
	docker compose logs -f

logs-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

logs-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Stop services
stop:
	docker compose down

stop-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

stop-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# Restart services
restart:
	docker compose restart

restart-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml restart

restart-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml restart

# Health check
health:
	@curl -s http://localhost:8765/health | python3 -m json.tool || echo "Service not responding"

health-dev:
	@curl -s http://localhost:8766/health | python3 -m json.tool || echo "Service not responding"

# Clean up (removes containers, volumes, and local images)
clean:
	@echo "Cleaning up Docker resources..."
	docker compose down -v --rmi local

clean-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v --rmi local

clean-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down -v --rmi local

# Setup: Copy environment files
setup:
	@if [ ! -f .env.dev ]; then \
		cp .env.dev.example .env.dev && \
		echo "Created .env.dev from template"; \
	fi
	@if [ ! -f .env.prod ]; then \
		cp .env.prod.example .env.prod && \
		echo "Created .env.prod from template"; \
	fi
	@echo "Setup complete. Edit .env.dev and .env.prod with your configuration."

# Help
help:
	@echo "Available commands:"
	@echo "  make setup       - Copy environment templates"
	@echo "  make dev         - Start development environment"
	@echo "  make prod        - Start production environment"
	@echo "  make build       - Build Docker images"
	@echo "  make logs        - View logs (all services)"
	@echo "  make logs-dev    - View development logs"
	@echo "  make logs-prod   - View production logs"
	@echo "  make stop        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make health      - Check service health"
	@echo "  make clean       - Remove containers, volumes, and images"
