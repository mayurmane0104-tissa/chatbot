'use client';
import { useState } from 'react'; // If you're using state on this page
import Link from 'next/link';
import { 
  Bot, 
  Zap, 
  ShieldCheck, 
  MessageSquare, 
  Code2, 
  ArrowRight, 
  Globe,
  CheckCircle2 // <--- ADD THIS LINE
} from 'lucide-react';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-white">
      {/* --- NAVBAR --- */}
      <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-md border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-slate-800 rounded-lg flex items-center justify-center">
                <Bot size={20} className="text-white" />
              </div>
              <span className="font-bold text-slate-900 text-xl tracking-tight">ChatBot AI</span>
            </div>
            
            <div className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-sm font-medium text-slate-600 hover:text-slate-900">Features</a>
              <a href="#how-it-works" className="text-sm font-medium text-slate-600 hover:text-slate-900">How it Works</a>
              <Link href="/login" className="text-sm font-medium text-slate-600 hover:text-slate-900">Sign In</Link>
              <Link href="/register" className="bg-slate-800 text-white px-5 py-2.5 rounded-full text-sm font-medium hover:bg-slate-900 transition-all shadow-md">
                Get Started Free
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* --- HERO SECTION --- */}
      <section className="pt-32 pb-20 px-4">
        <div className="max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-bold mb-6 border border-slate-200 uppercase tracking-widest">
            <Zap size={14} className="fill-slate-600" />
            AI-Powered Customer Support
          </div>
          <h1 className="text-5xl md:text-7xl font-extrabold text-slate-900 mb-6 tracking-tight leading-tight">
            Engage your visitors <br />
            <span className="text-slate-500">with intelligent chat.</span>
          </h1>
          <p className="text-lg text-slate-600 mb-10 max-w-2xl mx-auto leading-relaxed">
            Build, customize, and embed a smart chatbot on your website in under 5 minutes. 
            Capture leads and support customers 24/7 without lifting a finger.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/register" className="w-full sm:w-auto px-8 py-4 bg-slate-800 text-white rounded-2xl font-bold hover:bg-slate-900 transition-all shadow-xl flex items-center justify-center gap-2">
              Start Building Now <ArrowRight size={20} />
            </Link>
            <Link href="#features" className="w-full sm:w-auto px-8 py-4 bg-white text-slate-800 border border-slate-200 rounded-2xl font-bold hover:bg-slate-50 transition-all">
              View Demo
            </Link>
          </div>
        </div>
      </section>

      {/* --- FEATURES SECTION --- */}
      <section id="features" className="py-24 bg-slate-50 border-y border-slate-100">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">Everything you need to grow</h2>
            <p className="text-slate-500">Powerful features to help you automate customer interactions.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center mb-6">
                <MessageSquare size={24} />
              </div>
              <h3 className="text-xl font-bold text-slate-800 mb-3">Instant Responses</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Our AI understands customer intent and provides accurate answers instantly, reducing wait times to zero.
              </p>
            </div>

            <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <div className="w-12 h-12 bg-purple-50 text-purple-600 rounded-2xl flex items-center justify-center mb-6">
                <Code2 size={24} />
              </div>
              <h3 className="text-xl font-bold text-slate-800 mb-3">One-Line Embed</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Just copy and paste a single line of JavaScript into your website header to get started. Works with any platform.
              </p>
            </div>

            <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <div className="w-12 h-12 bg-green-50 text-green-600 rounded-2xl flex items-center justify-center mb-6">
                <ShieldCheck size={24} />
              </div>
              <h3 className="text-xl font-bold text-slate-800 mb-3">Lead Capture</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Automatically collect names and emails from visitors before starting a chat, sync them directly to your CRM.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* --- HOW IT WORKS --- */}
      <section id="how-it-works" className="py-24">
        <div className="max-w-4xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900">Set up in 3 simple steps</h2>
          </div>
          
          <div className="space-y-12">
            <div className="flex items-start gap-6">
              <div className="flex-shrink-0 w-10 h-10 bg-slate-800 text-white rounded-full flex items-center justify-center font-bold">1</div>
              <div>
                <h4 className="text-xl font-bold text-slate-900 mb-1">Create your Bot</h4>
                <p className="text-slate-600">Give your bot a name, personality, and provide the data it needs to learn about your business.</p>
              </div>
            </div>
            
            <div className="flex items-start gap-6">
              <div className="flex-shrink-0 w-10 h-10 bg-slate-800 text-white rounded-full flex items-center justify-center font-bold">2</div>
              <div>
                <h4 className="text-xl font-bold text-slate-900 mb-1">Customize the Look</h4>
                <p className="text-slate-600">Adjust colors, fonts, and avatars to match your brand's unique identity perfectly.</p>
              </div>
            </div>

            <div className="flex items-start gap-6">
              <div className="flex-shrink-0 w-10 h-10 bg-slate-800 text-white rounded-full flex items-center justify-center font-bold">3</div>
              <div>
                <h4 className="text-xl font-bold text-slate-900 mb-1">Go Live</h4>
                <p className="text-slate-600">Copy the embed code and paste it on your site. Start talking to your customers immediately!</p>
              </div>
            </div>
          </div>
        </div>
      </section>
{/* --- PRICING SECTION --- */}
      <section id="pricing" className="py-24 bg-slate-50 border-t border-slate-100">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">Simple, transparent pricing</h2>
            <p className="text-slate-500">Choose the plan that's right for your business growth.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
            
            {/* Free Tier */}
            <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm flex flex-col">
              <h4 className="font-bold text-slate-900 text-lg mb-2">Starter</h4>
              <p className="text-slate-500 text-sm mb-6">Perfect for testing the waters.</p>
              <div className="mb-6">
                <span className="text-4xl font-extrabold text-slate-900">$0</span>
                <span className="text-slate-500">/month</span>
              </div>
              <ul className="space-y-4 mb-8 flex-1">
                <li className="flex items-center gap-3 text-sm text-slate-600">
                  <CheckCircle2 size={18} className="text-green-500" /> 1 Chatbot
                </li>
                <li className="flex items-center gap-3 text-sm text-slate-600">
                  <CheckCircle2 size={18} className="text-green-500" /> 100 Chats/mo
                </li>
                <li className="flex items-center gap-3 text-sm text-slate-600">
                  <CheckCircle2 size={18} className="text-green-500" /> Basic Customization
                </li>
              </ul>
              <Link href="/register" className="w-full py-3 px-4 border border-slate-200 rounded-xl text-center text-sm font-bold text-slate-800 hover:bg-slate-50 transition-colors">
                Get Started
              </Link>
            </div>

            {/* Pro Tier (Featured) */}
            <div className="bg-slate-900 p-8 rounded-3xl border border-slate-800 shadow-2xl flex flex-col relative scale-105 z-10">
              <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-blue-500 text-white text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-widest">
                Most Popular
              </div>
              <h4 className="font-bold text-white text-lg mb-2">Professional</h4>
              <p className="text-slate-400 text-sm mb-6">For growing businesses.</p>
              <div className="mb-6">
                <span className="text-4xl font-extrabold text-white">$29</span>
                <span className="text-slate-400">/month</span>
              </div>
              <ul className="space-y-4 mb-8 flex-1">
                <li className="flex items-center gap-3 text-sm text-slate-300">
                  <CheckCircle2 size={18} className="text-blue-400" /> Unlimited Chatbots
                </li>
                <li className="flex items-center gap-3 text-sm text-slate-300">
                  <CheckCircle2 size={18} className="text-blue-400" /> 5,000 Chats/mo
                </li>
                <li className="flex items-center gap-3 text-sm text-slate-300">
                  <CheckCircle2 size={18} className="text-blue-400" /> Advanced AI Training
                </li>
                <li className="flex items-center gap-3 text-sm text-slate-300">
                  <CheckCircle2 size={18} className="text-blue-400" /> Remove Branding
                </li>
              </ul>
              <Link href="/register" className="w-full py-3 px-4 bg-blue-500 text-white rounded-xl text-center text-sm font-bold hover:bg-blue-600 transition-colors">
                Start Pro Trial
              </Link>
            </div>

            {/* Enterprise Tier */}
            <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm flex flex-col">
              <h4 className="font-bold text-slate-900 text-lg mb-2">Enterprise</h4>
              <p className="text-slate-500 text-sm mb-6">Advanced security & scale.</p>
              <div className="mb-6">
                <span className="text-4xl font-extrabold text-slate-900">Custom</span>
              </div>
              <ul className="space-y-4 mb-8 flex-1">
                <li className="flex items-center gap-3 text-sm text-slate-600">
                  <CheckCircle2 size={18} className="text-green-500" /> Dedicated Account Manager
                </li>
                <li className="flex items-center gap-3 text-sm text-slate-600">
                  <CheckCircle2 size={18} className="text-green-500" /> Custom API Access
                </li>
                <li className="flex items-center gap-3 text-sm text-slate-600">
                  <CheckCircle2 size={18} className="text-green-500" /> SSO & SAML
                </li>
              </ul>
              <Link href="/register" className="w-full py-3 px-4 border border-slate-200 rounded-xl text-center text-sm font-bold text-slate-800 hover:bg-slate-50 transition-colors">
                Contact Sales
              </Link>
            </div>

          </div>
        </div>
      </section>
      {/* --- FOOTER --- */}
      <footer className="py-12 border-t border-slate-100 text-center">
        <p className="text-slate-400 text-sm">© 2026 ChatBot AI Platform. All rights reserved.</p>
      </footer>
    </div>
  );
}