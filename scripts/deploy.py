import os
import json
import subprocess
from pathlib import Path

def update_host_json():
    """Update host.json with production settings"""
    host_config = {
        "version": "2.0",
        "logging": {
            "applicationInsights": {
                "samplingSettings": {
                    "isEnabled": true,
                    "excludedTypes": "Request"
                }
            }
        },
        "extensionBundle": {
            "id": "Microsoft.Azure.Functions.ExtensionBundle",
            "version": "[3.*, 4.0.0)"
        }
    }
    
    with open('host.json', 'w') as f:
        json.dump(host_config, f, indent=2)

def create_deployment_package():
    """Create deployment package for Azure Functions"""
    # Create deployment directory
    os.makedirs('deployment', exist_ok=True)
    
    # Copy necessary files
    files_to_copy = [
        'host.json',
        'local.settings.json',
        'requirements.txt',
        '.funcignore'
    ]
    
    for file in files_to_copy:
        if os.path.exists(file):
            subprocess.run(['cp', file, 'deployment/'])
    
    # Copy app and functions directories
    subprocess.run(['cp', '-r', 'app', 'deployment/'])
    subprocess.run(['cp', '-r', 'functions', 'deployment/'])
    
    print("Deployment package created in 'deployment' directory")

if __name__ == "__main__":
    update_host_json()
    create_deployment_package() 