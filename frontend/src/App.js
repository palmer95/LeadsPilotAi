import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const chatBoxRef = useRef(null);

  const faqs = [
    "What is your lead time?",
    "How much do your packages cost?",
    "What’s the process to book a shoot, and what details do you need from me?",
  ];

  useEffect(() => {
    chatBoxRef.current?.scrollTo({
      top: chatBoxRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  useEffect(() => {
    const welcome = {
      user: "",
      bot: "Hi! I’m Clyde 🤓\n\nI can answer questions about services and pricing, curate marketing packages based on your needs, and even book appointments with our team.\n\nPick from a FAQ below or type a message to get started.",
    };
    setMessages([welcome]);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    const newMessage = { user: query, bot: "..." };
    setMessages((prev) => [...prev, newMessage]);
    setLoading(true);

    try {
      const res = await axios.post("http://localhost:5050/api/chat", { query });
      newMessage.bot = res.data.response;
    } catch (err) {
      newMessage.bot = "Something went wrong!";
    }

    setMessages((prev) => [...prev.slice(0, -1), newMessage]);
    setQuery("");
    setLoading(false);
  };

  const handleFAQClick = (faq) => {
    setQuery(faq);
    setTimeout(() => document.querySelector("form").requestSubmit(), 50);
  };

  const handleReset = async () => {
    setMessages([]);
    setQuery("");
    try {
      await axios.post("http://localhost:5050/api/reset");
    } catch (err) {
      console.error("Reset failed", err);
    }

    setTimeout(() => {
      const welcome = {
        user: "",
        bot: "Hi! I’m Clyde 🤓\n\nI can answer questions about services and pricing, curate marketing packages based on your needs, and even book appointments with our team.\n\nPick from a FAQ below or type a message to get started.",
      };
      setMessages([welcome]);
    }, 200);
  };

  return (
    <div className="chat-container">
      <h2>Virtour Chat</h2>

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

        {loading && <div className="loading">Bot is typing...</div>}

        {messages.length === 1 && (
          <>
            <div className="faq-divider">Try a common question:</div>
            <div className="faq-buttons">
              {faqs.map((q, i) => (
                <button
                  key={i}
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
