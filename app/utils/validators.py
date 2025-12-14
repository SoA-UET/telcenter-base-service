import re
from typing import Optional, Tuple

class Validators:
    """Validation utilities for Customer Identity Service"""
    
    @staticmethod
    def validate_email(email: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Vietnamese email number format.
        Expected format: 10 digits starting with 0
        
        Returns:
            (is_valid, error_message)
        """
        if not email:
            return False, "Số điện thoại không được để trống"
        
        # Vietnamese email pattern: starts with 0, followed by 9 digits
        pattern = r'^0\d{9}$'
        if not re.match(pattern, email):
            return False, "Số điện thoại không hợp lệ (phải có 10 chữ số và bắt đầu bằng 0)"
        
        return True, None
    
    @staticmethod
    def validate_password(password: str) -> Tuple[bool, Optional[str]]:
        """
        Validate password strength.
        Requirements:
        - At least 8 characters
        - Contains at least one uppercase letter
        - Contains at least one lowercase letter
        - Contains at least one digit
        - Contains at least one special character
        
        Returns:
            (is_valid, error_message)
        """
        if not password:
            return False, "Mật khẩu không được để trống"
        
        if len(password) < 8:
            return False, "Mật khẩu phải có ít nhất 8 ký tự"
        
        if not re.search(r'[A-Z]', password):
            return False, "Mật khẩu phải chứa ít nhất một chữ cái viết hoa"
        
        if not re.search(r'[a-z]', password):
            return False, "Mật khẩu phải chứa ít nhất một chữ cái viết thường"
        
        if not re.search(r'\d', password):
            return False, "Mật khẩu phải chứa ít nhất một chữ số"
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Mật khẩu phải chứa ít nhất một ký tự đặc biệt"
        
        return True, None
    
    @staticmethod
    def validate_full_name(full_name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate full name.
        
        Returns:
            (is_valid, error_message)
        """
        if not full_name or not full_name.strip():
            return False, "Họ tên không được để trống"
        
        if len(full_name.strip()) < 2:
            return False, "Họ tên phải có ít nhất 2 ký tự"
        
        return True, None
    
    @staticmethod
    def validate_address(address: str) -> Tuple[bool, Optional[str]]:
        """
        Validate address.
        
        Returns:
            (is_valid, error_message)
        """
        if not address or not address.strip():
            return False, "Địa chỉ không được để trống"
        
        if len(address.strip()) < 5:
            return False, "Địa chỉ phải có ít nhất 5 ký tự"
        
        return True, None
    
    @staticmethod
    def validate_registration_data(email: str, password: str, 
                                   full_name: str, address: str) -> Tuple[bool, Optional[str]]:
        """
        Validate all registration data at once.
        
        Returns:
            (is_valid, error_message)
        """
        # Validate email number
        is_valid, error = Validators.validate_email(email)
        if not is_valid:
            return False, error
        
        # Validate password
        is_valid, error = Validators.validate_password(password)
        if not is_valid:
            return False, error
        
        # Validate full name
        is_valid, error = Validators.validate_full_name(full_name)
        if not is_valid:
            return False, error
        
        # Validate address
        is_valid, error = Validators.validate_address(address)
        if not is_valid:
            return False, error
        
        return True, None
