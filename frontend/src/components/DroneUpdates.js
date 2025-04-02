import React from "react";

const DroneUpdates = ({ droneData, lastUpdated }) => {
  return (
    <div className="drone-updates">
      <h2>📡 Live Drone Updates</h2>
      <p>🕒 Last Updated: {lastUpdated || "Waiting for updates..."}</p>
      {droneData.length > 0 ? (
        <ul>
          {droneData.map((drone, index) => (
            <li
              key={index}
              className={drone.unauthorized ? "unauthorized-drone" : "authorized-drone"}
            >
              🚁 <strong>{drone.callsign || "Unknown"}</strong> - 🌍 Lat: {drone.latitude}, 
              Lon: {drone.longitude} - 📏 Alt: {drone.altitude} m - 💨 Vel: {drone.velocity} km/h - 
              {drone.unauthorized ? " ❌ Unauthorized" : " ✅ Authorized"}
            </li>
          ))}
        </ul>
      ) : (
        <p>📡 No live drone updates available.</p>
      )}
    </div>
  );
};

export default DroneUpdates;
