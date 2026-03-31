'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  Bot, Globe, DatabaseZap, Palette, Code2, ArrowRight,
  CheckCircle2, Pipette, Layout, MessageSquare,
  Trash2, Copy, Plus, X, Send, AlertCircle, Loader2,
  RefreshCw, Wifi
} from 'lucide-react';
import { adminApi, widgetApi } from '@/lib/api';

const AVATAR_IMAGES = [
  'https://cdn-icons-png.flaticon.com/512/4712/4712109.png',
  'https://cdn-icons-png.flaticon.com/512/204/204328.png',
  'https://cdn-icons-png.flaticon.com/512/194/194938.png',
  'https://cdn-icons-png.flaticon.com/512/2919/2919572.png',
  'https://cdn-icons-png.flaticon.com/512/3211/3211186.png',
];

const steps = [
  { id: 1, name: 'Train', icon: DatabaseZap },
  { id: 2, name: 'Customize', icon: Palette },
  { id: 3, name: 'Get Your Code', icon: Code2 },
];

// Human-friendly labels for kb_status values returned by the backend
const KB_STATUS_LABELS: Record<string, { label: string; color: string; done: boolean }> = {
  queued:       { label: 'Queued…',                    color: 'text-slate-500',  done: false },
  crawling:     { label: 'Crawling website…',           color: 'text-blue-600',   done: false },
  uploading:    { label: 'Uploading to storage…',       color: 'text-blue-600',   done: false },
  provisioning: { label: 'Setting up AI knowledge base…', color: 'text-indigo-600', done: false },
  indexing:     { label: 'Indexing content…',           color: 'text-purple-600', done: false },
  ready:        { label: 'Ready! AI is trained.',       color: 'text-green-600',  done: true  },
  failed:       { label: 'Training failed.',            color: 'text-red-600',    done: true  },
  not_configured: { label: 'Not configured',            color: 'text-slate-400',  done: false },
};

function ChevronDown({ className = '' }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className={`w-5 h-5 ${className}`}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
    </svg>
  );
}

export default function SetupWizard() {
  const [currentStep, setCurrentStep] = useState(1);

  // ── Step 1 — Train ─────────────────────────────────────────────────────────
  const [websiteUrl, setWebsiteUrl]     = useState('');
  const [isTraining, setIsTraining]     = useState(false);
  const [trainError, setTrainError]     = useState('');
  const [crawlTaskId, setCrawlTaskId]   = useState('');
  const [kbStatus, setKbStatus]         = useState('');
  const [kbError, setKbError]           = useState('');
  const [trainedUrl, setTrainedUrl]     = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Step 2 — Customize ────────────────────────────────────────────────────
  const [botName, setBotName]                   = useState('Tissa');
  const [welcomeMsg, setWelcomeMsg]             = useState("Hi there! 👋 I'm Tissa. I'm here to help with information on our services. How can I assist you today?");
  const [primaryColor, setPrimaryColor]         = useState('#E65C5C');
  const [selectedAvatar, setSelectedAvatar]     = useState(AVATAR_IMAGES[4]);
  const [activeAccordion, setActiveAccordion]   = useState<string | null>('avatar');
  const [showEmailField, setShowEmailField]     = useState(true);
  const [showNameField, setShowNameField]       = useState(true);
  const [isSavingConfig, setIsSavingConfig]     = useState(false);
  const [configSaved, setConfigSaved]           = useState(false);

  // ── Step 3 — Deploy ───────────────────────────────────────────────────────
  const [copySuccess, setCopySuccess]           = useState(false);
  const [deploymentScript, setDeploymentScript] = useState<string>('');
  const [widgetPublicId, setWidgetPublicId]     = useState<string>('');
  const [widgetBaseUrl, setWidgetBaseUrl]       = useState<string>('');
  const [apiBaseUrl, setApiBaseUrl]             = useState<string>('');
  const [isLoadingScript, setIsLoadingScript]   = useState(false);

  // ── Poll crawl status ─────────────────────────────────────────────────────
  const startPolling = (taskId: string) => {
    stopPolling();
    const poll = async () => {
      try {
        const status = await (adminApi as any).getCrawlStatus(taskId) as any;
        const kb = status.kb_status as string;
        setKbStatus(kb);
        if (status.kb_error) setKbError(status.kb_error);

        if (kb === 'ready') {
          stopPolling();
          // Auto-advance to Step 2 after a brief success pause
          setTimeout(() => setCurrentStep(2), 1500);
        } else if (kb === 'failed') {
          stopPolling();
        }
      } catch {
        // Silently ignore transient network errors during polling
      }
    };

    // Run one check immediately so the UI starts moving without waiting for the first interval.
    void poll();
    pollRef.current = setInterval(poll, 2000);
  };

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  // Clean up interval on unmount
  useEffect(() => () => stopPolling(), []);

  // ── Auto-generate API key when entering Step 3 ───────────────────────────
  useEffect(() => {
    if (currentStep !== 3) return;
    if (deploymentScript) return;
    let cancelled = false;
    setIsLoadingScript(true);
    widgetApi.getDeploymentScript()
      .then((res) => {
        if (cancelled) return;
        setDeploymentScript(res.script_tag);
        setWidgetPublicId(res.widget_id);
        setWidgetBaseUrl(res.widget_base_url);
        setApiBaseUrl(res.api_base_url);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setIsLoadingScript(false); });
    return () => { cancelled = true; };
  }, [currentStep, deploymentScript]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleTrain = async () => {
    if (!websiteUrl.trim()) return;
    setIsTraining(true);
    setTrainError('');
    setKbStatus('');
    setKbError('');
    try {
      const url = websiteUrl.startsWith('http') ? websiteUrl : `https://${websiteUrl}`;
      const result = await adminApi.triggerCrawl(url, 100) as any;
      const taskId = result.task_id ?? '';
      setCrawlTaskId(taskId);
      setTrainedUrl(websiteUrl);
      setKbStatus('queued');
      if (taskId) startPolling(taskId);
    } catch (e: any) {
      setTrainError(e.detail ?? 'Crawl failed. Check your backend is running.');
    } finally {
      setIsTraining(false);
    }
  };

  const handleRetrain = () => {
    setKbStatus('');
    setKbError('');
    setCrawlTaskId('');
    setTrainedUrl('');
  };

  const handleSaveConfig = async () => {
    setIsSavingConfig(true);
    try {
      await widgetApi.saveConfig({
        bot_name: botName,
        greeting_message: welcomeMsg,
        primary_color: primaryColor,
        placeholder_text: 'Type a message...',
        position: 'bottom-right',
      });
      setConfigSaved(true);
      setTimeout(() => setCurrentStep(3), 600);
    } catch {
      setConfigSaved(true);
      setTimeout(() => setCurrentStep(3), 600);
    } finally {
      setIsSavingConfig(false);
    }
  };

  const copyCode = () => {
    if (!deploymentScript) return;
    navigator.clipboard.writeText(deploymentScript);
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2500);
  };

  const statusInfo = KB_STATUS_LABELS[kbStatus] ?? null;
  const isPolling = !!crawlTaskId && !statusInfo?.done;

  const AccordionItem = ({ id, title, icon: Icon, children }: any) => {
    const isOpen = activeAccordion === id;
    return (
      <div className="bg-white border border-slate-100 rounded-2xl shadow-sm overflow-hidden mb-3">
        <button onClick={() => setActiveAccordion(isOpen ? null : id)}
          className="w-full flex items-center justify-between p-5 text-left focus:outline-none">
          <div className="flex items-center gap-3.5 text-slate-700">
            <Icon size={20} className="text-slate-400" />
            <span className="font-semibold text-base">{title}</span>
          </div>
          <ChevronDown className={`text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>
        {isOpen && <div className="px-5 pb-5 pt-0 border-t border-slate-50">{children}</div>}
      </div>
    );
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 font-sans">
      {/* Header */}
      <header className="bg-slate-950 text-white p-4 px-10 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-2 font-black text-2xl tracking-tighter text-[#C9FA62]">
          <Bot size={28} /> BotOS
        </div>
        <div className="flex items-center gap-3">
          {steps.map((step, index) => {
            const isActive = currentStep === step.id;
            const isCompleted = currentStep > step.id;
            return (
              <div key={step.id} className="flex items-center gap-3">
                <div className={`flex items-center gap-2.5 px-5 py-2 rounded-full ${isActive ? 'bg-white text-slate-950 font-bold' : isCompleted ? 'bg-slate-800 text-green-400' : 'text-slate-500'}`}>
                  {isCompleted ? <CheckCircle2 size={16} /> : isActive ? <step.icon size={16} /> : <div className="w-4 h-4 rounded-full border border-current text-xs flex items-center justify-center font-bold">{step.id}</div>}
                  <span className="text-sm">{step.name}</span>
                </div>
                {index < steps.length - 1 && <div className={`w-8 h-px ${currentStep > step.id ? 'bg-green-400' : 'bg-slate-700'}`} />}
              </div>
            );
          })}
        </div>
        <button onClick={() => setCurrentStep((p) => Math.min(3, p + 1))}
          className="bg-[#C9FA62] text-slate-950 px-10 py-3 rounded-full font-extrabold text-sm hover:bg-[#b5e64a]">
          Next <ArrowRight size={18} className="inline ml-1" />
        </button>
      </header>

      <main className="flex-1 p-8 lg:p-12 relative flex flex-col items-center">

        {/* ── STEP 1: TRAIN ─────────────────────────────────────────────────── */}
        {currentStep === 1 && (
          <div className="w-full max-w-5xl space-y-10">
            <div className="text-center max-w-3xl mx-auto space-y-4">
              <h1 className="text-5xl font-extrabold text-slate-950 tracking-tight">Setup your Knowledge Base</h1>
              <p className="text-lg text-slate-600 leading-relaxed">
                Provide your website URL and our AI will crawl your pages to understand your business, products, and FAQs.
              </p>
            </div>

            {/* URL input card */}
            {!crawlTaskId && (
              <div className="bg-white p-10 rounded-3xl border border-slate-100 shadow-xl">
                <div className="flex gap-4">
                  <input
                    type="url"
                    value={websiteUrl}
                    onChange={(e) => setWebsiteUrl(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleTrain()}
                    placeholder="www.yourcompany.com"
                    className="flex-1 p-4 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-slate-400 font-mono text-sm"
                  />
                  <button
                    onClick={handleTrain}
                    disabled={!websiteUrl || isTraining}
                    className="px-10 py-4 bg-slate-950 text-white font-bold rounded-xl hover:bg-black transition-all flex items-center gap-2 disabled:opacity-50"
                  >
                    {isTraining
                      ? <><Loader2 size={20} className="animate-spin" /> Starting…</>
                      : <><DatabaseZap size={20} /> Crawl &amp; Train</>}
                  </button>
                </div>
                {trainError && (
                  <div className="mt-4 flex items-center gap-2 text-red-600 bg-red-50 p-3 rounded-xl text-sm">
                    <AlertCircle size={16} /> {trainError}
                  </div>
                )}
              </div>
            )}

            {/* Progress card — shown while crawl is running */}
            {crawlTaskId && (
              <div className="bg-white p-8 rounded-3xl border border-slate-100 shadow-xl max-w-3xl mx-auto w-full">
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center text-slate-400">
                      <Globe size={24} />
                    </div>
                    <div>
                      <p className="font-bold text-slate-900">{trainedUrl}</p>
                      <p className="text-xs text-slate-400 font-mono mt-0.5">Task: {crawlTaskId.slice(0, 20)}…</p>
                    </div>
                  </div>
                  {statusInfo?.done && (
                    <button onClick={handleRetrain}
                      className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-red-600 px-3 py-2 rounded-xl hover:bg-red-50 transition-all">
                      <RefreshCw size={14} /> Retrain
                    </button>
                  )}
                </div>

                {/* Progress steps */}
                <div className="space-y-3">
                  {(['queued', 'crawling', 'uploading', 'provisioning', 'indexing', 'ready'] as const).map((stage) => {
                    const stages = ['queued', 'crawling', 'uploading', 'provisioning', 'indexing', 'ready'];
                    const currentIdx = stages.indexOf(kbStatus);
                    const stageIdx = stages.indexOf(stage);
                    const isDone = currentIdx > stageIdx || kbStatus === 'ready';
                    const isActive = kbStatus === stage;
                    const label = KB_STATUS_LABELS[stage]?.label ?? stage;
                    return (
                      <div key={stage} className={`flex items-center gap-3 p-3 rounded-xl transition-all ${isActive ? 'bg-blue-50 border border-blue-100' : isDone ? 'bg-green-50 border border-green-100' : 'bg-slate-50 border border-slate-100'}`}>
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${isDone ? 'bg-green-500' : isActive ? 'bg-blue-500' : 'bg-slate-200'}`}>
                          {isDone
                            ? <CheckCircle2 size={14} className="text-white" />
                            : isActive
                              ? <Loader2 size={12} className="text-white animate-spin" />
                              : <div className="w-2 h-2 rounded-full bg-slate-400" />}
                        </div>
                        <span className={`text-sm font-medium ${isDone ? 'text-green-700' : isActive ? 'text-blue-700' : 'text-slate-400'}`}>
                          {label}
                        </span>
                      </div>
                    );
                  })}
                </div>

                {/* Error state */}
                {kbStatus === 'failed' && (
                  <div className="mt-4 flex items-start gap-2 text-red-600 bg-red-50 p-4 rounded-xl text-sm">
                    <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-bold">Training failed</p>
                      {kbError && <p className="mt-1 text-xs font-mono">{kbError}</p>}
                      <button onClick={handleRetrain} className="mt-2 text-xs font-bold underline">Try again</button>
                    </div>
                  </div>
                )}

                {/* Success state — show advance button */}
                {kbStatus === 'ready' && (
                  <div className="mt-6 flex items-center justify-between bg-green-50 border border-green-200 p-4 rounded-xl">
                    <div className="flex items-center gap-2 text-green-700 font-bold">
                      <CheckCircle2 size={20} /> AI training complete! Your bot is ready.
                    </div>
                    <button onClick={() => setCurrentStep(2)}
                      className="bg-slate-950 text-white px-6 py-2.5 rounded-xl font-bold text-sm hover:bg-black transition-all flex items-center gap-1.5">
                      Customize Bot <ArrowRight size={16} />
                    </button>
                  </div>
                )}

                {/* Live polling indicator */}
                {isPolling && (
                  <div className="mt-4 flex items-center gap-2 text-xs text-slate-400">
                    <Wifi size={12} className="animate-pulse" /> Checking status every 2 seconds…
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── STEP 2: CUSTOMIZE ─────────────────────────────────────────────── */}
        {currentStep === 2 && (
          <div className="w-full flex-1 flex flex-col">
            <div className="absolute inset-0 bg-slate-100 z-0 pt-[72px]">
              <div className="w-full h-full bg-gradient-to-br from-slate-200 to-slate-100 opacity-60" />
            </div>
            <div className="flex-1 flex relative z-10 gap-10">
              <div className="w-full max-w-sm p-4 pt-12">
                <div className="bg-white rounded-[2rem] p-5 shadow-2xl border border-slate-100/50">
                  <h3 className="text-xl font-bold text-slate-950 mb-6 p-1">Customization</h3>
                  <div className="space-y-1">
                    <AccordionItem id="avatar" title="Avatar" icon={MessageSquare}>
                      <div className="grid grid-cols-4 gap-3">
                        {AVATAR_IMAGES.map((img, i) => (
                          <button key={i} onClick={() => setSelectedAvatar(img)} className="relative group">
                            <img src={img} alt={`Avatar ${i}`} className={`w-14 h-14 rounded-full border-4 object-cover ${selectedAvatar === img ? 'border-red-400' : 'border-white'}`} />
                          </button>
                        ))}
                        <button className="w-14 h-14 bg-slate-100 rounded-full flex items-center justify-center border-4 border-white text-slate-400 font-bold hover:bg-slate-200">
                          <Plus size={20} />
                        </button>
                      </div>
                    </AccordionItem>

                    <AccordionItem id="message" title="First Message" icon={MessageSquare}>
                      <label className="text-xs font-semibold text-slate-700 block mb-2">First message:</label>
                      <textarea value={welcomeMsg} onChange={(e) => setWelcomeMsg(e.target.value)} rows={5}
                        className="w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl text-sm leading-relaxed text-slate-700 outline-none focus:border-slate-400 resize-none" />
                      <label className="text-xs font-semibold text-slate-700 block mt-4 mb-2">Display name:</label>
                      <input type="text" value={botName} onChange={(e) => setBotName(e.target.value)}
                        className="w-full p-4 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-slate-400 text-sm font-semibold" />
                    </AccordionItem>

                    <AccordionItem id="forms" title="Forms Customization" icon={Layout}>
                      <p className="text-xs text-slate-500 mb-4 font-medium">Select fields for the pre-chat form.</p>
                      <div className="space-y-3">
                        {[{ label: 'Collect Email', checked: showEmailField, set: setShowEmailField },
                          { label: 'Collect Name', checked: showNameField, set: setShowNameField }].map(({ label, checked, set }) => (
                          <div key={label} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-100">
                            <span className="text-sm font-medium text-slate-800">{label}</span>
                            <input type="checkbox" checked={checked} onChange={() => set(!checked)} className="w-5 h-5 accent-slate-900 cursor-pointer" />
                          </div>
                        ))}
                      </div>
                    </AccordionItem>

                    <AccordionItem id="color" title="Color" icon={Pipette}>
                      <div className="flex items-center gap-4">
                        <input type="color" value={primaryColor} onChange={(e) => setPrimaryColor(e.target.value)}
                          className="h-14 w-20 rounded-xl cursor-pointer border-none p-0 bg-transparent" />
                        <input type="text" value={primaryColor} onChange={(e) => setPrimaryColor(e.target.value)}
                          className="flex-1 p-4 bg-slate-50 border border-slate-200 rounded-xl font-mono text-sm outline-none" />
                      </div>
                    </AccordionItem>
                  </div>

                  <button onClick={handleSaveConfig} disabled={isSavingConfig}
                    className="w-full mt-10 bg-slate-950 text-white py-5 rounded-2xl font-bold hover:bg-black transition-all shadow-xl shadow-slate-200 flex items-center justify-center gap-2 disabled:opacity-70">
                    {isSavingConfig ? <><Loader2 size={18} className="animate-spin" /> Saving…</> :
                     configSaved ? <><CheckCircle2 size={18} className="text-[#C9FA62]" /> Saved!</> :
                     'Set as Default'}
                  </button>
                </div>
              </div>

              {/* Live Preview */}
              <div className="flex-1 flex items-end justify-end p-10">
                <div className="w-full max-w-[380px] bg-white rounded-3xl shadow-2xl border border-slate-100 overflow-hidden">
                  <div style={{ backgroundColor: primaryColor }} className="p-6 text-white flex justify-between items-center transition-all duration-300">
                    <div className="flex items-center gap-3">
                      <img src={selectedAvatar} alt="Bot Avatar" className="w-10 h-10 rounded-full object-cover border-2 border-white/40" />
                      <div>
                        <h4 className="font-bold leading-tight">{botName}</h4>
                        <span className="text-[10px] opacity-75 font-medium">Ready to assist you today?</span>
                      </div>
                    </div>
                    <X size={20} className="opacity-40" />
                  </div>
                  <div className="h-[280px] p-6 bg-slate-50/60 flex flex-col gap-5 overflow-y-auto">
                    <div className="bg-white p-4 rounded-2xl rounded-tl-none shadow-sm text-sm text-slate-800 leading-relaxed border border-slate-100">
                      {welcomeMsg}
                    </div>
                    <div className="space-y-4">
                      {showNameField && (
                        <div>
                          <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1">Your Name</label>
                          <input type="text" placeholder="John Doe" className="w-full p-3 bg-white border border-slate-200 rounded-xl outline-none" readOnly />
                        </div>
                      )}
                      {showEmailField && (
                        <div>
                          <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1">Your Email</label>
                          <input type="email" placeholder="john@example.com" className="w-full p-3 bg-white border border-slate-200 rounded-xl outline-none" readOnly />
                        </div>
                      )}
                      <button style={{ backgroundColor: primaryColor }} className="w-full py-3.5 text-white font-bold rounded-xl shadow-md flex items-center justify-center gap-2">
                        Let&apos;s chat! <Send size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="p-4 bg-white border-t border-slate-100 flex gap-2">
                    <div className="flex-1 bg-slate-100 px-4 py-2 rounded-full text-sm text-slate-400">Type a message...</div>
                    <div style={{ backgroundColor: primaryColor }} className="w-10 h-10 rounded-full flex items-center justify-center text-white shadow-md">
                      <ArrowRight size={18} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── STEP 3: DEPLOY ────────────────────────────────────────────────── */}
        {currentStep === 3 && (
          <div className="w-full max-w-4xl space-y-12 text-center flex-1 flex flex-col items-center justify-center">
            <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight">Installation</h1>
            <p className="text-lg text-slate-600 max-w-xl mx-auto leading-relaxed">
              Copy this script and paste it before the closing <code className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-800 font-bold">&lt;/body&gt;</code> tag of your website.
            </p>
            <div className="bg-white p-10 rounded-[2rem] border border-slate-100 shadow-xl relative w-full text-left font-mono text-sm leading-relaxed">
              <div className="absolute top-4 right-4 flex items-center gap-2 text-xs bg-slate-100 px-3 py-1.5 rounded-full text-slate-500 font-sans">
                {copySuccess ? <CheckCircle2 size={16} className="text-green-500" /> : <DatabaseZap size={16} />}
                data-bot-id=&quot;{widgetPublicId || (isLoadingScript ? 'Preparing...' : 'Not ready')}&quot;
              </div>
              <pre className="text-slate-600 p-8 pt-10 bg-slate-50 border border-slate-200 rounded-2xl overflow-x-auto">
                {deploymentScript || `<script\n  src="${widgetBaseUrl || (typeof window !== 'undefined' ? window.location.origin : 'https://your-widget-domain.com')}/embed.js"\n  data-bot-id="${widgetPublicId || 'YOUR_WIDGET_ID_HERE'}"\n  data-base-url="${widgetBaseUrl || (typeof window !== 'undefined' ? window.location.origin : 'https://your-widget-domain.com')}"\n  data-api-url="${apiBaseUrl || (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:8000` : 'https://your-api-domain.com')}"\n  defer\n></script>`}
              </pre>
              <button
                onClick={copyCode}
                disabled={!deploymentScript || isLoadingScript}
                className="mt-6 w-full flex items-center justify-center gap-2 px-8 py-3.5 bg-slate-950 text-white font-bold rounded-xl hover:bg-black transition-all disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {copySuccess ? 'Copied to Clipboard!' : isLoadingScript ? 'Preparing script...' : 'Copy Script'}
                {!copySuccess && <Copy size={18} />}
              </button>
            </div>
            <Link href="/admin/chatbots" className="text-indigo-600 font-bold hover:underline flex items-center gap-1">
              View your chatbots <ArrowRight size={16} />
            </Link>
          </div>
        )}
      </main>
    </div>
  );
}
