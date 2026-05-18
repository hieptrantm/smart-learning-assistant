"use client";

import { useAuthGoogleLoginService, useAuthGoogleLoginAccessTokenService } from "./useAuthService";
import { useAuthActions } from "./useAuth";
import { useAuthTokens } from "./useAuth";
import { useGoogleLogin, GoogleLogin } from "@react-oauth/google";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { setGoogleToken, getGoogleToken } from "./googleToken";

// ── Calendar-only token (fallback for email/password users) ──────────────────
/**
 * @param {(accessToken: string) => void} [onAfterSync] - Called after token is saved
 * @param {string} [hint] - Email hint to pre-select Google account
 */
export function useRequestCalendarToken(onAfterSync, hint) {
  return useGoogleLogin({
    scope: "https://www.googleapis.com/auth/calendar.events",
    flow: "implicit",
    ...(hint ? { hint } : {}),
    onSuccess: (tokenResponse) => {
      if (tokenResponse.access_token) {
        setGoogleToken({ google_access_token: tokenResponse.access_token });
        toast.success("Đã kết nối Google Calendar!");
        if (onAfterSync) onAfterSync(tokenResponse.access_token);
      }
    },
    onError: (err) => {
      if (err?.error === "access_denied") {
        toast("Bỏ qua Google Calendar — môn học vẫn sẽ được tạo.", { icon: "ℹ️" });
      } else {
        toast.error("Không thể kết nối Google Calendar.");
      }
    },
  });
}

// ── Combined Google Login + Calendar (one OAuth popup) ───────────────────────
/**
 * GoogleAuthWithCalendar: Replaces the old GoogleLogin button.
 * Requests both auth scopes AND calendar.events in a single implicit-flow popup.
 * - Saves the access_token as the calendar token immediately.
 * - Authenticates the user via /auth/google/login-access-token.
 */
export function GoogleAuthWithCalendar() {
  const { refreshUser } = useAuthActions();
  const authGoogleLoginAccessToken = useAuthGoogleLoginAccessTokenService();
  const navigate = useNavigate();

  const login = useGoogleLogin({
    scope: [
      "openid",
      "profile",
      "email",
      "https://www.googleapis.com/auth/calendar.events",
    ].join(" "),
    flow: "implicit",
    onSuccess: async (tokenResponse) => {
      if (!tokenResponse.access_token) return;

      try {
        // 1. Save calendar token right away
        setGoogleToken({ google_access_token: tokenResponse.access_token });

        // 2. Authenticate with our backend using the access_token
        await authGoogleLoginAccessToken(tokenResponse.access_token);

        // 3. Fetch full user profile
        await refreshUser();

        toast.success("Đăng nhập thành công! Google Calendar đã được kết nối.");
        navigate("/");
      } catch (error) {
        console.error("Google login error:", error);
        toast.error("Đăng nhập Google thất bại. Vui lòng thử lại!");
      }
    },
    onError: (err) => {
      if (err?.error !== "access_denied") {
        toast.error("Đăng nhập Google thất bại!");
      }
    },
  });

  return (
    <button
      onClick={() => login()}
      className="google-login-btn"
      type="button"
    >
      <svg width="18" height="18" viewBox="0 0 48 48" style={{ marginRight: 8 }}>
        <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
        <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
        <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
        <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
        <path fill="none" d="M0 0h48v48H0z"/>
      </svg>
      Đăng nhập với Google
    </button>
  );
}

// ── Legacy GoogleAuth (kept for reference / fallback) ────────────────────────
export default function GoogleAuth() {
  const { refreshUser } = useAuthActions();
  const { setTokensInfo } = useAuthTokens();
  const authGoogleLoginService = useAuthGoogleLoginService();
  const navigate = useNavigate();

  useEffect(() => {
    return () => {
      try {
        window.google?.accounts?.id?.cancel();
      } catch (e) {
        // ignore
      }
    };
  }, []);

  const onSuccess = async (tokenResponse) => {
    if (!tokenResponse.credential) return;

    try {
      const result = await authGoogleLoginService({
        id_token: tokenResponse.credential,
      });

      setTokensInfo({
        token: result.access_token,
        refreshToken: result.refresh_token,
        tokenExpires: result.expires_at,
      });

      await refreshUser();
      navigate("/");
    } catch (error) {
      console.error("Google login error:", error);
      toast.error("Đăng nhập Google thất bại. Vui lòng thử lại!");
    }
  };

  return (
    <GoogleLogin
      onSuccess={onSuccess}
      onError={() => {
        console.error("Google Login component error");
        toast.error("Đăng nhập Google thất bại!");
      }}
      locale="vi"
      size="large"
      width="350"
      logo_alignment="left"
      theme="outline"
      use_fedcm_for_prompt={false}
    />
  );
}
