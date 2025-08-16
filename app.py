#!/usr/bin/env python3
import os
import json
import re
from math import ceil
from urllib.parse import urlencode, quote_plus

from flask import Flask, render_template, request, redirect, url_for, flash
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

GEMINI_API_URL = os.environ.get("GEMINI_API_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Sample fallback response used only when the real API fails
SAMPLE_GEMINI_RAW = """===JSON_START===
{
  "destination_name": "Mathura, India",
  "maps_query": "Mathura,India",
  "itinerary": [
    { "day_number": 1, "summary": "Arrival and Janmabhoomi", "activities": ["Visit Shri Krishna Janmabhoomi","Evening aarti"], "approximate_cost": 500 },
    { "day_number": 2, "summary": "Vrindavan temples", "activities": ["Banke Bihari Temple","Prem Mandir"], "approximate_cost": 700 }
  ],
  "visit_sequence": [
    { "order": 1, "location_name": "Shri Krishna Janmabhoomi", "suggested_time": "Morning", "estimated_duration": "2 hours",
      "note": "Start early", "latitude": 27.4921, "longitude": 77.6745,
      "nearby_food_recommendations": [{"name":"Brijwasi Sweets","rating":4.2,"distance_m":300,"price_level":"₹","reason":"Famous for pedas"}]
    },
    { "order": 2, "location_name": "Banke Bihari Temple (Vrindavan)", "suggested_time": "Morning", "estimated_duration": "2 hours",
      "note": "Crowded, come early", "latitude": 27.5807, "longitude": 77.7061,
      "nearby_food_recommendations": [{"name":"Local stalls","rating":3.8,"distance_m":100,"price_level":"₹","reason":"Street snacks"}]
    }
  ],
  "popular_dinner_recommendations": [{"name":"Brijwasi Sweets","reason":"Local sweets","rating":4.2,"price_level":"₹"}],
  "popular_stays": [{"name":"Hotel Madhuvan","reason":"Comfortable near temples","rating":4.0,"price_level":"₹₹"}],
  "travel_instructions": [
    {"from":"Your origin","to":"Mathura Junction","transport":"Train/car","approx_time":"Varies","notes":"From Mathura Junction take a rickshaw to Janmabhoomi (~10-20 min)"}
  ]
}
===JSON_END==="""

# ----------------- Helpers -----------------
def strip_code_fences(text):
    """Remove wrapping triple-backtick fences if present."""
    if not isinstance(text, str):
        return text
    m = re.search(r"^```(?:json)?\s*(.*)\s*```$", text, re.S | re.I)
    if m:
        return m.group(1).strip()
    return text

def extract_text_from_api_response(data):
    """
    The Generative API responses vary in shape. Try several common locations
    and return the first plausible text blob we find.
    """
    if not data:
        return None
    if isinstance(data, str):
        return data

    checks = [
        ("candidates", 0, "content", "parts", 0, "text"),
        ("candidates", 0, "content", 0, "text"),
        ("candidates", 0, "text"),
        ("outputs", 0, "content", 0, "text"),
        ("outputs", 0, "text"),
        ("response", "text"),
        ("text",),
    ]

    for path in checks:
        cur = data
        ok = True
        try:
            for p in path:
                if isinstance(p, int):
                    cur = cur[p]
                else:
                    cur = cur.get(p) if isinstance(cur, dict) else None
                    if cur is None:
                        ok = False
                        break
            if ok and isinstance(cur, str) and cur.strip():
                return cur
        except Exception:
            continue

    # If none of the above worked, stringify the JSON and try to find an embedded code block there.
    try:
        return json.dumps(data, indent=2)
    except Exception:
        return str(data)

def extract_json_from_text(text):
    """
    Robust JSON extraction:
    - strip fenced code blocks
    - find marker-wrapped JSON between ===JSON_START=== and ===JSON_END===
    - otherwise find the first balanced {...} block
    """
    if not text or not isinstance(text, str):
        return None

    text = strip_code_fences(text).strip()

    marker_re = re.compile(r"===JSON_START===\s*(\{.*?\})\s*===JSON_END===", re.S)
    m = marker_re.search(text)
    if m:
        candidate = m.group(1)
        try:
            return json.loads(candidate)
        except Exception:
            try:
                cleaned = candidate.encode("utf-8").decode("unicode_escape")
                return json.loads(cleaned)
            except Exception:
                pass

    first = text.find("{")
    if first == -1:
        return None

    # Find first balanced JSON object (handles nested braces)
    stack = []
    end = -1
    for i in range(first, len(text)):
        ch = text[i]
        if ch == "{":
            stack.append("{")
        elif ch == "}":
            if stack:
                stack.pop()
            if not stack:
                end = i
                break
    if end != -1:
        candidate = text[first:end+1]
        try:
            return json.loads(candidate)
        except Exception:
            try:
                cleaned = candidate.encode("utf-8").decode("unicode_escape")
                return json.loads(cleaned)
            except Exception:
                pass

    return None

def normalize_visit_sequence(raw_seq):
    """
    Ensure visit_sequence is a list of dicts.
    - Handles strings, lists, and dicts.
    """
    if not raw_seq:
        return []

    normalized = []
    if isinstance(raw_seq, str):
        try:
            parsed = json.loads(raw_seq)
            raw_seq = parsed
        except Exception:
            parsed = extract_json_from_text(raw_seq)
            if isinstance(parsed, dict) and "visit_sequence" in parsed:
                raw_seq = parsed.get("visit_sequence") or []
            elif isinstance(parsed, list):
                raw_seq = parsed
            else:
                raw_seq = []

    if isinstance(raw_seq, dict):
        raw_seq = raw_seq.get("visit_sequence") or raw_seq.get("visits") or []

    if not isinstance(raw_seq, (list, tuple)):
        return []

    for item in raw_seq:
        if isinstance(item, dict):
            normalized.append(item)
            continue
        if isinstance(item, list):
            for it in item:
                if isinstance(it, dict):
                    normalized.append(it)
            continue
        if isinstance(item, str):
            parsed = None
            try:
                parsed = json.loads(item)
            except Exception:
                parsed = extract_json_from_text(item)
            if isinstance(parsed, dict):
                normalized.append(parsed)
            elif isinstance(parsed, list):
                for it in parsed:
                    if isinstance(it, dict):
                        normalized.append(it)
            else:
                kv_pairs = {}
                m = re.search(r"order\s*[:=]\s*(\d+)", item, re.I)
                if m:
                    kv_pairs["order"] = int(m.group(1))
                m2 = re.search(r'location_name\s*[:=]\s*["\']?([^,"\']+)["\']?', item, re.I)
                if m2:
                    kv_pairs["location_name"] = m2.group(1).strip()
                if kv_pairs:
                    normalized.append(kv_pairs)
    return normalized

# ---------- Gemini call ----------
def call_gemini(prompt):
    if (not GEMINI_API_URL) or (not GEMINI_API_KEY):
        raise RuntimeError("GEMINI_API_URL and GEMINI_API_KEY must be set as environment variables.")

    if "example" in GEMINI_API_URL or "your-gemini-endpoint" in GEMINI_API_URL:
        raise RuntimeError("GEMINI_API_URL appears to be a placeholder. Set it to the real Gemini endpoint.")

    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": GEMINI_API_KEY}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    resp = requests.post(GEMINI_API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    text = extract_text_from_api_response(data)
    text = strip_code_fences(text).strip() if isinstance(text, str) else text
    return text

# ---------- Flask routes ----------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/plan", methods=["POST"])
def plan():
    destination = request.form.get("destination", "").strip()
    preferences = request.form.get("preferences", "").strip()
    days = request.form.get("days", "").strip()
    budget = request.form.get("budget", "").strip()
    origin = request.form.get("origin", "").strip()

    if not destination:
        flash("Please provide a destination.")
        return redirect(url_for("index"))

    # Strict prompt with example (keeps model output structured)
    example = {
        "destination_name": "Place, Country",
        "maps_query": "Place,Country",
        "itinerary": [
            {"day_number": 1, "summary": "Sample day", "activities": ["Activity 1","Activity 2"], "approximate_cost": 100}
        ],
        "visit_sequence": [
            {"order": 1, "location_name": "Activity 1", "suggested_time": "Morning", "estimated_duration": "1 hour",
             "note": "Tip", "latitude": None, "longitude": None,
             "nearby_food_recommendations": [{"name":"Sample Eatery","rating":4.2,"distance_m":200,"price_level":"₹","reason":"Local favorite"}]}
        ],
        "popular_dinner_recommendations": [{"name":"Sample Eatery","reason":"Tasty local food","rating":4.2,"price_level":"₹"}],
        "popular_stays": [{"name":"Sample Hotel","reason":"Convenient","rating":4.0,"price_level":"₹₹"}],
        "travel_instructions": [{"from":"origin","to":"destination","transport":"train/taxi","approx_time":"Varies","notes":"Short note"}]
    }
    prompt = f"""
You are a travel planner assistant. Return ONLY a JSON object between the markers below:

===JSON_START===
<JSON>
===JSON_END===

Inputs:
- destination: "{destination}"
- preferences: "{preferences}"
- days: "{days}"
- budget: "{budget}"
- origin: "{origin if origin else 'not provided'}"

Schema example:
{json.dumps(example, indent=2)}

Requirements:
- Return exactly one JSON object between the markers. Do not include any other text.
- Ensure visit_sequence is an ordered array with numeric 'order' fields.
- For each visit_sequence item include at least one nearby_food_recommendation if possible.
- Use plain JSON (no markdown, no code fences). If you must include fences, they will be stripped.
"""

    try:
        gemini_raw = call_gemini(prompt)
    except Exception as e:
        flash(f"Gemini API error: {e}. Showing sample response.")
        gemini_raw = SAMPLE_GEMINI_RAW

    # Parse JSON out of model output
    parsed = extract_json_from_text(gemini_raw) or {}

    # Structured pieces
    itinerary = parsed.get("itinerary", []) or []
    raw_visit_sequence = parsed.get("visit_sequence", []) or []
    popular_foods = parsed.get("popular_dinner_recommendations", []) or []
    popular_stays = parsed.get("popular_stays", []) or []
    travel_instructions = parsed.get("travel_instructions", []) or []

    # Normalize visit_sequence robustly
    visit_sequence = normalize_visit_sequence(raw_visit_sequence)

    # If visit_sequence empty but itinerary present, build from itinerary
    try:
        days_n = int(days) if days and str(days).isdigit() else len(itinerary) or 1
    except Exception:
        days_n = len(itinerary) or 1

    if not visit_sequence and itinerary:
        # build a simple visit_sequence from itinerary activities
        idx = 1
        built = []
        for day in itinerary:
            activities = day.get("activities") or []
            for act in activities:
                name = act if isinstance(act, str) else act.get("name", f"Place {idx}")
                built.append({
                    "order": idx,
                    "location_name": name,
                    "suggested_time": "",
                    "estimated_duration": "",
                    "note": "",
                    "latitude": None,
                    "longitude": None,
                    "nearby_food_recommendations": (popular_foods or [])[:2]
                })
                idx += 1
        visit_sequence = built

    # Ensure itinerary exists for the requested days
    if not itinerary and visit_sequence:
        # distribute visits across days
        buckets = [[] for _ in range(days_n)]
        for i, v in enumerate(visit_sequence):
            day_index = min(days_n - 1, i // max(1, ceil(len(visit_sequence) / days_n)))
            name = v.get("location_name") if isinstance(v, dict) else f"Place {i+1}"
            buckets[day_index].append(name)
        itinerary = []
        for i in range(days_n):
            itinerary.append({
                "day_number": i + 1,
                "summary": f"Visit {len(buckets[i])} site(s)" if buckets[i] else "Free / explore",
                "activities": buckets[i] or ["Free time / local exploration"],
                "approximate_cost": None
            })

    # Final sort
    try:
        visit_sequence = sorted(visit_sequence, key=lambda x: int(x.get("order", 0)))
    except Exception:
        pass

    # Distribute into day buckets for meal suggestions
    visits_per_day = [[] for _ in range(days_n)]
    for idx, v in enumerate(visit_sequence):
        try:
            day_index = min(days_n - 1, idx // max(1, ceil(len(visit_sequence) / days_n)))
        except Exception:
            day_index = 0
        visits_per_day[day_index].append(v)

    # Build daily meal picks
    daily_meals = []
    for i in range(days_n):
        picks = []
        for v in visits_per_day[i]:
            if not isinstance(v, dict):
                continue
            nearby = v.get("nearby_food_recommendations") or []
            if isinstance(nearby, str):
                try:
                    nearby = json.loads(nearby)
                except Exception:
                    nearby = extract_json_from_text(nearby) or []
            if isinstance(nearby, dict):
                nearby = [nearby]
            if not isinstance(nearby, list) or not nearby:
                nearby = (popular_foods or [])[:2]
            for f in nearby[:3]:
                if not isinstance(f, dict):
                    continue
                picks.append({
                    "visit_location": v.get("location_name"),
                    "name": f.get("name"),
                    "rating": f.get("rating"),
                    "distance_m": f.get("distance_m"),
                    "price_level": f.get("price_level"),
                    "reason": f.get("reason"),
                })
        daily_meals.append({"day_number": i + 1, "meals": picks})

    # ---------- Improved node layout: grid / wrapping to reduce congestion ----------
    # We'll lay out nodes in a grid with a configurable max columns so the roadmap doesn't get a single cramped line.
    n_nodes = max(1, len(visit_sequence))
    max_cols = int(os.environ.get("TREASUREMAP_MAX_COLS", 4))  # default 4 columns, configurable via env
    cols = min(n_nodes, max_cols)
    rows = ceil(n_nodes / cols)
    svg_width = 940
    row_height = 160
    svg_height = max(220, rows * row_height + 40)
    margin_x = 60
    margin_top = 20
    usable_width = svg_width - margin_x * 2
    col_step = usable_width // max(1, cols - 1) if cols > 1 else 0

    node_positions = []
    for idx, v in enumerate(visit_sequence):
        if not isinstance(v, dict):
            continue
        col = idx % cols
        row = idx // cols
        x = margin_x + (col * col_step) if cols > 1 else svg_width // 2
        y = margin_top + (row * row_height) + (row * 10)
        node = {
            "order": v.get("order", idx + 1),
            "location_name": v.get("location_name") or v.get("name") or f"Place {idx+1}",
            "suggested_time": v.get("suggested_time", ""),
            "estimated_duration": v.get("estimated_duration", ""),
            "note": v.get("note", ""),
            "latitude": v.get("latitude"),
            "longitude": v.get("longitude"),
            "nearby_food_recommendations": v.get("nearby_food_recommendations") or [],
            "x": int(x),
            "y": int(y)
        }
        node_positions.append(node)

    # Build Google Maps links
    destination_for_search = (parsed.get("destination_name") or parsed.get("maps_query") or destination).strip()
    def build_maps_query(q):
        if not q:
            return ""
        q = str(q).strip()
        if re.match(r"^\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*$", q):
            return q.replace(" ", "")
        return quote_plus(q)
    destination_for_dirs = parsed.get("maps_query") or parsed.get("destination_name") or destination
    maps_link = None
    maps_search_link = None
    maps_iframe_src = None
    if destination_for_dirs:
        params = {"api": 1, "destination": build_maps_query(destination_for_dirs)}
        if origin:
            params["origin"] = origin
        params["travelmode"] = "driving"
        maps_link = "https://www.google.com/maps/dir/?" + urlencode(params)
    if destination_for_search:
        maps_search_link = "https://www.google.com/maps/search/?api=1&query=" + build_maps_query(destination_for_search)
        maps_iframe_src = maps_search_link

    # Travel instructions normalization (string -> list)
    if isinstance(travel_instructions, str):
        legs = [line.strip() for line in re.split(r"\n+", travel_instructions) if line.strip()]
        travel_instructions = [{"from": "", "to": "", "transport": "", "approx_time": "", "notes": leg} for leg in legs]

    show_debug = (os.environ.get("FLASK_ENV", "").lower() == "development") and (request.args.get("debug") == "1")

    return render_template(
        "result.html",
        destination=destination,
        preferences=preferences,
        days=days,
        budget=budget,
        origin=origin,
        gemini_raw=gemini_raw,
        parsed=parsed,
        itinerary=itinerary,
        visit_nodes=node_positions,
        daily_meals=daily_meals,
        maps_link=maps_link,
        maps_search_link=maps_search_link,
        maps_iframe_src=maps_iframe_src,
        travel_instructions=travel_instructions,
        show_debug=show_debug,
        svg_width=svg_width,
        svg_height=svg_height,
        cols=cols,
        rows=rows,
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_ENV","").lower()=="development")