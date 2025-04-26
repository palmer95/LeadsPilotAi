// product/frontend/chatbot.jsx

import React from "react";
import { createRoot } from "react-dom/client";
import ChatWidget from "./src/ChatWidget";
import css from "bundle-text:./src/ChatWidget.css";

// 1) Inject the widget’s CSS into <head>
const style = document.createElement("style");
style.textContent = css;
document.head.appendChild(style);

function mountWidget() {
  // 2) Grab the <script> tag that loaded this bundle
  const script = document.currentScript;

  // 3) Read the company slug (fallback to "leadspilotai" for local/dev)
  const company = script?.getAttribute("data-company") || "leadspilotai";

  // 4) Derive the base URL by stripping off "/chatbot.js" from the script src
  const src = script?.src || "";
  const configUrl = src.replace(/\/chatbot\.js.*$/, "");

  // 5) Create and append the container div
  const container = document.createElement("div");
  container.id = "leads-pilot-chatbot-container";
  document.body.appendChild(container);

  // 6) Render the React tree, passing down company & configUrl
  const root = createRoot(container);
  root.render(<ChatWidget company={company} configUrl={configUrl} />);
}

// 7) Wait until DOM is ready, then mount
if (
  document.readyState === "complete" ||
  document.readyState === "interactive"
) {
  mountWidget();
} else {
  window.addEventListener("DOMContentLoaded", mountWidget);
}
