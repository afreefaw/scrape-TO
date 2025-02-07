#!/bin/bash

# Run with: source scripts/setup_env.sh

# Define the virtual environment directory
VENV_DIR="venv"

# Check if the script is already running in a virtual environment
if [ -n "$VIRTUAL_ENV" ]; then
    echo "Already running inside a virtual environment: $VIRTUAL_ENV"
else
    # Check if the virtual environment directory exists
    if [ -d "$VENV_DIR" ]; then
        echo "Virtual environment already exists. Activating..."
    else
        echo "Creating virtual environment..."
        python -m venv "$VENV_DIR"
    fi

    # Activate the virtual environment
    source "$VENV_DIR/Scripts/activate"
fi

# Install requirements
if [ -f "requirements.txt" ]; then
    echo "Installing requirements..."
    pip install -r requirements.txt
else
    echo "requirements.txt not found. Skipping package installation."
fi

echo "Setup complete. Virtual environment is ready."
