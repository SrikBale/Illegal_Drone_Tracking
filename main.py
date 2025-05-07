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

# --- Setup & Configuration ---

# Attempt to import drone_db safely
try:
    from drone_db import log_drone
    DRONE_DB_ENABLED = True
except ImportError:
    DRONE_DB_ENABLED = False
    # Define a placeholder if drone_db is optional
    def log_drone(drone_data: Dict[str, Any]):
        # print(f"DB Logging Disabled: {drone_data.get('callsign')}") # Uncomment for debug print
        pass

# Load environment variables
load_dotenv()

# Configure logging
# Set level to DEBUG to see all logs, INFO for less verbosity
LOG_LEVEL = logging.DEBUG # Or logging.INFO
logging.basicConfig(
    level=LOG_LEVEL,
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
# Avoid logging password status directly in production logs unless debugging
# logger.info(f"Loaded EMAIL_PASSWORD: {'Set' if EMAIL_PASSWORD else 'Not Set'}")
logger.info(f"Loaded ALERT_EMAIL: {ALERT_EMAIL}")

# CORS Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Constants & Definitions ---

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

# CONUS bounding box (approximate)
CONUS_BOUNDS = {
    "lat_min": 24.0, "lat_max": 49.0,
    "lon_min": -125.0, "lon_max": -66.0
}

# Cache for recently alerted drones (callsign: timestamp)
ALERTED_DRONES: Dict[str, float] = {}
ALERT_COOLDOWN: int = 300 # 5 minutes in seconds

# --- Helper Functions ---

def haversine(lat1: Optional[float], lon1: Optional[float], lat2: float, lon2: float) -> float:
    """Calculate distance between two points on Earth using Haversine."""
    R = 6371 # Earth radius in kilometers
    if lat1 is None or lon1 is None:
        # Reduced verbosity for common case, change to WARNING if needed
        logger.debug(f"Haversine called with None coordinates: ({lat1}, {lon1})")
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
        distance = R * c
        # logger.debug(f"Haversine calc: ({lat1:.4f},{lon1:.4f}) to ({lat2:.4f},{lon2:.4f}) = {distance:.2f} km") # Verbose log
        return distance
    except (ValueError, TypeError) as e:
        logger.error(f"Error in Haversine calculation ({lat1}, {lon1} to {lat2}, {lon2}): {e}", exc_info=True)
        return float('inf')

def is_unauthorized_flight(latitude: Optional[float], longitude: Optional[float]) -> tuple[bool, Optional[str]]:
    """Checks if coordinates fall within any defined restricted zone."""
    if latitude is None or longitude is None: return False, None

    # logger.debug(f"--- Checking drone auth at Lat: {latitude:.4f}, Lon: {longitude:.4f} ---") # Debug log

    for zone in RESTRICTED_ZONES:
        try:
            # Basic validation
            if not all(k in zone for k in ["latitude", "longitude", "radius", "name"]):
                logger.warning(f"Skipping zone due to missing keys: {zone.get('name', 'Unknown')}")
                continue
            if not all(isinstance(zone[k], (int, float)) for k in ["latitude", "longitude", "radius"]):
                logger.warning(f"Skipping zone due to invalid coordinate/radius types: {zone.get('name', 'Unknown')}")
                continue

            zone_lat = zone["latitude"]
            zone_lon = zone["longitude"]
            zone_radius = zone["radius"]
            zone_name = zone["name"]

            distance = haversine(latitude, longitude, zone_lat, zone_lon)

            # logger.debug(f"Checking against zone '{zone_name}' (R: {zone_radius}km): Dist = {distance:.2f}km") # Verbose

            if distance <= zone_radius:
                # Log only when found inside for less noise
                logger.info(f"!!! Drone IN zone '{zone_name}'. Lat: {latitude:.4f}, Lon: {longitude:.4f}. Dist: {distance:.2f}km <= Radius: {zone_radius}km. UNAUTHORIZED")
                return True, zone_name

        except Exception as e:
             logger.error(f"Error checking zone {zone.get('name', 'Unknown')} for ({latitude}, {longitude}): {e}", exc_info=True)

    # logger.debug(f"--- Drone at Lat: {latitude:.4f}, Lon: {longitude:.4f} is AUTHORIZED ---") # Debug log
    return False, None

def validate_drone_counts(drone_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validates consistency of drone counts in a list."""
    if not isinstance(drone_data, list): return {"total_drones": 0, "authorized": 0, "unauthorized": 0, "validation_passed": False}
    total_drones = len(drone_data)
    authorized_count = sum(1 for d in drone_data if isinstance(d, dict) and d.get("unauthorized") is False) # Explicit check for False
    unauthorized_count = sum(1 for d in drone_data if isinstance(d, dict) and d.get("unauthorized") is True) # Explicit check for True
    validation_passed = (authorized_count + unauthorized_count) == total_drones
    if not validation_passed and total_drones > 0:
        # More detailed warning
        unknown_status_count = total_drones - (authorized_count + unauthorized_count)
        logger.warning(f"Validation FAILED: Total={total_drones}, Auth={authorized_count}, Unauth={unauthorized_count}, UnknownStatus={unknown_status_count}")
    return {"total_drones": total_drones, "authorized": authorized_count, "unauthorized": unauthorized_count, "validation_passed": validation_passed}

# --- Email Sending Functions ---

def send_alert_email(callsign: str, latitude: Optional[float], longitude: Optional[float], zone_name: Optional[str]):
    """Sends a single alert email (kept for testing)."""
    logger.info("📨 Preparing to send SINGLE alert email...")
    if not all([EMAIL_ADDRESS, EMAIL_PASSWORD, ALERT_EMAIL]):
        logger.error("❌ Missing email credentials. Cannot send single email.")
        return
    # ... (rest of the single email logic remains the same) ...
    lat = latitude if latitude is not None else 'N/A'
    lon = longitude if longitude is not None else 'N/A'
    lat_str = f"{lat:.4f}" if isinstance(lat, float) else str(lat)
    lon_str = f"{lon:.4f}" if isinstance(lon, float) else str(lon)
    subject = "🚨 Unauthorized Drone Alert (Single Test)"
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
        logger.info("   Setting debug level to 0...")
        server.set_debuglevel(0) # 0 for less spam, 1 for debug
        logger.info("   Attempting EHLO/HELO...")
        server.ehlo()
        logger.info(f"   Attempting login for {EMAIL_ADDRESS}...")
        login_response = server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        logger.info(f"✅ Login successful. Response Code: {login_response[0] if isinstance(login_response, tuple) else 'N/A'}")
        logger.info(f"   Attempting to send email to {ALERT_EMAIL}...")
        send_response = server.send_message(msg)
        logger.info(f"✅ Email sent successfully. Response: {send_response}")
    except Exception as e: logger.error(f"❌ Error sending SINGLE email: {type(e).__name__} - {e}", exc_info=True)
    finally:
        if server:
             try: server.quit()
             except Exception as e: logger.warning(f"   Error closing SMTP connection (Single): {e}")
        logger.info("📨 Finished send_alert_email attempt.")


def send_batched_alert_email(alerts: List[Dict[str, Any]]):
    """Sends a single email summarizing multiple new alerts."""
    alert_count = len(alerts)
    if alert_count == 0:
        # logger.debug("No new alerts to send in this batch.") # Reduce noise
        return

    logger.info(f"📨 Preparing to send batched alert email for {alert_count} drone(s)...")
    if not all([EMAIL_ADDRESS, EMAIL_PASSWORD, ALERT_EMAIL]):
        logger.error("❌ Missing email credentials. Cannot send batched email.")
        return

    # --- Create Email Body ---
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
        body_lines.append("")
    body_lines.append(f"\n🕒 Report Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    body = "\n".join(body_lines)

    # --- Setup Email Message ---
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg["Subject"] = EMAIL_ADDRESS, ALERT_EMAIL, subject
    msg.attach(MIMEText(body, "plain"))

    # --- Send Email ---
    server = None
    try:
        logger.info(f"🔐 Connecting to SMTP server (smtp.gmail.com:465) as {EMAIL_ADDRESS} for batch...")
        # Use slightly longer timeout for potential batch operations
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=45)
        server.set_debuglevel(0) # 0 for production, 1 for detailed SMTP logs
        server.ehlo()
        logger.info(f"   Attempting batch login for {EMAIL_ADDRESS}...")
        login_response = server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        logger.info(f"✅ Batch Login successful. Response Code: {login_response[0] if isinstance(login_response, tuple) else 'N/A'}")
        logger.info(f"   Attempting to send batched email to {ALERT_EMAIL}...")
        send_response = server.send_message(msg) # Response is usually {} on success
        logger.info(f"✅ Batched email sent successfully. Response: {send_response}")
    except Exception as e:
        logger.error(f"❌ Error sending BATCHED email: {type(e).__name__} - {e}", exc_info=True)
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


# --- Core Data Fetching and Processing ---

def fetch_opensky_data() -> Dict[str, Any]:
    """
    Fetches drone data from OpenSky API or simulates data if API fails.
    Processes data, checks restricted zones, and prepares for batch alerts.
    NOTE: This is a SYNCHRONOUS function, intended to be run in an executor.
    """
    logger.info("====== fetch_opensky_data START ======") # LOG START
    flights: Optional[List[List[Any]]] = None
    api_source = "OpenSky API" # Track data source

    # --- Step 1: Fetch Raw Data ---
    try:
        logger.info("Attempting OpenSky API fetch...")
        response = requests.get(OPENSKY_URL, timeout=15) # Reasonable timeout
        if response.status_code == 429:
            logger.warning("❌ OpenSky API request blocked: 429 Too Many Requests. Using simulation.")
            flights = [] # Indicate simulation needed
            api_source = "Simulation (429)"
        elif response.status_code == 204: # Handle No Content explicitly
             logger.info("OpenSky API returned 204 No Content. No states available currently.")
             flights = [] # Treat as no data, might not need simulation depending on requirements
             api_source = "OpenSky API (204)" # Or maybe still trigger simulation? You decide.
        else:
            response.raise_for_status() # Raise HTTPError for other bad responses (4xx, 5xx)
            raw_data = response.json()
            # Check if 'states' key exists and is a list
            if isinstance(raw_data, dict) and isinstance(raw_data.get("states"), list):
                flights = raw_data["states"]
                logger.info(f"OpenSky fetch SUCCESS, {len(flights)} states received.")
            else:
                logger.warning(f"OpenSky response format unexpected or 'states' is not a list. Response: {raw_data}. Using simulation.")
                flights = []
                api_source = "Simulation (Bad Format)"

    except requests.exceptions.Timeout:
        logger.error("❌ OpenSky API request timed out. Using simulation.")
        flights = []
        api_source = "Simulation (Timeout)"
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ OpenSky API request error: {e}. Using simulation.")
        flights = [] # Ensure flights is list
        api_source = f"Simulation (Request Error: {type(e).__name__})"
    except json.JSONDecodeError as e:
        logger.error(f"❌ OpenSky API JSON decode error: {e}. Using simulation.", exc_info=True)
        flights = []
        api_source = "Simulation (JSON Error)"
    except Exception as e: # Catch broader exceptions during fetch
        logger.error(f"❌ Unexpected error fetching OpenSky data: {e}", exc_info=True)
        flights = []
        api_source = f"Simulation (Unexpected Error: {type(e).__name__})"

    # --- Step 2: Structure and Process Flights (Real or Simulated) ---
    structured_flights: List[Dict[str, Any]] = []
    current_time: float = time.time()
    alerts_to_batch_this_run: List[Dict[str, Any]] = []

    if flights: # Process real flights if API returned data
        logger.debug(f"Processing {len(flights)} real flight states...")
        for state in flights:
            if not isinstance(state, list) or len(state) < 14: continue # Basic validation

            # Extract data safely, providing None as default
            callsign = str(state[1]).strip() if state[1] else None # Ensure string, handle empty
            longitude = float(state[5]) if isinstance(state[5], (float, int)) else None
            latitude = float(state[6]) if isinstance(state[6], (float, int)) else None
            velocity = float(state[9]) if isinstance(state[9], (float, int)) else None # meters/sec
            geo_altitude = float(state[13]) if isinstance(state[13], (float, int)) else None # meters
            baro_altitude = float(state[7]) if isinstance(state[7], (float, int)) else None # meters

            # Skip if essential data missing for mapping/checking
            if not callsign or latitude is None or longitude is None:
                logger.debug(f"Skipping state due to missing callsign/lat/lon: {state}")
                continue

            # Choose altitude (prefer geometric)
            altitude_m = geo_altitude if geo_altitude is not None else baro_altitude
            # Convert velocity from m/s to km/h (approx) if available
            velocity_kmh = (velocity * 3.6) if velocity is not None else 0

            # Check authorization status
            unauthorized, zone_name = is_unauthorized_flight(latitude, longitude)

            # Structure data for frontend/DB
            drone_data: Dict[str, Any] = {
                "callsign": callsign,
                "latitude": latitude,
                "longitude": longitude,
                "altitude": round(altitude_m) if altitude_m is not None else 0, # Use rounded meters
                "velocity": round(velocity_kmh, 1), # Use km/h rounded
                "unauthorized": unauthorized,
                "zone": zone_name,
                "source": api_source # Add source info
            }
            structured_flights.append(drone_data)

            # Optionally log to database
            if DRONE_DB_ENABLED:
                try:
                    log_drone(drone_data)
                except Exception as db_err:
                    logger.error(f"Error logging drone {callsign} to DB: {db_err}", exc_info=False) # Avoid excessive logs

            # Check alert cooldown and add to batch if newly unauthorized
            if unauthorized:
                last_alert_time = ALERTED_DRONES.get(callsign)
                if last_alert_time is None or (current_time - last_alert_time) > ALERT_COOLDOWN:
                    logger.info(f"ALERT: Unauthorized drone {callsign} in {zone_name}. Adding to alert batch.")
                    alerts_to_batch_this_run.append({
                        "callsign": callsign, "latitude": latitude, "longitude": longitude, "zone_name": zone_name
                    })
                    ALERTED_DRONES[callsign] = current_time # Update cooldown timestamp
                else:
                    logger.debug(f"Unauthorized drone {callsign} in {zone_name} still within cooldown ({current_time - last_alert_time:.0f}s < {ALERT_COOLDOWN}s).")

    # --- Step 3: Simulate Data if API Failed or Returned No Data ---
    # Decide if simulation should run even on API 204 No Content - currently yes
    if not flights: # This condition is true if flights is [] or was never assigned (due to error)
        logger.info(f">>> ENTERING SIMULATION BLOCK (Reason: {api_source}) <<<")
        sim_auth_count = 0
        sim_unauth_count = 0
        attempts_auth = 0
        target_auth_sim = random.randint(25, 50) # Simulate more drones generally
        target_unauth_sim = random.randint(5, 10) # Ensure some unauthorized ones

        # Simulate AUTHORIZED drones
        while sim_auth_count < target_auth_sim and attempts_auth < 500: # Increased attempts limit
             attempts_auth += 1
             lat = random.uniform(CONUS_BOUNDS["lat_min"], CONUS_BOUNDS["lat_max"])
             lon = random.uniform(CONUS_BOUNDS["lon_min"], CONUS_BOUNDS["lon_max"])
             is_unauth_sim_check, _ = is_unauthorized_flight(lat, lon)
             if not is_unauth_sim_check:
                 sim_callsign = f"SIM-A-{random.randint(1000, 9999)}" # More varied callsigns
                 sim_drone_data = {
                    "callsign": sim_callsign,
                    "latitude": round(lat, 6), "longitude": round(lon, 6),
                    "altitude": random.randint(300, 5000), # Meters
                    "velocity": random.randint(50, 300), # km/h
                    "unauthorized": False, "zone": None, "source": api_source
                 }
                 structured_flights.append(sim_drone_data)
                 # Log simulated authorized drone to DB (Expanded block)
                 if DRONE_DB_ENABLED:
                     try:
                         log_drone(sim_drone_data)
                     except Exception as db_log_err:
                         # Log a warning instead of passing silently, avoid full traceback unless needed
                         logger.warning(f"DB Log failed (Sim-Auth: {sim_drone_data.get('callsign', 'N/A')}): {db_log_err}", exc_info=False)
                 sim_auth_count += 1

        # Simulate UNAUTHORIZED drones
        if RESTRICTED_ZONES: # Check if zones exist
            for i in range(target_unauth_sim):
                 zone = random.choice(RESTRICTED_ZONES)
                 # Simulate slightly inside or just outside the radius
                 radius_factor = random.uniform(0.7, 1.0) # Mostly inside zone radius
                 angle = random.uniform(0, 2 * 3.14159)
                 # Convert radius (km) to approx degrees (rough)
                 dist_deg = (zone['radius'] * radius_factor) / 111.0
                 lat = zone["latitude"] + dist_deg * cos(angle)
                 lon = zone["longitude"] + dist_deg * sin(angle) / cos(radians(zone["latitude"]))
                 # Clamp to CONUS bounds
                 lat = max(CONUS_BOUNDS["lat_min"], min(CONUS_BOUNDS["lat_max"], lat))
                 lon = max(CONUS_BOUNDS["lon_min"], min(CONUS_BOUNDS["lon_max"], lon))
                 # Re-check if the *simulated* point is in *any* zone
                 is_unauth_sim, zone_name_sim = is_unauthorized_flight(lat, lon)
                 sim_unauth_callsign = f"SIM-U-{random.randint(100, 999)}"

                 # Ensure it's flagged as unauthorized if check passes
                 sim_drone_data = {
                    "callsign": sim_unauth_callsign,
                    "latitude": round(lat, 6), "longitude": round(lon, 6),
                    "altitude": random.randint(50, 1500), # Lower altitude typical
                    "velocity": random.randint(30, 150), # Slower typical
                    "unauthorized": is_unauth_sim, # Use result of check
                    "zone": zone_name_sim if is_unauth_sim else None,
                    "source": api_source
                 }
                 structured_flights.append(sim_drone_data)
                 # Log simulated unauthorized drone to DB (Expanded block)
                 if DRONE_DB_ENABLED:
                     try:
                         log_drone(sim_drone_data)
                     except Exception as db_log_err:
                         # Log a warning instead of passing silently
                         logger.warning(f"DB Log failed (Sim-Unauth: {sim_drone_data.get('callsign', 'N/A')}): {db_log_err}", exc_info=False)
                 sim_unauth_count += 1 if is_unauth_sim else 0

                 # Add to batch if simulated as unauthorized and not on cooldown
                 if is_unauth_sim:
                     last_alert_time = ALERTED_DRONES.get(sim_unauth_callsign)
                     if last_alert_time is None or (current_time - last_alert_time) > ALERT_COOLDOWN:
                         logger.info(f"ALERT: Simulated unauthorized drone {sim_unauth_callsign} in {zone_name_sim}. Adding to alert batch.")
                         alerts_to_batch_this_run.append({
                             "callsign": sim_unauth_callsign, "latitude": lat, "longitude": lon, "zone_name": zone_name_sim
                         })
                         ALERTED_DRONES[sim_unauth_callsign] = current_time
                     # else: logger.debug(f"Simulated unauth {sim_unauth_callsign} within cooldown.")
        else:
             logger.warning("Cannot simulate unauthorized drones, RESTRICTED_ZONES list is empty.")

        logger.info(f"<<< EXITED SIMULATION BLOCK - Added {sim_auth_count} auth, {sim_unauth_count} unauth >>>")

    # --- Step 4: Clean up Alert Cooldown Cache ---
    expired_drones = [cs for cs, ts in ALERTED_DRONES.items() if (current_time - ts) > ALERT_COOLDOWN]
    if expired_drones:
        logger.debug(f"Removing {len(expired_drones)} expired drones from alert cache: {', '.join(expired_drones)}")
        for cs in expired_drones:
            if cs in ALERTED_DRONES: del ALERTED_DRONES[cs]

    # --- Step 5: Send Batched Email (if new alerts occurred) ---
    if alerts_to_batch_this_run:
        logger.info(f"Attempting to send batch email for {len(alerts_to_batch_this_run)} new alerts...")
        try:
            # Running email sending synchronously within the executor thread is acceptable here,
            # as the entire fetch_opensky_data function runs off the main event loop.
            send_batched_alert_email(alerts_to_batch_this_run)
        except Exception as email_err:
            logger.error(f"Error occurred during call to send_batched_alert_email: {email_err}", exc_info=True)
    else:
        logger.debug("No new off-cooldown unauthorized drones found in this cycle. No batch email needed.")

    # --- Step 6: Final Validation and Return ---
    validation_result = validate_drone_counts(structured_flights)
    total_processed = validation_result.get('total_drones', 0)
    unauthorized_count = validation_result.get('unauthorized', 0)
    logger.info(f"Processed data: Total={total_processed}, Unauthorized={unauthorized_count}, Validation OK={validation_result.get('validation_passed', False)}")
    logger.info(f"====== fetch_opensky_data END - Returning {len(structured_flights)} drones (Source: {api_source}) ======") # LOG END + RESULT
    return {"drones": structured_flights, "validation": validation_result}

# --- WebSocket Endpoint ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handles WebSocket connections and streams drone data."""
    await websocket.accept()
    client_host = websocket.client.host if websocket.client else "Unknown"
    client_port = websocket.client.port if websocket.client else "N/A"
    client_id = f"{client_host}:{client_port}"
    logger.info(f"✅ WebSocket client connected: {client_id}")

    # Optional: Manage multiple connections if needed later
    # active_connections.add(websocket)

    loop_count = 0
    try:
        while True:
            loop_count += 1
            logger.info(f"[{client_id}] ---> WebSocket Loop Start - Iteration {loop_count} <---") # LOG START

            logger.debug(f"[{client_id}] Calling fetch_opensky_data in executor...")
            # Get the current running event loop
            loop = asyncio.get_running_loop()
            # Run the synchronous fetch_opensky_data function in a separate thread
            # to avoid blocking the main asyncio event loop.
            drone_data_packet = await loop.run_in_executor(None, fetch_opensky_data)
            logger.debug(f"[{client_id}] fetch_opensky_data returned.")

            # Log details before sending
            drones_count = len(drone_data_packet.get('drones', []))
            unauth_count = drone_data_packet.get('validation', {}).get('unauthorized', 0)
            source = "Unknown"
            if drones_count > 0:
                source = drone_data_packet['drones'][0].get('source', 'Unknown')
            logger.info(f"[{client_id}] Preparing to send packet: {drones_count} drones ({unauth_count} unauth). Source: {source}")

            # Optional: Log a small sample of data
            if drones_count > 0 and LOG_LEVEL == logging.DEBUG:
                sample_drone = drone_data_packet['drones'][0]
                logger.debug(f"[{client_id}] Sample drone[0]: CS={sample_drone.get('callsign')}, "
                             f"Lat={sample_drone.get('latitude'):.4f}, Lon={sample_drone.get('longitude'):.4f}, "
                             f"Unauth={sample_drone.get('unauthorized')}")

            try:
                # Send the JSON data packet as text
                await websocket.send_text(json.dumps(drone_data_packet))
                logger.debug(f"[{client_id}] Packet sent successfully.") # LOG AFTER SEND

            except WebSocketDisconnect:
                logger.warning(f"[{client_id}] WebSocket disconnected during send attempt. Exiting loop.")
                break # Exit loop if cannot send
            except Exception as send_err:
                logger.error(f"[{client_id}] Error sending data over WebSocket: {send_err}", exc_info=True)
                # Depending on the error, you might want to break or try again
                break # Assume connection is unstable

            # --- Sleep before next cycle ---
            # Adjust sleep duration as needed
            # 60 seconds is reasonable for API limits and UI updates
            sleep_duration = 60
            logger.info(f"[{client_id}] ---> WebSocket Loop End - Iteration {loop_count}. Sleeping for {sleep_duration}s... <---") # LOG END + SLEEP
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
        logger.info(f"⛔ WebSocket connection handling finished for {client_id}.")
        # Optional: Clean up connection if managing multiple
        # if websocket in active_connections:
        #     active_connections.remove(websocket)


# --- REST API Endpoints ---

@app.get("/restricted-zones")
async def get_restricted_zones() -> Dict[str, List[Dict[str, Any]]]:
    """Returns the list of defined restricted zones."""
    logger.debug("GET /restricted-zones request received.")
    return {"restricted_zones": RESTRICTED_ZONES}

# REST endpoint to trigger fetch_opensky_data manually (useful for initial load or testing)
@app.get("/fetch-drones-live")
async def get_drones_live() -> Dict[str, Any]:
     """
     Manually trigger the data fetching/processing logic via REST GET.
     Runs the core logic in an executor to avoid blocking.
     """
     logger.info("Manual fetch endpoint '/fetch-drones-live' triggered.")
     loop = asyncio.get_running_loop()
     # Use run_in_executor because fetch_opensky_data is sync and does I/O
     drone_data_packet = await loop.run_in_executor(None, fetch_opensky_data)
     logger.info("Manual fetch '/fetch-drones-live' completed.")
     return drone_data_packet

# Kept the original /fetch-drones-manual as well, it does the same thing now
@app.get("/fetch-drones-manual")
async def get_drones_manual() -> Dict[str, Any]:
     """Manually trigger the data fetching and processing logic (alternative endpoint)."""
     logger.info("Manual fetch endpoint '/fetch-drones-manual' triggered.")
     loop = asyncio.get_running_loop()
     drone_data_packet = await loop.run_in_executor(None, fetch_opensky_data)
     logger.info("Manual fetch '/fetch-drones-manual' completed.")
     return drone_data_packet

@app.post("/force-drone")
async def force_custom_drone(latitude: float = Query(...), longitude: float = Query(...)) -> Dict[str, Any]:
    """Checks a specific coordinate against restricted zones via POST."""
    logger.info(f"POST /force-drone check request for Lat: {latitude}, Lon: {longitude}")
    # This check is quick, doesn't strictly need executor unless haversine was very complex
    unauthorized, zone_name = is_unauthorized_flight(latitude, longitude)
    return {"callsign": "TEST-DRONE", "latitude": latitude, "longitude": longitude, "unauthorized": unauthorized, "zone": zone_name}

# Manual Email Test Endpoint (Uncomment decorator to enable)
# @app.get("/test-email")
# async def test_email(): # Make async if send_alert_email did heavy work, currently sync is fine
#     logger.info("Manual email test endpoint '/test-email' triggered.")
#     try:
#         # Example call to the *single* email function
#         send_alert_email(
#             callsign="TEST-EMAIL-001",
#             latitude=40.1234,
#             longitude=-74.5678,
#             zone_name="Hypothetical Test Zone"
#         )
#         return {"message": "Test email send function (single) called. Check logs and inbox."}
#     except Exception as e:
#          logger.error(f"Error in /test-email endpoint: {e}", exc_info=True)
#          return {"message": "Error calling test email function.", "error": str(e)}

# Root Endpoint
@app.get("/")
async def home() -> Dict[str, str]:
    """Basic root endpoint indicating the API is running."""
    logger.debug("GET / request received.")
    return {"message": "🚁 Illegal Drone Tracking API with WebSocket running. Connect clients to /ws"}

# --- Server Startup ---

if __name__ == "__main__":
    logger.info(f"Starting Uvicorn server on 0.0.0.0:8000 (Log Level: {logging.getLevelName(logger.level)})...")
    uvicorn.run(
        "main:app",       # App instance location
        host="0.0.0.0",   # Listen on all network interfaces
        port=8000,
        reload=False,     # IMPORTANT: Keep reload=False for stable WebSockets & state
        log_level=logging.getLevelName(logger.level).lower() # Sync Uvicorn log level
    )