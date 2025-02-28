"""Module for managing continuous chat history per model"""
import os
import json
import datetime
from typing import List, Dict
import pathlib
from log import setup_colored_logging

# Set up logger
logger = setup_colored_logging("chat_manager")

class ModelChatHistory:
    """Class to manage persistent chat history for a model"""
    def __init__(self, model_name: str, history_dir: str = "chat_history"):
        self.model_name = model_name.split(':')[0].capitalize()
        self.history_dir = history_dir
        self.history_file = f"{history_dir}/{model_name}_history.json"
        self.messages = []
        self.max_history_length = 50
        self.system_message = "You are a helpful and polite AI assistant. You always keep the the conversation light and try your best and provide answer to the point giving appropriate response."
        print(model_name.split(':')[0].capitalize())
        os.makedirs(self.history_dir, exist_ok=True)

        self.load_history()

    def load_history(self):
        """Load chat history from file"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.messages = data.get('messages', [])
                    logger.info("Loaded %d messages from history for model %s",
                               len(self.messages), self.model_name)
            else:
                logger.info("No history file found for model %s, starting fresh", self.model_name)
                # Initialize with system message if starting fresh
                system_message = {
                    "role": "system", 
                    "content": self.system_message
                }
                self.messages = [system_message]
                self.save_history()
        except Exception as e:
            logger.error("Error loading chat history for model %s: %s", self.model_name, e)

            system_message = {
                "role": "system", 
                "content": self.system_message
            }
            self.messages = [system_message]

    def add_message(self, role: str, content: str):
        """Add a message to the history"""
        message = {"role": role, "content": content}
        self.messages.append(message)

        if len(self.messages) > self.max_history_length + 1:
            # Keep the first message (system prompt) and the most recent messages
            self.messages = [self.messages[0]] + self.messages[-(self.max_history_length):]

        # Save after each update
        self.save_history()
        logger.debug("Added message with role '%s' to model history", role)

    def save_history(self):
        """Save chat history to file"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'model': self.model_name,
                    'updated_at': datetime.datetime.now().isoformat(),
                    'messages': self.messages
                }, f, ensure_ascii=False, indent=2)
            logger.debug("Saved chat history for model %s", self.model_name)
        except Exception as e:
            logger.error("Error saving chat history for model %s: %s", self.model_name, e)

    def get_messages(self) -> List[Dict[str, str]]:
        """Get all messages in history"""
        return self.messages

    def clear_history(self):
        """Clear the chat history except for the system message"""
        if self.messages and self.messages[0]["role"] == "system":
            # Keep only the system message
            system_message = self.messages[0]
            self.messages = [system_message]
        else:
            # Create a default system message if none exists
            system_message = {
                "role": "system", 
                "content": self.system_message
            }
            self.messages = [system_message]

        self.save_history()
        logger.info("Cleared chat history for model %s", self.model_name)

class ModelHistoryManager:
    """Manager for model chat histories"""
    def __init__(self, history_dir: str = "chat_history"):
        self.history_dir = history_dir
        self.model_histories: Dict[str, ModelChatHistory] = {}

        # Create history directory if it doesn't exist
        os.makedirs(self.history_dir, exist_ok=True)

    def get_model_history(self, model_name: str) -> ModelChatHistory:
        """Get or create history for a model"""
        model_name = model_name.split(':')[0].capitalize()
        if model_name not in self.model_histories:
            self.model_histories[model_name] = ModelChatHistory(model_name, self.history_dir)
        return self.model_histories[model_name]

    def list_available_models(self) -> List[str]:
        """List models that have saved history"""
        try:
            history_files = list(pathlib.Path(self.history_dir).glob("*_history.json"))
            models = [f.name.replace('_history.json', '') for f in history_files]
            return models
        except Exception as e:
            logger.error("Error listing available model histories: %s", e)
            return []

    def clear_model_history(self, model_name: str):
        """Clear history for a specific model"""
        if model_name in self.model_histories:
            self.model_histories[model_name].clear_history()
        else:
            # Create and immediately clear the history
            history = self.get_model_history(model_name)
            history.clear_history()

    def clear_all_histories(self):
        """Clear history for all models"""
        for model_name in self.list_available_models():
            self.clear_model_history(model_name)
