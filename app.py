#!/usr/bin/env python3
import os
import json
import re
import math
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

# Sample fallback response (used only when API fails)
SAMPLE_GEMINI_RAW = """===JSON_START===
{
  "destination_name": "Mathura, India",
  "maps_query": "Mathura,India",
  "itinerary": [
    { "day_number": 1, "summary": "Arrival and Janmabhoomi", "activities": ["Visit Shri Krishna Janmabhoomi","Evening aarti"], "approximate_cost": 500 },
    { "day_number": 2, "summary": "Vrindavan temples", "activities": ["Banke Bihari Temple","Prem Mandir"], "approximate_cost": 700 },
    { "day_number": 3, "summary": "Local markets & departure", "activities": ["Local markets","Depart"], "approximate_cost": 300 }
  ],
  "visit_sequence": [
    { "order": 1, "location_name": "Shri Krishna Janmabhoomi", "suggested_time": "Morning", "estimated_duration": "2 hours",
      "note": "Start early", "latitude": 27.4921, "longitude": 77.6745,
      "nearby_food_recommendations": [{"name":"Brijwasi Sweets","rating":4.2,"distance_m":300,"price_level":"₹","reason":"Famous for pedas"}]
    },
    { "order": 2, "location_name": "Banke Bihari Temple (Vrindavan)", "suggested_time": "Morning", "estimated_duration": "2 hours",
      "note": "Crowded, come early", "latitude": 27.5807, "longitude": 77.7061,
      "nearby_food_recommendations": [{"name":"Local stalls","rating":3.8,"distance_m":100,"price_level":"₹","reason":"Street snacks"}]
    },
    { "order": 3, "location_name": "Govardhan Hill", "suggested_time": "Afternoon", "estimated_duration": "3 hours",
      "note": "Scenic spot", "latitude": 27.4833, "longitude": 77.6750,
      "nearby_food_recommendations": [{"name":"Hill Cafe","rating":4.0,"distance_m":250,"price_level":"₹₹","reason":"Good view"}]
    }
  ],
  "popular_dinner_recommendations": [{"name":"Brijwasi Sweets","reason":"Local sweets","rating":4.2,"price_level":"₹"}],
  "popular_stays": [{"name":"Hotel Madhuvan","reason":"Comfortable near temples","rating":4.0,"price_level":"₹₹","address":"Near Janmabhoomi, Mathura"}],
  "travel_instructions": [
    {"from":"Your origin","to":"Mathura Junction","transport":"Train/car","approx_time":"Varies","notes":"From Mathura Junction take a rickshaw to Janmabhoomi (~10-20 min)"}
  ]
}
===JSON_END==="""

# ---------- Helpers ----------
def strip_code_fences(text):
    if not isinstance(text, str):
        return text
    m = re.search(r"^```(?:json)?\s*(.*)\s*```$", text, re.S | re.I)
    if m:
        return m.group(1).strip()
    return text

def extract_text_from_api_response(data):
    """
    Try several common model response shapes and return the first plausible text blob.
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

    # fallback: pretty JSON string
    try:
        return json.dumps(data, indent=2)
    except Exception:
        return str(data)

def extract_json_from_text(text):
    """
    Robust JSON extraction:
    - strip fenced code blocks
    - look for markers ===JSON_START=== ... ===JSON_END===
    - otherwise locate first balanced {...} block and parse it
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

    # find first balanced {...}
    first = text.find("{")
    if first == -1:
        return None

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
    Ensure visit_sequence is a list of dicts. Handle strings and nested shapes.
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
                kv = {}
                m = re.search(r"order\s*[:=]\s*(\d+)", item, re.I)
                if m:
                    kv["order"] = int(m.group(1))
                m2 = re.search(r'location_name\s*[:=]\s*["\']?([^,"\']+)["\']?', item, re.I)
                if m2:
                    kv["location_name"] = m2.group(1).strip()
                if kv:
                    normalized.append(kv)
    return normalized

def safe_load_json_like(x):
    if x is None:
        return []
    if isinstance(x, (list, dict)):
        return x
    if isinstance(x, str):
        try:
            return json.loads(x)
        except Exception:
            return extract_json_from_text(x) or []
    return []

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1); dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def call_gemini(prompt):
    """
    Call Generative API and return text. Raises on HTTP errors.
    """
    if (not GEMINI_API_URL) or (not GEMINI_API_KEY):
        raise RuntimeError("GEMINI_API_URL and GEMINI_API_KEY must be set as environment variables.")

    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": GEMINI_API_KEY}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    resp = requests.post(GEMINI_API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    text = extract_text_from_api_response(data)
    text = strip_code_fences(text).strip() if isinstance(text, str) else text
    return text

def build_maps_dir_link(origin, destination, waypoints=None):
    """
    Build a Google Maps Directions link using api=1. origin/destination can be "lat,lon" or place string.
    waypoints: list of "lat,lon" or place strings (interior waypoints).
    """
    if not destination:
        return None
    params = {"api": 1, "origin": origin or "", "destination": destination}
    if waypoints:
        # Google accepts pipe-separated list
        params["waypoints"] = "|".join(waypoints)
    params["travelmode"] = "driving"
    return "https://www.google.com/maps/dir/?" + urlencode(params)

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

    # Strict prompt example to encourage consistent JSON
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
"""

    try:
        gemini_raw = call_gemini(prompt)
    except Exception as e:
        flash(f"Gemini API error: {e}. Showing sample response.")
        gemini_raw = SAMPLE_GEMINI_RAW

    parsed = extract_json_from_text(gemini_raw) or {}

    # Extract core pieces
    itinerary = parsed.get("itinerary") or []
    raw_visit_sequence = parsed.get("visit_sequence") or []
    visit_sequence = normalize_visit_sequence(raw_visit_sequence)

    # Normalize popular dinner recommendations
    popular_dinners = parsed.get("popular_dinner_recommendations") \
                      or parsed.get("popular_dinners") \
                      or parsed.get("dining") \
                      or parsed.get("dinner_recommendations") \
                      or parsed.get("popular_foods") \
                      or []
    popular_dinners = safe_load_json_like(popular_dinners)
    if isinstance(popular_dinners, dict):
        popular_dinners = [popular_dinners]
    if not isinstance(popular_dinners, list):
        popular_dinners = []

    # Normalize popular stays (accept different key names)
    popular_stays = parsed.get("popular_stays") \
                    or parsed.get("stays") \
                    or parsed.get("accommodations") \
                    or parsed.get("hotels") \
                    or parsed.get("recommended_stays") \
                    or []
    popular_stays = safe_load_json_like(popular_stays)
    if isinstance(popular_stays, dict):
        popular_stays = [popular_stays]
    if not isinstance(popular_stays, list):
        popular_stays = []

    # Normalize travel instructions (handle many shapes)
    travel_raw = parsed.get("travel_instructions") \
                 or parsed.get("travel") \
                 or parsed.get("directions") \
                 or parsed.get("route") \
                 or parsed.get("travel_steps") \
                 or []
    travel_instructions = []
    if isinstance(travel_raw, str):
        try:
            travel_instructions = json.loads(travel_raw)
        except Exception:
            legs = [line.strip() for line in re.split(r"[\n\r]+", travel_raw) if line.strip()]
            travel_instructions = [{"from": "", "to": "", "transport": "", "approx_time": "", "notes": leg} for leg in legs]
    elif isinstance(travel_raw, dict):
        travel_instructions = [travel_raw]
    elif isinstance(travel_raw, list):
        travel_instructions = travel_raw
    else:
        travel_instructions = []

    # If itinerary missing, build a light one from visit_sequence
    try:
        days_n = int(days) if days and str(days).isdigit() else len(itinerary) or 1
    except Exception:
        days_n = len(itinerary) or 1

    if not visit_sequence and itinerary:
        visit_sequence = []
        idx = 1
        for day in itinerary:
            activities = day.get("activities") or []
            for act in activities:
                name = act if isinstance(act, str) else act.get("name", f"Place {idx}")
                visit_sequence.append({
                    "order": idx,
                    "location_name": name,
                    "suggested_time": "",
                    "estimated_duration": "",
                    "note": "",
                    "latitude": None,
                    "longitude": None,
                    "nearby_food_recommendations": (popular_dinners or [])[:2]
                })
                idx += 1

    # Final sort of visit_sequence
    try:
        visit_sequence = sorted(visit_sequence, key=lambda x: int(x.get("order", 0)))
    except Exception:
        pass

    # Build node_positions grid (fallback if coords missing)
    n_nodes = max(1, len(visit_sequence))
    max_cols = int(os.environ.get("TREASUREMAP_MAX_COLS", 6))
    cols = min(n_nodes, max_cols)
    rows = ceil(n_nodes / cols)
    svg_width = 1400
    row_height = 160
    svg_height = max(260, rows * row_height + 80)
    margin_x = 80
    margin_top = 40
    usable_width = svg_width - margin_x * 2
    col_step = usable_width // max(1, cols - 1) if cols > 1 else 0

    node_positions = []
    location_to_coords = {}
    for idx, v in enumerate(visit_sequence):
        if not isinstance(v, dict):
            continue
        col = idx % cols
        row = idx // cols
        x = margin_x + (col * col_step) if cols > 1 else svg_width // 2
        y = margin_top + (row * row_height) + (row * 6)
        lat = v.get("latitude")
        lon = v.get("longitude")
        node = {
            "order": int(v.get("order", idx + 1)),
            "location_name": v.get("location_name") or v.get("name") or f"Place {idx+1}",
            "suggested_time": v.get("suggested_time", ""),
            "estimated_duration": v.get("estimated_duration", ""),
            "note": v.get("note", ""),
            "latitude": lat,
            "longitude": lon,
            "nearby_food_recommendations": v.get("nearby_food_recommendations") or [],
            "x": int(x),
            "y": int(y)
        }
        node_positions.append(node)
        # normalize and store mapping for easy lookups later
        if lat is not None and lon is not None:
            try:
                location_to_coords[node["location_name"]] = f"{float(lat)},{float(lon)}"
            except Exception:
                pass

    # Build coords_list for Leaflet mapping
    coords_list = []
    for n in node_positions:
        lat = n.get("latitude"); lon = n.get("longitude")
        try:
            if lat is not None and lon is not None:
                coords_list.append([float(lat), float(lon)])
        except Exception:
            continue

    # Build Google Maps links for convenience
    destination_for_search = (parsed.get("destination_name") or parsed.get("maps_query") or destination).strip()
    destination_for_dirs = parsed.get("maps_query") or parsed.get("destination_name") or destination

    def build_maps_query(q):
        if not q:
            return ""
        q = str(q).strip()
        if re.match(r"^\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*$", q):
            return q.replace(" ", "")
        return quote_plus(q)

    maps_search_link = None
    maps_iframe_src = None
    maps_link = None
    maps_directions_link = None

    if destination_for_dirs:
        params = {"api": 1, "destination": build_maps_query(destination_for_dirs)}
        if origin:
            params["origin"] = origin
        params["travelmode"] = "driving"
        maps_link = "https://www.google.com/maps/dir/?" + urlencode(params)

    if destination_for_search:
        maps_search_link = "https://www.google.com/maps/search/?api=1&query=" + build_maps_query(destination_for_search)
        maps_iframe_src = maps_search_link

    coords = []
    for n in node_positions:
        lat = n.get("latitude"); lon = n.get("longitude")
        if lat is not None and lon is not None:
            coords.append(f"{lat},{lon}")
    if coords:
        if origin:
            origin_param = origin
            destination_param = coords[-1]
            waypoints = coords[:-1]
        else:
            origin_param = coords[0]
            destination_param = coords[-1]
            waypoints = coords[1:-1]
        waypoints_str = "|".join(waypoints) if waypoints else ""
        params = {"api": 1, "origin": origin_param, "destination": destination_param, "travelmode": "driving"}
        if waypoints_str:
            params["waypoints"] = waypoints_str
        maps_directions_link = "https://www.google.com/maps/dir/?" + urlencode(params)

    # --- Enrich travel_instructions with map links (restore the previous "good" travel instructions behaviour)
    enriched_travel = []
    # If the model provided detailed legs, try to enrich them
    for leg in travel_instructions:
        leg_map = None
        from_name = leg.get("from") if isinstance(leg, dict) else ""
        to_name = leg.get("to") if isinstance(leg, dict) else ""
        # attempt to find coordinates for from/to by name
        from_coords = location_to_coords.get(from_name)
        to_coords = location_to_coords.get(to_name)
        if from_coords and to_coords:
            leg_map = build_maps_dir_link(from_coords, to_coords)
        elif from_coords and to_name:
            leg_map = build_maps_dir_link(from_coords, to_name)
        elif to_coords and from_name:
            leg_map = build_maps_dir_link(from_name, to_coords)
        else:
            # fallback: if overall maps_directions_link exists, use it
            leg_map = maps_directions_link
        enriched = dict(leg if isinstance(leg, dict) else {"notes": str(leg)})
        enriched["map_link"] = leg_map
        enriched_travel.append(enriched)

    # If model didn't provide travel instructions, synthesize and include per-leg map links
    if not enriched_travel:
        synthesized = []
        for i in range(len(node_positions) - 1):
            a = node_positions[i]; b = node_positions[i+1]
            from_name = a.get("location_name")
            to_name = b.get("location_name")
            approx_time = ""
            if a.get("latitude") is not None and a.get("longitude") is not None and b.get("latitude") is not None and b.get("longitude") is not None:
                try:
                    lat1, lon1 = float(a["latitude"]), float(a["longitude"])
                    lat2, lon2 = float(b["latitude"]), float(b["longitude"])
                    dist_km = haversine_km(lat1, lon1, lat2, lon2)
                    mins = max(5, int((dist_km / 30.0) * 60))  # ~30 km/h
                    approx_time = f"{mins} min"
                except Exception:
                    approx_time = ""
            origin_param = f"{a['latitude']},{a['longitude']}" if a.get("latitude") is not None and a.get("longitude") is not None else from_name
            dest_param = f"{b['latitude']},{b['longitude']}" if b.get("latitude") is not None and b.get("longitude") is not None else to_name
            map_link = build_maps_dir_link(origin_param, dest_param)
            synthesized.append({
                "from": from_name,
                "to": to_name,
                "transport": "Taxi/Auto",
                "approx_time": approx_time,
                "notes": "",
                "map_link": map_link
            })
        enriched_travel = synthesized

    # Ensure enriched_travel is a list of dicts
    final_travel_instructions = []
    for leg in enriched_travel:
        if isinstance(leg, dict):
            final_travel_instructions.append(leg)
        else:
            final_travel_instructions.append({"from":"", "to":"", "transport":"", "approx_time":"", "notes": str(leg), "map_link": maps_directions_link})

    show_debug = (os.environ.get("FLASK_ENV", "").lower() == "development") and (request.args.get("debug") == "1")

    # Render template with normalized data (travel instructions restored & enriched)
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
        coords_list=coords_list,
        maps_link=maps_link,
        maps_search_link=maps_search_link,
        maps_iframe_src=maps_iframe_src,
        maps_directions_link=maps_directions_link,
        travel_instructions=final_travel_instructions,
        popular_dinners=popular_dinners,
        popular_stays=popular_stays,
        show_debug=show_debug,
        svg_width=svg_width,
        svg_height=svg_height,
        cols=cols,
        rows=rows,
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_ENV","").lower()=="development")