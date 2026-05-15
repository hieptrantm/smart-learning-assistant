"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AuthActionsContext,
  AuthContext,
  AuthTokensContext,
} from "./authContext";
import useFetch from "./useFetch.js";
import {
  getTokensInfo,
  setTokensInfo as setTokensInfoToStorage,
} from "./token.js";
import { setGoogleToken } from "./googleToken.js";

const AUTH_SERVICE_URL =
  process.env.REACT_APP_AUTH_SERVICE_URL || "http://localhost:8005";
const authUrl = (path) => `${AUTH_SERVICE_URL}${path}`;

// enum HTTP_CODES_ENUM {
//   OK = 200,
//   CREATED = 201,
//   ACCEPTED = 202,
//   NO_CONTENT = 204,
//   BAD_REQUEST = 400,
//   UNAUTHORIZED = 401,
//   FORBIDDEN = 403,
//   NOT_FOUND = 404,
//   UNPROCESSABLE_ENTITY = 422,
//   INTERNAL_SERVER_ERROR = 500,
//   SERVICE_UNAVAILABLE = 503,
//   GATEWAY_TIMEOUT = 504,
// }

function AuthProvider(props) {
  const [isLoaded, setIsLoaded] = useState(false);
  const [user, setUser] = useState(null);
  const fetchBase = useFetch();

  const setTokensInfo = useCallback((tokensInfo) => {
    setTokensInfoToStorage(tokensInfo);

    if (!tokensInfo) {
      setUser(null);
      setGoogleToken(null);
    }
  }, []);

  const logOut = useCallback(async () => {
    const tokens = getTokensInfo();

    if (tokens?.token) {
      await fetchBase(authUrl("/auth/logout"), {
        method: "POST",
      });
    }
    setTokensInfo(null);

    // Clear Google Identity Services session to prevent stale credentials on re-login
    try {
      window.google?.accounts?.id?.disableAutoSelect();
    } catch (e) {
      // ignore if Google SDK not loaded
    }
  }, [setTokensInfo, fetchBase]);

  const loadData = useCallback(async () => {
    const tokens = getTokensInfo();

    try {
      if (tokens?.token) {
        const response = await fetchBase(authUrl("/auth/me"), {
          method: "GET",
        });

        if (response.status === 401) {
          logOut();
          return;
        }

        const data = await response.json();
        console.log("User data loaded:", data);
        setUser(data);
      }
    } finally {
      setIsLoaded(true);
    }
  }, [fetchBase, logOut]);

  const refreshUser = useCallback(async () => {
    const tokens = getTokensInfo();
    if (!tokens?.token) return;

    try {
      const response = await fetchBase(authUrl("/auth/me"), { method: "GET" });
      if (response.status === 401) {
        logOut();
        return;
      }

      const data = await response.json();
      console.log("User refreshed:", data);
      setUser(data);
    } catch (err) {
      console.error("Failed to refresh user:", err);
    }
  }, [fetchBase, logOut]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const contextValue = useMemo(
    () => ({
      isLoaded,
      user,
    }),
    [isLoaded, user]
  );

  const contextActionsValue = useMemo(
    () => ({
      setUser,
      logOut,
      refreshUser,
    }),
    [logOut, refreshUser]
  );

  const contextTokensValue = useMemo(
    () => ({
      setTokensInfo,
    }),
    [setTokensInfo]
  );

  return (
    <AuthContext.Provider value={contextValue}>
      <AuthActionsContext.Provider value={contextActionsValue}>
        <AuthTokensContext.Provider value={contextTokensValue}>
          {props.children}
        </AuthTokensContext.Provider>
      </AuthActionsContext.Provider>
    </AuthContext.Provider>
  );
}

export default AuthProvider;
