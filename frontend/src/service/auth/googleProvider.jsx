"use client";

import { GoogleOAuthProvider } from "@react-oauth/google";

export const isGoogleAuthEnabled =
  process.env.REACT_APP_IS_GOOGLE_AUTH_ENABLED === "true";
export const googleClientId = process.env.REACT_APP_GOOGLE_CLIENT_ID;

function GoogleAuthProvider(props) {
  return isGoogleAuthEnabled && googleClientId ? (
    <GoogleOAuthProvider clientId={googleClientId}>
      {props.children}
    </GoogleOAuthProvider>
  ) : (
    props.children
  );
}

export default GoogleAuthProvider;
