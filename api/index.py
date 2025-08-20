from flask import Flask, render_template, request, jsonify
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.static_folder = 'static'
app.template_folder = '../templates'

try:
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
except Exception as e:
    print(f"Error initializing Gemini: {str(e)}")
    # Still initialize the model variable to avoid NameError
    model = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_itinerary', methods=['POST'])
def generate_itinerary():
    try:
        if not model:
            return jsonify({"error": "Gemini API not properly initialized"}), 500
            
        data = request.json
        if not all(key in data for key in ['days', 'destination', 'budget', 'travelers']):
            return jsonify({"error": "Missing required fields"}), 400

        prompt = f"Create a detailed {data['days']}-day travel itinerary for {data['destination']} with a budget of {data['budget']} for {data['travelers']} travelers. Include specific activities, restaurants, and accommodations."
        
        response = model.generate_content(prompt).text
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

application = app
