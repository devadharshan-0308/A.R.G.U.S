import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { Car } from 'lucide-react';

export default function VehicleAnalytics({ metrics }) {
  // Vehicle classification breakdown matching reference image
  const data = [
    { name: 'Cars', value: 1542, percentage: '44%', color: '#3b82f6' },
    { name: '2-Wheelers', value: 1120, percentage: '32%', color: '#10b981' },
    { name: 'Buses', value: 286, percentage: '8%', color: '#f59e0b' },
    { name: 'Trucks', value: 214, percentage: '6%', color: '#8b5cf6' },
    { name: 'Autos', value: 196, percentage: '6%', color: '#ec4899' },
    { name: 'Others', value: 124, percentage: '4%', color: '#64748b' }
  ];

  const totalCount = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <div id="vehicle-analytics-section" className="glass-panel rounded-2xl p-4 select-none border border-slate-800/80 shadow-tactical flex flex-col justify-between h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Car className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-bold text-slate-100 tracking-wide">Vehicle Analytics (Today)</h3>
        </div>
      </div>

      {/* Main Content: Donut Chart + Legend */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 items-center my-auto">
        {/* Recharts Donut Chart */}
        <div className="relative w-full h-40 flex items-center justify-center">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={45}
                outerRadius={65}
                paddingAngle={3}
                dataKey="value"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} stroke="#0f172a" strokeWidth={2} />
                ))}
              </Pie>
              <Tooltip 
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#fff', fontSize: '12px' }} 
              />
            </PieChart>
          </ResponsiveContainer>

          {/* Center Donut Label */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Total</span>
            <span className="text-base font-extrabold text-white font-mono">{totalCount.toLocaleString()}</span>
          </div>
        </div>

        {/* Legend List */}
        <div className="space-y-1.5 text-xs">
          {data.map((item, idx) => (
            <div key={idx} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }}></span>
                <span className="text-slate-300 font-medium">{item.name}</span>
              </div>
              <div className="font-mono text-slate-400">
                <span className="font-semibold text-slate-200">{item.value.toLocaleString()}</span>
                <span className="text-[10px] ml-1">({item.percentage})</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
