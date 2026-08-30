import React, { useState, useEffect } from 'react';
import { ShieldAlert, Activity, Wifi, WifiOff, RefreshCw, Layers } from 'lucide-react';

export default function Navbar({ connectionStatus, onReconnect, stats, activeFilter, setActiveFilter }) {
  const [time, setTime] = useState(new Date().toLocaleTimeString());

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const isLive = connectionStatus === 'CONNECTED';

  return (
    <header style={{
      backgroundColor: 'var(--bg-card)',
      borderBottom: '1px solid var(--border-color)',
      padding: '0.85rem 1.5rem',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      backdropFilter: 'blur(8px)'
    }}>
      {/* Brand & Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
        <div style={{
          backgroundColor: '#3b82f6',
          borderRadius: '8px',
          padding: '0.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 12px rgba(59, 130, 246, 0.4)'
        }}>
          <ShieldAlert size={22} color="#fff" />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <h1 style={{ fontSize: '1.15rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
              Smart City Command Center
            </h1>
            <span style={{
              fontSize: '0.65rem',
              fontWeight: 700,
              padding: '0.15rem 0.45rem',
              borderRadius: '4px',
              backgroundColor: 'rgba(59, 130, 246, 0.2)',
              color: '#60a5fa',
              border: '1px solid rgba(59, 130, 246, 0.4)'
            }}>
              AI INGESTION
            </span>
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Real-time Edge Vision, Pothole Deduplication & Geo-Enriched Safety Engine
          </p>
        </div>
      </div>

      {/* Quick Filter Buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', backgroundColor: 'var(--bg-main)', padding: '0.25rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
        {[
          { id: 'all', label: 'All Events', icon: Layers },
          { id: 'potholes', label: 'Potholes', color: 'var(--color-severe)' },
          { id: 'violations', label: 'Safety Violations', color: 'var(--color-critical-zone)' },
          { id: 'plates', label: 'License Plates', color: 'var(--color-plate)' }
        ].map(item => (
          <button
            key={item.id}
            onClick={() => setActiveFilter(item.id)}
            style={{
              padding: '0.35rem 0.75rem',
              fontSize: '0.75rem',
              fontWeight: 600,
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              transition: 'all 0.2s',
              backgroundColor: activeFilter === item.id ? 'var(--bg-card-hover)' : 'transparent',
              color: activeFilter === item.id ? 'var(--text-primary)' : 'var(--text-muted)',
              boxShadow: activeFilter === item.id ? '0 1px 3px rgba(0,0,0,0.3)' : 'none',
              borderBottom: activeFilter === item.id ? `2px solid ${item.color || '#3b82f6'}` : '2px solid transparent'
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      {/* Status & Clock Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
        {/* Live Status Pill */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.45rem',
          padding: '0.35rem 0.8rem',
          borderRadius: '9999px',
          backgroundColor: isLive ? 'var(--color-live-bg)' : 'rgba(239, 68, 68, 0.15)',
          border: `1px solid ${isLive ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)'}`
        }}>
          <span style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: isLive ? 'var(--color-live)' : 'var(--color-severe)',
            boxShadow: `0 0 8px ${isLive ? 'var(--color-live)' : 'var(--color-severe)'}`
          }} className={isLive ? 'animate-pulse-glow' : ''} />
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: isLive ? '#34d399' : '#f87171' }}>
            {isLive ? 'LIVE STREAM' : 'OFFLINE'}
          </span>
          {!isLive && (
            <button
              onClick={onReconnect}
              title="Reconnect to Backend WebSocket"
              style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', display: 'flex', padding: 0 }}
            >
              <RefreshCw size={12} />
            </button>
          )}
        </div>

        {/* System Clock */}
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.8rem',
          color: 'var(--text-secondary)',
          backgroundColor: 'var(--bg-main)',
          padding: '0.35rem 0.65rem',
          borderRadius: '6px',
          border: '1px solid var(--border-color)'
        }}>
          {time}
        </div>
      </div>
    </header>
  );
}
