import React, { useState } from "react";
import { Mail, Lock, Eye, EyeOff } from "lucide-react";
import { loginApi } from "../api/apiAuth";
import waveImg from "../assets/images/wave.png";
import dolphinImg from "../assets/images/dolphin_login.png";
import abstractBg from "../assets/images/abstract-login.png";
import dolphinBlack from "../assets/images/dolphin_b.png";
import DolphinWhite from "../assets/images/dolphin_w.png";
import raindropImg from "../assets/images/Rain_drop.png";
import { useThemeMode } from "../context/ThemeModeContext";
import ForgotPasswordPopup from "./ForgotPasswordPopup";
import packageJson from "../../package.json";

export default function Login({ onLoginSuccess }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState({});
  const [openForgot, setOpenForgot] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const { mode } = useThemeMode();

  const validate = () => {
    const newErrors = {};

    if (!email) newErrors.email = "Email is required";

    if (!password) newErrors.password = "Password is required";
    else if (password.length < 6)
      newErrors.password = "Password must be at least 6 characters";

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    try {
      const userId = await loginApi(email, password);
      localStorage.setItem("userId", userId);
      localStorage.setItem("user_id", userId);
      onLoginSuccess(userId);
    } catch (error) {
      setErrors({
        form: error.message || "Something went wrong",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="h-screen w-full flex bg-bg-default overflow-hidden relative"
      style={{
        backgroundImage: `url(${abstractBg})`,
        backgroundRepeat: "no-repeat",
        backgroundPosition: "center",
        backgroundSize: "100% 100%",
      }}
    >
      {/* ================= LEFT SECTION (Desktop) ================= */}
      <div className="hidden md:flex md:w-1/2 flex-col justify-start relative z-10 p-8">
        <div className="flex items-center gap-3 ml-4 mt-2">
          <img
            src={mode === "dark" ? DolphinWhite : dolphinBlack}
            alt="dolphin"
            className="w-20 h-20 object-contain"
          />
          <h1 className="text-3xl font-bold text-primary m-0">
            Dolphin | AI
          </h1>
        </div>

        <h2 className="text-4xl lg:text-5xl font-extrabold text-primary ml-4 mt-6 leading-tight">
          Your digital
          <br />
          shipmate –
        </h2>

        <p className="text-2xl lg:text-3xl font-medium text-primary ml-4 mt-2 leading-snug">
          Intelligent guidance,
          <br />
          anytime, anywhere
        </p>

        {/* Rotated decorative dolphin art */}
        <div className="absolute -bottom-24 -left-12 w-full h-64 pointer-events-none z-1 rotate-[20deg]">
          <img
            src={dolphinImg}
            alt="dolphin decorative"
            className="absolute w-72 left-0 bottom-0 object-contain"
          />
          <img
            src={dolphinImg}
            alt="dolphin decorative mini"
            className="absolute w-40 left-24 bottom-5 object-contain"
          />
        </div>
      </div>

      {/* ================= RIGHT SECTION (Login Form) ================= */}
      <div className="w-full md:w-1/2 flex flex-col items-center justify-center relative z-20 px-4">
        {/* Mobile brand header */}
        <div className="flex md:hidden flex-col items-center mb-6 text-center">
          <div className="flex items-center gap-2 mb-2">
            <img
              src={dolphinBlack}
              alt="dolphin"
              className="w-14 h-14 object-contain"
            />
            <h1 className="text-2xl font-bold text-primary m-0">
              Dolphin | AI
            </h1>
          </div>
          <h2 className="text-xl font-extrabold text-primary m-0">
            Your digital shipmate –
          </h2>
          <p className="text-sm font-medium text-primary m-0 mt-1">
            Intelligent guidance, anytime, anywhere
          </p>
        </div>

        {/* Login Card */}
        <div className="w-[90%] sm:w-[80%] md:w-[400px] max-w-full px-6 sm:px-8 pt-8 pb-5 rounded-3xl bg-bg-paper border-2 border-primary shadow-2xl relative z-20 mb-12 md:mb-20">
          {/* Raindrop ornament */}
          <img
            src={raindropImg}
            alt="raindrop decorative"
            className="absolute -top-16 -left-14 md:-top-24 md:-left-20 w-28 md:w-48 pointer-events-none z-30"
          />

          <h2 className="text-2xl font-bold text-primary mb-1 m-0">
            SIGN IN
          </h2>

          <p className="text-xs font-medium text-text-smallheading mb-5 m-0 leading-relaxed">
            Sign in to continue your smart conversations with our AI-powered chatbot.
          </p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {/* Email Field */}
            <div>
              <label className="block text-xs font-bold text-text-primary mb-1">
                Email
              </label>
              <div className="relative flex items-center">
                <Mail className="w-4 h-4 text-text-placeholder1 absolute left-3 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Enter your email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setErrors((prev) => ({ ...prev, email: null, form: null }));
                  }}
                  className={`w-full pl-9 pr-3 py-2 text-sm bg-bg-default border rounded-lg text-text-primary placeholder:text-text-placeholder1 focus:outline-hidden focus:ring-1 transition-all ${
                    errors.email
                      ? "border-rose-500 focus:border-rose-500 focus:ring-rose-500"
                      : "border-border-theme focus:border-primary focus:ring-primary"
                  }`}
                />
              </div>
              {errors.email && (
                <span className="text-xs text-rose-500 font-medium mt-1 block">
                  {errors.email}
                </span>
              )}
            </div>

            {/* Password Field */}
            <div>
              <label className="block text-xs font-bold text-text-primary mb-1">
                Password
              </label>
              <div className="relative flex items-center">
                <Lock className="w-4 h-4 text-text-placeholder1 absolute left-3 pointer-events-none" />
                <input
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setErrors((prev) => ({ ...prev, password: null, form: null }));
                  }}
                  className={`w-full pl-9 pr-9 py-2 text-sm bg-bg-default border rounded-lg text-text-primary placeholder:text-text-placeholder1 focus:outline-hidden focus:ring-1 transition-all ${
                    errors.password
                      ? "border-rose-500 focus:border-rose-500 focus:ring-rose-500"
                      : "border-border-theme focus:border-primary focus:ring-primary"
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-3 text-text-placeholder1 hover:text-text-primary transition-colors focus:outline-hidden"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <Eye className="w-4 h-4" />
                  ) : (
                    <EyeOff className="w-4 h-4" />
                  )}
                </button>
              </div>
              {errors.password && (
                <span className="text-xs text-rose-500 font-medium mt-1 block">
                  {errors.password}
                </span>
              )}
            </div>

            {/* Forgot Password Link */}
            <div className="text-right -mt-1">
              <button
                type="button"
                onClick={() => setOpenForgot(true)}
                className="text-xs font-semibold text-primary hover:underline transition-all"
              >
                Forgot Password ?
              </button>
            </div>

            {/* Form-level error */}
            {errors.form && (
              <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs font-medium text-center">
                {errors.form}
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2 px-4 rounded-lg bg-primary text-white font-bold text-sm shadow hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors tracking-wide mt-1"
            >
              {loading ? "Signing..." : "SIGN IN"}
            </button>

            {/* Footer Notice & Version */}
            <div className="text-center pt-2 text-[0.68rem] text-text-smallheading leading-tight space-y-1">
              <p className="m-0">© 2025 Mariner Skills , LLC. All rights reserved</p>
              <p className="m-0 text-text-caption">Version {packageJson.version}</p>
            </div>
          </form>
        </div>
      </div>

      {/* ================= WAVE BACKDROP ================= */}
      <div className="absolute bottom-0 w-full h-48 overflow-hidden pointer-events-none z-0">
        <img
          src={waveImg}
          alt="wave decorative background"
          className="w-full h-full object-cover"
        />
      </div>

      {/* ================= FORGOT PASSWORD POPUP ================= */}
      <ForgotPasswordPopup
        open={openForgot}
        handleClose={() => setOpenForgot(false)}
      />
    </div>
  );
}
