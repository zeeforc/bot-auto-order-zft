"""
Security utilities untuk Bot Auto Order
Validasi callback, hashing, dan security-related functions
"""
import hmac
import hashlib
from typing import Optional


def hash_password(password: str) -> str:
    """Hash password menggunakan SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """Verify password dengan hashed value"""
    return hash_password(password) == hashed


def generate_hmac_signature(data: str, secret: str) -> str:
    """Generate HMAC signature untuk webhook validation"""
    return hmac.new(
        secret.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()


def verify_webhook_signature(
    payload: str,
    signature: str,
    secret: str
) -> bool:
    """Verify webhook signature dari payment gateway"""
    expected_signature = generate_hmac_signature(payload, secret)
    return hmac.compare_digest(signature, expected_signature)


def validate_callback_token(token: str, expected_token: str) -> bool:
    """Validate Telegram callback query token"""
    return hmac.compare_digest(token, expected_token)
