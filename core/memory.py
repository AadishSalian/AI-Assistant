import json
import os
import logging

logger = logging.getLogger("sweetie.memory")

class MemoryBuffer:
    def __init__(self, filepath="logs/memory.json", max_exchanges=10):
        self.filepath = filepath
        self.max_exchanges = max_exchanges
        self.history = []
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    self.history = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load memory: {e}")
                self.history = []

    def save(self):
        try:
            with open(self.filepath, 'w') as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")

    def add_exchange(self, user_text, sweetie_reply, intent=None, params=None):
        exchange = {
            "user": user_text,
            "sweetie": sweetie_reply,
            "intent": intent,
            "params": params
        }
        self.history.append(exchange)
        
        # Keep only the last N exchanges
        if len(self.history) > self.max_exchanges:
            self.history = self.history[-self.max_exchanges:]
            
        self.save()

    def get_context_string(self):
        """Returns a formatted string of recent history for the LLM prompt"""
        if not self.history:
            return "No previous conversation context."
            
        context = "Recent Conversation History:\n"
        for i, ex in enumerate(self.history):
            context += f"User: {ex['user']}\n"
            context += f"Sweetie (Intent: {ex['intent']}): {ex['sweetie']}\n"
        return context
