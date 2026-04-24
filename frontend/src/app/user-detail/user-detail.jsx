import React, { useEffect, useState } from "react";
import "./user-detail.css";
import { useAuthGetMeService } from "../../service/auth/useAuthService.js";
import toast from "react-hot-toast";

export default function UserDetailPage() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const getMe = useAuthGetMeService();

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const userData = await getMe();
        setUser(userData);
      } catch (error) {
        console.error("Error fetching user data:", error);
      }
      setLoading(false);
    };
    fetchUser();
  }, [getMe]);

  console.log("User data:", user);

  if (loading) return <div>Loading...</div>;
  if (!user) return <div>No user found</div>;

  const disableVerify = user.email_verified === true;
  const disableSetPassword = user.has_password === true;

  const handleVerifyEmail = async () => {
    const res = await fetch("/api/auth/send-verification-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });

    if (res.ok) {
      toast.success("Verification email sent!");
    }
  };

  const handleSetPassword = () => {
    window.location.href = "/set-password";
  };

  return (
    <div className="user-container">
      <h2>User Details</h2>

      <div className="detail-row">
        <strong>Username:</strong> {user.username}
      </div>
      <div className="detail-row">
        <strong>Email:</strong> {user.email}
      </div>
      <div className="detail-row">
        <strong>Email Verified:</strong> {user.email_verified ? "Yes" : "No"}
      </div>
      <div className="detail-row">
        <strong>Provider:</strong> {user.provider}
      </div>
      <div className="detail-row">
        <strong>Last Login:</strong> {user.last_login || "Never"}
      </div>

      <button
        className="btn verify-btn"
        onClick={handleVerifyEmail}
        disabled={disableVerify}
      >
        {disableVerify ? "Email Already Verified" : "Verify Email"}
      </button>

      <button
        className="btn pwd-btn"
        onClick={handleSetPassword}
        disabled={disableSetPassword}
      >
        {disableSetPassword ? "Password Already Set" : "Set Password"}
      </button>
    </div>
  );
}
