import React from 'react';
import MapboxMap from '../components/cockpit/MapboxMap';
import FleetStatus from '../components/cockpit/FleetStatus';
import { Globe, Bus, AlertCircle, ShieldCheck, Activity } from 'lucide-react';

export default function CentralGisPage({ metric, incidents, onOpenEvidence, onSelectBus }) {
  return (
    <div className="p-4 space-y-4 max-w-[1920px] mx-auto animate-fadeIn select-none">
      {/* Top Header & Overview Chips */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-[#0d1322] border border-slate-800 rounded-2xl p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400">
            <Globe className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-base font-bold text-white">Central GIS Command Dashboard</h1>
            <p className="text-xs text-slate-400">Greater Chennai Metropolitan Transit & Infrastructure GIS Overview</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="bg-[#131b2e] border border-slate-700/60 rounded-xl px-3.5 py-2 flex items-center gap-2">
            <Bus className="w-4 h-4 text-blue-400" />
            <span className="text-xs text-slate-400">Active Fleet:</span>
            <span className="text-sm font-bold text-white font-mono">12 Buses Online</span>
          </div>

          <div className="bg-[#131b2e] border border-slate-700/60 rounded-xl px-3.5 py-2 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-400" />
            <span className="text-xs text-slate-400">Active Road Defects:</span>
            <span className="text-sm font-bold text-red-400 font-mono">85 Orders (54 P1)</span>
          </div>

          <div className="bg-[#131b2e] border border-slate-700/60 rounded-xl px-3.5 py-2 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span className="text-xs text-slate-400">City Infra Score:</span>
            <span className="text-sm font-bold text-emerald-400 font-mono">78 / 100</span>
          </div>
        </div>
      </div>

      {/* Main Full-Width GIS Cartographic Map with Fleet Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-3">
          <MapboxMap metric={metric} potholes={incidents} />
        </div>
        <div className="lg:col-span-1">
          <FleetStatus onSelectBus={onSelectBus} />
        </div>
      </div>
    </div>
  );
}
