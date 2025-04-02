import React from 'react';
import ReactDOM from 'react-dom';
import './index.css';  // Styles for the app
import App from './components/App';  // Main App component
import process from 'process';
window.process = process;

ReactDOM.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
  document.getElementById('root')
);
