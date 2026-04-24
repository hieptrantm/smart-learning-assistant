"use client";

import { useMemo } from "react";
import { getTokensInfo, setTokensInfo } from "./token";

function useFetch() {
  async function fetchWithAuth(input, init = {}) {
    let tokens = getTokensInfo();

    let headers = {
      ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
    };

    if (tokens?.token) {
      headers.Authorization = `Bearer ${tokens.token}`;
    }

    if (tokens?.tokenExpires && tokens.tokenExpires - 60000 <= Date.now()) {
      const res = await fetch('/auth/refresh', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          refresh_token: tokens.refreshToken,
        }),
      });

      if (res.ok) {
        const newTokens = await res.json();
        tokens = {
          token: newTokens.access_token || newTokens.token,
          refreshToken: newTokens.refresh_token || newTokens.refreshToken,
          tokenExpires: newTokens.expires_at || newTokens.tokenExpires,
        };
        setTokensInfo(tokens);
        headers.Authorization = `Bearer ${tokens.token}`;
      } else {
        setTokensInfo(null);
        throw new Error("Token refresh failed");
      }
    }

    return fetch(input, {
      ...init,
      headers: {
        ...headers,
        ...init.headers,
      },
    });
  }

  return useMemo(() => fetchWithAuth, []);
}

export default useFetch;
