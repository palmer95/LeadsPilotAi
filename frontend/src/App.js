// src/App.js

import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./App.css";

// ─── Your real chat API ─────────────────────────────────────────────────────
const API_BASE_URL = "https://leadspilotai.onrender.com";

export default function App({ company, configUrl }) {
  const [config, setConfig] = useState(null);
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const chatBoxRef = useRef(null);

  // 1️⃣ Load the JSON from your public/client-configs folder
  useEffect(() => {
    if (!company) return;
    (async () => {
      try {
        const res = await fetch(`${configUrl}/client-configs/${company}.json`);
        if (!res.ok) throw new Error(res.statusText);
        setConfig(await res.json());
      } catch (err) {
        console.error("Failed to load client config:", err);
      }
    })();
  }, [company, configUrl]);

  // 2️⃣ Seed welcome once config arrives
  useEffect(() => {
    if (!config) return;
    setMessages([{ user: "", bot: config.welcome }]);
  }, [config]);

  // 3️⃣ Scroll on new messages
  useEffect(() => {
    chatBoxRef.current?.scrollTo({
      top: chatBoxRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  // 4️⃣ Send a message to your Flask /api/chat
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim() || !config) return;

    setMessages((m) => [...m, { user: query, bot: "…" }]);
    setLoading(true);

    try {
      const res = await axios.post(`${API_BASE_URL}/api/chat`, {
        query,
        company,
      });
      setMessages((m) => {
        const last = m[m.length - 1];
        last.bot = res.data.response;
        return [...m.slice(0, -1), last];
      });
    } catch (err) {
      console.error("Chat error:", err);
      setMessages((m) => {
        const last = m[m.length - 1];
        last.bot = "Something went wrong!";
        return [...m.slice(0, -1), last];
      });
    }

    setQuery("");
    setLoading(false);
  };

  // 5️⃣ FAQ buttons still driven by config.faqs
  const handleFAQClick = (faq) => {
    setQuery(faq);
    setTimeout(() => document.querySelector("form").requestSubmit(), 50);
  };

  // 6️⃣ Reset both UI and server-side state
  const handleReset = async () => {
    setMessages([]);
    setQuery("");

    try {
      await axios.post(`${API_BASE_URL}/api/reset`);
    } catch (err) {
      console.error("Reset failed:", err);
    }

    // re-seed the welcome after a short delay
    setTimeout(() => setMessages([{ user: "", bot: config.welcome }]), 200);
  };

  // 7️⃣ Loading state
  if (!config) {
    return <div className="chat-container">Loading…</div>;
  }

  // ─── Render the chat UI ────────────────────────────────────────────────────
  return (
    <div className="chat-container">
      <h2>{config.business_name} Chat</h2>

      <div className="chat-box" ref={chatBoxRef}>
        {messages.map((m, i) => (
          <div key={i} className="message-pair">
            {m.user && (
              <div className="user-msg">
                <strong>You:</strong> {m.user}
              </div>
            )}
            {m.bot && (
              <div className="bot-msg">
                <strong>{config.business_name}:</strong> {m.bot}
              </div>
            )}
            <hr />
          </div>
        ))}

        {loading && <div className="loading">Bot is typing…</div>}

        {messages.length === 1 && (
          <>
            <div className="faq-divider">Try a common question:</div>
            <div className="faq-buttons">
              {config.faqs.map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => handleFAQClick(q)}
                  className="faq-button"
                >
                  {q}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <form onSubmit={handleSubmit} className="chat-form">
        <input
          className="chat-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask something…"
        />

        <div className="chat-form-buttons">
          <button type="submit" disabled={!query.trim() || loading}>
            Send
          </button>
          <button type="button" onClick={handleReset} disabled={loading}>
            Reset Chat
          </button>
        </div>

        <div className="branding">Powered by LeadsPilotAI</div>
      </form>
    </div>
  );
}
