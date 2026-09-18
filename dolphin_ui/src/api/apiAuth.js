import axios from "axios";
import APP_URL from "../config/apiConfig";
export const loginApi = async (email, password) => {
  try {
    const response = await axios.post(
      `${APP_URL}/login`,
      { email, password },
      {
        headers: {
          "Content-Type": "application/json",
        },
        withCredentials: true,
      }
    );

    const userId = response.data.user_id; 

    localStorage.setItem("userId", userId);
    localStorage.setItem("user_id", userId);
    if (response.data.user_role) {
      localStorage.setItem("userRole", response.data.user_role);
    }
    localStorage.setItem("userData", JSON.stringify(response.data));

    return userId;
  } catch (error) {


     if (error.response) {
    throw new Error(
      error.response.data?.detail ||
      error.response.data?.message ||
      "Login failed"
    );
  } else {
    throw new Error("Network error");
  }
  }
};

export const logout = async () => {
  try {
    await axios.post(
      `${APP_URL}/logout`,
      {},
      {
        withCredentials: true, // same as credentials: 'include'
      }
    );
  } catch (error) {
    if (error.response) {
      throw new Error(
        error.response.data?.message ||
          error.response.data ||
          "Unable to logout."
      );
    } else {
      throw new Error(error.message || "Network error");
    }
  } finally {
    localStorage.removeItem("userId");
    localStorage.removeItem("user_id");
    localStorage.removeItem("role_id");
    localStorage.removeItem("userRole");
    localStorage.removeItem("userData");
  }
};

export const fetchUserProfile = async (userId) => {
  try {
    const resolvedUserId = userId || localStorage.getItem("userId") || localStorage.getItem("user_id");
    if (!resolvedUserId) return null;

    const response = await axios.get(`${APP_URL}/login/user/${resolvedUserId}`, {
      withCredentials: true,
    });

    if (response.data) {
      const existing = (() => {
        try {
          return JSON.parse(localStorage.getItem("userData") || "{}");
        } catch {
          return {};
        }
      })();

      const userRole =
        existing.user_role ||
        localStorage.getItem("userRole") ||
        response.data.user_role ||
        "";

      const formattedData = {
        ...existing,
        ...response.data,
        user_id: response.data.id || response.data.user_id || existing.user_id || resolvedUserId,
        name: response.data.name || existing.name,
        email: response.data.email || existing.email,
        user_role: userRole,
        company_name: response.data.company_name || existing.company_name,
        user_type: response.data.user_type || existing.user_type,
        ship_name: response.data.ship_name || existing.ship_name,
        ship_type: response.data.ship_type || existing.ship_type,
        user_name: response.data.user_name || existing.user_name,
      };

      if (userRole) {
        localStorage.setItem("userRole", userRole);
      }
      localStorage.setItem("userData", JSON.stringify(formattedData));
      return formattedData;
    }
  } catch (error) {
    console.error("Unable to fetch user profile:", error);
  }

  // Fallback to local storage if available
  try {
    const stored = localStorage.getItem("userData");
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (e) {}

  return null;
};
