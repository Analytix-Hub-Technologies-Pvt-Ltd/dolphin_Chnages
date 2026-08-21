import axios from "axios";

const APP_URL = process.env.REACT_APP_BASE_URL || "http://localhost:8000";
const API_BASE_URL = `${APP_URL}/companies`; 

const getAuthHeaders = () => {
  return {};
};

export const fetchCompanyDocuments = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/documents`, {
      headers: getAuthHeaders(),
    });
    return response.data;
  } catch (error) {
    console.error("Error fetching documents:", error);
    throw error;
  }
};

export const deleteCompanyDocument = async (documentId) => {
  try {
    const response = await axios.delete(`${API_BASE_URL}/documents/${documentId}`, {
      headers: getAuthHeaders(),
    });
    return response.data;
  } catch (error) {
    console.error("Error deleting document:", error);
    throw error;
  }
};

export const uploadCompanyDocuments = async (companyId, files) => {
  const formData = new FormData();
  formData.append("company_id", companyId);

  for (let i = 0; i < files.length; i++) {
    formData.append("files", files[i]);
  }

  try {
    const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
        ...getAuthHeaders(),
      },
    });
    return response.data;
  } catch (error) {
    console.error("Error uploading documents:", error);
    throw error;
  }
};
