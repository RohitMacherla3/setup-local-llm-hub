#!/usr/bin/env python3
"""
Utility script for managing Ollama models
"""
import subprocess
import json
import argparse
import os
from pathlib import Path

def get_ollama_models():
    """Get list of downloaded models from Ollama"""
    result = subprocess.run(
        ["ollama", "list"], 
        capture_output=True, 
        text=True
    )

    if result.returncode != 0:
        print(f"Error listing models: {result.stderr}")
        return []

    # Parse the output to get model information
    lines = result.stdout.strip().split('\n')
    models = []

    # Skip header line
    for line in lines[1:]:
        if line.strip():
            parts = line.split()
            if len(parts) >= 4:
                model = {
                    'name': parts[0],
                    'id': parts[1],
                    'size': parts[2] + ' ' + parts[3]
                }
                models.append(model)
    
    return models

def delete_model(model_name):
    """Delete a model from Ollama"""
    print(f"Deleting model: {model_name}")
    
    result = subprocess.run(
        ["ollama", "rm", model_name],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print(f"Successfully deleted {model_name}")
        return True
    else:
        print(f"Failed to delete {model_name}: {result.stderr}")
        return False

def show_model_info(model_name):
    """Show information about a specific model"""
    result = subprocess.run(
        ["ollama", "show", model_name],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print(f"Information for model: {model_name}")
        print("-" * 40)
        print(result.stdout)
        return True
    else:
        print(f"Failed to get information for {model_name}: {result.stderr}")
        return False

def export_models_list():
    """Export the list of currently installed models to JSON"""
    models = get_ollama_models()
    
    if not models:
        print("No models found to export.")
        return False
    
    output_data = {"installed_models": models}
    
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = script_dir.parent
    output_path = project_root / "configs" / "installed_models.json"
    
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"Exported model list to {output_path}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Manage Ollama models")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all models")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a model")
    delete_parser.add_argument("model", help="Name of the model to delete")
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Show model information")
    info_parser.add_argument("model", help="Name of the model to show info for")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export list of installed models")
    
    args = parser.parse_args()
    
    if args.command == "list" or not args.command:
        models = get_ollama_models()
        if models:
            print("Installed models:")
            print("{:<30} {:<15} {:<15}".format("NAME", "ID", "SIZE"))
            print("-" * 60)
            for model in models:
                print("{:<30} {:<15} {:<15}".format(
                    model['name'], model['id'], model['size']
                ))
        else:
            print("No models installed.")
    
    elif args.command == "delete":
        delete_model(args.model)
    
    elif args.command == "info":
        show_model_info(args.model)
    
    elif args.command == "export":
        export_models_list()
    
    return 0

if __name__ == "__main__":
    main()