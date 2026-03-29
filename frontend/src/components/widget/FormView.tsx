import { useState } from 'react';
import { useChatStore } from '@/lib/store';
import { ArrowLeft, MoreHorizontal, Minus, Trash2, User } from 'lucide-react';
import styles from '@/app/widget/[botId]/widget.module.css';

export default function FormView() {
  const { setView, closeWidget, setUserProfile, startNewSession } = useChatStore();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [showError, setShowError] = useState(false);
  const [form, setForm] = useState({
    name: '', email: '', phone: '', organization: '', industry: '', role: '',
  });

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!form.name || !form.email || !form.role) {
      setShowError(true);
      return;
    }
    // Save profile to store — will be sent with every chat message
    setUserProfile({
      name: form.name,
      email: form.email,
      phone: form.phone,
      organization: form.organization,
      industry: form.industry,
      role: form.role,
    });
    startNewSession();
    setShowError(false);
    setView('chat');
  };

  const inputClass = (required: boolean, hasError: boolean) =>
    `w-full border rounded-lg p-2.5 outline-none transition-all bg-white text-sm ${
      required && hasError ? 'border-red-400 focus:border-red-500 focus:ring-1 focus:ring-red-500' :
      'border-slate-300 focus:border-slate-500 focus:ring-1 focus:ring-slate-500'
    }`;

  return (
    <div className={`${styles.widgetContainer} rounded-3xl overflow-hidden bg-slate-50 relative flex flex-col`}>
      {/* Header */}
      <div className="flex justify-between items-start p-4 relative z-10">
        <div className="flex gap-2 relative">
          <button onClick={() => setView('welcome')} className="p-2 bg-slate-200/50 rounded-full hover:bg-slate-200 transition-colors">
            <ArrowLeft size={18} className="text-slate-700" />
          </button>
          <button onClick={() => setIsMenuOpen(!isMenuOpen)} className="p-2 bg-slate-200/50 rounded-full hover:bg-slate-200 transition-colors">
            <MoreHorizontal size={18} className="text-slate-700" />
          </button>
          {isMenuOpen && (
            <div className="absolute top-12 left-10 w-40 bg-white border border-slate-100 rounded-xl shadow-lg z-50 overflow-hidden">
              <button onClick={() => { useChatStore.getState().clearChat(); setIsMenuOpen(false); }}
                className="w-full text-left px-4 py-3 text-sm text-red-600 hover:bg-slate-50 flex items-center gap-2">
                <Trash2 size={16} /> Clear chat
              </button>
            </div>
          )}
        </div>
        <button onClick={closeWidget} className="p-2 bg-slate-200/50 rounded-full hover:bg-slate-200 transition-colors">
          <Minus size={18} className="text-slate-700" />
        </button>
      </div>

      {/* Agent pill */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-white rounded-full pr-5 pl-2 py-1.5 flex items-center gap-3 shadow-md border border-slate-100 z-20">
        <div className="relative">
          <div className="w-8 h-8 bg-slate-100 rounded-full flex items-center justify-center text-slate-700 font-bold text-sm">T</div>
          <div className="absolute top-0 right-0 w-2.5 h-2.5 bg-green-500 rounded-full border-2 border-white" />
        </div>
        <div>
          <p className="text-sm font-bold text-slate-800 leading-none">Tissa</p>
          <p className="text-[10px] text-slate-500 mt-0.5">Ready to help</p>
        </div>
      </div>

      {/* Form */}
      <div className={`flex-1 px-5 pb-6 pt-10 ${styles.scrollArea}`}>
        <div className="relative mt-4">
          <div className="absolute -left-3 -top-3 w-8 h-8 bg-emerald-600 rounded-full flex items-center justify-center border-4 border-slate-50 z-10 shadow-sm">
            <User size={14} className="text-white" />
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
            <p className="text-slate-800 font-medium mb-6 text-lg">Welcome to Tissa! 👋</p>

            <form onSubmit={handleSubmit} noValidate className="space-y-4">
              <div>
                <label className="block text-sm text-slate-700 mb-1.5">Name: <span className="text-red-500">*</span></label>
                <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className={inputClass(true, showError && !form.name)} placeholder="John Doe" />
                {showError && !form.name && <p className="text-red-500 text-xs mt-1.5">Please enter your name.</p>}
              </div>

              <div>
                <label className="block text-sm text-slate-700 mb-1.5">E-mail: <span className="text-red-500">*</span></label>
                <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className={inputClass(true, showError && !form.email)} placeholder="john@example.com" />
                {showError && !form.email && <p className="text-red-500 text-xs mt-1.5">Please enter your email.</p>}
              </div>

              <div>
                <label className="block text-sm text-slate-700 mb-1.5">Mobile Number: <span className="text-slate-400 text-xs">(Optional)</span></label>
                <input type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  className={inputClass(false, false)} placeholder="+91 9876543210" />
              </div>

              <div>
                <label className="block text-sm text-slate-700 mb-1.5">Organization:</label>
                <input type="text" value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })}
                  className={inputClass(false, false)} placeholder="Your company name" />
              </div>

              <div>
                <label className="block text-sm text-slate-700 mb-1.5">Role: <span className="text-red-500">*</span></label>
                <input type="text" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}
                  className={inputClass(true, showError && !form.role)} placeholder="Founder, HR Manager, CTO, etc." />
                {showError && !form.role && <p className="text-red-500 text-xs mt-1.5">Please enter your role.</p>}
              </div>

              <div>
                <label className="block text-sm text-slate-700 mb-1.5">Industry:</label>
                <input type="text" value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })}
                  className={inputClass(false, false)} placeholder="Technology, Finance, etc." />
              </div>

              <div className="pt-2">
                <p className="text-sm text-slate-800 leading-relaxed">
                  Our Chat is always open! If you get <span className="underline decoration-slate-300 underline-offset-2">disconnected</span>, just come back anytime.
                </p>
              </div>

              <button type="submit" className="w-full bg-slate-700 hover:bg-slate-800 text-white font-medium py-3 rounded-xl mt-6 transition-colors shadow-sm">
                Start the chat
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
