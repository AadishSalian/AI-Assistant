import re
import requests
import json
import logging
import time

logger = logging.getLogger("sweetie.intent")

class IntentRouter:
    def __init__(self, ollama_host="http://localhost:11434", model="phi3:mini"):
        import os
        self.ollama_host = ollama_host
        self.model = model
        
        self.corrections_file = "data/corrections.json"
        self.corrections = {}
        if os.path.exists(self.corrections_file):
            try:
                with open(self.corrections_file, 'r') as f:
                    self.corrections = json.load(f)
            except Exception:
                pass
                
        # Load personality
        personality_text = "You are Sweetie, a witty, sophisticated, professional-but-personable AI assistant."
        try:
            with open("personality.md", "r") as f:
                personality_text = f.read()
        except Exception:
            pass

        
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
        12. window.position (params: layout="left"|"right"|"center"|"maximize"|"minimize", target_window=string)
        13. window.monitor (params: monitor_index=int)
        14. desktop.switch (params: target=int|"next"|"previous")
        15. desktop.create
        16. screenshot.capture (params: mode="fullscreen"|"window"|"region", target_window="app_name if applicable")
        17. file.search (params: query=string, extension=string, days_ago=int)
        18. file.open_folder (params: folder_name=string)
        19. file.organize (params: folder_name=string)
        20. file.bulk_operation (params: action="move"|"delete", source_folder=string, destination_folder=string, extension=string)
        21. desktop.close
        22. clarification_needed
        23. unknown (use if you cannot confidently determine the intent)
        """
        
        self.system_prompt = f"""
        {personality_text}
        
        Your job is to parse the user's input and return STRICT JSON.
        
        CRITICAL RULE: If the user is just making small talk, greeting you, saying goodbye, or saying something that doesn't clearly map to a specific system command, you MUST use the intent "conversational.chat". Do NOT hallucinate commands.
        
        {self.intent_schema}
        
        JSON SCHEMA:
        {{
            "intent": "<intent_name>",
            "parameters": {{}},
            "confidence": <float 0.0-1.0>,
            "conversational_reply": "<what Sweetie should say out loud>"
        }}
        """

    def detect_mood(self, text):
        t = text.lower()
        frustrated_keywords = ['now', 'hurry', 'urgent', 'fuck', 'shit', 'damn', 'why', 'stupid', 'slow']
        if any(kw in t.split() for kw in frustrated_keywords) or '!' in text or text.isupper():
            return "frustrated"
        return "casual"
        
    def _save_corrections(self):
        import os
        os.makedirs(os.path.dirname(self.corrections_file), exist_ok=True)
        with open(self.corrections_file, 'w') as f:
            json.dump(self.corrections, f, indent=4)

    def fast_path(self, text, memory=None):
        t = text.lower().strip()
        
        # Check for corrections ("no I meant X")
        correction_match = re.match(r'^(?:no\s*,?\s*i\s*meant|no\s*,?\s*open|actually\s*i\s*meant|wrong\s*,?\s*do)\s+(.*)', t)
        if correction_match and memory and memory.history:
            intended_action = correction_match.group(1).strip()
            last_exchange = memory.history[-1]
            last_user_text = last_exchange['user'].lower().strip()
            
            # Save the mapping: When I said <last_user_text>, I meant <intended_action>
            self.corrections[last_user_text] = intended_action
            self._save_corrections()
            
            # Now treat this turn as if the user just said the intended action
            t = intended_action
            text = intended_action
            
        # Apply any learned corrections
        if t in self.corrections:
            t = self.corrections[t]
            text = t
            
        # Confirm / Cancel
        if t in ["yes", "yep", "do it", "confirm", "sure"]:
            return {"intent": "system.confirm", "parameters": {}, "confidence": 1.0, "conversational_reply": "Done."}
        if t in ["no", "nope", "cancel", "stop"]:
            return {"intent": "system.cancel", "parameters": {}, "confidence": 1.0, "conversational_reply": "Cancelled."}
            
        # Bare keywords
        if t in ["volume", "sound", "brightness", "screen"]:
            return {"intent": "clarification_needed", "parameters": {}, "confidence": 1.0, "conversational_reply": f"What would you like me to do with the {t}?"}
            
        # Mute
        if re.search(r'\b(mute|unmute)\b', t):
            state = "on" if "mute" in t and "unmute" not in t else "off"
            return {"intent": "system.mute", "parameters": {"state": state}, "confidence": 1.0, "conversational_reply": "Got it."}
        # Volume
        match = re.search(r'(?:set )?volume (?:to )?(\d+)', t)
        if match:
            return {"intent": "system.volume", "parameters": {"level": int(match.group(1))}, "confidence": 1.0}
        if re.search(r'volume up|turn it up|louder|increase(?: the)? volume|raise(?: the)? volume', t):
            return {"intent": "system.volume", "parameters": {"direction": "up"}, "confidence": 1.0}
        if re.search(r'volume down|turn it down|quieter|decrease(?: the)? volume|lower(?: the)? volume', t):
            return {"intent": "system.volume", "parameters": {"direction": "down"}, "confidence": 1.0}
            
        # Brightness
        match = re.search(r'(?:set )?brightness (?:to )?(\d+)', t)
        if match:
            return {"intent": "system.brightness", "parameters": {"level": int(match.group(1))}, "confidence": 1.0}
        if re.search(r'brightness up|brighter|screen brighter|increase(?: the)? brightness|raise(?: the)? brightness', t):
            return {"intent": "system.brightness", "parameters": {"direction": "up"}, "confidence": 1.0}
        if re.search(r'brightness down|dimmer|screen dimmer|decrease(?: the)? brightness|lower(?: the)? brightness', t):
            return {"intent": "system.brightness", "parameters": {"direction": "down"}, "confidence": 1.0}
            
        # Power
        if re.search(r'\b(lock screen|lock computer|lock the pc|lock my pc)\b', t):
            return {"intent": "system.power", "parameters": {"action": "lock"}, "confidence": 1.0, "conversational_reply": "Are you sure you want to lock the screen?"}
        if re.search(r'\b(sleep|go to sleep|put pc to sleep)\b', t):
            return {"intent": "system.power", "parameters": {"action": "sleep"}, "confidence": 1.0, "conversational_reply": "Are you sure you want to go to sleep?"}
        if re.search(r'\b(restart|reboot)\b', t):
            return {"intent": "system.power", "parameters": {"action": "restart"}, "confidence": 1.0, "conversational_reply": "Are you sure you want to restart?"}
        if re.search(r'\b(shut down|shutdown|turn off)\b', t):
            return {"intent": "system.power", "parameters": {"action": "shutdown"}, "confidence": 1.0, "conversational_reply": "Are you sure you want to shut down?"}
            
        # System Info
        if re.search(r'\b(system status|how is my system|how\'s my system|system info)\b', t):
            return {"intent": "system.info", "parameters": {}, "confidence": 1.0}
            
        # Schedule
        match = re.search(r'\b(?:remind me|set a reminder) (?:to )?(.*?) (in|at|every) (.*)\b', t)
        if match:
            task = match.group(1).strip()
            time_str = f"{match.group(2)} {match.group(3)}".strip()
            return {"intent": "system.schedule", "parameters": {"task": task, "time": time_str}, "confidence": 0.9}
        # Screenshot (Phase 7)
        match = re.search(r'(take a )?screenshot of (the )?(.*) window', t)
        if match:
            target = match.group(3).strip()
            return {"intent": "screenshot.capture", "parameters": {"mode": "window", "target_window": target}, "confidence": 0.9}
            
        if "screenshot" in t:
            if "region" in t or "area" in t or "select" in t:
                return {"intent": "screenshot.capture", "parameters": {"mode": "region"}, "confidence": 0.9, "conversational_reply": "Select the region to capture."}
            elif "window" in t or "app" in t:
                return {"intent": "screenshot.capture", "parameters": {"mode": "window", "target_window": "current"}, "confidence": 0.9}
            else:
                return {"intent": "screenshot.capture", "parameters": {"mode": "fullscreen"}, "confidence": 0.9}
            
        # File Management (Phase 8)
        if re.search(r'\b(?:clean up|organize) (?:my |the )?(.*?) folder\b', t):
            match = re.search(r'\b(?:clean up|organize) (?:my |the )?(.*?) folder\b', t)
            return {"intent": "file.organize", "parameters": {"folder_name": match.group(1).strip()}, "confidence": 0.9, "conversational_reply": "Let me check that folder."}
            
        if re.search(r'\bopen (?:my |the )?(.*?) folder\b', t):
            match = re.search(r'\bopen (?:my |the )?(.*?) folder\b', t)
            return {"intent": "file.open_folder", "parameters": {"folder_name": match.group(1).strip()}, "confidence": 0.9}
            
        if re.search(r'\b(?:find|search for) (?:my |the )?(.*)\b', t):
            match = re.search(r'\b(?:find|search for) (?:my |the )?(.*)\b', t)
            return {"intent": "file.search", "parameters": {"query": match.group(1).strip()}, "confidence": 0.9, "conversational_reply": "Searching..."}

        if "create a new desktop" in t or "new virtual desktop" in t:
            return {"intent": "desktop.create", "parameters": {}, "confidence": 0.9}
            
        if "close the desktop" in t or "close this desktop" in t or "close virtual desktop" in t:
            return {"intent": "desktop.close", "parameters": {}, "confidence": 0.9, "conversational_reply": "Closing desktop."}

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
            
        # Window Management (Phase 6)
        match = re.search(r'(snap|move|put) (.*?) to the (left|right|top|bottom|center)', t)
        if match:
            target = match.group(2)
            for word in ['window', 'the', 'this', 'that', 'it', 'app', 'application']:
                target = target.replace(word, '')
            target = target.strip()
            if not target: target = 'current'
            return {"intent": "window.position", "parameters": {"layout": match.group(3), "target_window": target}, "confidence": 0.9}
            
        if "maximize" in t:
            match = re.search(r'maximize\s*(.*)', t)
            target = match.group(1) if match else ''
            for word in ['window', 'the', 'this', 'that', 'it', 'app', 'application']:
                target = target.replace(word, '')
            target = target.strip()
            if not target: target = 'current'
            return {"intent": "window.position", "parameters": {"layout": "maximize", "target_window": target}, "confidence": 0.9, "conversational_reply": "Maximizing."}

        if "minimize" in t:
            match = re.search(r'minimize\s*(.*)', t)
            target = match.group(1) if match else ''
            for word in ['window', 'the', 'this', 'that', 'it', 'app', 'application']:
                target = target.replace(word, '')
            target = target.strip()
            if not target: target = 'current'
            return {"intent": "window.position", "parameters": {"layout": "minimize", "target_window": target}, "confidence": 0.9, "conversational_reply": "Minimizing."}

        match = re.search(r'move (.*) to (monitor|screen) (\d+)', t)
        if match:
            target = match.group(1)
            for word in ['window', 'the', 'this', 'that', 'it', 'app', 'application']:
                target = target.replace(word, '')
            target = target.strip()
            if not target: target = 'current'
            return {"intent": "window.monitor", "parameters": {"monitor_index": int(match.group(3)), "target_window": target}, "confidence": 0.9}
            
        match = re.search(r'switch to desktop (\d+)', t)
        if match:
            return {"intent": "desktop.switch", "parameters": {"target": int(match.group(1))}, "confidence": 0.9}
            
        return None

    def smart_path(self, text, memory_context, mood):
        # Inject mood modifier into system prompt
        current_system_prompt = self.system_prompt
        if mood == "frustrated":
            current_system_prompt += "\n\nMOOD ALERT: The user is currently frustrated or rushed. Drop all teasing/sass. Be extremely fast, supportive, and concise. Do not joke."
            
        prompt = f"{memory_context}\n\nUser Input: {text}\n\nRespond ONLY with valid JSON."
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": current_system_prompt,
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

    def route(self, text, memory=None):
        memory_context = memory.get_context_string() if memory else ""
        mood = self.detect_mood(text)
        
        # 1. Try Fast Path
        start_time = time.time()
        fast_result = self.fast_path(text, memory)
        if fast_result:
            logger.info(f"Routed via FAST PATH in {(time.time() - start_time)*1000:.1f}ms (Mood: {mood})")
            return fast_result
            
        # 2. Try Smart Path
        logger.info(f"Falling back to SMART PATH (Ollama)... (Mood: {mood})")
        start_time = time.time()
        smart_result = self.smart_path(text, memory_context, mood)
        
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
