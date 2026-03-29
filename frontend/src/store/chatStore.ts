/**
 * store/chatStore.ts
 * Zustand store for chat state — messages, conversations, session.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Message } from "@/hooks/useStreamingChat";
import { nanoid } from "nanoid";

interface ChatState {
  messages: Message[];
  conversationId: string | null;
  sessionId: string;

  addMessage: (msg: Message) => void;
  updateLastMessage: (update: Partial<Message>) => void;
  setConversationId: (id: string) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: [],
      conversationId: null,
      sessionId: nanoid(16),

      addMessage: (msg) =>
        set((state) => ({ messages: [...state.messages, msg] })),

      updateLastMessage: (update) =>
        set((state) => {
          const messages = [...state.messages];
          const last = messages.findLastIndex((m) => m.role === "assistant");
          if (last >= 0) {
            messages[last] = { ...messages[last], ...update };
          }
          return { messages };
        }),

      setConversationId: (id) => set({ conversationId: id }),

      clearMessages: () =>
        set({ messages: [], conversationId: null }),
    }),
    {
      name: "tissatech-chat",
      partialize: (state) => ({
        // Don't persist streaming messages
        messages: state.messages.filter((m) => !m.isStreaming),
        conversationId: state.conversationId,
        sessionId: state.sessionId,
      }),
    }
  )
);
