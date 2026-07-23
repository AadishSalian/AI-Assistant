import os
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import dateparser
import re

logger = logging.getLogger("sweetie.scheduler_manager")

class SchedulerManager:
    def __init__(self, api, event_queue):
        self.api = api
        self.event_queue = event_queue
        self.scheduler = BackgroundScheduler()
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Use SQLite for persistence
        self.scheduler.add_jobstore('sqlalchemy', url='sqlite:///data/jobs.sqlite')
        self.scheduler.start()
        logger.info("Task Scheduler started.")

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
