import React, { useState, useEffect } from "react";
import axios from "axios";
import { createPortal } from "react-dom";
import "./AppointmentBookingModal.css";

interface AppointmentBookingModalProps {
  onClose: (status?: string) => void;
  company: string;
}

const API_BASE_URL = "https://leadspilotai.onrender.com";

const AppointmentBookingModal: React.FC<AppointmentBookingModalProps> = ({
  onClose,
  company,
}) => {
  const [slots, setSlots] = useState<string[]>([]);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  const [bookedSlot, setBookedSlot] = useState<string | null>(null);
  const [name, setName] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [notes, setNotes] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);

  useEffect(() => {
    const fetchSlots = async () => {
      try {
        const res = await axios.get<{ slots: string[] }>(
          `${API_BASE_URL}/api/admin/calendar/slots?company=${company}`
        );
        const fetchedSlots = res.data.slots || [];
        setSlots(fetchedSlots.slice(0, 12));
      } catch (err) {
        setError("Failed to load slots. Please try again.");
        console.error("Slot fetch error:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchSlots();
  }, [company]);

  const handleBook = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedSlot || !name || !email) {
      setError("Please select a slot and fill out all fields.");
      return;
    }

    try {
      await axios.post(`${API_BASE_URL}/api/admin/calendar/book`, {
        slot: selectedSlot,
        name,
        email,
        notes,
        company,
      });
      setBookedSlot(selectedSlot);
      setSuccess(true);
    } catch (err) {
      setError("Booking failed. Please try again.");
      console.error("Booking error:", err);
    }
  };

  const dateStr = bookedSlot
    ? new Date(bookedSlot).toLocaleString("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
        timeZone: "America/Los_Angeles",
      })
    : "";

  const target =
    document.getElementById("leads-pilot-chatbot-container") || document.body;

  return createPortal(
    success ? (
      <div className="modal-overlay">
        <div className="modal-content">
          <h2>✅ Appointment Booked!</h2>
          {dateStr && (
            <p style={{ fontWeight: "bold", marginTop: "0.5em" }}>{dateStr}</p>
          )}
          <p>You’ll receive a confirmation email shortly.</p>
          <button onClick={() => onClose("success")}>Close</button>
        </div>
      </div>
    ) : (
      <div className="modal-overlay">
        <div className="modal-content">
          <button className="modal-close" onClick={() => onClose()}>
            ×
          </button>
          <h2 style={{ marginBottom: "0.25em" }}>Book Appointment</h2>
          <p style={{ marginTop: 0, fontSize: "16px", fontWeight: 500 }}>
            Select a Slot
          </p>
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
    ),
    target
  );
};

export default AppointmentBookingModal;
