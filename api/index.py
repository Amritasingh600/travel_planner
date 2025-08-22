from flask import Flask, render_template, request, jsonify
import os
import sys
import google.generativeai as genai
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.static_folder = 'static'
app.template_folder = '../templates'

try:
    # Try both environment variable names
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("Neither GEMINI_API_KEY nor GOOGLE_API_KEY environment variable is set")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
    logger.info("Gemini API initialized successfully")
except Exception as e:
    logger.error(f"Error initializing Gemini: {str(e)}")
    model = None

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering template: {str(e)}")
        return jsonify({"error": "Error loading page"}), 500

@app.route('/generate_itinerary', methods=['POST'])
def generate_itinerary():
    try:
        if not model:
            logger.error("Gemini model not initialized")
            return jsonify({"error": "AI service not available"}), 503
            
        data = request.json
        if not data:
            logger.error("No JSON data received")
            return jsonify({"error": "No data provided"}), 400

        required_fields = ['days', 'destination', 'budget', 'travelers']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}")
            return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

        prompt = f"Create a detailed {data['days']}-day travel itinerary for {data['destination']} with a budget of {data['budget']} for {data['travelers']} travelers. Include specific activities, restaurants, and accommodations."
        
        logger.info(f"Generating itinerary for destination: {data['destination']}")
        response = model.generate_content(prompt).text
        
        if not response:
            logger.error("Empty response from Gemini API")
            return jsonify({"error": "Could not generate itinerary"}), 500
            
        return jsonify({"response": response})
    except Exception as e:
        logger.error(f"Error generating itinerary: {str(e)}")
        return jsonify({"error": "An error occurred while generating the itinerary"}), 500

application = app
