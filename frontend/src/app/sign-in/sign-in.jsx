"use client";

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthActions, useAuthTokens } from "../../service/auth/useAuth";
import { useAuthLoginService } from "../../service/auth/useAuthService";
import { useAuthForgotPassword } from "../../service/auth/useAuthService";
import "./sign-in.css";
import GoogleAuth from "../../service/auth/googleAuth";
import toast from "react-hot-toast";

// Sign In Component
const SignIn = () => {
  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });

  const navigate = useNavigate();

  const handleExit = () => {
    navigate(-1);
  };

  const handleSignUp = () => {
    navigate("/sign-up");
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const { setUser, refreshUser } = useAuthActions();
  const { setTokensInfo } = useAuthTokens();
  const fetchAuthLogin = useAuthLoginService();
  const fetchForgotPassword = useAuthForgotPassword();

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      console.log("Sign in:", formData);

      const res = await fetchAuthLogin({
        email: formData.email,
        password: formData.password,
        provider: "email",
      });

      setTokensInfo({
        token: res.access_token,
        refreshToken: res.refresh_token,
        tokenExpires: res.token_expires,
      });

      if (res.user) {
        setUser(res.user);
      }

      await refreshUser();
      navigate("/");
    } catch (error) {
      console.error("Login failed:", error);
      toast.error("Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin!");
    }
  };

  const handleSubmitForgotPassword = async (e) => {
    e.preventDefault();

    try {
      console.log("Forgot data:", formData);

      const res = await fetchForgotPassword({
        email: formData.email,
      });

      if (!res) {
        console.log("Can't reach endpoint forgot password");
      }

      toast.success(
        `Email reset mật khẩu đã được gửi đến email: ${formData.email}`
      );

      navigate("/");
    } catch (error) {
      console.error("Forgot password:", error);
      toast.error("Vui lòng kiểm tra lại thông tin!");
    }
  };

  return (
    <div className="container">
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <button className="close-btn" onClick={handleExit}>
          ×
        </button>

        <div className="auth-header">
          <h2>Đăng nhập</h2>
          <p>Chào mừng bạn trở lại!</p>
        </div>

        <div className="auth-form">
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="Nhập email của bạn"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Mật khẩu</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="Nhập mật khẩu"
            />
          </div>

          <div className="form-options">
            {/* <label className="remember-me">
              <input type="checkbox" />
              <span>Ghi nhớ đăng nhập</span>
            </label> */}
            <button
              className="forgot-password"
              onClick={handleSubmitForgotPassword}
            >
              Quên mật khẩu?
            </button>
          </div>

          <button className="auth-submit-btn" onClick={handleSubmit}>
            Đăng nhập
          </button>
        </div>

        <div className="auth-divider">
          <span>hoặc</span>
        </div>

        <div className="social-login">
          <GoogleAuth />
        </div>

        <div className="auth-footer">
          <p>
            Chưa có tài khoản?{" "}
            <button className="switch-btn" onClick={handleSignUp}>
              Đăng ký ngay
            </button>
          </p>
        </div>
      </div>
    </div>
  );
};

export default SignIn;
