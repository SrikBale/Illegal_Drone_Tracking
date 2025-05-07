// src/components/DroneMap.js

import React, { useState, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, CircleMarker } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./DroneMap.css"; // Ensure this CSS file has necessary styles
import { FaEye, FaClock, FaTimes } from "react-icons/fa";

// Import marker assets (verify paths based on your project structure)
// Assumes DroneMap.js is in src/components/ and assets are in src/assets/
import redMarkerIconUrl from "../assets/red_marker.png";
import greenMarkerIconUrl from "../assets/green_marker.png";

// --- Zone Color Definitions ---
const zoneColors = {
    airport: "#3388ff",    // Blue
    government: "#ff8c00", // Orange
    military: "#555555",    // Gray
    other: "#800080"       // Purple
};

// --- Helper Function: Get Zone Type ---
const getZoneType = (zoneName = "") => {
    const lowerName = zoneName.toLowerCase();
    if (lowerName.includes("airport")) return "airport";
    if (lowerName.includes("base") || lowerName.includes("fort") || lowerName.includes("military") || lowerName.includes("complex")) return "military";
    if (lowerName.includes("white house") || lowerName.includes("pentagon") || lowerName.includes("government") || lowerName.includes("national lab")) return "government";
    return "other"; // Default type
};

// --- Helper Function: Get Custom Marker Icon ---
// Uses L.divIcon to allow for CSS pulsing effects on the wrapper div
const getMarkerIcon = (drone) => {
    // Determine icon URL and CSS classes based on authorization status
    const iconUrl = drone.unauthorized ? redMarkerIconUrl : greenMarkerIconUrl;
    const baseIconClass = 'custom-leaflet-div-icon'; // Base class for common styling
    const statusIconClass = drone.unauthorized ? 'unauthorized-drone-marker' : 'authorized-drone-marker'; // Status-specific class
    const pulseClass = drone.unauthorized ? 'pulsing-marker-effect' : ''; // Add pulsing class only for unauthorized

    return L.divIcon({
        // The HTML includes a wrapper div for pulsing and an img tag for the actual icon
        html: `<div class="marker-wrapper ${pulseClass}">
                 <img src="${iconUrl}" alt="${drone.unauthorized ? 'unauthorized' : 'authorized'} drone marker" class="marker-icon-img" />
               </div>`,
        className: `${baseIconClass} ${statusIconClass}`, // Combine base and status classes for the main divIcon element
        iconSize: [32, 44],   // Overall size of the icon div (adjust as needed)
        iconAnchor: [16, 44],  // Point of the icon which corresponds to marker's location (bottom center)
        popupAnchor: [0, -40] // Point from which the popup should open relative to the iconAnchor
    });
};


// --- DroneMap Component ---
const DroneMap = ({ droneData, restrictedZones, lastUpdated }) => {
    // State for controlling the visibility of the "Live Detections" modal
    const [showLiveDetections, setShowLiveDetections] = useState(false);

    // --- Event Handlers ---
    const handleToggleDetections = () => setShowLiveDetections(true);
    const handleCloseModal = () => setShowLiveDetections(false);

    // --- Memoized Calculation for Modal Statistics ---
    // Calculates stats based *only* on the `droneData` currently passed to this component
    // This usually means the filtered data shown on the map.
    const modalStats = useMemo(() => {
        const totalDisplayed = droneData?.length || 0;
        const unauthorizedDisplayed = droneData?.filter(d => d && d.unauthorized).length || 0;
        // To show stats for *all* drones (not just filtered), the parent component (`App.js`)
        // would need to pass the complete, unfiltered drone list separately.
        return { totalDisplayed, unauthorizedDisplayed };
    }, [droneData]); // Recalculate only when droneData changes

    // --- Debugging Log ---
    // Add this log to check the data received by the component
    // console.log("DroneMap received droneData:", JSON.stringify(droneData, null, 2));

    // --- Render Logic ---
    return (
        <div className="drone-dashboard map-section-container">

            {/* Navbar specific to the map section */}
            <nav className="navbar map-navbar">
                <div className="navbar-brand">
                    <h2 className="neon-title map-section-title">🚁 Illegal Drone Tracking System</h2>
                </div>
                <div className="navbar-right">
                    {/* Button to open the Live Detections modal */}
                    <button className="action-button" onClick={handleToggleDetections}>
                        <FaEye /> Live Detections ({modalStats.totalDisplayed})
                    </button>
                </div>
            </nav>

            {/* Horizontal Legend for Zone Types */}
            <div className="legend-box-horizontal">
                 <ul>
                    {/* Dynamically generate legend items from zoneColors */}
                    {Object.entries(zoneColors).map(([type, color]) => (
                         <li key={type}>
                             <span className={`legend-indicator ${type}`} style={{ backgroundColor: color }}></span>
                             {/* Capitalize the zone type for display */}
                             {type.charAt(0).toUpperCase() + type.slice(1)} Area
                         </li>
                    ))}
                 </ul>
            </div>

            {/* Leaflet Map Container */}
            <div className="map-container">
                <MapContainer
                    center={[39.8283, -98.5795]} // Initial center (Continental US)
                    zoom={4}                     // Initial zoom level
                    style={{ height: "100%", width: "100%" }} // Ensure map fills container
                    scrollWheelZoom={true}       // Allow zooming with scroll wheel
                >
                    {/* Base Map Tile Layer */}
                    <TileLayer
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                        maxZoom={18} // Maximum zoom level for the tile layer
                    />

                    {/* Render Restricted Zone Markers */}
                    {restrictedZones && restrictedZones.map((zone, index) => {
                        // Basic validation for zone data
                        if (!zone || typeof zone.latitude !== 'number' || typeof zone.longitude !== 'number' || typeof zone.radius !== 'number') {
                            console.warn("Skipping invalid restricted zone object:", zone);
                            return null; // Skip rendering this zone
                        }
                        const zoneType = getZoneType(zone.name);
                        const zoneColor = zoneColors[zoneType];
                        // Note: Leaflet's Circle uses radius in meters, CircleMarker uses pixels.
                        // We use CircleMarker for consistent size regardless of zoom.
                        // const radiusInMeters = zone.radius * 1000; // Needed for L.Circle

                        return (
                            // Using CircleMarker for fixed pixel radius (easier visibility at different zooms)
                            <CircleMarker
                                key={`zone-${index}-${zone.name || index}`} // Unique key for each zone
                                center={[zone.latitude, zone.longitude]}
                                radius={8} // Fixed radius in pixels (adjust as needed)
                                pathOptions={{
                                    color: zoneColor,       // Outline color
                                    fillColor: zoneColor,   // Fill color
                                    fillOpacity: 0.3,       // Fill transparency
                                    weight: 1               // Outline thickness
                                }}
                            >
                                {/* Popup displayed when clicking the zone marker */}
                                <Popup>
                                    ⚠️ <strong>{zone.name || "Unnamed Zone"}</strong>
                                    <br /> Restricted Zone ({zoneType})
                                    <br /> Radius: {zone.radius.toFixed(1)} km
                                </Popup>
                            </CircleMarker>
                        );
                    })}

                    {/* Render Drone Markers */}
                    {/* Ensure droneData is an array before mapping */}
                    {Array.isArray(droneData) && droneData.map((drone) => {
                        // Basic validation for drone data
                        if (!drone || typeof drone.latitude !== 'number' || typeof drone.longitude !== 'number') {
                            console.warn("Skipping invalid drone object:", drone);
                            return null; // Skip rendering this drone marker
                        }

                        // ***** Add log here to debug individual drone status *****
                        // console.log('DroneMap rendering marker:', drone.callsign, 'Is Unauthorized:', drone.unauthorized);

                        return (
                            <Marker
                                // Use a stable and unique key. `renderKey` should be passed from App.js
                                // If renderKey isn't available, fallback to callsign, but ensure callsigns are unique
                                key={drone.renderKey || drone.callsign || `drone-${drone.latitude}-${drone.longitude}`}
                                position={[drone.latitude, drone.longitude]}
                                icon={getMarkerIcon(drone)} // Use the custom function to get the divIcon
                            >
                                {/* Popup displayed when clicking the drone marker */}
                                <Popup>
                                    {/* Use nullish coalescing (??) for safer default values */}
                                    <strong>{drone.callsign ?? "Unknown Callsign"}</strong>
                                    <br />Lat: {drone.latitude?.toFixed(4) ?? 'N/A'}, Lon: {drone.longitude?.toFixed(4) ?? 'N/A'}
                                    <br />Alt: {drone.altitude != null ? `${drone.altitude.toFixed(0)} m` : 'N/A'}
                                    <br />Vel: {drone.velocity != null ? `${drone.velocity.toFixed(1)} km/h` : 'N/A'}
                                    <br />Status: {drone.unauthorized
                                        ? <>❌ Unauthorized {drone.zone ? `(${drone.zone})` : ''}</>
                                        : <>✅ Authorized</>
                                    }
                                </Popup>
                            </Marker>
                        );
                    })}
                </MapContainer>
            </div> {/* End map-container */}

            {/* Live Detections Modal */}
            {/* This modal shows details about the drones currently displayed on the map */}
            {showLiveDetections && (
                // Overlay div to close modal on background click
                <div className="modal" onClick={handleCloseModal}>
                    {/* Modal content area (prevents click propagation) */}
                    <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                         {/* Close button */}
                         <button className="close-button" onClick={handleCloseModal}>
                           <FaTimes />
                         </button>
                         <h2 className="neon-title modal-title">📡 Drones Currently Displayed</h2>
                         <p className="modal-last-updated"><FaClock /> Data timestamp: {lastUpdated || "N/A"}</p>

                         {/* Statistics based on displayed drones */}
                         <div className="stats-container modal-stats">
                           <div className="stats-card">
                             <h3>Displayed</h3>
                             <p>{modalStats.totalDisplayed}</p>
                           </div>
                           <div className="stats-card unauthorized">
                             <h3>Unauthorized (Displayed)</h3>
                             <p>{modalStats.unauthorizedDisplayed}</p>
                           </div>
                         </div>

                         {/* List of displayed drones */}
                         {/* Add a scrollable container */}
                         <div className="modal-drone-list-container styled-scrollbar">
                             <ul className="modal-drone-list">
                                 {/* Check if droneData exists and has items */}
                                 {Array.isArray(droneData) && droneData.length > 0 ? (
                                     droneData.map((drone) => (
                                         // Use a stable key for list items
                                         <li key={drone.renderKey || drone.callsign || `modal-${drone.latitude}-${drone.longitude}`}
                                             className={drone.unauthorized ? "unauthorized-drone" : "authorized-drone"}>
                                             <strong>{drone.callsign ?? "Unknown"}</strong>
                                             <span> - Alt: {drone.altitude != null ? `${drone.altitude.toFixed(0)} m` : 'N/A'}</span>
                                             <span>, Vel: {drone.velocity != null ? `${drone.velocity.toFixed(1)} km/h` : 'N/A'}</span>
                                             <span> - {drone.unauthorized ? `❌ Unauth ${drone.zone ? `(${drone.zone})` : ''}` : "✅ Auth"}</span>
                                         </li>
                                     ))
                                 ) : (
                                     // Message shown if no drones are displayed
                                     <li className="no-drones-message">No drones currently displayed on the map.</li>
                                 )}
                             </ul>
                         </div> {/* End scrollable container */}
                    </div> {/* End modal-content */}
                </div> // End modal
            )}

        </div> // End map-section-container (root element)
    );
};

export default DroneMap;