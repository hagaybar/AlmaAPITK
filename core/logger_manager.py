import logging
import logging.handlers
from queue import Queue

class LoggerManager:
    """
    LoggerManager handles the logging setup and configuration for the ETL process.
    """
    
    def __init__(self, log_file: str = "alma_d_toolkit.log") -> None:
        self.logger = logging.getLogger("alma_d_toolkit")
        self.logger.handlers.clear()  # Clear existing handlers to avoid duplicate log records
        self.logger.setLevel(logging.DEBUG)
        self.log_queue = Queue()
        self.queue_handler = logging.handlers.QueueHandler(self.log_queue)
        self.file_handler = logging.FileHandler(log_file, encoding='utf-8')
        self.formatter = logging.Formatter('%(asctime)s %(levelname)s [%(threadName)s] %(message)s')
        
        self.file_handler.setFormatter(self.formatter)

        self.queue_listener = logging.handlers.QueueListener(self.log_queue, self.file_handler)
        self.queue_listener.start()

        self.logger.addHandler(self.queue_handler)

    def get_logger(self) -> logging.Logger:
        """
        Get the configured logger.

        Returns:
            logging.Logger: Configured logger.
        """
        return self.logger

    def stop_listener(self) -> None:
        """
        Stop the QueueListener to ensure all log records are written to the log file.
        """
        self.queue_listener.stop()
