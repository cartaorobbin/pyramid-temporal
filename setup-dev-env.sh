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

# Check if pyenv is installed
if ! command -v pyenv &> /dev/null; then
    print_error "pyenv is not installed. Please install it first:"
    echo "  brew install pyenv"
    exit 1
fi

print_status "pyenv is installed"

# Check if pyenv-virtualenv is installed
if ! pyenv commands | grep -q virtualenv; then
    print_error "pyenv-virtualenv is not installed. Please install it:"
    echo "  brew install pyenv-virtualenv"
    exit 1
fi

print_status "pyenv-virtualenv is installed"

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
VENV_NAME="pyramid-temporal"

echo ""
echo "🐍 Setting up Python environment..."

# Install Python version if not available
if ! pyenv versions | grep -q "$PYTHON_VERSION"; then
    print_status "Installing Python $PYTHON_VERSION..."
    pyenv install "$PYTHON_VERSION"
else
    print_status "Python $PYTHON_VERSION is already installed"
fi

# Create virtual environment if it doesn't exist
if ! pyenv versions | grep -q "$VENV_NAME"; then
    print_status "Creating virtual environment '$VENV_NAME'..."
    pyenv virtualenv "$PYTHON_VERSION" "$VENV_NAME"
else
    print_status "Virtual environment '$VENV_NAME' already exists"
fi

# Set local Python version
print_status "Setting local Python version to '$VENV_NAME'..."
pyenv local "$VENV_NAME"

# Verify Python setup
echo ""
echo "🔍 Verifying Python setup..."
echo "Python version: $(python --version)"
echo "Python location: $(which python)"

# Install Poetry if not available in the virtual environment
if ! pip list | grep -q poetry; then
    print_status "Installing Poetry..."
    pip install poetry
else
    print_status "Poetry is already installed"
fi

# Configure Poetry
print_status "Configuring Poetry..."
poetry config virtualenvs.in-project true

# Allow direnv if .envrc exists
if [ -f ".envrc" ]; then
    print_status "Allowing direnv to load .envrc..."
    direnv allow
else
    print_warning ".envrc file not found"
fi

echo ""
echo "📦 Installing project dependencies..."
poetry install

echo ""
echo "🔧 Setting up pre-commit hooks..."
poetry run pre-commit install

echo ""
echo "🎉 Environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Ensure your shell configuration includes pyenv and direnv hooks"
echo "2. Restart your terminal or run: source ~/.zshrc (or ~/.bashrc)"
echo "3. Navigate to the project directory to activate the environment"
echo "4. Run 'poetry run pytest' to verify everything works"
echo ""
echo "For more details, see: .cursor/rules/tools-and-setup.mdc"
