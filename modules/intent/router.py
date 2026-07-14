import re
import requests
import json
import logging
import time

logger = logging.getLogger("sweetie.intent")

class IntentRouter:
    def __init__(self, ollama_host="http://localhost:11434", model="phi3:mini"):
        self.ollama_host = ollama_host
        self.model = model
        
        self.intent_schema = """
        AVAILABLE INTENTS:
        1. system.volume (params: direction="up"|"down", level=0-100)
        2. system.mute (params: state="on"|"off")
        3. system.lock
        4. system.screenshot
        5. app.open (params: app_name)
        6. app.close (params: app_name, batch=True|False, except_app=app_name)
        7. app.focus (params: app_name)
        8. app.stats (params: app_name)
        9. system.startup (params: action="list"|"enable"|"disable", app_name=string)
        10. web.search (params: query)
        11. conversational.chat
        12. unknown (use if you cannot confidently determine the intent)
        """
        
        self.system_prompt = f"""
        You are Sweetie, a witty, sophisticated, professional-but-personable AI assistant. 
        You occasionally call the user "boss". Your responses must be concise.
        
        Your job is to parse the user's input and return STRICT JSON.
        
        {self.intent_schema}
        
        JSON SCHEMA:
        {{
            "intent": "<intent_name>",
            "parameters": {{}},
            "confidence": <float 0.0-1.0>,
            "conversational_reply": "<what Sweetie should say out loud>"
        }}
        """

    def fast_path(self, text):
        t = text.lower().strip()
        
        # Confirm / Cancel
        if t in ["yes", "yep", "do it", "confirm", "sure"]:
            return {"intent": "system.confirm", "parameters": {}, "confidence": 1.0, "conversational_reply": "Done."}
        if t in ["no", "nope", "cancel", "stop"]:
            return {"intent": "system.cancel", "parameters": {}, "confidence": 1.0, "conversational_reply": "Cancelled."}
            
        # Mute
        if re.search(r'\b(mute|unmute)\b', t):
            state = "on" if "mute" in t and "unmute" not in t else "off"
            return {"intent": "system.mute", "parameters": {"state": state}, "confidence": 1.0, "conversational_reply": "Got it."}
            
        # Volume
        if re.search(r'volume up|turn it up|louder', t):
            return {"intent": "system.volume", "parameters": {"direction": "up"}, "confidence": 1.0, "conversational_reply": "Turning it up."}
        if re.search(r'volume down|turn it down|quieter', t):
            return {"intent": "system.volume", "parameters": {"direction": "down"}, "confidence": 1.0, "conversational_reply": "Turning it down."}
            
        # Lock
        if re.search(r'\b(lock screen|lock computer|lock the pc|lock my pc)\b', t):
            return {"intent": "system.lock", "parameters": {}, "confidence": 1.0, "conversational_reply": "Locking the screen, boss."}
            
        # Screenshot
        if re.search(r'\b(take a screenshot|screenshot)\b', t):
            return {"intent": "system.screenshot", "parameters": {}, "confidence": 1.0, "conversational_reply": "Snap!"}
            
        # Open App (catch all)
        match = re.search(r'^open (.*?)[.!?]*$', t)
        if match:
            return {"intent": "app.open", "parameters": {"app_name": match.group(1)}, "confidence": 0.9, "conversational_reply": f"Opening {match.group(1)}."}
            
        # Close App (catch all)
        match = re.search(r'^close (.*?)[.!?]*$', t)
        if match:
            batch = "all" in match.group(1) or "everything" in match.group(1)
            return {"intent": "app.close", "parameters": {"app_name": match.group(1), "batch": batch}, "confidence": 0.9, "conversational_reply": f"Closing {match.group(1)}."}
            
        # App Stats
        match = re.search(r'how much (ram|memory).*? (.*?)[.!?]*$', t)
        if match:
            return {"intent": "app.stats", "parameters": {"app_name": match.group(2)}, "confidence": 0.9, "conversational_reply": "Let me check."}
            
        return None

    def smart_path(self, text, memory_context):
        prompt = f"{memory_context}\n\nUser Input: {text}\n\nRespond ONLY with valid JSON."
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": self.system_prompt,
            "stream": False,
            "format": "json"
        }
        
        try:
            response = requests.post(f"{self.ollama_host}/api/generate", json=payload, timeout=45)
            if response.status_code == 200:
                result = response.json().get("response", "{}")
                try:
                    data = json.loads(result)
                    return data
                except json.JSONDecodeError:
                    logger.error(f"Ollama returned invalid JSON: {result}")
            else:
                logger.error(f"Ollama API Error: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to reach Ollama: {e}")
            
        return None

    def route(self, text, memory_context=""):
        # 1. Try Fast Path
        start_time = time.time()
        fast_result = self.fast_path(text)
        if fast_result:
            logger.info(f"Routed via FAST PATH in {(time.time() - start_time)*1000:.1f}ms")
            return fast_result
            
        # 2. Try Smart Path
        logger.info("Falling back to SMART PATH (Ollama)...")
        start_time = time.time()
        smart_result = self.smart_path(text, memory_context)
        
        if smart_result:
            logger.info(f"Routed via SMART PATH in {time.time() - start_time:.2f}s")
            
            # Ensure required fields exist
            if "confidence" not in smart_result:
                smart_result["confidence"] = 0.5
            if "conversational_reply" not in smart_result:
                smart_result["conversational_reply"] = "I'm not quite sure what you mean, boss."
                
            return smart_result
            
        # 3. Fallback completely
        return {
            "intent": "unknown",
            "parameters": {},
            "confidence": 0.0,
            "conversational_reply": "Sorry, my brain isn't responding right now. Make sure Ollama is running."
        }
