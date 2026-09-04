import React from 'react';
import { Bus, ExternalLink } from 'lucide-react';

export default function FleetStatus({ onSelectBus }) {
  const fleet = [
    { id: 'TN-MTC-BUS-104', route: 'Route 21G', status: 'Online', statusColor: 'text-emerald-400 bg-emerald-500/20', speed: '32 km/h' },
    { id: 'TN-MTC-BUS-202', route: 'Route 102', status: 'Online', statusColor: 'text-emerald-400 bg-emerald-500/20', speed: '28 km/h' },
    { id: 'TN-MTC-BUS-305', route: 'Route 27B', status: 'Online', statusColor: 'text-emerald-400 bg-emerald-500/20', speed: '35 km/h' },
    { id: 'TN-MTC-BUS-418', route: 'Route 77A', status: 'Offline', statusColor: 'text-slate-400 bg-slate-700/30', speed: '--' },
    { id: 'TN-MTC-BUS-521', route: 'Route 19A', status: 'Maintenance', statusColor: 'text-amber-400 bg-amber-500/20', speed: '--' }
  ];

  return (
    <div id="fleet-status-section" className="glass-panel rounded-2xl p-4 select-none border border-slate-800/80 shadow-tactical flex flex-col justify-between h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Bus className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-bold text-slate-100 tracking-wide">Fleet Status</h3>
        </div>
        <button 
          onClick={() => onSelectBus && onSelectBus('TN-MTC-BUS-104')}
          className="text-xs font-semibold text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
        >
          <span>View All</span>
          <ExternalLink className="w-3 h-3" />
        </button>
      </div>

      {/* Fleet Buses List */}
      <div className="space-y-2 my-auto">
        {fleet.map((bus) => (
          <div
            key={bus.id}
            onClick={() => onSelectBus && onSelectBus(bus.id)}
            className="bg-[#0e1626] border border-slate-800 hover:border-slate-700 rounded-xl p-2.5 flex items-center justify-between cursor-pointer transition-all hover:scale-[1.01]"
          >
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-slate-800 flex items-center justify-center text-slate-300">
                <Bus className="w-3.5 h-3.5" />
              </div>
              <div>
                <div className="text-xs font-bold text-slate-100 font-mono">{bus.id}</div>
                <div className="text-[10px] text-slate-400 font-medium">{bus.route}</div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className={`flex items-center gap-1.5 text-[10px] font-bold px-2 py-0.5 rounded-full ${bus.statusColor}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${bus.status === 'Online' ? 'bg-emerald-400 animate-pulse' : (bus.status === 'Maintenance' ? 'bg-amber-400' : 'bg-slate-400')}`}></span>
                <span>{bus.status}</span>
              </div>
              <div className="text-xs font-mono font-semibold text-slate-300 text-right min-w-[50px]">
                {bus.speed}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
