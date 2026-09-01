import axios from "axios";

const APP_URL = process.env.REACT_APP_BASE_URL || "http://localhost:8000";
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
    localStorage.removeItem("userData");
  }
};

export const fetchUserProfile = async (userId) => {
  try {
    const resolvedUserId = userId || localStorage.getItem("userId");
    if (!resolvedUserId) return null;

    const response = await axios.get(`${APP_URL}/login/user/${resolvedUserId}`, {
      withCredentials: true,
    });

    if (response.data) {
      const formattedData = {
        user_id: response.data.id || response.data.user_id,
        name: response.data.name,
        email: response.data.email,
        role: response.data.role,
        company_name: response.data.company_name,
        user_type: response.data.user_type,
        ship_name: response.data.ship_name,
        ship_type: response.data.ship_type,
        user_name: response.data.user_name,
      };
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
