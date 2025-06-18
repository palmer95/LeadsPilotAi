// src/App.js
import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import AppointmentBookingModal from "./AppointmentBookingModal";
import "./App.css";

const API_BASE_URL = "https://leadspilotai.onrender.com";

export default function App({ company, configUrl }) {
  const [config, setConfig] = useState(null);
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showBookingModal, setShowBookingModal] = useState(false);
  const chatBoxRef = useRef(null);

  // Load client config JSON
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

  // Seed welcome message
  useEffect(() => {
    if (!config) return;
    setMessages([
      {
        user: "",
        bot: `Hi I'm Clyde 🤓, ${config.welcome} Type 'book' to schedule an appointment!`,
      },
    ]);
  }, [config]);

  // Auto-scroll
  useEffect(() => {
    chatBoxRef.current?.scrollTo({
      top: chatBoxRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  // Core send logic
  const sendMessage = async (msg) => {
    if (!msg.trim() || !config) return;
    setMessages((m) => [...m, { user: msg, bot: "…" }]);
    setLoading(true);

    try {
      // Check for booking command (case-insensitive, broader match)
      if (
        msg.toLowerCase().includes("book") ||
        msg.toLowerCase().includes("schedule") ||
        msg.toLowerCase().includes("appointment")
      ) {
        setShowBookingModal(true);
        setMessages((m) => {
          const last = m[m.length - 1];
          last.bot = "Opening appointment booking...";
          return [...m.slice(0, -1), last];
        });
        setLoading(false);
        return;
      }

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

  // Form submit
  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(query);
    setQuery("");
  };

  // FAQ click
  const handleFAQClick = (faq) => {
    sendMessage(faq);
  };

  // Booking button click
  const handleBookClick = () => {
    sendMessage("book appointment");
  };

  // Reset chat
  const handleReset = async () => {
    setMessages([]);
    setQuery("");
    setShowBookingModal(false);
    try {
      await axios.post(`${API_BASE_URL}/api/reset`);
    } catch (err) {
      console.error("Reset failed:", err);
    }
    setTimeout(
      () =>
        setMessages([
          {
            user: "",
            bot: `Hi I'm Clyde 🤓, ${config.welcome} Type 'book' to schedule an appointment!`,
          },
        ]),
      200
    );
  };

  // Modal close
  const handleModalClose = (status) => {
    setShowBookingModal(false);
    if (status === "success") {
      setMessages((m) => [
        ...m,
        {
          user: "",
          bot: "Your appointment has been booked! Check your email for confirmation.",
        },
      ]);
    }
  };

  if (!config) {
    return <div className="chat-container">Loading…</div>;
  }

  return (
    <div className="chat-container">
      <h2 className="chat-header">{config.business_name} Chat</h2>

      <div className="chat-box" ref={chatBoxRef} aria-live="polite">
        {messages.map((m, i) => (
          <div key={i} className="message-pair">
            {m.user && (
              <div className="user-msg">
                <span className="message-label">You:</span> {m.user}
              </div>
            )}
            {m.bot && (
              <div className="bot-msg">
                <span className="message-label">Clyde:</span> {m.bot}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="loading">
            Clyde is typing<span className="loading-dots">...</span>
          </div>
        )}

        {/* Always show Book Appointment button */}
        <div className="faq-divider">Options:</div>
        <div className="faq-buttons">
          <button
            onClick={handleBookClick}
            className="faq-button"
            disabled={loading}
            aria-label="Book an appointment"
          >
            Book Appointment
          </button>
          {config.faqs.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleFAQClick(q)}
              className="faq-button"
              disabled={loading}
              aria-label={`Ask: ${q}`}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="chat-form">
        <input
          className="chat-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask something…"
          disabled={loading}
          aria-label="Type your message"
        />

        <div className="chat-form-buttons">
          <button
            type="button"
            onClick={handleReset}
            disabled={loading}
            aria-label="Reset chat"
          >
            Reset Chat
          </button>
          <button
            type="submit"
            disabled={!query.trim() || loading}
            aria-label="Send message"
          >
            Send
          </button>
        </div>

        <div className="branding">
          <a
            href="https://www.leadspilotai.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="branding-link"
          >
            Powered by LeadsPilotAI
          </a>
        </div>
      </form>

      {showBookingModal && (
        <AppointmentBookingModal onClose={handleModalClose} company={company} />
      )}
    </div>
  );
}

// PRE GROK
// // src/App.js
// import React, { useState, useEffect, useRef } from "react";
// import axios from "axios";
// import AppointmentBookingModal from "./AppointmentBookingModal";
// import "./App.css";

// // your real chat API
// const API_BASE_URL = "https://leadspilotai.onrender.com";

// export default function App({ company, configUrl }) {
//   const [config, setConfig] = useState(null);
//   const [query, setQuery] = useState("");
//   const [messages, setMessages] = useState([]);
//   const [loading, setLoading] = useState(false);
//   const [showBookingModal, setShowBookingModal] = useState(false);
//   const chatBoxRef = useRef(null);

//   // Load the client config JSON
//   useEffect(() => {
//     if (!company) return;
//     (async () => {
//       try {
//         const res = await fetch(`${configUrl}/client-configs/${company}.json`);
//         if (!res.ok) throw new Error(res.statusText);
//         setConfig(await res.json());
//       } catch (err) {
//         console.error("Failed to load client config:", err);
//       }
//     })();
//   }, [company, configUrl]);

//   // Seed the welcome message
//   useEffect(() => {
//     if (!config) return;
//     setMessages([{ user: "", bot: `Hi I'm Clyde 🤓, ${config.welcome}` }]);
//   }, [config]);

//   // Auto-scroll when messages change
//   useEffect(() => {
//     chatBoxRef.current?.scrollTo({
//       top: chatBoxRef.current.scrollHeight,
//       behavior: "smooth",
//     });
//   }, [messages]);

//   // Core send logic
//   const sendMessage = async (msg) => {
//     if (!msg.trim() || !config) return;
//     setMessages((m) => [...m, { user: msg, bot: "…" }]);
//     setLoading(true);

//     try {
//       // check for booking
//       // Check for booking command
//       if (msg.toLowerCase().includes("book")) {
//         setShowBookingModal(true);
//         setMessages((m) => {
//           const last = m[m.length - 1];
//           last.bot = "Opening appointment booking...";
//           return [...m.slice(0, -1), last];
//         });
//         setLoading(false);
//         return;
//       }

//       const res = await axios.post(`${API_BASE_URL}/api/chat`, {
//         query: msg,
//         company,
//       });
//       setMessages((m) => {
//         const last = m[m.length - 1];
//         last.bot = res.data.response;
//         return [...m.slice(0, -1), last];
//       });
//     } catch (err) {
//       console.error("Chat error:", err);
//       setMessages((m) => {
//         const last = m[m.length - 1];
//         last.bot = "Something went wrong!";
//         return [...m.slice(0, -1), last];
//       });
//     } finally {
//       setLoading(false);
//     }
//   };

//   // Form submit uses sendMessage()
//   const handleSubmit = (e) => {
//     e.preventDefault();
//     sendMessage(query);
//     setQuery("");
//   };

//   // FAQ click now calls sendMessage() directly
//   const handleFAQClick = (faq) => {
//     sendMessage(faq);
//   };

//   const handleBookClick = () => {
//     sendMessage("book appointment");
//   };

//   // Reset chat
//   const handleReset = async () => {
//     setMessages([]);
//     setQuery("");
//     try {
//       await axios.post(`${API_BASE_URL}/api/reset`);
//     } catch (err) {
//       console.error("Reset failed:", err);
//     }
//     // re-seed welcome
//     setTimeout(
//       () =>
//         setMessages([{ user: "", bot: `Hi I'm Clyde 🤓, ${config.welcome}` }]),
//       200
//     );
//   };

//   // Handle modal close
//   const handleModalClose = (status) => {
//     setShowBookingModal(false);
//     if (status === "success") {
//       setMessages((m) => [
//         ...m,
//         {
//           user: "",
//           bot: "Your appointment has been booked! Check your email for confirmation.",
//         },
//       ]);
//     }
//   };

//   // Show loading state for config
//   if (!config) {
//     return <div className="chat-container">Loading…</div>;
//   }

//   return (
//     <div className="chat-container">
//       <h2 className="chat-header">{config.business_name} Chat</h2>

//       <div className="chat-box" ref={chatBoxRef} aria-live="polite">
//         {messages.map((m, i) => (
//           <div key={i} className="message-pair">
//             {m.user && (
//               <div className="user-msg">
//                 <span className="message-label">You:</span> {m.user}
//               </div>
//             )}
//             {m.bot && (
//               <div className="bot-msg">
//                 <span className="message-label">Clyde:</span> {m.bot}
//               </div>
//             )}
//           </div>
//         ))}

//         {loading && (
//           <div className="loading">
//             Clyde is typing<span className="loading-dots">...</span>
//           </div>
//         )}

//         {messages.length === 1 && (
//           <>
//             <div className="faq-divider">Try a common question:</div>
//             <div className="faq-buttons">
//               <button
//                 onClick={handleBookClick}
//                 className="faq-button"
//                 disabled={loading}
//                 aria-label="Book an appointment"
//               >
//                 Book Appointment
//               </button>
//               {config.faqs.map((q, idx) => (
//                 <button
//                   key={idx}
//                   onClick={() => handleFAQClick(q)}
//                   className="faq-button"
//                   disabled={loading}
//                   aria-label={`Ask: ${q}`}
//                 >
//                   {q}
//                 </button>
//               ))}
//             </div>
//           </>
//         )}
//       </div>

//       <form onSubmit={handleSubmit} className="chat-form">
//         <input
//           className="chat-input"
//           value={query}
//           onChange={(e) => setQuery(e.target.value)}
//           placeholder="Ask something…"
//           disabled={loading}
//           aria-label="Type your message"
//         />

//         <div className="chat-form-buttons">
//           <button
//             type="button"
//             onClick={handleReset}
//             disabled={loading}
//             aria-label="Reset chat"
//           >
//             Reset Chat
//           </button>
//           <button
//             type="submit"
//             disabled={!query.trim() || loading}
//             aria-label="Send message"
//           >
//             Send
//           </button>
//         </div>

//         <div className="branding">
//           <a
//             href="https://www.leadspilotai.com/"
//             target="_blank"
//             rel="noopener noreferrer"
//             className="branding-link"
//           >
//             Powered by LeadsPilotAI
//           </a>
//         </div>
//       </form>

//       {showBookingModal && (
//         <AppointmentBookingModal onClose={handleModalClose} company={company} />
//       )}
//     </div>
//   );
// }
