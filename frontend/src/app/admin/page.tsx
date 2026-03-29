'use client';
import { useEffect, useState } from 'react';
import { BarChart3, Users, MessageSquare, Zap, ArrowUpRight, Plus, Bot, Globe, MoreHorizontal } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { adminApi, type Analytics, type Conversation } from '@/lib/api';

export default function AdminDashboard() {
  const router = useRouter();
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      adminApi.getAnalytics(30),
      adminApi.getConversations(1),
    ]).then(([a, c]) => {
      setAnalytics(a);
      setConversations(c.slice(0, 5));
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  const stats = analytics ? [
    { name: 'Active Chats', value: analytics.total_conversations.toString(), trend: '+12%', icon: MessageSquare, color: 'bg-indigo-500' },
    { name: 'Total Messages', value: analytics.total_messages.toLocaleString(), trend: '+5%', icon: Users, color: 'bg-emerald-500' },
    { name: 'Satisfaction', value: analytics.satisfaction_rate ? `${analytics.satisfaction_rate}%` : 'N/A', trend: '+2%', icon: Zap, color: 'bg-amber-500' },
    { name: 'Avg Latency', value: `${analytics.avg_latency_ms}ms`, trend: '-8%', icon: Globe, color: 'bg-blue-500' },
  ] : [
    { name: 'Active Chats', value: '—', trend: '—', icon: MessageSquare, color: 'bg-indigo-500' },
    { name: 'Total Messages', value: '—', trend: '—', icon: Users, color: 'bg-emerald-500' },
    { name: 'Satisfaction', value: '—', trend: '—', icon: Zap, color: 'bg-amber-500' },
    { name: 'Avg Latency', value: '—', trend: '—', icon: Globe, color: 'bg-blue-500' },
  ];

  return (
    <div className="p-8 lg:p-12 space-y-10">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div>
          <h1 className="text-4xl font-black text-slate-900 tracking-tight">Dashboard</h1>
          <p className="text-slate-500 font-medium mt-1">Your AI agents are performing at peak efficiency.</p>
        </div>
        <div className="flex gap-3">
          <button className="px-6 py-3 bg-white border border-slate-200 rounded-2xl font-bold text-slate-700 hover:bg-slate-50 transition-all shadow-sm active:scale-95">
            Download Report
          </button>
          <button
            onClick={() => router.push('/admin/setup')}
            className="px-6 py-3 bg-slate-900 text-white rounded-2xl font-bold hover:bg-black hover:shadow-2xl transition-all active:scale-95 flex items-center gap-2"
          >
            <Plus size={20} /> New Chatbot
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => (
          <div key={stat.name} className="bg-white p-6 rounded-[2rem] border border-slate-100 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300 group cursor-default">
            <div className="flex justify-between items-start mb-4">
              <div className={`${stat.color} p-3 rounded-2xl text-white shadow-lg group-hover:rotate-6 transition-transform`}>
                <stat.icon size={22} />
              </div>
              <span className="flex items-center gap-1 text-emerald-600 text-xs font-black bg-emerald-50 px-2 py-1 rounded-lg">
                <ArrowUpRight size={14} /> {stat.trend}
              </span>
            </div>
            <p className="text-slate-400 text-[10px] font-black uppercase tracking-[0.15em]">{stat.name}</p>
            <h2 className={`text-3xl font-black text-slate-900 mt-1 ${loading ? 'animate-pulse' : ''}`}>{stat.value}</h2>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* Live Interactions */}
        <div className="lg:col-span-2 bg-white rounded-[2.5rem] border border-slate-100 shadow-sm overflow-hidden flex flex-col">
          <div className="p-8 border-b border-slate-50 flex justify-between items-center">
            <h3 className="text-xl font-black text-slate-900">Live Interactions</h3>
            <button className="p-2 hover:bg-slate-100 rounded-xl transition-colors">
              <MoreHorizontal size={20} className="text-slate-400" />
            </button>
          </div>
          <div className="p-4 flex-1">
            {loading ? (
              <div className="space-y-2 p-4">
                {[1,2,3].map(i => <div key={i} className="h-14 bg-slate-100 rounded-2xl animate-pulse" />)}
              </div>
            ) : conversations.length > 0 ? conversations.map((conv, i) => (
              <div key={conv.id} className="flex items-center justify-between p-4 hover:bg-indigo-50/40 rounded-3xl transition-all cursor-pointer group mb-1"
                onClick={() => router.push('/admin/conversations')}>
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center font-black text-slate-400 group-hover:bg-white group-hover:shadow-md group-hover:text-indigo-600 transition-all">
                    {conv.title ? conv.title.charAt(0).toUpperCase() : '#'}
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900 text-sm">{conv.title ?? `Conversation ${i + 1}`}</h4>
                    <p className="text-xs text-slate-500 font-medium">{conv.message_count} messages · {conv.channel}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <p className="text-[10px] font-black text-slate-300 uppercase tracking-widest hidden sm:block">
                    {new Date(conv.created_at).toLocaleDateString()}
                  </p>
                  <div className={`w-2.5 h-2.5 rounded-full ring-4 ring-white shadow-sm ${conv.status === 'active' ? 'bg-emerald-500' : 'bg-slate-200'}`} />
                </div>
              </div>
            )) : (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <MessageSquare size={40} className="text-slate-200 mb-4" />
                <p className="text-slate-400 font-medium text-sm">No conversations yet</p>
                <p className="text-slate-300 text-xs mt-1">Conversations will appear here once users start chatting</p>
              </div>
            )}
          </div>
          <button onClick={() => router.push('/admin/conversations')}
            className="w-full p-6 text-center text-slate-400 hover:text-indigo-600 font-bold text-xs uppercase tracking-widest border-t border-slate-50 hover:bg-slate-50 transition-all">
            View All Activity
          </button>
        </div>

        {/* System Health */}
        <div className="bg-slate-950 rounded-[2.5rem] p-8 text-white shadow-2xl flex flex-col justify-between overflow-hidden relative group">
          <div className="absolute inset-0 opacity-20 pointer-events-none bg-[radial-gradient(circle_at_50%_120%,rgba(120,119,198,0.3),rgba(255,255,255,0))]" />
          <div className="relative z-10">
            <div className="w-14 h-14 bg-indigo-600 rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-500/20 mb-8 group-hover:scale-110 transition-transform duration-500">
              <Bot size={28} className="text-white" />
            </div>
            <h3 className="text-2xl font-black mb-2 tracking-tight">System Health</h3>
            <p className="text-slate-400 text-sm font-medium leading-relaxed">
              {analytics ? (
                <>Your bot has processed <span className="text-white font-bold">{analytics.total_messages.toLocaleString()} messages</span> with
                {analytics.satisfaction_rate ? <> <span className="text-white font-bold">{analytics.satisfaction_rate}%</span> satisfaction rate</> : ' no feedback yet'}.</>
              ) : 'Loading health metrics...'}
            </p>
          </div>
          <div className="relative z-10 mt-12 space-y-4">
            <div className="flex justify-between items-end mb-1">
              <p className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">Efficiency</p>
              <p className="text-lg font-black italic tracking-tighter">
                {analytics?.satisfaction_rate ? `${analytics.satisfaction_rate}%` : '—'}
              </p>
            </div>
            <div className="h-3 w-full bg-slate-900 rounded-full overflow-hidden border border-white/5">
              <div className="h-full bg-gradient-to-r from-indigo-500 to-indigo-400 rounded-full shadow-[0_0_20px_rgba(99,102,241,0.4)] transition-all duration-500"
                style={{ width: `${analytics?.satisfaction_rate ?? 0}%` }} />
            </div>
          </div>
          <Zap className="absolute -bottom-6 -right-6 w-32 h-32 text-white/5 -rotate-12" />
        </div>
      </div>
    </div>
  );
}
