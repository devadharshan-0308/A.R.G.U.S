import React from 'react';
import VehicleAnalytics from '../components/cockpit/VehicleAnalytics';
import { BarChart3, AlertTriangle, TrendingUp, Clock } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function TrafficAnalyticsPage({ metric }) {
  // Congestion timeline history data
  const trafficTimeline = [
    { time: '08:00 AM', density: 35 },
    { time: '09:00 AM', density: 78 },
    { time: '10:00 AM', density: 85 },
    { time: '11:00 AM', density: 60 },
    { time: '12:00 PM', density: 45 },
    { time: '01:00 PM', density: 40 },
    { time: '02:00 PM', density: 50 },
    { time: '03:00 PM', density: 65 },
    { time: '04:00 PM', density: 82 },
    { time: '05:00 PM', density: 92 },
    { time: '06:00 PM', density: 88 },
  ];

  return (
    <div className="p-4 space-y-4 max-w-[1920px] mx-auto animate-fadeIn select-none">
      {/* Top Header */}
      <div className="bg-[#0d1322] border border-slate-800 rounded-2xl p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
            <BarChart3 className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-base font-bold text-white">Traffic Analytics & Corridor Delay Center</h1>
            <p className="text-xs text-slate-400">Real-Time Transit Headway, Bottleneck Identification & Vehicle Categorization</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="bg-[#131b2e] border border-slate-700/60 rounded-xl px-3.5 py-2 flex items-center gap-2 text-xs">
            <TrendingUp className="w-4 h-4 text-amber-400" />
            <span className="text-slate-400">Peak Congestion Index:</span>
            <span className="font-bold text-amber-400 font-mono">92% (05:00 PM)</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Chart + Vehicle Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Hourly Congestion Timeline Chart (Spans 2 columns) */}
        <div className="lg:col-span-2 glass-panel rounded-2xl p-4 flex flex-col justify-between border border-slate-800">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2 text-sm font-bold text-white">
              <Clock className="w-4 h-4 text-blue-400" />
              <span>Corridor Traffic Density Timeline (Today)</span>
            </div>
            <span className="text-xs text-slate-400 font-mono">Corridor: Anna Salai Arterial</span>
          </div>

          <div className="w-full h-64 my-auto">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trafficTimeline}>
                <defs>
                  <linearGradient id="colorDensity" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" stroke="#64748b" fontSize={11} />
                <YAxis stroke="#64748b" fontSize={11} domain={[0, 100]} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#fff', fontSize: '12px' }} />
                <Area type="monotone" dataKey="density" stroke="#3b82f6" strokeWidth={3} fillOpacity={1} fill="url(#colorDensity)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Vehicle Analytics (1 column) */}
        <div className="lg:col-span-1">
          <VehicleAnalytics metrics={metric} />
        </div>
      </div>
    </div>
  );
}
