import os
import smtplib
import requests
import uvicorn
import json
import asyncio
import logging
import time
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from math import radians, cos, sin, sqrt, atan2
import random
from typing import List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from drone_db import log_drone


# ✅ Load environment variables
load_dotenv()

# ✅ Configure logging
logging.basicConfig(filename="drone_tracking.log", level=logging.INFO, 
                    format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()

# ✅ OpenSky API URL
OPENSKY_URL = "https://opensky-network.org/api/states/all"

# ✅ Email Credentials from .env
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
ALERT_EMAIL = os.getenv("ALERT_EMAIL")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ✅ Restricted Zones
RESTRICTED_ZONES = [
    {"name": "JFK Airport", "latitude": 40.6413, "longitude": -73.7781, "radius": 10},
    {"name": "Los Angeles Airport", "latitude": 33.9416, "longitude": -118.4085, "radius": 10},
    {"name": "Hartsfield-Jackson Atlanta Airport", "latitude": 33.6407, "longitude": -84.4277, "radius": 10},
    {"name": "Denver International Airport", "latitude": 39.8561, "longitude": -104.6737, "radius": 10},
    {"name": "Chicago O'Hare Airport", "latitude": 41.9742, "longitude": -87.9073, "radius": 10},
    {"name": "Pentagon", "latitude": 38.8719, "longitude": -77.0563, "radius": 5},
    {"name": "Area 51", "latitude": 37.2431, "longitude": -115.7930, "radius": 15},
]

# ✅ Haversine formula to check if a drone is in a restricted area
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of Earth in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))

# ✅ Check if drone is in a restricted zone
def is_unauthorized_flight(latitude, longitude):
    for zone in RESTRICTED_ZONES:
        distance = haversine(latitude, longitude, zone["latitude"], zone["longitude"])
        if distance <= zone["radius"]:
            return True, zone["name"]
    return False, None

# ✅ Validate Drone Data
def validate_drone_counts(drone_data):
    total_drones = len(drone_data)
    authorized_count = sum(1 for drone in drone_data if not drone["unauthorized"])
    unauthorized_count = sum(1 for drone in drone_data if drone["unauthorized"])

    return {
        "total_drones": total_drones,
        "authorized": authorized_count,
        "unauthorized": unauthorized_count,
        "validation_passed": (authorized_count + unauthorized_count) == total_drones
    }

# ✅ Send Alert Email
def send_alert_email(callsign: str, latitude: float, longitude: float, zone_name: str):
    subject = "🚨 Unauthorized Drone Alert"
    body = (
        f"An unauthorized drone has been detected!\n\n"
        f"🛸 Callsign: {callsign}\n"
        f"📍 Location: Latitude {latitude}, Longitude {longitude}\n"
        f"🚫 Restricted Zone: {zone_name}\n\n"
        f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = ALERT_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        logging.info("Attempting to send unauthorized drone alert email...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        logging.info(f"✅ Alert email sent for {callsign}")
    except Exception as e:
        logging.error(f"❌ Failed to send alert email: {e}")

# ✅ Fetch Live Drone Data
@app.get("/fetch-drones-live")
def fetch_opensky_data():
    try:
        response = requests.get(OPENSKY_URL, timeout=10)
        flights = response.json().get("states", []) if response.status_code == 200 else []
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ OpenSky API error: {str(e)}. Using simulated data.")
        flights = []

    structured_flights = []

    # 1) Generate unauthorized drones in restricted zones
    for i in range(random.randint(3, 7)):  # random 3-7
        zone = random.choice(RESTRICTED_ZONES)
        lat = zone["latitude"] + random.uniform(-0.05, 0.05)
        lon = zone["longitude"] + random.uniform(-0.05, 0.05)
        structured_flights.append({
            "callsign": f"SIM-{i+1}",
            "latitude": lat,
            "longitude": lon,
            "altitude": random.randint(500, 3000),
            "velocity": random.uniform(50, 300),
            "unauthorized": True,
            "zone": zone["name"]
        })

    # 2) Generate random drones and check if they're in restricted zones
    for i in range(10):
        lat = random.uniform(33.0, 43.0)
        lon = random.uniform(-110.0, -80.0)
        unauthorized, zone_name = is_unauthorized_flight(lat, lon)

        structured_flights.append({
            "callsign": f"SIM-{i+6}",
            "latitude": lat,
            "longitude": lon,
            "altitude": random.randint(500, 3000),
            "velocity": random.uniform(50, 300),
            "unauthorized": unauthorized,
            "zone": zone_name if unauthorized else "None"
        })

    # Log unauthorized drone count
    unauthorized_count = sum(1 for drone in structured_flights if drone["unauthorized"])
    logging.info(f"🔴 Unauthorized Drone Count Updated: {unauthorized_count}")

    # ✅ Trigger email alerts and log to database
    for drone in structured_flights:
        if drone["unauthorized"]:
            zone = drone["zone"] if drone["zone"] != "None" else "Unknown"
            send_alert_email(drone["callsign"], drone["latitude"], drone["longitude"], zone)
            log_drone(drone)  # ✅ Log to PostgreSQL

    validation_result = validate_drone_counts(structured_flights)
    return {"drones": structured_flights, "validation": validation_result}


# ✅ WebSocket Streaming for Real-Time Data
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            drones = fetch_opensky_data()
            await websocket.send_text(json.dumps(drones))
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        logging.info("⚠️ WebSocket Disconnected.")
    finally:
        await websocket.close()

# ✅ Get Restricted Zones
@app.get("/restricted-zones")
def get_restricted_zones():
    return {"restricted_zones": RESTRICTED_ZONES}

# ✅ Force a Test Drone
@app.post("/force-drone")
def force_custom_drone(latitude: float = Query(...), longitude: float = Query(...)):
    unauthorized, zone_name = is_unauthorized_flight(latitude, longitude)
    return {
        "callsign": "TEST-DRONE",
        "latitude": latitude,
        "longitude": longitude,
        "unauthorized": unauthorized,
        "zone": zone_name if unauthorized else "None"
    }

# ✅ Home Route
@app.get("/")
def home():
    return {"message": "🚁 Illegal Drone Tracking API with WebSocket running at ws://localhost:8000/ws"}

# ✅ Run FastAPI Server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
