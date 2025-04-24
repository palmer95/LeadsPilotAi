// ChatWidget.js
import React, { useState } from "react";
import App from "./App";
import "./ChatWidget.css";

function ChatWidget() {
  // start open so you can see the form/buttons right away
  const [isOpen, setIsOpen] = useState(false);

  const toggleWidget = () => setIsOpen((o) => !o);

  return (
    <div className="chat-widget-wrapper">
      {isOpen && (
        <div className="chat-widget-popup">
          <App />
        </div>
      )}
      <button className="chat-bubble" onClick={toggleWidget}>
        {isOpen ? "✕" : "💬"}
      </button>
    </div>
  );
}

export default ChatWidget;
