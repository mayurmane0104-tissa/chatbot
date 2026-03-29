"use client";

import { useState, FC } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import type { Message } from "@/hooks/useStreamingChat";
import { chatApi } from "@/lib/api";
import { PropsWithChildren } from "react";

interface Props {
  message: Message;
}

export const MessageBubble: FC<Props> = ({ message }) => {

// export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const [hovered, setHovered] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const submitFeedback = async (type: "up" | "down") => {
    if (feedback) return;
    try {
      await chatApi.submitFeedback(message.id, type === "up" ? "thumbs_up" : "thumbs_down");
      setFeedback(type);
    } catch { /* silent */ }
  };

  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        style={{
          display: "flex",
          justifyContent: "flex-end",
          marginBottom: "20px",
          gap: "12px",
          alignItems: "flex-end",
        }}
      >
        <div style={{
          maxWidth: "72%",
          padding: "12px 18px",
          background: "var(--tt-user-bubble)",
          border: "1px solid var(--tt-user-border)",
          borderRadius: "18px",
          borderBottomRightRadius: "4px",
          fontSize: "14px",
          lineHeight: "1.65",
          color: "var(--tt-text)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}>
          {message.content}
        </div>
        {/* User avatar */}
        <div style={{
          width: "32px", height: "32px", borderRadius: "10px",
          background: "var(--tt-surface-3)",
          border: "1px solid var(--tt-border)",
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0, fontSize: "14px", color: "var(--tt-text-2)",
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
        </div>
      </motion.div>
    );
  }

  // AI message
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "flex",
        gap: "12px",
        marginBottom: "24px",
        alignItems: "flex-start",
      }}
    >
      {/* AI avatar */}
      <div style={{
        width: "32px", height: "32px", borderRadius: "10px",
        background: "linear-gradient(135deg, #4f8ef7, #7c6af7)",
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0, marginTop: "2px",
        boxShadow: "0 0 12px rgba(79,142,247,0.25)",
      }}>
        <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
          <path d="M10 2L3 6v4c0 4.4 3 8.5 7 9.5 4-1 7-5.1 7-9.5V6L10 2z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
          <circle cx="10" cy="10" r="2" fill="white" fillOpacity="0.8"/>
        </svg>
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Sender label */}
        <div style={{
          fontSize: "11px",
          color: "var(--tt-text-3)",
          marginBottom: "6px",
          fontWeight: 500,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
        }}>
          TissaTech AI
        </div>

        {/* Message bubble */}
        <div style={{
          padding: "16px 20px",
          background: "var(--tt-surface)",
          border: "1px solid var(--tt-border)",
          borderRadius: "18px",
          borderTopLeftRadius: "4px",
          position: "relative",
        }}>
          {message.isStreaming && !message.content ? (
            <div style={{ display: "flex", gap: "5px", alignItems: "center", height: "20px" }}>
              {[0,1,2].map(i => (
                <div key={i} style={{
                  width: "6px", height: "6px", borderRadius: "50%",
                  background: "var(--tt-text-3)",
                }} className={`dot-${i+1}`} />
              ))}
            </div>
          ) : (
            <div className="prose-chat">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                {message.content}
              </ReactMarkdown>
              {message.isStreaming && <span className="cursor-blink" />}
            </div>
          )}
        </div>

        {/* Action bar */}
        {!message.isStreaming && message.content && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: hovered ? 1 : 0 }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              marginTop: "8px",
              paddingLeft: "4px",
            }}
          >
            {/* Copy */}
            <ActionBtn onClick={copy} title="Copy response">
              {copied ? (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--tt-success)" strokeWidth="2">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              ) : (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
              )}
            </ActionBtn>

            {/* Thumbs up */}
            <ActionBtn
              onClick={() => submitFeedback("up")}
              title="Good response"
              active={feedback === "up"}
              activeColor="var(--tt-success)"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill={feedback === "up" ? "var(--tt-success)" : "none"} stroke={feedback === "up" ? "var(--tt-success)" : "currentColor"} strokeWidth="1.5">
                <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
              </svg>
            </ActionBtn>

            {/* Thumbs down */}
            <ActionBtn
              onClick={() => submitFeedback("down")}
              title="Poor response"
              active={feedback === "down"}
              activeColor="var(--tt-error)"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill={feedback === "down" ? "var(--tt-error)" : "none"} stroke={feedback === "down" ? "var(--tt-error)" : "currentColor"} strokeWidth="1.5">
                <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
              </svg>
            </ActionBtn>

            {/* Metadata */}
            {message.metadata?.latency_ms && (
              <span style={{
                fontSize: "10px",
                color: "var(--tt-text-3)",
                marginLeft: "6px",
                fontFamily: "var(--font-mono)",
              }}>
                {message.metadata.latency_ms}ms
                {message.metadata.tokens_used ? ` · ${message.metadata.tokens_used} tokens` : ""}
              </span>
            )}
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}

type ActionBtnProps = PropsWithChildren<{
  onClick: () => void | Promise<void>;
  title: string;
  active?: boolean;
  activeColor?: string;
}>;

function ActionBtn({
  children,
  onClick,
  title,
  active,
  activeColor,
}: ActionBtnProps) {
  const [hov, setHov] = useState(false);

  return (
    <button
      onClick={onClick}
      title={title}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        width: "28px",
        height: "28px",
        borderRadius: "7px",
        border: "1px solid",
        borderColor: active
          ? activeColor + "40"
          : hov
          ? "var(--tt-border-hover)"
          : "transparent",
        background: active
          ? activeColor + "15"
          : hov
          ? "var(--tt-surface-2)"
          : "transparent",
        color: active ? activeColor : "var(--tt-text-3)",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transition: "all 0.15s",
      }}
    >
      {children}
    </button>
  );
}

// function ActionBtn({
//   children,
//   onClick,
//   title,
//   active,
//   activeColor
// }: {
//   children: React.ReactNode;
//   onClick: () => void | Promise<void>;
//   title: string;
//   active?: boolean;
//   activeColor?: string;
// }) {
//   const [hov, setHov] = useState(false);
//   return (
//     <button
//       onClick={onClick}
//       title={title}
//       onMouseEnter={() => setHov(true)}
//       onMouseLeave={() => setHov(false)}
//       style={{
//         width: "28px", height: "28px",
//         borderRadius: "7px",
//         border: "1px solid",
//         borderColor: active ? (activeColor + "40") : (hov ? "var(--tt-border-hover)" : "transparent"),
//         background: active ? (activeColor + "15") : (hov ? "var(--tt-surface-2)" : "transparent"),
//         color: active ? activeColor : "var(--tt-text-3)",
//         cursor: "pointer",
//         display: "flex", alignItems: "center", justifyContent: "center",
//         transition: "all 0.15s",
//       }}
//     >
//       {children}
//     </button>
//   );
// }
