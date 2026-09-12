import { useRef, useState } from "react";
import api from "../api/client";

function UploadBox({ setFileName, onUploadSuccess }) {
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  const handleBrowseClick = () => {
    fileInputRef.current.click();
  };

  const handleFileChange = (event) => {
    const file = event.target.files[0];

    if (file) {
      setSelectedFile(file);
      setFileName(file.name);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      alert("Please select a file first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      setUploading(true);

      const response = await api.post(
        "/upload",
        formData,
        {
          headers: {
            "Content-Type":
              "multipart/form-data",
          },
        }
      );

      alert(response.data.message);

      setFileName(
        response.data.filename
      );

      if (onUploadSuccess) {
        onUploadSuccess();
      }

      setSelectedFile(null);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (error) {
      console.error(
        "Upload Error:",
        error
      );

      if (error.response) {
        console.error(
          "Response:",
          error.response.data
        );
      }

      alert(
        error.response?.data?.error ||
          error.message ||
          "Upload failed."
      );
    } finally {
      setUploading(false);
    }
  };

  return (
    <div
      style={{
        background: "#ffffff",
        borderRadius: "10px",
        padding: "30px",
        marginTop: "30px",
        textAlign: "center",
        border:
          "2px dashed #3b82f6",
      }}
    >
      <h2
        style={{
          color: "#111827",
        }}
      >
        📤 Upload Document
      </h2>

      <p
        style={{
          color: "#111827",
        }}
      >
        Select a PDF, DOCX, PPTX or XLSX document
      </p>

      <button
        onClick={
          handleBrowseClick
        }
        style={{
          padding:
            "10px 20px",
          background:
            "#2563eb",
          color: "#fff",
          border: "none",
          borderRadius:
            "6px",
          cursor:
            "pointer",
        }}
      >
        Browse File
      </button>

      <button
        onClick={
          handleUpload
        }
        disabled={
          !selectedFile ||
          uploading
        }
        style={{
          marginLeft:
            "10px",
          padding:
            "10px 20px",
          background:
            !selectedFile ||
            uploading
              ? "#94a3b8"
              : "#16a34a",
          color: "white",
          border: "none",
          borderRadius:
            "6px",
          cursor:
            !selectedFile ||
            uploading
              ? "not-allowed"
              : "pointer",
        }}
      >
        {uploading
          ? "Uploading..."
          : "Upload"}
      </button>

      {selectedFile && (
        <p
          style={{
            marginTop:
              "15px",
            color:
              "#0f172a",
          }}
        >
          Selected:{" "}
          <strong>
            {selectedFile.name}
          </strong>
        </p>
      )}

      <input
        type="file"
        accept=".pdf,.doc,.docx,.pptx,.xlsx"
        ref={fileInputRef}
        onChange={
          handleFileChange
        }
        style={{
          display: "none",
        }}
      />
    </div>
  );
}

export default UploadBox;