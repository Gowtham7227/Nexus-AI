import React, { useState, useCallback } from "react";
import { FaCopy, FaCheck } from "react-icons/fa";

/**
 * CodeBlock Component with syntax styling, language tag, and isolated Copy button.
 */
function CodeBlock({ language, code }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.warn("Failed to copy code block:", err);
    }
  }, [code]);

  return (
    <div
      style={{
        margin: "12px 0 16px",
        borderRadius: "10px",
        overflow: "hidden",
        border: "1px solid #334155",
        background: "#0f172a",
        color: "#f8fafc",
        fontSize: "13.5px",
        fontFamily: 'Consolas, Monaco, "Courier New", monospace',
        maxWidth: "100%",
      }}
    >
      {/* Code Header Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "8px 14px",
          background: "#1e293b",
          borderBottom: "1px solid #334155",
          color: "#94a3b8",
          fontSize: "12px",
          fontWeight: 600,
          userSelect: "none",
        }}
      >
        <span style={{ textTransform: "lowercase", letterSpacing: "0.04em" }}>
          {language || "code"}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          aria-label={copied ? "Code copied to clipboard" : "Copy code"}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            background: copied ? "rgba(16, 185, 129, 0.2)" : "rgba(255, 255, 255, 0.08)",
            color: copied ? "#34d399" : "#e2e8f0",
            border: copied ? "1px solid rgba(16, 185, 129, 0.4)" : "1px solid rgba(255, 255, 255, 0.15)",
            padding: "4px 10px",
            borderRadius: "6px",
            fontSize: "11.5px",
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.15s ease",
          }}
        >
          {copied ? (
            <>
              <FaCheck size={11} />
              <span>Copied</span>
            </>
          ) : (
            <>
              <FaCopy size={11} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Code Content */}
      <pre
        style={{
          margin: 0,
          padding: "14px 16px",
          overflowX: "auto",
          lineHeight: 1.55,
          whiteSpace: "pre",
          tabSize: 2,
        }}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}

/**
 * Format inline tokens: bold, italic, code, sanitized links, strikethrough.
 */
function formatInlineTokens(text) {
  if (!text) return "";
  const str = String(text);

  const regex = /(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|~~[^~]+~~|\[[^\]]+\]\([^)]+\)|\*[^*]+\*|_[^_]+_)/g;
  const parts = str.split(regex);

  return parts.map((part, index) => {
    if (!part) return null;

    // Inline Code
    if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
      return (
        <code
          key={index}
          style={{
            padding: "2px 6px",
            borderRadius: "5px",
            background: "var(--nx-primary-soft, rgba(37,99,235,0.08))",
            color: "var(--nx-primary, #2563eb)",
            fontSize: "0.9em",
            fontFamily: 'Consolas, Monaco, "Courier New", monospace',
            fontWeight: 600,
          }}
        >
          {part.slice(1, -1)}
        </code>
      );
    }

    // Bold
    if (
      (part.startsWith("**") && part.endsWith("**") && part.length >= 4) ||
      (part.startsWith("__") && part.endsWith("__") && part.length >= 4)
    ) {
      return (
        <strong key={index} style={{ fontWeight: 750, color: "inherit" }}>
          {formatInlineTokens(part.slice(2, -2))}
        </strong>
      );
    }

    // Strikethrough
    if (part.startsWith("~~") && part.endsWith("~~") && part.length >= 4) {
      return (
        <del key={index} style={{ opacity: 0.75 }}>
          {formatInlineTokens(part.slice(2, -2))}
        </del>
      );
    }

    // Links [label](url) with sanitization
    const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (linkMatch) {
      const label = linkMatch[1];
      const rawUrl = linkMatch[2].trim();

      const isSafeUrl = /^(https?:\/\/|mailto:)/i.test(rawUrl);
      const safeHref = isSafeUrl ? rawUrl : "#";

      return (
        <a
          key={index}
          href={safeHref}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            color: "var(--nx-primary, #2563eb)",
            textDecoration: "underline",
            textUnderlineOffset: "3px",
            fontWeight: 600,
          }}
        >
          {label}
        </a>
      );
    }

    // Italic
    if (
      (part.startsWith("*") && part.endsWith("*") && part.length >= 2) ||
      (part.startsWith("_") && part.endsWith("_") && part.length >= 2)
    ) {
      return (
        <em key={index} style={{ fontStyle: "italic" }}>
          {formatInlineTokens(part.slice(1, -1))}
        </em>
      );
    }

    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}

/**
 * Parses and renders GitHub-flavored Markdown text cleanly and safely.
 */
function MarkdownRenderer({ content }) {
  if (!content || !String(content).trim()) {
    return null;
  }

  const text = String(content);
  const elements = [];
  const lines = text.split(/\r?\n/);
  const totalLines = lines.length;
  let i = 0;

  while (i < totalLines) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // 1. Fenced Code Block: ```lang ... ```
    if (trimmed.startsWith("```")) {
      const lang = trimmed.slice(3).trim();
      const codeLines = [];
      i++;
      while (i < totalLines && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // consume closing ```
      elements.push(
        <CodeBlock
          key={`code-${elements.length}-${i}`}
          language={lang}
          code={codeLines.join("\n")}
        />
      );
      continue;
    }

    // 2. Table Block: lines with | col | col |
    if (trimmed.startsWith("|") && trimmed.endsWith("|") && i + 1 < totalLines && lines[i + 1].trim().startsWith("|") && lines[i + 1].includes("---")) {
      const tableHeaderRaw = lines[i];
      i += 2; // skip header and separator
      const tableRowsRaw = [];
      while (i < totalLines && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
        tableRowsRaw.push(lines[i]);
        i++;
      }

      const parseRow = (r) =>
        r
          .slice(1, -1)
          .split("|")
          .map((c) => c.trim());

      const headers = parseRow(tableHeaderRaw);
      const rows = tableRowsRaw.map(parseRow);

      elements.push(
        <div
          key={`table-${elements.length}`}
          style={{
            margin: "12px 0 16px",
            overflowX: "auto",
            borderRadius: "8px",
            border: "1px solid var(--nx-border, #e2e8f0)",
          }}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "13.5px",
              textAlign: "left",
            }}
          >
            <thead>
              <tr style={{ background: "var(--nx-surface-2, #f8fafc)", borderBottom: "2px solid var(--nx-border, #e2e8f0)" }}>
                {headers.map((h, hIdx) => (
                  <th key={hIdx} style={{ padding: "9px 14px", fontWeight: 700, color: "var(--nx-text, #0f172a)" }}>
                    {formatInlineTokens(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rIdx) => (
                <tr
                  key={rIdx}
                  style={{
                    borderBottom: rIdx === rows.length - 1 ? "none" : "1px solid var(--nx-border, #e2e8f0)",
                    background: rIdx % 2 === 1 ? "var(--nx-bg, #ffffff)" : "var(--nx-surface-2, #f8fafc)",
                  }}
                >
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} style={{ padding: "8px 14px", color: "var(--nx-text, #334155)" }}>
                      {formatInlineTokens(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // 3. Headings
    if (/^####\s+/.test(trimmed)) {
      elements.push(
        <h5
          key={`h4-${elements.length}`}
          style={{
            margin: "12px 0 6px",
            fontSize: "14px",
            fontWeight: 800,
            color: "var(--nx-text)",
          }}
        >
          {formatInlineTokens(trimmed.replace(/^####\s+/, ""))}
        </h5>
      );
      i++;
      continue;
    }

    if (/^###\s+/.test(trimmed)) {
      elements.push(
        <h4
          key={`h3-${elements.length}`}
          style={{
            margin: "14px 0 6px",
            fontSize: "15px",
            fontWeight: 800,
            color: "var(--nx-text)",
          }}
        >
          {formatInlineTokens(trimmed.replace(/^###\s+/, ""))}
        </h4>
      );
      i++;
      continue;
    }

    if (/^##\s+/.test(trimmed)) {
      elements.push(
        <h3
          key={`h2-${elements.length}`}
          style={{
            margin: "16px 0 8px",
            fontSize: "17px",
            fontWeight: 800,
            color: "var(--nx-text)",
          }}
        >
          {formatInlineTokens(trimmed.replace(/^##\s+/, ""))}
        </h3>
      );
      i++;
      continue;
    }

    if (/^#\s+/.test(trimmed)) {
      elements.push(
        <h2
          key={`h1-${elements.length}`}
          style={{
            margin: "18px 0 8px",
            fontSize: "19px",
            fontWeight: 850,
            color: "var(--nx-text)",
          }}
        >
          {formatInlineTokens(trimmed.replace(/^#\s+/, ""))}
        </h2>
      );
      i++;
      continue;
    }

    // 4. Blockquotes: > quote
    if (trimmed.startsWith(">")) {
      const quoteLines = [];
      while (i < totalLines && lines[i].trim().startsWith(">")) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ""));
        i++;
      }
      elements.push(
        <blockquote
          key={`quote-${elements.length}`}
          style={{
            margin: "10px 0 14px",
            padding: "8px 14px",
            borderLeft: "4px solid var(--nx-primary, #2563eb)",
            background: "var(--nx-primary-soft, rgba(37,99,235,0.06))",
            borderRadius: "0 8px 8px 0",
            color: "var(--nx-text-secondary, #475569)",
            fontStyle: "italic",
            fontSize: "14px",
          }}
        >
          {quoteLines.map((ql, qIdx) => (
            <div key={qIdx} style={{ margin: qIdx > 0 ? "4px 0 0" : 0 }}>
              {formatInlineTokens(ql)}
            </div>
          ))}
        </blockquote>
      );
      continue;
    }

    // 5. Unordered Lists: - item, * item, • item
    if (/^[-*•]\s+/.test(trimmed)) {
      const listItems = [];
      while (i < totalLines && /^[-*•]\s+/.test(lines[i].trim())) {
        listItems.push(lines[i].trim().replace(/^[-*•]\s+/, ""));
        i++;
      }
      elements.push(
        <ul
          key={`ul-${elements.length}`}
          style={{
            margin: "6px 0 12px 20px",
            padding: 0,
            lineHeight: 1.6,
          }}
        >
          {listItems.map((item, idx) => (
            <li key={idx} style={{ marginBottom: "4px" }}>
              {formatInlineTokens(item)}
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // 6. Ordered Lists: 1. item, 2. item
    if (/^\d+\.\s+/.test(trimmed)) {
      const listItems = [];
      while (i < totalLines && /^\d+\.\s+/.test(lines[i].trim())) {
        listItems.push(lines[i].trim().replace(/^\d+\.\s+/, ""));
        i++;
      }
      elements.push(
        <ol
          key={`ol-${elements.length}`}
          style={{
            margin: "6px 0 12px 20px",
            padding: 0,
            lineHeight: 1.6,
          }}
        >
          {listItems.map((item, idx) => (
            <li key={idx} style={{ marginBottom: "4px" }}>
              {formatInlineTokens(item)}
            </li>
          ))}
        </ol>
      );
      continue;
    }

    // 7. Blank lines
    if (!trimmed) {
      elements.push(<div key={`space-${elements.length}`} style={{ height: "6px" }} />);
      i++;
      continue;
    }

    // 8. Standard Paragraph
    elements.push(
      <p
        key={`p-${elements.length}`}
        style={{
          margin: "0 0 8px",
          lineHeight: 1.65,
          color: "inherit",
          fontSize: "14.5px",
        }}
      >
        {formatInlineTokens(trimmed)}
      </p>
    );
    i++;
  }

  return <div className="nx-markdown-body">{elements}</div>;
}

export default React.memo(MarkdownRenderer);
