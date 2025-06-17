// src/components/AppointmentBookingModal.js
import { useState, useEffect } from "react";

export default function AppointmentBookingModal({ onClose, company }) {
  const [slots, setSlots] = useState([]);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [formData, setFormData] = useState({ name: "", email: "", notes: "" });
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchSlots = async () => {
      const token = localStorage.getItem("authToken");
      if (!token) {
        setError("Please log in to book an appointment.");
        return;
      }
      try {
        const res = await fetch(
          `https://leadspilotai.onrender.com/api/admin/calendar/slots?company=${company}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        if (!res.ok) throw new Error("Failed to fetch slots");
        const data = await res.json();
        setSlots(data.slots || []);
      } catch (err) {
        setError("Could not load available slots. Try again later.");
      }
    };
    fetchSlots();
  }, [company]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const token = localStorage.getItem("authToken");
    if (!token) {
      setError("Please log in to book an appointment.");
      return;
    }
    try {
      const res = await fetch(
        "https://leadspilotai.onrender.com/api/admin/calendar/book",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ slot: selectedSlot, ...formData, company }),
        }
      );
      const data = await res.json();
      if (data.success) {
        setStatus("success");
      } else {
        setError(data.error || "Booking failed. Try again.");
      }
    } catch (err) {
      setError("Booking failed. Try again later.");
    }
  };

  if (error) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
        <div className="bg-white p-6 rounded-lg shadow-lg w-96">
          <p className="text-red-600">{error}</p>
          <button
            onClick={() => onClose(null)}
            className="mt-4 text-blue-600 underline"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
      <div className="bg-white p-6 rounded-lg shadow-lg w-96">
        <h2 className="text-xl font-bold text-blue-600 mb-4">
          Book Appointment
        </h2>
        {!selectedSlot ? (
          <div>
            <h3 className="text-lg mb-2">Select a Slot</h3>
            {slots.length === 0 ? (
              <p className="text-gray-600">No slots available.</p>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {slots.map((slot) => (
                  <button
                    key={slot}
                    onClick={() => setSelectedSlot(slot)}
                    className="p-2 border border-blue-600 text-blue-600 rounded hover:bg-blue-100"
                  >
                    {new Date(slot).toLocaleString("en-US", {
                      weekday: "short",
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : !status ? (
          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label className="block text-sm font-medium">Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                className="w-full p-2 border rounded"
                required
              />
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium">Email</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
                className="w-full p-2 border rounded"
                required
              />
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium">Notes</label>
              <textarea
                value={formData.notes}
                onChange={(e) =>
                  setFormData({ ...formData, notes: e.target.value })
                }
                className="w-full p-2 border rounded"
              />
            </div>
            <button
              type="submit"
              className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700"
            >
              Book Now
            </button>
          </form>
        ) : (
          <div className="text-center">
            {status === "success" ? (
              <p className="text-green-600">Appointment booked!</p>
            ) : (
              <p className="text-red-600">Booking failed. Try again.</p>
            )}
            <button
              onClick={() => onClose(status)}
              className="mt-4 text-blue-600 underline"
            >
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
