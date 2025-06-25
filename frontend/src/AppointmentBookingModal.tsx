import React, { useState, useEffect } from "react";
import axios from "axios";
import { createPortal } from "react-dom";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import scrollgridPlugin from "@fullcalendar/scrollgrid"; // Added missing plugin
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
  const [events, setEvents] = useState<any[]>([]);
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
        const calendarData = res.data.calendar || {};
        const eventsData = Object.entries(calendarData).flatMap(
          ([date, slots]) =>
            slots.map((slot) => ({
              title: new Date(slot).toLocaleTimeString("en-US", {
                hour: "numeric",
                minute: "2-digit",
                hour12: true,
              }),
              start: new Date(slot),
              allDay: false,
              extendedProps: { slot: slot },
            }))
        );
        setEvents(eventsData);
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

  const handleSelectSlot = (info: any) => {
    setSelectedSlot(info.event ? info.event.extendedProps.slot : info.startStr);
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
                <div className="calendar-wrapper">
                  <FullCalendar
                    plugins={[
                      timeGridPlugin,
                      interactionPlugin,
                      scrollgridPlugin,
                    ]} // Added scrollgridPlugin
                    initialView="timeGridWeek"
                    events={events}
                    selectable={true}
                    selectMirror={true}
                    dayMinWidth={100} // Ensure readable columns
                    slotMinTime="09:00:00" // Start at 9 AM
                    slotMaxTime="17:00:00" // End at 5 PM
                    allDaySlot={false} // Disable all-day slot
                    height="auto"
                    contentHeight="400px"
                    eventClick={handleSelectSlot}
                    datesSet={(dateInfo) => {
                      const start = new Date(dateInfo.start);
                      start.setHours(0, 0, 0, 0);
                      if (start > currentWeekStart) setCurrentWeekStart(start);
                    }}
                    customButtons={{
                      prev: {
                        text: "Previous",
                        click: () => navigateWeek("prev"),
                      },
                      next: { text: "Next", click: () => navigateWeek("next") },
                    }}
                    headerToolbar={false} // Use custom nav
                  />
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
