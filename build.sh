#!/bin/bash

set -e

PROJECT_NAME="partomatic"
# Define the test command as a variable
TEST_CMD="exec(\"from partomatic import Partomatic, PartomaticConfig, AutomatablePart\nprint(PartomaticConfig().stl_folder)\")"
# Define sleep time for PyPI availability
PYPI_WAIT_TIME=30

read -p "Do you want to run pytest --cov ([Y]/N)? " PYTEST_CHOSEN
PYTEST_CHOSEN=${PYTEST_CHOSEN:-Y}
if [[ "$PYTEST_CHOSEN" =~ ^[Yy]$ ]]; then
    pytest --cov
    read -p "Based on the pytest results, proceed with the build? ([Y]/N)? " PYTEST_CLEAN
    PYTEST_CLEAN=${PYTEST_CLEAN:-Y}
    if [[ ! "$PYTEST_CLEAN" =~ ^[Yy]$ ]]; then
        echo "Build aborted."
        exit 0
    fi
fi

# Build process
pip3 uninstall -y "$PROJECT_NAME" || true
rm -rf dist/*

python3 -m build
pip3 install -e .

# # Local testß
python3 -c "$TEST_CMD"

read -p "Based on that simple test, upload to PyPI? ([Y]/N)? " PYPI_UPLOAD
PYPI_UPLOAD=${PYPI_UPLOAD:-Y}
if [[ "$PYPI_UPLOAD" =~ ^[Yy]$ ]]; then
    python3 -m twine upload dist/*
    pip3 uninstall -y "$PROJECT_NAME" || true
    sleep $PYPI_WAIT_TIME
    pip3 install "$PROJECT_NAME"
    python3 -c "$TEST_CMD"
    echo "REMINDER!!! Commit and push git changes!!!"
else
    echo "Upload to PyPI skipped."
fi