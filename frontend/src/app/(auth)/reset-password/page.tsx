'use client';
import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Lock, ArrowRight, Eye, EyeOff } from 'lucide-react';
import { authApi } from '@/lib/api';

export default function ResetPasswordPage() {
  const router = useRouter();
  const params = useSearchParams();
  const urlToken = useMemo(() => params.get('token') ?? '', [params]);

  const [token, setToken] = useState(urlToken);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token.trim() || !newPassword || !confirmPassword) {
      setError('Please fill in all fields.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setError('');
    setSuccess('');
    setIsSubmitting(true);
    try {
      const res = await authApi.resetPassword(token.trim(), newPassword);
      setSuccess(res.message || 'Password reset successful.');
      setTimeout(() => router.push('/login'), 1200);
    } catch (err: any) {
      setError(err.detail ?? 'Password reset failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputClass = 'block w-full pl-10 pr-10 py-2.5 border border-slate-300 rounded-xl text-sm outline-none focus:border-slate-500 focus:ring-1 focus:ring-slate-500 transition-all';

  return (
    <div>
      <h3 className="text-xl font-bold text-slate-800 mb-2 text-center">Reset password</h3>
      <p className="text-sm text-slate-500 text-center mb-6">
        Set a new secure password for your account.
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
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Reset token</label>
          <input
            type="text"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className="block w-full px-3 py-2.5 border border-slate-300 rounded-xl text-sm outline-none focus:border-slate-500 focus:ring-1 focus:ring-slate-500 transition-all"
            placeholder="Paste reset token"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">New password</label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Lock size={18} className="text-slate-400" />
            </div>
            <input
              type={showPassword ? 'text' : 'password'}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className={inputClass}
              placeholder="Min 8 chars, upper + lower + digit + symbol"
            />
            <button type="button" onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600">
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Confirm new password</label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Lock size={18} className="text-slate-400" />
            </div>
            <input
              type={showConfirmPassword ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className={inputClass}
              placeholder="Repeat new password"
            />
            <button type="button" onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600">
              {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full flex justify-center items-center gap-2 py-3 px-4 rounded-xl shadow-sm text-sm font-medium text-white bg-slate-800 hover:bg-slate-900 transition-colors disabled:opacity-70"
        >
          {isSubmitting ? 'Updating...' : 'Update password'}
          {!isSubmitting && <ArrowRight size={18} />}
        </button>
      </form>

      <div className="mt-6 text-center text-sm">
        <Link href="/login" className="font-bold text-slate-800 hover:text-black transition-colors">
          Back to sign in
        </Link>
      </div>
    </div>
  );
}
