"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import "./sidebar.css";
import { X } from "lucide-react";
import { useGetDetectsByDate } from "../../service/user/useDetectService";

const Sidebar = ({ sidebarOpen, setSidebarOpen, userId }) => {
  const navigate = useNavigate();
  const [detections, setDetections] = useState([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const observerTarget = useRef(null);

  const getUserDetects = useGetDetectsByDate();

  const encodeId = (id) => {
    const SECRET = 12345;
    return (id ^ SECRET).toString(36);
  };

  const handleDetectionClick = (detectId) => {
    const encodedId = encodeId(detectId);
    navigate(`/detection/${encodedId}`);
  };

  const fetchDetections = useCallback(
    async (pageNum) => {
      if (!userId) return;
      setLoading(true);

      try {
        const offset = (pageNum - 1) * 10;
        const limit = 10;

        const response = await getUserDetects(
          userId,
          null,
          null,
          offset,
          limit
        );

        const newDetections = response.detects.map((detect) => ({
          id: detect.id,
          date: new Date(detect.created_at || detect.date).toLocaleDateString(
            "en-US",
            {
              month: "long",
              day: "numeric",
              year: "numeric",
            }
          ),
          time: new Date(detect.created_at || detect.date).toLocaleTimeString(
            "en-US",
            {
              hour: "numeric",
              minute: "2-digit",
              hour12: true,
            }
          ),
        }));

        setDetections((prev) => {
          const existingIds = new Set(prev.map((d) => d.id));
          const uniqueNew = newDetections.filter((d) => !existingIds.has(d.id));
          return [...prev, ...uniqueNew];
        });

        // Check if there are more results
        if (newDetections.length < limit) {
          setHasMore(false);
        }
      } catch (error) {
        console.error("Error fetching detections:", error);
      } finally {
        setLoading(false);
      }
    },
    [getUserDetects, userId]
  );

  // Reset state when userId changes
  useEffect(() => {
    if (sidebarOpen && userId) {
      setDetections([]);
      setPage(1);
      setHasMore(true);
      setLoading(false);
    }
  }, [sidebarOpen, userId]);

  // Initial load
  useEffect(() => {
    if (sidebarOpen && page === 1 && userId) {
      fetchDetections(1);
    }
  }, [sidebarOpen, page, fetchDetections, userId]);

  // Intersection Observer for infinite scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading && userId) {
          setPage((prev) => prev + 1);
        }
      },
      { threshold: 1.0 }
    );

    const currentTarget = observerTarget.current;
    if (currentTarget) {
      observer.observe(currentTarget);
    }

    return () => {
      if (currentTarget) {
        observer.unobserve(currentTarget);
      }
    };
  }, [hasMore, loading, userId]);

  // Fetch more data when page changes
  useEffect(() => {
    if (page > 1 && userId) {
      fetchDetections(page);
    }
  }, [page, fetchDetections, userId]);

  return (
    <div className={`sidebar ${sidebarOpen ? "open" : "closed"}`}>
      <div className="sidebar-content">
        <div className="sidebar-header">
          <h2 className="sidebar-title">Detections</h2>
          <button
            onClick={() => setSidebarOpen(false)}
            className="close-button"
          >
            <X size={24} />
          </button>
        </div>

        <div className="sidebar-body">
          {!userId ? (
            <div className="empty-state">Please log in to view detections</div>
          ) : detections.length === 0 && !loading ? (
            <div className="empty-state">No detections found</div>
          ) : (
            <>
              {detections.map((detection) => (
                <button
                  key={detection.id}
                  onClick={() => handleDetectionClick(detection.id)}
                  className="detection-button"
                >
                  <div className="detection-info">
                    <div className="detection-id">
                      {detection.date} — {detection.time}
                    </div>
                    <div className="detection-id">
                      Detection #{detection.id}
                    </div>
                  </div>
                </button>
              ))}

              {loading && (
                <div className="loading-container">
                  <div className="loading-spinner"></div>
                  <span>Loading more detections...</span>
                </div>
              )}

              {!hasMore && detections.length > 0 && (
                <div className="end-message">No more detections</div>
              )}

              <div ref={observerTarget} style={{ height: "20px" }} />
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default Sidebar;
