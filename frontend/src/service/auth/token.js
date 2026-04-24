import Cookies from "js-cookie";

export function getTokensInfo() {
  try {
    return JSON.parse(Cookies.get('auth-token-data') ?? "null");
  } catch {
    return null;
  }
}

export function setTokensInfo(tokens) {
  if (tokens) {
    Cookies.set('auth-token-data', JSON.stringify(tokens), {
      sameSite: "strict",
      expires: 30, // 30 days (matches refresh token)
      secure: window.location.protocol === "https:",
    });
  } else {
    Cookies.remove('auth-token-data');
  }
}