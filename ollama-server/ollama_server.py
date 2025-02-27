from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import subprocess
import asyncio
import json
from typing import List, Dict, Any
from pydantic import BaseModel
import logging
import uuid
import tiktoken

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Ollama Chat API")

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models for request/response
class Message(BaseModel):
    role: str
    content: str

class ChatSession:
    def __init__(self, model_name: str, max_tokens: int = 4096):
        self.id = str(uuid.uuid4())
        self.model_name = model_name
        self.messages: List[Message] = []
        self.max_tokens = max_tokens
        self.tokenizer = tiktoken.get_encoding("cl100k_base")  # Use OpenAI's tokenizer as a standard

    def add_message(self, role: str, content: str):
        self.messages.append(Message(role=role, content=content))
        self._trim_context()

    def _trim_context(self):
        """Trim context to stay within token limit"""
        while self._calculate_tokens() > self.max_tokens:
            # Remove the oldest message, keeping system/initial context
            if len(self.messages) > 1:
                self.messages.pop(0)
            else:
                break

    def _calculate_tokens(self) -> int:
        """Calculate total tokens in the conversation"""
        return sum(
            len(self.tokenizer.encode(msg.content)) 
            for msg in self.messages
        )

    def get_context(self) -> List[Dict[str, str]]:
        """Get the current conversation context"""
        return [
            {"role": msg.role, "content": msg.content} 
            for msg in self.messages
        ]


class SessionManager:
    def __init__(self):
        # Nested dictionary to store sessions per model and connection
        self.sessions: Dict[str, Dict[str, ChatSession]] = {}

    def create_or_get_session(self, model_name: str, connection_id: str) -> ChatSession:
        # Create model-specific session container if not exists
        if model_name not in self.sessions:
            self.sessions[model_name] = {}
        
        # Create or retrieve session for this connection
        if connection_id not in self.sessions[model_name]:
            self.sessions[model_name][connection_id] = ChatSession(model_name)
        
        return self.sessions[model_name][connection_id]

    def remove_session(self, model_name: str, connection_id: str):
        if (model_name in self.sessions and 
            connection_id in self.sessions[model_name]):
            del self.sessions[model_name][connection_id]

# Initialize session manager
session_manager = SessionManager()

class ModelRequest(BaseModel):
    name: str
    prompt: str

# Store active WebSocket connections
active_connections: Dict[str, List[WebSocket]] = {}

# Check if Ollama is running
async def is_ollama_running():
    try:
        process = await asyncio.create_subprocess_exec(
            "ollama", "list",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return process.returncode == 0
    except Exception as e:
        logger.error(f"Error checking Ollama status: {e}")
        return False

# Start Ollama if not running
async def ensure_ollama_running():
    if not await is_ollama_running():
        logger.info("Starting Ollama...")
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
                    logger.info("Ollama started successfully")
                    return True
            
            logger.error("Failed to start Ollama after waiting")
            return False
        except Exception as e:
            logger.error(f"Error starting Ollama: {e}")
            return False
    return True

# Get installed models
async def get_ollama_models():
    try:
        process = await asyncio.create_subprocess_exec(
            "ollama", "list",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Error listing models: {stderr.decode()}")
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
        
        return models
    except Exception as e:
        logger.error(f"Error getting Ollama models: {e}")
        return []

# Modify the websocket_endpoint
@app.websocket("/ws/{model_name}")
async def websocket_endpoint(websocket: WebSocket, model_name: str):
    await websocket.accept()
    
    # Create a unique connection ID
    connection_id = str(id(websocket))
    
    # Create or get session for this connection
    session = session_manager.create_or_get_session(model_name, connection_id)
    
    # Check if Ollama is running (existing code)
    if not await ensure_ollama_running():
        await websocket.send_text(json.dumps({
            "type": "system",
            "content": "Failed to start Ollama service"
        }))
        await websocket.close()
        return
    
    try:
        # Process messages
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "message":
                user_message = message_data.get("content", "")
                
                # Add user message to session context
                session.add_message("user", user_message)
                
                # Notify client that streaming is starting
                await websocket.send_text(json.dumps({
                    "type": "stream_start"
                }))
                
                # Process with Ollama, passing full context
                await process_ollama_message(
                    websocket, 
                    model_name, 
                    session.get_context()
                )
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for model: {model_name}")
    finally:
        # Remove the session
        session_manager.remove_session(model_name, connection_id)

async def process_ollama_message(
    websocket: WebSocket, 
    model_name: str, 
    context: List[Dict[str, str]]
):
    try:
        import aiohttp
        
        # Prepare the full context for Ollama
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:11434/api/chat",
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
                            logger.error(f"Error parsing line: {e}")
                
        # Signal end of stream
        await websocket.send_text(json.dumps({
            "type": "stream_end"
        }))
        
        # Add assistant's response to the session
        # Note: This would be handled by the calling function in the websocket_endpoint
        
    except Exception as e:
        logger.error(f"Error processing Ollama message: {e}")
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
    return {"message": "Ollama Chat API is running"}

@app.get("/api/models")
async def get_models():
    # Ensure Ollama is running
    if not await ensure_ollama_running():
        raise HTTPException(status_code=500, detail="Failed to start Ollama service")
    
    # Get models
    models = await get_ollama_models()
    return {"models": models}

@app.post("/api/chat")
async def chat(request: ModelRequest):
    # For non-streaming API requests
    # This is an alternative to WebSockets if you prefer REST
    if not await ensure_ollama_running():
        raise HTTPException(status_code=500, detail="Failed to start Ollama service")
    
    try:
        process = await asyncio.create_subprocess_exec(
            "ollama", "run", request.name,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Send prompt to Ollama
        process.stdin.write(f"{request.prompt}\n".encode())
        await process.stdin.drain()
        
        # Read the response
        full_response = ""
        is_first_line = True
        
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            
            text = line.decode().strip()
            
            # Skip the first line (echo of the prompt)
            if is_first_line:
                is_first_line = False
                continue
            
            full_response += text + "\n"
        
        # Terminate process
        try:
            process.terminate()
            await process.wait()
        except:
            pass
        
        return {"response": full_response.strip()}
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Startup event to ensure Ollama is running
@app.on_event("startup")
async def startup_event():
    if not await ensure_ollama_running():
        logger.error("Failed to start Ollama service during startup")

if __name__ == "__main__":
    uvicorn.run("ollama_server:app", host="0.0.0.0", port=8000, reload=True)
