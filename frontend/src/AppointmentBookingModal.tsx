// src/components/AppointmentBookingModal.js
import React, { useState, useEffect } from "react";
import axios from "axios";
import "./AppointmentBookingModal.css";

const API_BASE_URL = "https://leadspilotai.onrender.com";

const AppointmentBookingModal = ({ onClose, company }) => {
  const [slots, setSlots] = useState([]);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchSlots = async () => {
      try {
        const authToken = localStorage.getItem("authToken");
        const res = await axios.get(
          `${API_BASE_URL}/api/admin/calendar/slots?company=${company}`,
          {
            headers: { Authorization: `Bearer ${authToken}` },
          }
        );
        const fetchedSlots = res.data.slots || [];

        console.log("Raw slots from backend: ", fetchedSlots);

        const filteredSlots = fetchedSlots
          .map((slot) => new Date(slot))
          .filter((date) => {
            const localHour = date.getHours(); // Local time already
            return localHour >= 9 && localHour < 17;
          })
          .map((date) => date.toISOString());

        console.log("Filtered (9am-5pm) slots:", filteredSlots);

        setSlots(filteredSlots.slice(0, 20));
      } catch (err) {
        setError("Failed to load slots. Please try again.");
        console.error("Slot fetch error:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchSlots();
  }, [company]);

  const handleBook = async (e) => {
    e.preventDefault();
    if (!selectedSlot || !name || !email) {
      setError("Please select a slot and fill out all fields.");
      return;
    }

    try {
      const authToken = localStorage.getItem("authToken");
      await axios.post(
        `${API_BASE_URL}api/admin/calendar/book`,
        { slot: selectedSlot, name, email, notes, company },
        { headers: { Authorization: `Bearer ${authToken}` } }
      );
      onClose("success");
    } catch (err) {
      setError("Booking failed. Please try again.");
      console.error("Booking error:", err);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <button className="modal-close" onClick={() => onClose()}>
          ×
        </button>
        <h2>Book Appointment</h2>
        <h3>Select a Slot</h3>
        {loading && <p>Loading slots...</p>}
        {error && <p className="modal-error">{error}</p>}
        {!loading && !error && (
          <div className="slot-grid">
            {slots.map((slot, index) => (
              <button
                key={index}
                onClick={() => setSelectedSlot(slot)}
                className={selectedSlot === slot ? "slot-selected" : "slot"}
              >
                {new Date(slot).toLocaleString("en-US", {
                  weekday: "short",
                  hour: "numeric",
                  minute: "2-digit",
                  hour12: true,
                })}
              </button>
            ))}
          </div>
        )}
        <form onSubmit={handleBook}>
          <input
            type="text"
            placeholder="Your Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <input
            type="email"
            placeholder="Your Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <textarea
            placeholder="Notes (optional)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <button type="submit" disabled={loading || !selectedSlot}>
            {loading ? "Booking..." : "Book Now"}
          </button>
        </form>
      </div>
    </div>
  );
};

export default AppointmentBookingModal;
