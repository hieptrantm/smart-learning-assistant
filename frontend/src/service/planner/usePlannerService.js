import { useCallback, useMemo } from "react";
import useFetch from "../auth/useFetch";

const PLANNER_API_URL =
  process.env.REACT_APP_PLANNER_API_URL || "http://localhost:8005";

const plannerUrl = (path) => `${PLANNER_API_URL}${path}`;

/**
 * Service hooks for the Study Planner API (study-planner-api at /planner).
 */
export function usePlannerService() {
  const fetchWithAuth = useFetch();

  /** List all subjects for the current user */
  const getSubjects = useCallback(async () => {
    const res = await fetchWithAuth(plannerUrl("/subjects"));
    if (!res.ok) throw new Error("Failed to fetch subjects");
    return res.json();
  }, [fetchWithAuth]);

  /** Get a single subject detail */
  const getSubject = useCallback(async (subjectId) => {
    const res = await fetchWithAuth(plannerUrl(`/subjects/${subjectId}`));
    if (!res.ok) throw new Error("Failed to fetch subject");
    return res.json();
  }, [fetchWithAuth]);

  /** Update a subject */
  const updateSubject = useCallback(async (subjectId, data) => {
    const formData = new FormData();
    if (data.name != null) formData.append("name", data.name);
    if (data.emoji != null) formData.append("emoji", data.emoji);
    if (data.target_grade != null) formData.append("target_grade", String(data.target_grade));
    if (data.end_date !== undefined) formData.append("end_date", data.end_date || "");
    if (data.free_time != null) formData.append("free_time", JSON.stringify(data.free_time));

    const res = await fetchWithAuth(plannerUrl(`/subjects/${subjectId}`), {
      method: "PUT",
      body: formData,
    });
    if (!res.ok) throw new Error("Failed to update subject");
    return res.json();
  }, [fetchWithAuth]);

  /** Delete a subject */
  const deleteSubject = useCallback(async (subjectId) => {
    const res = await fetchWithAuth(plannerUrl(`/subjects/${subjectId}`), {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete subject");
    return res.json();
  }, [fetchWithAuth]);

  /** Check pipeline status (ingest + plan generation) */
  const getSubjectStatus = useCallback(async (subjectId) => {
    const res = await fetchWithAuth(plannerUrl(`/subjects/${subjectId}/status`));
    if (!res.ok) throw new Error("Failed to get status");
    return res.json();
  }, [fetchWithAuth]);

  /** Get generated study plan */
  const getStudyPlan = useCallback(async (subjectId) => {
    const res = await fetchWithAuth(plannerUrl(`/subjects/${subjectId}/plan`));
    if (!res.ok) throw new Error("Failed to get plan");
    return res.json();
  }, [fetchWithAuth]);

  /** Sync plan to Google Calendar */
  const syncCalendar = useCallback(async (subjectId, googleAuth) => {
    const payload = typeof googleAuth === "string"
      ? { google_access_token: googleAuth }
      : {
          google_access_token: googleAuth?.google_access_token,
          google_refresh_token: googleAuth?.google_refresh_token,
        };

    const res = await fetchWithAuth(plannerUrl(`/subjects/${subjectId}/sync-calendar`), {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to sync calendar");
    return res.json();
  }, [fetchWithAuth]);

  /** Get occupied time slots for the current user */
  const getOccupiedSlots = useCallback(async (userId, excludeSubjectId = null) => {
    let url = `/occupied-slots/${userId}`;
    if (excludeSubjectId) url += `?exclude_subject_id=${excludeSubjectId}`;
    const res = await fetchWithAuth(plannerUrl(url));
    if (!res.ok) throw new Error("Failed to get occupied slots");
    return res.json();
  }, [fetchWithAuth]);

  return useMemo(() => ({
    getSubjects,
    getSubject,
    updateSubject,
    deleteSubject,
    getSubjectStatus,
    getStudyPlan,
    syncCalendar,
    getOccupiedSlots,
  }), [
    getSubjects,
    getSubject,
    updateSubject,
    deleteSubject,
    getSubjectStatus,
    getStudyPlan,
    syncCalendar,
    getOccupiedSlots,
  ]);
}
