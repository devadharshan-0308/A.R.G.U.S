import React, { useState, useEffect } from 'react';
import { 
  Bus, Globe, LayoutDashboard, FileSpreadsheet, AlertTriangle, 
  ShieldAlert, BarChart3, FileText, Settings, User
} from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab, onOpenPwdModal }) {
  const [timeStr, setTimeStr] = useState('');
  const [dateStr, setDateStr] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(now.toLocaleTimeString('en-US', { hour12: true, hour: '2-digit', minute: '2-digit', second: '2-digit' }));
      setDateStr(now.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { id: 'gis', label: 'Central GIS', icon: Globe },
    { id: 'cockpit', label: 'Onboard Cockpit', icon: LayoutDashboard },
    { id: 'pwd', label: 'PWD Work Orders', icon: FileSpreadsheet, action: onOpenPwdModal },
    { id: 'traffic', label: 'Traffic & Route Delays', icon: AlertTriangle },
    { id: 'security', label: 'Security & Hit-and-Run', icon: ShieldAlert },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'reports', label: 'Reports', icon: FileText },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <header className="h-16 bg-[#0a0e1a] border-b border-slate-800/80 px-4 flex items-center justify-between sticky top-0 z-50 select-none">
      {/* Brand & Active Vehicle Badge */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400 shadow-glow-blue">
            <Bus className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-1.5 font-bold text-base tracking-wide text-white">
              <span>Bus-Sense</span>
            </div>
            <div className="text-[10px] tracking-wider text-slate-400 font-medium uppercase -mt-0.5">
              AI Urban Intelligence Platform
            </div>
          </div>
        </div>

        {/* Onboard Cockpit Badge */}
        <div className="hidden xl:flex items-center gap-2 bg-[#131b2e] border border-slate-700/60 rounded-full px-3 py-1">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span className="text-xs font-semibold text-slate-200">Onboard Cockpit</span>
          <span className="text-[11px] font-mono text-slate-400 border-l border-slate-700 pl-2">TN-MTC-BUS-104</span>
        </div>
      </div>

      {/* Center Navigation Tabs */}
      <nav className="flex items-center gap-1 bg-[#0d1322] border border-slate-800/90 rounded-xl p-1 overflow-x-auto max-w-3xl">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => {
                if (item.action) {
                  item.action();
                } else {
                  setActiveTab(item.id);
                }
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
                isActive
                  ? 'bg-blue-600 text-white shadow-glow-blue font-semibold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-white' : 'text-slate-400'}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Right User & Time Metadata */}
      <div className="flex items-center gap-4">
        <div className="text-right hidden md:block">
          <div className="font-mono text-sm font-semibold text-slate-200 tracking-wider">
            {timeStr || '09:42:18 AM'}
          </div>
          <div className="text-[11px] text-slate-400 font-medium">
            {dateStr || '03 Sep 2026'}
          </div>
        </div>

        <div className="flex items-center gap-2.5 bg-[#131b2e] border border-slate-700/60 rounded-xl px-3 py-1.5">
          <div className="w-7 h-7 rounded-full bg-slate-700/80 flex items-center justify-center text-slate-300">
            <User className="w-4 h-4" />
          </div>
          <div className="text-left text-xs">
            <div className="font-semibold text-slate-200 leading-tight">Operator</div>
            <div className="text-[10px] text-slate-400 leading-tight font-mono">Bus 104</div>
          </div>
        </div>
      </div>
    </header>
  );
}
