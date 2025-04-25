import React, { useMemo } from "react";
import "./DroneValidation.css";

const DroneValidation = ({ droneData }) => {
  const validationResult = useMemo(() => {
    const total_drones = droneData.length;
    const authorized = droneData.filter((drone) => !drone.unauthorized).length;
    const unauthorized = droneData.filter((drone) => drone.unauthorized).length;
    const unknown = 0;
    const validation_passed = authorized + unauthorized === total_drones;
    return { total_drones, authorized, unauthorized, unknown, validation_passed };
  }, [droneData]);

  return (
    <div className="drone-validation">
      <h2 className="validation-heading neon-title">📊 Drone Data Validation</h2>
      {droneData.length === 0 ? (
        <p className="no-data">No drone data available for validation.</p>
      ) : (
        <div className="validation-container">
          <table className="validation-table">
            <tbody>
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

          <div className={`validation-status ${validationResult.validation_passed ? "passed" : "failed"}`}>
            {validationResult.validation_passed ? "✔ Validation Passed" : "❌ Validation Failed"}
          </div>
        </div>
      )}
    </div>
  );
};

export default DroneValidation;