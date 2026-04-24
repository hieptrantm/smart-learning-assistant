"use client";

import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthChangePasswordService } from "../../service/auth/useAuthService.js";
import "./forgot-password.css";

export default function ForgotPassword() {
  const navigate = useNavigate();
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [errors, setErrors] = useState({});
  const authPassword = useAuthChangePasswordService();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get("token");
    console.log("Token:", t);
    if (!t) {
      setStatus("Invalid or missing token");
    } else {
      setToken(t);
    }
  }, []);

  const validatePassword = (pwd) => {
    const errors = {};

    if (pwd.length < 8) {
      errors.length = "Password must be at least 8 characters";
    }
    if (!/[A-Za-z]/.test(pwd)) {
      errors.letter = "Password must contain at least one letter";
    }
    if (!/\d/.test(pwd)) {
      errors.number = "Password must contain at least one number";
    }

    return errors;
  };

  const handlePasswordChange = (e) => {
    const newPassword = e.target.value;
    setPassword(newPassword);

    if (newPassword) {
      setErrors(validatePassword(newPassword));
    } else {
      setErrors({});
    }
  };

  const submit = async (e) => {
    e.preventDefault();

    if (!password || !confirm) {
      setStatus("Please fill out all fields");
      return;
    }

    const validationErrors = validatePassword(password);
    if (Object.keys(validationErrors).length > 0) {
      setStatus("Please fix password requirements");
      return;
    }

    if (password !== confirm) {
      setStatus("Passwords do not match");
      return;
    }

    setLoading(true);
    setStatus("");

    try {
      const res = await authPassword({ password: password, token: token });

      console.log(res);

      if (res.ok) {
        setStatus("Password set successfully! You can now log in.");
        setTimeout(() => navigate("/"), 2000);
      } else {
        const err = await res.json();
        setStatus(err.detail || "Error setting password");
      }
    } catch {
      setStatus("Network error");
    }

    setLoading(false);
  };

  const getRequirementClass = (requirementMet) => {
    if (!password) return "requirement";
    return requirementMet ? "requirement met" : "requirement unmet";
  };

  return (
    <div className="set-password-container">
      <div className="set-password-card">
        <div className="icon-container">
          <span className="icon">🔐</span>
        </div>

        <h2 className="title">Set Your Password</h2>
        <p className="subtitle">
          Create a strong password to secure your account
        </p>

        {status && (
          <div
            className={`status ${
              status.includes("successfully") ? "success" : "error"
            }`}
          >
            {status}
          </div>
        )}

        <form onSubmit={submit} className="form">
          <div className="input-group">
            <label className="label">New Password</label>
            <input
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={handlePasswordChange}
              className={`input ${
                password && Object.keys(errors).length > 0 ? "invalid" : ""
              }`}
            />
          </div>

          {password && (
            <div className="requirements">
              <p className="requirements-title">Password must contain:</p>
              <div className={getRequirementClass(!errors.length)}>
                <span className="checkmark">{!errors.length ? "✓" : "○"}</span>
                At least 8 characters
              </div>
              <div className={getRequirementClass(!errors.letter)}>
                <span className="checkmark">{!errors.letter ? "✓" : "○"}</span>
                At least one letter
              </div>
              <div className={getRequirementClass(!errors.number)}>
                <span className="checkmark">{!errors.number ? "✓" : "○"}</span>
                At least one number
              </div>
            </div>
          )}

          <div className="input-group">
            <label className="label">Confirm Password</label>
            <input
              type="password"
              placeholder="Confirm your password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className={`input ${
                confirm && password !== confirm ? "invalid" : ""
              }`}
            />
            {confirm && password !== confirm && (
              <p className="error-text">Passwords do not match</p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading || !token || Object.keys(errors).length > 0}
            className="button"
          >
            {loading ? (
              <>
                <span className="spinner"></span>
                Changing Password...
              </>
            ) : (
              "Change Password"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
