import React, { useState, useEffect, CSSProperties } from "react"; // <-- 1. CSSProperties is imported here
import axios from "axios";
import { createPortal } from "react-dom";
import ShadowWrapper from "./ShadowWrapper";

// --- STYLES ARE NOW EXPLICITLY TYPED ---
// 2. We tell TypeScript this object contains keys that map to CSSProperties objects
const styles: { [key: string]: CSSProperties } = {
  modalOverlay: {
    position: "fixed",
    top: 0,
    left: 0,
    width: "100vw",
    height: "100vh",
    background: "rgba(0, 0, 0, 0.75)",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 2147483647,
    fontFamily:
      "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  },
  modalContent: {
    background: "white",
    padding: "24px",
    borderRadius: "12px",
    width: "95%",
    maxWidth: "1100px",
    maxHeight: "90vh",
    overflowY: "auto", // <-- This is now type-safe
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.2)",
    position: "relative",
  },
  h2: { marginTop: 0, marginBottom: "4px", fontSize: "24px", color: "#1a1a1a" },
  modalSubtitle: {
    marginTop: 0,
    marginBottom: "20px",
    fontSize: "16px",
    color: "#666",
  },
  modalClose: {
    position: "absolute",
    top: "12px",
    right: "12px",
    border: "none",
    background: "none",
    fontSize: "30px",
    fontWeight: "bold",
    lineHeight: 1,
    cursor: "pointer",
    color: "#aaa",
    padding: 0,
    transition: "color 0.2s ease-in-out, transform 0.2s ease",
  },
  modalError: {
    color: "#d93025",
    backgroundColor: "#fbe9e7",
    border: "1px solid #d93025",
    borderRadius: "4px",
    padding: "10px",
    margin: "10px 0",
    fontSize: "14px",
  },
  loadingText: { textAlign: "center", padding: "40px", color: "#666" },
  calendarNav: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "16px",
    background: "#f8f9fa",
    padding: "8px",
    borderRadius: "6px",
  },
  navButton: {
    padding: "8px 16px",
    fontSize: "14px",
    background: "#007bff",
    color: "white",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    transition: "background 0.2s",
  },
  navButtonDisabled: { background: "#ccc", cursor: "not-allowed" },
  navSpan: { fontSize: "16px", fontWeight: 500, color: "#333" },
  calendarGrid: {
    width: "100%",
    border: "1px solid #e0e0e0",
    borderRadius: "8px",
    overflow: "hidden",
  },
  calendarHeader: {
    display: "grid",
    gridTemplateColumns: "repeat(7, 1fr)",
    width: "100%",
  },
  calendarBody: {
    display: "grid",
    gridTemplateColumns: "repeat(7, 1fr)",
    width: "100%",
  },
  dayHeaderCell: {
    textAlign: "center",
    padding: "12px 5px",
    background: "#f8f9fa",
    fontSize: "14px",
    fontWeight: 600,
    color: "#333",
    borderBottom: "1px solid #e0e0e0",
  },
  dayNumber: { fontSize: "12px", fontWeight: 400, color: "#666" },
  dayColumn: {
    borderRight: "1px solid #e0e0e0",
    minHeight: "150px",
    padding: "8px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "8px",
  },
  slot: {
    width: "100%",
    padding: "10px 5px",
    border: "1px solid #007bff",
    borderRadius: "4px",
    background: "white",
    color: "#007bff",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: 500,
    transition: "all 0.2s",
    boxSizing: "border-box",
  },
  slotSelected: {
    background: "#007bff",
    color: "white",
    borderColor: "#0056b3",
    transform: "scale(1.05)",
  },
  slotDisabled: {
    borderColor: "#ccc",
    color: "#ccc",
    cursor: "not-allowed",
    background: "#f9f9f9",
  },
  noSlots: {
    color: "#999",
    fontStyle: "italic",
    fontSize: "12px",
    textAlign: "center",
    marginTop: "20px",
  },
  viewMore: {
    width: "100%",
    background: "transparent",
    border: "none",
    color: "#007bff",
    fontWeight: 500,
    cursor: "pointer",
    padding: "8px",
    marginTop: "auto",
  },
  bookingForm: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    marginTop: "24px",
  },
  input: {
    padding: "12px",
    fontSize: "16px",
    border: "1px solid #ccc",
    borderRadius: "4px",
  },
  submitButton: {
    padding: "14px",
    fontSize: "16px",
    fontWeight: "bold",
    background: "#28a745",
    color: "white",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
  },
  successDate: {
    fontWeight: "bold",
    marginTop: "0.5em",
    fontSize: "18px",
    color: "#28a745",
  },
};

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

  const getStartOfWeek = (date: Date) => {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    d.setHours(0, 0, 0, 0);
    return new Date(d.setDate(diff));
  };

  const [currentWeekStart, setCurrentWeekStart] = useState<Date>(() =>
    getStartOfWeek(new Date())
  );
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  useEffect(() => {
    const fetchCalendar = async () => {
      setLoading(true);
      setError(null);
      try {
        const weekStartIso = currentWeekStart.toISOString();
        const res = await axios.get(
          `${API_BASE_URL}/api/admin/calendar/week?company=${company}&currentTime=${weekStartIso}`
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
  }, [company, currentWeekStart]);

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
    } finally {
      setLoading(false);
    }
  };

  const isPastSlot = (slotISOString: string): boolean =>
    new Date(slotISOString) < new Date();
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
  const toggleShowAll = (date: string) =>
    setShowAllSlots((prev) => ({ ...prev, [date]: !prev[date] }));
  const getMaxSlots = (date: string) =>
    showAllSlots[date] ? calendar[date]?.length || 0 : 5;

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

  const target =
    document.getElementById("leads-pilot-chatbot-container") || document.body;

  // The hover effect for the close button is handled here since it's tricky with inline styles
  const handleCloseButtonHover = (
    isHovering: boolean,
    e: React.MouseEvent<HTMLButtonElement>
  ) => {
    e.currentTarget.style.color = isHovering ? "#ff4136" : "#aaa";
    e.currentTarget.style.transform = isHovering
      ? "rotate(90deg)"
      : "rotate(0deg)";
  };

  return createPortal(
    <ShadowWrapper>
      {success ? (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <h2 style={styles.h2}>✅ Appointment Booked!</h2>
            {dateStr && <p style={styles.successDate}>{dateStr}</p>}
            <p>
              You’ll receive a confirmation email and calendar invite shortly.
            </p>
            <button
              style={styles.submitButton}
              onClick={() => onClose("success")}
            >
              Close
            </button>
          </div>
        </div>
      ) : (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <button
              style={styles.modalClose}
              onMouseEnter={(e) => handleCloseButtonHover(true, e)}
              onMouseLeave={(e) => handleCloseButtonHover(false, e)}
              onClick={() => onClose()}
            >
              ×
            </button>
            <h2 style={styles.h2}>Book an Appointment</h2>
            <p style={styles.modalSubtitle}>
              Select an available time slot below.
            </p>
            {error && <p style={styles.modalError}>{error}</p>}
            <div className="calendar-container">
              <div style={styles.calendarNav}>
                <button
                  style={{
                    ...styles.navButton,
                    ...(currentWeekStart <= today && styles.navButtonDisabled),
                  }}
                  onClick={() => navigateWeek("prev")}
                  disabled={currentWeekStart <= today}
                >
                  Previous
                </button>
                <span style={styles.navSpan}>
                  {new Date(weekDates[0]).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })}{" "}
                  -{" "}
                  {new Date(weekDates[6]).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
                <button
                  style={styles.navButton}
                  onClick={() => navigateWeek("next")}
                >
                  Next
                </button>
              </div>
              {loading && <p style={styles.loadingText}>Loading calendar...</p>}
              {!loading && !error && (
                <div style={styles.calendarGrid}>
                  <div style={styles.calendarHeader}>
                    {daysOfWeek.map((day, index) => {
                      const date = new Date(weekDates[index]);
                      return (
                        <div
                          key={weekDates[index]}
                          style={styles.dayHeaderCell}
                        >
                          <div>{day}</div>
                          <div style={styles.dayNumber}>
                            {date.getDate()}
                            {getDaySuffix(date.getDate())}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div style={styles.calendarBody}>
                    {weekDates.map((date, index) => (
                      <div
                        key={date}
                        style={{
                          ...styles.dayColumn,
                          borderRight:
                            index === 6 ? "none" : "1px solid #e0e0e0",
                        }}
                      >
                        {(calendar[date] || [])
                          .slice(0, getMaxSlots(date))
                          .map((slot) => {
                            const isSelected = selectedSlot === slot;
                            const isPast = isPastSlot(slot);
                            const currentStyle = isPast
                              ? { ...styles.slot, ...styles.slotDisabled }
                              : isSelected
                                ? { ...styles.slot, ...styles.slotSelected }
                                : styles.slot;
                            return (
                              <button
                                key={slot}
                                style={currentStyle}
                                onClick={() => setSelectedSlot(slot)}
                                disabled={isPast}
                              >
                                {new Date(slot).toLocaleTimeString("en-US", {
                                  hour: "numeric",
                                  minute: "2-digit",
                                  hour12: true,
                                })}
                              </button>
                            );
                          })}
                        {(calendar[date] || []).length === 0 && !loading && (
                          <p style={styles.noSlots}>No slots</p>
                        )}
                        {calendar[date] && calendar[date].length > 5 && (
                          <button
                            style={styles.viewMore}
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
            <form onSubmit={handleBook} style={styles.bookingForm}>
              <input
                style={styles.input}
                type="text"
                placeholder="Your Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
              <input
                style={styles.input}
                type="email"
                placeholder="Your Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <input
                style={styles.input}
                type="tel"
                placeholder="Your Phone (Optional)"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
              <textarea
                style={styles.input}
                placeholder="Notes (Optional)"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
              <button
                type="submit"
                style={{
                  ...styles.submitButton,
                  ...((loading || !selectedSlot) && styles.navButtonDisabled),
                }}
                disabled={loading || !selectedSlot}
              >
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
