import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useGetDetectsByDate } from "../../service/user/useDetectService";
import "./history.css";

const History = ({ userId }) => {
  const navigate = useNavigate();
  const [currentDate, setCurrentDate] = useState(new Date());
  const [expandedDay, setExpandedDay] = useState(null);
  const getUserDetects = useGetDetectsByDate();
  const [requests, setRequests] = useState({});

  const encodeId = (id) => {
    const SECRET = 12345;
    return (id ^ SECRET).toString(36);
  };

  const handleDetectionClick = (detectId) => {
    const encodedId = encodeId(detectId);
    navigate(`/detection/${encodedId}`);
  };

  useEffect(() => {
    const fetchData = async () => {
      const monthsAgo = new Date(currentDate);
      monthsAgo.setMonth(currentDate.getMonth() - 2);

      const monthsAhead = new Date(currentDate);
      monthsAhead.setMonth(currentDate.getMonth() + 2);

      const fetch_requests = await getUserDetects(
        userId,
        monthsAgo.toISOString().split("T")[0],
        monthsAhead.toISOString().split("T")[0],
        0,
        1000
      );

      // ✅ GROUP BY DATE HERE
      const grouped = {};

      fetch_requests.detects.forEach((item) => {
        const date = new Date(item.created_at);
        const key = `${date.getFullYear()}-${
          date.getMonth() + 1
        }-${date.getDate()}`;

        if (!grouped[key]) {
          grouped[key] = [];
        }

        grouped[key].push(item);
      });

      setRequests(grouped);

      console.log("✅ Grouped Requests:", grouped);
    };

    fetchData();
  }, [currentDate, userId]);

  const demo_requests = {
    "2025-8-1": [
      { time: "10:24", title: "Chicken" },
      { time: "10:40", title: "Beef" },
      { time: "11:30", title: "Potato" },
      { time: "14:15", title: "Fish" },
      { time: "15:30", title: "Salad" },
    ],
    "2025-8-5": [
      { time: "09:00", title: "Meeting" },
      { time: "11:30", title: "Lunch" },
    ],
    "2025-8-12": [
      { time: "10:00", title: "Review" },
      { time: "14:00", title: "Planning" },
      { time: "16:00", title: "Call" },
    ],
    "2025-8-20": [{ time: "08:30", title: "Breakfast" }],
    "2025-7-15": [{ time: "12:00", title: "July Event" }],
  };

  const getDaysInMonth = (date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    return { firstDay, daysInMonth };
  };

  const { firstDay, daysInMonth } = getDaysInMonth(currentDate);
  const monthNames = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];

  const navigateMonth = (direction) => {
    setCurrentDate(
      new Date(currentDate.getFullYear(), currentDate.getMonth() + direction, 1)
    );
    setExpandedDay(null);
  };

  const renderRequests = (day, isExpanded) => {
    const dateKey = `${currentDate.getFullYear()}-${
      currentDate.getMonth() + 1
    }-${day}`;
    const dayRequests = requests[dateKey] || [];
    if (dayRequests.length === 0) return null;

    console.log("Rendering requests for", dateKey, dayRequests);

    const maxVisible = isExpanded ? dayRequests.length : 3;
    const visibleRequests = dayRequests.slice(0, maxVisible);
    const hasMore = dayRequests.length > maxVisible;

    return (
      <div className={`requests-container ${isExpanded ? "expanded" : ""}`}>
        {visibleRequests.map((req, idx) => (
          <div key={idx} className="request-item">
            <button
              onClick={() => handleDetectionClick(req.id)}
              className="request-button"
            >
              {req.created_at} - {req.recommendation}
            </button>
          </div>
        ))}
        {hasMore && !isExpanded && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setExpandedDay(day);
            }}
            className="more-button"
          >
            ...
          </button>
        )}
      </div>
    );
  };

  const renderCalendar = () => {
    const days = [];
    const totalCells = Math.ceil((firstDay + daysInMonth) / 7) * 7;

    for (let i = 0; i < totalCells; i++) {
      const dayNumber = i - firstDay + 1;
      const isValidDay = dayNumber > 0 && dayNumber <= daysInMonth;
      const isExpanded = expandedDay === dayNumber;

      days.push(
        <div
          key={i}
          className={`calendar-day ${isValidDay ? "valid" : "invalid"} ${
            isExpanded ? "expanded" : ""
          }`}
          onClick={() => {
            if (isExpanded) setExpandedDay(null);
          }}
        >
          {isValidDay && (
            <>
              <div className={`day-number ${isExpanded ? "expanded" : ""}`}>
                {dayNumber}
              </div>
              {renderRequests(dayNumber, isExpanded)}
            </>
          )}
        </div>
      );
    }

    return days;
  };

  return (
    <div className="calendar-app">
      <div className="main-content">
        <div className="content-wrapper">
          <div className="calendar-container">
            <div className="calendar-header">
              <button onClick={() => navigateMonth(-1)} className="nav-button">
                <ChevronLeft size={20} />
              </button>
              <h1 className="calendar-title">
                {monthNames[currentDate.getMonth()]} {currentDate.getFullYear()}
              </h1>
              <button onClick={() => navigateMonth(1)} className="nav-button">
                <ChevronRight size={20} />
              </button>
            </div>

            <div className="calendar-grid">
              {[
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
              ].map((day) => (
                <div key={day} className="day-header">
                  {day}
                </div>
              ))}

              {renderCalendar()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default History;
