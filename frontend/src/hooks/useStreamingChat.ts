/**
 * hooks/useStreamingChat.ts
 * React hook for streaming chat with SSE.
 * Handles partial message display, conversation state, and error recovery.
 */
"use client";

import { useState, useCallback, useRef } from "react";
import { streamChatMessage, type StreamChunk } from "@/lib/api";
import { useChatStore } from "@/store/chatStore";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  feedback?: "thumbs_up" | "thumbs_down";
  metadata?: { tokens_used?: number; latency_ms?: number };
}

export function useStreamingChat() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const {
    messages,
    addMessage,
    updateLastMessage,
    conversationId,
    setConversationId,
    sessionId,
  } = useChatStore();

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return;

      setIsLoading(true);
      setError(null);

      // Abort any previous stream
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      // Optimistically add user message
      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: "user",
        content: text,
      };
      addMessage(userMsg);

      // Add placeholder for streaming assistant message
      const assistantId = `assistant-${Date.now()}`;
      addMessage({
        id: assistantId,
        role: "assistant",
        content: "",
        isStreaming: true,
      });

      let streamedContent = "";
      let finalMessageId: string | undefined;
      let metadata: Message["metadata"] | undefined;

      try {
        for await (const chunk of streamChatMessage(text, conversationId ?? undefined, sessionId)) {
          if (chunk.content) {
            streamedContent += chunk.content;
            updateLastMessage({ content: streamedContent, isStreaming: true });
          }

          if (chunk.conversation_id && !conversationId) {
            setConversationId(chunk.conversation_id);
          }

          if (chunk.message_id) {
            finalMessageId = chunk.message_id;
            metadata = {
              tokens_used: chunk.tokens_used,
              latency_ms: chunk.latency_ms,
            };
          }

          if (chunk.error) {
            throw new Error(chunk.error);
          }
        }

        // Finalize message
        updateLastMessage({
          id: finalMessageId ?? assistantId,
          content: streamedContent,
          isStreaming: false,
          metadata,
        });
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") {
          setError("Failed to get a response. Please try again.");
          updateLastMessage({
            content: streamedContent || "Sorry, I encountered an error. Please try again.",
            isStreaming: false,
          });
        }
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, conversationId, sessionId, addMessage, updateLastMessage, setConversationId]
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    setIsLoading(false);
  }, []);

  return { messages, isLoading, error, sendMessage, stopStreaming };
}
