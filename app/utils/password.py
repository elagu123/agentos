"""
Password utilities for AgentOS
Secure password generation and validation
"""

import secrets
import string
from typing import Dict, Any

def generate_temp_password(length: int = 12) -> str:
    """
    Generate a secure temporary password

    Args:
        length: Password length (minimum 8, default 12)

    Returns:
        Secure temporary password
    """

    if length < 8:
        length = 8

    # Define character sets
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    symbols = "!@#$%^&*"

    # Ensure at least one character from each set
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(symbols)
    ]

    # Fill the rest randomly
    all_chars = lowercase + uppercase + digits + symbols
    for _ in range(length - 4):
        password.append(secrets.choice(all_chars))

    # Shuffle the password
    secrets.SystemRandom().shuffle(password)

    return ''.join(password)

def validate_password_strength(password: str) -> Dict[str, Any]:
    """
    Validate password strength

    Args:
        password: Password to validate

    Returns:
        Dict with validation results
    """

    result = {
        "is_valid": False,
        "score": 0,
        "feedback": [],
        "requirements": {
            "min_length": False,
            "has_uppercase": False,
            "has_lowercase": False,
            "has_digit": False,
            "has_symbol": False
        }
    }

    # Check minimum length
    if len(password) >= 8:
        result["requirements"]["min_length"] = True
        result["score"] += 20
    else:
        result["feedback"].append("Password must be at least 8 characters long")

    # Check for uppercase letters
    if any(c.isupper() for c in password):
        result["requirements"]["has_uppercase"] = True
        result["score"] += 20
    else:
        result["feedback"].append("Password must contain at least one uppercase letter")

    # Check for lowercase letters
    if any(c.islower() for c in password):
        result["requirements"]["has_lowercase"] = True
        result["score"] += 20
    else:
        result["feedback"].append("Password must contain at least one lowercase letter")

    # Check for digits
    if any(c.isdigit() for c in password):
        result["requirements"]["has_digit"] = True
        result["score"] += 20
    else:
        result["feedback"].append("Password must contain at least one digit")

    # Check for symbols
    if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        result["requirements"]["has_symbol"] = True
        result["score"] += 20
    else:
        result["feedback"].append("Password must contain at least one symbol")

    # Bonus points for length
    if len(password) >= 12:
        result["score"] += 10
    if len(password) >= 16:
        result["score"] += 10

    # Check if password meets all requirements
    result["is_valid"] = all(result["requirements"].values())

    return result