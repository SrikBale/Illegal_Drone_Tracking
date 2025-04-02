import React, { useState, useEffect } from 'react';

const StatsPanel = ({ droneData }) => {
  const [stats, setStats] = useState({
    totalDrones: 0,
    unauthorizedDrones: 0,
    avgSpeed: 0,
    avgAltitude: 0,
    restrictedZoneViolations: 0,
    lastUpdated: new Date().toLocaleTimeString(),
  });

  useEffect(() => {
    if (!droneData || droneData.length === 0) {
      setStats(prevStats => ({
        ...prevStats,
        totalDrones: 0,
        unauthorizedDrones: 0,
        avgSpeed: 0,
        avgAltitude: 0,
        restrictedZoneViolations: 0,
        lastUpdated: new Date().toLocaleTimeString(),
      }));
      return;
    }

    const totalDrones = droneData.length;
    const unauthorizedDrones = droneData.filter(drone => drone.unauthorized).length;
    const avgSpeed = totalDrones > 0
      ? (droneData.reduce((sum, drone) => sum + drone.velocity, 0) / totalDrones).toFixed(2)
      : 0;
    const avgAltitude = totalDrones > 0
      ? (droneData.reduce((sum, drone) => sum + drone.altitude, 0) / totalDrones).toFixed(2)
      : 0;
    const restrictedZoneViolations = droneData.filter(drone => drone.inRestrictedZone).length;

    setStats({
      totalDrones,
      unauthorizedDrones,
      avgSpeed,
      avgAltitude,
      restrictedZoneViolations,
      lastUpdated: new Date().toLocaleTimeString(),
    });
  }, [droneData]);

  return (
    <div className="stats-panel">
      <h2>📊 Real-Time Drone Statistics</h2>
      <p>⏳ Last Updated: {stats.lastUpdated}</p>
      <ul>
        <li>🚁 <strong>Total Drones:</strong> {stats.totalDrones}</li>
        <li>🚨 <strong>Unauthorized Drones:</strong> {stats.unauthorizedDrones}</li>
        <li>📈 <strong>Avg Speed:</strong> {stats.avgSpeed} km/h</li>
        <li>⛰️ <strong>Avg Altitude:</strong> {stats.avgAltitude} m</li>
        <li>🏛️ <strong>Restricted Zone Violations:</strong> {stats.restrictedZoneViolations}</li>
      </ul>
    </div>
  );
};

export default StatsPanel;
