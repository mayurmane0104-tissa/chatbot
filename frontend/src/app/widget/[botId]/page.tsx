'use client';
import { useEffect } from 'react';
import { useParams } from 'next/navigation';
import { useChatStore } from '@/lib/store';
import { MessageSquare } from 'lucide-react';
import WelcomeView from '@/components/widget/WelcomeView';
import FormView from '@/components/widget/FormView';
import ChatView from '@/components/widget/ChatView';

export default function WidgetPage() {
  const params = useParams();
  const botId = params?.botId as string;
  const { currentView, setView } = useChatStore();

  useEffect(() => {
    document.body.style.backgroundColor = 'transparent';
    document.body.style.margin = '0';
    document.body.style.padding = '0';
  }, []);

  if (currentView === 'closed') {
    return (
      <div className="fixed bottom-0 right-0 p-4">
        <button
          onClick={() => setView('welcome')}
          className="w-16 h-16 bg-slate-700 rounded-full flex items-center justify-center hover:bg-slate-800 transition-colors shadow-2xl hover:scale-105 active:scale-95"
          style={{ animation: 'wiggle 2s ease-in-out infinite' }}
        >
          <MessageSquare size={32} color="white" />
        </button>
      </div>
    );
  }

  return (
    <div className="fixed bottom-0 right-0 p-4">
      {currentView === 'welcome' && <WelcomeView botId={botId} />}
      {currentView === 'form' && <FormView />}
      {currentView === 'chat' && <ChatView botId={botId} />}
    </div>
  );
}
