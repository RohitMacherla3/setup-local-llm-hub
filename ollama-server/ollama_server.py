"""Module to start the Ollama server with continuous chat history"""
import asyncio
import json
import os
from typing import List, Dict
from pydantic import BaseModel
import uvicorn
import aiohttp
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from log import setup_colored_logging
from chat_manager import ModelHistoryManager

OLLAMA_MODE = "network"  # Options: "local" or "network"
OLLAMA_NETWORK_URL = "http://192.168.1.203:11434"  # URL for remote Ollama instance

# Set up the logger for this file
logger = setup_colored_logging("ollama_server")

app = FastAPI(title="Ollama Chat API")

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models for request/response
class ModelRequest(BaseModel):
    """Model request for chat API"""
    name: str
    prompt: str

# Initialize the history manager
history_manager = ModelHistoryManager()

# Store active WebSocket connections
active_connections: Dict[str, List[WebSocket]] = {}

def get_ollama_base_url():
    """Get the base URL for Ollama API based on mode"""
    if OLLAMA_MODE == "network":
        return OLLAMA_NETWORK_URL
    return "http://localhost:11434"

async def is_ollama_running():
    """Check if Ollama is running"""
    if OLLAMA_MODE == "network":
        # For network mode, check if the remote Ollama is accessible
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{OLLAMA_NETWORK_URL}/api/tags") as response:
                    return response.status == 200
        except Exception as e:
            logger.error("Error checking remote Ollama status: %s", e)
            return False
    else:
        # For local mode, check if the local Ollama process is running
        try:
            process = await asyncio.create_subprocess_exec(
                "ollama", "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return process.returncode == 0
        except Exception as e:
            logger.error("Error checking local Ollama status: %s", e)
            return False

async def ensure_ollama_running():
    """Ensure Ollama is running"""
    if OLLAMA_MODE == "network":
        # For network mode, just check if remote Ollama is accessible
        if not await is_ollama_running():
            logger.error("Remote Ollama service at %s is not accessible", OLLAMA_NETWORK_URL)
            return False
        return True
    else:
        # For local mode, start Ollama if not running
        if not await is_ollama_running():
            logger.debug("Starting local Ollama...")
            try:
                process = await asyncio.create_subprocess_exec(
                    "ollama", "serve",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                # Wait for Ollama to start (max 10 seconds)
                for _ in range(10):
                    await asyncio.sleep(1)
                    if await is_ollama_running():
                        logger.info("Local Ollama started successfully")
                        return True

                logger.error("Failed to start local Ollama after waiting")
                return False
            except Exception as e:
                logger.error("Error starting local Ollama: %s", e)
                return False
        return True

async def get_ollama_models():
    """Get a list of installed Ollama models"""
    if OLLAMA_MODE == "network":
        # For network mode, use HTTP API to get models
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{OLLAMA_NETWORK_URL}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [model["name"] for model in data.get("models", [])]
                        logger.info("Available remote models: %s", models)
                        return models
                    else:
                        logger.error("Error listing remote models: %s", await response.text())
                        return []
        except Exception as e:
            logger.error("Error getting remote Ollama models: %s", e)
            return []
    else:
        # For local mode, use CLI to get models
        try:
            process = await asyncio.create_subprocess_exec(
                "ollama", "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error("Error listing local models: %s", stderr.decode())
                return []

            # Parse output to get model names
            models = []
            lines = stdout.decode().strip().split('\n')

            # Skip header line
            for line in lines[1:]:
                if line.strip():
                    parts = line.split()
                    if parts:
                        # Get model name
                        models.append(parts[0])
                        
            logger.info("Available local models: %s", models)

            return models
        except Exception as e:
            logger.error("Error getting local Ollama models: %s", e)
            return []

@app.websocket("/ws/{model_name}")
async def websocket_endpoint(websocket: WebSocket, model_name: str):
    """WebSocket endpoint for chat"""
    await websocket.accept()

    # Create a unique connection ID
    connection_id = str(id(websocket))
    logger.info("New WebSocket connection for model %s with ID %s", model_name, connection_id)

    # Get the model history
    model_history = history_manager.get_model_history(model_name)

    # Check if Ollama is running
    if not await ensure_ollama_running():
        await websocket.send_text(json.dumps({
            "type": "system",
            "content": f"Failed to connect to {'remote' if OLLAMA_MODE == 'network' else 'local'} Ollama service"
        }))
        logger.error("Failed to connect to Ollama service for connection %s", connection_id)
        await websocket.close()
        return

    # Send welcome message
    await websocket.send_text(json.dumps({
        "type": "welcome",
        "model": model_name,
        "modelDisplayName": model_name.split(":")[0].capitalize(),
        "ollama_mode": OLLAMA_MODE
    }))

    # Get all previous messages and send to client
    previous_messages = model_history.get_messages()

    # Filter out system messages for display
    display_messages = [msg for msg in previous_messages if msg["role"] != "system"]

    if display_messages:
        await websocket.send_text(json.dumps({
            "type": "history_loaded",
            "messages": display_messages
        }))

    try:
        # Process messages
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "message":
                user_message = message_data.get("content", "")
                logger.info("Received user message: %s...", user_message[:50])
                # Add user message to chat history
                model_history.add_message("user", user_message)

                # Notify client that streaming is starting
                await websocket.send_text(json.dumps({
                    "type": "stream_start"
                }))

                # Process with Ollama, passing full context
                await process_ollama_message(
                    websocket,
                    model_name,
                    model_history,
                    connection_id
                )

            elif message_data.get("type") == "clear_history":
                # Clear the chat history for this model
                model_history.clear_history()

                # Notify client that history was cleared
                await websocket.send_text(json.dumps({
                    "type": "history_cleared"
                }))

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for model %s and connection %s", model_name, connection_id)
    finally:
        # No need to explicitly save as it's saved after each message
        pass

async def process_ollama_message(websocket: WebSocket,
                                model_name: str,
                                model_history,
                                connection_id: str):
    """Process a message with Ollama and stream the response"""
    try:
        # Get the current history context
        context = model_history.get_messages()
        logger.debug("Sending %d messages to Ollama", len(context))

        # Get the base URL for Ollama
        ollama_base_url = get_ollama_base_url()
        logger.debug("Using Ollama API at: %s", ollama_base_url)

        # Prepare the full context for Ollama
        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(
                f"{ollama_base_url}/api/chat",
                json={
                    "model": model_name,
                    "messages": context,
                    "stream": True
                }
            ) as response:
                full_response = ""
                async for line in response.content:
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data:
                                chunk = data["message"].get("content", "")
                                full_response += chunk

                                # Stream each chunk to the client
                                await websocket.send_text(json.dumps({
                                    "type": "stream",
                                    "content": chunk
                                }))
                        except Exception as e:
                            logger.error("Error parsing line: %s", e)

        # Signal end of stream
        await websocket.send_text(json.dumps({
            "type": "stream_end"
        }))

        # Add assistant's response to the chat history
        logger.info("Adding assistant response: %s...", full_response[:50])
        model_history.add_message("assistant", full_response)

    except Exception as e:
        logger.error("Error processing Ollama message: %s", e)
        await websocket.send_text(json.dumps({
            "type": "error",
            "content": f"Error: {str(e)}"
        }))
        await websocket.send_text(json.dumps({
            "type": "stream_end"
        }))

# API Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Ollama Chat API is running",
        "mode": OLLAMA_MODE,
        "url": get_ollama_base_url()
    }

@app.get("/api/models")
async def get_models():
    """Get available models endpoint"""
    if not await ensure_ollama_running():
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to connect to {'remote' if OLLAMA_MODE == 'network' else 'local'} Ollama service"
        )

    # Get models
    models = await get_ollama_models()
    return {"models": models, "mode": OLLAMA_MODE}

@app.get("/api/chat_history/{model_name}")
async def get_model_chat_history(model_name: str):
    """Get chat history for a specific model"""
    model_history = history_manager.get_model_history(model_name)
    messages = model_history.get_messages()

    # Filter out system messages for display
    display_messages = [msg for msg in messages if msg["role"] != "system"]

    return {
        "model": model_name,
        "messages": display_messages
    }

@app.post("/api/clear_history/{model_name}")
async def clear_model_history(model_name: str):
    """Clear chat history for a specific model"""
    history_manager.clear_model_history(model_name)
    return {"status": "success", "message": f"Cleared history for model {model_name}"}

@app.post("/api/chat")
async def chat(request: ModelRequest):
    """Chat endpoint for non-WebSocket requests"""
    if not await ensure_ollama_running():
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to connect to {'remote' if OLLAMA_MODE == 'network' else 'local'} Ollama service"
        )

    try:
        # Get model history
        model_history = history_manager.get_model_history(request.name)

        # Add user message
        model_history.add_message("user", request.prompt)

        # Get full context
        context = model_history.get_messages()

        # Get the base URL for Ollama
        ollama_base_url = get_ollama_base_url()

        # Make a request to Ollama API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ollama_base_url}/api/chat",
                json={
                    "model": request.name,
                    "messages": context,
                    "stream": False
                }
            ) as response:
                result = await response.json()

                if "message" in result:
                    assistant_response = result["message"].get("content", "")

                    # Add assistant response to history
                    model_history.add_message("assistant", assistant_response)

                    return {"response": assistant_response}
                else:
                    raise HTTPException(status_code=500, detail="Invalid response from Ollama")

    except Exception as e:
        logger.error("Error in chat endpoint: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

# Startup event to ensure Ollama is running
@app.on_event("startup")
async def startup_event():
    """Startup event to ensure Ollama is running"""
    logger.info("Server starting up in %s mode", OLLAMA_MODE)
    if not await ensure_ollama_running():
        logger.error(
            "Failed to connect to %s Ollama service during startup", 
            "remote" if OLLAMA_MODE == "network" else "local"
        )

if __name__ == "__main__":
    uvicorn.run("ollama_server:app", host="0.0.0.0", port=8000, reload=True)
