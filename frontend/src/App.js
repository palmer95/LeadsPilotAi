// src/App.js

import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./App.css";

// your real chat API
const API_BASE_URL = "https://leadspilotai.onrender.com";

export default function App({ company, configUrl }) {
  const [config, setConfig] = useState(null);
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const chatBoxRef = useRef(null);

  // Load the client config JSON
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

  // Seed the welcome message
  useEffect(() => {
    if (!config) return;
    setMessages([{ user: "", bot: config.welcome }]);
  }, [config]);

  // Auto-scroll when messages change
  useEffect(() => {
    chatBoxRef.current?.scrollTo({
      top: chatBoxRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  // Core send logic
  const sendMessage = async (msg) => {
    if (!msg.trim() || !config) return;
    // append the user's message
    setMessages((m) => [...m, { user: msg, bot: "…" }]);
    setLoading(true);

    try {
      const res = await axios.post(`${API_BASE_URL}/api/chat`, {
        query: msg,
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
    } finally {
      setLoading(false);
    }
  };

  // Form submit uses sendMessage()
  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(query);
    setQuery("");
  };

  // FAQ click now calls sendMessage() directly
  const handleFAQClick = (faq) => {
    sendMessage(faq);
  };

  // Reset chat
  const handleReset = async () => {
    setMessages([]);
    setQuery("");
    try {
      await axios.post(`${API_BASE_URL}/api/reset`);
    } catch (err) {
      console.error("Reset failed:", err);
    }
    // re-seed welcome
    setTimeout(() => setMessages([{ user: "", bot: config.welcome }]), 200);
  };

  // Show loading state for config
  if (!config) {
    return <div className="chat-container">Loading…</div>;
  }

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
                <strong>Clyde:</strong> {m.bot}
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
                  disabled={loading}
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
          disabled={loading}
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
