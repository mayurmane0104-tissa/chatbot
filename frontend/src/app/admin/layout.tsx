'use client';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Bot, LayoutDashboard, Settings, MessageSquare, ChevronRight, LogOut } from 'lucide-react';
import { useAuthStore } from '@/lib/store';
import { authApi } from '@/lib/api';
import { useEffect } from 'react';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, clearUser } = useAuthStore();

  useEffect(() => {
    // If no user in store, verify token with backend
    if (!user) {
      authApi.me().then((u) => {
        useAuthStore.getState().setUser(u);
      }).catch(() => {
        router.push('/login');
      });
    }
  }, []);

  const handleLogout = async () => {
    await authApi.logout();
    clearUser();
    router.push('/login');
  };

  const menuItems = [
    { name: 'Dashboard', icon: LayoutDashboard, href: '/admin' },
    { name: 'Setup Wizard', icon: Settings, href: '/admin/setup' },
    { name: 'My Chatbots', icon: MessageSquare, href: '/admin/chatbots' },
  ];

  const initials = user?.full_name
    ? user.full_name.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase()
    : 'AD';

  return (
    <div className="flex min-h-screen bg-[#F8FAFC]">
      <aside className="w-72 bg-white border-r border-slate-200 hidden lg:flex flex-col p-8 space-y-10 sticky top-0 h-screen">
        <div className="flex items-center gap-2 px-2">
          <div className="bg-[#C9FA62] p-1.5 rounded-lg shadow-sm">
            <Bot className="text-slate-900" size={22} strokeWidth={3} />
          </div>
          <span className="font-black text-slate-900 text-2xl tracking-tighter italic">Tisaa</span>
        </div>

        <nav className="flex-1 space-y-2">
          {menuItems.map((item) => {
            const isActive = item.href === '/admin' ? pathname === '/admin' : pathname.startsWith(item.href);
            return (
              <Link key={item.name} href={item.href}
                className={`flex items-center justify-between px-5 py-4 rounded-2xl text-sm font-black transition-all group ${
                  isActive
                    ? 'bg-slate-900 text-white shadow-2xl shadow-slate-200 translate-x-1'
                    : 'text-slate-400 hover:bg-slate-50 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center gap-3">
                  <item.icon size={18} strokeWidth={isActive ? 3 : 2} /> {item.name}
                </div>
                {isActive && <ChevronRight size={14} className="text-[#C9FA62]" />}
              </Link>
            );
          })}
        </nav>

        <div className="space-y-3">
          <div className="p-4 bg-slate-50 rounded-3xl border border-slate-100 flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-100 border-2 border-white shadow-sm flex items-center justify-center font-black text-indigo-600 text-xs">
              {initials}
            </div>
            <div className="overflow-hidden flex-1">
              <p className="text-xs font-black text-slate-900 truncate">{user?.full_name ?? 'Admin User'}</p>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{user?.role ?? 'Admin'}</p>
            </div>
          </div>
          <button onClick={handleLogout}
            className="w-full flex items-center gap-2 px-5 py-3 rounded-2xl text-sm font-bold text-slate-400 hover:bg-red-50 hover:text-red-600 transition-all">
            <LogOut size={16} /> Sign Out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
