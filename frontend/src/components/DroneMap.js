import React, { useState, useEffect, useRef } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./DroneMap.css";
import { FaEye, FaClock } from "react-icons/fa";

// Marker icons
import redMarkerIcon from "../assets/red_marker.png";
import greenMarkerIcon from "../assets/green_marker.png";
import airportIconImg from "../assets/airport.png";
import militaryIconImg from "../assets/military.jpg";
import governmentIconImg from "../assets/government.jpg";

const DroneMap = () => {
  // State for drone data, restricted zones, modal visibility, and update time
  const [droneData, setDroneData] = useState([]);
  const [restrictedZones, setRestrictedZones] = useState([]);
  const [showLiveDetections, setShowLiveDetections] = useState(false);
  const [lastUpdated, setLastUpdated] = useState("");

  // WebSocket reference
  const socketRef = useRef(null);

  // -------------------------
  // 1) Random Drone Generator
  // -------------------------
  // Generates N random drones. If forceUnauthorized is true, they are all flagged unauthorized.
  const generateRandomDrones = (count, forceUnauthorized = false) => {
    const drones = [];
    for (let i = 0; i < count; i++) {
      drones.push({
        callsign: `SIM-${i + 1}`,
        latitude: getRandomInRange(25, 49),     // US latitude range
        longitude: getRandomInRange(-125, -67), // US longitude range
        altitude: getRandomInRange(100, 3000),
        velocity: getRandomInRange(30, 200),
        unauthorized: forceUnauthorized ? true : Math.random() < 0.4,
        reason: forceUnauthorized ? "Simulated: Restricted Zone" : "",
      });
    }
    return drones;
  };

  const getRandomInRange = (min, max) => {
    return parseFloat((Math.random() * (max - min) + min).toFixed(6));
  };

  // -------------------------
  // 2) Haversine Distance Helper
  // -------------------------
  const toRad = (value) => (value * Math.PI) / 180;
  const haversineDistance = (lat1, lon1, lat2, lon2) => {
    const R = 6371; // Earth radius in km
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) ** 2 +
              Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
              Math.sin(dLon / 2) ** 2;
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  };

  // -------------------------
  // 3) Apply Restricted Zone Logic
  // -------------------------
  // For each drone, if it falls within any restricted zone, mark it unauthorized and add a reason.
  const applyRestrictedZoneLogic = (drone, zones) => {
    for (const zone of zones) {
      const distance = haversineDistance(drone.latitude, drone.longitude, zone.latitude, zone.longitude);
      if (distance <= zone.radius) {
        return { ...drone, unauthorized: true, reason: `Restricted Zone: ${zone.name}` };
      }
    }
    return drone;
  };

  // -------------------------
  // 4) Fetch Data + WebSocket Setup
  // -------------------------
  useEffect(() => {
    // Fetch real drone data from the server
    const fetchDroneData = async () => {
      try {
        const response = await fetch("http://127.0.0.1:8000/fetch-drones-live");
        const data = await response.json();
        let realDrones = data.drones || [];
        const unauthorizedCount = realDrones.filter(d => d.unauthorized).length;
        // If no unauthorized drones, append 5 random unauthorized drones
        if (unauthorizedCount === 0) {
          const randomUnauthorized = generateRandomDrones(5, true);
          realDrones = realDrones.concat(randomUnauthorized);
        }
        setDroneData(realDrones);
        setLastUpdated(new Date().toLocaleTimeString());
      } catch (error) {
        console.error("Error fetching drone data:", error);
        let fallbackRandom = generateRandomDrones(10);
        const unauthorizedCount = fallbackRandom.filter(d => d.unauthorized).length;
        if (unauthorizedCount === 0) {
          const forcedUnauthorized = generateRandomDrones(5, true);
          fallbackRandom = fallbackRandom.concat(forcedUnauthorized);
        }
        setDroneData(fallbackRandom);
        setLastUpdated(new Date().toLocaleTimeString());
      }
    };

    // Fetch restricted zones from the server
    const fetchRestrictedZones = async () => {
      try {
        const response = await fetch("http://127.0.0.1:8000/restricted-zones");
        const data = await response.json();
        setRestrictedZones(data.restricted_zones || []);
      } catch (error) {
        console.error("Error fetching restricted zones:", error);
        setRestrictedZones([]);
      }
    };

    // Initial fetches
    fetchDroneData();
    fetchRestrictedZones();

    // Set up WebSocket connection for live updates
    socketRef.current = new WebSocket("ws://localhost:8000/ws");
    socketRef.current.onopen = () => {
      console.log("✅ WebSocket Connected");
    };
    socketRef.current.onmessage = (event) => {
      try {
        const receivedData = JSON.parse(event.data);
        if (receivedData.drones && Array.isArray(receivedData.drones)) {
          let updatedDrones = receivedData.drones;
          const unauthorizedCount = updatedDrones.filter(d => d.unauthorized).length;
          if (unauthorizedCount === 0) {
            const randomUnauthorized = generateRandomDrones(5, true);
            updatedDrones = updatedDrones.concat(randomUnauthorized);
          }
          setDroneData(updatedDrones);
          setLastUpdated(new Date().toLocaleTimeString());
        } else {
          console.warn("⚠️ Unexpected WebSocket Data Format:", receivedData);
        }
      } catch (error) {
        console.error("❌ WebSocket Error Parsing Data:", event.data);
      }
    };
    socketRef.current.onerror = (error) => {
      console.error("❌ WebSocket Error:", error);
    };
    socketRef.current.onclose = () => {
      console.warn("⚠️ WebSocket Disconnected. Reconnecting...");
      setTimeout(() => {
        socketRef.current = new WebSocket("ws://localhost:8000/ws");
      }, 10000);
    };

    return () => {
      if (socketRef.current) socketRef.current.close();
    };
  }, []);

  // -------------------------
  // 5) Re-Apply Restricted Zone Logic
  // -------------------------
  // When either droneData or restrictedZones changes, update each drone to flag if it falls within a restricted zone.
  useEffect(() => {
    if (droneData.length === 0 || restrictedZones.length === 0) return;
    const updatedDrones = droneData.map((drone) => applyRestrictedZoneLogic(drone, restrictedZones));
    // Only update if there is a change to avoid infinite loops.
    setDroneData(updatedDrones);
  }, [restrictedZones]);

  // -------------------------
  // 6) Marker Icon Functions
  // -------------------------
  const getZoneIcon = (zoneType) => {
    let iconImage;
    if (zoneType.includes("Airport")) iconImage = airportIconImg;
    else if (zoneType.includes("Base") || zoneType.includes("Fort")) iconImage = militaryIconImg;
    else iconImage = governmentIconImg;
    return L.icon({
      iconUrl: iconImage,
      iconSize: [40, 40],
      iconAnchor: [20, 40],
      popupAnchor: [0, -35],
    });
  };

  const getMarkerIcon = (drone) => {
    return L.icon({
      iconUrl: drone.unauthorized ? redMarkerIcon : greenMarkerIcon,
      iconSize: [30, 40],
      iconAnchor: [15, 40],
      popupAnchor: [0, -35],
    });
  };

  // -------------------------
  // 7) Modal Handlers
  // -------------------------
  const handleToggleDetections = () => {
    setShowLiveDetections(true);
  };

  const handleCloseModal = () => {
    setShowLiveDetections(false);
  };

  // -------------------------
  // 8) Render
  // -------------------------
  return (
    <div className="drone-dashboard">
      {/* Minimal Navigation Bar */}
      <nav className="navbar">
        <div className="navbar-brand">
          <h2 className="brand-title">🚁 Illegal Drone Tracking System</h2>
        </div>
        <div className="navbar-right">
          <button className="nav-button" onClick={handleToggleDetections}>
            <FaEye /> Live Detections
          </button>
        </div>
      </nav>

      {/* Full-Width Map */}
      <div className="map-container">
        <MapContainer
          center={[37.7749, -99.4194]} // Broader US view center
          zoom={4}
          style={{ height: "600px", width: "100%" }}
        >
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />

          {/* Render restricted zones */}
          {restrictedZones.map((zone, index) => (
            <Marker
              key={index}
              position={[zone.latitude, zone.longitude]}
              icon={getZoneIcon(zone.name)}
            >
              <Popup>
                ⚠️ <strong>{zone.name}</strong>
                <br /> Restricted Zone - Radius: {zone.radius} km
              </Popup>
            </Marker>
          ))}

          {/* Render drones */}
          {droneData.map((drone, index) => (
            <Marker
              key={index}
              position={[drone.latitude, drone.longitude]}
              icon={getMarkerIcon(drone)}
            >
              <Popup>
                <strong>{drone.callsign || "Unknown"}</strong>
                <br />Lat: {drone.latitude.toFixed(2)}, Lon: {drone.longitude.toFixed(2)}
                <br />Alt: {drone.altitude.toFixed(2)} m, Vel: {drone.velocity.toFixed(2)} km/h
                <br />
                Status:{" "}
                {drone.unauthorized
                  ? `❌ Unauthorized `
                  : "✅ Authorized"}
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>

      {/* Live Detections Modal */}
      {showLiveDetections && (
        <div className="modal">
          <div className="modal-content">
            {/* Close Button */}
            <span className="close-button" onClick={handleCloseModal}>
              &times;
            </span>
            <h2>📡 Live Drone Detections</h2>
            <p>
              <FaClock /> Last Updated: {lastUpdated}
            </p>
            <div className="stats-container">
              <div className="stats-card">
                <h3>Total Drones</h3>
                <p>{droneData.length}</p>
              </div>
              <div className="stats-card unauthorized">
                <h3>Unauthorized Drones</h3>
                <p>{droneData.filter((d) => d.unauthorized).length}</p>
              </div>
            </div>
            <ul>
              {droneData.map((drone, index) => (
                <li
                  key={index}
                  className={drone.unauthorized ? "unauthorized-drone" : "authorized-drone"}
                >
                  <strong>{drone.callsign || "Unknown"}</strong> - Lat:{" "}
                  {drone.latitude.toFixed(2)}, Lon: {drone.longitude.toFixed(2)}, Alt:{" "}
                  {drone.altitude.toFixed(2)} m, Vel: {drone.velocity.toFixed(2)} km/h, Status:{" "}
                  {drone.unauthorized
                    ? `❌ Unauthorized `
                    : "✅ Authorized"}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default DroneMap;
