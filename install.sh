#!/bin/bash
# Installation script for MyAgent

set -e

echo "🚀 Installing MyAgent..."

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python 3.10+ is required. Found: $PYTHON_VERSION"
    exit 1
fi

echo "✓ Python $PYTHON_VERSION detected"

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -e "." --quiet

# Initialize myagent
echo "🔧 Initializing MyAgent..."
myagent init

echo ""
echo "✅ MyAgent installed successfully!"
echo ""
echo "Next steps:"
echo "1. Add MyAgent to Kimi CLI MCP config at ~/.kimi/mcp.json"
echo "2. Or run 'myagent serve' to start the MCP server directly"
echo ""
echo "See README.md for configuration details."
