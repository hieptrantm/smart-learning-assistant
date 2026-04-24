"use client"

import { useCallback } from "react";
import { getTokensInfo, setTokensInfo } from "../auth/token";

async function fetchWithAuth(url, options = {}) {
  let tokens = getTokensInfo();

  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");

  if (tokens?.tokenExpires && tokens.tokenExpires - 60000 <= Date.now()) {
    const res = await fetch(`/auth/refresh`, {
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

export function useGetDetectDetail() {
  return useCallback(async (detectId) => {
    const res = await fetchWithAuth(`/detect/detect-detail/${detectId}`, {
      method: "GET",
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Fetch detect detail failed: ${res.status} - ${errorText}`);
    }

    return res.json();
  }, []);
}


export function useCreateDetect() {
    return useCallback(async (data) => {
        const res = await fetchWithAuth(`/detect/detect-detail`, {
            method: "POST",
            body: JSON.stringify(data),
        });
        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`Create detect failed: ${res.status} - ${errorText}`);
        }
        return res.json();
    }, []);
}

export function useGetUserDetects() {
    return useCallback(async (userId, offset = 0, limit = 10) => {
        const res = await fetchWithAuth(`/detect/user/${userId}?offset=${offset}&limit=${limit}`, {
            method: "GET",
        });
        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`Fetch user detects failed: ${res.status} - ${errorText}`);
        }
        return res.json();
    }, []);
}

export function useGetDetectsByDate() {
    return useCallback(async (userId, startDate = null, endDate = null, offset = 0, limit = 10) => {
        let url = `/detect/user/${userId}/by-date?offset=${offset}&limit=${limit}`;
        
        if (startDate) {
            url += `&start_date=${startDate}`;
        }
        if (endDate) {
            url += `&end_date=${endDate}`;
        }
        
        const res = await fetchWithAuth(url, {
            method: "GET",
        });
        
        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`Fetch detects by date failed: ${res.status} - ${errorText}`);
        }
        
        return res.json();
    }, []);
}