import React from 'react';
import { AlertTriangle, Flame, BellRing, Car, Users } from 'lucide-react';

export default function KpiRow({ stats }) {
  const peds = stats?.traffic_totals?.total_pedestrians ?? 0;

  const cards = [
    {
      title: 'Total Potholes Detected',
      value: stats?.total_potholes ?? 0,
      subtext: 'Deduplicated (2.5m radius)',
      icon: AlertTriangle,
      color: '#f97316',
      bgGradient: 'linear-gradient(135deg, rgba(249, 115, 22, 0.15), rgba(249, 115, 22, 0.02))',
      borderColor: 'rgba(249, 115, 22, 0.3)'
    },
    {
      title: 'Severe Pothole Hazards',
      value: stats?.severe_potholes ?? 0,
      subtext: 'High road safety risk',
      icon: Flame,
      color: '#ef4444',
      bgGradient: 'linear-gradient(135deg, rgba(239, 68, 68, 0.18), rgba(239, 68, 68, 0.02))',
      borderColor: 'rgba(239, 68, 68, 0.35)'
    },
    {
      title: 'Critical Zone Alerts',
      value: stats?.school_zone_critical_alerts ?? 0,
      subtext: 'School & Hospital proximity',
      icon: BellRing,
      color: '#a855f7',
      bgGradient: 'linear-gradient(135deg, rgba(168, 85, 247, 0.15), rgba(168, 85, 247, 0.02))',
      borderColor: 'rgba(168, 85, 247, 0.3)'
    },
    {
      title: 'Unique Plates Scanned',
      value: stats?.unique_plates_scanned ?? 0,
      subtext: 'ANPR Local GPU + OCR',
      icon: Car,
      color: '#06b6d4',
      bgGradient: 'linear-gradient(135deg, rgba(6, 182, 212, 0.15), rgba(6, 182, 212, 0.02))',
      borderColor: 'rgba(6, 182, 212, 0.3)'
    },
    {
      title: 'Pedestrians Monitored',
      value: peds,
      subtext: 'Roadway Safety Tracking',
      icon: Users,
      color: '#f43f5e',
      bgGradient: 'linear-gradient(135deg, rgba(244, 63, 94, 0.15), rgba(244, 63, 94, 0.02))',
      borderColor: 'rgba(244, 63, 94, 0.3)'
    }
  ];

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
      gap: '0.85rem',
      padding: '1.25rem 1.5rem 0.5rem 1.5rem'
    }}>
      {cards.map((card, idx) => {
        const Icon = card.icon;
        return (
          <div
            key={idx}
            style={{
              background: card.bgGradient,
              backgroundColor: 'var(--bg-card)',
              border: `1px solid ${card.borderColor}`,
              borderRadius: '10px',
              padding: '0.85rem 1.1rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
              transition: 'transform 0.2s, box-shadow 0.2s'
            }}
          >
            <div>
              <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                {card.title}
              </div>
              <div style={{
                fontSize: '1.65rem',
                fontWeight: 800,
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-mono)',
                lineHeight: 1.2,
                marginTop: '0.2rem'
              }}>
                {typeof card.value === 'number' ? card.value.toLocaleString() : card.value}
              </div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                {card.subtext}
              </div>
            </div>

            <div style={{
              backgroundColor: 'var(--bg-main)',
              borderRadius: '10px',
              padding: '0.65rem',
              border: `1px solid ${card.borderColor}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: card.color
            }}>
              <Icon size={22} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
