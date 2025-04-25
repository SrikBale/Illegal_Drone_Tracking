import React, { useState, useEffect } from 'react';
import './StatsPanel.css'; // Make sure this CSS file exists and is correctly styled

const StatsPanel = ({ droneData }) => {
  // State to hold the calculated statistics
  const [stats, setStats] = useState({
    totalDrones: 0,
    unauthorizedDrones: 0,
    avgSpeed: 0,
    avgAltitude: 0,
    restrictedZoneViolations: 0, // Note: Assuming `inRestrictedZone` property exists in droneData
    lastUpdated: new Date().toLocaleTimeString(),
  });

  // Effect to recalculate stats when droneData changes
  useEffect(() => {
    // Default state for when there's no data
    if (!droneData || droneData.length === 0) {
      setStats({
        totalDrones: 0,
        unauthorizedDrones: 0,
        avgSpeed: 0,
        avgAltitude: 0,
        restrictedZoneViolations: 0,
        lastUpdated: new Date().toLocaleTimeString(),
      });
      return; // Exit early if no data
    }

    // Calculate stats from the provided droneData
    const totalDrones = droneData.length;
    const unauthorizedDrones = droneData.filter(drone => drone.unauthorized).length;

    // Calculate averages only if there are drones
    const avgSpeed = totalDrones > 0
      ? (droneData.reduce((sum, drone) => sum + (drone.velocity || 0), 0) / totalDrones).toFixed(1) // Use toFixed(1) for one decimal place
      : 0;
    const avgAltitude = totalDrones > 0
      ? (droneData.reduce((sum, drone) => sum + (drone.altitude || 0), 0) / totalDrones).toFixed(0) // Use toFixed(0) for whole meters
      : 0;

    // Calculate restricted zone violations - *Important: Check your drone data structure*
    // The backend response currently has `zone` which is the zone name if unauthorized,
    // but not a specific `inRestrictedZone` boolean. We'll count drones marked as unauthorized
    // as a proxy, or specifically those with a zone name other than 'None'.
    // Let's count based on the `unauthorized` flag which is set by the backend's zone check.
    const restrictedZoneViolations = unauthorizedDrones; // Simpler: count unauthorized as violations for this panel

    // Update the state with the new calculations
    setStats({
      totalDrones,
      unauthorizedDrones,
      avgSpeed,
      avgAltitude,
      restrictedZoneViolations, // Using the count of unauthorized drones here
      lastUpdated: new Date().toLocaleTimeString(),
    });

  }, [droneData]); // Dependency array: re-run effect when droneData changes

  // Function to determine the threat level based on the count of unauthorized drones
  const getThreatLevel = (unauthorizedCount) => {
    if (unauthorizedCount >= 5) return { level: 'high', text: 'Threat Level: High' }; // Adjusted threshold
    if (unauthorizedCount > 0) return { level: 'medium', text: 'Threat Level: Medium' };
    return { level: 'low', text: 'Threat Level: Low' };
  };

  // Get the current threat level object
  const threat = getThreatLevel(stats.unauthorizedDrones);

  // Render the component
  return (
    <div className="stats-panel">
      {/* Title */}
      <h2 className="neon-title">📊 Real-Time Statistics</h2>

      {/* Last updated timestamp */}
      <p>⏳ Last Updated: {stats.lastUpdated}</p>

      {/* List of statistics */}
      <ul>
        <li>
          🚁 <strong>Total Drones:</strong> <span className="value">{stats.totalDrones}</span>
        </li>
        {/* Apply specific class for unauthorized stats styling */}
        <li className="unauthorized-stat">
          🚨 <strong>Unauthorized:</strong> <span className="value">{stats.unauthorizedDrones}</span>
        </li>
        <li>
          📈 <strong>Avg Speed:</strong> <span className="value">{stats.avgSpeed} km/h</span>
        </li>
        <li>
          ⛰️ <strong>Avg Altitude:</strong> <span className="value">{stats.avgAltitude} m</span>
        </li>
        {/* Displaying the count of unauthorized drones as 'violations' */}
        <li>
          🏛️ <strong>Violations:</strong> <span className="value">{stats.restrictedZoneViolations}</span>
        </li>
      </ul>

      {/* Display the Threat Level Badge */}
      <div className={`threat-level threat-${threat.level}`}>
        {threat.text}
      </div>
    </div>
  );
};

export default StatsPanel;