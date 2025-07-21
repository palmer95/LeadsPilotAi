import React from "react";
import { createRoot } from "react-dom/client";
import ChatWidget from "./src/ChatWidget";

// Inject the necessary CSS into the page head
import chatCss from "bundle-text:./src/ChatWidget.css";
import appCss from "bundle-text:./src/App.css";

const style = document.createElement("style");
style.textContent = chatCss + "\n" + appCss;
document.head.appendChild(style);

function mountWidget() {
  const script = document.currentScript;
  const company = script?.getAttribute("data-company") || "leadspilotai";

  // --- THE FIX IS HERE ---
  // We are hardcoding the URL to YOUR site, so it always knows where to look.
  const configUrl = "https://www.leadspilotai.com";

  const container = document.createElement("div");
  container.id = "leads-pilot-chatbot-container";
  document.body.appendChild(container);

  const root = createRoot(container);
  // We now pass the correct, hardcoded configUrl to your ChatWidget
  root.render(<ChatWidget company={company} configUrl={configUrl} />);
}

if (
  document.readyState === "complete" ||
  document.readyState === "interactive"
) {
  mountWidget();
} else {
  window.addEventListener("DOMContentLoaded", mountWidget);
}
