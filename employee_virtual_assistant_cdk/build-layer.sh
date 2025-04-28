#!/bin/bash
# Build Lambda Layer Script
#
# This script creates a layer structure and installs the required Python 
# packages for AWS Lambda layers. The layer is used by Lambda functions
# that need these dependencies.

echo "Starting Lambda layer build process..."

# Create the layer directory structure
mkdir -p layer/python
echo "Created directory structure: layer/python"

# Install required packages directly to the layer directory
pip install -t layer/python requests requests_aws4auth opensearch-py

# Verify that files were created successfully
if [ "$(ls -A layer/python)" ]; then
    echo "Layer build complete. Directory 'layer/python' contains:"
    ls -la layer/python
else
    echo "Error: 'layer/python' directory is empty after installation."
    exit 1
fi

echo "Lambda layer build complete. Directory 'layer' is ready to use."