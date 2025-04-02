import React, { useMemo } from "react";
import "./DroneValidation.css"; // <-- Import your new CSS file

const DroneValidation = ({ droneData }) => {
  // Compute validation results using useMemo
  const validationResult = useMemo(() => {
    const total_drones = droneData.length;
    const authorized = droneData.filter((drone) => !drone.unauthorized).length;
    const unauthorized = droneData.filter((drone) => drone.unauthorized).length;
    const unknown = 0; // or compute if needed

    const validation_passed = authorized + unauthorized === total_drones;
    return { total_drones, authorized, unauthorized, unknown, validation_passed };
  }, [droneData]);

  return (
    <div className="drone-validation">
      <h2>📊 Drone Data Validation</h2>
      {droneData.length === 0 ? (
        <p>No drone data available for validation.</p>
      ) : (
        <div className="validation-container">
          <table className="validation-table">
            <tbody>
              {/* 
                Add the .unauthorized-row class to highlight the Unauthorized row in red.
                If you only want color when the unauthorized count is > 0, add conditional logic.
              */}
              <tr>
                <th>Total Drones</th>
                <td>{validationResult.total_drones}</td>
              </tr>
              <tr>
                <th>Authorized</th>
                <td>{validationResult.authorized}</td>
              </tr>
              <tr className={validationResult.unauthorized > 0 ? "unauthorized-row" : ""}>
                <th>Unauthorized</th>
                <td>{validationResult.unauthorized}</td>
              </tr>

              <tr>
                <th>Unknown</th>
                <td>{validationResult.unknown}</td>
              </tr>
            </tbody>
          </table>

          <p
            className="validation-status"
            style={{
              color: validationResult.validation_passed ? "green" : "red",
            }}
          >
            {validationResult.validation_passed
              ? "✔ Validation Passed"
              : "❌ Validation Failed"}
          </p>
        </div>
      )}
    </div>
  );
};

export default DroneValidation;
