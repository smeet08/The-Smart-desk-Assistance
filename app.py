# Smeet Patel 
# Arnav Nigam 
import base64
import os
import serial
import time
import re
import requests
import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, redirect, url_for
from threading import Thread

# Load environment variables
load_dotenv()

# Initialize Gemini API client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Set ESP32 IP address
ESP32_IP = "192.168.2.164"

# URL for sending AI messages & buzzer activation to ESP32
SEND_AI_URL = f"http://{ESP32_IP}/send-ai-message"
SEND_BUZZER_URL = f"http://{ESP32_IP}/buzzer"

# Initialize serial connection (adjust port and baud rate accordingly)
ser = serial.Serial(port='COM5', baudrate=115200, timeout=1)

# Flask Application Initialization
app = Flask(__name__)

# Track session state and data
session_active = False
sensor_data = []
ai_recommendations = []
connection_status = "Disconnected"
session_start_time = None
session_end_time = None

# Time interval for collecting sensor data (5 minutes = 300 seconds)
DATA_COLLECTION_INTERVAL = 300
last_data_collection_time = 0

# Flag to track if AI recommendation has been requested for current session
ai_recommendation_requested = False

@app.route('/')
def index():
    """Render the main monitoring page."""
    return render_template('index.html')

@app.route('/data', methods=['GET'])
def get_data():
    """Serve data to the frontend for live updates."""
    global session_start_time, session_end_time
    session_duration = ""
    
    if session_active and session_start_time:
        current_time = datetime.datetime.now()
        duration = current_time - session_start_time
        hours, remainder = divmod(duration.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        session_duration = f"{hours}h {minutes}m {seconds}s"
    elif session_start_time and session_end_time:
        duration = session_end_time - session_start_time
        hours, remainder = divmod(duration.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        session_duration = f"{hours}h {minutes}m {seconds}s"

    return jsonify({
        "session_active": session_active,
        "session_start_time": session_start_time.strftime("%Y-%m-%d %H:%M:%S") if session_start_time else "",
        "session_end_time": session_end_time.strftime("%Y-%m-%d %H:%M:%S") if session_end_time else "",
        "session_duration": session_duration,
        "sensor_data": sensor_data[-10:],  # Display the last 10 entries
        "ai_recommendations": ai_recommendations[-10:],  # Display the last 10 AI recommendations
        "connection_status": connection_status
    })

def get_ai_response(temperature, humidity, lux):
    """Get AI response with break time and activity suggestions."""
    prompt = (
        f"Given the following environmental conditions:\n"
        f"- Temperature: {temperature}°C\n"
        f"- Humidity: {humidity}%\n"
        f"- Light Level: {lux} lux\n\n"
        f"Provide TWO specific recommendations in the following format:\n"
        f"1. BREAK RECOMMENDATION: Suggest when to take a break (in X minutes) based on these readings\n"
        f"2. ACTIVITY SUGGESTION: Recommend ONE specific activity for the break period (something physical, mental, or relaxing)\n"
        f"3. ENVIRONMENT SUGGESTION: Suggest any adjustments to improve the workspace environment\n\n"
        f"Be specific and creative with your suggestions. Vary the activities across different recommendations."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-thinking-exp-01-21",
            contents=[prompt]
        )

        ai_text = response.text.strip()
        
        # Extract break recommendation
        break_match = re.search(r"BREAK RECOMMENDATION:(.+?)(?=ACTIVITY SUGGESTION:|$)", ai_text, re.DOTALL)
        break_recommendation = break_match.group(1).strip() if break_match else "Take a short break soon."
        
        # Extract activity suggestion
        activity_match = re.search(r"ACTIVITY SUGGESTION:(.+?)(?=ENVIRONMENT SUGGESTION:|$)", ai_text, re.DOTALL)
        activity_suggestion = activity_match.group(1).strip() if activity_match else "Try a brief relaxation exercise."
        
        # Extract environment suggestion
        env_match = re.search(r"ENVIRONMENT SUGGESTION:(.+?)$", ai_text, re.DOTALL)
        env_suggestion = env_match.group(1).strip() if env_match else "Consider adjusting your workspace based on current readings."
        
        # Format the recommendation
        recommendation = f"BREAK: {break_recommendation}\n\nACTIVITY: {activity_suggestion}\n\nENVIRONMENT: {env_suggestion}"
        return recommendation

    except Exception as e:
        print(f"Error getting AI response: {e}")
        return f"BREAK: Consider taking a short break soon.\n\nACTIVITY: Step away from your screen for a few minutes.\n\nENVIRONMENT: Unable to analyze environment data."

def send_to_esp32(text):
    """Send AI break message to ESP32 and trigger buzzer."""
    if text:
        message = f"BREAK:{text}"
        try:
            response = requests.post(SEND_AI_URL, data=message)
            if response.status_code == 200:
                print(f"Sent to ESP32: {message}")
                activate_buzzer()
            else:
                print(f"Failed to send message. Status: {response.status_code}")
        except Exception as e:
            print(f"Error sending message: {e}")

def activate_buzzer():
    """Trigger the buzzer on ESP32 when break starts/ends."""
    try:
        response = requests.post(SEND_BUZZER_URL, data="BUZZER:START")
        if response.status_code == 200:
            print("Buzzer activated for break alert.")
        else:
            print(f"Failed to activate buzzer. Status: {response.status_code}")
    except Exception as e:
        print(f"Error activating buzzer: {e}")

def request_initial_ai_recommendation():
    """Request AI recommendation at the beginning of the session."""
    global ai_recommendation_requested, ai_recommendations
    
    if not ai_recommendation_requested:
        # For the first data request, we'll use default values if we don't have real data yet
        if len(sensor_data) > 0:
            # Try to parse the last sensor data
            try:
                last_data = sensor_data[-1]
                # Extract values from the format "[timestamp] Temp: X°C, Humidity: Y%, Light: Z lux"
                temp_match = re.search(r"Temp: ([\d.]+)°C", last_data)
                humidity_match = re.search(r"Humidity: ([\d.]+)%", last_data)
                light_match = re.search(r"Light: ([\d.]+) lux", last_data)
                
                temperature = temp_match.group(1) if temp_match else "22"
                humidity = humidity_match.group(1) if humidity_match else "50"
                lux = light_match.group(1) if light_match else "300"
            except:
                temperature, humidity, lux = "22", "50", "300"  # Default values
        else:
            temperature, humidity, lux = "22", "50", "300"  # Default values
        
        # Get and save AI recommendation
        ai_response = get_ai_response(temperature, humidity, lux)
        ai_recommendations.append(ai_response)
        send_to_esp32(ai_response)
        
        # Mark as requested
        ai_recommendation_requested = True

def process_sensor_data(data):
    """Process incoming sensor data, update webpage, and collect only every 5 minutes."""
    global sensor_data, last_data_collection_time
    if not session_active:
        return  # Ignore data if session is not active

    current_time = time.time()
    
    # Only collect data at the beginning of the session and then every 5 minutes
    if len(sensor_data) == 0 or (current_time - last_data_collection_time >= DATA_COLLECTION_INTERVAL):
        parts = data.strip().split(',')
        if len(parts) >= 3:
            temperature, humidity, lux = parts[0], parts[1], parts[2]
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            sensor_data.append(f"[{timestamp}] Temp: {temperature}°C, Humidity: {humidity}%, Light: {lux} lux")
            
            # Update last collection time
            last_data_collection_time = current_time
        
        # For the first data collection, request AI recommendation
        if len(sensor_data) == 1:
            request_initial_ai_recommendation()

def read_serial_data():
    """Read data from serial connection and process it."""
    global connection_status
    buffer = ""

    while True:
        try:
            if ser.in_waiting > 0:
                connection_status = "Connected"
                char = ser.read().decode('utf-8', errors='ignore')
                if char == '\n':
                    if buffer:
                        print(f"Received: {buffer}")
                        process_sensor_data(buffer)
                        buffer = ""
                else:
                    buffer += char
            time.sleep(0.01)
        except Exception as e:
            connection_status = "Disconnected"
            print(f"Serial error: {e}")
            time.sleep(5)  # Wait before retrying

@app.route('/session', methods=['POST'])
def manage_session():
    """Start or end work session."""
    global session_active, ai_recommendations, sensor_data, session_start_time, session_end_time, ai_recommendation_requested, last_data_collection_time
    data = request.json

    if data.get("action") == "start":
        session_active = True
        session_start_time = datetime.datetime.now()
        session_end_time = None
        ai_recommendations = []
        sensor_data = []
        ai_recommendation_requested = False
        last_data_collection_time = 0  # Reset the data collection timer
        print(f"Work session started at {session_start_time}")
        return jsonify({
            "message": "Work session started.",
            "start_time": session_start_time.strftime("%Y-%m-%d %H:%M:%S")
        })

    elif data.get("action") == "end":
        session_active = False
        session_end_time = datetime.datetime.now()
        print(f"Work session ended at {session_end_time}")
        return jsonify({
            "message": "Work session ended.",
            "end_time": session_end_time.strftime("%Y-%m-%d %H:%M:%S")
        })

    else:
        return jsonify({"message": "Invalid action."})

@app.route('/templates/<path:path>')
def send_template(path):
    """Serve template files to avoid URL not found errors."""
    return render_template(path)

if __name__ == "__main__":
    # Create templates directory if it doesn't exist
    os.makedirs("templates", exist_ok=True)
    
    # Start the serial reading thread
    thread = Thread(target=read_serial_data)
    thread.daemon = True
    thread.start()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)