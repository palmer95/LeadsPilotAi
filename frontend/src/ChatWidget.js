// product/frontend/src/ChatWidget.js

import React, { useState } from "react";
import App from "./App";
import ShadowWrapper from "./ShadowWrapper";
import "./ChatWidget.css";

export default function ChatWidget({ company, configUrl }) {
  const [isOpen, setIsOpen] = useState(false);
  const toggleWidget = () => setIsOpen((o) => !o);

  return (
    <div className="chat-widget-wrapper">
      {isOpen && (
        <div className="chat-widget-popup">
          <ShadowWrapper>
            <App company={company} configUrl={configUrl} />
          </ShadowWrapper>
        </div>
      )}
      <button className="chat-bubble" onClick={toggleWidget}>
        {isOpen ? "✕" : "💬"}
      </button>
    </div>
  );
}
