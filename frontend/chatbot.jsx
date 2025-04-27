import React from "react";
import { createRoot } from "react-dom/client";
import ChatWidget from "./src/ChatWidget";

// ① Inline both your widget styles and your app styles
import chatCss from "bundle-text:./src/ChatWidget.css";
import appCss from "bundle-text:./src/App.css";

// ② Inject the combined CSS into <head>
const style = document.createElement("style");
style.textContent = chatCss + "\n" + appCss;
document.head.appendChild(style);

function mountWidget() {
  const script = document.currentScript;
  const company = script?.getAttribute("data-company") || "leadspilotai";
  const src = script?.src || "";
  const configUrl = src.replace(/\/chatbot\.js.*$/, "");

  const container = document.createElement("div");
  container.id = "leads-pilot-chatbot-container";
  document.body.appendChild(container);

  const root = createRoot(container);
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
