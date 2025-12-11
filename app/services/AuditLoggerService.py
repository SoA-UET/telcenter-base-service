"""
Audit Logger Service
Logs all actions for audit and security purposes
"""

import logging
from datetime import datetime
from typing import Optional
import json


class AuditLogger:
    """
    Audit logger for security and compliance tracking.
    All authentication and customer management actions should be logged.
    """
    
    def __init__(self, service_name: str = "CustomerIdentityService"):
        self.service_name = service_name
        
        # Configure logger
        self.logger = logging.getLogger(f"audit.{service_name}")
        self.logger.setLevel(logging.INFO)
        
        # Create file handler for audit logs
        file_handler = logging.FileHandler('audit.log', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers if not already added
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def _format_log_entry(
        self,
        action: str,
        customer_id: Optional[str] = None,
        phone_number: Optional[str] = None,
        status: str = "success",
        details: Optional[dict] = None,
        error: Optional[str] = None
    ) -> dict:
        """Format a log entry with standard fields"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "service": self.service_name,
            "action": action,
            "status": status,
        }
        
        if customer_id:
            entry["customer_id"] = customer_id
        
        if phone_number:
            # Mask phone number for privacy (show only last 4 digits)
            masked = phone_number[:-4] + "****" if len(phone_number) > 4 else "****"
            entry["phone_number"] = masked
        
        if details:
            entry["details"] = details
        
        if error:
            entry["error"] = error
        
        return entry
    
    def log_registration(
        self,
        phone_number: str,
        customer_id: Optional[str] = None,
        status: str = "success",
        error: Optional[str] = None
    ):
        """Log customer registration attempt"""
        entry = self._format_log_entry(
            action="REGISTER",
            customer_id=customer_id,
            phone_number=phone_number,
            status=status,
            error=error
        )
        
        if status == "success":
            self.logger.info(json.dumps(entry, ensure_ascii=False))
        else:
            self.logger.warning(json.dumps(entry, ensure_ascii=False))
    
    def log_login(
        self,
        phone_number: str,
        customer_id: Optional[str] = None,
        status: str = "success",
        error: Optional[str] = None,
        login_method: str = "password"
    ):
        """Log customer login attempt"""
        entry = self._format_log_entry(
            action="LOGIN",
            customer_id=customer_id,
            phone_number=phone_number,
            status=status,
            details={"method": login_method},
            error=error
        )
        
        if status == "success":
            self.logger.info(json.dumps(entry, ensure_ascii=False))
        else:
            self.logger.warning(json.dumps(entry, ensure_ascii=False))
    
    def log_oauth_login(
        self,
        provider: str,
        email: Optional[str] = None,
        customer_id: Optional[str] = None,
        status: str = "success",
        error: Optional[str] = None
    ):
        """Log OAuth login attempt"""
        details = {"provider": provider}
        if email:
            # Mask email for privacy
            parts = email.split('@')
            if len(parts) == 2:
                masked_email = parts[0][:2] + "***@" + parts[1]
                details["email"] = masked_email
        
        entry = self._format_log_entry(
            action="OAUTH_LOGIN",
            customer_id=customer_id,
            status=status,
            details=details,
            error=error
        )
        
        if status == "success":
            self.logger.info(json.dumps(entry, ensure_ascii=False))
        else:
            self.logger.warning(json.dumps(entry, ensure_ascii=False))
    
    def log_validation_error(
        self,
        action: str,
        error_type: str,
        phone_number: Optional[str] = None
    ):
        """Log validation errors"""
        entry = self._format_log_entry(
            action=action,
            phone_number=phone_number,
            status="validation_error",
            details={"error_type": error_type}
        )
        self.logger.warning(json.dumps(entry, ensure_ascii=False))
    
    def log_security_event(
        self,
        event_type: str,
        customer_id: Optional[str] = None,
        phone_number: Optional[str] = None,
        details: Optional[dict] = None
    ):
        """Log security-related events"""
        entry = self._format_log_entry(
            action="SECURITY_EVENT",
            customer_id=customer_id,
            phone_number=phone_number,
            status="alert",
            details={"event_type": event_type, **(details or {})}
        )
        self.logger.warning(json.dumps(entry, ensure_ascii=False))
    
    def log_error(
        self,
        action: str,
        error: str,
        customer_id: Optional[str] = None,
        phone_number: Optional[str] = None
    ):
        """Log general errors"""
        entry = self._format_log_entry(
            action=action,
            customer_id=customer_id,
            phone_number=phone_number,
            status="error",
            error=error
        )
        self.logger.error(json.dumps(entry, ensure_ascii=False))
