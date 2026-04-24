"use client";

import { useAuthGoogleLoginService } from "./useAuthService";
import { useAuthActions } from "./useAuth";
import { useAuthTokens } from "./useAuth";
import { useGoogleLogin, GoogleLogin } from "@react-oauth/google";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { setGoogleToken } from "./googleToken";

export function useRequestCalendarToken() {
  return useGoogleLogin({
    scope: "https://www.googleapis.com/auth/calendar.events",
    flow: "implicit",
    onSuccess: (tokenResponse) => {
      if (tokenResponse.access_token) {
        setGoogleToken({ google_access_token: tokenResponse.access_token });
        toast.success("Đã kết nối Google Calendar!");
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

export default function GoogleAuth() {
  const { refreshUser } = useAuthActions();
  const { setTokensInfo } = useAuthTokens();
  const authGoogleLoginService = useAuthGoogleLoginService();
  const navigate = useNavigate();

  // Cancel any pending Google prompts on unmount to prevent stale state
  useEffect(() => {
    return () => {
      try {
        window.google?.accounts?.id?.cancel();
      } catch (e) {
        // ignore
      }
    };
  }, []);

  // Step 2 (optional): request Calendar access token silently after login.
  // Uses implicit flow with calendar scope – only runs after the user is
  // already authenticated so it won't block the main sign-in flow.
  const requestCalendarToken = useGoogleLogin({
    scope: "https://www.googleapis.com/auth/calendar",
    flow: "implicit",
    prompt: "none", // silent – no extra consent screen if already granted
    onSuccess: (tokenResponse) => {
      if (tokenResponse.access_token) {
        setGoogleToken({ google_access_token: tokenResponse.access_token });
      }
    },
    onError: () => {
      // Calendar access not granted – that's fine, the token just won't be used
    },
  });

  const onSuccess = async (tokenResponse) => {
    if (!tokenResponse.credential) return;

    try {
      const result = await authGoogleLoginService({
        id_token: tokenResponse.credential,
      });

      // Set tokens via context (this also persists to cookie)
      setTokensInfo({
        token: result.access_token,
        refreshToken: result.refresh_token,
        tokenExpires: result.expires_at,
      });

      // Fetch full user profile from /auth/me
      await refreshUser();

      // Silently try to get a Calendar token in the background
      try {
        requestCalendarToken();
      } catch (_) {
        // non-critical
      }

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
