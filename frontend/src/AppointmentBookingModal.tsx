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
  const [phone, setPhone] = useState<string>("");
  const [notes, setNotes] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);
  const [currentWeekStart, setCurrentWeekStart] = useState<Date>(() => {
    const now = new Date();
    const dayOfWeek = now.getDay();
    const diffToSunday = dayOfWeek === 0 ? 0 : 7 - dayOfWeek;
    return new Date(now.setDate(now.getDate() + diffToSunday));
  });
  const [showAllSlots, setShowAllSlots] = useState<{ [date: string]: boolean }>(
    {}
  ); // Track expanded days

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
      const currentSunday = new Date(
        now.setDate(now.getDate() - now.getDay() + (now.getDay() === 0 ? 0 : 7))
      );
      const newWeekStart = new Date(prev);
      newWeekStart.setDate(prev.getDate() + (direction === "next" ? 7 : -7));
      return newWeekStart >= currentSunday ? newWeekStart : prev;
    });
  };

  const handleBook = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedSlot || !name || !email || !phone) {
      setError("Please select a slot and fill out all fields.");
      return;
    }
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

  const target =
    document.getElementById("leads-pilot-chatbot-container") || document.body;

  const daysOfWeek = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
  ];
  const weekDates = Array.from({ length: 7 }, (_, i) => {
    const date = new Date(currentWeekStart);
    date.setDate(currentWeekStart.getDate() + i);
    return date.toISOString().split("T")[0];
  });

  const toggleShowAll = (date: string) => {
    setShowAllSlots((prev) => ({ ...prev, [date]: !prev[date] }));
  };

  // Determine the maximum number of slots to render based on "View More"
  const getMaxSlots = (date: string) =>
    showAllSlots[date] ? calendar[date]?.length || 0 : 5;

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
                            (new Date().getDay() === 0 ? 0 : 7)
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
                <div className="calendar-table-wrapper">
                  <table className="calendar-table">
                    <thead>
                      <tr className="day-headers">
                        {daysOfWeek.map((day, index) => {
                          const date = new Date(weekDates[index]);
                          const dayNum = date.getDate();
                          const suffix = getDaySuffix(dayNum);
                          return (
                            <th
                              key={weekDates[index]}
                              className="day-header-cell"
                            >
                              {day} ({dayNum}
                              {suffix})
                            </th>
                          );
                        })}
                      </tr>
                    </thead>
                    <tbody className="day-slots">
                      {Array.from({ length: 10 }).map(
                        (
                          _,
                          rowIndex // Increased to 10 to handle more slots if expanded
                        ) => (
                          <tr key={rowIndex} className="slot-row">
                            {weekDates.map((date) => {
                              const slots = calendar[date] || [];
                              const maxSlots = getMaxSlots(date);
                              const displaySlots = slots.slice(0, maxSlots);
                              const slot = displaySlots[rowIndex];
                              return (
                                <td key={date} className="day-column">
                                  {slot ? (
                                    <button
                                      className={
                                        selectedSlot === slot
                                          ? "slot-selected"
                                          : "slot"
                                      }
                                      onClick={() => setSelectedSlot(slot)}
                                    >
                                      {new Date(slot).toLocaleTimeString(
                                        "en-US",
                                        {
                                          hour: "numeric",
                                          minute: "2-digit",
                                          hour12: true,
                                        }
                                      )}
                                    </button>
                                  ) : rowIndex === 0 && slots.length === 0 ? (
                                    <p className="no-slots">
                                      No available slots
                                    </p>
                                  ) : null}
                                </td>
                              );
                            })}
                          </tr>
                        )
                      )}
                      <tr className="view-more-row">
                        {weekDates.map((date) => (
                          <td key={date} className="day-column">
                            {calendar[date] && calendar[date].length > 5 && (
                              <button
                                className="view-more"
                                onClick={() => toggleShowAll(date)}
                                style={{
                                  display: "block",
                                  margin: "10px auto",
                                }}
                              >
                                {showAllSlots[date] ? "View Less" : "View More"}
                              </button>
                            )}
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <form onSubmit={handleBook} className="form">
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
                placeholder="Your Phone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
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
