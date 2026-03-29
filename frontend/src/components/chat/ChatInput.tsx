"use client";

import { useRef, useEffect, KeyboardEvent, useState } from "react";

interface Props {
  onSend: (msg: string) => void;
  onStop: () => void;
  isLoading: boolean;
}

export function ChatInput({ onSend, onStop, isLoading }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = Math.min(ref.current.scrollHeight, 180) + "px";
    }
  }, [value]);

  const send = () => {
    const v = value.trim();
    if (!v || isLoading) return;
    onSend(v);
    setValue("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  const isEmpty = value.trim().length === 0;

  return (
    <div style={{
      display: "flex",
      alignItems: "flex-end",
      gap: "10px",
      padding: "12px 16px",
      background: "var(--tt-surface-2)",
      border: "1px solid",
      borderColor: focused ? "rgba(79,142,247,0.4)" : "var(--tt-border)",
      borderRadius: "16px",
      transition: "border-color 0.2s",
      boxShadow: focused ? "0 0 0 3px rgba(79,142,247,0.08)" : "none",
    }}>
      <textarea
        ref={ref}
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder="Ask TissaTech Assistant anything..."
        rows={1}
        style={{
          flex: 1,
          background: "transparent",
          border: "none",
          outline: "none",
          resize: "none",
          fontSize: "14px",
          lineHeight: "1.6",
          color: "var(--tt-text)",
          fontFamily: "var(--font-main)",
          minHeight: "24px",
          maxHeight: "180px",
          padding: "2px 0",
        }}
      />

      {/* Send / Stop button */}
      <button
        onClick={isLoading ? onStop : send}
        disabled={!isLoading && isEmpty}
        style={{
          width: "36px",
          height: "36px",
          borderRadius: "10px",
          border: "none",
          background: isLoading
            ? "rgba(248,113,113,0.15)"
            : isEmpty
            ? "var(--tt-surface-3)"
            : "linear-gradient(135deg, #4f8ef7, #7c6af7)",
          color: isLoading
            ? "var(--tt-error)"
            : isEmpty
            ? "var(--tt-text-3)"
            : "#fff",
          cursor: isLoading || !isEmpty ? "pointer" : "not-allowed",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          transition: "all 0.15s",
          boxShadow: (!isLoading && !isEmpty) ? "0 2px 8px rgba(79,142,247,0.35)" : "none",
        }}
      >
        {isLoading ? (
          // Stop icon
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="2"/>
          </svg>
        ) : (
          // Send icon
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        )}
      </button>
    </div>
  );
}
