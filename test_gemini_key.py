#!/usr/bin/env python3
"""
Simple test script to check a Google Generative Language (Gemini) API key or service account.
Usage:
  - With env vars:
      export GEMINI_API_URL="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
      export GEMINI_API_KEY="YOUR_API_KEY"
      python test_gemini_key.py
  - Or pass as arguments:
      python test_gemini_key.py --url URL --key YOUR_API_KEY

Notes:
  - This script by default sends the API key in the X-Goog-Api-Key header (simple test).
  - For production use prefer service account OAuth. See comments below if you want OAuth.
"""
import os
import sys
import json
import argparse
import requests
from dotenv import load_dotenv
load_dotenv()


DEFAULT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

def extract_text_from_google_response(data):
    # Try a few common shapes returned by Google Generative API
    out = ""
    if isinstance(data, dict):
        candidates = data.get("candidates") or data.get("outputs") or []
        if isinstance(candidates, list) and candidates:
            for cand in candidates:
                if isinstance(cand, dict):
                    content = cand.get("content") or cand.get("output") or []
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("text"):
                                out += item["text"]
                            elif isinstance(item, str):
                                out += item
                    if not out and cand.get("text"):
                        out += cand.get("text", "")
                elif isinstance(cand, str):
                    out += cand
    return out.strip()

def main():
    p = argparse.ArgumentParser(description="Test Gemini (Google Generative) API key connectivity.")
    p.add_argument("--url", "-u", help="Full Gemini generateContent URL", default=os.getenv("GEMINI_API_URL", DEFAULT_URL))
    p.add_argument("--key", "-k", help="API key to send in X-Goog-Api-Key header", default=os.getenv("GEMINI_API_KEY"))
    p.add_argument("--prompt", "-p", help="Prompt text to send (default: short test)", default="Return the single word: OK")
    args = p.parse_args()

    if not args.key:
        print("ERROR: No API key provided. Set GEMINI_API_KEY env var or pass --key.", file=sys.stderr)
        sys.exit(2)

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": args.key
    }

    payload = {
        "contents": [
            { "parts": [ { "text": args.prompt } ] }
        ]
    }

    print(f"Testing endpoint: {args.url}")
    try:
        resp = requests.post(args.url, headers=headers, json=payload, timeout=30)
    except requests.exceptions.RequestException as e:
        print(f"Network error when calling the endpoint: {e}", file=sys.stderr)
        sys.exit(3)

    print(f"HTTP {resp.status_code}")
    if resp.status_code == 200:
        try:
            data = resp.json()
        except ValueError:
            print("Response not JSON; raw response:")
            print(resp.text)
            sys.exit(0)
        text = extract_text_from_google_response(data)
        if text:
            print("Success: model returned text:")
            print(text)
        else:
            print("Success: got JSON response but couldn't extract plain text. Full JSON below:")
            print(json.dumps(data, indent=2))
        sys.exit(0)
    elif resp.status_code == 401:
        print("Unauthorized (401). The API key was rejected.", file=sys.stderr)
        print("Common fixes to try:", file=sys.stderr)
        print("- Verify the API key value is correct and not expired/rotated.", file=sys.stderr)
        print("- In Google Cloud Console: enable the Generative Language API (or PaLM/Generative AI) for the project.", file=sys.stderr)
        print("- Ensure billing is enabled for the project.", file=sys.stderr)
        print("- Check API key restrictions (APIs, HTTP referrers, IPs); remove restrictions for testing.", file=sys.stderr)
        print("- Alternatively use a service account and OAuth token (see comments in script).", file=sys.stderr)
        print("Response body (maybe contains more details):", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(4)
    else:
        print("Non-200 response; printing body for debugging:")
        try:
            print(json.dumps(resp.json(), indent=2))
        except Exception:
            print(resp.text)
        sys.exit(5)

if __name__ == "__main__":
    main()

# ---- Notes on using OAuth/service account instead of API key (optional) ----
# If you prefer service-account OAuth (recommended for server apps), install google-auth:
#   pip install google-auth
# Then you can replace the header-building block with code that loads credentials and refreshes a token:
#
# from google.auth.transport.requests import Request
# from google.oauth2 import service_account
# SERVICE_ACCOUNT_FILE = "/path/to/service-account.json"
# creds = service_account.Credentials.from_service_account_file(
#     SERVICE_ACCOUNT_FILE,
#     scopes=["https://www.googleapis.com/auth/cloud-platform"]
# )
# creds.refresh(Request())
# headers = {"Content-Type": "application/json", "Authorization": f"Bearer {creds.token}"}
#
# Use that headers dict to call the same endpoint.