#!/bin/bash

echo "========================================================"
echo " Thinx - Human Trafficking Research Platform"
echo " (Data Science in Practice - Leiden University)"
echo "========================================================"
echo ""
echo " Documentation:"
echo "  - Quick Start: QUICK_START.md"
echo "  - Main Docs: README.md"
echo "  - All Docs: docs/README.md"
echo "  - Mock Data: Mock data/ folder"
echo ""
echo "========================================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed."
    echo "Please install Docker and try again."
    exit 1
fi

# Check if the Docker Compose plugin is installed (docker-compose v1 is retired)
if ! docker compose version &> /dev/null; then
    echo "ERROR: The Docker Compose plugin is not available."
    echo "Install Docker Engine with the compose plugin and try again."
    exit 1
fi

# Every service belongs to a Compose profile, so a profile has to be selected or
# nothing starts at all (finding L1). COMPOSE_PROFILES in .env is honoured too.
PROFILE="${COMPOSE_PROFILES:-${1:-full}}"

if [ ! -f .env ]; then
    echo "ERROR: .env is missing. Copy .env.example to .env and set SECRET_KEY"
    echo "and AGRAPH_SUPER_PASSWORD before starting."
    exit 1
fi

echo "Docker is ready!"
echo ""
echo "Starting services (this may take a few minutes on first run)..."
echo ""

docker compose --profile "$PROFILE" up --build -d

echo ""
echo "Interface:  http://localhost:8080"
echo "API:        http://localhost:5000"
echo "Database:   http://localhost:10035"
echo ""
echo "First run: open the interface and register. The first account becomes the administrator."
