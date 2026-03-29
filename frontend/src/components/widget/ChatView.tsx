import { useState, useRef, useEffect } from 'react';
import { useChatStore } from '@/lib/store';
import { ArrowLeft, MoreHorizontal, Minus, Trash2, Send, Paperclip, ThumbsUp, ThumbsDown, Copy, Check } from 'lucide-react';
import styles from '@/app/widget/[botId]/widget.module.css';
import { streamChatMessage, chatApi } from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function toReadableMarkdown(raw: string): string {
  const text = (raw || '').replace(/\r/g, '').trim();
  if (!text) return '';

  const blocks = text.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  const transformed: string[] = [];

  for (const block of blocks) {
    const lines = block.split('\n').map((line) => line.trim()).filter(Boolean);
    if (lines.length <= 1) {
      transformed.push(lines[0] ?? '');
      continue;
    }

    // If a block starts with a lead-in ending with ":" convert following lines to bullets.
    if (/:\s*$/.test(lines[0])) {
      transformed.push(lines[0]);
      transformed.push(...lines.slice(1).map((line) => {
        const clean = line.replace(/^[-*•]\s*/, '').trim();
        return `- ${clean}`;
      }));
      continue;
    }

    transformed.push(lines.join('\n'));
  }

  return transformed
    .join('\n\n')
    .replace(/\s+-\s+/g, '\n- ')
    .replace(/\n{3,}/g, '\n\n');
}

export default function ChatView({ botId }: { botId: string }) {
  const {
    setView, closeWidget, messages, addMessage,
    updateLastBotMessage, clearChat, conversationId,
    setConversationId, sessionId, userProfile, isStreaming, setIsStreaming
  } = useChatStore();

  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, 'up' | 'down'>>({});
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasUserMessages = messages.some((m) => m.sender === 'user');

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  useEffect(() => {
    const role = userProfile?.role?.trim();
    if (!role || !botId || hasUserMessages) {
      setSuggestedQuestions([]);
      return;
    }

    let active = true;
    chatApi.getRoleSuggestions(role, botId, 5)
      .then((res) => {
        if (active) {
          setSuggestedQuestions(res.suggestions ?? []);
        }
      })
      .catch(() => {
        if (active) {
          setSuggestedQuestions([]);
        }
      });

    return () => {
      active = false;
    };
  }, [userProfile?.role, botId, hasUserMessages]);

  const sendText = async (rawText: string) => {
    if (!rawText.trim() || isStreaming) return;

    const text = rawText.trim();
    setInputValue('');
    setIsStreaming(true);
    setSuggestedQuestions([]);

    // Add user message
    addMessage({ text, sender: 'user' });

    // Add empty bot message placeholder for streaming
    addMessage({ text: '', sender: 'bot' });

    try {
      let fullText = '';
      const profile = userProfile ? {
        name: userProfile.name,
        email: userProfile.email,
        phone: userProfile.phone ?? '',
        organization: userProfile.organization ?? '',
        industry: userProfile.industry ?? '',
        role: userProfile.role ?? '',
      } : undefined;

      for await (const chunk of streamChatMessage(text, conversationId, sessionId, profile, botId)) {
        if (chunk.content) {
          fullText += chunk.content;
          updateLastBotMessage(fullText, false);
        }
        if (chunk.conversation_id && !conversationId) {
          setConversationId(chunk.conversation_id);
        }
        if (chunk.message_id) {
          updateLastBotMessage(fullText, true, chunk.message_id);
        }
        if (chunk.error) {
          updateLastBotMessage('Sorry, I encountered an error. Please try again.', true);
          break;
        }
      }

      if (!fullText) {
        updateLastBotMessage('Sorry, I encountered an error. Please try again.', true);
      }
    } catch {
      updateLastBotMessage('Connection error. Please check your network and try again.', true);
    } finally {
      setIsStreaming(false);
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    await sendText(inputValue);
  };

  const handleCopy = async (text: string, id: string) => {
    await navigator.clipboard.writeText(text).catch(() => {});
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleFeedback = async (messageId: string | undefined, type: 'up' | 'down') => {
    if (!messageId || feedbackGiven[messageId]) return;
    setFeedbackGiven((p) => ({ ...p, [messageId]: type }));
    try {
      await chatApi.submitFeedback(messageId, type === 'up' ? 'thumbs_up' : 'thumbs_down');
    } catch {}
  };

  return (
    <div className={`${styles.widgetContainer} rounded-3xl overflow-hidden bg-slate-50 relative flex flex-col shadow-2xl`}>
      {/* Header */}
      <div className="flex justify-between items-center p-4 bg-white border-b border-slate-100 relative z-10 shadow-sm">
        <div className="flex items-center gap-3">
          <button onClick={() => setView('form')} className="p-2 bg-slate-100 rounded-full hover:bg-slate-200 transition-colors">
            <ArrowLeft size={18} className="text-slate-700" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-slate-100 rounded-full flex items-center justify-center text-slate-700 font-bold text-sm relative">
              T
              <div className="absolute top-0 right-0 w-2.5 h-2.5 bg-green-500 rounded-full border-2 border-white" />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-800 leading-none">Tissa</p>
              {isStreaming && <p className="text-[10px] text-indigo-500 font-medium">Typing...</p>}
            </div>
          </div>
        </div>

        <div className="flex gap-2 relative">
          <button onClick={() => setIsMenuOpen(!isMenuOpen)} className="p-2 bg-slate-100 rounded-full hover:bg-slate-200 transition-colors">
            <MoreHorizontal size={18} className="text-slate-700" />
          </button>
          {isMenuOpen && (
            <div className="absolute top-10 right-10 w-40 bg-white border border-slate-100 rounded-xl shadow-lg z-50 overflow-hidden">
              <button onClick={() => { clearChat(); setIsMenuOpen(false); }}
                className="w-full text-left px-4 py-3 text-sm text-red-600 hover:bg-slate-50 flex items-center gap-2">
                <Trash2 size={16} /> Clear chat
              </button>
            </div>
          )}
          <button onClick={closeWidget} className="p-2 bg-slate-100 rounded-full hover:bg-slate-200 transition-colors">
            <Minus size={18} className="text-slate-700" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className={`flex-1 p-5 ${styles.scrollArea} flex flex-col gap-4`}>
        {suggestedQuestions.length > 0 && (
          <div className="mb-1">
            <p className="text-xs text-slate-500 mb-2">Suggested questions for your role:</p>
            <div className="flex flex-wrap gap-2">
              {suggestedQuestions.map((question, index) => (
                <button
                  key={`${question}-${index}`}
                  type="button"
                  onClick={() => { void sendText(question); }}
                  disabled={isStreaming}
                  className="text-left px-3 py-2 text-xs rounded-full border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-60"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
            <div className={`max-w-[85%] p-3 px-4 rounded-2xl text-sm leading-relaxed shadow-sm ${
              msg.sender === 'user'
                ? 'bg-slate-700 text-white rounded-br-sm'
                : 'bg-white text-slate-800 border border-slate-100 rounded-bl-sm'
            }`}>
              {msg.sender === 'user' ? (
                <span className="whitespace-pre-wrap break-words">{msg.text}</span>
              ) : (
                <>
                  {msg.text ? (
                    <div className="max-w-none break-words text-[15px] text-slate-800">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p: ({ children }) => <p className="mb-2 leading-7">{children}</p>,
                          ul: ({ children }) => <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>,
                          ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>,
                          li: ({ children }) => <li className="leading-7">{children}</li>,
                          h1: ({ children }) => <h1 className="text-base font-semibold mb-2">{children}</h1>,
                          h2: ({ children }) => <h2 className="text-[15px] font-semibold mb-2">{children}</h2>,
                          h3: ({ children }) => <h3 className="text-sm font-semibold mb-1.5">{children}</h3>,
                          strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
                          a: ({ children, href }) => (
                            <a href={href} target="_blank" rel="noreferrer" className="text-blue-700 underline">
                              {children}
                            </a>
                          ),
                          code: ({ children }) => <code className="bg-slate-100 px-1 py-0.5 rounded text-[13px]">{children}</code>,
                        }}
                      >
                        {toReadableMarkdown(msg.text)}
                      </ReactMarkdown>
                    </div>
                  ) : (msg.isStreaming ? (
                    <span className="flex gap-1 items-center py-1">
                      {[0,1,2].map(i => (
                        <span key={i} className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce"
                          style={{ animationDelay: `${i * 0.15}s` }} />
                      ))}
                    </span>
                  ) : '...')}
                  {msg.isStreaming && msg.text && (
                    <span className="inline-block w-0.5 h-3.5 bg-slate-400 ml-0.5 align-middle animate-pulse" />
                  )}
                </>
              )}
            </div>

            {/* Actions for bot messages */}
            {msg.sender === 'bot' && !msg.isStreaming && msg.text && (
              <div className="flex gap-1 mt-1 opacity-0 hover:opacity-100 group-hover:opacity-100 transition-opacity">
                <button onClick={() => handleCopy(msg.text, msg.id)}
                  className="p-1.5 rounded-lg text-slate-300 hover:text-slate-600 hover:bg-white transition-all">
                  {copiedId === msg.id ? <Check size={12} className="text-green-500" /> : <Copy size={12} />}
                </button>
                {msg.messageId && (
                  <>
                    <button onClick={() => handleFeedback(msg.messageId, 'up')}
                      className={`p-1.5 rounded-lg transition-all ${feedbackGiven[msg.messageId!] === 'up' ? 'text-green-500' : 'text-slate-300 hover:text-slate-600 hover:bg-white'}`}>
                      <ThumbsUp size={12} />
                    </button>
                    <button onClick={() => handleFeedback(msg.messageId, 'down')}
                      className={`p-1.5 rounded-lg transition-all ${feedbackGiven[msg.messageId!] === 'down' ? 'text-red-500' : 'text-slate-300 hover:text-slate-600 hover:bg-white'}`}>
                      <ThumbsDown size={12} />
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 bg-white border-t border-slate-100">
        <form onSubmit={handleSend} className="flex items-center gap-2">
          <button type="button" className="p-2 text-slate-400 hover:text-slate-600 transition-colors">
            <Paperclip size={20} />
          </button>
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={isStreaming ? 'Tissa is typing...' : 'Type your message...'}
            disabled={isStreaming}
            className="flex-1 bg-slate-50 border border-slate-200 rounded-full px-4 py-2.5 outline-none focus:border-slate-500 transition-all text-sm disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isStreaming}
            className="p-2.5 bg-slate-700 text-white rounded-full hover:bg-slate-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send size={18} className="ml-0.5" />
          </button>
        </form>
      </div>
    </div>
  );
}
