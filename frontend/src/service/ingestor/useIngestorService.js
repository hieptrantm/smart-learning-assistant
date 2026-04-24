import { useCallback, useMemo } from "react";
import useFetch from "../auth/useFetch";

const INGESTOR_API_URL =
  process.env.REACT_APP_INGESTOR_API_URL || "http://localhost:8005";

const ingestorUrl = (path) => `${INGESTOR_API_URL}${path}`;

/**
 * Service hooks for the Data Ingestor API (data-ingestor service).
 * Handles full subject CRUD + PDF ingest pipeline.
 */
export function useIngestorService() {
  const fetchWithAuth = useFetch();

  // ── Subject CRUD ─────────────────────────────────────────────

  /** List all subjects for the current user */
  const getSubjects = useCallback(async () => {
    const res = await fetchWithAuth(ingestorUrl("/subjects"));
    if (!res.ok) throw new Error("Failed to fetch subjects");
    return res.json();
  }, [fetchWithAuth]);

  /**
   * Create a new subject + start background ingest pipeline.
   * @param {Object} data - { name, emoji, target_grade, end_date, free_time, file, google_access_token, google_refresh_token }
   */
  const createSubject = useCallback(async (data) => {
    const formData = new FormData();
    formData.append("name", data.name);
    formData.append("emoji", data.emoji || "📚");
    formData.append("target_grade", String(data.target_grade || 7));
    if (data.end_date) formData.append("end_date", data.end_date);
    formData.append("free_time", JSON.stringify(data.free_time || {}));
    if (data.file) formData.append("file", data.file);
    if (data.google_access_token) formData.append("google_access_token", data.google_access_token);
    console.log("createSubject - google_access_token:", data.google_access_token);
    if (data.google_refresh_token) formData.append("google_refresh_token", data.google_refresh_token);

    const res = await fetchWithAuth(ingestorUrl("/subjects"), {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || "Failed to create subject");
    }
    return res.json();
  }, [fetchWithAuth]);

  /** Update subject info (name, emoji, target_grade, end_date, free_time) */
  const updateSubject = useCallback(async (subjectId, data) => {
    const formData = new FormData();
    if (data.name != null) formData.append("name", data.name);
    if (data.emoji != null) formData.append("emoji", data.emoji);
    if (data.target_grade != null) formData.append("target_grade", String(data.target_grade));
    if (data.end_date !== undefined) formData.append("end_date", data.end_date || "");
    if (data.free_time != null) formData.append("free_time", JSON.stringify(data.free_time));

    const res = await fetchWithAuth(ingestorUrl(`/subjects/${subjectId}`), {
      method: "PUT",
      body: formData,
    });
    if (!res.ok) throw new Error("Failed to update subject");
    return res.json();
  }, [fetchWithAuth]);

  // ── Raw ingest endpoints ─────────────────────────────────────

  /**
   * Upload & ingest a PDF asynchronously (no subject metadata).
   * Returns immediately with a job_id; use getIngestStatus() to poll.
   * @param {Object} data - { file: File, subject: string, language?: string }
   */
  const ingest = useCallback(async ({ file, subject, language }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("subject", subject);
    if (language) formData.append("language", language);

    const res = await fetchWithAuth(ingestorUrl("/ingest"), {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || "Failed to start ingestion");
    }
    return res.json();
  }, [fetchWithAuth]);

  /**
   * Upload & ingest a PDF synchronously (waits for full pipeline to finish).
   * @param {Object} data - { file: File, subject: string, language?: string }
   */
  const ingestSync = useCallback(async ({ file, subject, language }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("subject", subject);
    if (language) formData.append("language", language);

    const res = await fetchWithAuth(ingestorUrl("/ingest/sync"), {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || "Ingestion failed");
    }
    return res.json();
  }, [fetchWithAuth]);

  return useMemo(() => ({
    // Subject CRUD
    getSubjects,
    createSubject,
    updateSubject,
    // Raw ingest
    ingest,
    ingestSync,
  }), [getSubjects, createSubject, updateSubject, ingest, ingestSync]);
}

