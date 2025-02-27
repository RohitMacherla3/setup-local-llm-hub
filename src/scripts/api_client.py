#!/usr/bin/env python3
"""
Python client for interacting with Ollama API
"""
import json
import requests
import time
import sys
import subprocess

# Ollama API endpoint
OLLAMA_API = "http://localhost:11434/api"

class OllamaAPI:
    def __init__(self, api_base=OLLAMA_API):
        self.api_base = api_base
        
    def _make_request(self, endpoint, method="GET", data=None):
        """Make a request to the Ollama API"""
        url = f"{self.api_base}/{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request error: {e}")
            return None
            
    def list_models(self):
        """Get a list of available models"""
        return self._make_request("tags")
    
    def get_model_info(self, model_name):
        """Get information about a specific model"""
        return self._make_request("show", method="POST", data={"name": model_name})
    
    def generate(self, model_name, prompt, options=None):
        """Generate a completion for the given prompt"""
        data = {
            "model": model_name,
            "prompt": prompt
        }
        
        if options:
            data.update(options)
            
        return self._make_request("generate", method="POST", data=data)
    
    def chat(self, model_name, messages, options=None):
        """Send a chat request to the model"""
        data = {
            "model": model_name,
            "messages": messages
        }
        
        if options:
            data.update(options)
            
        return self._make_request("chat", method="POST", data=data)
    
    def generate_stream(self, model_name, prompt, options=None):
        """Generate a streaming completion for the given prompt"""
        data = {
            "model": model_name,
            "prompt": prompt,
            "stream": True
        }
        
        if options:
            data.update(options)
            
        url = f"{self.api_base}/generate"
        headers = {"Content-Type": "application/json"}
        
        try:
            response = requests.post(url, headers=headers, json=data, stream=True)
            response.raise_for_status()
            
            full_response = ""
            
            for line in response.iter_lines():
                if line:
                    line_data = json.loads(line)
                    if "response" in line_data:
                        chunk = line_data["response"]
                        full_response += chunk
                        print(chunk, end="", flush=True)
                        
                    if line_data.get("done", False):
                        break
                        
            print("\n")
            return full_response
        except requests.exceptions.RequestException as e:
            print(f"API request error: {e}")
            return None

def ensure_ollama_running():
    """Check if Ollama is running, start it if not"""
    try:
        # Try to make a simple request to the Ollama API
        response = requests.get(f"{OLLAMA_API}/tags")
        if response.status_code == 200:
            print("Ollama is running.")
            return True
    except requests.exceptions.ConnectionError:
        # Ollama is not running, try to start it
        print("Ollama is not running. Attempting to start...")
        
        try:
            # Start Ollama in the background
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait for Ollama to start
            max_attempts = 10
            for i in range(max_attempts):
                try:
                    time.sleep(1)
                    response = requests.get(f"{OLLAMA_API}/tags")
                    if response.status_code == 200:
                        print("Ollama started successfully.")
                        return True
                except requests.exceptions.ConnectionError:
                    if i == max_attempts - 1:
                        print("Failed to start Ollama after multiple attempts.")
                        return False
                    continue
        except Exception as e:
            print(f"Error starting Ollama: {e}")
            return False
    
    return False

def main():
    """Example usage of the Ollama API client"""
    if not ensure_ollama_running():
        return 1
    
    api = OllamaAPI()
    
    # Get list of available models
    model_data = api.list_models()
    
    if not model_data or "models" not in model_data:
        print("No models found or failed to get model list.")
        return 1
    
    available_models = [model["name"] for model in model_data["models"]]
    
    if not available_models:
        print("No models are available. Please download models using the setup script.")
        return 1
    
    print("Available models:")
    for i, model in enumerate(available_models, 1):
        print(f"  {i}. {model}")
    
    choice = input("\nEnter the number of the model to test: ")
    try:
        index = int(choice) - 1
        if 0 <= index < len(available_models):
            model_name = available_models[index]
        else:
            print("Invalid selection.")
            return 1
    except ValueError:
        print("Please enter a number.")
        return 1
    
    prompt = input("\nEnter a prompt to test: ")
    
    print("\nGenerating response...")
    api.generate_stream(model_name, prompt)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())