// product/frontend/src/ChatWidget.js

import React, { useState, useEffect } from "react"; // 1. Make sure useEffect is imported
import App from "./App";
import "./ChatWidget.css";

export default function ChatWidget({ company, configUrl }) {
  const [isOpen, setIsOpen] = useState(false);
  const toggleWidget = () => setIsOpen((o) => !o);

  useEffect(() => {
    // This is the function that will be our "remote control"
    const openChat = () => {
      setIsOpen(true); // Sets the state to open the widget
    };

    // Attach the function to the global window object so the contact page can call it
    window.openLeadsPilotWidget = openChat;

    // Cleanup function: This is important to prevent memory leaks.
    // It removes the function from the window object if the widget is ever removed from the page.
    return () => {
      delete window.openLeadsPilotWidget;
    };
  }, []); // The empty array [] means this effect runs only once when the component mounts.

  return (
    <div className="chat-widget-wrapper">
      {isOpen && (
        <div className="chat-widget-popup">
          <App company={company} configUrl={configUrl} />
        </div>
      )}
      <button className="chat-bubble" onClick={toggleWidget}>
        {isOpen ? "✕" : "💬"}
      </button>
    </div>
  );
}
