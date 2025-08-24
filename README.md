# AI Travel Planner ✈️🌍

A comprehensive Flask-powered travel planning application that uses Google's Gemini AI to generate personalized travel itineraries with interactive maps, route planning, and detailed recommendations.

## 🌟 Features

- **AI-Powered Itinerary Generation**: Uses Google Gemini AI to create detailed day-by-day travel plans
- **Interactive Maps**: Integrated with Google Maps and Leaflet for route visualization
- **Smart Route Planning**: Automatically calculates travel distances and times between locations
- **Comprehensive Recommendations**: Includes accommodation, dining, and activity suggestions
- **Visual Treasure Map**: SVG-based interactive visualization of your journey
- **Multiple Deployment Options**: Works locally and on cloud platforms like Render
- **Responsive Design**: Modern, mobile-friendly interface

## 🏗️ Project Structure

```
gemini_travel/
├── templates/
│   ├── base.html          # Base template with styling
│   ├── index.html         # Main input form
│   └── result.html        # Detailed results with maps
├── app.py                 # Main Flask application
├── gemini_google.py       # Google API integration utilities
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (local)
└── README.md             # This file
```

## 🚀 How It Works

### 1. User Input Collection
- **Destination**: Where you want to travel
- **Origin**: Your starting point (optional)
- **Preferences**: Activities you enjoy (temples, food, museums, etc.)
- **Duration**: Number of days for the trip
- **Budget**: Your spending preference

### 2. AI Processing
The application sends a structured prompt to Google Gemini AI requesting:
```json
{
  "destination_name": "Place, Country",
  "maps_query": "Place,Country", 
  "itinerary": [
    {
      "day_number": 1,
      "summary": "Day overview",
      "activities": ["Activity 1", "Activity 2"],
      "approximate_cost": 100
    }
  ],
  "visit_sequence": [
    {
      "order": 1,
      "location_name": "Attraction Name",
      "suggested_time": "Morning",
      "estimated_duration": "2 hours",
      "latitude": 12.3456,
      "longitude": 78.9012,
      "nearby_food_recommendations": [...]
    }
  ],
  "popular_dinner_recommendations": [...],
  "popular_stays": [...],
  "travel_instructions": [...]
}
```

### 3. Data Processing & Visualization
- **JSON Extraction**: Robust parsing of AI responses
- **Route Calculation**: Haversine distance calculations between locations
- **Map Integration**: Google Maps embedding and directions
- **Interactive Elements**: SVG treasure map with clickable nodes

### 4. Result Presentation
- **Day-by-day Itinerary**: Organized schedule with activities and costs
- **Interactive Map**: Visual route with markers and popups
- **Recommendations**: Curated dining and accommodation options
- **Travel Instructions**: Step-by-step directions with map links

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.9+ 
- Google Cloud Project with Generative AI API enabled
- Gemini API key

### Local Development

1. **Clone the repository**
```bash
git clone <repository-url>
cd gemini_travel
```

2. **Create virtual environment**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
Create a `.env` file:
```env
GEMINI_API_URL=https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent
GEMINI_API_KEY=your_api_key_here
FLASK_ENV=development
FLASK_SECRET_KEY=your_secret_key_here
```

5. **Run the application**
```bash
python app.py
```
Visit `http://localhost:5000`

### Render Deployment

1. **Create a Render account**
   - Go to [render.com](https://render.com) and sign up

2. **Connect your repository**
   - Connect your GitHub repository to Render
   - Create a new Web Service

3. **Configure deployment settings**
   ```
   Build Command: pip install -r requirements.txt
   Start Command: python app.py
   ```

4. **Set Environment Variables**
   In your Render dashboard, add:
   - `GEMINI_API_KEY`: Your Google AI API key
   - `GEMINI_API_URL`: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent`
   - `FLASK_ENV`: `production`
   - `PORT`: `10000` (Render's default)

5. **Deploy**
   - Click "Create Web Service"
   - Render will automatically deploy your application

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `GEMINI_API_KEY` | Google Generative AI API key | Yes | `AIzaSy...` |
| `GEMINI_API_URL` | Full API endpoint URL | Yes | `https://generativelanguage.googleapis.com/...` |
| `FLASK_SECRET_KEY` | Flask session secret | No | `your-secret-key` |
| `FLASK_ENV` | Flask environment | No | `development` or `production` |
| `PORT` | Server port (for Render) | No | `10000` |

### API Configuration

The application uses Google's Generative Language API. To get your API key:

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Enable the Generative Language API in Google Cloud Console

## 🏃‍♂️ Usage

### Basic Flow

1. **Enter Trip Details**: Fill out the form with your destination and preferences
2. **Generate Itinerary**: Click "Generate My Itinerary" 
3. **Review Results**: Explore your personalized travel plan
4. **Use Maps**: Click map links for navigation
5. **Follow Route**: Use the treasure map for visual guidance

### Advanced Features

- **Debug Mode**: Add `?debug=1` to see raw AI responses
- **Custom Prompts**: Modify prompt templates in `app.py`
- **Map Customization**: Adjust SVG parameters for different layouts

## 🧰 Technical Details

### Dependencies

#### Core Framework
- **Flask 2.2.5**: Web framework
- **Werkzeug 2.2.3**: WSGI utilities

#### AI Integration  
- **google-generativeai 0.3.0**: Google Gemini AI client
- **requests 2.31.0**: HTTP requests

#### Utilities
- **python-dotenv 1.0.0**: Environment variable management

### Architecture

#### Frontend
- **Responsive CSS**: Mobile-first design with CSS Grid
- **Leaflet Maps**: Interactive mapping with routing
- **SVG Graphics**: Custom treasure map visualization

#### Backend
- **Flask Routes**: RESTful API endpoints
- **Error Handling**: Comprehensive exception management
- **Logging**: Structured logging for debugging

#### AI Integration
- **Prompt Engineering**: Structured prompts for consistent responses
- **JSON Parsing**: Robust extraction from AI responses
- **Fallback Handling**: Graceful degradation when AI fails

### Algorithms

#### Route Optimization
```python
def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates"""
    R = 6371.0  # Earth's radius in kilometers
    # Haversine formula implementation
```

#### JSON Extraction
```python
def extract_json_from_text(text):
    """Extract JSON from AI response with multiple fallback strategies"""
    # 1. Look for markers ===JSON_START=== ... ===JSON_END===
    # 2. Find balanced {...} blocks
    # 3. Clean and parse with error handling
```

## 🚨 Troubleshooting

### Common Issues

#### "Internal Server Error"
- **Cause**: Missing environment variables or template errors
- **Solution**: Check Render environment variables and template paths

#### "AI service not available" 
- **Cause**: Invalid API key or network issues
- **Solution**: Verify API key and check Google Cloud quotas

#### Template not found
- **Cause**: Incorrect template folder path in deployment
- **Solution**: Ensure `templates/` folder is included in deployment

#### Map not loading
- **Cause**: Missing coordinates or Google Maps API issues
- **Solution**: Check coordinate extraction and API limits

#### Render deployment fails
- **Cause**: Missing dependencies or incorrect start command
- **Solution**: Verify `requirements.txt` and ensure `python app.py` works locally

### Debug Mode

Enable debug mode by setting `FLASK_ENV=development` and adding `?debug=1` to URLs to see:
- Raw AI responses
- Parsed JSON data
- Coordinate calculations
- Error stack traces

## 🔧 Development

### Adding New Features

#### Custom AI Models
Modify `gemini_google.py` to integrate different AI providers:
```python
def call_custom_ai(prompt):
    # Your custom AI integration
    pass
```

#### New Map Providers
Add alternative mapping in `result.html`:
```javascript
// Mapbox, OpenStreetMap, etc.
```

#### Enhanced Parsing
Improve JSON extraction in `app.py`:
```python
def enhanced_parser(response):
    # Better parsing logic
    pass
```

### Testing

#### Local Testing
```bash
python -m pytest tests/
```

#### Render Testing
```bash
# Test locally first
python app.py

# Check logs in Render dashboard
```

## 📄 License

This project is open source. Feel free to modify and distribute.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📞 Support

For issues and questions:
- Check the troubleshooting section
- Review Render deployment logs
- Verify environment variables
- Test API connections

## 🔮 Future Enhancements

- **Multi-language Support**: Internationalization
- **User Accounts**: Save and share itineraries
- **Real-time Updates**: Live travel information
- **Social Features**: Trip sharing and reviews
- **Mobile App**: React Native or Flutter version
- **Offline Mode**: PWA capabilities
- **AI Improvements**: Fine-tuned travel models

---

**Happy Traveling! ✈️🌍**