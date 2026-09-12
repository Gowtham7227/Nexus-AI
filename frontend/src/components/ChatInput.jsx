/*
  NexusAI ChatInput
  UI changes:
  - Removed the large robot welcome message from the chat history.
  - Added browser voice-to-text input with a microphone button.
  - Dispatches "nexusai-chat-started" when the first real question is sent,
    allowing ChatWindow to move the composer from center to bottom.
  - Existing document upload, selection, chat history, and AI calls preserved.
*/
import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { FaArrowUp, FaPlus, FaMicrophone } from "react-icons/fa";

function ChatInput({
  selectedDocument,
  selectedDocuments = [],
  onDocumentsChange,
}) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const [processingMode, setProcessingMode] =
    useState("cloud");

  const [showPlusMenu, setShowPlusMenu] =
    useState(false);

  const [showDocumentModal, setShowDocumentModal] =
    useState(false);

  const [documents, setDocuments] =
    useState([]);

  const [documentSearch, setDocumentSearch] =
    useState("");

  const [modalSelectedDocuments, setModalSelectedDocuments] =
    useState([]);

  const [loadingDocuments, setLoadingDocuments] =
    useState(false);

  const [uploading, setUploading] =
    useState(false);

  // ============================================================
  // VOICE INPUT
  // ============================================================

  const [isListening, setIsListening] =
    useState(false);

  const recognitionRef = useRef(null);

  const fileInputRef = useRef(null);

  const CHAT_STORAGE_KEY =
    "nexusai_chat_history";

  const MODE_STORAGE_KEY =
    "nexusai_processing_mode";

  // ============================================================
  // NORMALIZE SELECTED DOCUMENTS
  // ============================================================

  const activeDocuments =
    Array.isArray(selectedDocuments) &&
    selectedDocuments.length > 0
      ? selectedDocuments
      : selectedDocument
      ? [selectedDocument]
      : [];

  const isMultiDocument =
    activeDocuments.length > 1;

  // ============================================================
  // CHAT HISTORY KEY
  // ============================================================

  const getChatHistoryKey = () => {
    if (activeDocuments.length === 0) {
      return "";
    }

    return activeDocuments
      .slice()
      .sort()
      .join("||");
  };

  // ============================================================
  // LOAD AI MODE
  // ============================================================

  useEffect(() => {
    const loadMode = () => {
      const savedMode =
        localStorage.getItem(
          MODE_STORAGE_KEY
        );

      if (
        savedMode === "local" ||
        savedMode === "cloud"
      ) {
        setProcessingMode(savedMode);
      } else {
        setProcessingMode("cloud");
      }
    };

    loadMode();

    window.addEventListener(
      "nexusai-mode-change",
      loadMode
    );

    return () => {
      window.removeEventListener(
        "nexusai-mode-change",
        loadMode
      );
    };
  }, []);

  // ============================================================
  // LOAD CHAT HISTORY
  // ============================================================

  useEffect(() => {
    if (activeDocuments.length === 0) {
      setMessages([]);
      setQuestion("");
      return;
    }

    try {
      const storedChats =
        localStorage.getItem(
          CHAT_STORAGE_KEY
        );

      if (!storedChats) {
        setMessages([]);
        setQuestion("");
        return;
      }

      const allChats =
        JSON.parse(storedChats);

      const historyKey =
        getChatHistoryKey();

      const documentMessages =
        allChats[historyKey] || [];

      setMessages(
        Array.isArray(documentMessages)
          ? documentMessages
          : []
      );

      setQuestion("");
    } catch (error) {
      console.error(
        "Failed to load chat history:",
        error
      );

      setMessages([]);
      setQuestion("");
    }
  }, [
    selectedDocument,
    selectedDocuments,
  ]);

  // ============================================================
  // SAVE CHAT HISTORY
  // ============================================================

  const saveMessages = (
    updatedMessages
  ) => {
    if (activeDocuments.length === 0) {
      return;
    }

    try {
      const storedChats =
        localStorage.getItem(
          CHAT_STORAGE_KEY
        );

      const allChats =
        storedChats
          ? JSON.parse(storedChats)
          : {};

      const historyKey =
        getChatHistoryKey();

      allChats[historyKey] =
        updatedMessages;

      localStorage.setItem(
        CHAT_STORAGE_KEY,
        JSON.stringify(allChats)
      );
    } catch (error) {
      console.error(
        "Failed to save chat history:",
        error
      );
    }
  };

  // ============================================================
  // ADD MESSAGE
  // ============================================================

  const addMessage = (
    message
  ) => {
    setMessages(
      (previousMessages) => {
        const updatedMessages = [
          ...previousMessages,
          message,
        ];

        saveMessages(
          updatedMessages
        );

        return updatedMessages;
      }
    );
  };

  // ============================================================
  // FETCH DOCUMENTS FOR MODAL
  // ============================================================

  const fetchDocuments = async () => {
    try {
      setLoadingDocuments(true);

      const response =
        await axios.get(
          "http://127.0.0.1:8000/documents"
        );

      setDocuments(
        response.data.documents || []
      );
    } catch (error) {
      console.error(
        "Failed to load documents:",
        error
      );

      alert(
        "Unable to load documents."
      );
    } finally {
      setLoadingDocuments(false);
    }
  };

  // ============================================================
  // OPEN DOCUMENT MODAL
  // ============================================================

  const openDocumentModal = async () => {
    setShowPlusMenu(false);

    setModalSelectedDocuments(
      activeDocuments
    );

    setDocumentSearch("");

    setShowDocumentModal(true);

    await fetchDocuments();
  };

  // ============================================================
  // TOGGLE MODAL DOCUMENT
  // ============================================================

  const toggleModalDocument = (
    filename
  ) => {
    setModalSelectedDocuments(
      (previous) => {
        if (
          previous.includes(filename)
        ) {
          return previous.filter(
            (item) =>
              item !== filename
          );
        }

        return [
          ...previous,
          filename,
        ];
      }
    );
  };

  // ============================================================
  // APPLY DOCUMENT SELECTION
  // ============================================================

  const applyDocumentSelection = () => {
    if (
      modalSelectedDocuments.length ===
      0
    ) {
      alert(
        "Please select at least one document."
      );

      return;
    }

    localStorage.setItem(
      "nexusai_selected_documents",
      JSON.stringify(
        modalSelectedDocuments
      )
    );

    if (
      modalSelectedDocuments.length ===
      1
    ) {
      localStorage.setItem(
        "nexusai_selected_document",
        modalSelectedDocuments[0]
      );
    } else {
      localStorage.removeItem(
        "nexusai_selected_document"
      );
    }

    if (onDocumentsChange) {
      onDocumentsChange(
        modalSelectedDocuments
      );
    }

    setMessages([]);

    setQuestion("");

    setShowDocumentModal(false);

    window.dispatchEvent(
      new Event(
        "nexusai-selected-documents-change"
      )
    );
  };

  // ============================================================
  // UPLOAD FILES
  // ============================================================

  const handleFileUpload = async (
    event
  ) => {
    const files =
      Array.from(
        event.target.files || []
      );

    if (files.length === 0) {
      return;
    }

    setShowPlusMenu(false);

    setUploading(true);

    const uploadedFilenames = [];

    try {
      for (const file of files) {
        const formData =
          new FormData();

        formData.append(
          "file",
          file
        );

        try {
          const response =
            await axios.post(
              "http://127.0.0.1:8000/upload",
              formData,
              {
                headers: {
                  "Content-Type":
                    "multipart/form-data",
                },
              }
            );

          const filename =
            response.data
              ?.filename;

          const message =
            response.data
              ?.message || "";

          if (
            filename &&
            (
              message
                .toLowerCase()
                .includes(
                  "success"
                ) ||
              response.status === 200
            )
          ) {
            uploadedFilenames.push(
              filename
            );
          }
        } catch (uploadError) {
          console.error(
            `Upload failed for ${file.name}:`,
            uploadError
          );
        }
      }

      if (
        uploadedFilenames.length ===
        0
      ) {
        alert(
          "No files were uploaded successfully."
        );

        return;
      }

      // Automatically use uploaded files
      localStorage.setItem(
        "nexusai_selected_documents",
        JSON.stringify(
          uploadedFilenames
        )
      );

      if (
        uploadedFilenames.length ===
        1
      ) {
        localStorage.setItem(
          "nexusai_selected_document",
          uploadedFilenames[0]
        );
      } else {
        localStorage.removeItem(
          "nexusai_selected_document"
        );
      }

      if (onDocumentsChange) {
        onDocumentsChange(
          uploadedFilenames
        );
      }

      setMessages([]);

      setQuestion("");

      window.dispatchEvent(
        new Event(
          "nexusai-selected-documents-change"
        )
      );

      if (
        uploadedFilenames.length ===
        1
      ) {
        alert(
          `${uploadedFilenames[0]} uploaded and selected.`
        );
      } else {
        alert(
          `${uploadedFilenames.length} files uploaded and selected.`
        );
      }
    } catch (error) {
      console.error(
        "Upload error:",
        error
      );

      alert(
        "File upload failed."
      );
    } finally {
      setUploading(false);

      if (
        fileInputRef.current
      ) {
        fileInputRef.current.value =
          "";
      }
    }
  };

  // ============================================================
  // OPEN FILE PICKER
  // ============================================================

  const openFilePicker = () => {
    setShowPlusMenu(false);

    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  // ============================================================
  // EXPLAIN ENTIRE DOCUMENT
  // ============================================================

  const explainEntireDocument = async () => {
    if (loading || uploading) return;

    if (activeDocuments.length === 0) {
      addMessage({ type: "ai", text: "📄 Please select a document first." });
      return;
    }

    const filename = activeDocuments[0];
    setLoading(true);

    addMessage({
      type: "user",
      text: `📖 Explain entire document: ${filename}`,
    });

    try {
      const response = await axios.post(
        "http://127.0.0.1:8000/document-summary",
        {
          question: "Explain the entire document in simple language.",
          filenames: [filename],
          filename,
        }
      );

      addMessage({
        type: "ai",
        text:
          response.data?.answer ||
          response.data?.error ||
          "No document explanation received.",
      });
    } catch (error) {
      console.error("Document explanation error:", error);
      addMessage({
        type: "ai",
        text: "❌ Unable to explain the entire document. Please check the backend and Gemini API connection.",
      });
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // VOICE INPUT
  // ============================================================

  const toggleVoiceInput = () => {
    if (loading || uploading) return;

    const SpeechRecognition =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert(
        "Voice input is not supported in this browser. Please use Chrome or Edge."
      );
      return;
    }

    // Stop an active recognition session.
    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
      return;
    }

    const recognition = new SpeechRecognition();

    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onresult = (event) => {
      let transcript = "";

      for (
        let index = event.resultIndex;
        index < event.results.length;
        index += 1
      ) {
        transcript += event.results[index][0].transcript;
      }

      const cleanedTranscript =
        transcript.trim();

      if (cleanedTranscript) {
        setQuestion(cleanedTranscript);
      }
    };

    recognition.onerror = (event) => {
      console.error(
        "Voice input error:",
        event.error
      );
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;
    recognition.start();
  };

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, []);

  // ============================================================
  // ASK QUESTION
  // ============================================================

  const askQuestion = async () => {
    if (
      !question.trim() ||
      loading
    ) {
      return;
    }


    const currentQuestion =
      question.trim();

    // Tell ChatWindow that the first real chat message has started.
    // ChatWindow uses this to move the composer from the centered
    // welcome position to the normal bottom position.
    window.dispatchEvent(
      new Event("nexusai-chat-started")
    );

    addMessage({
      type: "user",
      text: currentQuestion,
    });

    setQuestion("");

    setLoading(true);

    const requestBody = {
      question:
        currentQuestion,

      filenames:
        activeDocuments,

      filename:
        activeDocuments.length === 1
          ? activeDocuments[0]
          : null,
    };

    console.log(
      "=========================================="
    );

    console.log(
      "NEXUSAI CHAT REQUEST"
    );

    console.log(
      "Processing Mode:",
      processingMode
    );

    console.log(
      "Selected Documents:",
      activeDocuments
    );

    console.log(
      "Question:",
      currentQuestion
    );

    console.log(
      "Multi Document:",
      isMultiDocument
    );

    console.log(
      "=========================================="
    );

    // ==========================================================
    // LOCAL AI
    // ==========================================================

    if (
      processingMode === "local"
    ) {
      try {
        const response =
          await fetch(
            "http://127.0.0.1:8000/local-chat",
            {
              method: "POST",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body:
                JSON.stringify(
                  requestBody
                ),
            }
          );

        if (!response.ok) {
          throw new Error(
            `Local AI request failed: ${response.status}`
          );
        }

        if (!response.body) {
          throw new Error(
            "Streaming response is not supported."
          );
        }

        setMessages(
          (previousMessages) => [
            ...previousMessages,
            {
              type: "ai",
              text: "",
            },
          ]
        );

        const reader =
          response.body.getReader();

        const decoder =
          new TextDecoder(
            "utf-8"
          );

        let accumulatedText =
          "";

        while (true) {
          const {
            value,
            done,
          } =
            await reader.read();

          if (done) {
            break;
          }

          const chunk =
            decoder.decode(
              value,
              {
                stream: true,
              }
            );

          if (!chunk) {
            continue;
          }

          accumulatedText +=
            chunk;

          setMessages(
            (previousMessages) => {
              const updatedMessages =
                [
                  ...previousMessages,
                ];

              const lastIndex =
                updatedMessages.length -
                1;

              if (
                updatedMessages[
                  lastIndex
                ] &&
                updatedMessages[
                  lastIndex
                ].type === "ai"
              ) {
                updatedMessages[
                  lastIndex
                ] = {
                  ...updatedMessages[
                    lastIndex
                  ],

                  text:
                    accumulatedText,
                };
              }

              return updatedMessages;
            }
          );
        }

        accumulatedText +=
          decoder.decode();

        const finalAnswer =
          accumulatedText.trim();

        setMessages(
          (previousMessages) => {
            const updatedMessages =
              [
                ...previousMessages,
              ];

            const lastIndex =
              updatedMessages.length -
              1;

            if (
              updatedMessages[
                lastIndex
              ] &&
              updatedMessages[
                lastIndex
              ].type === "ai"
            ) {
              updatedMessages[
                lastIndex
              ] = {
                ...updatedMessages[
                  lastIndex
                ],

                text:
                  finalAnswer ||
                  "No answer received.",
              };
            }

            saveMessages(
              updatedMessages
            );

            return updatedMessages;
          }
        );
      } catch (error) {
        console.error(
          "Local AI error:",
          error
        );

        addMessage({
          type: "ai",
          text:
            "❌ Local AI is unavailable. Please make sure Ollama and Qwen3 are running.",
        });
      } finally {
        setLoading(false);
      }

      return;
    }

    // ==========================================================
    // CLOUD AI
    // ==========================================================

    try {
      const normalizedQuestion = currentQuestion.toLowerCase().trim();

      const isDocumentOverviewQuestion =
        normalizedQuestion === "what is the document about" ||
        normalizedQuestion === "what is this document about" ||
        normalizedQuestion === "what's the document about" ||
        normalizedQuestion === "what's this document about" ||
        normalizedQuestion.includes("explain the entire document") ||
        normalizedQuestion.includes("explain entire document") ||
        normalizedQuestion.includes("explain this document") ||
        normalizedQuestion.includes("summarize the entire document") ||
        normalizedQuestion.includes("summarize this document") ||
        normalizedQuestion.includes("give me a summary of the document") ||
        normalizedQuestion.includes("give me an overview of the document");

      if (isDocumentOverviewQuestion) {
        // The current backend summary endpoint processes one document.
        const filename = activeDocuments[0];

        const summaryResponse = await axios.post(
          "http://127.0.0.1:8000/document-summary",
          {
            question: currentQuestion,
            filenames: [filename],
            filename,
          }
        );

        addMessage({
          type: "ai",
          text:
            summaryResponse.data?.answer ||
            summaryResponse.data?.error ||
            "No document explanation received.",
        });
      } else {
        // Normal RAG chat remains unchanged.
        const response = await axios.post(
          "http://127.0.0.1:8000/chat",
          requestBody
        );

        addMessage({
          type: "ai",
          text:
            response.data.answer ||
            response.data.error ||
            "No answer received.",
        });
      }
    } catch (error) {
      console.error("Cloud chat error:", error);

      addMessage({
        type: "ai",
        text: "❌ Cloud AI is unavailable. Please check the Gemini API connection.",
      });
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // ENTER KEY
  // ============================================================

  const handleKeyDown = (
    event
  ) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      askQuestion();
    }
  };

  // ============================================================
  // CLEAR CHAT
  // ============================================================

  const clearChat = () => {
    setMessages([]);

    if (
      activeDocuments.length ===
      0
    ) {
      return;
    }

    try {
      const storedChats =
        localStorage.getItem(
          CHAT_STORAGE_KEY
        );

      if (!storedChats) {
        return;
      }

      const allChats =
        JSON.parse(
          storedChats
        );

      const historyKey =
        getChatHistoryKey();

      delete allChats[
        historyKey
      ];

      localStorage.setItem(
        CHAT_STORAGE_KEY,
        JSON.stringify(
          allChats
        )
      );
    } catch (error) {
      console.error(
        "Failed to clear chat history:",
        error
      );
    }
  };

  // ============================================================
  // CHAT MARKDOWN RENDERER
  // ============================================================

  const renderChatMarkdown = (value) => {
    if (!value) return null;

    const lines = String(value).split("\n");
    const elements = [];
    let listItems = [];

    const flushList = () => {
      if (!listItems.length) return;

      elements.push(
        <ul
          key={`list-${elements.length}`}
          style={{
            margin: "8px 0 12px 20px",
            padding: 0,
          }}
        >
          {listItems.map((item, itemIndex) => (
            <li
              key={itemIndex}
              style={{
                marginBottom: "6px",
                paddingLeft: "4px",
              }}
            >
              {formatChatInline(item)}
            </li>
          ))}
        </ul>
      );

      listItems = [];
    };

    lines.forEach((rawLine, lineIndex) => {
      const line = rawLine.trim();

      if (!line) {
        flushList();
        elements.push(
          <div key={`space-${lineIndex}`} style={{ height: "8px" }} />
        );
        return;
      }

      if (/^[-*]\s+/.test(line)) {
        listItems.push(line.replace(/^[-*]\s+/, ""));
        return;
      }

      flushList();

      if (/^###\s+/.test(line)) {
        elements.push(
          <h4
            key={`h4-${lineIndex}`}
            style={{
              margin: "16px 0 7px",
              fontSize: "15px",
              lineHeight: 1.45,
              fontWeight: 800,
            }}
          >
            {formatChatInline(line.replace(/^###\s+/, ""))}
          </h4>
        );
        return;
      }

      if (/^##\s+/.test(line)) {
        elements.push(
          <h3
            key={`h3-${lineIndex}`}
            style={{
              margin: "18px 0 8px",
              fontSize: "17px",
              lineHeight: 1.45,
              fontWeight: 800,
            }}
          >
            {formatChatInline(line.replace(/^##\s+/, ""))}
          </h3>
        );
        return;
      }

      if (/^#\s+/.test(line)) {
        elements.push(
          <h2
            key={`h2-${lineIndex}`}
            style={{
              margin: "18px 0 8px",
              fontSize: "19px",
              lineHeight: 1.4,
              fontWeight: 800,
            }}
          >
            {formatChatInline(line.replace(/^#\s+/, ""))}
          </h2>
        );
        return;
      }

      elements.push(
        <p
          key={`p-${lineIndex}`}
          style={{
            margin: "0 0 9px",
            lineHeight: 1.7,
          }}
        >
          {formatChatInline(line)}
        </p>
      );
    });

    flushList();
    return elements;
  };

  const formatChatInline = (value) => {
    const parts = String(value).split(
      /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g
    );

    return parts.map((part, index) => {
      if (
        part.startsWith("**") &&
        part.endsWith("**") &&
        part.length > 4
      ) {
        return (
          <strong key={index}>
            {part.slice(2, -2)}
          </strong>
        );
      }

      if (
        part.startsWith("`") &&
        part.endsWith("`") &&
        part.length > 2
      ) {
        return (
          <code
            key={index}
            style={{
              padding: "2px 6px",
              borderRadius: "5px",
              background: "var(--nx-bg)",
              border: "1px solid var(--nx-border)",
              fontSize: "0.9em",
            }}
          >
            {part.slice(1, -1)}
          </code>
        );
      }

      if (
        part.startsWith("*") &&
        part.endsWith("*") &&
        !part.startsWith("**") &&
        part.length > 2
      ) {
        return (
          <em key={index}>
            {part.slice(1, -1)}
          </em>
        );
      }

      return <span key={index}>{part}</span>;
    });
  };

  // ============================================================
  // FILTER DOCUMENTS
  // ============================================================

  const filteredDocuments =
    documents.filter(
      (document) =>
        document.filename
          .toLowerCase()
          .includes(
            documentSearch.toLowerCase()
          )
    );

  // ============================================================
  // RENDER
  // ============================================================

  return (
    <div
      style={{
        marginTop: "0",
      }}
    >
      {/* ========================================================
          DOCUMENT ANALYSIS STATUS
          Single-document "Asking about..." and AI provider badges
          are intentionally hidden for a cleaner chat UI.
      ======================================================== */}

      {isMultiDocument && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "4px",
            marginBottom: "15px",
            padding: "10px 13px",
            background: "#fefce8",
            border: "1px solid #fde68a",
            borderRadius: "8px",
            color: "#854d0e",
            fontSize: "13px",
          }}
        >
          <div style={{ fontWeight: "600" }}>
            📚 Analyzing {activeDocuments.length} documents
          </div>

          {activeDocuments.map((filename) => (
            <div
              key={filename}
              style={{
                fontSize: "12px",
                lineHeight: "1.4",
              }}
            >
              • {filename}
            </div>
          ))}
        </div>
      )}

      {/* ========================================================
          CHAT HISTORY
      ======================================================== */}

      <div
        style={{
          maxHeight:
            "500px",
          overflowY:
            "auto",
          padding: "5px",
        }}
      >
        {messages.map(
          (
            message,
            index
          ) => (
            <div
              key={
                index
              }
              style={{
                display:
                  "flex",
                justifyContent:
                  message.type ===
                  "user"
                    ? "flex-end"
                    : "flex-start",
                marginBottom:
                  "15px",
              }}
            >
              <div
                style={{
                  maxWidth:
                    "75%",
                  padding:
                    "14px 18px",
                  borderRadius:
                    "14px",
                  background:
                    message.type ===
                    "user"
                      ? "var(--nx-primary)"
                      : "var(--nx-surface)",
                  color:
                    message.type ===
                    "user"
                      ? "var(--nx-surface)"
                      : "var(--nx-text)",
                  boxShadow:
                    message.type ===
                    "ai"
                      ? "0 2px 8px rgba(0,0,0,0.08)"
                      : "0 2px 8px rgba(37,99,235,0.2)",
                  lineHeight:
                    "1.6",
                  whiteSpace:
                    "pre-wrap",
                }}
              >
                <div
                  style={{
                    fontWeight:
                      "700",
                    marginBottom:
                      "6px",
                  }}
                >
                  {message.type ===
                  "user"
                    ? "👤 You"
                    : "🤖 AI Assistant"}
                </div>

                <div>
                  {message.type === "ai"
                    ? renderChatMarkdown(message.text)
                    : message.text}

                  {loading &&
                    message.type ===
                      "ai" &&
                    index ===
                      messages.length -
                        1 && (
                      <span
                        style={{
                          display:
                            "inline-block",
                          marginLeft:
                            "3px",
                          animation:
                            "blink 1s infinite",
                        }}
                      >
                        ▌
                      </span>
                    )}
                </div>
              </div>
            </div>
          )
        )}

        {loading && (
          <div
            style={{
              display:
                "flex",
              justifyContent:
                "flex-start",
              marginBottom:
                "15px",
            }}
          >
            <div
              style={{
                background:
                  "var(--nx-surface)",
                color:
                  "var(--nx-text-muted)",
                padding:
                  "14px 18px",
                borderRadius:
                  "14px",
                boxShadow:
                  "0 2px 8px rgba(0,0,0,0.08)",
              }}
            >
              {processingMode ===
              "local"
                ? "Generating..."
                : "Generating..."}
            </div>
          </div>
        )}
      </div>

      {/* ========================================================
          INPUT AREA
      ======================================================== */}

      {isListening && (
       <div
  style={{
    marginTop: "10px",
    marginBottom: "-5px",
    color: "#60a5fa",
    fontSize: "13px",
    fontWeight: "600",
    textAlign: "center",
  }}
>
  Listening… speak your question
</div>
      )}

      <div
        style={{
          display: "flex",
          gap: "10px",
          alignItems: "center",
          marginTop: "15px",
          position: "relative",
          width: "100%",
        }}
      >
        {/* ======================================================
            HIDDEN FILE INPUT
        ====================================================== */}

        <input
          ref={
            fileInputRef
          }
          type="file"
          multiple
          accept="*/*"
          onChange={
            handleFileUpload
          }
          style={{
            display:
              "none",
          }}
        />

        {/* ======================================================
            PLUS BUTTON
        ====================================================== */}

        <button
          type="button"
          onClick={() =>
            setShowPlusMenu(
              (previous) =>
                !previous
            )
          }
          disabled={
            loading ||
            uploading
          }
          style={{
            width: "46px",
            height: "46px",
            flexShrink: 0,
            border:
              "1px solid var(--nx-border)",
            borderRadius: "50%",
            background: "var(--nx-bg)",
            color: "var(--nx-primary)",
            fontSize: "17px",
            fontWeight:
              "700",
            cursor:
              loading ||
              uploading
                ? "not-allowed"
                : "pointer",
          }}
          title="Add files or documents"
        >
          +
        </button>

        {/* ======================================================
            PLUS MENU
        ====================================================== */}

        {showPlusMenu && (
          <div
            style={{
              position:
                "absolute",
              bottom:
                "58px",
              left: "0",
              width:
                "250px",
              background:
                "var(--nx-surface)",
              border:
                "1px solid var(--nx-border)",
              borderRadius:
                "12px",
              boxShadow:
                "0 8px 25px rgba(0,0,0,0.15)",
              overflow:
                "hidden",
              zIndex:
                1000,
            }}
          >
            <button
              type="button"
              onClick={
                openFilePicker
              }
              style={{
                width:
                  "100%",
                padding:
                  "14px 16px",
                border:
                  "none",
                background:
                  "var(--nx-surface)",
                textAlign:
                  "left",
                cursor:
                  "pointer",
                fontSize:
                  "14px",
                color:
                  "var(--nx-text)",
              }}
            >
              📄{" "}
              <strong>
                Upload PDF
              </strong>
              <div
                style={{
                  marginTop:
                    "3px",
                  marginLeft:
                    "25px",
                  color:
                    "var(--nx-text-muted)",
                  fontSize:
                    "12px",
                }}
              >
                Upload a PDF directly
              </div>
            </button>

            <button
              type="button"
              onClick={
                openDocumentModal
              }
              style={{
                width:
                  "100%",
                padding:
                  "14px 16px",
                border:
                  "none",
                borderTop:
                  "1px solid var(--nx-surface-2)",
                background:
                  "var(--nx-surface)",
                textAlign:
                  "left",
                cursor:
                  "pointer",
                fontSize:
                  "14px",
                color:
                  "var(--nx-text)",
              }}
            >
              📚{" "}
              <strong>
                Select Document
              </strong>
              <div
                style={{
                  marginTop:
                    "3px",
                  marginLeft:
                    "25px",
                  color:
                    "var(--nx-text-muted)",
                  fontSize:
                    "12px",
                }}
              >
                Choose existing documents
              </div>
            </button>

            <button
              type="button"
              onClick={
                openFilePicker
              }
              style={{
                width:
                  "100%",
                padding:
                  "14px 16px",
                border:
                  "none",
                borderTop:
                  "1px solid var(--nx-surface-2)",
                background:
                  "var(--nx-surface)",
                textAlign:
                  "left",
                cursor:
                  "pointer",
                fontSize:
                  "14px",
                color:
                  "var(--nx-text)",
              }}
            >
              🖼️{" "}
              <strong>
                Photos & Files
              </strong>
              <div
                style={{
                  marginTop:
                    "3px",
                  marginLeft:
                    "25px",
                  color:
                    "var(--nx-text-muted)",
                  fontSize:
                    "12px",
                }}
              >
                Choose one or more files
              </div>
            </button>
          </div>
        )}

        {/* ======================================================
            QUESTION INPUT
        ====================================================== */}

        <input
          type="text"
          placeholder={
            activeDocuments.length >
            0
              ? isMultiDocument
                ? "Compare, summarize, or ask anything..."
                : "Ask a question about your document..."
              : "Type your question or tap the mic..."
          }
          value={
            question
          }
          onChange={(e) =>
            setQuestion(
              e.target.value
            )
          }
          onKeyDown={
            handleKeyDown
          }
          disabled={
            loading ||
            uploading
          }
          style={{
            flex: 1,
            padding: "13px 16px",
            fontSize: "15px",
            border: "1px solid #d7dee8",
            borderRadius: "14px",
            outline:
              "none",
            color:
              "var(--nx-text)",
            background: "var(--nx-surface)",
            boxShadow: "inset 0 1px 2px rgba(15,23,42,0.03)",
            transition: "border-color 0.2s ease, box-shadow 0.2s ease",
          }}
        />

        {/* ======================================================
            VOICE INPUT
        ====================================================== */}

        <button
  type="button"
  onClick={toggleVoiceInput}
  disabled={loading || uploading}
  title={isListening ? "Stop voice input" : "Voice input"}
  aria-label={isListening ? "Stop voice input" : "Voice input"}
  style={{
    width: "46px",
    height: "46px",
    flexShrink: 0,
    border: "1px solid var(--nx-border)",
    borderRadius: "50%",
    background: "var(--nx-primary-soft, #172b4d)",
    color: "#ffffff",
    cursor:
      loading || uploading
        ? "not-allowed"
        : "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 0,
  }}
>
  <FaMicrophone
    size={20}
    aria-hidden="true"
  />
</button>
        

        {/* ======================================================
            SEND
        ====================================================== */}

        <button
          type="button"
          onClick={
            askQuestion
          }
          disabled={
            loading ||
            uploading ||
            !question.trim()
          }
          style={{
            width: "46px",
            height: "46px",
            padding: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background:
              loading ||
              uploading ||
              !question.trim()
                ? "var(--nx-text-muted)"
                : "var(--nx-primary)",
            color:
              "var(--nx-surface)",
            border:
              "none",
            borderRadius:
              "10px",
            fontSize:
              "16px",
            fontWeight:
              "600",
           cursor:
  loading ||
  uploading ||
  !question.trim()
    ? "not-allowed"
    : "pointer",
          }}
        >
          {uploading ? "…" : loading ? "…" : <FaArrowUp size={16} />}
        </button>
      </div>

      {/* ========================================================
          CLEAR CHAT
      ======================================================== */}

      {messages.length >
        0 && (
        <button
          type="button"
          onClick={
            clearChat
          }
          style={{
            marginTop:
              "12px",
            padding:
              "8px 14px",
            background:
              "var(--nx-surface)",
            color:
              "#dc2626",
            border:
              "1px solid #fecaca",
            borderRadius:
              "8px",
            cursor:
              "pointer",
          }}
        >
          🗑️ Clear Chat
        </button>
      )}

      {/* ========================================================
          DOCUMENT SELECTION MODAL
      ======================================================== */}

      {showDocumentModal && (
        <div
          style={{
            position:
              "fixed",
            inset: 0,
            background:
              "rgba(15,23,42,0.55)",
            display:
              "flex",
            alignItems:
              "center",
            justifyContent:
              "center",
            zIndex:
              2000,
            padding:
              "20px",
          }}
          onClick={() =>
            setShowDocumentModal(
              false
            )
          }
        >
          <div
            onClick={(event) =>
              event.stopPropagation()
            }
            style={{
              width:
                "min(600px, 100%)",
              maxHeight:
                "80vh",
              background:
                "var(--nx-surface)",
              borderRadius:
                "14px",
              boxShadow:
                "0 20px 50px rgba(0,0,0,0.25)",
              display:
                "flex",
              flexDirection:
                "column",
              overflow:
                "hidden",
            }}
          >
            {/* MODAL HEADER */}

            <div
              style={{
                padding:
                  "18px 20px",
                borderBottom:
                  "1px solid var(--nx-border)",
                display:
                  "flex",
                justifyContent:
                  "space-between",
                alignItems:
                  "center",
              }}
            >
              <div>
                <h3
                  style={{
                    margin: 0,
                    color:
                      "var(--nx-text)",
                  }}
                >
                  📚 Select Documents
                </h3>

                <p
                  style={{
                    margin:
                      "5px 0 0 0",
                    color:
                      "var(--nx-text-muted)",
                    fontSize:
                      "13px",
                  }}
                >
                  Select one or more documents
                  for this chat.
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  setShowDocumentModal(
                    false
                  )
                }
                style={{
                  border:
                    "none",
                  background:
                    "var(--nx-surface-2)",
                  borderRadius:
                    "50%",
                  width:
                    "34px",
                  height:
                    "34px",
                  cursor:
                    "pointer",
                  fontSize:
                    "18px",
                }}
              >
                ×
              </button>
            </div>

            {/* SEARCH */}

            <div
              style={{
                padding:
                  "15px 20px",
                borderBottom:
                  "1px solid var(--nx-border)",
              }}
            >
              <input
                type="text"
                placeholder="🔍 Search documents..."
                value={
                  documentSearch
                }
                onChange={(e) =>
                  setDocumentSearch(
                    e.target.value
                  )
                }
                style={{
                  width:
                    "100%",
                  boxSizing:
                    "border-box",
                  padding:
                    "11px 13px",
                  border:
                    "1px solid var(--nx-border)",
                  borderRadius:
                    "8px",
                  outline:
                    "none",
                }}
              />
            </div>

            {/* DOCUMENT LIST */}

            <div
              style={{
                flex: 1,
                overflowY:
                  "auto",
                padding:
                  "15px 20px",
              }}
            >
              {loadingDocuments ? (
                <div
                  style={{
                    textAlign:
                      "center",
                    padding:
                      "30px",
                    color:
                      "var(--nx-text-muted)",
                  }}
                >
                  Loading documents...
                </div>
              ) : filteredDocuments.length ===
                0 ? (
                <div
                  style={{
                    textAlign:
                      "center",
                    padding:
                      "30px",
                    color:
                      "var(--nx-text-muted)",
                  }}
                >
                  No documents found.
                </div>
              ) : (
                filteredDocuments.map(
                  (document) => {
                    const isSelected =
                      modalSelectedDocuments.includes(
                        document.filename
                      );

                    return (
                      <label
                        key={
                          document.filename
                        }
                        style={{
                          display:
                            "flex",
                          alignItems:
                            "center",
                          gap:
                            "12px",
                          padding:
                            "13px",
                          marginBottom:
                            "8px",
                          background:
                            isSelected
                              ? "var(--nx-primary-soft)"
                              : "var(--nx-bg)",
                          border:
                            isSelected
                              ? "2px solid var(--nx-primary)"
                              : "1px solid var(--nx-border)",
                          borderRadius:
                            "9px",
                          cursor:
                            "pointer",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={
                            isSelected
                          }
                          onChange={() =>
                            toggleModalDocument(
                              document.filename
                            )
                          }
                          style={{
                            width:
                              "18px",
                            height:
                              "18px",
                            cursor:
                              "pointer",
                          }}
                        />

                        <span
                          style={{
                            color:
                              "var(--nx-text)",
                            fontWeight:
                              "600",
                            fontSize:
                              "14px",
                            wordBreak:
                              "break-word",
                          }}
                        >
                          📄{" "}
                          {
                            document.filename
                          }
                        </span>
                      </label>
                    );
                  }
                )
              )}
            </div>

            {/* MODAL FOOTER */}

            <div
              style={{
                padding:
                  "15px 20px",
                borderTop:
                  "1px solid var(--nx-border)",
                display:
                  "flex",
                justifyContent:
                  "space-between",
                alignItems:
                  "center",
                gap:
                  "10px",
              }}
            >
              <div
                style={{
                  color:
                    "var(--nx-text-muted)",
                  fontSize:
                    "13px",
                }}
              >
                {modalSelectedDocuments.length}{" "}
                selected
              </div>

              <div
                style={{
                  display:
                    "flex",
                  gap:
                    "8px",
                }}
              >
                <button
                  type="button"
                  onClick={() =>
                    setShowDocumentModal(
                      false
                    )
                  }
                  style={{
                    padding:
                      "10px 15px",
                    background:
                      "var(--nx-surface)",
                    color:
                      "var(--nx-text-secondary)",
                    border:
                      "1px solid var(--nx-border)",
                    borderRadius:
                      "8px",
                    cursor:
                      "pointer",
                    fontWeight:
                      "600",
                  }}
                >
                  Cancel
                </button>

                <button
                  type="button"
                  onClick={
                    applyDocumentSelection
                  }
                  disabled={
                    modalSelectedDocuments.length ===
                    0
                  }
                  style={{
                    padding:
                      "10px 17px",
                    background:
                      modalSelectedDocuments.length >
                      0
                        ? "var(--nx-primary)"
                        : "var(--nx-text-muted)",
                    color:
                      "var(--nx-surface)",
                    border:
                      "none",
                    borderRadius:
                      "8px",
                    cursor:
                      modalSelectedDocuments.length >
                      0
                        ? "pointer"
                        : "not-allowed",
                    fontWeight:
                      "700",
                  }}
                >
                  Select & Chat
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================
          BLINK ANIMATION
      ======================================================== */}

      <style>
        {`
          @keyframes blink {
            0% {
              opacity: 1;
            }

            50% {
              opacity: 0;
            }

            100% {
              opacity: 1;
            }
          }
        `}
      </style>
    </div>
  );
}

export default ChatInput;