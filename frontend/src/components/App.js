import React, { useState, useEffect, useRef } from "react";
import DroneMap from "./DroneMap";
import StatsPanel from "./StatsPanel";         // Make sure StatsPanel is imported
import DroneValidation from "./DroneValidation"; // Make sure DroneValidation is imported
import { motion } from "framer-motion";
import { FaPlay } from 'react-icons/fa';      // Import an icon for the button

// Import CSS files
import './App.css'; // Main App styles (Hero, Layout, Buttons)
// Component-specific CSS will be imported within those components

// Define the maximum number of drones to display on the map
const MAX_DRONES_ON_MAP = 20; // Set your desired limit here

const App = () => {
  // State for ALL drone data received (for stats & calculations)
  const [allDroneData, setAllDroneData] = useState([]);
  // State for the SUBSET of drones to display on the map
  const [displayDrones, setDisplayDrones] = useState([]);
  // Other existing state
  const [restrictedZones, setRestrictedZones] = useState([]);
  const [lastUpdated, setLastUpdated] = useState("");
  const socketRef = useRef(null);


  // --- Helper function to filter drones for display ---
  const filterAndSetDisplayDrones = (fullList) => {
    if (!Array.isArray(fullList)) {
         setDisplayDrones([]);
         return;
    }

    // Use callsign as a primary key check, adding simple index if needed for rendering keys
    // It's still important backend sends mostly unique callsigns
    const ensureUniqueKeys = (drones) => drones.map((drone, index) => ({
        ...drone,
        renderKey: `${drone.callsign || 'no-callsign'}-${index}` // Create a key for rendering
    }));


    const unauthorizedDrones = fullList.filter(d => d.unauthorized);
    const authorizedDrones = fullList.filter(d => !d.unauthorized);

    let dronesForMap = [];

    // Add unauthorized drones first
    dronesForMap = unauthorizedDrones;

    // Calculate remaining slots
    const remainingSlots = MAX_DRONES_ON_MAP - dronesForMap.length;

    if (remainingSlots > 0) {
      // If there's space left, fill with authorized drones (taking from the start of the list)
      // We take a slice of authorized drones to fill the remaining slots
      dronesForMap = dronesForMap.concat(authorizedDrones.slice(0, remainingSlots));
    }

    // If even the unauthorized drones exceed the limit, slice the result
    if (dronesForMap.length > MAX_DRONES_ON_MAP) {
        // Ensure we only take the max allowed, prioritizing the unauthorized ones already added
        dronesForMap = dronesForMap.slice(0, MAX_DRONES_ON_MAP);
    }

    // Add unique render keys before setting state
    const dronesWithKeys = ensureUniqueKeys(dronesForMap);

    // Update the state that controls the map markers
    setDisplayDrones(dronesWithKeys);
    console.log(`Displaying ${dronesWithKeys.length} of ${fullList.length} drones on map (prioritized unauthorized).`);
  };


  // --- Existing Hooks and Functions (Slightly modified for new state) ---
  const scrollToMap = () => {
    const mapSection = document.getElementById("dashboard-start");
    if (mapSection) {
      mapSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  // Ensure generated drones have a callsign that can be used for keys
  const generateRandomDrones = (count, forceUnauthorized = false) => {
    const drones = [];
    for (let i = 0; i < count; i++) {
      const lat = getRandomInRange(25, 49);
      const lon = getRandomInRange(-125, -67);
      const { isUnauthorized, zoneName } = checkRestrictedZone(lat, lon, restrictedZones);
      const shouldBeUnauthorized = forceUnauthorized || isUnauthorized || Math.random() < 0.1; // Reduced random chance

      // **Crucial:** Generate a unique callsign for simulation
      const callsign = `SIM-${Date.now().toString().slice(-6)}-${i}`;

      drones.push({
        callsign: callsign, // Ensure this is unique enough
        latitude: lat,
        longitude: lon,
        altitude: getRandomInRange(100, 3000),
        velocity: getRandomInRange(30, 200),
        unauthorized: shouldBeUnauthorized,
        zone: shouldBeUnauthorized ? (zoneName || (forceUnauthorized ? "Sim: Forced" : "Sim: Random")) : null,
      });
    }
    return drones;
  };

  const getRandomInRange = (min, max) => {
    return parseFloat((Math.random() * (max - min) + min).toFixed(6));
  };

  const checkRestrictedZone = (lat, lon, zones) => {
      const haversine = (lat1, lon1, lat2, lon2) => { /* ... haversine implementation ... */
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
          } else { console.warn("Skipping invalid zone object:", zone); }
      }
      return { isUnauthorized: false, zoneName: null };
  };

  // Fetch initial data and set up WebSocket
  useEffect(() => {
    const fetchRestrictedZones = async () => {
      try {
        const response = await fetch("http://127.0.0.1:8000/restricted-zones");
        if (!response.ok) throw new Error(`HTTP error fetching zones: ${response.status}`);
        const data = await response.json();
        const validZones = Array.isArray(data?.restricted_zones)
             ? data.restricted_zones.filter(z => z && typeof z.latitude === 'number' && typeof z.longitude === 'number')
             : [];
        setRestrictedZones(validZones);
        console.log("Fetched restricted zones:", validZones.length);
        // Fetch drone data only after zones are potentially loaded
        fetchDroneData(validZones);
      } catch (error) {
        console.error("Error fetching restricted zones:", error);
        setRestrictedZones([]);
        fetchDroneData([]); // Still try to fetch/simulate drones
      }
    };

    const fetchDroneData = async (currentZones) => {
      let initialFullDrones = []; // To hold the full list
      try {
         // ** Important: Make sure this backend endpoint exists or change URL **
        const response = await fetch("http://127.0.0.1:8000/fetch-drones-live");
        if (!response.ok) throw new Error(`HTTP error fetching drones: ${response.status}`);
        const data = await response.json();
        let fetchedDrones = data?.drones && Array.isArray(data.drones) ? data.drones : [];

        // Process fetched drones
        initialFullDrones = fetchedDrones.map(d => {
            const { isUnauthorized, zoneName } = checkRestrictedZone(d.latitude, d.longitude, currentZones);
            return { /* ... drone processing logic ... */
                ...d,
                // ** Crucial: Try to use a unique identifier from backend if available (e.g., icao24), otherwise fallback **
                callsign: d.callsign?.trim() || `UNK-${d.icao24 || Date.now().toString().slice(-5)}`, // Example using icao24
                latitude: d.latitude ?? 0,
                longitude: d.longitude ?? 0,
                altitude: d.altitude ?? 0,
                velocity: d.velocity ?? 0,
                unauthorized: d.unauthorized || isUnauthorized,
                zone: d.unauthorized ? (d.zone || zoneName || "Unauthorized") : (isUnauthorized ? zoneName : null)
             };
        });
        console.log("Initial drone data fetched:", initialFullDrones.length, "drones");

      } catch (error) {
        console.error("Error fetching initial drone data:", error);
        // Generate fallback data only on error
        console.log("Generating fallback simulation data due to fetch error...");
        let fallbackDrones = generateRandomDrones(15, false); // Generate more for fallback visibility
        const fallbackUnauthorized = generateRandomDrones(5, true); // Add 5 unauthorized
        initialFullDrones = [...fallbackDrones, ...fallbackUnauthorized];
      } finally {
          // Always update state after try/catch/fallback
          setAllDroneData(initialFullDrones); // Update the full data state
          filterAndSetDisplayDrones(initialFullDrones); // Filter for display
          setLastUpdated(new Date().toLocaleTimeString());
      }
    };

    fetchRestrictedZones(); // Start the process

    // --- WebSocket Setup ---
    const connectWebSocket = () => {
        console.log("Attempting WebSocket connection...");
        if (socketRef.current && socketRef.current.readyState !== WebSocket.CLOSED) {
             socketRef.current.close();
        }
        socketRef.current = new WebSocket("ws://127.0.0.1:8000/ws");
        socketRef.current.onopen = () => { console.log("✅ WebSocket Connected"); };
        socketRef.current.onmessage = (event) => {
            try {
                const receivedData = JSON.parse(event.data);
                if (receivedData.drones && Array.isArray(receivedData.drones)) {
                    console.log(`Received ${receivedData.drones.length} drones via WebSocket.`);
                    // Process WebSocket drones
                    let wsFullDrones = receivedData.drones.map(d => {
                         const { isUnauthorized, zoneName } = checkRestrictedZone(d.latitude, d.longitude, restrictedZones);
                         return { /* ... drone processing logic ... */
                           ...d,
                           // ** Crucial: Use same logic as initial fetch for consistent IDs **
                           callsign: d.callsign?.trim() || `UNK-${d.icao24 || Date.now().toString().slice(-5)}`,
                           latitude: d.latitude ?? 0,
                           longitude: d.longitude ?? 0,
                           altitude: d.altitude ?? 0,
                           velocity: d.velocity ?? 0,
                           unauthorized: d.unauthorized || isUnauthorized,
                           zone: d.unauthorized ? (d.zone || zoneName || "Unauthorized") : (isUnauthorized ? zoneName : null)
                         };
                     });

                    // Update full data state FIRST
                    setAllDroneData(wsFullDrones);
                    // THEN Filter for display
                    filterAndSetDisplayDrones(wsFullDrones);
                    // Update timestamp
                    setLastUpdated(new Date().toLocaleTimeString());

                } else { console.warn("⚠️ Unexpected WebSocket Data Format:", receivedData); }
            } catch (error) { console.error("❌ WebSocket Error Parsing Data:", error, "Data:", event.data); }
        };
        socketRef.current.onerror = (error) => { /* ... error handling ... */
             console.error("❌ WebSocket Error:", error);
             // Maybe add exponential backoff for retries
             setTimeout(connectWebSocket, 10000);
        };
        socketRef.current.onclose = (event) => { /* ... close handling ... */
             console.warn(`⚠️ WebSocket Disconnected. Code: ${event.code}, Reason: ${event.reason}. Reconnecting...`);
             if (event.code !== 1000 && event.code !== 1005) {
                setTimeout(connectWebSocket, 5000);
             }
        };
    };
    connectWebSocket(); // Initial connection attempt
    return () => { /* ... cleanup ... */
        console.log("Closing WebSocket connection on component unmount.");
        if (socketRef.current) {
            socketRef.current.onclose = null; // Prevent reconnect attempts after unmount
            socketRef.current.onerror = null;
            socketRef.current.close(1000, "Component unmounting");
        }
    };
  }, []); // Run only on mount


  // --- Framer Motion Animation Variants ---
  const containerVariants = { /* ... variants ... */
     hidden: { opacity: 0 },
     visible: { opacity: 1, transition: { staggerChildren: 0.25, delayChildren: 0.3, }}
  };
  const itemVariants = { /* ... variants ... */
     hidden: { y: 40, opacity: 0 },
     visible: { y: 0, opacity: 1, transition: { type: 'spring', stiffness: 80, damping: 15, duration: 0.8 } }
  };

  // --- Render JSX ---
  return (
    <div className="app-root-container">
      {/* === Hero Section === */}
      <section className="hero-section">
         {/* ... hero content ... */}
          <motion.h1 className="hero-title" initial={{ opacity: 0, y: -50 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}>
            🛰️ Real-Time Airspace Surveillance & Drone Monitoring
          </motion.h1>
          <motion.p className="hero-subtitle" initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1.0, delay: 0.4, ease: "easeOut" }}>
            Monitor unauthorized aerial activity, enhance airspace protection, and ensure real-time drone tracking with advanced detection technologies.
          </motion.p>
          <motion.button onClick={scrollToMap} className="hero-button" initial={{ opacity: 0, scale: 0.7 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.6, delay: 0.7, type: 'spring', stiffness: 120 }} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
             <FaPlay /> Launch Mission
          </motion.button>
      </section>

      {/* === Dashboard Section === */}
      <div id="dashboard-start"></div>
      <motion.div
         className="dashboard-container"
         variants={containerVariants}
         initial="hidden"
         whileInView="visible"
         viewport={{ once: true, amount: 0.1 }}
      >
          {/* --- Map Component --- */}
          <motion.section id="map-section" className="dashboard-item map-item" variants={itemVariants}>
            {/* ****** CHANGE HERE: Pass displayDrones to the map ****** */}
            <DroneMap
                // Use the filtered list for map markers
                droneData={displayDrones}
                // Other props remain the same
                restrictedZones={restrictedZones}
                lastUpdated={lastUpdated}
            />
          </motion.section>

          {/* --- Stats Panel Component --- */}
          <motion.div className="dashboard-item stats-item" variants={itemVariants}>
             {/* ****** CHANGE HERE: Pass allDroneData for stats ****** */}
             <StatsPanel droneData={allDroneData} />
          </motion.div>

          {/* --- Validation Panel Component --- */}
          <motion.div className="dashboard-item validation-item" variants={itemVariants}>
             {/* ****** CHANGE HERE: Pass allDroneData for validation ****** */}
             <DroneValidation droneData={allDroneData} />
          </motion.div>

      </motion.div>
    </div>
  );
};

export default App;