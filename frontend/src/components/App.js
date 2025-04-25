import React, { useState, useEffect, useRef } from "react";
import DroneMap from "./DroneMap";
import StatsPanel from "./StatsPanel";         // Make sure StatsPanel is imported
import DroneValidation from "./DroneValidation"; // Make sure DroneValidation is imported
import { motion } from "framer-motion";
import { FaPlay } from 'react-icons/fa';      // Import an icon for the button

// Import CSS files
import './App.css'; // Main App styles (Hero, Layout, Buttons)
// Component-specific CSS will be imported within those components

const App = () => {
  const [droneData, setDroneData] = useState([]);
  const [restrictedZones, setRestrictedZones] = useState([]);
  const [lastUpdated, setLastUpdated] = useState("");
  const socketRef = useRef(null);

  // --- Existing Hooks and Functions ---
  const scrollToMap = () => {
    const mapSection = document.getElementById("dashboard-start"); // Target the dashboard container
    if (mapSection) {
      mapSection.scrollIntoView({ behavior: "smooth", block: "start" }); // Scroll to top of dashboard
    }
  };

  const generateRandomDrones = (count, forceUnauthorized = false) => {
    const drones = [];
    for (let i = 0; i < count; i++) {
      // Use a wider range for more visual spread initially if needed
      const lat = getRandomInRange(25, 49);
      const lon = getRandomInRange(-125, -67);
       // Determine if unauthorized based on actual zones or random chance/forcing
      const { isUnauthorized, zoneName } = checkRestrictedZone(lat, lon, restrictedZones);
      const shouldBeUnauthorized = forceUnauthorized || isUnauthorized || Math.random() < 0.2; // Example logic

      drones.push({
        callsign: `SIM-${Date.now().toString().slice(-4)}-${i + 1}`, // More unique callsign
        latitude: lat,
        longitude: lon,
        altitude: getRandomInRange(100, 3000),
        velocity: getRandomInRange(30, 200),
        unauthorized: shouldBeUnauthorized,
        // Add zone info if applicable
        zone: shouldBeUnauthorized ? (zoneName || (forceUnauthorized ? "Simulated: Forced" : "Simulated: Random")) : null,
      });
    }
    return drones;
  };

  const getRandomInRange = (min, max) => {
    return parseFloat((Math.random() * (max - min) + min).toFixed(6));
  };

   // Helper to check restricted zones (can be moved to a utils file)
  const checkRestrictedZone = (lat, lon, zones) => {
      // Haversine formula (ensure it's defined or imported)
      const haversine = (lat1, lon1, lat2, lon2) => {
          const R = 6371; // Radius of Earth in km
          const toRad = (value) => (value * Math.PI) / 180;
          const dLat = toRad(lat2 - lat1);
          const dLon = toRad(lon2 - lon1);
          const a = Math.sin(dLat / 2) ** 2 +
                    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
                    Math.sin(dLon / 2) ** 2;
          const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
          return R * c;
      };

      for (const zone of zones) {
          if (zone && typeof zone.latitude === 'number' && typeof zone.longitude === 'number' && typeof zone.radius === 'number') {
             const distance = haversine(lat, lon, zone.latitude, zone.longitude);
             if (distance <= zone.radius) {
                return { isUnauthorized: true, zoneName: zone.name };
             }
          } else {
              console.warn("Skipping invalid zone object:", zone);
          }
      }
      return { isUnauthorized: false, zoneName: null };
  };


  // Fetch initial data and set up WebSocket
  useEffect(() => {
    const fetchRestrictedZones = async () => {
      try {
        const response = await fetch("http://127.0.0.1:8000/restricted-zones");
        const data = await response.json();
        // Basic validation of fetched zones
        const validZones = Array.isArray(data?.restricted_zones)
             ? data.restricted_zones.filter(z => z && typeof z.latitude === 'number' && typeof z.longitude === 'number')
             : [];
        setRestrictedZones(validZones);
        console.log("Fetched restricted zones:", validZones);
        // Now fetch drone data after zones are loaded
        fetchDroneData(validZones);
      } catch (error) {
        console.error("Error fetching restricted zones:", error);
        setRestrictedZones([]); // Set empty array on error
        fetchDroneData([]); // Fetch drones even if zones fail
      }
    };

    // Fetch initial drone data (pass zones for immediate check)
    const fetchDroneData = async (currentZones) => {
      try {
        const response = await fetch("http://127.0.0.1:8000/fetch-drones-live");
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        let initialDrones = data?.drones && Array.isArray(data.drones) ? data.drones : [];

        // Ensure drone data has necessary fields & check against zones
        initialDrones = initialDrones.map(d => {
            const { isUnauthorized, zoneName } = checkRestrictedZone(d.latitude, d.longitude, currentZones);
            return {
                ...d,
                callsign: d.callsign || `DRN-${Date.now().toString().slice(-5)}`,
                latitude: d.latitude ?? 0, // Provide defaults
                longitude: d.longitude ?? 0,
                altitude: d.altitude ?? 0,
                velocity: d.velocity ?? 0,
                unauthorized: d.unauthorized || isUnauthorized, // Keep backend unauthorized or set based on zone check
                zone: d.unauthorized ? (d.zone || zoneName || "Unauthorized") : (isUnauthorized ? zoneName : null)
            };
        });


        // Optional: Add simulated drones if needed (e.g., for guaranteed unauthorized)
        let unauthorizedCount = initialDrones.filter(d => d.unauthorized).length;
        if (unauthorizedCount === 0 && initialDrones.length > 0) { // Only add if real drones exist but none are unauthorized
            console.log("Injecting simulated unauthorized drones...");
            const simulatedUnauthorized = generateRandomDrones(3, true); // Add 3 forced unauthorized
             // Filter out potential duplicates if needed (e.g., based on callsign)
            initialDrones = [...initialDrones, ...simulatedUnauthorized];
        } else if (initialDrones.length === 0) {
             console.log("No real-time drones fetched, generating fallback simulation...");
             initialDrones = generateRandomDrones(10, false); // Generate 10 mixed drones
             const fallbackUnauthorized = generateRandomDrones(2, true); // Ensure at least 2 unauthorized
             initialDrones = [...initialDrones, ...fallbackUnauthorized];
        }


        setDroneData(initialDrones);
        setLastUpdated(new Date().toLocaleTimeString());
        console.log("Initial drone data processed:", initialDrones.length, "drones");

      } catch (error) {
        console.error("Error fetching initial drone data:", error);
        // Generate fallback data on error
        console.log("Generating fallback drone data due to fetch error...");
        let fallbackDrones = generateRandomDrones(10, false);
        const fallbackUnauthorized = generateRandomDrones(3, true); // Add 3 unauthorized
        setDroneData([...fallbackDrones, ...fallbackUnauthorized]);
        setLastUpdated(new Date().toLocaleTimeString());
      }
    };

    fetchRestrictedZones(); // Start the process

    // --- WebSocket Setup ---
    const connectWebSocket = () => {
        console.log("Attempting WebSocket connection...");
        // Ensure previous socket is closed if reconnecting
        if (socketRef.current && socketRef.current.readyState !== WebSocket.CLOSED) {
             console.log("Closing existing WebSocket connection before reconnecting.");
             socketRef.current.close();
        }

        socketRef.current = new WebSocket("ws://127.0.0.1:8000/ws");

        socketRef.current.onopen = () => {
            console.log("✅ WebSocket Connected");
        };

        socketRef.current.onmessage = (event) => {
            try {
                const receivedData = JSON.parse(event.data);
                if (receivedData.drones && Array.isArray(receivedData.drones)) {
                    console.log(`Received ${receivedData.drones.length} drones via WebSocket.`);
                    let updatedDrones = receivedData.drones.map(d => {
                         const { isUnauthorized, zoneName } = checkRestrictedZone(d.latitude, d.longitude, restrictedZones); // Check zones again
                         return {
                             ...d,
                             callsign: d.callsign || `DRN-${Date.now().toString().slice(-5)}`,
                             latitude: d.latitude ?? 0,
                             longitude: d.longitude ?? 0,
                             altitude: d.altitude ?? 0,
                             velocity: d.velocity ?? 0,
                             unauthorized: d.unauthorized || isUnauthorized,
                             zone: d.unauthorized ? (d.zone || zoneName || "Unauthorized") : (isUnauthorized ? zoneName : null)
                         };
                     });

                    // Optional: Re-inject simulated if needed
                    let wsUnauthorizedCount = updatedDrones.filter(d => d.unauthorized).length;
                    // Example: Always ensure at least 1 unauthorized for demo purposes via WS
                    if (wsUnauthorizedCount === 0 && updatedDrones.length > 0) {
                         console.log("Injecting simulated unauthorized drone via WebSocket update...");
                         updatedDrones = [...updatedDrones, ...generateRandomDrones(1, true)];
                    }


                    setDroneData(updatedDrones);
                    setLastUpdated(new Date().toLocaleTimeString());
                } else {
                    console.warn("⚠️ Unexpected WebSocket Data Format:", receivedData);
                }
            } catch (error) {
                console.error("❌ WebSocket Error Parsing Data:", error, "Data:", event.data);
            }
        };

        socketRef.current.onerror = (error) => {
            console.error("❌ WebSocket Error:", error);
            // Attempt to reconnect on error after a delay
             setTimeout(connectWebSocket, 10000); // Try reconnecting every 10 seconds
        };

        socketRef.current.onclose = (event) => {
            console.warn(`⚠️ WebSocket Disconnected. Code: ${event.code}, Reason: ${event.reason}. Reconnecting...`);
            // Don't automatically reconnect if the closure was intentional (e.g., code 1000 or 1005)
             if (event.code !== 1000 && event.code !== 1005) {
                setTimeout(connectWebSocket, 5000); // Shorter delay for unexpected closures
             }
        };
    };

    connectWebSocket(); // Initial connection attempt

    // Cleanup function
    return () => {
        console.log("Closing WebSocket connection on component unmount.");
        if (socketRef.current) {
            socketRef.current.close();
        }
    };
  }, []); // Run only on mount

  // --- Framer Motion Animation Variants ---
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.25, // Stagger animation of children
        delayChildren: 0.3,    // Wait slightly before starting children animations
      }
    }
  };

  const itemVariants = {
    hidden: { y: 40, opacity: 0 }, // Start slightly lower and faded out
    visible: {
      y: 0,
      opacity: 1,
      transition: { type: 'spring', stiffness: 80, damping: 15, duration: 0.8 } // Spring animation
    }
  };

  // --- Render JSX ---
  return (
    <div className="app-root-container"> {/* Optional: Overall root container */}
      {/* === Hero Section === */}
      <section className="hero-section">
         <div className="hero-content">
            {/* Using motion for entry animation */}
            <motion.h1
              className="hero-title" // Use class from App.css
              initial={{ opacity: 0, y: -50 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
            >
              🛰️ Real-Time Airspace Surveillance & Drone Monitoring
            </motion.h1>

            <motion.p
              className="hero-subtitle" // Use class from App.css
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 1.0, delay: 0.4, ease: "easeOut" }}
            >
              Monitor unauthorized aerial activity, enhance airspace protection, and ensure real-time drone tracking with advanced detection technologies.
            </motion.p>

            <motion.button
              onClick={scrollToMap}
              className="hero-button" // Use class from App.css
              initial={{ opacity: 0, scale: 0.7 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.6, delay: 0.7, type: 'spring', stiffness: 120 }}
              whileHover={{ scale: 1.05, transition: { duration: 0.2 } }} // Hover effect
              whileTap={{ scale: 0.95 }} // Tap effect
            >
               <FaPlay /> Launch Mission
            </motion.button>
         </div>
      </section>

      {/* === Dashboard Section === */}
      {/* Add an ID here for the scroll target */}
      <div id="dashboard-start"></div>

      {/* Use motion.div for the container to stagger children animations */}
      <motion.div
         className="dashboard-container" // Use class from App.css for grid layout
         variants={containerVariants}
         initial="hidden"
         whileInView="visible" // Animate when scrolled into view
         viewport={{ once: true, amount: 0.1 }} // Trigger animation when 10% visible, only once
      >
          {/* --- Map Component --- */}
          {/* Wrap map section in motion.div with item variant */}
          <motion.section id="map-section" className="dashboard-item map-item" variants={itemVariants}>
            {/* Pass necessary props to DroneMap */}
            <DroneMap
                droneData={droneData}
                restrictedZones={restrictedZones}
                lastUpdated={lastUpdated}
            />
          </motion.section>

          {/* --- Stats Panel Component --- */}
          {/* Wrap in motion.div with item variant */}
          <motion.div className="dashboard-item stats-item" variants={itemVariants}>
             <StatsPanel droneData={droneData} />
          </motion.div>

          {/* --- Validation Panel Component --- */}
          {/* Wrap in motion.div with item variant */}
          <motion.div className="dashboard-item validation-item" variants={itemVariants}>
             <DroneValidation droneData={droneData} />
          </motion.div>

          {/* --- Removed DroneUpdates as it seems redundant with the map/modal --- */}
          {/* If you need DroneUpdates, wrap it similarly:
           <motion.div className="dashboard-item updates-item" variants={itemVariants}>
             <DroneUpdates droneData={droneData} lastUpdated={lastUpdated} />
           </motion.div>
          */}

      </motion.div>
    </div>
  );
};

export default App;