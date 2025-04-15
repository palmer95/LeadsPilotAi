import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const chatBoxRef = useRef(null);

  useEffect(() => {
    // Auto-scroll to bottom when messages update
    chatBoxRef.current?.scrollTo({
      top: chatBoxRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    const newMessage = { user: query, bot: "..." };
    setMessages((prev) => [...prev, newMessage]);
    setLoading(true);

    try {
      const res = await axios.post(
        "http://localhost:5050/api/chat",
        { query },
        {
          headers: { "Content-Type": "application/json" },
        }
      );
      newMessage.bot = res.data.response;
    } catch (err) {
      newMessage.bot = "Something went wrong!";
    }

    setMessages((prev) => [...prev.slice(0, -1), newMessage]);
    setQuery("");
    setLoading(false);
  };

  const handleReset = async () => {
    setMessages([]);
    try {
      await axios.post("http://localhost:5050/api/reset");
    } catch (err) {
      console.error("Failed to reset memory", err);
    }
  };

  return (
    <div className="chat-container">
      <h2>Virtour Chatbot</h2>

      <div className="chat-box" ref={chatBoxRef}>
        {messages.map((m, i) => (
          <div key={i} className="message-pair">
            <div className="user-msg">
              <strong>You:</strong> {m.user}
            </div>
            <div className="bot-msg">
              <strong>Bot:</strong>{" "}
              {typeof m.bot === "string"
                ? m.bot
                : m.bot?.result || "Error rendering response"}
            </div>

            <hr />
          </div>
        ))}
        {loading && <div className="loading">Bot is typing...</div>}
      </div>

      <form onSubmit={handleSubmit} className="chat-form">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask something..."
        />
        <button type="submit" disabled={!query.trim() || loading}>
          Send
        </button>
        <button type="button" onClick={handleReset}>
          Reset Chat
        </button>
      </form>
    </div>
  );
}

export default App;
