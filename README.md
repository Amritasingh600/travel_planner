# Flask Trip Planner (Gemini-powered)

This small Flask app collects a destination, preferences, days, budget and starting location, sends a structured prompt to the Gemini API, and displays the generated itinerary, popular dinner & stay recommendations, and a map/route link.

Prerequisites
- Python 3.10+
- A Gemini-compatible HTTP endpoint and API key (set environment variables below).
  - GEMINI_API_URL: Full URL to POST the prompt (e.g. your provider's generate endpoint).
  - GEMINI_API_KEY: API key / Bearer token.

Installation
1. Clone or copy these files.
2. Create a virtual environment and install requirements:
   python -m venv venv
   source venv/bin/activate   # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
3. Create `.env` (or export env vars) with GEMINI_API_URL and GEMINI_API_KEY. See `.env.example`.

Run
export FLASK_APP=app.py
export FLASK_ENV=development
# or use .env; the app reads environment variables using python-dotenv
flask run

How it works
- The server builds a prompt that asks Gemini to return a JSON object between markers ===JSON_START=== and ===JSON_END=== with keys:
  - itinerary: list of day-by-day items
  - popular_dinner_recommendations: list
  - popular_stays: list
  - travel_instructions: text steps to reach there from the origin
  - maps_query: a short query (destination) suitable for Google Maps
- The server attempts to extract that JSON. If extraction fails, the raw text from Gemini is shown.

Notes / Next steps
- Configure GEMINI_API_URL to the exact API endpoint your account supports and adjust the request body keys if required by the vendor.
- If you want integrated routing without opening Google Maps, integrate a routing service (e.g., Mapbox Directions API or OSRM).