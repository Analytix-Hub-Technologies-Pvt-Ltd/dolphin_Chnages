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
