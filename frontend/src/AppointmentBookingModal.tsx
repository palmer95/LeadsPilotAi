import React, { useState, useEffect } from "react";
import axios from "axios";
import { createPortal } from "react-dom";
import "./AppointmentBookingModal.css";
import ShadowWrapper from "./ShadowWrapper";

interface AppointmentBookingModalProps {
  onClose: (status?: string) => void;
  company: string;
}

const API_BASE_URL = "https://leadspilotai.onrender.com";

const AppointmentBookingModal: React.FC<AppointmentBookingModalProps> = ({
  onClose,
  company,
}) => {
  const [calendar, setCalendar] = useState<{ [date: string]: string[] }>({});
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  const [bookedSlot, setBookedSlot] = useState<string | null>(null);
  const [name, setName] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [notes, setNotes] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);
  const [currentWeekStart, setCurrentWeekStart] = useState<Date>(() => {
    const now = new Date();
    const dayOfWeek = now.getDay(); // 0 (Sun) to 6 (Sat)
    const diffToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek; // Adjust to Monday
    return new Date(now.setDate(now.getDate() + diffToMonday));
  });

  useEffect(() => {
    const fetchCalendar = async () => {
      try {
        const startOfWeek = currentWeekStart.toISOString().split("T")[0];
        const res = await axios.get<{
          calendar: { [date: string]: string[] };
          startDate: string;
        }>(
          `${API_BASE_URL}/api/admin/calendar/week?company=${company}&startDate=${startOfWeek}`
        );
        setCalendar(res.data.calendar || {});
        setCurrentWeekStart(new Date(res.data.startDate)); // Sync with API response
      } catch (err) {
        setError("Failed to load calendar. Please try again.");
        console.error("Calendar fetch error:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchCalendar();
  }, [company, currentWeekStart]);

  const navigateWeek = (direction: "prev" | "next") => {
    setCurrentWeekStart((prev) => {
      const now = new Date();
      const currentMonday = new Date(
        now.setDate(
          now.getDate() - now.getDay() + (now.getDay() === 0 ? -6 : 1)
        )
      );
      const newWeekStart = new Date(prev);
      newWeekStart.setDate(prev.getDate() + (direction === "next" ? 7 : -7));
      return newWeekStart >= currentMonday ? newWeekStart : prev; // Prevent past weeks
    });
  };

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
    <ShadowWrapper>
      {success ? (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2>✅ Appointment Booked!</h2>
            {dateStr && (
              <p style={{ fontWeight: "bold", marginTop: "0.5em" }}>
                {dateStr}
              </p>
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
            {loading && <p>Loading calendar...</p>}
            {error && <p className="modal-error">{error}</p>}

            {!loading && !error && (
              <div className="calendar-container">
                <div className="calendar-nav">
                  <button
                    onClick={() => navigateWeek("prev")}
                    disabled={
                      currentWeekStart <=
                      new Date(
                        new Date().setDate(
                          new Date().getDate() -
                            new Date().getDay() +
                            (new Date().getDay() === 0 ? -6 : 1)
                        )
                      )
                    }
                  >
                    Previous Week
                  </button>
                  <span>
                    {currentWeekStart.toLocaleDateString("en-US", {
                      month: "long",
                      day: "numeric",
                    })}{" "}
                    -{" "}
                    {new Date(
                      currentWeekStart.getTime() + 6 * 24 * 60 * 60 * 1000
                    ).toLocaleDateString("en-US", {
                      month: "long",
                      day: "numeric",
                    })}
                  </span>
                  <button onClick={() => navigateWeek("next")}>
                    Next Week
                  </button>
                </div>
                <div className="calendar-grid">
                  {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map(
                    (day, index) => {
                      const date = new Date(currentWeekStart);
                      date.setDate(currentWeekStart.getDate() + index);
                      const dateStr = date.toISOString().split("T")[0];
                      const daySlots = calendar[dateStr] || [];
                      return (
                        <div key={day} className="calendar-day">
                          <h3>{day}</h3>
                          {daySlots.length ? (
                            daySlots.map((slot, i) => (
                              <button
                                key={i}
                                onClick={() => setSelectedSlot(slot)}
                                className={
                                  selectedSlot === slot
                                    ? "slot-selected"
                                    : "slot"
                                }
                              >
                                {new Date(slot).toLocaleTimeString("en-US", {
                                  hour: "numeric",
                                  minute: "2-digit",
                                  hour12: true,
                                })}
                              </button>
                            ))
                          ) : (
                            <p>No available slots</p>
                          )}
                        </div>
                      );
                    }
                  )}
                </div>
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
      )}
    </ShadowWrapper>,
    target
  );
};

export default AppointmentBookingModal;
