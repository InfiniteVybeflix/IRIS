#!/usr/bin/env bash
# IRIS v7.0 Setup Script
# One-command bootstrap for the Aevibron Agent Corps

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     AEVIBRON AGENT CORPS — IRIS v7.0 SETUP                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Create directories
echo "Creating directories..."
mkdir -p /mnt/agents/output/iris_v7/data
mkdir -p /mnt/agents/output/iris_v7/logs
mkdir -p /mnt/agents/output/iris_v7/tests

# Install dependencies
echo "Installing dependencies..."
pip3 install -q -r requirements.txt 2>/dev/null || echo "Some packages may need manual installation"

# Set permissions
echo "Setting permissions..."
chmod +x main.py
chmod +x core/api_server.py

# Create .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from template. Please edit with your API keys."
fi

# Bootstrap test
echo ""
echo "Running bootstrap test..."
python3 -c "
from core.bootstrap import bootstrap_all, shutdown
c = bootstrap_all(data_dir='/mnt/agents/output/iris_v7/data', max_workers=4)
stats = c.registry.get_stats()
print(f'Agents registered: {stats["total_agents"]}/29')
print(f'Domains: {', '.join(stats["domains"])}')
print(f'Status: {stats["status_breakdown"]}')
shutdown(c)
print('Bootstrap test PASSED')
"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     SETUP COMPLETE                                          ║"
echo "║                                                              ║"
echo "║  Run: python3 main.py                                        ║"
echo "║  API: python3 core/api_server.py                             ║"
echo "║  Test: python3 -m pytest tests/ -v                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
