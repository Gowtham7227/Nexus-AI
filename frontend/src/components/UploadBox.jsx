import { useRef, useState } from "react";
import api from "../api/client";

const MAX_FILE_SIZE_MB = 100;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".xlsx", ".txt"];

function UploadBox({ setFileName, onUploadSuccess }) {
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const handleBrowseClick = () => {
    setStatusMessage(null);
    setErrorMessage(null);
    fileInputRef.current.click();
  };

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    setStatusMessage(null);
    setErrorMessage(null);

    if (file) {
      const ext = "." + file.name.split(".").pop().toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        setErrorMessage(
          `Unsupported file format "${ext}". Allowed: PDF, DOCX, PPTX, XLSX, TXT.`
        );
        setSelectedFile(null);
        return;
      }

      if (file.size > MAX_FILE_SIZE_BYTES) {
        setErrorMessage(
          `File is too large (${(file.size / (1024 * 1024)).toFixed(1)} MB). Maximum allowed size is ${MAX_FILE_SIZE_MB} MB.`
        );
        setSelectedFile(null);
        return;
      }

      setSelectedFile(file);
      if (setFileName) {
        setFileName(file.name);
      }
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setErrorMessage("Please select a file first.");
      return;
    }

    if (selectedFile.size > MAX_FILE_SIZE_BYTES) {
      setErrorMessage(
        `File is too large. Maximum allowed size is ${MAX_FILE_SIZE_MB} MB.`
      );
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      setUploading(true);
      setErrorMessage(null);
      setStatusMessage(null);

      const response = await api.post("/upload", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      const successMsg =
        response.data?.message || "File uploaded and indexed successfully!";
      setStatusMessage(successMsg);

      if (setFileName && response.data?.filename) {
        setFileName(response.data.filename);
      }

      if (onUploadSuccess) {
        onUploadSuccess();
      }

      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (error) {
      console.error("Upload Error:", error);

      let extractedError = "Upload failed. Please try again.";

      if (error.response) {
        const status = error.response.status;
        const data = error.response.data;

        if (status === 413) {
          extractedError =
            data?.detail || `File is too large. Maximum allowed size is ${MAX_FILE_SIZE_MB} MB.`;
        } else if (status === 415) {
          extractedError =
            data?.detail || "Unsupported file format. Please upload PDF, DOCX, PPTX, XLSX, or TXT.";
        } else if (status === 401) {
          extractedError = "Your session has expired. Please log in again.";
        } else if (status === 409) {
          extractedError =
            data?.detail || "A document with this name already exists. Please rename it.";
        } else if (data?.detail) {
          extractedError = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
        } else if (data?.message) {
          extractedError = data.message;
        } else if (data?.error) {
          extractedError = data.error;
        }
      } else if (error.message) {
        extractedError = error.message;
      }

      setErrorMessage(extractedError);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div
      style={{
        background: "var(--nx-surface, #ffffff)",
        borderRadius: "14px",
        padding: "28px",
        marginTop: "16px",
        textAlign: "center",
        border: "2px dashed var(--nx-primary-border, #3b82f6)",
        boxShadow: "0 4px 20px rgba(0,0,0,0.04)",
      }}
    >
      <div style={{ fontSize: "36px", marginBottom: "8px" }}>📤</div>
      <h3
        style={{
          margin: "0 0 6px 0",
          color: "var(--nx-text, #111827)",
          fontSize: "18px",
          fontWeight: "700",
        }}
      >
        Upload Workspace Document
      </h3>

      <p
        style={{
          margin: "0 0 20px 0",
          color: "var(--nx-text-muted, #64748b)",
          fontSize: "13px",
        }}
      >
        Supports PDF, DOCX, PPTX, XLSX, and TXT documents (up to {MAX_FILE_SIZE_MB} MB)
      </p>

      {statusMessage && (
        <div
          style={{
            margin: "0 auto 16px auto",
            maxWidth: "520px",
            padding: "10px 14px",
            borderRadius: "8px",
            background: "rgba(16, 185, 129, 0.12)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            color: "#059669",
            fontSize: "13px",
            fontWeight: "600",
            textAlign: "left",
          }}
        >
          ✓ {statusMessage}
        </div>
      )}

      {errorMessage && (
        <div
          style={{
            margin: "0 auto 16px auto",
            maxWidth: "520px",
            padding: "10px 14px",
            borderRadius: "8px",
            background: "rgba(239, 68, 68, 0.10)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#dc2626",
            fontSize: "13px",
            fontWeight: "600",
            textAlign: "left",
          }}
        >
          ✕ {errorMessage}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "center", gap: "10px", flexWrap: "wrap" }}>
        <button
          onClick={handleBrowseClick}
          type="button"
          style={{
            padding: "10px 20px",
            background: "var(--nx-primary, #2563eb)",
            color: "#fff",
            border: "none",
            borderRadius: "8px",
            cursor: "pointer",
            fontWeight: "600",
            fontSize: "14px",
          }}
        >
          📁 Browse File
        </button>

        <button
          onClick={handleUpload}
          disabled={!selectedFile || uploading}
          type="button"
          style={{
            padding: "10px 22px",
            background: !selectedFile || uploading ? "#94a3b8" : "#16a34a",
            color: "white",
            border: "none",
            borderRadius: "8px",
            cursor: !selectedFile || uploading ? "not-allowed" : "pointer",
            fontWeight: "600",
            fontSize: "14px",
            transition: "all 0.2s ease",
          }}
        >
          {uploading ? "⏳ Uploading & Indexing..." : "⬆ Upload & Index"}
        </button>
      </div>

      {selectedFile && (
        <div
          style={{
            marginTop: "16px",
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "6px 14px",
            background: "rgba(37, 99, 235, 0.08)",
            borderRadius: "20px",
            border: "1px solid rgba(37, 99, 235, 0.2)",
            color: "var(--nx-text, #0f172a)",
            fontSize: "13px",
          }}
        >
          <span>📄</span>
          <strong>{selectedFile.name}</strong>
          <span style={{ color: "#64748b" }}>
            ({selectedFile.size > 1024 * 1024
              ? `${(selectedFile.size / (1024 * 1024)).toFixed(1)} MB`
              : `${(selectedFile.size / 1024).toFixed(1)} KB`})
          </span>
        </div>
      )}

      <input
        type="file"
        accept=".pdf,.doc,.docx,.pptx,.xlsx,.txt"
        ref={fileInputRef}
        onChange={handleFileChange}
        style={{ display: "none" }}
      />
    </div>
  );
}

export default UploadBox;