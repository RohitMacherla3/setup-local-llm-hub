#!/usr/bin/env python3
"""
Script to interact with downloaded Ollama models
This script will:
1. Fetch and list all installed models
2. Let the user select a model by number
3. Run an interactive session with the selected model
"""
import subprocess
import sys

def get_installed_models():
    """Get list of installed models from Ollama"""
    try:
        result = subprocess.run(
            ["ollama", "list"], 
            capture_output=True, 
            text=True
        )

        if result.returncode != 0:
            print(f"Error listing models: {result.stderr}")
            return []

        lines = result.stdout.strip().split('\n')
        models = []

        for line in lines[1:]:
            if line.strip():
                parts = line.split()
                if parts:
                    models.append(parts[0])

        return models
    except Exception as e:
        print(f"Error getting installed models: {e}")
        return []

def interactive_mode(model_name):
    """Run an interactive session with the selected model"""
    print(f"\nStarting interactive session with {model_name}")
    print("Type 'exit' or 'quit' to end the session")
    print("-" * 40)

    current_model = model_name
    while True:
        try:
            user_input = input(f"\n[{current_model}] > Press enter to continue and 'exit' or 'quit' to end the session: ")

            if user_input.lower() in ['exit', 'quit',  ]:
                break

            cmd = f"ollama run {current_model}"
            print(f"Running: {cmd}")
            subprocess.run(cmd, shell=True)

        except KeyboardInterrupt:
            print("\nExiting interactive mode...")
            break
        except Exception as e:
            print(f"Error: {e}")

def ensure_ollama_running():
    """Check if Ollama is running, start it if not"""
    try:
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
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        print("Waiting for Ollama to start...")
        import time
        for _ in range(5):
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
    print("Ollama Model Interaction")
    print("=" * 60)

    try:
        subprocess.run(["ollama", "--version"], 
                     stdout=subprocess.PIPE, 
                     stderr=subprocess.PIPE)
    except FileNotFoundError:
        print("Error: Ollama not found. Please install Ollama first.")
        print("Visit https://ollama.com for installation instructions.")
        return 1

    if not ensure_ollama_running():
        print("Please start Ollama manually and try again.")
        return 1

    available_models = get_installed_models()

    if not available_models:
        print("No models are currently available. Please download models first.")
        return 1

    print("\nAvailable models:")
    for i, model in enumerate(available_models, 1):
        print(f"  {i}. {model}")

    while True:
        try:
            choice = input("\nSelect a model by number (or 'q' to quit): ")

            if choice.lower() in ['q', 'quit', 'exit']:
                print("Exiting...")
                return 0

            index = int(choice) - 1
            if 0 <= index < len(available_models):
                model_name = available_models[index]
                break
            else:
                print(f"Invalid selection. Please enter a number between 1 and {len(available_models)}.")
        except ValueError:
            print("Please enter a valid number.")

    interactive_mode(model_name)
    return 0

if __name__ == "__main__":
    sys.exit(main())
