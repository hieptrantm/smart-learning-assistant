"use client";

import { createContext } from "react";

// User = {
//   id: string;
//   email: string;
//   provider?: UserProviderEnum;
// };

// Token = {
//   token: string;
//   refreshToken: string;
//   tokenExpires: number;
// };

export const AuthContext = createContext({
  user: null,
  isLoaded: true,
});

export const AuthActionsContext = createContext({
  setUser: () => {},
  logOut: async () => {},
  refreshUser: async () => {},
});

export const AuthTokensContext = createContext({
  setTokensInfo: () => {},
});
