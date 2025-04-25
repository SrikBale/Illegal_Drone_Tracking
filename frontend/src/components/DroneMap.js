// src/components/DroneMap.js

import React, { useState, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, CircleMarker } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./DroneMap.css"; // Ensure this CSS file has all the necessary styles applied
import { FaEye, FaClock, FaTimes } from "react-icons/fa";

// Import marker assets (verify paths are correct relative to this file)
import redMarkerIconUrl from "../assets/red_marker.png";
import greenMarkerIconUrl from "../assets/green_marker.png";

// --- DroneMap Component ---
// Accepts the filtered drone data (subset for display) as droneData prop
const DroneMap = ({ droneData, restrictedZones, lastUpdated }) => {
  const [showLiveDetections, setShowLiveDetections] = useState(false);

  // --- Event Handlers ---
  const handleToggleDetections = () => setShowLiveDetections(true);
  const handleCloseModal = () => setShowLiveDetections(false);

  // --- Helper Functions ---
  const zoneColors = {
    airport: "#3388ff",    // Blue
    government: "#ff8c00", // Orange
    military: "#555555",    // Gray
    other: "#800080"       // Purple
  };

  const getZoneType = (zoneName = "") => {
    const lowerName = zoneName.toLowerCase();
    if (lowerName.includes("airport")) return "airport";
    if (lowerName.includes("base") || lowerName.includes("fort") || lowerName.includes("military") || lowerName.includes("complex")) return "military";
    if (lowerName.includes("white house") || lowerName.includes("pentagon") || lowerName.includes("government") || lowerName.includes("national lab")) return "government";
    return "other"; // Includes Area 51, Groom Lake etc. as 'other'
  };

  // --- UPDATED: Define custom Leaflet icons using L.divIcon for easier CSS styling ---
  const getMarkerIcon = (drone) => {
    const iconUrl = drone.unauthorized ? redMarkerIconUrl : greenMarkerIconUrl;
    const baseIconClass = 'custom-leaflet-div-icon';
    const statusIconClass = drone.unauthorized ? 'unauthorized-drone-marker' : 'authorized-drone-marker';
    const pulseClass = drone.unauthorized ? 'pulsing-marker-effect' : ''; // CSS class for pulsing

    return L.divIcon({
      // Embed an img inside a div. Style the div with pulse, reference img for content.
      html: `<div class="marker-wrapper ${pulseClass}">
               <img src="${iconUrl}" alt="${drone.unauthorized ? 'unauthorized' : 'authorized'} drone marker" class="marker-icon-img" />
             </div>`,
      className: `${baseIconClass} ${statusIconClass}`, // Apply multiple classes
      iconSize: [32, 44],   // Size of the overall icon div
      iconAnchor: [16, 44],  // Point of the icon which corresponds to marker's location (bottom center)
      popupAnchor: [0, -40] // Point from which the popup should open relative to the iconAnchor
    });
  };


  // --- Memoized Calculations for Modal Stats (Based on the FILTERED droneData) ---
  const modalStats = useMemo(() => {
     // droneData here IS the filtered list passed from App.js
     const totalDisplayed = droneData?.length || 0;
     const unauthorizedDisplayed = droneData?.filter(d => d.unauthorized).length || 0;
     // Note: These stats only reflect the drones currently shown on the map.
     // If you need stats for ALL drones, `allDroneData` needs to be passed separately.
     return { totalDisplayed, unauthorizedDisplayed };
  }, [droneData]);


  // --- Render Logic ---
  return (
    <div className="drone-dashboard map-section-container">

      {/* Navbar specific to the map section */}
      <nav className="navbar map-navbar">
        <div className="navbar-brand">
          <h2 className="neon-title map-section-title">🚁 Illegal Drone Tracking System</h2>
        </div>
        <div className="navbar-right">
          <button className="action-button" onClick={handleToggleDetections}>
            <FaEye /> Live Detections ({modalStats.totalDisplayed}) {/* Show count on button */}
          </button>
        </div>
      </nav>

      {/* Horizontal Legend Section */}
      <div className="legend-box-horizontal">
         <ul>
             {/* Map over zoneColors for dynamic legend */}
             {Object.entries(zoneColors).map(([type, color]) => (
                 <li key={type}>
                     <span className={`legend-indicator ${type}`} style={{ backgroundColor: color }}></span>
                     {/* Capitalize type for display */}
                     {type.charAt(0).toUpperCase() + type.slice(1)} Area
                 </li>
             ))}
         </ul>
      </div>


      {/* Map Container Section */}
      <div className="map-container">
        <MapContainer
            center={[39.8283, -98.5795]} // Centered on continental US
            zoom={4} // Adjust initial zoom as needed
            style={{ height: "100%", width: "100%" }}
            scrollWheelZoom={true}
          >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            maxZoom={18} // Slightly lower maxZoom can improve performance if needed
          />

          {/* Render Restricted Zone Circles */}
          {restrictedZones && restrictedZones.map((zone, index) => {
              if (!zone || typeof zone.latitude !== 'number' || typeof zone.longitude !== 'number' || typeof zone.radius !== 'number') {
                  console.warn("Skipping invalid restricted zone object:", zone);
                  return null;
              }
              const zoneType = getZoneType(zone.name);
              const zoneColor = zoneColors[zoneType];
              // Using actual radius in meters for Circle (Leaflet standard)
              const radiusInMeters = zone.radius * 1000;

              return (
                  // Using Circle for real-world radius, requires conversion to meters
                  <CircleMarker // CircleMarker keeps constant screen pixel size, better for many zones
                      key={`zone-${index}-${zone.name}`}
                      center={[zone.latitude, zone.longitude]}
                      radius={8} // Fixed pixel radius for CircleMarker, easier to see
                      pathOptions={{
                          color: zoneColor,
                          fillColor: zoneColor,
                          fillOpacity: 0.3, // Slightly less opaque
                          weight: 1
                      }}
                  >
                      <Popup>
                          ⚠️ <strong>{zone.name || "Unnamed Zone"}</strong>
                          <br /> Restricted Zone ({zoneType})
                          <br /> Radius: {zone.radius.toFixed(1)} km
                      </Popup>
                  </CircleMarker>
              );
          })}

          {/* Render Drone Markers (using the filtered droneData prop) */}
          {droneData && droneData.map((drone) => {
              if (!drone || typeof drone.latitude !== 'number' || typeof drone.longitude !== 'number') {
                  console.warn("Skipping invalid drone object:", drone);
                  return null;
              }
              return (
                  <Marker
                      // ****** CHANGE HERE: Use renderKey passed from App.js ******
                      key={drone.renderKey} // Use the unique key generated in App.js
                      position={[drone.latitude, drone.longitude]}
                      icon={getMarkerIcon(drone)} // Use the custom divIcon
                  >
                      <Popup>
                          {/* Use nullish coalescing for safer defaults */}
                          <strong>{drone.callsign ?? "Unknown Callsign"}</strong>
                          <br />Lat: {drone.latitude?.toFixed(4) ?? 'N/A'}, Lon: {drone.longitude?.toFixed(4) ?? 'N/A'}
                          <br />Alt: {drone.altitude?.toFixed(0) ?? 'N/A'} m, Vel: {drone.velocity?.toFixed(1) ?? 'N/A'} km/h
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


      {/* Live Detections Modal (Displays data based on the FILTERED drones shown on map) */}
      {showLiveDetections && (
        <div className="modal" onClick={handleCloseModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
             <button className="close-button" onClick={handleCloseModal}>
               <FaTimes />
             </button>
             <h2 className="neon-title modal-title">📡 Drones Currently Displayed</h2>
             <p className="modal-last-updated"><FaClock /> Data timestamp: {lastUpdated || "N/A"}</p>

             {/* Stats inside modal (Reflects displayed drones only) */}
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

             {/* Drone List (Reflects displayed drones only) */}
             <ul className="modal-drone-list styled-scrollbar"> {/* Added scrollbar class */}
               {droneData && droneData.length > 0 ? (
                   droneData.map((drone) => ( // No need for index if using renderKey
                     <li key={drone.renderKey} className={drone.unauthorized ? "unauthorized-drone" : "authorized-drone"}>
                       <strong>{drone.callsign ?? "Unknown"}</strong>
                       <span> - Alt: {drone.altitude?.toFixed(0) ?? 'N/A'}m</span>
                       <span>, Vel: {drone.velocity?.toFixed(1) ?? 'N/A'}km/h</span>
                       <span> - {drone.unauthorized ? `❌ Unauth ${drone.zone ? `(${drone.zone})` : ''}` : "✅ Auth"}</span>
                     </li>
                   ))
                 ) : (
                   <li className="no-drones-message">No drones currently displayed on the map.</li>
                 )
               }
             </ul>
          </div> {/* End modal-content */}
        </div> // End modal
      )}

    </div> // End map-section-container
  );
};

export default DroneMap;