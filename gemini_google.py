import os
import json
import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

# Reads environment variables:
# GEMINI_API_URL: full Google generateContent URL
# GEMINI_API_KEY: API key (optional)
# GOOGLE_SERVICE_ACCOUNT_FILE: path to service account JSON (optional)
# USE_GOOGLE_API_KEY: "1" (default) to prefer API key header, "0" to force OAuth

GEMINI_API_URL = os.environ.get("GEMINI_API_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
USE_GOOGLE_API_KEY = os.environ.get("USE_GOOGLE_API_KEY", "1").lower() in ("1", "true", "yes")

def call_gemini(prompt):
    """
    Call Google Generative Language (generateContent).
    - If GEMINI_API_KEY is provided and USE_GOOGLE_API_KEY is true, sends X-Goog-Api-Key header.
    - Otherwise uses service account JSON at SERVICE_ACCOUNT_FILE to get an OAuth token.
    Returns string output (text) or JSON string on fallback.
    """
    if not GEMINI_API_URL:
        raise RuntimeError("GEMINI_API_URL is not set in environment")

    headers = {"Content-Type": "application/json"}

    # Prefer API key header if provided and enabled
    if GEMINI_API_KEY and USE_GOOGLE_API_KEY:
        headers["X-Goog-Api-Key"] = GEMINI_API_KEY
    else:
        # Use service account OAuth
        if not SERVICE_ACCOUNT_FILE:
            raise RuntimeError("No API key set and no service account file provided. Set GEMINI_API_KEY or GOOGLE_SERVICE_ACCOUNT_FILE.")
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        creds.refresh(Request())
        headers["Authorization"] = f"Bearer {creds.token}"

    payload = {
        "contents": [
            { "parts": [ { "text": prompt } ] }
        ]
    }

    resp = requests.post(GEMINI_API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    # Extract model text from Google-style response
    text_out = ""
    candidates = data.get("candidates") or data.get("outputs") or []
    if isinstance(candidates, list) and candidates:
        for cand in candidates:
            if isinstance(cand, dict):
                content = cand.get("content") or cand.get("output") or []
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("text"):
                            text_out += item["text"]
                        elif isinstance(item, str):
                            text_out += item
                if not text_out and cand.get("text"):
                    text_out += cand["text"]
            elif isinstance(cand, str):
                text_out += cand

    if not text_out:
        # fallback to top-level text fields
        for k in ("output", "text", "response", "result"):
            v = data.get(k) if isinstance(data, dict) else None
            if isinstance(v, str) and v.strip():
                text_out = v
                break

    return text_out or json.dumps(data, indent=2)