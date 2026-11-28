#!/bin/bash
# Run tests for the haijunbot_agent module

echo "Running tests for haijunbot_agent module..."
cd ..
python -m pytest -v --tb=short
