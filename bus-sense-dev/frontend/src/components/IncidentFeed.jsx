import React from 'react';
import { AlertTriangle, Car, ShieldAlert, Clock, MapPin, Eye } from 'lucide-react';

export default function IncidentFeed({ events = [], onSelectEvidence }) {
  if (!events || events.length === 0) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        color: 'var(--text-muted)',
        textAlign: 'center',
        padding: '2rem'
      }}>
        <AlertTriangle size={36} style={{ opacity: 0.4, marginBottom: '0.75rem' }} />
        <p style={{ fontSize: '0.85rem', fontWeight: 600 }}>No Incidents Yet</p>
        <p style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
          Run the video pipeline (<code style={{ fontFamily: 'var(--font-mono)', color: '#38bdf8' }}>python main.py</code>) to stream live events.
        </p>
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '0.75rem',
      overflowY: 'auto',
      maxHeight: '100%',
      paddingRight: '0.35rem'
    }}>
      {events.map((ev, idx) => {
        let tagBg = 'rgba(59, 130, 246, 0.15)';
        let tagColor = '#60a5fa';
        let tagText = 'Incident';
        let TagIcon = AlertTriangle;

        if (ev.event_type === 'pothole') {
          const sev = (ev.severity || '').toLowerCase();
          if (sev.includes('severe')) {
            tagBg = 'var(--color-severe-bg)';
            tagColor = 'var(--color-severe)';
            tagText = 'Severe Pothole';
          } else if (sev.includes('mild')) {
            tagBg = 'var(--color-mild-bg)';
            tagColor = 'var(--color-mild)';
            tagText = 'Mild Pothole';
          } else {
            tagBg = 'var(--color-shallow-bg)';
            tagColor = 'var(--color-shallow)';
            tagText = 'Shallow Pothole';
          }
        } else if (ev.event_type === 'violation') {
          tagBg = 'var(--color-critical-zone-bg)';
          tagColor = 'var(--color-critical-zone)';
          tagText = ev.violation_type || 'Safety Alert';
          TagIcon = ShieldAlert;
        } else if (ev.event_type === 'plate') {
          tagBg = 'var(--color-plate-bg)';
          tagColor = 'var(--color-plate)';
          tagText = ev.plate_text ? `Plate: ${ev.plate_text}` : 'License Plate';
          TagIcon = Car;
        }

        return (
          <div
            key={ev.id || idx}
            className={idx === 0 ? 'animate-flash-new' : ''}
            style={{
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              padding: '0.85rem',
              display: 'flex',
              gap: '0.85rem',
              boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
              transition: 'all 0.2s',
              cursor: ev.evidence_image ? 'pointer' : 'default'
            }}
            onClick={() => {
              if (ev.evidence_image && onSelectEvidence) {
                onSelectEvidence(ev);
              }
            }}
          >
            {/* Evidence Image Thumbnail */}
            {ev.evidence_image ? (
              <div style={{
                width: '80px',
                height: '70px',
                borderRadius: '6px',
                overflow: 'hidden',
                flexShrink: 0,
                border: '1px solid var(--border-color)',
                position: 'relative'
              }}>
                <img
                  src={ev.evidence_image}
                  alt="Evidence"
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
                <div style={{
                  position: 'absolute',
                  inset: 0,
                  backgroundColor: 'rgba(0,0,0,0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  opacity: 0,
                  transition: 'opacity 0.2s'
                }} className="hover:opacity-100">
                  <Eye size={16} color="#fff" />
                </div>
              </div>
            ) : (
              <div style={{
                width: '80px',
                height: '70px',
                borderRadius: '6px',
                backgroundColor: 'var(--bg-main)',
                border: '1px solid var(--border-color)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                color: tagColor
              }}>
                <TagIcon size={24} />
              </div>
            )}

            {/* Content Details */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                <span style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                  padding: '0.15rem 0.5rem',
                  borderRadius: '4px',
                  backgroundColor: tagBg,
                  color: tagColor,
                  fontSize: '0.7rem',
                  fontWeight: 700
                }}>
                  <TagIcon size={11} />
                  {tagText}
                </span>

                <span style={{
                  fontSize: '0.7rem',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.2rem'
                }}>
                  <Clock size={11} />
                  {ev.timestamp_sec ? `${ev.timestamp_sec.toFixed(1)}s` : 'Live'}
                </span>
              </div>

              <div style={{
                fontSize: '0.78rem',
                color: 'var(--text-primary)',
                fontWeight: 500,
                marginTop: '0.35rem',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                display: 'flex',
                alignItems: 'center',
                gap: '0.25rem'
              }}>
                <MapPin size={12} color="var(--text-muted)" style={{ flexShrink: 0 }} />
                <span>{ev.formatted_address || ev.street_name || 'MG Road Corridor, Bengaluru'}</span>
              </div>

              {/* Badges for School/Hospital Zone */}
              <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.35rem' }}>
                {ev.is_school_zone && (
                  <span style={{
                    fontSize: '0.62rem',
                    fontWeight: 600,
                    backgroundColor: 'rgba(124, 58, 237, 0.12)',
                    color: '#7C3AED',
                    padding: '0.1rem 0.35rem',
                    borderRadius: '3px',
                    border: '1px solid rgba(124, 58, 237, 0.35)'
                  }}>
                    🏫 School Zone
                  </span>
                )}
                {ev.confidence && (
                  <span style={{
                    fontSize: '0.62rem',
                    fontFamily: 'var(--font-mono)',
                    backgroundColor: 'var(--bg-main)',
                    color: 'var(--text-muted)',
                    padding: '0.1rem 0.35rem',
                    borderRadius: '3px',
                    border: '1px solid var(--border-color)'
                  }}>
                    {(ev.confidence * 100).toFixed(0)}% Conf
                  </span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
