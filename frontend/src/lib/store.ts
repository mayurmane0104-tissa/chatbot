import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type ViewState = 'closed' | 'welcome' | 'form' | 'chat';

export interface Message {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: Date;
  isStreaming?: boolean;
  messageId?: string;
}

export interface UserProfile {
  name: string;
  email: string;
  phone?: string;
  organization?: string;
  industry?: string;
  role?: string;
}

// ── Widget / Chat Store ───────────────────────────────────────────────────────
interface ChatState {
  currentView: ViewState;
  messages: Message[];
  conversationId: string | null;
  sessionId: string;
  userProfile: UserProfile | null;
  isStreaming: boolean;

  setView: (view: ViewState) => void;
  closeWidget: () => void;
  addMessage: (msg: { text: string; sender: 'user' | 'bot'; messageId?: string }) => string;
  updateLastBotMessage: (text: string, done?: boolean, messageId?: string) => void;
  clearChat: () => void;
  setConversationId: (id: string) => void;
  setUserProfile: (profile: UserProfile) => void;
  setIsStreaming: (v: boolean) => void;
  startNewSession: () => void;
}

function generateId() {
  return Math.random().toString(36).slice(2, 18);
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      currentView: 'closed',
      messages: [
        { id: '1', text: "Hi there! 👋 I'm Tissa. How can I help you today?", sender: 'bot', timestamp: new Date() },
      ],
      conversationId: null,
      sessionId: generateId(),
      userProfile: null,
      isStreaming: false,

      setView: (view) => {
        if (typeof window !== 'undefined') {
          window.parent.postMessage({ type: 'CHAT_TOGGLED', isOpen: view !== 'closed' }, '*');
        }
        set({ currentView: view });
      },

      closeWidget: () => {
        if (typeof window !== 'undefined') {
          window.parent.postMessage({ type: 'CHAT_TOGGLED', isOpen: false }, '*');
        }
        set({ currentView: 'closed' });
      },

      addMessage: (msg) => {
        const id = generateId();
        set((state) => ({
          messages: [...state.messages, {
            ...msg, id, timestamp: new Date(), isStreaming: false,
          }],
        }));
        return id;
      },

      updateLastBotMessage: (text, done = false, messageId) => {
        set((state) => {
          const messages = [...state.messages];
          const lastIdx = messages.map(m => m.sender).lastIndexOf('bot');
          if (lastIdx >= 0) {
            messages[lastIdx] = {
              ...messages[lastIdx],
              text,
              isStreaming: !done,
              messageId: messageId ?? messages[lastIdx].messageId,
            };
          }
          return { messages };
        });
      },

      clearChat: () => set({
        messages: [{ id: generateId(), text: 'Chat cleared. How can I help you?', sender: 'bot', timestamp: new Date() }],
        conversationId: null,
        isStreaming: false,
      }),

      setConversationId: (id) => set({ conversationId: id }),
      setUserProfile: (profile) => set({ userProfile: profile }),
      setIsStreaming: (v) => set({ isStreaming: v }),
      startNewSession: () => set({
        messages: [
          { id: generateId(), text: "Hi there! I'm Tissa. How can I help you today?", sender: 'bot', timestamp: new Date() },
        ],
        conversationId: null,
        sessionId: generateId(),
        isStreaming: false,
      }),
    }),
    {
      name: 'tisaa-chat-store',
      version: 2,
      migrate: (persistedState: unknown) => {
        const state = (persistedState ?? {}) as { userProfile?: UserProfile | null };
        return {
          userProfile: state.userProfile ?? null,
        };
      },
      partialize: (s) => ({
        // Keep only profile across refresh; conversations always start fresh.
        userProfile: s.userProfile,
      }),
    }
  )
);

// ── Auth Store ────────────────────────────────────────────────────────────────
interface AuthState {
  user: { id: string; email: string; full_name: string; role: string } | null;
  setUser: (user: AuthState['user']) => void;
  clearUser: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      setUser: (user) => set({ user }),
      clearUser: () => set({ user: null }),
    }),
    { name: 'tisaa-auth' }
  )
);
