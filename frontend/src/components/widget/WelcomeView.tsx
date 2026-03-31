import { useEffect, useState } from 'react';
import { useChatStore } from '@/lib/store';
import { Minus, Send, Home, MessageCircle } from 'lucide-react';
import styles from '@/app/widget/[botId]/widget.module.css';
import { widgetApi, type WidgetConfig } from '@/lib/api';

interface Props {
  botId?: string;
}

export default function WelcomeView({ botId }: Props) {
  const { setView, closeWidget } = useChatStore();
  const [config, setConfig] = useState<WidgetConfig>({
    bot_name: 'Tissa',
    greeting_message: "Hi there! 👋 I'm Tissa. How can I help you today?",
    primary_color: '#E65C5C',
    secondary_color: '#c0392b',
    placeholder_text: 'Type a message...',
    position: 'bottom-right',
  });

  useEffect(() => {
    // `botId` is the public widget id from embed script.
    // We also send it through legacy API-key header for backward compatibility.
    widgetApi.getPublicConfig(botId).then(setConfig).catch(() => {});
  }, [botId]);

  const handleGoHome = () => {
    if (typeof window !== 'undefined') {
      window.parent.postMessage({ type: 'GO_HOME' }, '*');
    }
  };

  return (
    <div className={`${styles.widgetContainer} rounded-3xl overflow-hidden bg-slate-50 shadow-2xl`}>
      {/* Header */}
      <div className={`${styles.blueGreyGradient} rounded-t-3xl`}>
        <div className="flex justify-between items-center mb-6">
          <span className="bg-slate-800 text-white text-xs px-2 py-1 rounded-md opacity-80">Chat with me</span>
          <button onClick={closeWidget} className="text-slate-800 hover:text-black transition-colors">
            <Minus size={24} />
          </button>
        </div>
        <div className="w-12 h-12 rounded-full flex items-center justify-center font-bold text-xl text-slate-800 mb-4 overflow-hidden shadow-sm"
          style={{ backgroundColor: config.primary_color + '20', border: `2px solid ${config.primary_color}40` }}>
          {config.bot_name.charAt(0).toUpperCase()}
        </div>
        <h1 className="text-4xl font-extrabold text-slate-900 leading-tight">
          Welcome to<br />{config.bot_name}
        </h1>
      </div>

      {/* Agent Card */}
      <div className="bg-white rounded-2xl px-6 py-5 mx-5 -mt-12 shadow-lg z-10 border border-slate-100 relative">
        <div className="flex items-center gap-4 mb-5">
          <div className="w-11 h-11 rounded-full flex-shrink-0 relative flex items-center justify-center text-white font-bold text-sm"
            style={{ backgroundColor: config.primary_color }}>
            {config.bot_name.charAt(0).toUpperCase()}
            <div className="absolute top-0 right-0 w-3 h-3 bg-green-500 rounded-full border-2 border-white" />
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-0.5">Your AI assistant</p>
            <p className="text-sm text-slate-700 font-medium leading-snug">{config.greeting_message}</p>
          </div>
        </div>
        <button
          onClick={() => setView('form')}
          className="w-full text-white font-medium py-3 rounded-xl flex items-center justify-center gap-2 transition-colors shadow-sm hover:opacity-90"
          style={{ backgroundColor: config.primary_color }}
        >
          Let&apos;s chat <Send size={18} />
        </button>
      </div>

      <div className="flex-1 min-h-[20px]" />

      {/* Bottom Nav */}
      <div className="border-t border-slate-200 flex justify-between p-4 px-6 bg-slate-50 rounded-b-3xl">
        <button onClick={handleGoHome} className="flex flex-col items-center flex-1 text-slate-800 hover:text-slate-600 transition-colors">
          <Home size={20} className="mb-1" />
          <span className="text-xs font-medium">Home</span>
        </button>
        <button onClick={() => setView('form')} className="flex flex-col items-center flex-1 text-slate-400 hover:text-slate-600 transition-colors">
          <MessageCircle size={20} className="mb-1" />
          <span className="text-xs font-medium">Chat</span>
        </button>
      </div>
    </div>
  );
}
