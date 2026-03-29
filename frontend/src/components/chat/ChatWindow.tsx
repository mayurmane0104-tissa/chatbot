"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useStreamingChat } from "@/hooks/useStreamingChat";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";

const SUGGESTIONS = [
  { icon: "◈", text: "What services does TissaTech offer?" },
  { icon: "◉", text: "How can I contact your team?" },
  { icon: "◆", text: "Tell me about your technology stack" },
  { icon: "◇", text: "What industries do you serve?" },
];

export function ChatWindow() {
  const { messages, isLoading, error, sendMessage, stopStreaming } = useStreamingChat();
  const bottomRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (!mounted) return null;
  const isEmpty = messages.length === 0;

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "100vh",
      maxWidth: "860px",
      margin: "0 auto",
      width: "100%",
    }}>

      {/* ── Header ─────────────────────────────────────────────────── */}
      <header style={{
        display: "flex",
        alignItems: "center",
        gap: "14px",
        padding: "18px 28px",
        borderBottom: "1px solid var(--tt-border)",
        background: "var(--tt-surface)",
        backdropFilter: "blur(20px)",
        flexShrink: 0,
      }}>
        {/* Logo mark */}
        <div style={{
          width: "40px",
          height: "40px",
          borderRadius: "12px",
          background: "linear-gradient(135deg, #4f8ef7 0%, #7c6af7 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          boxShadow: "0 0 20px rgba(79,142,247,0.35)",
        }}>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M10 2L3 6v4c0 4.4 3 8.5 7 9.5 4-1 7-5.1 7-9.5V6L10 2z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
            <circle cx="10" cy="10" r="2.5" fill="white"/>
          </svg>
        </div>

        <div style={{ flex: 1 }}>
          <div style={{
            fontSize: "15px",
            fontWeight: 600,
            color: "#fff",
            letterSpacing: "-0.01em",
          }}>
            TissaTech Assistant
          </div>
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            marginTop: "2px",
          }}>
            <div style={{ position: "relative", width: "8px", height: "8px" }}>
              <div style={{
                width: "8px", height: "8px",
                borderRadius: "50%",
                background: "var(--tt-success)",
                position: "absolute",
              }} />
              <div style={{
                width: "8px", height: "8px",
                borderRadius: "50%",
                background: "var(--tt-success)",
                position: "absolute",
                animation: "pulse-ring 1.5s ease-out infinite",
              }} />
            </div>
            <span style={{ fontSize: "12px", color: "var(--tt-text-2)", fontWeight: 400 }}>
              Online · Powered by AWS Bedrock
            </span>
          </div>
        </div>

        {/* Model badge */}
        <div style={{
          padding: "4px 10px",
          borderRadius: "99px",
          background: "var(--tt-surface-3)",
          border: "1px solid var(--tt-border)",
          fontSize: "11px",
          color: "var(--tt-text-2)",
          fontFamily: "var(--font-mono)",
          letterSpacing: "0.02em",
        }}>
          Claude 3 Sonnet
        </div>
      </header>

      {/* ── Messages ───────────────────────────────────────────────── */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: "28px 28px 12px",
      }}>

        {isEmpty && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              minHeight: "calc(100vh - 280px)",
              textAlign: "center",
              gap: "32px",
            }}
          >
            {/* Hero icon */}
            <div style={{ position: "relative" }}>
              <div style={{
                width: "72px",
                height: "72px",
                borderRadius: "22px",
                background: "linear-gradient(135deg, var(--tt-surface-2) 0%, var(--tt-surface-3) 100%)",
                border: "1px solid var(--tt-border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 0 40px rgba(79,142,247,0.12)",
              }}>
                <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                  <path d="M16 4L6 9v6c0 7 4.8 13.6 10 15.2C21.2 28.6 26 22 26 15V9L16 4z" stroke="#4f8ef7" strokeWidth="1.5" strokeLinejoin="round" fill="rgba(79,142,247,0.1)"/>
                  <circle cx="16" cy="15" r="4" fill="#4f8ef7" fillOpacity="0.8"/>
                  <circle cx="16" cy="15" r="2" fill="#fff"/>
                </svg>
              </div>
              <div style={{
                position: "absolute",
                inset: "-8px",
                borderRadius: "28px",
                background: "radial-gradient(circle, rgba(79,142,247,0.08) 0%, transparent 70%)",
              }} />
            </div>

            <div>
              <h2 style={{
                fontSize: "22px",
                fontWeight: 600,
                color: "#fff",
                margin: "0 0 10px",
                letterSpacing: "-0.02em",
              }}>
                How can I help you today?
              </h2>
              <p style={{
                fontSize: "14px",
                color: "var(--tt-text-2)",
                margin: 0,
                maxWidth: "380px",
                lineHeight: 1.6,
              }}>
                Ask me anything about TissaTech — our services, technology, pricing, or how we can help your business grow.
              </p>
            </div>

            {/* Suggestion chips */}
            <div style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "10px",
              width: "100%",
              maxWidth: "560px",
            }}>
              {SUGGESTIONS.map((s, i) => (
                <motion.button
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 + i * 0.06 }}
                  onClick={() => sendMessage(s.text)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "13px 16px",
                    background: "var(--tt-surface)",
                    border: "1px solid var(--tt-border)",
                    borderRadius: "12px",
                    color: "var(--tt-text-2)",
                    fontSize: "13px",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.15s ease",
                    fontFamily: "var(--font-main)",
                    lineHeight: 1.4,
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(79,142,247,0.4)";
                    (e.currentTarget as HTMLButtonElement).style.color = "#fff";
                    (e.currentTarget as HTMLButtonElement).style.background = "var(--tt-surface-2)";
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--tt-border)";
                    (e.currentTarget as HTMLButtonElement).style.color = "var(--tt-text-2)";
                    (e.currentTarget as HTMLButtonElement).style.background = "var(--tt-surface)";
                  }}
                >
                  <span style={{ color: "var(--tt-accent)", fontSize: "16px", flexShrink: 0 }}>{s.icon}</span>
                  {s.text}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <div key={msg.id}>
              <MessageBubble message={msg} />
            </div>
          ))}
        </AnimatePresence>

        {/* Loading indicator */}
        {isLoading && messages[messages.length - 1]?.role !== "assistant" && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            style={{ display: "flex", alignItems: "center", gap: "12px", padding: "8px 0 16px" }}
          >
            <div style={{
              width: "32px", height: "32px", borderRadius: "10px",
              background: "linear-gradient(135deg, #4f8ef7, #7c6af7)",
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}>
              <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
                <path d="M10 2L3 6v4c0 4.4 3 8.5 7 9.5 4-1 7-5.1 7-9.5V6L10 2z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
              </svg>
            </div>
            <div style={{
              padding: "12px 16px",
              background: "var(--tt-surface)",
              border: "1px solid var(--tt-border)",
              borderRadius: "16px",
              borderBottomLeftRadius: "4px",
              display: "flex", gap: "5px", alignItems: "center",
            }}>
              {[0,1,2].map(i => (
                <div key={i} style={{
                  width: "6px", height: "6px", borderRadius: "50%",
                  background: "var(--tt-text-3)",
                }} className={`dot-${i+1}`} />
              ))}
            </div>
          </motion.div>
        )}

        {error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{
              margin: "8px 0",
              padding: "10px 16px",
              background: "rgba(248,113,113,0.08)",
              border: "1px solid rgba(248,113,113,0.2)",
              borderRadius: "10px",
              color: "var(--tt-error)",
              fontSize: "13px",
              textAlign: "center",
            }}
          >
            {error}
          </motion.div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input ──────────────────────────────────────────────────── */}
      <div style={{
        padding: "16px 28px 24px",
        borderTop: "1px solid var(--tt-border)",
        background: "var(--tt-surface)",
        flexShrink: 0,
      }}>
        <ChatInput
          onSend={sendMessage}
          onStop={stopStreaming}
          isLoading={isLoading}
        />
        <p style={{
          textAlign: "center",
          fontSize: "11px",
          color: "var(--tt-text-3)",
          margin: "10px 0 0",
          letterSpacing: "0.01em",
        }}>
          TissaTech AI · Responses may not be 100% accurate · Always verify important information
        </p>
      </div>
    </div>
  );
}
