export const ALLOWED_FEEDBACK_EMAILS = [
  "pammu167@gmail.com",
  "nandukvm@hotmail.com",
  "k.vivekanand@aduacademy.in",
  "mullothashok@gmail.com",
  "ashwathykr009@yahoo.co.in",
  "karthikeyanc@compunetconnections.com",
];

export const isFeedbackAuthorized = (userEmail, userRole) => {
  if (userRole === "ADMIN" || userRole === "SUPER_ADMIN") return true;
  if (!userEmail || typeof userEmail !== "string") return false;
  const cleanEmail = userEmail.trim().toLowerCase();
  return ALLOWED_FEEDBACK_EMAILS.includes(cleanEmail);
};

export const getCurrentUserRole = () => {
  try {
    return JSON.parse(localStorage.getItem("userData") || "null")?.user_role || "";
  } catch {
    return "";
  }
};

export const getCurrentUserEmail = () => {
  try {
    const raw = localStorage.getItem("userData");
    if (!raw) return "";
    const parsed = JSON.parse(raw);
    return (
      parsed.email ||
      parsed.user_profile?.email ||
      parsed.user_email ||
      parsed.user_name ||
      ""
    ).trim().toLowerCase();
  } catch (e) {
    return "";
  }
};
