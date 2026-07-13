import logging
import logging.handlers
import os
import sys

def setup_logger(log_level="INFO"):
    os.makedirs("logs", exist_ok=True)
    
    logger = logging.getLogger("sweetie")
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    
    # Avoid adding duplicate handlers if setup is called multiple times
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        # File Handler (rotating log, max 5MB, keep 3 backups)
        file_handler = logging.handlers.RotatingFileHandler(
            "logs/sweetie.log", maxBytes=5*1024*1024, backupCount=3
        )
        file_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
    return logger
