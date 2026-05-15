"use client";

import { GoogleOAuthProvider } from "@react-oauth/google";

export const isGoogleAuthEnabled =
  process.env.REACT_APP_IS_GOOGLE_AUTH_ENABLED === "true";
export const googleClientId = process.env.REACT_APP_GOOGLE_CLIENT_ID;

const FALLBACK_CLIENT_ID = "placeholder";

function GoogleAuthProvider(props) {
  return (
    <GoogleOAuthProvider clientId={googleClientId || FALLBACK_CLIENT_ID}>
      {props.children}
    </GoogleOAuthProvider>
  );
}

export default GoogleAuthProvider;
