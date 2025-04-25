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
from typing import List, Dict, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Attempt to import drone_db safely
try:
    from drone_db import log_drone
    DRONE_DB_ENABLED = True
except ImportError:
    DRONE_DB_ENABLED = False
    # Define a placeholder if drone_db is optional
    def log_drone(drone_data: Dict[str, Any]):
        pass

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("main") # Use specific logger name
if not DRONE_DB_ENABLED:
    logger.warning("Drone DB module not found or 'log_drone' function missing. DB logging disabled.")

app = FastAPI(title="Illegal Drone Tracking API")

# OpenSky API URL
OPENSKY_URL = "https://opensky-network.org/api/states/all"

# Email Credentials from .env
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
ALERT_EMAIL = os.getenv("ALERT_EMAIL")

# Log loaded credentials status safely
logger.info(f"Loaded EMAIL_ADDRESS: {'Set' if EMAIL_ADDRESS else 'Not Set'}")
logger.info(f"Loaded EMAIL_PASSWORD: {'Set' if EMAIL_PASSWORD else 'Not Set'}")
logger.info(f"Loaded ALERT_EMAIL: {ALERT_EMAIL}")

# Allow CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    # Adjust origins as needed for your specific setup
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001", # Example if React runs on 3001
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Restricted Zones
RESTRICTED_ZONES = [
    # Major Airports
    {"name": "JFK Airport", "latitude": 40.6413, "longitude": -73.7781, "radius": 10, "type": "Airport"},
    {"name": "Los Angeles Airport", "latitude": 33.9416, "longitude": -118.4085, "radius": 10, "type": "Airport"},
    {"name": "Hartsfield-Jackson Atlanta Airport", "latitude": 33.6407, "longitude": -84.4277, "radius": 10, "type": "Airport"},
    {"name": "Denver International Airport", "latitude": 39.8561, "longitude": -104.6737, "radius": 10, "type": "Airport"},
    {"name": "Chicago O'Hare Airport", "latitude": 41.9742, "longitude": -87.9073, "radius": 10, "type": "Airport"},
    {"name": "Dallas/Fort Worth Airport", "latitude": 32.8998, "longitude": -97.0403, "radius": 10, "type": "Airport"},
    {"name": "Miami International Airport", "latitude": 25.7959, "longitude": -80.2870, "radius": 10, "type": "Airport"},
    {"name": "San Francisco International Airport", "latitude": 37.6213, "longitude": -122.3790, "radius": 10, "type": "Airport"},
    {"name": "Seattle-Tacoma International Airport", "latitude": 47.4502, "longitude": -122.3088, "radius": 10, "type": "Airport"},
    {"name": "Orlando International Airport", "latitude": 28.4312, "longitude": -81.3081, "radius": 10, "type": "Airport"},
    # Military Bases
    {"name": "Pentagon", "latitude": 38.8719, "longitude": -77.0563, "radius": 5, "type": "Military"},
    {"name": "Fort Liberty (Bragg)", "latitude": 35.1401, "longitude": -79.0060, "radius": 10, "type": "Military"},
    {"name": "Edwards Air Force Base", "latitude": 34.9054, "longitude": -117.8844, "radius": 15, "type": "Military"},
    {"name": "Wright-Patterson Air Force Base", "latitude": 39.8149, "longitude": -84.0497, "radius": 10, "type": "Military"},
    {"name": "Norfolk Naval Base", "latitude": 36.9460, "longitude": -76.3087, "radius": 10, "type": "Military"},
    # Government Restricted Locations
    {"name": "White House", "latitude": 38.8977, "longitude": -77.0365, "radius": 3, "type": "Government"},
    {"name": "Area 51", "latitude": 37.2431, "longitude": -115.7930, "radius": 15, "type": "Government"},
    {"name": "Cheyenne Mountain Complex", "latitude": 38.6766, "longitude": -104.7887, "radius": 8, "type": "Military"},
    {"name": "Los Alamos National Lab", "latitude": 35.8440, "longitude": -106.2857, "radius": 8, "type": "Government"},
    {"name": "Groom Lake Facility (CIA)", "latitude": 37.2491, "longitude": -115.8001, "radius": 12, "type": "Government"},
]

# Define CONUS bounding box (approximate)
CONUS_BOUNDS = {
    "lat_min": 24.0, "lat_max": 49.0,
    "lon_min": -125.0, "lon_max": -66.0
}

# Haversine formula
def haversine(lat1: Optional[float], lon1: Optional[float], lat2: float, lon2: float) -> float:
    """Calculate distance between two points on Earth using Haversine."""
    R = 6371 # Earth radius in kilometers
    if lat1 is None or lon1 is None:
        logger.warning(f"Haversine called with None coordinates: ({lat1}, {lon1})")
        return float('inf')
    if not all(isinstance(coord, (int, float)) for coord in [lat1, lon1, lat2, lon2]):
        logger.warning(f"Invalid coordinate types for Haversine: ({lat1} [{type(lat1)}], {lon1} [{type(lon1)}]), ({lat2} [{type(lat2)}], {lon2} [{type(lon2)}])")
        return float('inf')
    try:
        lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c
    except (ValueError, TypeError) as e:
        logger.error(f"Error in Haversine calculation ({lat1}, {lon1} to {lat2}, {lon2}): {e}", exc_info=True)
        return float('inf')

# Check if drone is in a restricted zone
def is_unauthorized_flight(latitude: Optional[float], longitude: Optional[float]) -> tuple[bool, Optional[str]]:
    """Checks if coordinates fall within any defined restricted zone."""
    if latitude is None or longitude is None: return False, None
    for zone in RESTRICTED_ZONES:
        try:
            if not all(k in zone for k in ["latitude", "longitude", "radius"]):
                logger.warning(f"Skipping zone due to missing keys: {zone.get('name', 'Unknown')}")
                continue
            if not all(isinstance(zone[k], (int, float)) for k in ["latitude", "longitude", "radius"]):
                 logger.warning(f"Skipping zone due to invalid coordinate/radius types: {zone.get('name', 'Unknown')}")
                 continue

            distance = haversine(latitude, longitude, zone["latitude"], zone["longitude"])
            if distance <= zone["radius"]:
                logger.info(f"Drone at ({latitude:.4f}, {longitude:.4f}) is IN restricted zone: {zone['name']} (Dist: {distance:.2f}km)")
                return True, zone["name"]
        except Exception as e:
             logger.error(f"Error checking zone {zone.get('name', 'Unknown')} for ({latitude}, {longitude}): {e}", exc_info=True)
    return False, None

# Validate Drone Data counts
def validate_drone_counts(drone_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validates consistency of drone counts in a list."""
    if not isinstance(drone_data, list): return {"total_drones": 0, "authorized": 0, "unauthorized": 0, "validation_passed": False}
    total_drones = len(drone_data)
    authorized_count = sum(1 for d in drone_data if isinstance(d, dict) and not d.get("unauthorized"))
    unauthorized_count = sum(1 for d in drone_data if isinstance(d, dict) and d.get("unauthorized"))
    validation_passed = (authorized_count + unauthorized_count) == total_drones
    if not validation_passed and total_drones > 0: logger.warning(f"Validation FAILED: Total={total_drones}, Auth={authorized_count}, Unauth={unauthorized_count}")
    return {"total_drones": total_drones, "authorized": authorized_count, "unauthorized": unauthorized_count, "validation_passed": validation_passed}

# --- ORIGINAL Individual Send Alert Email (Kept for /test-email endpoint if needed) ---
def send_alert_email(callsign: str, latitude: Optional[float], longitude: Optional[float], zone_name: Optional[str]):
    logger.info("📨 Preparing to send SINGLE alert email...")
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD or not ALERT_EMAIL:
        logger.error("❌ Missing email credentials. Cannot send email.")
        return
    lat = latitude if latitude is not None else 'N/A'
    lon = longitude if longitude is not None else 'N/A'
    lat_str = f"{lat:.4f}" if isinstance(lat, float) else str(lat)
    lon_str = f"{lon:.4f}" if isinstance(lon, float) else str(lon)
    subject = "🚨 Unauthorized Drone Alert (Single)"
    body = ( f"An unauthorized drone has been detected!\n\n"
             f"🛸 Callsign: {callsign or 'Unknown'}\n📍 Location: Latitude {lat_str}, Longitude {lon_str}\n"
             f"🚫 Restricted Zone: {zone_name or 'Unknown'}\n\n🕒 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg["Subject"] = EMAIL_ADDRESS, ALERT_EMAIL, subject
    msg.attach(MIMEText(body, "plain"))
    server = None
    try:
        logger.info(f"🔐 Connecting to SMTP server (smtp.gmail.com:465) as {EMAIL_ADDRESS} (SINGLE)...")
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30)
        logger.info("   Setting debug level to 1...")
        server.set_debuglevel(0) # Set to 0 to reduce log spam, set to 1 for debugging
        logger.info("   Attempting EHLO/HELO...")
        server.ehlo()
        logger.info(f"   Attempting login for {EMAIL_ADDRESS}...")
        login_response = server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        logger.info(f"✅ Login successful. Response: {login_response}")
        logger.info(f"   Attempting to send email to {ALERT_EMAIL}...")
        send_response = server.send_message(msg)
        logger.info(f"✅ Email sent successfully. Response: {send_response}")
    except smtplib.SMTPAuthenticationError as e: logger.error(f"❌ SMTP Auth Error (Single): {e}", exc_info=True)
    except smtplib.SMTPConnectError as e: logger.error(f"❌ SMTP Connect Error (Single): {e}", exc_info=True)
    except smtplib.SMTPRecipientsRefused as e: logger.error(f"❌ SMTP Recipient Error (Single): {e}", exc_info=True)
    except smtplib.SMTPHeloError as e: logger.error(f"❌ SMTP Helo/Ehlo Error (Single): {e}", exc_info=True)
    except smtplib.SMTPSenderRefused as e: logger.error(f"❌ SMTP Sender Error (Single): {e}", exc_info=True)
    except smtplib.SMTPDataError as e: logger.error(f"❌ SMTP Data Error (Single): {e}", exc_info=True)
    except TimeoutError: logger.error("❌ SMTP Operation Timed Out (Single).", exc_info=True)
    except Exception as e: logger.error(f"❌ General Email Sending Error (Single) ({type(e).__name__}): {e}", exc_info=True)
    finally:
        if server:
             try:
                 logger.info("   Closing SMTP connection (Single)...")
                 server.quit()
             except Exception as e: logger.warning(f"   Error closing SMTP connection (Single): {e}")
        logger.info("📨 Finished send_alert_email attempt.")

# --- NEW Batched Send Alert Email Function ---
def send_batched_alert_email(alerts: List[Dict[str, Any]]):
    """Sends a single email summarizing multiple alerts."""
    alert_count = len(alerts)
    if alert_count == 0:
        logger.info("No new alerts to send in this batch.")
        return

    logger.info(f"📨 Preparing to send batched alert email for {alert_count} drone(s)...")
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD or not ALERT_EMAIL:
        logger.error("❌ Missing email credentials. Cannot send batched email.")
        return

    # Create the email body
    subject = f"🚨 {alert_count} Unauthorized Drone Alert(s)"
    body_lines = [f"Detected {alert_count} new unauthorized drone flight(s):\n"]

    for i, alert in enumerate(alerts):
        callsign = alert.get('callsign', 'Unknown')
        lat = alert.get('latitude', 'N/A')
        lon = alert.get('longitude', 'N/A')
        zone_name = alert.get('zone_name', 'Unknown')
        lat_str = f"{lat:.4f}" if isinstance(lat, float) else str(lat)
        lon_str = f"{lon:.4f}" if isinstance(lon, float) else str(lon)

        body_lines.append(f"--- Alert {i+1} ---")
        body_lines.append(f"🛸 Callsign: {callsign}")
        body_lines.append(f"📍 Location: Lat {lat_str}, Lon {lon_str}")
        body_lines.append(f"🚫 Restricted Zone: {zone_name}")
        body_lines.append("") # Add a blank line

    body_lines.append(f"\n🕒 Report Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    body = "\n".join(body_lines)

    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = ALERT_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    server = None
    try:
        # --- Single Connection/Login for the batch ---
        logger.info(f"🔐 Connecting to SMTP server (smtp.gmail.com:465) as {EMAIL_ADDRESS} for batch...")
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=45) # Slightly longer timeout for batch potentially
        logger.info("   Setting debug level to 0...") # Usually 0 for production, 1 for debugging
        server.set_debuglevel(0)
        logger.info("   Attempting EHLO/HELO...")
        server.ehlo()
        logger.info(f"   Attempting login for {EMAIL_ADDRESS}...")
        login_response = server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        logger.info(f"✅ Batch Login successful. Response Code: {login_response[0] if isinstance(login_response, tuple) else 'N/A'}") # Only log code
        # --- Send the single message ---
        logger.info(f"   Attempting to send batched email to {ALERT_EMAIL}...")
        send_response = server.send_message(msg)
        logger.info(f"✅ Batched email sent successfully. Response: {send_response}") # Response is usually {} on success

    # Explicitly catch the server disconnected error during login/auth phase
    except smtplib.SMTPServerDisconnected as e: logger.error(f"❌ SMTP Server Disconnected (Batch): {e}. Possibly during login/auth.", exc_info=True)
    except smtplib.SMTPAuthenticationError as e: logger.error(f"❌ SMTP Auth Error (Batch): {e}", exc_info=True)
    except smtplib.SMTPConnectError as e: logger.error(f"❌ SMTP Connect Error (Batch): {e}", exc_info=True)
    except smtplib.SMTPRecipientsRefused as e: logger.error(f"❌ SMTP Recipient Error (Batch): {e}", exc_info=True)
    except smtplib.SMTPHeloError as e: logger.error(f"❌ SMTP Helo/Ehlo Error (Batch): {e}", exc_info=True)
    except smtplib.SMTPSenderRefused as e: logger.error(f"❌ SMTP Sender Error (Batch): {e}", exc_info=True)
    except smtplib.SMTPDataError as e: logger.error(f"❌ SMTP Data Error (Batch): {e}", exc_info=True)
    except TimeoutError: logger.error("❌ SMTP Operation Timed Out (Batch).", exc_info=True)
    except Exception as e: logger.error(f"❌ General Email Sending Error (Batch) ({type(e).__name__}): {e}", exc_info=True)
    finally:
        if server:
             try:
                 logger.info("   Closing SMTP connection (Batch)...")
                 server.quit()
             except smtplib.SMTPServerDisconnected:
                 logger.warning("   SMTP server already disconnected before quit (Batch).")
             except Exception as e:
                 logger.warning(f"   Error closing SMTP connection (Batch): {e}")
        logger.info("📨 Finished send_batched_alert_email attempt.")


# Cache for recently alerted drones
ALERTED_DRONES: Dict[str, float] = {}
ALERT_COOLDOWN: int = 300 # 5 minutes in seconds

# Fetch Live Drone Data (Main data processing function) - MODIFIED FOR BATCHING
# @app.get("/fetch-drones-live") # This decorator isn't needed if only called internally
def fetch_opensky_data() -> Dict[str, Any]:
    """Fetches drone data, processes, checks zones, handles simulation, and queues alerts."""
    # --- Step 1: Fetch Raw Data ---
    flights: Optional[List[List[Any]]] = None # Initialize flights
    try:
        logger.info("Attempting to fetch data from OpenSky API...")
        response = requests.get(OPENSKY_URL, timeout=15)
        if response.status_code == 429:
             logger.warning("❌ OpenSky API request blocked: 429 Too Many Requests. Using simulated data.")
             flights = [] # Indicate simulation needed
        else:
             response.raise_for_status() # Raise HTTPError for other bad responses (4xx, 5xx)
             raw_data = response.json()
             flights = raw_data.get("states") if isinstance(raw_data, dict) else []
             if flights is None: flights = [] # Handle null states case
             logger.info(f"Fetched {len(flights)} states from OpenSky API.")
    except requests.exceptions.Timeout:
        logger.error("❌ OpenSky API request timed out. Using simulated data.")
        flights = []
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ OpenSky API request error: {e}. Using simulated data.")
        if flights is None: flights = []
    except json.JSONDecodeError as e:
        logger.error(f"❌ OpenSky API JSON decode error: {e}. Using simulated data.", exc_info=True)
        if flights is None: flights = []
    except Exception as e: # Catch broader exceptions during fetch
        logger.error(f"❌ Unexpected error fetching OpenSky data: {e}", exc_info=True)
        if flights is None: flights = [] # Ensure flights is list

    # --- Step 2: Structure and Process Real Flights ---
    structured_flights: List[Dict[str, Any]] = []
    current_time: float = time.time()
    # ***** NEW: Initialize list for batching alerts *****
    alerts_to_batch_this_run: List[Dict[str, Any]] = []

    if flights: # Process real flights if available and not None
        for state in flights:
            # Basic validation of state format
            if not isinstance(state, list) or len(state) < 14: continue
            # Extract data with checks for None/type
            callsign = state[1].strip() if isinstance(state[1], str) else None
            longitude = state[5] if isinstance(state[5], (float, int)) else None
            latitude = state[6] if isinstance(state[6], (float, int)) else None
            velocity = state[9] if isinstance(state[9], (float, int)) else None
            geo_altitude = state[13] if isinstance(state[13], (float, int)) else None
            baro_altitude = state[7] if isinstance(state[7], (float, int)) else None

            # Skip if essential data missing
            if not callsign or latitude is None or longitude is None: continue

            # Choose altitude
            altitude_to_use = geo_altitude if geo_altitude is not None else baro_altitude

            # Check if unauthorized
            unauthorized, zone_name = is_unauthorized_flight(latitude, longitude)

            # Structure data
            drone_data: Dict[str, Any] = {
                "callsign": callsign,
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude_to_use if altitude_to_use is not None else 0,
                "velocity": velocity if velocity is not None else 0,
                "unauthorized": unauthorized,
                "zone": zone_name # Will be None if not unauthorized
            }
            structured_flights.append(drone_data)

            # Optionally log to database
            if DRONE_DB_ENABLED: log_drone(drone_data)

            # If unauthorized, check cooldown and add to batch list if needed
            if unauthorized:
                last_alert_time = ALERTED_DRONES.get(callsign)
                if last_alert_time is None or (current_time - last_alert_time) > ALERT_COOLDOWN:
                    logger.info(f"Unauthorized drone {callsign} in {zone_name}. Adding to alert batch.")
                    # ***** MODIFIED: Add details to batch list *****
                    alerts_to_batch_this_run.append({
                        "callsign": callsign,
                        "latitude": latitude,
                        "longitude": longitude,
                        "zone_name": zone_name
                    })
                    # ***** Update cooldown timestamp *****
                    ALERTED_DRONES[callsign] = current_time
                else:
                     logger.info(f"Unauthorized drone {callsign} in {zone_name} within cooldown.")

    # --- Step 3: Clean up old entries in alert cache ---
    expired_drones = [cs for cs, ts in ALERTED_DRONES.items() if (current_time - ts) > ALERT_COOLDOWN]
    if expired_drones:
        logger.debug(f"Removing {len(expired_drones)} expired drones from alert cache: {', '.join(expired_drones)}")
        for cs in expired_drones:
            if cs in ALERTED_DRONES: del ALERTED_DRONES[cs]

    # --- Step 4: Add Simulation Data if Needed ---
    if not flights: # Use simulation only if OpenSky failed or returned empty/null states
        logger.info("No valid real-time flights processed. Generating simulation data within CONUS...")
        # Simulate authorized flights outside zones
        sim_auth_count = 0
        attempts = 0
        target_auth_sim = random.randint(5, 15) # Slightly more simulation
        while sim_auth_count < target_auth_sim and attempts < 100: # Increased attempts limit
             attempts += 1
             lat = random.uniform(CONUS_BOUNDS["lat_min"], CONUS_BOUNDS["lat_max"])
             lon = random.uniform(CONUS_BOUNDS["lon_min"], CONUS_BOUNDS["lon_max"])
             is_unauth_sim_check, _ = is_unauthorized_flight(lat, lon)
             if not is_unauth_sim_check:
                 sim_drone_data = {"callsign": f"SIM-AUTH-{sim_auth_count+1}", "latitude": lat, "longitude": lon, "altitude": random.randint(500, 3000), "velocity": random.uniform(50, 300), "unauthorized": False, "zone": None}
                 structured_flights.append(sim_drone_data)
                 if DRONE_DB_ENABLED: log_drone(sim_drone_data)
                 sim_auth_count += 1

        # Simulate unauthorized flights near zones
        target_unauth_sim = random.randint(2, 5)
        if RESTRICTED_ZONES: # Check if zones exist
            for i in range(target_unauth_sim):
                 zone = random.choice(RESTRICTED_ZONES)
                 # Simulate slightly inside or just outside the radius for realism
                 radius_factor = random.uniform(0.5, 1.1) # 50% to 110% of radius
                 angle = random.uniform(0, 2 * 3.14159)
                 # Convert radius (km) to approximate degrees (very rough, varies by lat)
                 dist_deg = (zone['radius'] * radius_factor) / 111.0
                 lat = zone["latitude"] + dist_deg * cos(angle)
                 lon = zone["longitude"] + dist_deg * sin(angle) / cos(radians(zone["latitude"])) # Lon adjust
                 # Clamp to CONUS bounds just in case
                 lat = max(CONUS_BOUNDS["lat_min"], min(CONUS_BOUNDS["lat_max"], lat))
                 lon = max(CONUS_BOUNDS["lon_min"], min(CONUS_BOUNDS["lon_max"], lon))
                 # Re-check if the *simulated* point ended up in *any* zone
                 is_unauth_sim, zone_name_sim = is_unauthorized_flight(lat, lon)
                 sim_unauth_callsign = f"SIM-UNAUTH-{i+1}"

                 sim_drone_data = {"callsign": sim_unauth_callsign, "latitude": lat, "longitude": lon, "altitude": random.randint(100, 1500), "velocity": random.uniform(30, 150), "unauthorized": is_unauth_sim, "zone": zone_name_sim}
                 structured_flights.append(sim_drone_data)
                 if DRONE_DB_ENABLED: log_drone(sim_drone_data)

                 # Add to batch if simulated as unauthorized and not on cooldown
                 if is_unauth_sim:
                     last_alert_time = ALERTED_DRONES.get(sim_unauth_callsign)
                     if last_alert_time is None or (current_time - last_alert_time) > ALERT_COOLDOWN:
                         logger.info(f"Simulated unauthorized drone {sim_unauth_callsign} in {zone_name_sim}. Adding to alert batch.")
                         # ***** MODIFIED: Add to batch list *****
                         alerts_to_batch_this_run.append({
                             "callsign": sim_unauth_callsign,
                             "latitude": lat,
                             "longitude": lon,
                             "zone_name": zone_name_sim
                         })
                         # ***** Update cooldown timestamp *****
                         ALERTED_DRONES[sim_unauth_callsign] = current_time
                     else:
                         logger.info(f"Simulated unauthorized drone {sim_unauth_callsign} in {zone_name_sim} within cooldown.")

    # --- Step 5: Send Batched Email (if any alerts were added) ---
    # ***** NEW: Call the batch sending function AFTER processing all drones *****
    if alerts_to_batch_this_run:
        logger.info(f"Collected {len(alerts_to_batch_this_run)} new alerts in this cycle. Attempting batch email.")
        try:
            # Run synchronously for now, can be moved to thread executor if needed
            send_batched_alert_email(alerts_to_batch_this_run)
        except Exception as email_err:
            logger.error(f"Error occurred during call to send_batched_alert_email: {email_err}", exc_info=True)
    else:
        logger.info("No new off-cooldown unauthorized drones found in this cycle. No batch email needed.")

    # --- Step 6: Final Validation and Return ---
    validation_result = validate_drone_counts(structured_flights)
    unauthorized_count = validation_result.get("unauthorized", 0)
    logger.info(f"Processed data: Total={validation_result.get('total_drones', 0)}, Unauthorized={unauthorized_count}, Validation OK={validation_result.get('validation_passed', False)}")
    logger.info(f"Returning {len(structured_flights)} processed drones for WebSocket/API.")
    return {"drones": structured_flights, "validation": validation_result}

# WebSocket Streaming Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    logger.info("WebSocket client attempting to connect...")
    await websocket.accept()
    client_host = websocket.client.host if websocket.client else "Unknown"
    client_port = websocket.client.port if websocket.client else "N/A"
    client_id = f"{client_host}:{client_port}"
    logger.info(f"WebSocket client connected: {client_id}")

    active_connections: List[WebSocket] = [] # Manage connections if needed, but example sends to one
    active_connections.append(websocket) # Simple add for this example

    try:
        while True:
            logger.debug(f"[{client_id}] Starting data fetch cycle for WebSocket...")
            # Run the potentially blocking I/O operation (requests + email sending) in a thread pool
            loop = asyncio.get_running_loop()
            # Use run_in_executor for the whole fetch_opensky_data function
            drone_data_packet = await loop.run_in_executor(None, fetch_opensky_data)

            packet_size = len(json.dumps(drone_data_packet)) # Calculate size before send
            drones_count = len(drone_data_packet.get('drones', []))
            logger.info(f"[{client_id}] Sending data packet ({packet_size} bytes) with {drones_count} drones.")

            try:
                # Ensure connection is still open before sending
                # Note: FastAPI handles basic checks, but explicit check can be added if needed
                await websocket.send_text(json.dumps(drone_data_packet))
            except WebSocketDisconnect: # Catch if disconnected during send attempt
                logger.warning(f"[{client_id}] WebSocket disconnected during send attempt.")
                break # Exit loop if cannot send
            except Exception as send_err: # Catch other potential send errors
                logger.error(f"[{client_id}] Error sending data over WebSocket: {send_err}", exc_info=True)
                # Depending on the error, you might want to break or continue
                break # Assume connection is unstable

            # Adjust sleep duration as needed - 60 seconds is reasonable for API limits and UI updates
            sleep_duration = 60
            logger.debug(f"[{client_id}] WebSocket send complete. Sleeping for {sleep_duration} seconds...")
            await asyncio.sleep(sleep_duration)

    except WebSocketDisconnect as e:
        logger.warning(f"WebSocket client {client_id} disconnected cleanly. Code: {e.code}, Reason: {e.reason}")
    except asyncio.CancelledError:
        logger.info(f"WebSocket task for {client_id} was cancelled (likely server shutdown).")
    except RuntimeError as e:
        if "Cannot call 'send' after connection is closed" in str(e):
            logger.warning(f"[{client_id}] Attempted send on closed WebSocket connection (RuntimeError).")
        else:
            logger.error(f"[{client_id}] Unexpected RuntimeError in WebSocket endpoint: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"[{client_id}] Unexpected error in WebSocket endpoint: {type(e).__name__} - {e}", exc_info=True)
        try:
            # Attempt to gracefully close from server-side if an unexpected error occurs
            await websocket.close(code=1011) # Internal Server Error code
        except Exception as close_err:
             logger.error(f"[{client_id}] Error trying to close WebSocket after exception: {close_err}")
    finally:
        logger.info(f"WebSocket connection handling finished for {client_id}.")
        if websocket in active_connections:
            active_connections.remove(websocket) # Clean up connection list if used

# REST Endpoints

@app.get("/restricted-zones")
def get_restricted_zones() -> Dict[str, List[Dict[str, Any]]]:
    """Returns the list of defined restricted zones."""
    return {"restricted_zones": RESTRICTED_ZONES}

# Add REST endpoint to trigger fetch_opensky_data manually (for testing API part)
@app.get("/fetch-drones-manual")
async def get_drones_manual() -> Dict[str, Any]:
     """Manually trigger the data fetching and processing logic."""
     logger.info("Manual fetch endpoint '/fetch-drones-manual' triggered.")
     # Run in executor as it involves I/O and potential email sending
     loop = asyncio.get_running_loop()
     drone_data_packet = await loop.run_in_executor(None, fetch_opensky_data)
     return drone_data_packet

@app.post("/force-drone")
def force_custom_drone(latitude: float = Query(...), longitude: float = Query(...)) -> Dict[str, Any]:
    """Checks a specific coordinate against restricted zones."""
    logger.info(f"Force drone check request for Lat: {latitude}, Lon: {longitude}")
    unauthorized, zone_name = is_unauthorized_flight(latitude, longitude)
    return {"callsign": "TEST-DRONE", "latitude": latitude, "longitude": longitude, "unauthorized": unauthorized, "zone": zone_name}

# Manual Email Test Endpoint (uncomment to use)
# @app.get("/test-email")
# def test_email():
#     logger.info("Manual email test endpoint triggered.")
#     # Example call to the *single* email function
#     send_alert_email(
#         callsign="TEST-EMAIL-001",
#         latitude=40.1234,
#         longitude=-74.5678,
#         zone_name="Hypothetical Test Zone"
#     )
#     return {"message": "Test email send function (single) called."}

# Root Endpoint
@app.get("/")
def home() -> Dict[str, str]:
    """Basic root endpoint indicating the API is running."""
    return {"message": "🚁 Illegal Drone Tracking API with WebSocket running. Connect clients to /ws"}

# Start Server
if __name__ == "__main__":
    logger.info("Starting Uvicorn server on 0.0.0.0:8000...")
    uvicorn.run(
        "main:app", # Points to the 'app' instance in this 'main.py' file
        host="0.0.0.0", # Listen on all available network interfaces
        port=8000,
        reload=False, # IMPORTANT: Keep reload=False for stable WebSockets, DB connections, and email cooldowns
        log_level="info" # Uvicorn's own log level
    )