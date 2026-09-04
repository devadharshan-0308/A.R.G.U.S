import React from 'react';
import { AlertTriangle, MapPin, Navigation } from 'lucide-react';

export default function TelemetryRow({ metric }) {
  const speed = metric?.speed_kmh ?? 32;
  const speedLimit = metric?.speed_limit_kmh ?? 40;
  const isSchoolZone = metric?.is_school_zone ?? true;
  const congestionIndex = metric?.congestion_index ?? 45;
  const lat = metric?.latitude ?? 13.0827;
  const lng = metric?.longitude ?? 80.2707;
  const routeCode = metric?.route_code ?? '21G';
  const routeName = metric?.route_name ?? 'Anna Salai → Broadway';

  // Congestion status label & color
  let congestionLabel = 'Low';
  let congestionColor = 'bg-emerald-500';
  if (congestionIndex > 70) {
    congestionLabel = 'Critical';
    congestionColor = 'bg-red-500';
  } else if (congestionIndex > 35) {
    congestionLabel = 'Medium';
    congestionColor = 'bg-amber-500';
  }

  // Speedometer arc rotation angle (-90deg to +90deg based on 0-100 km/h)
  const arcAngle = Math.min(Math.max((speed / 80) * 180 - 90, -90), 90);

  return (
    <div id="maneuver-hud-section" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 mb-4 select-none">
      {/* 1. Current Speed Gauge Card */}
      <div className="glass-panel rounded-2xl p-3.5 flex items-center justify-between">
        <div>
          <div className="text-[11px] text-slate-400 font-medium">Current Speed</div>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-3xl font-extrabold text-white font-mono">{speed}</span>
            <span className="text-xs text-slate-400 font-medium">km/h</span>
          </div>
        </div>
        {/* Speedometer Arc Visual */}
        <div className="relative w-14 h-14 flex items-center justify-center">
          <svg className="w-12 h-12 transform -rotate-90" viewBox="0 0 36 36">
            <path
              className="text-slate-800"
              strokeWidth="4"
              stroke="currentColor"
              fill="none"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
            <path
              className="text-blue-500 transition-all duration-500"
              strokeDasharray={`${(speed / 80) * 100}, 100`}
              strokeWidth="4"
              strokeLinecap="round"
              stroke="currentColor"
              fill="none"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
          </svg>
          <div 
            className="absolute w-1 h-5 bg-blue-400 rounded-full origin-bottom transition-transform duration-500"
            style={{ transform: `rotate(${arcAngle}deg)` }}
          ></div>
        </div>
      </div>

      {/* 2. Speed Limit Card */}
      <div className="glass-panel rounded-2xl p-3.5 flex items-center gap-3">
        <div className="w-12 h-12 rounded-full border-4 border-red-600 bg-white text-black font-extrabold text-lg flex items-center justify-center shadow-glow-red shrink-0">
          {speedLimit}
        </div>
        <div>
          <div className="text-[11px] text-slate-400 font-medium">Speed Limit</div>
          <div className="text-sm font-bold text-slate-200 font-mono mt-0.5">{speedLimit} km/h</div>
        </div>
      </div>

      {/* 3. School Zone Alert Card */}
      <div className={`glass-panel rounded-2xl p-3.5 flex items-center gap-3 transition-all ${
        isSchoolZone ? 'border-amber-500/50 bg-amber-500/10 shadow-glow-amber' : ''
      }`}>
        <div className="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center shrink-0">
          <AlertTriangle className="w-6 h-6 animate-pulse" />
        </div>
        <div>
          <div className="text-[11px] font-bold text-amber-400 uppercase tracking-wide">SCHOOL ZONE</div>
          <div className="text-xs text-slate-300 font-semibold">&lt; 150 m</div>
          <div className="text-[10px] text-amber-300 font-medium mt-0.5">Reduce to 25 km/h</div>
        </div>
      </div>

      {/* 4. Traffic Density Barometer */}
      <div className="glass-panel rounded-2xl p-3.5 space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-[11px] text-slate-400 font-medium">Traffic Density</div>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded text-white ${congestionColor}`}>
            {congestionLabel}
          </span>
        </div>
        <div className="text-xl font-bold text-white font-mono">{congestionIndex}%</div>
        <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden flex">
          <div className="h-full bg-emerald-500" style={{ width: '35%' }}></div>
          <div className="h-full bg-amber-500" style={{ width: '35%' }}></div>
          <div className="h-full bg-red-500" style={{ width: '30%' }}></div>
        </div>
      </div>

      {/* 5. GPS Coordinates Card */}
      <div className="glass-panel rounded-2xl p-3.5 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-blue-500/20 text-blue-400 flex items-center justify-center shrink-0">
          <MapPin className="w-5 h-5" />
        </div>
        <div>
          <div className="text-[11px] text-slate-400 font-medium">GPS Coordinates</div>
          <div className="text-xs font-bold text-slate-200 font-mono mt-0.5">{lat.toFixed(4)}° N</div>
          <div className="text-xs font-bold text-slate-200 font-mono">{lng.toFixed(4)}° E</div>
        </div>
      </div>

      {/* 6. Route Info Card */}
      <div className="glass-panel rounded-2xl p-3.5 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center shrink-0">
          <Navigation className="w-5 h-5" />
        </div>
        <div>
          <div className="text-[11px] text-slate-400 font-medium">Route</div>
          <div className="text-base font-extrabold text-white font-mono">{routeCode}</div>
          <div className="text-[10px] text-slate-400 font-medium truncate max-w-[110px]">{routeName}</div>
        </div>
      </div>
    </div>
  );
}
