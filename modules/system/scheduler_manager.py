import os
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import dateparser
import re

logger = logging.getLogger("sweetie.scheduler_manager")

class SchedulerManager:
    def __init__(self, config, api, event_queue):
        self.config = config
        self.api = api
        self.event_queue = event_queue
        self.scheduler = BackgroundScheduler()
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Use SQLite for persistence
        self.scheduler.add_jobstore('sqlalchemy', url='sqlite:///data/jobs.sqlite')
        
        # Proactive Assistance Toggle
        if self.config.get('assistant', {}).get('proactive_suggestions', False):
            # Run the proactive check every hour
            self.scheduler.add_job(self._proactive_check, 'interval', hours=1, id='proactive_check', replace_existing=True)
            logger.info("Proactive suggestions enabled (checks every 1 hour).")
            
        self.scheduler.start()
        logger.info("Task Scheduler started.")

    def _proactive_check(self):
        """Analyzes memory to find common patterns and suggests an action."""
        import json
        try:
            with open("logs/memory.json", "r") as f:
                history = json.load(f)
        except Exception:
            return
            
        if not history:
            return
            
        # Very simple heuristic: find the most common intent in the last N exchanges
        intents = {}
        for ex in history[-20:]: # Look at recent history
            i = ex.get('intent')
            if i and i not in ['unknown', 'clarification_needed', 'conversational.chat']:
                intents[i] = intents.get(i, 0) + 1
                
        if not intents:
            return
            
        most_common = max(intents, key=intents.get)
        if intents[most_common] >= 3: # If they did it at least 3 times recently
            suggestion_text = f"Hey, you've been asking for {most_common} a lot. Want me to do that for you?"
            
            # Send to event queue so the main loop speaks it safely
            self.event_queue.put({
                'type': 'reminder',
                'message': suggestion_text
            })

    def add_reminder(self, task_description, time_string):
        """
        Parses a time string like 'in 20 minutes' or 'at 6pm' and schedules a reminder.
        """
        try:
            is_recurring = False
            # Very basic recurring check
            if "every day" in time_string.lower() or "daily" in time_string.lower():
                is_recurring = True
                # Clean up string for dateparser
                time_string = time_string.lower().replace("every day", "").replace("daily", "").strip()
                if time_string.startswith("at "):
                    time_string = time_string[3:].strip()
                if not time_string: 
                    time_string = "9:00 am" # fallback
                    
            parsed_time = dateparser.parse(time_string, settings={'PREFER_DATES_FROM': 'future'})
            
            if not parsed_time:
                return False, f"I couldn't understand the time."
                
            if not is_recurring and parsed_time < datetime.now():
                parsed_time += timedelta(days=1)
                
            job_id = f"reminder_{int(datetime.now().timestamp())}"
            
            if is_recurring:
                self.scheduler.add_job(
                    self._execute_reminder,
                    'cron',
                    hour=parsed_time.hour,
                    minute=parsed_time.minute,
                    args=[task_description],
                    id=job_id,
                    replace_existing=True
                )
                time_format = parsed_time.strftime("%I:%M %p")
                return True, f"Recurring reminder set for every day at {time_format}."
            else:
                self.scheduler.add_job(
                    self._execute_reminder,
                    'date',
                    run_date=parsed_time,
                    args=[task_description],
                    id=job_id,
                    replace_existing=True
                )
                
                # Check if it's today
                if parsed_time.date() == datetime.now().date():
                    time_format = parsed_time.strftime("%I:%M %p today")
                else:
                    time_format = parsed_time.strftime("%I:%M %p on %b %d")
                    
                return True, f"Reminder set for {time_format}."
                
        except Exception as e:
            logger.error(f"Failed to set reminder: {e}")
            return False, "Failed to schedule the reminder."

    def _execute_reminder(self, task_description):
        """Called by APScheduler when it's time to remind the user."""
        try:
            message = f"Reminder: {task_description}"
            logger.info(f"Queuing reminder: {message}")
            self.event_queue.put({"type": "reminder", "message": message})
        except Exception as e:
            logger.error(f"Error executing reminder: {e}")
            
    def shutdown(self):
        self.scheduler.shutdown()
