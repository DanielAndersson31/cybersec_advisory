import logging
import sys
import json
from logging.handlers import TimedRotatingFileHandler

class JsonFormatter(logging.Formatter):
    """
    Formats log records as a single line of JSON.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_object = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "funcName": record.funcName,
            "lineno": record.lineno,
        }
        if record.exc_info:
            log_object['exc_info'] = self.formatException(record.exc_info)
        
        return json.dumps(log_object)

def setup_logging(
    level: int = logging.INFO,
    log_to_console: bool = True,
    log_file_path: str = "logs/app.log.json"
):
    """
    Configures the root logger for the application.

    This should be called once when the application starts.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = []

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    if log_file_path:
        # Ensure the logs directory exists
        import os
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        
        file_handler = TimedRotatingFileHandler(
            log_file_path, when="midnight", interval=1, backupCount=7
        )
        json_formatter = JsonFormatter()
        file_handler.setFormatter(json_formatter)
        root_logger.addHandler(file_handler)