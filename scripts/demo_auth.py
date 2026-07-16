#!/usr/bin/env python3
"""
Shared demo-account login helper for demo verification/test scripts.
Replaces the old mock-token auth bypass with a real POST /api/v1/auth/login call.
"""

import requests

from src.config.settings import settings

DEMO_PASSWORD = settings.demo_password


def login(email: str, password: str = None, base_url: str = "http://localhost:8000") -> dict:
    """Log in a demo account and return the login response
    (access_token, user_id, email, role)."""
    if password is None:
        password = settings.demo_password
    if not password:
        raise SystemExit(
            "DEMO_PASSWORD not set — add it to .env (see README)"
        )
    response = requests.post(
        f"{base_url}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
