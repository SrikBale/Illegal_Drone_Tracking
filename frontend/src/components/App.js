import React, { useState, useEffect, useRef } from "react";
import DroneMap from "./DroneMap";
import DroneUpdates from "./DroneUpdates";
import DroneValidation from "./DroneValidation";
//import "./App.css"; // Optional: your global styles

const App = () => {
  // Centralized state for drone data, restricted zones, and last update time
  const [droneData, setDroneData] = useState([]);
  const [restrictedZones, setRestrictedZones] = useState([]);
  const [lastUpdated, setLastUpdated] = useState("");
  const socketRef = useRef(null);

  // Helper to generate random drones; if forceUnauthorized is true, all drones will be flagged as unauthorized
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

  // Helper to generate a random number between min and max
  const getRandomInRange = (min, max) => {
    return parseFloat((Math.random() * (max - min) + min).toFixed(6));
  };

  useEffect(() => {
    // Fetch real drone data from the server
    const fetchDroneData = async () => {
      try {
        const response = await fetch("http://127.0.0.1:8000/fetch-drones-live");
        const data = await response.json();
        let realDrones = data.drones || [];
        // Check how many drones are flagged unauthorized
        const unauthorizedCount = realDrones.filter((d) => d.unauthorized).length;
        // If none are unauthorized, generate 5 random unauthorized drone
        if (unauthorizedCount === 0) {
          const randomUnauthorized = generateRandomDrones(5, true);
          realDrones = realDrones.concat(randomUnauthorized);
        }
        setDroneData(realDrones);
        setLastUpdated(new Date().toLocaleTimeString());
      } catch (error) {
        console.error("Error fetching drone data:", error);
        // Fallback: generate 10 random drones and add 5 forced unauthorized if needed
        let fallback = generateRandomDrones(10);
        const unauthorizedCount = fallback.filter((d) => d.unauthorized).length;
        if (unauthorizedCount === 0) {
          const randomUnauthorized = generateRandomDrones(5, true);
          fallback = fallback.concat(randomUnauthorized);
        }
        setDroneData(fallback);
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

    // Initial data fetches
    fetchDroneData();
    fetchRestrictedZones();

    // Set up WebSocket connection for live updates
    socketRef.current = new WebSocket("ws://127.0.0.1:8000/ws");
    socketRef.current.onopen = () => {
      console.log("✅ WebSocket Connected");
    };
    socketRef.current.onmessage = (event) => {
      try {
        const receivedData = JSON.parse(event.data);
        if (receivedData.drones && Array.isArray(receivedData.drones)) {
          let updatedDrones = receivedData.drones;
          const unauthorizedCount = updatedDrones.filter((d) => d.unauthorized).length;
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
        socketRef.current = new WebSocket("ws://127.0.0.1:8000/ws");
      }, 10000);
    };

    // Cleanup on unmount
    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, []);

  return (
    <div className="container">
      <h1>Airspace Security Monitor</h1>
      {/* Pass unified data to child components */}
      <DroneMap
        droneData={droneData}
        restrictedZones={restrictedZones}
        lastUpdated={lastUpdated}
      />
      <DroneUpdates droneData={droneData} lastUpdated={lastUpdated} />
      <DroneValidation droneData={droneData} />
    </div>
  );
};

export default App;
