'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { MessageSquare, MoreVertical, Plus, Globe, Loader2 } from 'lucide-react';
import { adminApi, type Analytics } from '@/lib/api';

// In a real multi-bot setup these would come from an API.
// For now we show the single TissaTech bot with real analytics.
export default function MyChatbots() {
  const router = useRouter();
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApi.getAnalytics(30)
      .then(setAnalytics)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const bots = [
    {
      id: 'bot-1',
      name: 'Tissa Support',
      status: 'Live',
      leads: analytics?.thumbs_up ?? 0,
      chats: analytics?.total_conversations ?? 0,
      messages: analytics?.total_messages ?? 0,
      color: '#E65C5C',
      url: 'tissatech.com',
    },
  ];

  return (
    <div className="p-8 lg:p-12 space-y-10">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-black text-slate-900 tracking-tight leading-none">My Chatbots</h1>
          <p className="text-slate-500 font-medium mt-2">Manage and monitor your deployed AI agents.</p>
        </div>
        <button
          onClick={() => router.push('/admin/setup')}
          className="bg-slate-900 text-white px-8 py-4 rounded-3xl font-black text-sm flex items-center gap-2 hover:bg-black transition-all shadow-xl shadow-slate-200"
        >
          <Plus size={20} strokeWidth={3} /> Create New Bot
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
        {bots.map((bot) => (
          <div key={bot.id} className="bg-white rounded-[2.5rem] border border-slate-100 shadow-sm hover:shadow-2xl hover:-translate-y-2 transition-all duration-500 group overflow-hidden">
            <div className="p-8 pb-0">
              <div className="flex justify-between items-start mb-6">
                <div style={{ backgroundColor: bot.color }} className="w-14 h-14 rounded-2xl flex items-center justify-center text-white shadow-lg">
                  <MessageSquare size={28} />
                </div>
                <span className={`px-4 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${bot.status === 'Live' ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-400'}`}>
                  {bot.status}
                </span>
              </div>

              <h3 className="text-2xl font-black text-slate-900 group-hover:text-indigo-600 transition-colors">{bot.name}</h3>
              <div className="flex items-center gap-1.5 text-slate-400 mt-1 mb-6">
                <Globe size={14} />
                <span className="text-xs font-bold">{bot.url}</span>
              </div>

              <div className="grid grid-cols-3 gap-4 py-6 border-t border-slate-50">
                <div>
                  <p className="text-[10px] font-black text-slate-300 uppercase tracking-widest">Leads</p>
                  <p className="text-xl font-black text-slate-800">
                    {loading ? <Loader2 size={16} className="animate-spin" /> : bot.leads}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-black text-slate-300 uppercase tracking-widest">Chats</p>
                  <p className="text-xl font-black text-slate-800">
                    {loading ? <Loader2 size={16} className="animate-spin" /> : bot.chats.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-black text-slate-300 uppercase tracking-widest">Messages</p>
                  <p className="text-xl font-black text-slate-800">
                    {loading ? <Loader2 size={16} className="animate-spin" /> : bot.messages.toLocaleString()}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-slate-50/50 p-4 px-8 flex gap-3">
              <button
                onClick={() => router.push(`/admin/chatbots/${bot.id}`)}
                className="flex-1 py-3 bg-white border border-slate-200 rounded-2xl font-black text-xs text-slate-700 hover:bg-slate-900 hover:text-white transition-all shadow-sm"
              >
                Manage
              </button>
              <button className="p-3 bg-white border border-slate-200 rounded-2xl text-slate-400 hover:text-red-500 transition-all">
                <MoreVertical size={18} />
              </button>
            </div>
          </div>
        ))}

        {/* Add new bot card */}
        <button
          onClick={() => router.push('/admin/setup')}
          className="bg-slate-50 rounded-[2.5rem] border-2 border-dashed border-slate-200 flex flex-col items-center justify-center gap-4 p-8 hover:border-indigo-300 hover:bg-indigo-50/30 transition-all group min-h-[300px]"
        >
          <div className="w-14 h-14 bg-white rounded-2xl border border-slate-200 flex items-center justify-center group-hover:bg-indigo-600 group-hover:border-indigo-600 transition-all shadow-sm">
            <Plus size={24} className="text-slate-400 group-hover:text-white transition-colors" />
          </div>
          <div className="text-center">
            <p className="font-black text-slate-500 group-hover:text-indigo-600 transition-colors">Add New Bot</p>
            <p className="text-xs text-slate-400 mt-1">Set up a new chatbot</p>
          </div>
        </button>
      </div>
    </div>
  );
}
