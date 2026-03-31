'use client';
import { useState } from 'react';
import Link from 'next/link';
import { Mail, ArrowRight } from 'lucide-react';
import { authApi } from '@/lib/api';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [resetUrl, setResetUrl] = useState('');

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setError('Please enter your email.');
      return;
    }
    setError('');
    setSuccess('');
    setResetUrl('');
    setIsSubmitting(true);
    try {
      const res = await authApi.forgotPassword(email.trim());
      setSuccess(res.message || 'If that email is registered, password reset instructions are ready.');
      if (res.reset_url) setResetUrl(res.reset_url);
    } catch (err: any) {
      setError(err.detail ?? 'Unable to start password reset right now.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div>
      <h3 className="text-xl font-bold text-slate-800 mb-2 text-center">Forgot your password?</h3>
      <p className="text-sm text-slate-500 text-center mb-6">
        Enter your account email and we&apos;ll help you reset it.
      </p>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600 text-center">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-700 text-center">
          {success}
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-5" noValidate>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Email address</label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Mail size={18} className="text-slate-400" />
            </div>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="block w-full pl-10 pr-3 py-2.5 border border-slate-300 rounded-xl text-sm outline-none focus:border-slate-500 focus:ring-1 focus:ring-slate-500 transition-all"
              placeholder="admin@example.com"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full flex justify-center items-center gap-2 py-3 px-4 rounded-xl shadow-sm text-sm font-medium text-white bg-slate-800 hover:bg-slate-900 transition-colors disabled:opacity-70"
        >
          {isSubmitting ? 'Sending...' : 'Send reset instructions'}
          {!isSubmitting && <ArrowRight size={18} />}
        </button>
      </form>

      {resetUrl && (
        <div className="mt-4 text-xs text-slate-500 break-all">
          <p className="font-semibold mb-1">Local test reset URL:</p>
          <a href={resetUrl} className="text-indigo-600 hover:underline">{resetUrl}</a>
        </div>
      )}

      <div className="mt-6 text-center text-sm">
        <Link href="/login" className="font-bold text-slate-800 hover:text-black transition-colors">
          Back to sign in
        </Link>
      </div>
    </div>
  );
}
