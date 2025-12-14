import logging
from datetime import datetime
from typing import Any, Dict

class LoggingService:
    """
    Service for logging actions for audit and security purposes.
    All actions in the Customer Identity Service are logged.
    """
    
    def __init__(self, service_name: str = "CustomerIdentityService"):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        self.logger.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(console_handler)
    
    def log_info(self, message: str, extra: Dict[str, Any] = None):
        """Log informational message"""
        log_message = self._format_message(message, extra)
        self.logger.info(log_message)
    
    def log_warning(self, message: str, extra: Dict[str, Any] = None):
        """Log warning message"""
        log_message = self._format_message(message, extra)
        self.logger.warning(log_message)
    
    def log_error(self, message: str, extra: Dict[str, Any] = None):
        """Log error message"""
        log_message = self._format_message(message, extra)
        self.logger.error(log_message)
    
    def log_audit(self, action: str, user_id: str = None, details: Dict[str, Any] = None):
        """
        Log audit trail for security purposes
        
        Args:
            action: The action being performed (e.g., "USER_REGISTERED", "LOGIN_SUCCESS")
            user_id: The user performing the action
            details: Additional details about the action
        """
        audit_data = {
            "action": action,
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "details": details or {}
        }
        self.logger.info(f"AUDIT: {self._format_dict(audit_data)}")
    
    def _format_message(self, message: str, extra: Dict[str, Any] = None) -> str:
        """Format log message with extra data"""
        if extra:
            return f"{message} | {self._format_dict(extra)}"
        return message
    
    def _format_dict(self, data: Dict[str, Any]) -> str:
        """Format dictionary for logging"""
        return " | ".join([f"{k}={v}" for k, v in data.items()])
