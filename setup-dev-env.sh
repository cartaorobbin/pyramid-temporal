#!/bin/bash

# Development Environment Setup Script for pyramid-temporal
# This script helps set up the local development environment

set -e  # Exit on any error

echo "🚀 Setting up pyramid-temporal development environment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    print_error "uv is not installed. Please install it first:"
    echo "  brew install uv"
    exit 1
fi

print_status "uv is installed"

# Check if direnv is installed
if ! command -v direnv &> /dev/null; then
    print_warning "direnv is not installed. Installing..."
    brew install direnv
    echo ""
    print_warning "Please add the following to your shell configuration (~/.zshrc or ~/.bashrc):"
    echo '  eval "$(direnv hook zsh)"  # or bash'
    echo ""
fi

print_status "direnv is available"

# Python version to use
PYTHON_VERSION="3.11.7"

echo ""
echo "🐍 Setting up Python environment..."

print_status "Pinning Python $PYTHON_VERSION..."
uv python pin "$PYTHON_VERSION"
uv python install "$PYTHON_VERSION"

# Verify Python setup
echo ""
echo "🔍 Verifying Python setup..."
uv run python --version

# Allow direnv if .envrc exists
if [ -f ".envrc" ]; then
    print_status "Allowing direnv to load .envrc..."
    direnv allow
else
    print_warning ".envrc file not found"
fi

echo ""
echo "📦 Installing project dependencies..."
uv sync

echo ""
echo "🔧 Setting up pre-commit hooks..."
uv run pre-commit install

echo ""
echo "🎉 Environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Ensure your shell configuration includes direnv hooks"
echo "2. Restart your terminal or run: source ~/.zshrc (or ~/.bashrc)"
echo "3. Navigate to the project directory to activate the environment"
echo "4. Run 'uv run pytest' to verify everything works"
echo ""
echo "For more details, see: .cursor/rules/tools-and-setup.mdc"
