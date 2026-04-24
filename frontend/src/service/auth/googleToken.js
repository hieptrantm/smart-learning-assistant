import Cookies from "js-cookie";

const COOKIE_KEY = "google-calendar-token";

/**
 * Get the stored Google Calendar access token info.
 * @returns {{ google_access_token: string } | null}
 */
export function getGoogleToken() {
  try {
    return JSON.parse(Cookies.get(COOKIE_KEY) ?? "null");
  } catch {
    return null;
  }
}

/**
 * Persist Google Calendar token info to a cookie.
 * @param {{ google_access_token: string } | null} data
 */
export function setGoogleToken(data) {
  if (data) {
    // Google access token expires in ~1 hour, store for 55 minutes
    Cookies.set(COOKIE_KEY, JSON.stringify(data), {
      sameSite: "strict",
      expires: 55 / (60 * 24), // 55 minutes in days
      secure: window.location.protocol === "https:",
    });
  } else {
    Cookies.remove(COOKIE_KEY);
  }
}
