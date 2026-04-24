"use client";

import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./verify-email.css";
import { useAuthVerifyEmailService } from "../../service/auth/useAuthService";

export default function VerifyEmail() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(true);
  const authVerifyEmail = useAuthVerifyEmailService();

  useEffect(() => {
    const verify = async () => {
      const params = new URLSearchParams(window.location.search);
      const t = params.get("token");
      console.log("Token:", t);

      if (!t) {
        setStatus("Invalid or missing token");
        setLoading(false);
        return;
      }

      try {
        const res = await authVerifyEmail({ token: t });
        setInfo(res.message);
        setStatus("Email verified successfully!");
      } catch (error) {
        setStatus("Email verification failed: " + error.message);
      }

      setLoading(false);

      // Delay 2 seconds before navigating
      await new Promise((resolve) => setTimeout(resolve, 2000));
      navigate("/");
    };

    verify();
  }, [authVerifyEmail, navigate]);

  return (
    <div className="verify-email-container">
      {loading ? (
        <div className="verify-email-loading">
          <h2>Verifying your email...</h2>
        </div>
      ) : (
        <div className="verify-email-success">
          <h2>{status}</h2>
          <p>{info}</p>
          <p>Redirecting to home page...</p>
        </div>
      )}
    </div>
  );
}
