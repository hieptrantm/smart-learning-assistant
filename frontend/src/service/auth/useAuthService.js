"use client";

import { useCallback } from "react";
import { getTokensInfo, setTokensInfo } from "./token";

const AUTH_SERVICE_URL =
  process.env.REACT_APP_AUTH_SERVICE_URL || "http://localhost:8001";
const authUrl = (path) => `${AUTH_SERVICE_URL}${path}`;

async function fetchWithAuth(url, options = {}) {
  let tokens = getTokensInfo();

  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");

  if (tokens?.tokenExpires && tokens.tokenExpires - 60000 <= Date.now()) {
    const res = await fetch(authUrl("/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: tokens.refreshToken }),
    });

    if (res.ok) {
      const newTokens = await res.json();
      tokens = {
        token: newTokens.access_token,
        refreshToken: newTokens.refresh_token,
        tokenExpires: newTokens.expires_at,
      };
      setTokensInfo(tokens);
    } else {
      setTokensInfo(null);
      throw new Error("Session expired");
    }
  }

  if (tokens?.token) {
    headers.set("Authorization", `Bearer ${tokens.token}`);
  }

  const response = await fetch(url, { ...options, headers });
  return response;
}

export function useAuthLoginService() {
  return useCallback(async (data) => {
    const res = await fetch(authUrl("/auth/login"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    if (!res.ok) throw new Error("Login failed");
    const result = await res.json();

    setTokensInfo({
      token: result.access_token,
      refreshToken: result.refresh_token,
      tokenExpires: result.expires_at,
    });

    return result;
  }, []);
}

export function useAuthSignUpService() {
  return useCallback(async (data) => {
    const res = await fetch(authUrl("/auth/login"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    if (!res.ok) throw new Error("Register failed");
    return res.json();
  }, []);
}

export function useAuthGetMeService() {
  return useCallback(async () => {
    const res = await fetchWithAuth(`/auth/me`);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Failed to fetch user: ${res.status} ${text}`);
    }
    return res.json();
  }, []);
}

export function useAuthPatchMeService() {
  return useCallback(async (data) => {
    const res = await fetchWithAuth(`/auth/me`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Update failed");
    return res.json();
  }, []);
}

export function useAuthLogoutService() {
  return useCallback(async () => {
    await fetchWithAuth(`/auth/logout`, { method: "POST" });
    setTokensInfo(null);
  }, []);
}

export function useAuthConfirmEmailService() {
  return useCallback(async (data) => {
    const res = await fetch(authUrl("/auth/email/confirm"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Email confirmation failed");
    return res.json();
  }, []);
}

export function useAuthConfirmNewEmailService() {
  return useCallback(async (data) => {
    const res = await fetch(authUrl("/auth/email/confirm/new"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("New email confirmation failed");
    return res.json();
  }, []);
}

export function useAuthGoogleLoginService() {
  return useCallback(async (data) => {
    const res = await fetch(authUrl("/auth/google/login"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      const errorText = await res.text().catch(() => "Unknown error");
      console.error(`Google login failed: ${res.status} ${errorText}`);
      throw new Error(`Google login failed: ${res.status}`);
    }
    const result = await res.json();

    setTokensInfo({
      token: result.access_token,
      refreshToken: result.refresh_token,
      tokenExpires: result.expires_at,
    });

    return result;
  }, []);
}

export function useAuthForgotPassword() {
  return useCallback(async (data) => {
    const res = await fetch(authUrl("/auth/forgot-password"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Forgot password request failed");
    return res.json();
  }, []);
}

export function useAuthSetPasswordService() {
  return useCallback(async (data) => {
    const res = await fetch(authUrl("/auth/set-password"), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Password reset failed");
    return res;
  }, []);
}

export function useAuthChangePasswordService() {
  return useCallback(async (data) => {
    const res = await fetch(authUrl("/auth/change-password"), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Password change failed");
    return res;
  }, []);
}

export function useAuthRequestPasswordChangeService() {
  return useCallback(async () => {
    const res = await fetchWithAuth(`/auth/request-change-password-email`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Set password failed");
    return res;
  }, []);
}

export function useAuthVerifyEmailService() {
  return useCallback(async (data) => {
    const res = await fetchWithAuth(`/auth/verify-email`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Email verification failed");
    return res.json();
  }, []);
}

export function useAuthRequestEmailVerificationService() {
  return useCallback(async (data) => {
    const res = await fetchWithAuth(`/auth/send-verification`, {
      method: "POST",
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Email verification request failed");
    return res.json();
  }, []);
}

export function useTestEmail() {
  return useCallback(async (data) => {
    const res = await fetch(authUrl("/auth/test-email"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Test email sending failed");
    return res;
  }, []);
}
