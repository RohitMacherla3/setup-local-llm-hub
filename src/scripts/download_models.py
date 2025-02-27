#!/usr/bin/env python3
"""
Script to download models from Ollama based on a JSON configuration file.
This script will:
1. Load models from a JSON file located two directories up
2. Display available models with numbers
3. Allow the user to select a model by number
4. Download the selected model
"""
import json
import subprocess
import sys
import time
import os
from pathlib import Path

def load_models():
    """Load models from JSON file located two directories up"""
    # Get the path to the JSON file (two directories up from the script)
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    json_path = script_dir.parent.parent / "model_list.json"

    if not json_path.exists():
        print(f"Error: JSON file not found at {json_path}")
        return None

    try:
        # Load the JSON data from file
        with open(json_path, 'r') as f:
            data = json.load(f)
        models = data.get('models', [])
        if not models:
            print("No models found in configuration file.")
            return None

        # Display the models with numbers
        print("\nAvailable models:")
        for i, model in enumerate(models, 1):
            name = model['name']
            desc = model.get('description', 'No description')
            params = model.get('parameters', 'N/A')
            print(f"  {i}. {name} ({params}) - {desc}")

        return models
    except Exception as e:
        print(f"Error loading models: {e}")
        return None

def download_model(model):
    """Download a specific model using the command from the JSON"""
    name = model['name']
    command = model['command_install']

    print(f"\nDownloading model: {name}")
    print(f"Running command: {command}")

    try:
        # Run the command directly with shell=True for better output handling
        result = subprocess.run(
            command,
            shell=True,
            check=False,  # Don't raise exception on non-zero return code
            text=True,
            capture_output=False  # Don't capture output, show it in real-time
        )

        # Check if successful
        if result.returncode == 0:
            print(f"\n✅ Successfully downloaded {name}")
            return True
        else:
            print(f"\n❌ Failed to download {name}")
            return False

    except Exception as e:
        print(f"\nError downloading model: {e}")
        import traceback
        traceback.print_exc()
        return False

def ensure_ollama_running():
    """Check if Ollama is running, start it if not"""
    try:
        # Try to run a simple ollama command
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("Ollama is running.")
            return True
    except Exception:
        pass

    print("Ollama is not running. Attempting to start...")

    try:
        # Start Ollama in the background
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Wait for Ollama to start
        print("Waiting for Ollama to start...")
        for _ in range(5):  # Try for 5 seconds
            time.sleep(1)
            try:
                result = subprocess.run(
                    ["ollama", "list"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print("Ollama started successfully.")
                    return True
            except Exception:
                pass

        print("Failed to start Ollama automatically.")
        return False
    except Exception as e:
        print(f"Error starting Ollama: {e}")
        return False

def main():
    """Main entry point for the script"""
    print("=" * 60)
    print("Ollama Model Downloader")
    print("=" * 60)

    # Check if Ollama is installed
    try:
        subprocess.run(["ollama", "--version"], 
                     stdout=subprocess.PIPE, 
                     stderr=subprocess.PIPE)
    except FileNotFoundError:
        print("Error: Ollama not found. Please install Ollama first.")
        print("Visit https://ollama.com for installation instructions.")
        return 1

    # Ensure Ollama is running
    if not ensure_ollama_running():
        print("Please start Ollama manually and try again.")
        return 1

    # Load and display available models
    models = load_models()

    if not models:
        return 1

    # Ask user to select a model
    while True:
        try:
            choice = input("\nEnter the number of the model you want to download (or 'q' to quit): ")

            if choice.lower() in ['q', 'quit', 'exit']:
                print("Exiting...")
                return 0

            model_idx = int(choice) - 1

            if 0 <= model_idx < len(models):
                selected_model = models[model_idx]
                break
            else:
                print(f"Invalid selection. Please enter a number between 1 and {len(models)}.")
        except ValueError:
            print("Please enter a valid number.")

    # Download the selected model
    success = download_model(selected_model)

    # Show final message
    if success:
        print(f"\nModel {selected_model['name']} has been downloaded and is ready to use.")
        print("You can run it with:")
        print(f"  {selected_model['command_run']}")
    else:
        print("\nDownload failed. Please check your connection and try again.")

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
