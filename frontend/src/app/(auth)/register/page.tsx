'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Mail, Lock, User, Building2, ArrowRight, Eye, EyeOff } from 'lucide-react';
import { authApi, setTokens } from '@/lib/api';
import { useAuthStore } from '@/lib/store';

/**
 * Generates a URL-safe workspace slug from a company name.
 * e.g. "Acme Corp Ltd" → "acme-corp-ltd-k3x9"
 * The 4-char suffix prevents collisions between similarly-named companies.
 */
function generateSlug(companyName: string): string {
  const base = companyName
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')   // non-alphanumeric → dash
    .replace(/^-+|-+$/g, '')        // trim leading/trailing dashes
    .slice(0, 40);                  // keep it short
  const suffix = Math.random().toString(36).slice(2, 6);  // 4 random chars
  return `${base}-${suffix}`;
}

export default function RegisterPage() {
  const router = useRouter();
  const setUser = useAuthStore((s) => s.setUser);

  const [fullName, setFullName]       = useState('');
  const [companyName, setCompanyName] = useState('');
  const [email, setEmail]             = useState('');
  const [password, setPassword]       = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError]             = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName || !companyName || !email || !password) {
      setError('Please fill in all fields.');
      return;
    }
    setError('');
    setIsSubmitting(true);
    try {
      // Auto-generate workspace slug — user never sees or types this
      const workspaceSlug = generateSlug(companyName);

      const tokens = await authApi.register({
        email,
        password,
        full_name: fullName,
        workspace_slug: workspaceSlug,
        company_name: companyName,
      } as any);
      setTokens(tokens.access_token, tokens.refresh_token);
      const user = await authApi.me();
      setUser(user);
      // Redirect straight to setup wizard so they can train their bot
      router.push('/admin/setup');
    } catch (err: any) {
      setError(err.detail ?? 'Registration failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputClass = 'block w-full pl-10 pr-3 py-2.5 border border-slate-300 rounded-xl text-sm outline-none focus:border-slate-500 focus:ring-1 focus:ring-slate-500 transition-all';

  return (
    <div>
      <h3 className="text-xl font-bold text-slate-800 mb-6 text-center">Create your account</h3>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600 text-center">
          {error}
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {/* Full Name */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Full name</label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <User size={18} className="text-slate-400" />
            </div>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className={inputClass}
              placeholder="Jane Smith"
            />
          </div>
        </div>

        {/* Company Name — generates workspace slug automatically */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Company name</label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Building2 size={18} className="text-slate-400" />
            </div>
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              className={inputClass}
              placeholder="Acme Corp"
            />
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Your private workspace will be created automatically.
          </p>
        </div>

        {/* Email */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Work email</label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Mail size={18} className="text-slate-400" />
            </div>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              placeholder="jane@acmecorp.com"
            />
          </div>
        </div>

        {/* Password */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Password</label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Lock size={18} className="text-slate-400" />
            </div>
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="block w-full pl-10 pr-10 py-2.5 border border-slate-300 rounded-xl text-sm outline-none focus:border-slate-500 focus:ring-1 focus:ring-slate-500 transition-all"
              placeholder="Min 8 chars, upper + lower + digit + symbol"
            />
            <button type="button" onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600">
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full flex justify-center items-center gap-2 py-3 px-4 rounded-xl shadow-sm text-sm font-medium text-white bg-slate-800 hover:bg-slate-900 transition-colors disabled:opacity-70 mt-2"
        >
          {isSubmitting ? 'Creating account...' : 'Create account'}
          {!isSubmitting && <ArrowRight size={18} />}
        </button>
      </form>

      <div className="mt-6 text-center text-sm">
        <span className="text-slate-500">Already have an account? </span>
        <Link href="/login" className="font-bold text-slate-800 hover:text-black transition-colors">Sign in</Link>
      </div>
    </div>
  );
}
