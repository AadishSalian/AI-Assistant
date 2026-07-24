import json
import os
import logging

logger = logging.getLogger("sweetie.memory")

class MemoryBuffer:
    def __init__(self, filepath="logs/memory.json", max_exchanges=50):
        self.filepath = filepath
        self.max_exchanges = max_exchanges
        self.history = []
        self.session_start = len(self.history) # Track where the current session started
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        self.load()
        self.session_start = len(self.history)

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
            self.session_start = max(0, self.session_start - 1)
            
        self.save()

    def get_context_string(self):
        """Returns a formatted string of recent history for the LLM prompt"""
        if not self.history:
            return "No previous conversation context."
            
        context = "Recent Conversation History:\n"
        
        # Determine how many exchanges to show to avoid blowing up the context window
        # For a 3B model, we want to keep it reasonable. 
        recent = self.history[-10:]
        
        for i, ex in enumerate(recent):
            context += f"User: {ex['user']}\n"
            context += f"Sweetie (Intent: {ex['intent']}): {ex['sweetie']}\n"
            
        return context
