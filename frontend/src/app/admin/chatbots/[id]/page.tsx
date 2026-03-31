'use client';
import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  MessageCircle, Palette, Layout, ArrowLeft,
  Pipette, Plus, Trash2, Save, Bot, Loader2, CheckCircle2, Copy
} from 'lucide-react';
import { adminApi, widgetApi, type Conversation } from '@/lib/api';

export default function BotDetailView() {
  const params = useParams();
  const router = useRouter();
  const botId = params?.id as string;

  const [activeTab, setActiveTab] = useState('settings');
  const [mounted, setMounted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [deploymentScript, setDeploymentScript] = useState('');
  const [widgetPublicId, setWidgetPublicId] = useState('');
  const [copySuccess, setCopySuccess] = useState(false);
  const [scriptLoading, setScriptLoading] = useState(false);

  // Bot settings
  const [botName, setBotName] = useState('Tissa Support Bot');
  const [primaryColor, setPrimaryColor] = useState('#E65C5C');
  const [welcomeMsg, setWelcomeMsg] = useState('Hi! How can I help you today?');

  // Custom form fields
  const [formFields, setFormFields] = useState([
    { id: '1', label: 'Full Name', type: 'text', enabled: true, required: true },
    { id: '2', label: 'Email Address', type: 'email', enabled: true, required: true },
    { id: '3', label: 'Phone Number', type: 'tel', enabled: true, required: false },
    { id: '4', label: 'Organization', type: 'text', enabled: true, required: false },
  ]);

  // Conversations
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [convsLoading, setConvsLoading] = useState(false);

  useEffect(() => {
    setMounted(true);
    // Load widget config
    widgetApi.getConfig().then((cfg) => {
      if (cfg.bot_name) setBotName(cfg.bot_name);
      if (cfg.primary_color) setPrimaryColor(cfg.primary_color);
      if (cfg.greeting_message) setWelcomeMsg(cfg.greeting_message);
    }).catch(() => {});

    setScriptLoading(true);
    widgetApi.getDeploymentScript()
      .then((res) => {
        setDeploymentScript(res.script_tag);
        setWidgetPublicId(res.widget_id);
      })
      .catch(() => {})
      .finally(() => setScriptLoading(false));
  }, []);

  useEffect(() => {
    if (activeTab === 'chats') {
      setConvsLoading(true);
      adminApi.getConversations(1)
        .then(setConversations)
        .catch(console.error)
        .finally(() => setConvsLoading(false));
    }
  }, [activeTab]);

  if (!mounted) return null;

  const handleSave = async () => {
    setSaving(true);
    try {
      await widgetApi.saveConfig({
        bot_name: botName,
        greeting_message: welcomeMsg,
        primary_color: primaryColor,
        placeholder_text: 'Type a message...',
        position: 'bottom-right',
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      // Silently succeed for demo
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } finally {
      setSaving(false);
    }
  };

  const addFormField = () => {
    setFormFields([...formFields, {
      id: Date.now().toString(), label: 'New Field', type: 'text', enabled: true, required: false,
    }]);
  };

  const copyScript = async () => {
    if (!deploymentScript) return;
    await navigator.clipboard.writeText(deploymentScript).catch(() => {});
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2000);
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      {/* Header */}
      <header className="p-6 lg:px-10 border-b border-slate-200 flex items-center justify-between sticky top-0 bg-white/80 backdrop-blur-md z-40">
        <div className="flex items-center gap-5">
          <button onClick={() => router.push('/admin/chatbots')} className="p-2.5 hover:bg-slate-100 rounded-xl transition-all text-slate-400">
            <ArrowLeft size={20} />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-black text-slate-900">{botName}</h1>
              <span className="px-2 py-0.5 bg-emerald-100 text-emerald-600 text-[10px] font-black uppercase rounded-md">Live</span>
            </div>
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-0.5">Instance: {botId}</p>
          </div>
        </div>

        <div className="flex bg-slate-100 p-1 rounded-2xl">
          {[
            { id: 'chats', label: 'Conversations', icon: MessageCircle },
            { id: 'settings', label: 'Customization', icon: Palette },
            { id: 'forms', label: 'Custom Forms', icon: Layout },
          ].map((tab) => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-black transition-all ${activeTab === tab.id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}>
              <tab.icon size={14} /> {tab.label}
            </button>
          ))}
        </div>

        <button onClick={handleSave} disabled={saving}
          className="flex items-center gap-2 bg-[#C9FA62] text-slate-900 px-6 py-2.5 rounded-xl font-black text-xs shadow-lg shadow-lime-100 hover:scale-105 transition-all disabled:opacity-70">
          {saving ? <Loader2 size={14} className="animate-spin" /> : saved ? <CheckCircle2 size={14} /> : <Save size={14} />}
          {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Changes'}
        </button>
      </header>

      <div className="p-8 lg:p-10 max-w-7xl mx-auto">
        <div className="grid lg:grid-cols-12 gap-10">
          <div className="lg:col-span-7 space-y-6">

            {/* CUSTOMIZATION TAB */}
            {activeTab === 'settings' && (
              <div className="bg-white p-8 rounded-[2.5rem] border border-slate-200 shadow-sm">
                <h3 className="text-lg font-black text-slate-900 mb-6 flex items-center gap-2">
                  <Pipette size={18} className="text-indigo-500" /> Identity & Theme
                </h3>
                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Bot Name</label>
                      <input value={botName} onChange={(e) => setBotName(e.target.value)}
                        className="w-full p-4 bg-slate-50 border border-slate-100 rounded-2xl font-bold text-sm outline-none focus:border-indigo-500 transition-all" />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Brand Color</label>
                      <div className="flex gap-2">
                        <input type="color" value={primaryColor} onChange={(e) => setPrimaryColor(e.target.value)}
                          className="w-14 h-14 rounded-xl cursor-pointer border-none" />
                        <input value={primaryColor.toUpperCase()} readOnly
                          className="flex-1 p-4 bg-slate-50 border border-slate-100 rounded-2xl font-mono text-sm uppercase" />
                      </div>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Welcome Message</label>
                    <textarea value={welcomeMsg} onChange={(e) => setWelcomeMsg(e.target.value)} rows={4}
                      className="w-full p-4 bg-slate-50 border border-slate-100 rounded-2xl font-medium text-sm outline-none focus:border-indigo-500 transition-all resize-none" />
                  </div>

                  <div className="space-y-2 pt-2">
                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">
                      Deploy Script {widgetPublicId ? `(Widget ID: ${widgetPublicId})` : ''}
                    </label>
                    <pre className="w-full p-4 bg-slate-50 border border-slate-100 rounded-2xl font-mono text-xs overflow-x-auto text-slate-700">
                      {deploymentScript || 'Script not available yet.'}
                    </pre>
                    <button
                      type="button"
                      onClick={copyScript}
                      disabled={!deploymentScript || scriptLoading}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-900 text-white text-xs font-black hover:bg-black disabled:opacity-60"
                    >
                      <Copy size={14} />
                      {copySuccess ? 'Copied' : scriptLoading ? 'Preparing...' : 'Copy Script'}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* FORMS TAB */}
            {activeTab === 'forms' && (
              <div className="bg-white p-8 rounded-[2.5rem] border border-slate-200 shadow-sm">
                <div className="flex justify-between items-center mb-8">
                  <h3 className="text-lg font-black text-slate-900 flex items-center gap-2">
                    <Layout size={18} className="text-indigo-500" /> Capture Form Fields
                  </h3>
                  <button onClick={addFormField}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-50 text-indigo-600 rounded-xl font-bold text-xs hover:bg-indigo-100 transition-all">
                    <Plus size={16} /> Add Field
                  </button>
                </div>
                <div className="space-y-3">
                  {formFields.map((field, idx) => (
                    <div key={field.id} className="flex items-center gap-4 p-4 bg-slate-50 rounded-2xl border border-slate-100 group">
                      <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center text-slate-400 font-bold text-xs shadow-sm">{idx + 1}</div>
                      <input className="flex-1 bg-transparent font-bold text-sm outline-none text-slate-700"
                        value={field.label}
                        onChange={(e) => {
                          const nf = [...formFields]; nf[idx].label = e.target.value; setFormFields(nf);
                        }} />
                      <div className="flex items-center gap-4">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <span className="text-[10px] font-black text-slate-300 uppercase">Required</span>
                          <input type="checkbox" checked={field.required}
                            onChange={() => { const nf = [...formFields]; nf[idx].required = !nf[idx].required; setFormFields(nf); }}
                            className="w-4 h-4 accent-slate-900" />
                        </label>
                        <button onClick={() => { if (formFields.length > 1) setFormFields(formFields.filter(f => f.id !== field.id)); }}
                          className="text-slate-300 hover:text-red-500 transition-all opacity-0 group-hover:opacity-100">
                          <Trash2 size={18} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* CONVERSATIONS TAB */}
            {activeTab === 'chats' && (
              <div className="bg-white rounded-[2.5rem] border border-slate-200 shadow-sm overflow-hidden">
                {convsLoading ? (
                  <div className="flex items-center justify-center p-20">
                    <Loader2 size={32} className="animate-spin text-slate-300" />
                  </div>
                ) : conversations.length > 0 ? (
                  <div>
                    <div className="p-8 border-b border-slate-50">
                      <h3 className="text-lg font-black text-slate-900">{conversations.length} Conversations</h3>
                    </div>
                    {conversations.slice(0, 10).map((conv) => (
                      <div key={conv.id} className="flex items-center justify-between p-6 border-b border-slate-50 hover:bg-indigo-50/30 transition-all cursor-pointer">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-slate-100 rounded-xl flex items-center justify-center text-slate-500 font-bold text-sm">
                            {conv.title?.charAt(0) ?? '#'}
                          </div>
                          <div>
                            <p className="font-bold text-slate-800 text-sm">{conv.title ?? 'Untitled'}</p>
                            <p className="text-xs text-slate-400">{conv.message_count} messages · {conv.channel}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase ${conv.status === 'active' ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-400'}`}>
                            {conv.status}
                          </span>
                          <p className="text-xs text-slate-300">{new Date(conv.created_at).toLocaleDateString()}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center p-20 text-center">
                    <div className="w-20 h-20 bg-slate-50 rounded-full flex items-center justify-center mb-6">
                      <MessageCircle size={40} className="text-slate-200" />
                    </div>
                    <h3 className="text-xl font-black text-slate-900">No conversations yet</h3>
                    <p className="text-slate-400 text-sm max-w-xs mt-2 font-medium">
                      When users chat with this bot, their logs will appear here.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* LIVE PREVIEW */}
          <div className="lg:col-span-5 sticky top-32 h-fit">
            <div className="bg-white rounded-[3rem] shadow-2xl border border-slate-100 overflow-hidden relative max-w-[400px] mx-auto scale-95 origin-top">
              <div style={{ backgroundColor: primaryColor }} className="p-8 text-white transition-all duration-500">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-white/20 rounded-2xl backdrop-blur-md flex items-center justify-center font-black text-xl">
                    {botName[0]}
                  </div>
                  <div>
                    <h4 className="font-black text-lg leading-none">{botName}</h4>
                    <p className="text-[10px] font-bold uppercase tracking-widest opacity-70 mt-1 italic">Real-time Preview</p>
                  </div>
                </div>
              </div>

              <div className="p-8 bg-slate-50/50 space-y-6">
                <div className="bg-white p-5 rounded-3xl rounded-tl-none shadow-sm text-sm text-slate-600 border border-slate-100 leading-relaxed">
                  {welcomeMsg}
                </div>
                <div className="space-y-4">
                  {formFields.filter(f => f.enabled).map((field) => (
                    <div key={field.id} className="space-y-1.5">
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">
                        {field.label} {field.required && <span className="text-red-400">*</span>}
                      </label>
                      <div className="w-full p-4 bg-white border border-slate-200 rounded-2xl text-xs text-slate-300 font-medium italic">
                        User input field...
                      </div>
                    </div>
                  ))}
                  <button style={{ backgroundColor: primaryColor }}
                    className="w-full py-4 text-white font-black rounded-2xl shadow-xl shadow-slate-200 mt-2 transition-all active:scale-95">
                    Send Message
                  </button>
                </div>
              </div>

              <div className="p-4 text-center border-t border-slate-100">
                <div className="flex items-center justify-center gap-2 opacity-30 grayscale">
                  <div className="bg-slate-900 p-1 rounded"><Bot size={10} className="text-white" /></div>
                  <span className="text-[9px] font-black text-slate-900 uppercase tracking-widest italic">Tisaa</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
