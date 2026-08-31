import React, { useState } from 'react';
import { Activity, Car, Users, Truck, Bus, Layers } from 'lucide-react';

export default function TrafficCharts({ metrics = [], trafficTotals = null }) {
  const [viewMode, setViewMode] = useState('cumulative'); // 'cumulative' | 'live'

  // Extract last 25 metrics for live line graph
  const recentMetrics = metrics.slice(-25);

  const maxVal = Math.max(
    ...recentMetrics.map(m => (m.total_vehicles || 0) + (m.pedestrians || 0)),
    10
  );

  // Latest frame metrics
  const latest = recentMetrics.length > 0 ? recentMetrics[recentMetrics.length - 1] : {
    total_vehicles: 0,
    pedestrians: 0,
    cars: 0,
    motorcycles: 0,
    buses: 0,
    trucks: 0
  };

  // Cumulative totals from all ingested frames in SQLite
  const cumulative = trafficTotals || {
    total_vehicles: metrics.reduce((acc, m) => acc + (m.total_vehicles || 0), 0),
    total_pedestrians: metrics.reduce((acc, m) => acc + (m.pedestrians || 0), 0),
    total_cars: metrics.reduce((acc, m) => acc + (m.cars || 0), 0),
    total_motorcycles: metrics.reduce((acc, m) => acc + (m.motorcycles || 0), 0),
    total_buses: metrics.reduce((acc, m) => acc + (m.buses || 0), 0),
    total_trucks: metrics.reduce((acc, m) => acc + (m.trucks || 0), 0),
  };

  const activeData = viewMode === 'cumulative'
    ? {
        cars: cumulative.total_cars || 0,
        motorcycles: cumulative.total_motorcycles || 0,
        buses: cumulative.total_buses || 0,
        trucks: cumulative.total_trucks || 0,
        pedestrians: cumulative.total_pedestrians || 0,
        total: (cumulative.total_cars || 0) + (cumulative.total_motorcycles || 0) + (cumulative.total_buses || 0) + (cumulative.total_trucks || 0) + (cumulative.total_pedestrians || 0)
      }
    : {
        cars: latest.cars || 0,
        motorcycles: latest.motorcycles || 0,
        buses: latest.buses || 0,
        trucks: latest.trucks || 0,
        pedestrians: latest.pedestrians || 0,
        total: (latest.total_vehicles || 0) + (latest.pedestrians || 0)
      };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', height: '100%', overflowY: 'auto' }}>
      {/* Real-time Density Timeline (SVG Sparkline) */}
      <div style={{
        backgroundColor: 'var(--bg-card)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '1rem',
        boxShadow: '0 2px 6px rgba(0,0,0,0.15)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            <Activity size={16} color="#38bdf8" />
            <span>Traffic Flow & Pedestrian Density (Live)</span>
          </div>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            {recentMetrics.length} frames plotted
          </span>
        </div>

        {recentMetrics.length < 2 ? (
          <div style={{ height: '120px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
            Awaiting traffic telemetry frames...
          </div>
        ) : (
          <div style={{ width: '100%', height: '120px', position: 'relative' }}>
            <svg viewBox="0 0 300 100" style={{ width: '100%', height: '100%', overflow: 'visible' }}>
              <defs>
                <linearGradient id="vehiclesGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.0" />
                </linearGradient>
                <linearGradient id="pedestriansGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* Grid Lines */}
              <line x1="0" y1="25" x2="300" y2="25" stroke="rgba(51, 65, 85, 0.3)" strokeDasharray="3 3" />
              <line x1="0" y1="50" x2="300" y2="50" stroke="rgba(51, 65, 85, 0.3)" strokeDasharray="3 3" />
              <line x1="0" y1="75" x2="300" y2="75" stroke="rgba(51, 65, 85, 0.3)" strokeDasharray="3 3" />

              {/* Vehicle Points Polyline */}
              {(() => {
                const step = 300 / (recentMetrics.length - 1);
                const points = recentMetrics.map((m, i) => {
                  const x = i * step;
                  const y = 90 - ((m.total_vehicles || 0) / maxVal) * 80;
                  return `${x},${y}`;
                }).join(' ');

                const areaPoints = `0,95 ${points} 300,95`;

                return (
                  <>
                    <polygon points={areaPoints} fill="url(#vehiclesGrad)" />
                    <polyline fill="none" stroke="#38bdf8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" points={points} />
                  </>
                );
              })()}

              {/* Pedestrian Points Polyline */}
              {(() => {
                const step = 300 / (recentMetrics.length - 1);
                const points = recentMetrics.map((m, i) => {
                  const x = i * step;
                  const y = 90 - ((m.pedestrians || 0) / maxVal) * 80;
                  return `${x},${y}`;
                }).join(' ');

                return (
                  <polyline fill="none" stroke="#f43f5e" strokeWidth="2" strokeDasharray="4 2" strokeLinecap="round" points={points} />
                );
              })()}
            </svg>

            {/* Legend */}
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end', marginTop: '0.35rem', fontSize: '0.65rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#38bdf8' }}>
                <span style={{ width: '8px', height: '8px', backgroundColor: '#38bdf8', borderRadius: '2px' }} />
                <span>Vehicles</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#f43f5e' }}>
                <span style={{ width: '8px', height: '8px', backgroundColor: '#f43f5e', borderRadius: '2px' }} />
                <span>Pedestrians</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Vehicle Type Breakdown Distribution with Mode Switcher */}
      <div style={{
        backgroundColor: 'var(--bg-card)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '1rem',
        boxShadow: '0 2px 6px rgba(0,0,0,0.15)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            Vehicle & Pedestrian Distribution
          </div>

          {/* Mode Switch Buttons */}
          <div style={{ display: 'flex', backgroundColor: 'var(--bg-main)', borderRadius: '6px', padding: '2px', border: '1px solid var(--border-color)' }}>
            <button
              onClick={() => setViewMode('cumulative')}
              style={{
                padding: '0.2rem 0.5rem',
                fontSize: '0.65rem',
                fontWeight: 700,
                borderRadius: '4px',
                border: 'none',
                cursor: 'pointer',
                backgroundColor: viewMode === 'cumulative' ? '#3b82f6' : 'transparent',
                color: viewMode === 'cumulative' ? '#fff' : 'var(--text-muted)'
              }}
            >
              All-Time Totals
            </button>
            <button
              onClick={() => setViewMode('live')}
              style={{
                padding: '0.2rem 0.5rem',
                fontSize: '0.65rem',
                fontWeight: 700,
                borderRadius: '4px',
                border: 'none',
                cursor: 'pointer',
                backgroundColor: viewMode === 'live' ? '#3b82f6' : 'transparent',
                color: viewMode === 'live' ? '#fff' : 'var(--text-muted)'
              }}
            >
              Live Frame
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
          {[
            { label: 'Cars', count: activeData.cars, icon: Car, color: '#38bdf8' },
            { label: 'Motorcycles / Bikes', count: activeData.motorcycles, icon: Activity, color: '#a855f7' },
            { label: 'Buses', count: activeData.buses, icon: Bus, color: '#10b981' },
            { label: 'Trucks', count: activeData.trucks, icon: Truck, color: '#f97316' },
            { label: 'Pedestrians', count: activeData.pedestrians, icon: Users, color: '#f43f5e' }
          ].map(item => {
            const pct = activeData.total > 0 ? ((item.count / activeData.total) * 100).toFixed(1) : 0;
            const Icon = item.icon;
            return (
              <div key={item.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '0.2rem' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--text-secondary)' }}>
                    <Icon size={14} color={item.color} />
                    <span>{item.label}</span>
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {item.count.toLocaleString()} <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}>({pct}%)</span>
                  </span>
                </div>
                <div style={{ width: '100%', height: '7px', backgroundColor: 'var(--bg-main)', borderRadius: '4px', overflow: 'hidden' }}>
                  <div style={{
                    width: `${pct}%`,
                    height: '100%',
                    backgroundColor: item.color,
                    borderRadius: '4px',
                    transition: 'width 0.3s ease'
                  }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
