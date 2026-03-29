'use client';
import { useEffect, useState } from 'react';
import { MessageSquare, Search, RefreshCw } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { adminApi, type Conversation } from '@/lib/api';

export default function ConversationsPage() {
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  const load = async (p = 1) => {
    setLoading(true);
    try {
      const data = await adminApi.getConversations(p);
      setConversations(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const filtered = conversations.filter(c =>
    !search || (c.title ?? '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-8 lg:p-12 space-y-8">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-4xl font-black text-slate-900 tracking-tight">Conversations</h1>
          <p className="text-slate-500 font-medium mt-1">{conversations.length} total conversations</p>
        </div>
        <div className="flex gap-3">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Search conversations..."
              className="pl-9 pr-4 py-2.5 border border-slate-200 rounded-2xl text-sm outline-none focus:border-slate-400 bg-white w-64"
            />
          </div>
          <button onClick={() => load(page)} className="p-2.5 bg-white border border-slate-200 rounded-2xl text-slate-500 hover:bg-slate-50 transition-all">
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      <div className="bg-white rounded-[2.5rem] border border-slate-100 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-50">
                <th className="text-left p-6 text-[10px] font-black text-slate-400 uppercase tracking-widest">Title</th>
                <th className="text-left p-6 text-[10px] font-black text-slate-400 uppercase tracking-widest">Status</th>
                <th className="text-left p-6 text-[10px] font-black text-slate-400 uppercase tracking-widest">Messages</th>
                <th className="text-left p-6 text-[10px] font-black text-slate-400 uppercase tracking-widest">Channel</th>
                <th className="text-left p-6 text-[10px] font-black text-slate-400 uppercase tracking-widest">Date</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-b border-slate-50">
                    {Array.from({ length: 5 }).map((_, j) => (
                      <td key={j} className="p-6"><div className="h-4 bg-slate-100 rounded-full animate-pulse" /></td>
                    ))}
                  </tr>
                ))
              ) : filtered.length > 0 ? (
                filtered.map((conv) => (
                  <tr key={conv.id} className="border-b border-slate-50 hover:bg-indigo-50/30 transition-all cursor-pointer group">
                    <td className="p-6">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 bg-slate-100 rounded-xl flex items-center justify-center text-slate-400 group-hover:bg-white group-hover:shadow-sm group-hover:text-indigo-600 transition-all">
                          <MessageSquare size={16} />
                        </div>
                        <span className="font-bold text-slate-800 text-sm truncate max-w-xs">
                          {conv.title ?? 'Untitled conversation'}
                        </span>
                      </div>
                    </td>
                    <td className="p-6">
                      <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${
                        conv.status === 'active' ? 'bg-emerald-50 text-emerald-600' :
                        conv.status === 'escalated' ? 'bg-amber-50 text-amber-600' :
                        'bg-slate-100 text-slate-400'
                      }`}>
                        {conv.status}
                      </span>
                    </td>
                    <td className="p-6 text-sm font-bold text-slate-700">{conv.message_count}</td>
                    <td className="p-6 text-sm text-slate-500 capitalize">{conv.channel}</td>
                    <td className="p-6 text-sm text-slate-400">{new Date(conv.created_at).toLocaleDateString()}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="p-20 text-center">
                    <MessageSquare size={40} className="text-slate-200 mx-auto mb-4" />
                    <p className="text-slate-400 font-bold">No conversations yet</p>
                    <p className="text-slate-300 text-sm mt-1">Conversations will appear here when users chat with your bot</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
