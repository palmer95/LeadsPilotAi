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
  const [showAllSlots, setShowAllSlots] = useState<{ [date: string]: boolean }>(
    {}
  );
  const [bookedSlot, setBookedSlot] = useState<string | null>(null);
  const [name, setName] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [phone, setPhone] = useState<string>("");
  const [notes, setNotes] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);

  // Helper to get the start of the week (Monday)
  const getStartOfWeek = (date: Date) => {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
    d.setHours(0, 0, 0, 0); // Set to midnight
    return new Date(d.setDate(diff));
  };

  const [currentWeekStart, setCurrentWeekStart] = useState<Date>(() =>
    getStartOfWeek(new Date())
  );

  // Memoize today's date at midnight for accurate comparisons
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  useEffect(() => {
    const fetchCalendar = async () => {
      setLoading(true);
      try {
        const now = new Date().toISOString();
        const res = await axios.get<{
          calendar: { [date: string]: string[] };
        }>(
          `${API_BASE_URL}/api/admin/calendar/week?company=${company}&currentTime=${now}`
        );
        setCalendar(res.data.calendar || {});
      } catch (err) {
        setError("Failed to load available slots. Please try again later.");
        console.error("Calendar fetch error:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchCalendar();
  }, [company, currentWeekStart]); // Refetch when week changes

  const navigateWeek = (direction: "prev" | "next") => {
    setCurrentWeekStart((prev) => {
      const newWeekStart = new Date(prev);
      newWeekStart.setDate(prev.getDate() + (direction === "next" ? 7 : -7));
      return newWeekStart;
    });
  };

  const handleBook = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedSlot || !name || !email) {
      setError("Please select a time slot and fill in your name and email.");
      return;
    }
    setLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/api/admin/calendar/book`, {
        slot: selectedSlot,
        name,
        email,
        phone,
        notes,
        company,
      });
      setBookedSlot(selectedSlot);
      setSuccess(true);
    } catch (err) {
      setError("Booking failed. The selected slot may no longer be available.");
      console.error("Booking error:", err);
    } finally {
      setLoading(false);
    }
  };

  // New, more accurate function to check if a slot is in the past
  const isPastSlot = (slotISOString: string): boolean => {
    return new Date(slotISOString) < new Date();
  };

  const dateStr = bookedSlot
    ? new Date(bookedSlot).toLocaleString("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      })
    : "";

  const getDaySuffix = (day: number) => {
    if (day > 3 && day < 21) return "th";
    switch (day % 10) {
      case 1:
        return "st";
      case 2:
        return "nd";
      case 3:
        return "rd";
      default:
        return "th";
    }
  };

  const weekDates = Array.from({ length: 7 }, (_, i) => {
    const date = new Date(currentWeekStart);
    date.setDate(currentWeekStart.getDate() + i);
    return date.toISOString().split("T")[0];
  });

  const daysOfWeek = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  const toggleShowAll = (date: string) => {
    setShowAllSlots((prev) => ({ ...prev, [date]: !prev[date] }));
  };

  const getMaxSlots = (date: string) =>
    showAllSlots[date] ? calendar[date]?.length || 0 : 5;

  const target =
    document.getElementById("leads-pilot-chatbot-container") || document.body;

  return createPortal(
    <ShadowWrapper>
      {success ? (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2>✅ Appointment Booked!</h2>
            {dateStr && <p className="success-date">{dateStr}</p>}
            <p>
              You’ll receive a confirmation email and calendar invite shortly.
            </p>
            <button onClick={() => onClose("success")}>Close</button>
          </div>
        </div>
      ) : (
        <div className="modal-overlay">
          <div className="modal-content">
            <button className="modal-close" onClick={() => onClose()}>
              ×
            </button>
            <h2>Book an Appointment</h2>
            <p className="modal-subtitle">
              Select an available time slot below.
            </p>

            {error && <p className="modal-error">{error}</p>}

            <div className="calendar-container">
              <div className="calendar-nav">
                <button
                  onClick={() => navigateWeek("prev")}
                  disabled={currentWeekStart <= today}
                >
                  Previous
                </button>
                <span>
                  {new Date(weekDates[0]).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })}
                  {" - "}
                  {new Date(weekDates[6]).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
                <button onClick={() => navigateWeek("next")}>Next</button>
              </div>

              {loading && <p className="loading-text">Loading calendar...</p>}
              {!loading && (
                <div className="calendar-grid">
                  <div className="calendar-header">
                    {daysOfWeek.map((day, index) => {
                      const date = new Date(weekDates[index]);
                      const dayNum = date.getDate();
                      return (
                        <div key={weekDates[index]} className="day-header-cell">
                          <div>{day}</div>
                          <div className="day-number">
                            {dayNum}
                            {getDaySuffix(dayNum)}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="calendar-body">
                    {weekDates.map((date) => (
                      <div key={date} className="day-column">
                        {(calendar[date] || [])
                          .slice(0, getMaxSlots(date))
                          .map((slot) => (
                            <button
                              key={slot}
                              className={
                                selectedSlot === slot
                                  ? "slot slot-selected"
                                  : "slot"
                              }
                              onClick={() => setSelectedSlot(slot)}
                              disabled={isPastSlot(slot)}
                            >
                              {new Date(slot).toLocaleTimeString("en-US", {
                                hour: "numeric",
                                minute: "2-digit",
                                hour12: true,
                              })}
                            </button>
                          ))}
                        {(calendar[date] || []).length === 0 && !loading && (
                          <p className="no-slots">No slots</p>
                        )}
                        {calendar[date] && calendar[date].length > 5 && (
                          <button
                            className="view-more"
                            onClick={() => toggleShowAll(date)}
                          >
                            {showAllSlots[date] ? "View Less" : "View More"}
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <form onSubmit={handleBook} className="booking-form">
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
              <input
                type="tel"
                placeholder="Your Phone (Optional)"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
              <textarea
                placeholder="Notes (Optional)"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
              <button type="submit" disabled={loading || !selectedSlot}>
                {loading ? "Booking..." : "Book Appointment"}
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
