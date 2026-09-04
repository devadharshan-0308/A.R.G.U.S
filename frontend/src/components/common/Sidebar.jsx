import React from 'react';
import { 
  Activity, Gauge, Map, AlertCircle, BarChart2, Shield, 
  FileSpreadsheet, Download, CheckCircle2
} from 'lucide-react';

export default function Sidebar({ activeSideItem, setActiveSideItem, activeTab, setActiveTab, onOpenPwdModal, connectionStatus }) {
  
  const scrollToSection = (sectionId) => {
    if (activeTab !== 'cockpit') {
      setActiveTab('cockpit');
      setTimeout(() => {
        const el = document.getElementById(sectionId);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } else {
      const el = document.getElementById(sectionId);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const handleSidebarClick = (itemId) => {
    setActiveSideItem(itemId);
    switch (itemId) {
      case 'monitor':
        scrollToSection('live-video-section');
        break;
      case 'hud':
        scrollToSection('maneuver-hud-section');
        break;
      case 'map':
        scrollToSection('live-map-section');
        break;
      case 'incidents':
        scrollToSection('live-incidents-section');
        break;
      case 'analytics':
        scrollToSection('vehicle-analytics-section');
        break;
      case 'road':
        setActiveTab('gis');
        break;
      case 'pwd':
        onOpenPwdModal();
        break;
      case 'export':
        onOpenPwdModal();
        break;
      default:
        break;
    }
  };

  const sideItems = [
    { id: 'monitor', label: 'Live Monitor', icon: Activity },
    { id: 'hud', label: 'Maneuver HUD', icon: Gauge },
    { id: 'map', label: 'Live Map', icon: Map },
    { id: 'incidents', label: 'Incidents', icon: AlertCircle },
    { id: 'analytics', label: 'Vehicle Analytics', icon: BarChart2 },
    { id: 'road', label: 'Road Intelligence', icon: Shield },
    { id: 'pwd', label: 'PWD Work Orders', icon: FileSpreadsheet },
    { id: 'export', label: 'Reports & Export', icon: Download },
  ];

  const systemChecks = [
    { label: 'Camera', ok: true },
    { label: 'GPS', ok: true },
    { label: 'AI Inference', ok: true },
    { label: 'Backend Connection', ok: true },
    { label: 'WebSocket Stream', ok: connectionStatus === 'CONNECTED' },
  ];

  return (
    <aside className="w-64 bg-[#0d1322] border-r border-slate-800/80 flex flex-col justify-between p-4 h-[calc(100vh-4rem)] sticky top-16 select-none shrink-0 overflow-y-auto">
      {/* Top Sidebar Menu */}
      <div className="space-y-1">
        {sideItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeSideItem === item.id;
          return (
            <button
              key={item.id}
              onClick={() => handleSidebarClick(item.id)}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all ${
                isActive
                  ? 'bg-blue-600/90 text-white shadow-glow-blue font-semibold border border-blue-500/50'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      {/* Bottom System Status Panel & Skyline Branding */}
      <div id="system-status-section" className="space-y-4 pt-4 border-t border-slate-800/80">
        {/* System Status Header */}
        <div className="bg-[#131b2e] border border-slate-700/60 rounded-xl p-3.5 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300">System Status</span>
            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>All Systems Online</span>
            </div>
          </div>

          <div className="space-y-1.5 pt-1">
            {systemChecks.map((check, idx) => (
              <div key={idx} className="flex items-center gap-2 text-[11px] text-slate-300">
                <CheckCircle2 className={`w-3.5 h-3.5 ${check.ok ? 'text-emerald-400' : 'text-amber-400'}`} />
                <span>{check.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* City Skyline Branding Outline Graphic */}
        <div className="relative pt-2 text-center">
          <svg className="w-full h-12 text-slate-800 opacity-60" viewBox="0 0 200 60" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M0 50 L10 50 L10 30 L20 30 L20 50 L35 50 L35 20 L45 20 L45 50 L60 50 L60 15 L70 10 L80 15 L80 50 L100 50 L100 35 L115 35 L115 50 L130 50 L130 25 L145 25 L145 50 L160 50 L160 30 L170 30 L170 50 L200 50" />
          </svg>
          <div className="text-[10px] text-slate-400 font-medium leading-tight mt-1">
            Smart Roads · Safer Cities<br />Stronger Communities
          </div>
        </div>
      </div>
    </aside>
  );
}
