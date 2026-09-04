import React from 'react';
import { AlertCircle, CheckCircle } from 'lucide-react';

export default function SystemAnnouncement() {
  const announcements = [
    "Heavy traffic reported on Anna Salai between Teynampet and Nungambakkam.",
    "Waterlogging detected near Guindy Railway Underpass.",
    "School zone active on Cathedral Road — Speed limit enforced to 25 km/h.",
    "MTC Route 21G schedule updated for peak evening corridors."
  ];

  return (
    <div className="h-10 bg-[#0d1322] border-t border-slate-800/80 px-4 flex items-center justify-between text-xs overflow-hidden select-none">
      {/* Left System Announcement Badge */}
      <div className="flex items-center gap-2 shrink-0 z-10 bg-[#0d1322] pr-3">
        <div className="flex items-center gap-1.5 bg-amber-500/15 border border-amber-500/40 text-amber-400 font-bold px-2.5 py-0.5 rounded-md text-[11px]">
          <AlertCircle className="w-3.5 h-3.5" />
          <span>System Announcement</span>
        </div>
      </div>

      {/* Center Ticker Text */}
      <div className="flex-1 overflow-hidden relative mx-4">
        <div className="animate-ticker text-slate-300 font-medium text-xs">
          {announcements.map((msg, i) => (
            <span key={i} className="mr-8">
              • {msg}
            </span>
          ))}
          {announcements.map((msg, i) => (
            <span key={`dup-${i}`} className="mr-8">
              • {msg}
            </span>
          ))}
        </div>
      </div>

      {/* Right All Systems Operational Badge */}
      <div className="flex items-center gap-1.5 text-emerald-400 font-semibold text-[11px] shrink-0 z-10 bg-[#0d1322] pl-3">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
        <CheckCircle className="w-3.5 h-3.5" />
        <span>All Systems Operational</span>
      </div>
    </div>
  );
}
