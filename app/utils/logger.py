from datetime import datetime

class Logger:
    """
    Simple logger for audit and security purposes
    """
    
    def __init__(self, name: str):
        self.name = name
    
    def info(self, message: str, **kwargs):
        """Log info level message"""
        timestamp = datetime.now().isoformat()
        extra = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        print(f"[{timestamp}] INFO [{self.name}] {message} {extra}")
    
    def warning(self, message: str, **kwargs):
        """Log warning level message"""
        timestamp = datetime.now().isoformat()
        extra = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        print(f"[{timestamp}] WARNING [{self.name}] {message} {extra}")
    
    def error(self, message: str, **kwargs):
        """Log error level message"""
        timestamp = datetime.now().isoformat()
        extra = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        print(f"[{timestamp}] ERROR [{self.name}] {message} {extra}")
    
    def audit(self, action: str, user_id: str = None, details: dict = None):
        """Log audit event"""
        timestamp = datetime.now().isoformat()
        user_info = f"user_id={user_id}" if user_id else "user_id=unknown"
        details_str = " ".join([f"{k}={v}" for k, v in (details or {}).items()])
        print(f"[{timestamp}] AUDIT [{self.name}] action={action} {user_info} {details_str}")
