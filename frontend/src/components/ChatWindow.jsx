import { useState, useEffect, useRef, useCallback } from "react";
import api, { API_BASE_URL, getAuthHeaders } from "../api/client";
import {
  FaPaperPlane,
  FaMicrophone,
  FaPlus,
  FaTrash,
  FaTimes,
  FaBookOpen,
  FaFileAlt,
  FaCloud,
  FaDesktop,
  FaCopy,
  FaCheck,
  FaRedo,
  FaStop,
  FaArrowDown,
  FaExclamationTriangle,
  FaEdit,
  FaBars,
  FaShieldAlt,
  FaExternalLinkAlt,
} from "react-icons/fa";
import MarkdownRenderer from "./MarkdownRenderer";

const MODE_STORAGE_KEY = "nexusai_processing_mode";
const HISTORY_SIDEBAR_STORAGE_KEY = "nexusai_chat_history_open";
const MAX_UPLOAD_SIZE_MB = 100;
const MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024;

function ChatWindow() {
  // ----------------------------------------------------
  // State: Conversations & Persistence
  // ----------------------------------------------------
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [activeConversationTitle, setActiveConversationTitle] = useState("");
  const [loadingConversations, setLoadingConversations] = useState(false);
  const [conversationLoadError, setConversationLoadError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    try {
      const saved = localStorage.getItem(HISTORY_SIDEBAR_STORAGE_KEY);
      if (saved !== null) {
        return saved === "true";
      }
    } catch {
      // ignore
    }
    if (typeof window !== "undefined") {
      return window.innerWidth >= 1024;
    }
    return true;
  });

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(HISTORY_SIDEBAR_STORAGE_KEY, String(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  // Rename modal / inline state
  const [editingConvId, setEditingConvId] = useState(null);
  const [editingTitleText, setEditingTitleText] = useState("");
  const [isRenaming, setIsRenaming] = useState(false);

  // Delete modal state
  const [deletingConv, setDeletingConv] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // ----------------------------------------------------
  // State: Documents & Context
  // ----------------------------------------------------
  const [selectedDocuments, setSelectedDocuments] = useState(() => {
    try {
      const saved = localStorage.getItem("nexusai_selected_documents");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) return parsed;
      }
      const single = localStorage.getItem("nexusai_selected_document");
      return single ? [single] : [];
    } catch {
      return [];
    }
  });

  const [availableDocuments, setAvailableDocuments] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [docLoadError, setDocLoadError] = useState("");
  const [showDocModal, setShowDocModal] = useState(false);
  const [docSearchQuery, setDocSearchQuery] = useState("");
  const [modalSelectedDocs, setModalSelectedDocs] = useState([]);

  // ----------------------------------------------------
  // State: AI Processing Mode
  // ----------------------------------------------------
  const [processingMode, setProcessingMode] = useState(() => {
    const saved = localStorage.getItem(MODE_STORAGE_KEY);
    return saved === "local" ? "local" : "cloud";
  });

  // ----------------------------------------------------
  // State: Chat Messages & Input
  // ----------------------------------------------------
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStatusText, setLoadingStatusText] = useState("Thinking...");
  const [uploading, setUploading] = useState(false);
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const [copiedMessageIndex, setCopiedMessageIndex] = useState(null);
  const [copyToast, setCopyToast] = useState({ show: false, message: "", isError: false });
  const copyToastTimerRef = useRef(null);
  const [activeEvidence, setActiveEvidence] = useState(null);



  // ----------------------------------------------------
  // State: Scrolling & Autoscroll Management
  // ----------------------------------------------------
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const userScrolledUpRef = useRef(false);

  // ----------------------------------------------------
  // State: Voice Input & DOM Refs
  // ----------------------------------------------------
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef(null);
  const fileInputRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const messagesEndRef = useRef(null);
  const inputFieldRef = useRef(null);
  const abortControllerRef = useRef(null);

  // ----------------------------------------------------
  // Auto-scroll logic (Precision scroll without layout fight)
  // ----------------------------------------------------
  const scrollToBottom = useCallback((behavior = "smooth") => {
    const container = messagesContainerRef.current;
    if (!container) return;

    if (behavior === "auto" || behavior === "instant") {
      container.scrollTop = container.scrollHeight;
    } else {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: "smooth",
      });
    }
  }, []);

  const handleContainerScroll = useCallback(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;

    const scrolledUp = distanceFromBottom > 80;
    userScrolledUpRef.current = scrolledUp;
    setShowScrollBottom(scrolledUp);
  }, []);

  useEffect(() => {
    if (!userScrolledUpRef.current) {
      scrollToBottom("auto");
    }
  }, [messages, loading, scrollToBottom]);

  // ----------------------------------------------------
  // Load User Conversations
  // ----------------------------------------------------
  const fetchConversations = useCallback(async () => {
    setLoadingConversations(true);
    setConversationLoadError("");
    try {
      const response = await api.get("/conversations");
      setConversations(Array.isArray(response.data) ? response.data : []);
    } catch (err) {
      console.warn("Could not load conversations:", err);
      setConversationLoadError("Unable to load conversations.");
      setConversations([]);
    } finally {
      setLoadingConversations(false);
    }
  }, []);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // ----------------------------------------------------
  // Load Single Conversation by ID
  // ----------------------------------------------------
  const selectConversation = async (convId) => {
    if (loading) return;
    try {
      const response = await api.get(`/conversations/${convId}`);
      const conv = response.data;
      if (!conv) return;

      setActiveConversationId(conv.id);
      setActiveConversationTitle(conv.title || "Conversation");

      // Format messages
      const formatted = (conv.messages || []).map((m) => ({
        id: m.id,
        type: m.role === "user" ? "user" : "ai",
        text: m.content,
        timestamp: m.created_at,
        sources: conv.documents || [],
        citations: m.citations || [],
        grounding: m.grounding || null,
        queryUsed: m.role === "user" ? m.content : "",
      }));
      setMessages(formatted);

      // Restore selected documents if any
      const docs = conv.documents || [];
      setSelectedDocuments(docs);
      localStorage.setItem("nexusai_selected_documents", JSON.stringify(docs));

      userScrolledUpRef.current = false;
      setShowScrollBottom(false);

      // Auto-collapse sidebar on mobile/narrow screens when selecting a conversation
      if (typeof window !== "undefined" && window.innerWidth <= 900) {
        setSidebarOpen(false);
      }

      setTimeout(() => {
        scrollToBottom("instant");
      }, 30);
    } catch (err) {
      console.error("Failed to restore conversation:", err);
      alert("Unable to open conversation. It may have been deleted.");
      fetchConversations();
    }
  };

  // ----------------------------------------------------
  // Create / Start New Chat
  // ----------------------------------------------------
  const handleNewChat = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setLoading(false);
    setActiveConversationId(null);
    setActiveConversationTitle("");
    setMessages([]);
    setQuestion("");
    userScrolledUpRef.current = false;
    setShowScrollBottom(false);

    // Auto-collapse sidebar on mobile/narrow screens
    if (typeof window !== "undefined" && window.innerWidth <= 900) {
      setSidebarOpen(false);
    }
  };

  // ----------------------------------------------------
  // Rename Conversation Handler
  // ----------------------------------------------------
  const handleStartRename = (e, conv) => {
    e.stopPropagation();
    setEditingConvId(conv.id);
    setEditingTitleText(conv.title);
  };

  const handleSaveRename = async (e) => {
    if (e) e.preventDefault();
    if (!editingConvId || !editingTitleText.trim() || isRenaming) return;

    setIsRenaming(true);
    try {
      await api.patch(`/conversations/${editingConvId}`, {
        title: editingTitleText.trim(),
      });
      setConversations((prev) =>
        prev.map((c) =>
          c.id === editingConvId ? { ...c, title: editingTitleText.trim() } : c
        )
      );
      if (activeConversationId === editingConvId) {
        setActiveConversationTitle(editingTitleText.trim());
      }
      setEditingConvId(null);
      setEditingTitleText("");
    } catch (err) {
      console.error("Failed to rename conversation:", err);
      alert("Failed to rename conversation. Please try again.");
    } finally {
      setIsRenaming(false);
    }
  };

  // ----------------------------------------------------
  // Delete Conversation Handler
  // ----------------------------------------------------
  const handleConfirmDelete = async () => {
    if (!deletingConv || isDeleting) return;

    setIsDeleting(true);
    const targetId = deletingConv.id;
    try {
      await api.delete(`/conversations/${targetId}`);
      setConversations((prev) => prev.filter((c) => c.id !== targetId));
      if (activeConversationId === targetId) {
        handleNewChat();
      }
      setDeletingConv(null);
    } catch (err) {
      console.error("Failed to delete conversation:", err);
      alert("Failed to delete conversation. Please try again.");
    } finally {
      setIsDeleting(false);
    }
  };

  // ----------------------------------------------------
  // Load Workspace Documents
  // ----------------------------------------------------
  const fetchWorkspaceDocuments = useCallback(async () => {
    setLoadingDocs(true);
    setDocLoadError("");
    try {
      const response = await api.get("/documents");
      const docs = response.data?.documents || [];
      setAvailableDocuments(docs);
    } catch (err) {
      console.warn("Could not load documents:", err);
      setDocLoadError("Unable to load workspace documents.");
      setAvailableDocuments([]);
    } finally {
      setLoadingDocs(false);
    }
  }, []);

  useEffect(() => {
    fetchWorkspaceDocuments();
  }, [fetchWorkspaceDocuments]);

  // ----------------------------------------------------
  // Mode Change Listener
  // ----------------------------------------------------
  useEffect(() => {
    const handleModeChange = () => {
      const saved = localStorage.getItem(MODE_STORAGE_KEY);
      setProcessingMode(saved === "local" ? "local" : "cloud");
    };
    window.addEventListener("nexusai-mode-change", handleModeChange);
    return () => window.removeEventListener("nexusai-mode-change", handleModeChange);
  }, []);

  // ----------------------------------------------------
  // Synchronize document selection changes
  // ----------------------------------------------------
  const updateSelectedDocuments = (newSelection) => {
    setSelectedDocuments(newSelection);
    localStorage.setItem("nexusai_selected_documents", JSON.stringify(newSelection));
    if (newSelection.length === 1) {
      localStorage.setItem("nexusai_selected_document", newSelection[0]);
    } else {
      localStorage.removeItem("nexusai_selected_document");
    }
    window.dispatchEvent(new Event("nexusai-selected-documents-change"));
  };

  const removeSelectedDocument = (filenameToRemove) => {
    const updated = selectedDocuments.filter((f) => f !== filenameToRemove);
    updateSelectedDocuments(updated);
  };

  const clearAllSelectedDocuments = () => {
    updateSelectedDocuments([]);
  };

  // ----------------------------------------------------
  // Auto-resize textarea
  // ----------------------------------------------------
  const adjustTextareaHeight = () => {
    const textarea = inputFieldRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      const newHeight = Math.min(Math.max(textarea.scrollHeight, 44), 160);
      textarea.style.height = `${newHeight}px`;
    }
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [question]);

  // ----------------------------------------------------
  // Mode Switch Toggle
  // ----------------------------------------------------
  const handleToggleMode = () => {
    const nextMode = processingMode === "cloud" ? "local" : "cloud";
    setProcessingMode(nextMode);
    localStorage.setItem(MODE_STORAGE_KEY, nextMode);
    window.dispatchEvent(new Event("nexusai-mode-change"));
  };

  // ----------------------------------------------------
  // Copy Answer
  // ----------------------------------------------------
  const handleCopyAnswer = async (textToCopy, index) => {
    if (copyToastTimerRef.current) clearTimeout(copyToastTimerRef.current);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(textToCopy);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = textToCopy;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setCopiedMessageIndex(index);
      setCopyToast({ show: true, message: "Message copied", isError: false });
      copyToastTimerRef.current = setTimeout(() => {
        setCopiedMessageIndex(null);
        setCopyToast({ show: false, message: "", isError: false });
      }, 1800);
    } catch (err) {
      console.error("Failed to copy answer to clipboard:", err);
      setCopyToast({ show: true, message: "Unable to copy message", isError: true });
      copyToastTimerRef.current = setTimeout(() => {
        setCopyToast({ show: false, message: "", isError: false });
      }, 2200);
    }
  };



  // ----------------------------------------------------
  // Stop Generating
  // ----------------------------------------------------
  const handleStopGenerating = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setLoading(false);
    setLoadingStatusText("Generation stopped.");
  };

  // ----------------------------------------------------
  // Document Full Explanation (Integrated into Conversation Flow)
  // ----------------------------------------------------
  const handleExplainDocument = async () => {
    if (selectedDocuments.length === 0 || loading) return;

    const targetDoc = selectedDocuments[0];
    const promptText = "Explain the document";

    // 1. Append user message to conversation
    const userMessage = {
      type: "user",
      text: promptText,
      timestamp: new Date().toISOString(),
    };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);

    userScrolledUpRef.current = false;
    setShowScrollBottom(false);
    setLoading(true);
    setLoadingStatusText(`Analyzing and explaining ${targetDoc}...`);

    setTimeout(() => {
      scrollToBottom("smooth");
    }, 20);

    try {
      const response = await api.post("/document-summary", {
        question: promptText,
        filenames: [targetDoc],
        filename: targetDoc,
        conversation_id: activeConversationId,
      });

      const data = response.data;
      const answer = data.answer || "No structured explanation could be generated.";

      if (data.conversation_id) {
        setActiveConversationId(data.conversation_id);
        if (data.conversation_title) {
          setActiveConversationTitle(data.conversation_title);
        }
      }

      const aiMessage = {
        type: "ai",
        text: answer,
        sources: [targetDoc],
        queryUsed: promptText,
        timestamp: new Date().toISOString(),
      };
      setMessages([...updatedMessages, aiMessage]);

      // Refresh sidebar conversations
      fetchConversations();
    } catch (err) {
      console.error("Document explanation error:", err);
      const errorDetail =
        err.response?.data?.detail ||
        err.message ||
        "Failed to generate comprehensive explanation. Check backend availability.";

      setMessages([
        ...updatedMessages,
        {
          type: "ai",
          text: errorDetail,
          isError: true,
          queryUsed: promptText,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // ----------------------------------------------------
  // Voice Input (Speech Recognition)
  // ----------------------------------------------------
  const toggleVoiceInput = () => {
    if (loading || uploading) return;

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Voice input is not supported in this browser. Please use Chrome or Edge.");
      return;
    }

    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = "en-US";

      recognition.onstart = () => setIsListening(true);
      recognition.onresult = (event) => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        if (transcript.trim()) {
          setQuestion(transcript.trim());
        }
      };
      recognition.onerror = (event) => {
        console.warn("Speech recognition error:", event.error);
        setIsListening(false);
      };
      recognition.onend = () => {
        setIsListening(false);
        recognitionRef.current = null;
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.error("Failed to start voice recognition:", err);
      setIsListening(false);
    }
  };

  // ----------------------------------------------------
  // Send Message / Ask Question
  // ----------------------------------------------------
  const handleSendMessage = async (textToSend, options = {}) => {
    const query = (textToSend || question).trim();
    if (!query || loading) return;

    const { isRegenerate = false, targetIndex = null } = options;

    let updatedMessages = [...messages];
    if (!isRegenerate) {
      const userMessage = {
        type: "user",
        text: query,
        timestamp: new Date().toISOString(),
      };
      updatedMessages = [...updatedMessages, userMessage];
      setMessages(updatedMessages);
      setQuestion("");
    } else if (targetIndex !== null && targetIndex < updatedMessages.length) {
      updatedMessages = updatedMessages.filter((_, idx) => idx !== targetIndex);
      setMessages(updatedMessages);
    }

    userScrolledUpRef.current = false;
    setShowScrollBottom(false);
    setLoading(true);
    setTimeout(() => {
      scrollToBottom("smooth");
    }, 20);

    if (selectedDocuments.length > 0) {
      setLoadingStatusText("Searching document context...");
    } else {
      setLoadingStatusText("NexusAI is thinking...");
    }

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    const requestBody = {
      question: query,
      filenames: selectedDocuments,
      filename: selectedDocuments.length === 1 ? selectedDocuments[0] : null,
      conversation_id: activeConversationId,
    };

    // 1. LOCAL AI (Streaming with Qwen)
    if (processingMode === "local") {
      try {
        const response = await fetch(`${API_BASE_URL}/local-chat`, {
          method: "POST",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify(requestBody),
          signal: abortController.signal,
        });

        if (!response.ok) {
          throw new Error(`Local AI request failed: ${response.status}`);
        }

        // Capture conversation headers if returned
        const headerConvId = response.headers.get("X-Conversation-Id");
        const headerConvTitle = response.headers.get("X-Conversation-Title");
        if (headerConvId) {
          const parsedId = parseInt(headerConvId, 10);
          setActiveConversationId(parsedId);
          if (headerConvTitle) setActiveConversationTitle(headerConvTitle);
        }

        if (!response.body) {
          throw new Error("Streaming response is not supported.");
        }

        const initialAiMessages = [
          ...updatedMessages,
          {
            type: "ai",
            text: "",
            sources: selectedDocuments.length > 0 ? selectedDocuments : [],
            queryUsed: query,
            timestamp: new Date().toISOString(),
          },
        ];
        setMessages(initialAiMessages);

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let accumulated = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          if (!chunk) continue;
          accumulated += chunk;

          setMessages((prev) => {
            const copy = [...prev];
            const lastIdx = copy.length - 1;
            if (copy[lastIdx] && copy[lastIdx].type === "ai") {
              copy[lastIdx] = { ...copy[lastIdx], text: accumulated };
            }
            return copy;
          });
        }

        // Refresh conversations list in sidebar
        fetchConversations();
      } catch (err) {
        if (err.name === "AbortError") {
          console.log("Local generation was stopped by user.");
        } else {
          console.error("Local AI streaming error:", err);
          setMessages((prev) => [
            ...prev,
            {
              type: "ai",
              text: "Local AI failed to respond. Ensure local model is running or switch to Cloud mode.",
              isError: true,
              queryUsed: query,
              timestamp: new Date().toISOString(),
            },
          ]);
        }
      } finally {
        setLoading(false);
        abortControllerRef.current = null;
      }
      return;
    }

    // 2. CLOUD AI (Gemini Streaming)
    try {
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(requestBody),
        signal: abortController.signal,
      });

      if (!response.ok) {
        let errDetail = `Cloud AI request failed with status ${response.status}`;
        try {
          const errJson = await response.json();
          if (errJson?.detail) errDetail = errJson.detail;
        } catch {
          // ignore json parse error
        }
        throw new Error(errDetail);
      }

      const headerConvId = response.headers.get("X-Conversation-Id");
      const headerConvTitle = response.headers.get("X-Conversation-Title");
      if (headerConvId) {
        const parsedId = parseInt(headerConvId, 10);
        setActiveConversationId(parsedId);
        if (headerConvTitle) setActiveConversationTitle(headerConvTitle);
      }

      if (!response.body) {
        throw new Error("Streaming response is not supported by browser.");
      }

      const initialAiMessages = [
        ...updatedMessages,
        {
          type: "ai",
          text: "",
          sources: selectedDocuments.length > 0 ? selectedDocuments : [],
          queryUsed: query,
          timestamp: new Date().toISOString(),
        },
      ];
      setMessages(initialAiMessages);

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let accumulated = "";
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          if (!block.trim()) continue;
          const eventMatch = block.match(/^event:\s*(\w+)/m);
          const dataMatch = block.match(/^data:\s*(.+)$/m);

          const eventType = eventMatch ? eventMatch[1] : "token";
          const dataRaw = dataMatch ? dataMatch[1] : "";

          if (eventType === "start") {
            try {
              const startData = JSON.parse(dataRaw);
              if (startData.conversation_id) {
                setActiveConversationId(startData.conversation_id);
              }
              if (startData.conversation_title) {
                setActiveConversationTitle(startData.conversation_title);
              }
            } catch {
              // ignore parse errors
            }
          } else if (eventType === "token") {
            try {
              const tokenData = JSON.parse(dataRaw);
              if (tokenData.text) {
                accumulated += tokenData.text;
                setMessages((prev) => {
                  const copy = [...prev];
                  const lastIdx = copy.length - 1;
                  if (copy[lastIdx] && copy[lastIdx].type === "ai") {
                    copy[lastIdx] = { ...copy[lastIdx], text: accumulated };
                  }
                  return copy;
                });
              }
            } catch {
              accumulated += dataRaw;
              setMessages((prev) => {
                const copy = [...prev];
                const lastIdx = copy.length - 1;
                if (copy[lastIdx] && copy[lastIdx].type === "ai") {
                  copy[lastIdx] = { ...copy[lastIdx], text: accumulated };
                }
                return copy;
              });
            }
          } else if (eventType === "complete") {
            try {
              const completeData = JSON.parse(dataRaw);
              if (completeData.final_text) {
                accumulated = completeData.final_text;
              }
              setMessages((prev) => {
                const copy = [...prev];
                const lastIdx = copy.length - 1;
                if (copy[lastIdx] && copy[lastIdx].type === "ai") {
                  copy[lastIdx] = {
                    ...copy[lastIdx],
                    text: completeData.final_text || accumulated,
                    citations: completeData.citations || copy[lastIdx].citations || [],
                    grounding: completeData.grounding || copy[lastIdx].grounding || null,
                  };
                }
                return copy;
              });
              if (completeData.conversation_id) {
                setActiveConversationId(completeData.conversation_id);
              }
              if (completeData.conversation_title) {
                setActiveConversationTitle(completeData.conversation_title);
              }
            } catch {
              // ignore
            }
          } else if (eventType === "error") {
            try {
              const errData = JSON.parse(dataRaw);
              throw new Error(errData.detail || "Error during streaming");
            } catch {
              throw new Error(dataRaw || "Error during streaming");
            }
          }
        }
      }

      // Refresh sidebar conversations
      fetchConversations();
    } catch (err) {
      if (err.name === "AbortError" || err.name === "CanceledError" || err.code === "ERR_CANCELED") {
        console.log("Cloud request was stopped by user.");
      } else {
        console.error("Chat request error:", err);
        const errorDetail =
          err.message ||
          "Unable to complete chat request. Please check your connection.";

        setMessages((prev) => {
          const copy = [...prev];
          const lastIdx = copy.length - 1;
          if (copy[lastIdx] && copy[lastIdx].type === "ai" && !copy[lastIdx].text) {
            copy[lastIdx] = {
              ...copy[lastIdx],
              text: errorDetail,
              isError: true,
            };
            return copy;
          }
          return [
            ...prev,
            {
              type: "ai",
              text: errorDetail,
              isError: true,
              queryUsed: query,
              timestamp: new Date().toISOString(),
            },
          ];
        });
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  // ----------------------------------------------------
  // Handle Keyboard Submit
  // ----------------------------------------------------
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // ----------------------------------------------------
  // Document Selection Modal Handlers
  // ----------------------------------------------------
  const openDocumentModal = () => {
    setModalSelectedDocs([...selectedDocuments]);
    setDocSearchQuery("");
    setShowDocModal(true);
    fetchWorkspaceDocuments();
  };

  const toggleModalDocSelection = (filename) => {
    setModalSelectedDocs((prev) =>
      prev.includes(filename)
        ? prev.filter((f) => f !== filename)
        : [...prev, filename]
    );
  };

  const handleApplyDocumentSelection = () => {
    updateSelectedDocuments(modalSelectedDocs);
    setShowDocModal(false);
  };

  // ----------------------------------------------------
  // File Upload via Plus Button
  // ----------------------------------------------------
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > MAX_UPLOAD_SIZE_BYTES) {
      alert(`File exceeds maximum size of ${MAX_UPLOAD_SIZE_MB}MB.`);
      return;
    }

    setUploading(true);
    setShowPlusMenu(false);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await api.post("/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const uploadedName = response.data?.filename || file.name;
      alert(`"${file.name}" uploaded successfully!`);
      await fetchWorkspaceDocuments();

      if (!selectedDocuments.includes(uploadedName)) {
        updateSelectedDocuments([...selectedDocuments, uploadedName]);
      }
    } catch (err) {
      console.error("Upload error:", err);
      alert(err.response?.data?.detail || "Document upload failed.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const filteredModalDocs = availableDocuments.filter((doc) => {
    const name = doc.filename || doc.name || "";
    return name.toLowerCase().includes(docSearchQuery.toLowerCase());
  });

  return (
    <div className="nx-chat-workspace">
      {/* ========================================================
          STYLES
      ======================================================== */}
      <style>{`
        .nx-chat-workspace {
          display: flex;
          width: 100%;
          height: 100%;
          flex: 1;
          min-height: 0;
          background: var(--nx-surface, #ffffff);
          border: 1px solid var(--nx-border, #e2e8f0);
          border-radius: 16px;
          overflow: hidden;
          box-shadow: 0 4px 20px rgba(15, 23, 42, 0.05);
          position: relative;
        }

        /* --------------------------------------------------
           CONVERSATION SIDEBAR
        -------------------------------------------------- */
        .nx-conv-sidebar {
          width: 270px;
          min-width: 270px;
          flex-shrink: 0;
          height: 100%;
          min-height: 0;
          background: var(--nx-bg, #f8fafc);
          border-right: 1px solid var(--nx-border, #e2e8f0);
          display: flex;
          flex-direction: column;
          transition: width 0.22s cubic-bezier(0.4, 0, 0.2, 1),
                      min-width 0.22s cubic-bezier(0.4, 0, 0.2, 1),
                      opacity 0.18s ease,
                      border-color 0.22s ease;
          overflow: hidden;
          z-index: 10;
          position: relative;
          white-space: nowrap;
        }

        .nx-conv-sidebar.collapsed {
          width: 0 !important;
          min-width: 0 !important;
          border-right-width: 0 !important;
          border-right-color: transparent !important;
          opacity: 0;
          pointer-events: none;
          visibility: hidden;
        }

        .nx-conv-sidebar-header {
          padding: 16px 14px 12px;
          border-bottom: 1px solid var(--nx-border, #e2e8f0);
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .nx-new-chat-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          flex: 1;
          padding: 10px 14px;
          border-radius: 10px;
          border: 1px solid var(--nx-primary-border, #bfdbfe);
          background: var(--nx-primary-soft, #eff6ff);
          color: var(--nx-primary, #2563eb);
          font-size: 13.5px;
          font-weight: 750;
          cursor: pointer;
          transition: all 0.15s ease;
          white-space: nowrap;
        }

        .nx-new-chat-btn:hover {
          background: var(--nx-primary, #2563eb);
          color: #ffffff;
          border-color: var(--nx-primary, #2563eb);
          box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
        }

        .nx-conv-collapse-btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 38px;
          border-radius: 9px;
          border: 1px solid var(--nx-border, #cbd5e1);
          background: var(--nx-surface, #ffffff);
          color: var(--nx-text-secondary, #334155);
          cursor: pointer;
          transition: all 0.15s ease;
          flex-shrink: 0;
        }

        .nx-conv-collapse-btn:hover {
          color: var(--nx-text, #0f172a);
          background: var(--nx-surface-3, #eef2f7);
          border-color: var(--nx-border-strong, #94a3b8);
        }

        .nx-conv-collapse-btn svg {
          display: block;
          fill: currentColor;
          font-size: 13px;
        }

        .nx-history-toggle-btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 36px;
          border-radius: 8px;
          border: 1px solid var(--nx-border, #cbd5e1);
          background: var(--nx-surface, #ffffff);
          color: var(--nx-text-secondary, #334155);
          cursor: pointer;
          transition: all 0.15s ease;
          flex-shrink: 0;
        }

        .nx-history-toggle-btn svg {
          display: block;
          fill: currentColor;
          font-size: 14px;
        }

        .nx-history-toggle-btn:hover {
          color: var(--nx-primary, #2563eb);
          border-color: var(--nx-primary-border, #bfdbfe);
          background: var(--nx-primary-soft, #eff6ff);
        }

        .nx-history-toggle-btn.active {
          color: var(--nx-primary, #2563eb);
          background: var(--nx-primary-soft, #eff6ff);
          border-color: var(--nx-primary-border, #bfdbfe);
        }

        .nx-sidebar-backdrop {
          display: none;
        }

        .nx-conv-list-header {
          padding: 12px 16px 6px;
          font-size: 11px;
          font-weight: 800;
          color: var(--nx-text-muted, #64748b);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .nx-conv-list {
          flex: 1;
          overflow-y: auto;
          padding: 6px 10px 14px;
          display: flex;
          flex-direction: column;
          gap: 3px;
        }

        .nx-conv-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 9px 12px;
          border-radius: 9px;
          font-size: 13.5px;
          color: var(--nx-text, #0f172a);
          cursor: pointer;
          transition: all 0.15s ease;
          border: 1px solid transparent;
          position: relative;
          group: true;
        }

        .nx-conv-item:hover {
          background: var(--nx-surface, #ffffff);
          border-color: var(--nx-border, #e2e8f0);
        }

        .nx-conv-item.active {
          background: var(--nx-primary-soft, #eff6ff);
          border-color: var(--nx-primary-border, #bfdbfe);
          color: var(--nx-primary, #2563eb);
          font-weight: 700;
        }

        .nx-conv-title {
          flex: 1;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          margin-right: 6px;
        }

        .nx-conv-actions {
          display: none;
          align-items: center;
          gap: 4px;
        }

        .nx-conv-item:hover .nx-conv-actions,
        .nx-conv-item.active .nx-conv-actions {
          display: flex;
        }

        .nx-conv-action-btn {
          background: transparent;
          border: none;
          color: var(--nx-text-muted, #64748b);
          padding: 4px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
          display: grid;
          placeItems: center;
          transition: all 0.15s ease;
        }

        .nx-conv-action-btn:hover {
          color: var(--nx-text, #0f172a);
          background: rgba(0,0,0,0.06);
        }

        .nx-conv-action-btn.delete:hover {
          color: #dc2626;
          background: #fee2e2;
        }

        .nx-conv-empty {
          padding: 30px 16px;
          text-align: center;
          color: var(--nx-text-muted, #64748b);
          font-size: 13px;
        }

        /* --------------------------------------------------
           MAIN CHAT VIEWPORT
        -------------------------------------------------- */
        .nx-main-chat {
          flex: 1;
          display: flex;
          flex-direction: column;
          min-width: 0;
          height: 100%;
          min-height: 0;
          background: var(--nx-surface, #ffffff);
          overflow: hidden;
          position: relative;
        }

        .nx-chat-header {
          padding: 14px 24px;
          border-bottom: 1px solid var(--nx-border, #e2e8f0);
          background: var(--nx-surface, #ffffff);
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 12px;
        }

        .nx-context-bar {
          padding: 8px 24px;
          background: var(--nx-bg, #f8fafc);
          border-bottom: 1px solid var(--nx-border, #e2e8f0);
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          flex-wrap: wrap;
          font-size: 13px;
        }

        .nx-doc-pills {
          display: flex;
          align-items: center;
          gap: 6px;
          flex-wrap: wrap;
        }

        .nx-doc-pill {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 3px 10px;
          background: var(--nx-primary-soft, #eff6ff);
          border: 1px solid var(--nx-primary-border, #bfdbfe);
          color: var(--nx-primary, #2563eb);
          border-radius: 999px;
          font-size: 12px;
          font-weight: 650;
        }

        .nx-doc-pill-remove {
          border: none;
          background: transparent;
          color: var(--nx-primary, #2563eb);
          cursor: pointer;
          padding: 0;
          display: grid;
          placeItems: center;
          font-size: 11px;
          opacity: 0.75;
          transition: opacity 0.15s ease;
        }

        .nx-doc-pill-remove:hover {
          opacity: 1;
        }

        .nx-messages-viewport {
          flex: 1;
          min-height: 0;
          overflow-y: auto;
          overflow-x: hidden;
          padding: 20px 24px;
          display: flex;
          flex-direction: column;
          gap: 18px;
        }

        .nx-messages-viewport::-webkit-scrollbar {
          width: 6px;
        }
        .nx-messages-viewport::-webkit-scrollbar-track {
          background: transparent;
        }
        .nx-messages-viewport::-webkit-scrollbar-thumb {
          background: rgba(100, 116, 139, 0.25);
          border-radius: 999px;
        }
        .nx-messages-viewport::-webkit-scrollbar-thumb:hover {
          background: rgba(100, 116, 139, 0.45);
        }

        .nx-message-row {
          display: flex;
          width: 100%;
          animation: nx-fade-in 0.2s ease-in-out;
        }

        .nx-message-row-user {
          justify-content: flex-end;
        }

        .nx-message-row-ai {
          justify-content: flex-start;
        }

        @keyframes nx-fade-in {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }

        /* --------------------------------------------------
           USER MESSAGE BUBBLE (Compact, clean, modern)
        -------------------------------------------------- */
        .nx-bubble-user {
          margin-left: auto;
          background: var(--nx-primary, #2563eb);
          color: #ffffff;
          border-radius: 14px;
          border-bottom-right-radius: 4px;
          padding: 10px 16px;
          max-width: 72%;
          width: fit-content;
          box-shadow: 0 2px 10px rgba(37, 99, 235, 0.16);
          font-size: 14.5px;
          line-height: 1.55;
          word-break: break-word;
        }

        /* --------------------------------------------------
           ASSISTANT ANSWER (Clean enterprise typography, NO card)
        -------------------------------------------------- */
        .nx-bubble-ai {
          width: 100%;
          max-width: 100%;
          background: transparent;
          color: var(--nx-text, #0f172a);
          border: none;
          box-shadow: none;
          padding: 2px 0 6px 0;
          position: relative;
        }

        .nx-ai-text-content {
          font-size: 14.5px;
          line-height: 1.68;
          color: var(--nx-text, #0f172a);
          word-break: break-word;
          padding-right: 36px;
        }

        /* --------------------------------------------------
           TOP-RIGHT COPY BUTTON
        -------------------------------------------------- */
        .nx-ai-copy-btn {
          position: absolute;
          top: 0;
          right: 0;
          width: 26px;
          height: 26px;
          display: grid;
          place-items: center;
          border-radius: 6px;
          border: 1px solid var(--nx-border, #e2e8f0);
          background: var(--nx-surface, #ffffff);
          color: var(--nx-text-muted, #64748b);
          cursor: pointer;
          font-size: 11px;
          transition: all 0.15s ease;
          z-index: 2;
          opacity: 0.85;
        }

        .nx-ai-copy-btn:hover {
          opacity: 1;
          background: var(--nx-primary-soft, #eff6ff);
          color: var(--nx-primary, #2563eb);
          border-color: var(--nx-primary-border, #bfdbfe);
        }

        .nx-ai-copy-btn.copied {
          opacity: 1;
          background: #dcfce7;
          color: #16a34a;
          border-color: #86efac;
        }

        /* --------------------------------------------------
           SOURCES & GROUNDING BADGE
        -------------------------------------------------- */
        .nx-ai-sources-section {
          margin-top: 14px;
          padding-top: 10px;
          border-top: 1px solid var(--nx-border, #e2e8f0);
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .nx-ai-sources-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 8px;
        }

        .nx-ai-sources-title {
          font-size: 12px;
          font-weight: 700;
          color: var(--nx-text-muted, #64748b);
          display: inline-flex;
          align-items: center;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .nx-grounding-badge {
          display: inline-flex;
          align-items: center;
          padding: 3px 8px;
          border-radius: 999px;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.02em;
        }

        .nx-grounding-badge.high {
          background: rgba(22, 163, 74, 0.12);
          color: #16a34a;
          border: 1px solid rgba(22, 163, 74, 0.25);
        }

        .nx-grounding-badge.medium {
          background: rgba(217, 119, 6, 0.12);
          color: #d97706;
          border: 1px solid rgba(217, 119, 6, 0.25);
        }

        .nx-grounding-badge.low {
          background: rgba(100, 116, 139, 0.12);
          color: #64748b;
          border: 1px solid rgba(100, 116, 139, 0.25);
        }

        .nx-ai-sources-list {
          display: flex;
          align-items: center;
          gap: 6px;
          flex-wrap: wrap;
        }

        .nx-ai-source-pill {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          padding: 4px 10px;
          border-radius: 8px;
          border: 1px solid var(--nx-border, #e2e8f0);
          background: var(--nx-surface, #ffffff);
          color: var(--nx-text, #0f172a);
          font-size: 12px;
          font-weight: 550;
          cursor: pointer;
          transition: all 0.15s ease;
          text-align: left;
        }

        .nx-ai-source-pill:hover {
          border-color: var(--nx-primary, #2563eb);
          background: var(--nx-primary-soft, #eff6ff);
          color: var(--nx-primary, #2563eb);
          transform: translateY(-1px);
          box-shadow: 0 2px 6px rgba(37, 99, 235, 0.12);
        }

        .nx-source-id {
          font-weight: 750;
          color: var(--nx-primary, #2563eb);
        }

        .nx-source-name {
          max-width: 180px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .nx-source-page {
          color: var(--nx-text-muted, #64748b);
          font-size: 11.5px;
        }

        .nx-source-score {
          padding: 1px 5px;
          border-radius: 4px;
          background: var(--nx-surface-3, #eef2f7);
          color: var(--nx-text-secondary, #334155);
          font-size: 10.5px;
          font-weight: 700;
        }

        /* --------------------------------------------------
           EVIDENCE MODAL
        -------------------------------------------------- */
        .nx-evidence-modal-backdrop {
          position: fixed;
          inset: 0;
          background: rgba(15, 23, 42, 0.6);
          backdrop-filter: blur(4px);
          z-index: 9999;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 20px;
          animation: nx-fade-in 0.15s ease;
        }

        .nx-evidence-modal-card {
          width: 100%;
          max-width: 640px;
          background: var(--nx-surface, #ffffff);
          border: 1px solid var(--nx-border, #e2e8f0);
          border-radius: 16px;
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
          overflow: hidden;
          display: flex;
          flex-direction: column;
          max-height: 85vh;
        }

        .nx-evidence-modal-header {
          padding: 16px 20px;
          border-bottom: 1px solid var(--nx-border, #e2e8f0);
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: var(--nx-bg, #f8fafc);
        }

        .nx-evidence-badge {
          display: inline-block;
          padding: 3px 8px;
          border-radius: 6px;
          background: var(--nx-primary-soft, #eff6ff);
          border: 1px solid var(--nx-primary-border, #bfdbfe);
          color: var(--nx-primary, #2563eb);
          font-size: 12px;
          font-weight: 750;
        }

        .nx-evidence-title {
          margin: 0;
          font-size: 15px;
          font-weight: 700;
          color: var(--nx-text, #0f172a);
          max-width: 380px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .nx-evidence-close-btn {
          width: 32px;
          height: 32px;
          display: grid;
          place-items: center;
          border-radius: 8px;
          border: 1px solid var(--nx-border, #cbd5e1);
          background: var(--nx-surface, #ffffff);
          color: var(--nx-text-muted, #64748b);
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .nx-evidence-close-btn:hover {
          color: var(--nx-text, #0f172a);
          background: var(--nx-surface-3, #eef2f7);
        }

        .nx-evidence-modal-body {
          padding: 20px;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .nx-evidence-meta-row {
          display: flex;
          flex-wrap: wrap;
          gap: 12px;
          font-size: 13px;
          color: var(--nx-text-secondary, #334155);
        }

        .nx-evidence-meta-item {
          display: inline-flex;
          align-items: center;
          gap: 4px;
        }

        .nx-evidence-snippet-title {
          font-size: 12px;
          font-weight: 750;
          color: var(--nx-text-muted, #64748b);
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .nx-evidence-snippet-box {
          padding: 14px 16px;
          border-radius: 10px;
          background: var(--nx-bg, #f8fafc);
          border: 1px solid var(--nx-border, #e2e8f0);
          color: var(--nx-text, #0f172a);
          font-size: 13.5px;
          line-height: 1.6;
          white-space: pre-wrap;
          font-family: inherit;
        }

        .nx-evidence-modal-footer {
          padding: 14px 20px;
          border-top: 1px solid var(--nx-border, #e2e8f0);
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: 10px;
          background: var(--nx-bg, #f8fafc);
        }

        .nx-evidence-btn-secondary {
          padding: 8px 16px;
          border-radius: 8px;
          border: 1px solid var(--nx-border, #cbd5e1);
          background: var(--nx-surface, #ffffff);
          color: var(--nx-text, #0f172a);
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .nx-evidence-btn-secondary:hover {
          background: var(--nx-surface-3, #eef2f7);
        }

        .nx-evidence-btn-primary {
          display: inline-flex;
          align-items: center;
          padding: 8px 16px;
          border-radius: 8px;
          border: 1px solid var(--nx-primary, #2563eb);
          background: var(--nx-primary, #2563eb);
          color: #ffffff;
          font-size: 13px;
          font-weight: 650;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .nx-evidence-btn-primary:hover {
          background: var(--nx-primary-hover, #1d4ed8);
        }

        /* --------------------------------------------------
           COPY TOAST & ERROR BUBBLE
        -------------------------------------------------- */
        .nx-copy-toast {
          position: fixed;
          bottom: 24px;
          left: 50%;
          transform: translateX(-50%);
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 7px 16px;
          border-radius: 999px;
          background: #0f172a;
          color: #ffffff;
          font-size: 12.5px;
          font-weight: 600;
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
          z-index: 99999;
          animation: nx-fade-in 0.2s ease;
          pointer-events: none;
        }

        .nx-copy-toast.error {
          background: #991b1b;
        }

        .nx-bubble-error {
          background: #fef2f2;
          color: #991b1b;
          border: 1px solid #fecaca;
          border-radius: 12px;
          padding: 12px 16px;
          max-width: 85%;
          font-size: 14px;
          line-height: 1.5;
        }

        .nx-loading-bubble {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 10px 16px;
          background: var(--nx-bg, #f8fafc);
          border: 1px solid var(--nx-border, #e2e8f0);
          border-radius: 12px;
          color: var(--nx-text-muted, #64748b);
          font-size: 13.5px;
          font-weight: 600;
        }

        .nx-dot-pulse {
          display: inline-flex;
          gap: 4px;
        }

        .nx-dot-pulse span {
          width: 5px;
          height: 5px;
          border-radius: 50%;
          background: var(--nx-primary, #2563eb);
          animation: nx-pulse 1.2s infinite ease-in-out;
        }

        .nx-dot-pulse span:nth-child(2) { animation-delay: 0.2s; }
        .nx-dot-pulse span:nth-child(3) { animation-delay: 0.4s; }

        @keyframes nx-pulse {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40% { transform: scale(1.1); opacity: 1; }
        }

        .nx-jump-btn {
          position: absolute;
          bottom: 95px;
          right: 28px;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 7px 14px;
          border-radius: 999px;
          background: var(--nx-surface, #ffffff);
          color: var(--nx-primary, #2563eb);
          border: 1px solid var(--nx-primary-border, #bfdbfe);
          box-shadow: 0 4px 14px rgba(37,99,235,0.18);
          font-size: 12px;
          font-weight: 750;
          cursor: pointer;
          z-index: 20;
          transition: all 0.15s ease;
        }

        .nx-jump-btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 18px rgba(37,99,235,0.25);
        }

        .nx-chat-footer {
          padding: 12px 24px 18px;
          border-top: 1px solid var(--nx-border, #e2e8f0);
          background: var(--nx-surface, #ffffff);
          position: relative;
        }

        .nx-composer-box {
          display: flex;
          align-items: flex-end;
          gap: 10px;
          background: var(--nx-bg, #f8fafc);
          border: 1px solid var(--nx-border, #cbd5e1);
          border-radius: 14px;
          padding: 8px 12px;
          transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }

        .nx-composer-box:focus-within {
          border-color: var(--nx-primary, #2563eb);
          box-shadow: 0 0 0 3px var(--nx-primary-soft, rgba(37,99,235,0.15));
        }

        .nx-textarea {
          flex: 1;
          border: none;
          background: transparent;
          color: var(--nx-text, #0f172a);
          font-size: 14.5px;
          line-height: 1.5;
          font-family: inherit;
          resize: none;
          outline: none;
          padding: 6px 4px;
          max-height: 160px;
          min-height: 24px;
          overflow-y: auto;
        }

        /* Modal Overlay & Card System */
        .nx-modal-overlay {
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(10, 15, 29, 0.65);
          backdrop-filter: blur(4px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 9999;
          padding: 20px;
        }

        .nx-modal-card {
          width: 100%;
          max-width: 520px;
          background: var(--nx-surface, #ffffff);
          color: var(--nx-text, #0f172a);
          border-radius: 16px;
          border: 1px solid var(--nx-border, #e2e8f0);
          box-shadow: 0 24px 48px rgba(0, 0, 0, 0.25);
          overflow: hidden;
          animation: nx-fade-in 0.2s ease;
        }

        /* Dedicated Document Selector Modal Elements */
        .nx-doc-modal-header {
          padding: 16px 20px;
          border-bottom: 1px solid var(--nx-border, #e2e8f0);
          background: var(--nx-surface, #ffffff);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .nx-doc-modal-title {
          margin: 0;
          font-size: 16px;
          font-weight: 800;
          color: var(--nx-text, #0f172a);
        }
        .nx-doc-modal-subtitle {
          font-size: 12px;
          color: var(--nx-text-muted, #64748b);
          margin-top: 2px;
        }
        .nx-doc-modal-close {
          border: none;
          background: transparent;
          font-size: 16px;
          color: var(--nx-text-muted, #64748b);
          cursor: pointer;
          padding: 4px 8px;
          border-radius: 6px;
          transition: background 0.15s ease, color 0.15s ease;
        }
        .nx-doc-modal-close:hover {
          background: var(--nx-surface-3, #eef2f7);
          color: var(--nx-text, #0f172a);
        }
        .nx-doc-modal-search-wrap {
          padding: 14px 20px;
          background: var(--nx-surface, #ffffff);
        }
        .nx-doc-modal-search-input {
          width: 100%;
          padding: 9px 12px;
          border-radius: 8px;
          border: 1px solid var(--nx-border, #cbd5e1);
          background: var(--nx-surface-2, #f8fafc);
          color: var(--nx-text, #0f172a);
          font-size: 13.5px;
          outline: none;
          transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }
        .nx-doc-modal-search-input:focus {
          border-color: var(--nx-primary, #2563eb);
          box-shadow: 0 0 0 3px var(--nx-primary-soft, rgba(37,99,235,0.15));
        }
        .nx-doc-modal-search-input::placeholder {
          color: var(--nx-text-muted, #94a3b8);
        }
        .nx-doc-modal-list {
          max-height: 260px;
          overflow-y: auto;
          padding: 0 20px 10px;
          background: var(--nx-surface, #ffffff);
        }
        .nx-doc-modal-row {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 12px;
          border-radius: 8px;
          cursor: pointer;
          background: transparent;
          border: 1px solid transparent;
          margin-bottom: 4px;
          transition: background 0.15s ease, border-color 0.15s ease;
          user-select: none;
        }
        .nx-doc-modal-row:hover {
          background: var(--nx-surface-3, #f1f5f9);
        }
        .nx-doc-modal-row.selected {
          background: var(--nx-primary-soft, #eff6ff);
          border-color: var(--nx-primary-border, #bfdbfe);
        }
        .nx-doc-modal-checkbox {
          cursor: pointer;
          width: 16px;
          height: 16px;
          accent-color: var(--nx-primary, #2563eb);
          flex-shrink: 0;
        }
        .nx-doc-modal-icon {
          flex-shrink: 0;
          color: var(--nx-primary, #2563eb);
          font-size: 13px;
        }
        .nx-doc-modal-name {
          font-size: 13.5px;
          font-weight: 550;
          color: var(--nx-text, #0f172a);
          flex: 1;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .nx-doc-modal-row.selected .nx-doc-modal-name {
          font-weight: 650;
          color: var(--nx-primary, #2563eb);
        }
        .nx-doc-modal-footer {
          padding: 14px 20px;
          border-top: 1px solid var(--nx-border, #e2e8f0);
          background: var(--nx-surface-2, #f8fafc);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .nx-doc-modal-btn-clear {
          border: none;
          background: transparent;
          color: var(--nx-text-muted, #64748b);
          font-size: 12.5px;
          cursor: pointer;
          font-weight: 600;
          padding: 6px 10px;
          border-radius: 6px;
          transition: color 0.15s ease, background 0.15s ease;
        }
        .nx-doc-modal-btn-clear:hover {
          color: var(--nx-text, #0f172a);
          background: var(--nx-surface-3, #e2e8f0);
        }
        .nx-doc-modal-btn-cancel {
          padding: 7px 14px;
          border-radius: 8px;
          border: 1px solid var(--nx-border, #cbd5e1);
          background: var(--nx-surface, #ffffff);
          color: var(--nx-text, #334155);
          font-size: 13px;
          font-weight: 650;
          cursor: pointer;
          transition: background 0.15s ease;
        }
        .nx-doc-modal-btn-cancel:hover {
          background: var(--nx-surface-3, #f1f5f9);
        }
        .nx-doc-modal-btn-apply {
          padding: 7px 16px;
          border-radius: 8px;
          border: none;
          background: var(--nx-primary, #2563eb);
          color: #ffffff;
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          transition: background 0.15s ease, transform 0.15s ease;
        }
        .nx-doc-modal-btn-apply:hover {
          background: var(--nx-primary-hover, #1d4ed8);
          transform: translateY(-1px);
        }

        /* Mobile responsiveness */
        @media (max-width: 900px) {
          .nx-conv-sidebar {
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 270px;
            min-width: 270px;
            transform: translateX(0);
            box-shadow: 4px 0 24px rgba(15, 23, 42, 0.18);
            transition: transform 0.22s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.18s ease;
            visibility: visible;
            opacity: 1;
            z-index: 50;
          }

          .nx-conv-sidebar.collapsed {
            transform: translateX(-100%) !important;
            width: 270px !important;
            min-width: 270px !important;
            opacity: 0;
            visibility: hidden;
          }

          .nx-sidebar-backdrop {
            display: block;
            position: absolute;
            inset: 0;
            background: rgba(15, 23, 42, 0.45);
            backdrop-filter: blur(2px);
            z-index: 40;
            animation: nx-fade-in 0.18s ease;
          }
        }

        @media (max-width: 768px) {
          .nx-chat-header {
            padding: 12px 16px;
          }
          .nx-context-bar {
            padding: 8px 16px;
          }
          .nx-messages-viewport {
            padding: 16px;
          }
          .nx-message-bubble {
            max-width: 92%;
          }
          .nx-chat-footer {
            padding: 10px 14px 14px;
          }
          .nx-jump-btn {
            bottom: 80px;
            right: 16px;
          }
        }
      `}</style>

      {/* Mobile Backdrop Overlay */}
      {sidebarOpen && (
        <div
          className="nx-sidebar-backdrop"
          onClick={toggleSidebar}
          aria-hidden="true"
        />
      )}

      {/* ========================================================
          1. CONVERSATIONS HISTORY SIDEBAR
      ======================================================== */}
      <aside
        className={`nx-conv-sidebar ${!sidebarOpen ? "collapsed" : ""}`}
        aria-label="Conversation History"
        aria-hidden={!sidebarOpen}
      >
        <div className="nx-conv-sidebar-header">
          <button
            type="button"
            onClick={handleNewChat}
            className="nx-new-chat-btn"
            aria-label="Start a new conversation"
          >
            <FaPlus size={12} />
            <span>New Chat</span>
          </button>
          <button
            type="button"
            onClick={toggleSidebar}
            aria-label="Hide conversation history"
            title="Hide conversation history"
            className="nx-conv-collapse-btn"
          >
            <FaTimes size={13} />
          </button>
        </div>

        <div className="nx-conv-list-header">
          Recent
        </div>

        <div className="nx-conv-list">
          {loadingConversations ? (
            <div className="nx-conv-empty">
              Loading conversations...
            </div>
          ) : conversationLoadError ? (
            <div className="nx-conv-empty" style={{ color: "#b91c1c" }}>
              {conversationLoadError}
            </div>
          ) : conversations.length === 0 ? (
            <div className="nx-conv-empty">
              <div style={{ fontWeight: 650, marginBottom: "4px" }}>No conversations yet</div>
              <div style={{ fontSize: "11.5px" }}>Start a new conversation to begin.</div>
            </div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeConversationId;
              const isEditing = conv.id === editingConvId;

              if (isEditing) {
                return (
                  <form
                    key={conv.id}
                    onSubmit={handleSaveRename}
                    style={{ padding: "4px 8px" }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      type="text"
                      value={editingTitleText}
                      onChange={(e) => setEditingTitleText(e.target.value)}
                      autoFocus
                      maxLength={100}
                      style={{
                        width: "100%",
                        padding: "6px 8px",
                        fontSize: "13px",
                        borderRadius: "6px",
                        border: "1px solid var(--nx-primary, #2563eb)",
                        outline: "none",
                        background: "#ffffff",
                      }}
                      onBlur={handleSaveRename}
                      onKeyDown={(e) => {
                        if (e.key === "Escape") setEditingConvId(null);
                      }}
                    />
                  </form>
                );
              }

              return (
                <div
                  key={conv.id}
                  onClick={() => selectConversation(conv.id)}
                  className={`nx-conv-item ${isActive ? "active" : ""}`}
                  title={conv.title}
                >
                  <span className="nx-conv-title">{conv.title}</span>

                  <div className="nx-conv-actions">
                    <button
                      type="button"
                      onClick={(e) => handleStartRename(e, conv)}
                      className="nx-conv-action-btn"
                      aria-label="Rename conversation"
                      title="Rename"
                    >
                      <FaEdit />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeletingConv(conv);
                      }}
                      className="nx-conv-action-btn delete"
                      aria-label="Delete conversation"
                      title="Delete"
                    >
                      <FaTrash />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </aside>

      {/* ========================================================
          2. MAIN CHAT WORKSPACE
      ======================================================== */}
      <div className="nx-main-chat">
        {/* HEADER BAR */}
        <header className="nx-chat-header">
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <button
              type="button"
              onClick={toggleSidebar}
              aria-label={sidebarOpen ? "Hide conversation history" : "Show conversation history"}
              title={sidebarOpen ? "Hide conversation history" : "Show conversation history"}
              className={`nx-history-toggle-btn ${sidebarOpen ? "active" : ""}`}
            >
              <FaBars size={14} />
            </button>

            <div>
              <h2
                style={{
                  margin: 0,
                  fontSize: "18px",
                  fontWeight: 850,
                  color: "var(--nx-text, #0f172a)",
                  letterSpacing: "-0.02em",
                  maxWidth: "360px",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
                title={activeConversationTitle || "NexusAI Assistant"}
              >
                {activeConversationTitle || "NexusAI Assistant"}
              </h2>
              <div style={{ marginTop: "2px", color: "var(--nx-text-muted, #64748b)", fontSize: "12px" }}>
                AI Powered Document Intelligence & Conversational RAG
              </div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
            {/* Privacy Shield Badge */}
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
                padding: "6px 12px",
                borderRadius: "999px",
                background: "rgba(16, 185, 129, 0.1)",
                border: "1px solid rgba(16, 185, 129, 0.25)",
                color: "#059669",
                fontSize: "11.5px",
                fontWeight: 750,
              }}
              title="Privacy-Aware Advanced RAG active: PII Redaction, Hybrid Retrieval, Prompt Injection Shield"
            >
              🛡️ Privacy-Aware RAG
            </span>

            {/* AI Mode Toggle Button */}
            <button
              type="button"
              onClick={handleToggleMode}
              title="Click to switch AI processing mode"
              aria-label={`Current mode: ${processingMode === "local" ? "Local Qwen3" : "Cloud Gemini"}. Click to switch.`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "7px",
                padding: "7px 13px",
                borderRadius: "999px",
                border: "1px solid var(--nx-primary-border, #bfdbfe)",
                background: "var(--nx-primary-soft, #eff6ff)",
                color: "var(--nx-primary, #2563eb)",
                fontSize: "12px",
                fontWeight: 750,
                cursor: "pointer",
              }}
            >
              {processingMode === "local" ? <FaDesktop /> : <FaCloud />}
              <span>{processingMode === "local" ? "Local · Qwen3" : "Cloud · Gemini"}</span>
            </button>

            {/* New Chat Button */}
            <button
              type="button"
              onClick={handleNewChat}
              aria-label="Start a new chat conversation"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "7px 13px",
                borderRadius: "999px",
                border: "1px solid var(--nx-border, #cbd5e1)",
                background: "var(--nx-surface, #ffffff)",
                color: "var(--nx-text, #0f172a)",
                fontSize: "12px",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              <FaPlus size={10} />
              <span>New Chat</span>
            </button>
          </div>
        </header>

        {/* CONTEXT BAR */}
        <section className="nx-context-bar" aria-label="Active document context">
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", flex: 1 }}>
            <span style={{ fontWeight: 750, color: "var(--nx-text-secondary, #475569)", fontSize: "12px" }}>
              Context:
            </span>

            {selectedDocuments.length === 0 ? (
              <span style={{ color: "var(--nx-text-muted, #64748b)", fontStyle: "italic", fontSize: "12.5px" }}>
                No documents selected · General AI Mode
              </span>
            ) : (
              <div className="nx-doc-pills">
                {selectedDocuments.map((docName) => (
                  <span key={docName} className="nx-doc-pill">
                    <FaFileAlt size={10} />
                    <span>{docName}</span>
                    <button
                      type="button"
                      onClick={() => removeSelectedDocument(docName)}
                      className="nx-doc-pill-remove"
                      aria-label={`Remove ${docName} from context`}
                      title="Remove from context"
                    >
                      <FaTimes />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            {selectedDocuments.length === 1 && (
              <button
                type="button"
                onClick={handleExplainDocument}
                disabled={loading}
                aria-label="Generate comprehensive explanation of selected document"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "6px 11px",
                  borderRadius: "8px",
                  border: "1px solid var(--nx-primary-border, #bfdbfe)",
                  background: "var(--nx-primary-soft, #eff6ff)",
                  color: "var(--nx-primary, #2563eb)",
                  fontSize: "12px",
                  fontWeight: 750,
                  cursor: loading ? "wait" : "pointer",
                }}
              >
                <FaBookOpen size={12} />
                <span>Explain Document</span>
              </button>
            )}

            <button
              type="button"
              onClick={openDocumentModal}
              aria-label="Select workspace documents"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 11px",
                borderRadius: "8px",
                border: "1px solid var(--nx-border, #cbd5e1)",
                background: "var(--nx-surface, #ffffff)",
                color: "var(--nx-text, #0f172a)",
                fontSize: "12px",
                fontWeight: 750,
                cursor: "pointer",
              }}
            >
              <FaFileAlt size={12} />
              <span>Select Documents</span>
            </button>

            {selectedDocuments.length > 0 && (
              <button
                type="button"
                onClick={clearAllSelectedDocuments}
                aria-label="Clear document context"
                style={{
                  padding: "6px 10px",
                  borderRadius: "8px",
                  border: "none",
                  background: "transparent",
                  color: "var(--nx-text-muted, #64748b)",
                  fontSize: "12px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Clear Context
              </button>
            )}
          </div>
        </section>

        {/* CONVERSATION MESSAGES AREA */}
        <main
          ref={messagesContainerRef}
          onScroll={handleContainerScroll}
          className="nx-messages-viewport"
        >

          {messages.length === 0 ? (
            /* CLEAN ENTERPRISE EMPTY STATE */
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                margin: "auto",
                maxWidth: "540px",
                textAlign: "center",
                padding: "36px 20px",
              }}
            >
              <h3
                style={{
                  margin: "0 0 10px 0",
                  fontSize: "24px",
                  fontWeight: 750,
                  color: "var(--nx-text, #0f172a)",
                  letterSpacing: "-0.025em",
                }}
              >
                Start a conversation
              </h3>

              <p
                style={{
                  margin: 0,
                  fontSize: "15px",
                  color: "var(--nx-text-muted, #64748b)",
                  lineHeight: 1.6,
                }}
              >
                Ask questions, analyze documents, or explore your files.
              </p>
            </div>
          ) : (
            /* CLEAN MESSAGE STREAM */
            messages.map((msg, index) => {
              const isUser = msg.type === "user";
              const isError = msg.isError;

              if (isUser) {
                return (
                  <div key={index} className="nx-message-row nx-message-row-user">
                    <div className="nx-bubble-user">
                      <div style={{ whiteSpace: "pre-wrap" }}>{msg.text}</div>
                    </div>
                  </div>
                );
              }

              if (isError) {
                return (
                  <div key={index} className="nx-message-row nx-message-row-ai">
                    <div className="nx-bubble-error">
                      <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
                        <FaExclamationTriangle style={{ flexShrink: 0, marginTop: "3px", fontSize: "16px" }} />
                        <div style={{ flex: 1 }}>
                          <div>{msg.text}</div>
                          {msg.queryUsed && (
                            <div style={{ marginTop: "10px" }}>
                              <button
                                type="button"
                                onClick={() => handleSendMessage(msg.queryUsed, { isRegenerate: true, targetIndex: index })}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "6px",
                                  padding: "6px 12px",
                                  borderRadius: "8px",
                                  border: "1px solid #f87171",
                                  background: "#ffffff",
                                  color: "#b91c1c",
                                  fontSize: "12px",
                                  fontWeight: 750,
                                  cursor: "pointer",
                                }}
                              >
                                <FaRedo size={11} /> Retry
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              }

              const isCopied = copiedMessageIndex === index;
              const hasContent = Boolean(msg.text && msg.text.trim().length > 0);

              return (
                <div key={index} className="nx-message-row nx-message-row-ai">
                  <div className="nx-bubble-ai">
                    {/* Top-Right Copy Icon for Assistant Messages */}
                    {hasContent && (
                      <button
                        type="button"
                        onClick={() => handleCopyAnswer(msg.text, index)}
                        className={`nx-ai-copy-btn ${isCopied ? "copied" : ""}`}
                        aria-label={isCopied ? "Message copied" : "Copy response"}
                        title={isCopied ? "Copied" : "Copy response"}
                      >
                        {isCopied ? (
                          <FaCheck size={11} color="#16a34a" />
                        ) : (
                          <FaCopy size={11} />
                        )}
                      </button>
                    )}

                    {/* Assistant Markdown Content */}
                    <div className="nx-ai-text-content">
                      <MarkdownRenderer content={msg.text} />
                    </div>

                    {/* Sources & Citations Section */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="nx-ai-sources-section">
                        <div className="nx-ai-sources-header">
                          <span className="nx-ai-sources-title">
                            <FaBookOpen size={11} style={{ marginRight: "5px" }} /> Sources & Evidence ({msg.citations.length})
                          </span>
                          {msg.grounding && msg.grounding.grounding_score !== undefined && (
                            <span
                              className={`nx-grounding-badge ${
                                msg.grounding.grounding_score >= 0.8
                                  ? "high"
                                  : msg.grounding.grounding_score >= 0.5
                                  ? "medium"
                                  : "low"
                              }`}
                              title={`Deterministic Evidence Grounding: ${Math.round(msg.grounding.grounding_score * 100)}% (${msg.grounding.supported_claims || 0}/${msg.grounding.total_claims || 0} claims supported)`}
                            >
                              <FaShieldAlt size={10} style={{ marginRight: "4px" }} />
                              {msg.grounding.grounding_score >= 0.8
                                ? `Grounded: ${Math.round(msg.grounding.grounding_score * 100)}%`
                                : msg.grounding.grounding_score >= 0.5
                                ? `Partially Grounded: ${Math.round(msg.grounding.grounding_score * 100)}%`
                                : `Limited Evidence: ${Math.round(msg.grounding.grounding_score * 100)}%`}
                            </span>
                          )}
                        </div>
                        <div className="nx-ai-sources-list">
                          {msg.citations.map((cite) => (
                            <button
                              key={cite.id}
                              type="button"
                              onClick={() => setActiveEvidence(cite)}
                              className="nx-ai-source-pill"
                              title="Click to inspect verified evidence chunk"
                            >
                              <span className="nx-source-id">[{cite.id}]</span>
                              <span className="nx-source-name">{cite.source_name}</span>
                              {cite.page !== null && cite.page !== undefined && (
                                <span className="nx-source-page">· p. {cite.page}</span>
                              )}
                              {cite.score !== undefined && cite.score !== null && (
                                <span className="nx-source-score">{Math.round(cite.score * 100)}%</span>
                              )}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}

          {/* LOADING & THINKING STATE */}
          {loading && (
            <div className="nx-message-row" style={{ justifyContent: "flex-start" }}>
              <div className="nx-loading-bubble">
                <span className="nx-dot-pulse">
                  <span />
                  <span />
                  <span />
                </span>
                <span>{loadingStatusText}</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </main>

        {/* Floating Jump to Latest Button */}
        {showScrollBottom && (
          <button
            type="button"
            onClick={() => {
              userScrolledUpRef.current = false;
              setShowScrollBottom(false);
              scrollToBottom("smooth");
            }}
            className="nx-jump-btn"
            aria-label="Jump to latest message"
          >
            <FaArrowDown size={11} />
            <span>Latest</span>
          </button>
        )}

        {/* INPUT COMPOSER */}
        <footer className="nx-chat-footer">
          <input
            ref={fileInputRef}
            type="file"
            style={{ display: "none" }}
            onChange={handleFileUpload}
            accept=".pdf,.docx,.pptx,.txt,.xlsx"
          />

          <div className="nx-composer-box">
            {/* Plus / Upload Button */}
            <div style={{ position: "relative" }}>
              <button
                type="button"
                onClick={() => setShowPlusMenu((prev) => !prev)}
                aria-label="Upload document or attach context"
                title="Attach file"
                style={{
                  width: "34px",
                  height: "34px",
                  borderRadius: "10px",
                  border: "1px solid var(--nx-border, #cbd5e1)",
                  background: "var(--nx-surface, #ffffff)",
                  color: "var(--nx-text-secondary, #475569)",
                  display: "grid",
                  placeItems: "center",
                  cursor: "pointer",
                  fontSize: "14px",
                  transition: "all 0.15s ease",
                }}
              >
                <FaPlus />
              </button>

              {showPlusMenu && (
                <div
                  style={{
                    position: "absolute",
                    bottom: "44px",
                    left: "0",
                    background: "var(--nx-surface, #ffffff)",
                    border: "1px solid var(--nx-border, #e2e8f0)",
                    borderRadius: "12px",
                    boxShadow: "0 10px 25px rgba(15,23,42,0.12)",
                    padding: "6px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "2px",
                    minWidth: "180px",
                    zIndex: 50,
                  }}
                >
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "8px 12px",
                      border: "none",
                      background: "transparent",
                      color: "var(--nx-text, #0f172a)",
                      fontSize: "13px",
                      fontWeight: 600,
                      borderRadius: "8px",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <FaFileAlt size={12} color="#2563eb" />
                    <span>Upload Document</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setShowPlusMenu(false);
                      openDocumentModal();
                    }}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "8px 12px",
                      border: "none",
                      background: "transparent",
                      color: "var(--nx-text, #0f172a)",
                      fontSize: "13px",
                      fontWeight: 600,
                      borderRadius: "8px",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <FaBookOpen size={12} color="#059669" />
                    <span>Select Existing Files</span>
                  </button>
                </div>
              )}
            </div>

            {/* Input Textarea */}
            <textarea
              ref={inputFieldRef}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                selectedDocuments.length > 0
                  ? `Ask questions grounded in ${selectedDocuments.length} document${selectedDocuments.length > 1 ? "s" : ""}... (Shift+Enter for new line)`
                  : "Ask NexusAI anything... (Shift+Enter for new line)"
              }
              rows={1}
              className="nx-textarea"
              aria-label="Chat input query"
            />

            {/* Voice Input Microphone */}
            <button
              type="button"
              onClick={toggleVoiceInput}
              aria-label={isListening ? "Listening to voice input..." : "Use voice input"}
              title={isListening ? "Listening..." : "Voice Input"}
              style={{
                width: "34px",
                height: "34px",
                borderRadius: "10px",
                border: isListening ? "1px solid #ef4444" : "1px solid var(--nx-border, #cbd5e1)",
                background: isListening ? "#fee2e2" : "var(--nx-surface, #ffffff)",
                color: isListening ? "#dc2626" : "var(--nx-text-secondary, #475569)",
                display: "grid",
                placeItems: "center",
                cursor: "pointer",
                fontSize: "13px",
                transition: "all 0.15s ease",
              }}
            >
              <FaMicrophone />
            </button>

            {/* Send / Stop Button */}
            {loading ? (
              <button
                type="button"
                onClick={handleStopGenerating}
                aria-label="Stop generating response"
                title="Stop generation"
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "10px",
                  border: "none",
                  background: "#dc2626",
                  color: "#ffffff",
                  display: "grid",
                  placeItems: "center",
                  cursor: "pointer",
                  fontSize: "13px",
                  transition: "all 0.15s ease",
                }}
              >
                <FaStop />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => handleSendMessage()}
                disabled={!question.trim()}
                aria-label="Send message"
                title="Send"
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "10px",
                  border: "none",
                  background: question.trim() ? "var(--nx-primary, #2563eb)" : "var(--nx-border, #cbd5e1)",
                  color: "#ffffff",
                  display: "grid",
                  placeItems: "center",
                  cursor: question.trim() ? "pointer" : "not-allowed",
                  fontSize: "14px",
                  transition: "all 0.15s ease",
                }}
              >
                <FaPaperPlane />
              </button>
            )}
          </div>
        </footer>
      </div>

      {/* ========================================================
          3. DELETE CONVERSATION CONFIRMATION MODAL
      ======================================================== */}
      {deletingConv && (
        <div className="nx-modal-overlay">
          <div className="nx-modal-card" style={{ maxWidth: "440px", padding: "24px" }}>
            <div style={{ fontSize: "20px", fontWeight: 800, color: "var(--nx-text, #0f172a)", marginBottom: "8px" }}>
              Delete conversation?
            </div>
            <p style={{ color: "var(--nx-text-muted, #64748b)", fontSize: "14px", lineHeight: 1.5, margin: "0 0 20px" }}>
              This will permanently delete this conversation and its messages.
              <br /><br />
              <strong>Note:</strong> It will <em>NOT</em> delete your uploaded documents.
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                type="button"
                onClick={() => setDeletingConv(null)}
                disabled={isDeleting}
                className="nx-doc-modal-btn-cancel"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                style={{
                  padding: "8px 18px",
                  borderRadius: "8px",
                  border: "none",
                  background: "#dc2626",
                  color: "#ffffff",
                  fontWeight: 700,
                  fontSize: "13px",
                  cursor: "pointer",
                }}
              >
                {isDeleting ? "Deleting..." : "Delete Conversation"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================
          4. DOCUMENT SELECTOR MODAL
      ======================================================== */}
      {showDocModal && (
        <div className="nx-modal-overlay">
          <div className="nx-modal-card">
            <div className="nx-doc-modal-header">
              <div>
                <h3 className="nx-doc-modal-title">
                  Select Workspace Documents
                </h3>
                <div className="nx-doc-modal-subtitle">
                  Attach documents for grounded RAG conversational retrieval
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowDocModal(false)}
                aria-label="Close document selector modal"
                className="nx-doc-modal-close"
              >
                ✕
              </button>
            </div>

            <div className="nx-doc-modal-search-wrap">
              <input
                type="text"
                value={docSearchQuery}
                onChange={(e) => setDocSearchQuery(e.target.value)}
                placeholder="Search documents by filename..."
                className="nx-doc-modal-search-input"
              />
            </div>

            <div className="nx-doc-modal-list">
              {loadingDocs ? (
                <div style={{ textAlign: "center", padding: "20px", color: "var(--nx-text-muted)" }}>
                  Loading library documents...
                </div>
              ) : docLoadError ? (
                <div style={{ color: "#ef4444", fontSize: "13px", padding: "10px", textAlign: "center" }}>
                  {docLoadError}
                </div>
              ) : filteredModalDocs.length === 0 ? (
                <div style={{ textAlign: "center", padding: "24px", color: "var(--nx-text-muted)", fontSize: "13px" }}>
                  No documents found matching search.
                </div>
              ) : (
                filteredModalDocs.map((doc) => {
                  const name = doc.filename || doc.name;
                  const isChecked = modalSelectedDocs.includes(name);

                  return (
                    <label
                      key={name}
                      className={`nx-doc-modal-row ${isChecked ? "selected" : ""}`}
                      title={name}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleModalDocSelection(name)}
                        className="nx-doc-modal-checkbox"
                      />
                      <FaFileAlt className="nx-doc-modal-icon" />
                      <span className="nx-doc-modal-name">
                        {name}
                      </span>
                    </label>
                  );
                })
              )}
            </div>

            <div className="nx-doc-modal-footer">
              <button
                type="button"
                onClick={() => setModalSelectedDocs([])}
                className="nx-doc-modal-btn-clear"
              >
                Clear All
              </button>

              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  type="button"
                  onClick={() => setShowDocModal(false)}
                  className="nx-doc-modal-btn-cancel"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleApplyDocumentSelection}
                  className="nx-doc-modal-btn-apply"
                >
                  Apply Selection ({modalSelectedDocs.length})
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* ========================================================
          EVIDENCE PREVIEW MODAL / DRAWER
      ======================================================== */}
      {activeEvidence && (
        <div className="nx-evidence-modal-backdrop" onClick={() => setActiveEvidence(null)}>
          <div className="nx-evidence-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="nx-evidence-modal-header">
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span className="nx-evidence-badge">Source [{activeEvidence.id}]</span>
                <h3 className="nx-evidence-title">{activeEvidence.source_name}</h3>
              </div>
              <button
                type="button"
                onClick={() => setActiveEvidence(null)}
                className="nx-evidence-close-btn"
                aria-label="Close evidence preview"
              >
                <FaTimes size={14} />
              </button>
            </div>

            <div className="nx-evidence-modal-body">
              <div className="nx-evidence-meta-row">
                <span className="nx-evidence-meta-item">
                  <strong>Location:</strong> {activeEvidence.page ? `Page ${activeEvidence.page}` : "General document excerpt"}
                </span>
                {activeEvidence.score !== undefined && activeEvidence.score !== null && (
                  <span className="nx-evidence-meta-item">
                    <strong>Relevance Match:</strong> {Math.round(activeEvidence.score * 100)}%
                  </span>
                )}
                {activeEvidence.chunk_id && (
                  <span className="nx-evidence-meta-item nx-evidence-chunk-id">
                    <strong>Chunk ID:</strong> {activeEvidence.chunk_id}
                  </span>
                )}
              </div>

              <div className="nx-evidence-snippet-title">Verified Text Excerpt</div>
              <div className="nx-evidence-snippet-box">
                {activeEvidence.snippet || "No snippet text available."}
              </div>
            </div>

            <div className="nx-evidence-modal-footer">
              <button
                type="button"
                className="nx-evidence-btn-secondary"
                onClick={() => setActiveEvidence(null)}
              >
                Close
              </button>
              <button
                type="button"
                className="nx-evidence-btn-primary"
                onClick={() => {
                  const downloadUrl = `${API_BASE_URL}/documents/${encodeURIComponent(activeEvidence.source_name)}/file`;
                  window.open(downloadUrl, "_blank");
                }}
              >
                <FaExternalLinkAlt size={12} style={{ marginRight: "6px" }} /> Open Source Document
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Copy Toast Notification */}
      {copyToast.show && (
        <div className={`nx-copy-toast ${copyToast.isError ? "error" : ""}`} role="status" aria-live="polite">
          {copyToast.isError ? (
            <FaExclamationTriangle size={13} color="#fca5a5" />
          ) : (
            <FaCheck size={12} color="#4ade80" />
          )}
          <span>{copyToast.message}</span>
        </div>
      )}
    </div>
  );
}

export default ChatWindow;
