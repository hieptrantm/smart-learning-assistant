"use client";

import "./navbar.css";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthActions } from "../../service/auth/useAuth";
import {
  useAuthRequestEmailVerificationService,
  useAuthRequestPasswordChangeService,
} from "../../service/auth/useAuthService";
import toast from "react-hot-toast";
import {
  GraduationCap,
  Home,
  MessageSquare,
  CalendarCheck,
  Upload,
  BarChart3,
  LogOut,
  Mail,
  ShieldCheck,
  KeyRound,
} from "lucide-react";

const Navbarr = ({ onTabChange, activeTab, user, isLoaded }) => {
  const { logOut } = useAuthActions();
  const navigate = useNavigate();
  const sendLinkPassword = useAuthRequestPasswordChangeService();
  const sendLinkEmailVerification = useAuthRequestEmailVerificationService();

  const handleSignUp = () => {
    navigate("/sign-up");
  };

  const handleSignIn = () => {
    navigate("/sign-in");
  };

  const handleLogout = async () => {
    await logOut();
    navigate("/");
  };

  const handleVerifyEmail = async () => {
    if (user?.email) {
      try {
        await sendLinkEmailVerification({
          email: user.email,
        });
        toast.success("Verification email sent!");
      } catch (error) {
        toast.error("Failed to send verification email: " + error.message);
      }
      return;
    }

    toast.error("User email not available");
  };

  const handleSetPassword = async () => {
    if (user?.email) {
      try {
        const res = await sendLinkPassword();
        if (!res.ok) {
          toast.error("Password set email fault");
          return;
        }

        toast.success("Password set email sent!");
      } catch (error) {
        toast.error("Error setting password: " + error.message);
      }
      return;
    }

    toast.error("User email not available");
  };

  const handleResetPassword = async () => {
    if (user?.email) {
      try {
        const res = await sendLinkPassword();
        if (!res.ok) {
          toast.error("Password reset email fault");
          return;
        }

        toast.success("Password reset email sent!");
      } catch (error) {
        toast.error("Failed to send password reset email: " + error.message);
      }
      return;
    }

    toast.error("User email not available");
  };

  const tabs = [
    { id: "Home", icon: <Home size={16} />, label: "Trang chủ" },
    { id: "Chatbot", icon: <MessageSquare size={16} />, label: "Chatbot" },
    { id: "Planner", icon: <CalendarCheck size={16} />, label: "Study Planner" },
    { id: "Import", icon: <Upload size={16} />, label: "Import" },
    { id: "Dashboard", icon: <BarChart3 size={16} />, label: "Dashboard" },
  ];

  const displayName = user?.username || user?.email || "User";
  const userHandle = user?.email || user?.username || "";
  const avatarInitials = useMemo(() => {
    const source = (user?.username || user?.email || "U").trim();
    const parts = source.split(/\s+/).filter(Boolean);

    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    }

    return source.slice(0, 2).toUpperCase();
  }, [user?.email, user?.username]);

  return (
    <nav className="header">
      <div className="header-title-btn">
        <div className="header-brand" onClick={() => onTabChange("Home")}>
          <img src="/sla_g.png" alt="SLA Logo" className="brand-logo" />
        </div>
        <div className="header-tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`tab ${activeTab === tab.id ? "tab-active" : ""}`}
              onClick={() => onTabChange(tab.id)}
            >
              <span className="tab-icon">{tab.icon}</span>
              <span className="tab-text">{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="header-actions">
        {!isLoaded ? (
          <div className="loading-indicator">Loading...</div>
        ) : user ? (
          <div className="dropdown user-menu">
            <button className="user-avatar-trigger" aria-label="User profile menu">
              {user.avatar_url ? (
                <img
                  src={user.avatar_url}
                  alt={displayName}
                  className="user-avatar-image"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <span className="user-avatar-fallback">{avatarInitials}</span>
              )}
            </button>

            <div className="dropdown-content user-card">
              <div className="user-card-header">
                <div className="user-card-avatar">
                  {user.avatar_url ? (
                    <img
                      src={user.avatar_url}
                      alt={displayName}
                      className="user-card-avatar-image"
                      referrerPolicy="no-referrer"
                    />
                  ) : (
                    <span className="user-avatar-fallback user-avatar-fallback-large">
                      {avatarInitials}
                    </span>
                  )}
                </div>

                <div className="user-card-heading">
                  <h3>{displayName}</h3>
                  <p>{userHandle}</p>
                </div>
              </div>

              <div className="user-card-details">
                <div className="detail-row">
                  <span className="detail-icon">
                    <Mail size={14} />
                  </span>
                  <div>
                    <strong>Email</strong>
                    <span id="email">{user.email}</span>
                  </div>
                </div>

                <div className="detail-row">
                  <span className="detail-icon">
                    <ShieldCheck size={14} />
                  </span>
                  <div>
                    <strong>Trạng thái email</strong>
                    <span id="email-verified">
                      {user.email_verified ? "Đã xác minh" : "Chưa xác minh"}
                    </span>
                  </div>
                </div>
              </div>

              {!user.email_verified && (
                <button
                  className="btn verify-btn"
                  id="verifyBtn"
                  onClick={handleVerifyEmail}
                >
                  Xác minh email
                </button>
              )}

              {user.has_password ? (
                <button
                  className="btn pwd-btn"
                  id="pwdBtn"
                  onClick={handleResetPassword}
                >
                  <KeyRound size={14} />
                  Đổi mật khẩu
                </button>
              ) : (
                <button
                  className="btn pwd-btn"
                  id="pwdBtn"
                  onClick={handleSetPassword}
                >
                  <KeyRound size={14} />
                  Đặt mật khẩu
                </button>
              )}

              <button className="btn logout-btn" onClick={handleLogout}>
                <LogOut size={14} />
                Đăng xuất
              </button>
            </div>
          </div>
        ) : (
          <>
            <button
              className="header-btn header-btn-outline"
              onClick={handleSignIn}
            >
              Đăng nhập
            </button>
            <button
              className="header-btn header-btn-filled"
              onClick={handleSignUp}
            >
              Đăng ký
            </button>
          </>
        )}
      </div>
    </nav>
  );
};

export default Navbarr;
