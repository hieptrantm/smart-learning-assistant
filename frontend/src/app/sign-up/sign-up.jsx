"use client";

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Cookies from "js-cookie";
import "./sign-up.css";
import GoogleAuth from "../../service/auth/googleAuth";
import toast from "react-hot-toast";

const SignUp = () => {
  const [formData, setFormData] = useState({
    fullName: "",
    email: "",
    password: "",
    confirmPassword: "",
  });

  const [errors, setErrors] = useState({});
  const navigate = useNavigate();

  const handleExit = () => navigate(-1);
  const handleSignIn = () => navigate("/sign-in");

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
    setErrors({
      ...errors,
      [e.target.name]: "",
    });
  };

  const validateEmail = (email) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const validatePassword = (password) => {
    if (password.length < 8) return "Mật khẩu phải ít nhất 8 ký tự";
    if (!/[A-Za-z]/.test(password))
      return "Mật khẩu phải chứa ít nhất một chữ cái";
    if (!/\d/.test(password)) return "Mật khẩu phải chứa ít nhất một số";
    return "";
  };

  const handleSubmit = async () => {
    const newErrors = {};
    if (!formData.fullName)
      newErrors.fullName = "Họ và tên không được để trống";
    if (!validateEmail(formData.email)) newErrors.email = "Email không hợp lệ";
    const passwordError = validatePassword(formData.password);
    if (passwordError) newErrors.password = passwordError;
    if (formData.password !== formData.confirmPassword)
      newErrors.confirmPassword = "Mật khẩu không khớp";

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    try {
      const response = await fetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: formData.fullName,
          email: formData.email,
          password: formData.password,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Đăng ký thất bại!");
      }

      const data = await response.json();
      Cookies.set("access_token", data.access_token, { expires: 1 });

      toast.success("Đăng ký thành công!");
      navigate("/");
    } catch (error) {
      console.error("Registration error:", error);
      toast.error(error.message || "Đăng ký thất bại!");
    }
  };

  return (
    <div className="container">
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <button className="close-btn" onClick={handleExit}>
          ×
        </button>

        <div className="auth-header">
          <h2>Đăng ký</h2>
          <p>Tạo tài khoản mới để bắt đầu</p>
        </div>

        <div className="auth-form">
          <div className="form-group">
            <label htmlFor="fullName">Họ và tên</label>
            <input
              type="text"
              id="fullName"
              name="fullName"
              value={formData.fullName}
              onChange={handleChange}
              placeholder="Nhập họ và tên"
            />
            {errors.fullName && <p className="error">{errors.fullName}</p>}
          </div>

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
            {errors.email && <p className="error">{errors.email}</p>}
          </div>

          <div className="form-group">
            <label htmlFor="password">Mật khẩu</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="Tạo mật khẩu (tối thiểu 8 ký tự)"
            />
            {errors.password && <p className="error">{errors.password}</p>}
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">Xác nhận mật khẩu</label>
            <input
              type="password"
              id="confirmPassword"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              placeholder="Nhập lại mật khẩu"
            />
            {errors.confirmPassword && (
              <p className="error">{errors.confirmPassword}</p>
            )}
          </div>

          <button className="auth-submit-btn" onClick={handleSubmit}>
            Đăng ký
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
            Đã có tài khoản?{" "}
            <button className="switch-btn" onClick={handleSignIn}>
              Đăng nhập
            </button>
          </p>
        </div>
      </div>
    </div>
  );
};

export default SignUp;
