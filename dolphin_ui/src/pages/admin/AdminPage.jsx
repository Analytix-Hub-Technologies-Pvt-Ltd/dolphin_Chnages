import React, { useState, useEffect } from "react";
import {
  Container,
  Typography,
  Box,
  Button,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  CircularProgress,
  Snackbar,
  Alert
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import { fetchCompanyDocuments, uploadCompanyDocuments, deleteCompanyDocument } from "../../api/apiAdmin";

const AdminPage = () => {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [companyId, setCompanyId] = useState("");
  const [selectedFiles, setSelectedFiles] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: "", severity: "success" });

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const data = await fetchCompanyDocuments();
      setDocuments(data.documents || []);
    } catch (error) {
      showSnackbar("Failed to load documents", "error");
    } finally {
      setLoading(false);
    }
  };

  const showSnackbar = (message, severity = "success") => {
    setSnackbar({ open: true, message, severity });
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  const handleFileChange = (event) => {
    setSelectedFiles(event.target.files);
  };

  const handleUpload = async (event) => {
    event.preventDefault();
    if (!companyId || !selectedFiles || selectedFiles.length === 0) {
      showSnackbar("Please enter a company ID and select files", "warning");
      return;
    }

    setUploading(true);
    try {
      await uploadCompanyDocuments(companyId, selectedFiles);
      showSnackbar("Documents uploaded successfully", "success");
      setCompanyId("");
      setSelectedFiles(null);
      // Reset file input visually
      document.getElementById("file-upload").value = "";
      loadDocuments();
    } catch (error) {
      showSnackbar("Failed to upload documents", "error");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (documentId) => {
    if (!window.confirm("Are you sure you want to delete this document?")) return;

    try {
      await deleteCompanyDocument(documentId);
      showSnackbar("Document deleted successfully", "success");
      loadDocuments();
    } catch (error) {
      showSnackbar("Failed to delete document", "error");
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom>
        Admin Dashboard
      </Typography>

      {/* Upload Section */}
      <Paper sx={{ p: 3, mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          Upload Company Document
        </Typography>
        <Box component="form" onSubmit={handleUpload} sx={{ display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap" }}>
          <TextField
            label="Company ID"
            variant="outlined"
            size="small"
            value={companyId}
            onChange={(e) => setCompanyId(e.target.value)}
            required
          />
          <Button
            component="label"
            variant="outlined"
            startIcon={<CloudUploadIcon />}
          >
            Select Files
            <input
              type="file"
              id="file-upload"
              hidden
              multiple
              onChange={handleFileChange}
              accept=".pdf,.docx,.txt,.xlsx,.csv"
            />
          </Button>
          <Typography variant="body2" color="textSecondary">
            {selectedFiles ? `${selectedFiles.length} file(s) selected` : "No files selected"}
          </Typography>
          <Button 
            type="submit" 
            variant="contained" 
            color="primary"
            disabled={uploading}
          >
            {uploading ? <CircularProgress size={24} /> : "Upload"}
          </Button>
        </Box>
      </Paper>

      {/* Manage Documents Section */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Manage Company Documents
        </Typography>
        {loading ? (
          <Box display="flex" justifyContent="center" my={4}>
            <CircularProgress />
          </Box>
        ) : (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Company ID</TableCell>
                  <TableCell>Title</TableCell>
                  <TableCell>Size (chars)</TableCell>
                  <TableCell>Date Added</TableCell>
                  <TableCell align="center">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {documents.length > 0 ? (
                  documents.map((doc) => (
                    <TableRow key={doc.document_id}>
                      <TableCell>{doc.document_id}</TableCell>
                      <TableCell>{doc.company_id || "N/A"}</TableCell>
                      <TableCell>{doc.document_title}</TableCell>
                      <TableCell>{doc.content_length}</TableCell>
                      <TableCell>{new Date(doc.created_at).toLocaleDateString()}</TableCell>
                      <TableCell align="center">
                        <IconButton color="error" onClick={() => handleDelete(doc.document_id)}>
                          <DeleteIcon />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={6} align="center">
                      No documents found.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={handleCloseSnackbar}>
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: "100%" }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Container>
  );
};

export default AdminPage;
