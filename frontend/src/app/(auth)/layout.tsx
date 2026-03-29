import Link from 'next/link';
import { Bot } from 'lucide-react';

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2">
            <div className="bg-[#C9FA62] p-1.5 rounded-lg shadow-sm">
              <Bot className="text-slate-900" size={22} strokeWidth={3} />
            </div>
            <span className="font-black text-slate-900 text-2xl tracking-tighter italic">Tisaa</span>
          </Link>
        </div>
        {/* Card */}
        <div className="bg-white rounded-3xl shadow-xl border border-slate-100 p-8">
          {children}
        </div>
      </div>
    </div>
  );
}
