/*
  NexusAI ChatWindow
  UI changes:
  - Removed the large robot "Ask NexusAI anything" empty state.
  - Chat input is centered before the first message.
  - Chat input moves to the bottom after ChatInput dispatches
    the "nexusai-chat-started" event.
  - Existing document selection/explanation/backend logic is preserved.
*/
import React, {
  useEffect,
  useState,
} from "react";

import api from "../api/client";
import { FaRobot } from "react-icons/fa";
import ChatInput from "./ChatInput";

function ChatWindow() {
  // ============================================================
  // SELECTED DOCUMENTS
  // ============================================================

  const [
    selectedDocuments,
    setSelectedDocuments,
  ] = useState([]);

  const [
    loaded,
    setLoaded,
  ] = useState(false);

  // ============================================================
  // CHAT START STATE
  // ============================================================

  const [
    chatStarted,
    setChatStarted,
  ] = useState(false);

  // ============================================================
  // DOCUMENT EXPLANATION
  // ============================================================

  const [
    explanation,
    setExplanation,
  ] = useState("");

  const [
    explaining,
    setExplaining,
  ] = useState(false);

  const [
    explanationError,
    setExplanationError,
  ] = useState("");

  // ============================================================
  // LOAD SELECTED DOCUMENTS
  // ============================================================

  useEffect(() => {
    const loadSelectedDocuments = () => {
      try {
        const saved =
          localStorage.getItem(
            "nexusai_selected_documents"
          );

        if (saved) {
          const parsed =
            JSON.parse(saved);

          if (
            Array.isArray(parsed)
          ) {
            setSelectedDocuments(
              parsed
            );

            setLoaded(true);

            return;
          }
        }

        const oldDocument =
          localStorage.getItem(
            "nexusai_selected_document"
          );

        if (oldDocument) {
          setSelectedDocuments([
            oldDocument,
          ]);
        } else {
          setSelectedDocuments([]);
        }
      } catch (error) {
        console.error(
          "Error loading selected documents:",
          error
        );

        setSelectedDocuments([]);
      }

      setLoaded(true);
    };

    loadSelectedDocuments();

    const handleDocumentChange = () => {
      loadSelectedDocuments();

      // A document selection change starts
      // a fresh explanation state.
      setExplanation("");
      setExplanationError("");
    };

    window.addEventListener(
      "nexusai-selected-documents-change",
      handleDocumentChange
    );

    const handleChatStarted = () => {
      setChatStarted(true);
    };

    window.addEventListener(
      "nexusai-chat-started",
      handleChatStarted
    );

    return () => {
      window.removeEventListener(
        "nexusai-selected-documents-change",
        handleDocumentChange
      );

      window.removeEventListener(
        "nexusai-chat-started",
        handleChatStarted
      );
    };
  }, []);

  // ============================================================
  // DOCUMENT CHANGE CALLBACK
  // ============================================================

  const handleDocumentsChange = (
    documents
  ) => {
    if (
      !Array.isArray(documents)
    ) {
      return;
    }

    setSelectedDocuments(
      documents
    );

    localStorage.setItem(
      "nexusai_selected_documents",
      JSON.stringify(documents)
    );

    if (
      documents.length === 1
    ) {
      localStorage.setItem(
        "nexusai_selected_document",
        documents[0]
      );
    } else {
      localStorage.removeItem(
        "nexusai_selected_document"
      );
    }

    // Clear old explanation when the
    // selected document set changes.
    setExplanation("");
    setExplanationError("");
  };

  // ============================================================
  // NEW CHAT
  // ============================================================

  const handleNewChat = () => {
    setSelectedDocuments([]);
    setChatStarted(false);

    setExplanation("");
    setExplanationError("");
    setExplaining(false);

    localStorage.removeItem(
      "nexusai_selected_documents"
    );

    localStorage.removeItem(
      "nexusai_selected_document"
    );

    localStorage.removeItem(
      "nexusai_new_chat"
    );

    window.dispatchEvent(
      new Event(
        "nexusai-new-chat"
      )
    );

    // Stay on /chat.
  };

  // ============================================================
  // EXPLAIN ENTIRE DOCUMENT
  // ============================================================

  const handleExplainDocument = async () => {
    if (
      selectedDocuments.length !== 1
    ) {
      setExplanationError(
        "Please select one document to explain."
      );

      return;
    }

    const filename =
      selectedDocuments[0];

    setExplaining(true);
    setExplanation("");
    setExplanationError("");

    try {
      const response =
        await api.post(
          "/document-summary",
          {
            question:
              "Explain entire document",
            filenames: [
              filename,
            ],
          }
        );

      const answer =
        response.data?.answer;

      if (
        answer &&
        String(answer).trim()
      ) {
        setExplanation(
          String(answer).trim()
        );
      } else {
        setExplanationError(
          "I couldn't generate an explanation from the uploaded document."
        );
      }
    } catch (error) {
      console.error(
        "Error explaining document:",
        error
      );

      const backendError =
        error?.response?.data?.error;

      setExplanationError(
        backendError
          ? `Unable to explain the document: ${backendError}`
          : "Unable to explain the document. Please make sure the NexusAI backend is running."
      );
    } finally {
      setExplaining(false);
    }
  };

  // ============================================================
  // SIMPLE MARKDOWN-LIKE RENDERER
  // ============================================================

  const renderExplanation = () => {
    if (!explanation) {
      return null;
    }

    const lines =
      explanation.split("\n");

    return (
      <div
        style={{
          color: "var(--nx-text-secondary)",
          fontSize: "15px",
          lineHeight: "1.75",
        }}
      >
        {lines.map(
          (line, index) => {
            const trimmed =
              line.trim();

            if (!trimmed) {
              return (
                <div
                  key={index}
                  style={{
                    height: "8px",
                  }}
                />
              );
            }

            if (
              trimmed.startsWith("### ")
            ) {
              return (
                <h3
                  key={index}
                  style={{
                    margin:
                      "20px 0 8px 0",
                    color: "var(--nx-text)",
                    fontSize: "19px",
                    lineHeight: "1.4",
                  }}
                >
                  {trimmed
                    .replace(
                      /^###\s+/,
                      ""
                    )}
                </h3>
              );
            }

            if (
              trimmed.startsWith("## ")
            ) {
              return (
                <h3
                  key={index}
                  style={{
                    margin:
                      "20px 0 8px 0",
                    color: "var(--nx-text)",
                    fontSize: "19px",
                  }}
                >
                  {trimmed
                    .replace(
                      /^##\s+/,
                      ""
                    )}
                </h3>
              );
            }

            if (
              trimmed.startsWith("- ") ||
              trimmed.startsWith("* ")
            ) {
              return (
                <div
                  key={index}
                  style={{
                    display: "flex",
                    gap: "9px",
                    marginBottom:
                      "7px",
                    paddingLeft:
                      "4px",
                  }}
                >
                  <span
                    style={{
                      color: "var(--nx-primary)",
                      fontWeight: "700",
                    }}
                  >
                    •
                  </span>

                  <span>
                    {formatInlineText(
                      trimmed.substring(2)
                    )}
                  </span>
                </div>
              );
            }

            return (
              <p
                key={index}
                style={{
                  margin:
                    "0 0 10px 0",
                }}
              >
                {formatInlineText(
                  trimmed
                )}
              </p>
            );
          }
        )}
      </div>
    );
  };

  // ============================================================
  // INLINE FORMATTING
  // ============================================================

  const formatInlineText = (
    text
  ) => {
    const parts =
      text.split(
        /(\*\*[^*]+\*\*|`[^`]+`)/g
      );

    return parts.map(
      (part, index) => {
        if (
          part.startsWith("**") &&
          part.endsWith("**")
        ) {
          return (
            <strong
              key={index}
              style={{
                color: "var(--nx-text)",
              }}
            >
              {part.slice(
                2,
                -2
              )}
            </strong>
          );
        }

        if (
          part.startsWith("`") &&
          part.endsWith("`")
        ) {
          return (
            <code
              key={index}
              style={{
                background:
                  "var(--nx-surface-2)",
                padding:
                  "2px 6px",
                borderRadius:
                  "4px",
                fontSize:
                  "13px",
              }}
            >
              {part.slice(
                1,
                -1
              )}
            </code>
          );
        }

        return (
          <React.Fragment
            key={index}
          >
            {part}
          </React.Fragment>
        );
      }
    );
  };

  // ============================================================
  // CHAT MODE TEXT
  // ============================================================



  // ============================================================
  // LOADING
  // ============================================================

  if (!loaded) {
    return (
      <div
        style={{
          marginTop: "30px",
          background: "#f8f9fa",
          borderRadius: "12px",
          padding: "20px",
          minHeight: "300px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--nx-text-muted)",
        }}
      >
        Loading chat...
      </div>
    );
  }

  // ============================================================
  // RENDER
  // ============================================================

  return (
    <div
      style={{
        marginTop: "24px",
        background: "var(--nx-surface)",
        border: "1px solid var(--nx-border)",
        borderRadius: "18px",
        padding: "22px",
        minHeight: "calc(100vh - 245px)",
        display: "flex",
        flexDirection: "column",
        boxShadow: "0 12px 35px rgba(15, 23, 42, 0.06)",
        overflow: "hidden",
      }}
    >
      {/* ======================================================
          HEADER
      ====================================================== */}

      <div
        style={{
          display: "flex",
          justifyContent:
            "space-between",
          alignItems: "center",
          gap: "15px",
          marginBottom: "18px",
          flexWrap: "wrap",
          paddingBottom: "16px",
          borderBottom: "1px solid var(--nx-border)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <FaRobot
            size={28}
            color="var(--nx-primary)"
          />

          <h2
            style={{
              margin: 0,
              color: "var(--nx-text)",
              fontSize: "21px",
              letterSpacing: "-0.02em",
            }}
          >
            NexusAI Assistant
          </h2>
        </div>

        <button
          type="button"
          onClick={
            handleNewChat
          }
          style={{
            border: "none",
            background: "var(--nx-primary)",
            color: "var(--nx-surface)",
            padding: "10px 15px",
            borderRadius: "10px",
            fontSize: "14px",
            fontWeight: "700",
            cursor: "pointer",
            boxShadow: "0 5px 14px rgba(37,99,235,0.20)",
            transition: "all 0.2s ease",
          }}
        >
          ＋ New Chat
        </button>
      </div>

      {/* ======================================================
          SELECTED DOCUMENTS
      ====================================================== */}

      {selectedDocuments.length > 0 && (
        <div
          style={{
            background: "var(--nx-bg)",
            padding: "10px 12px",
            borderRadius: "12px",
            marginBottom: "10px",
            border: "1px solid var(--nx-border)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              flexWrap: "wrap",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "7px",
                color: "var(--nx-text)",
                fontWeight: "700",
                fontSize: "14px",
                flexShrink: 0,
              }}
            >
              📚 Selected
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "7px",
                flex: 1,
                minWidth: 0,
                overflowX: "auto",
                paddingBottom: "1px",
              }}
            >
              {selectedDocuments.map((filename) => (
                <div
                  key={filename}
                  title={filename}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "7px",
                    padding: "7px 10px",
                    background: "var(--nx-primary-soft)",
                    border: "1px solid var(--nx-primary-border)",
                    borderRadius: "8px",
                    color: "var(--nx-primary-hover)",
                    fontSize: "13px",
                    fontWeight: "600",
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                    maxWidth: "320px",
                  }}
                >
                  <span>📄</span>
                  <span
                    style={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {filename}
                  </span>
                </div>
              ))}
            </div>

            <div
              style={{
                padding: "4px 9px",
                borderRadius: "20px",
                background: "#dcfce7",
                color: "#166534",
                fontSize: "11px",
                fontWeight: "700",
                flexShrink: 0,
              }}
            >
              {selectedDocuments.length}{" "}
              {selectedDocuments.length === 1 ? "document" : "documents"}
            </div>
          </div>

          <div
            style={{
              marginTop: "7px",
              color: "var(--nx-text-muted)",
              fontSize: "11px",
              lineHeight: "1.4",
            }}
          >
            🔒 Only the selected {selectedDocuments.length === 1 ? "document" : "documents"} will be used for this chat.
          </div>
        </div>
      )}

      {/* ======================================================
          EXPLAIN ENTIRE DOCUMENT
      ====================================================== */}

      {selectedDocuments.length === 1 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
            padding: "9px 12px",
            marginBottom: "10px",
            borderRadius: "10px",
            background: "var(--nx-primary-soft)",
            border: "1px solid var(--nx-primary-border)",
            flexWrap: "wrap",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              minWidth: 0,
            }}
          >
            <span style={{ fontSize: "16px" }}>📖</span>
            <span
              style={{
                color: "var(--nx-text)",
                fontSize: "13px",
                fontWeight: "700",
              }}
            >
              Need a quick overview?
            </span>
            <span
              style={{
                color: "var(--nx-text-muted)",
                fontSize: "12px",
              }}
            >
              Explain the entire document
            </span>
          </div>

          <button
            type="button"
            onClick={handleExplainDocument}
            disabled={explaining}
            style={{
              border: "none",
              background: explaining
                ? "var(--nx-text-muted)"
                : "var(--nx-primary)",
              color: "#ffffff",
              padding: "7px 12px",
              borderRadius: "7px",
              fontSize: "12px",
              fontWeight: "700",
              cursor: explaining ? "not-allowed" : "pointer",
              whiteSpace: "nowrap",
              boxShadow: "0 2px 6px rgba(37,99,235,0.18)",
              flexShrink: 0,
            }}
          >
            {explaining ? "⏳ Explaining..." : "📖 Explain Document"}
          </button>
        </div>
      )}

      {/* ======================================================
          EXPLANATION ERROR
      ====================================================== */}

      {explanationError && (
        <div
          style={{
            background:
              "#fef2f2",
            border:
              "1px solid #fecaca",
            color:
              "#b91c1c",
            padding:
              "13px 15px",
            borderRadius:
              "9px",
            marginBottom:
              "20px",
            fontSize:
              "14px",
          }}
        >
          ⚠️ {explanationError}
        </div>
      )}

      {/* ======================================================
          EXPLANATION LOADING
      ====================================================== */}

      {explaining && (
        <div
          style={{
            background:
              "var(--nx-surface)",
            borderRadius:
              "12px",
            padding:
              "28px",
            marginBottom:
              "20px",
            textAlign:
              "center",
            boxShadow:
              "0 2px 8px rgba(0,0,0,0.08)",
          }}
        >
          <div
            style={{
              fontSize:
                "32px",
              marginBottom:
                "10px",
            }}
          >
            🧠
          </div>

          <h3
            style={{
              margin:
                "0 0 7px 0",
              color:
                "var(--nx-text)",
            }}
          >
            Reading the entire document...
          </h3>

          <p
            style={{
              margin: 0,
              color:
                "var(--nx-text-muted)",
              fontSize:
                "14px",
            }}
          >
            NexusAI is preparing a
            complete explanation.
            This may take a moment.
          </p>
        </div>
      )}

      {/* ======================================================
          EXPLANATION RESULT
      ====================================================== */}

      {explanation && (
        <div
          style={{
            background:
              "var(--nx-surface)",
            borderRadius:
              "12px",
            padding:
              "24px",
            marginBottom:
              "20px",
            boxShadow:
              "0 2px 8px rgba(0,0,0,0.08)",
            border:
              "1px solid var(--nx-border)",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent:
                "space-between",
              alignItems:
                "center",
              gap: "10px",
              marginBottom:
                "18px",
              paddingBottom:
                "14px",
              borderBottom:
                "1px solid var(--nx-border)",
              flexWrap:
                "wrap",
            }}
          >
            <div>
              <div
                style={{
                  color:
                    "var(--nx-primary)",
                  fontSize:
                    "12px",
                  fontWeight:
                    "800",
                  textTransform:
                    "uppercase",
                  letterSpacing:
                    "0.05em",
                }}
              >
                Document Explanation
              </div>

              <div
                style={{
                  marginTop:
                    "4px",
                  color:
                    "var(--nx-text)",
                  fontSize:
                    "17px",
                  fontWeight:
                    "700",
                  wordBreak:
                    "break-word",
                }}
              >
                📄{" "}
                {
                  selectedDocuments[0]
                }
              </div>
            </div>

            <button
              type="button"
              onClick={
                handleExplainDocument
              }
              disabled={
                explaining
              }
              style={{
                border:
                  "1px solid var(--nx-primary-border)",
                background:
                  "var(--nx-primary-soft)",
                color:
                  "var(--nx-primary-hover)",
                padding:
                  "8px 12px",
                borderRadius:
                  "7px",
                fontSize:
                  "13px",
                fontWeight:
                  "700",
                cursor:
                  explaining
                    ? "not-allowed"
                    : "pointer",
              }}
            >
              ↻ Explain Again
            </button>
          </div>

          {renderExplanation()}
        </div>
      )}

      {/* ======================================================
          CHAT INPUT
          Centered before the first message.
          Bottom-aligned after the first message.
      ====================================================== */}

      <div
        style={{
          minHeight: chatStarted ? "0" : "220px",
          display: "flex",
          alignItems: chatStarted ? "flex-end" : "center",
          justifyContent: "center",
          transition:
            "min-height 0.25s ease, align-items 0.25s ease",
          paddingTop: chatStarted ? "6px" : "12px",
          paddingBottom: "4px",
        }}
      >
        <div
          style={{
            width: "100%",
            transition:
              "transform 0.25s ease, width 0.25s ease",
          }}
        >
          <ChatInput
            selectedDocument={
              selectedDocuments.length ===
              1
                ? selectedDocuments[0]
                : ""
            }
            selectedDocuments={
              selectedDocuments
            }
            onDocumentsChange={
              handleDocumentsChange
            }
          />
        </div>
      </div>
    </div>
  );
}

export default ChatWindow;
