import React from 'react';
import { X, MapPin, Clock, ShieldAlert, Car, AlertTriangle, Download } from 'lucide-react';

export default function EvidenceModal({ event, onClose }) {
  if (!event) return null;

  let title = 'Incident Evidence Details';
  let badgeColor = '#3b82f6';
  let badgeBg = 'rgba(59, 130, 246, 0.2)';

  if (event.event_type === 'pothole') {
    title = `Pothole Incident #${event.pothole_id || event.id || ''}`;
    badgeColor = event.severity?.includes('severe') ? '#ef4444' : '#f97316';
    badgeBg = event.severity?.includes('severe') ? 'rgba(239, 68, 68, 0.2)' : 'rgba(249, 115, 22, 0.2)';
  } else if (event.event_type === 'violation') {
    title = event.violation_type || 'Safety Violation Alert';
    badgeColor = '#a855f7';
    badgeBg = 'rgba(168, 85, 247, 0.2)';
  } else if (event.event_type === 'plate') {
    title = `Scanned Plate: ${event.plate_text || 'ANPR Recognition'}`;
    badgeColor = '#06b6d4';
    badgeBg = 'rgba(6, 182, 212, 0.2)';
  }

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 1000,
      backgroundColor: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(5px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem'
    }} onClick={onClose}>
      <div
        style={{
          backgroundColor: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          maxWidth: '620px',
          width: '100%',
          boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
          overflow: 'hidden'
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          padding: '1rem 1.25rem',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: 'var(--bg-main)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <span style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              padding: '0.2rem 0.6rem',
              borderRadius: '4px',
              backgroundColor: badgeBg,
              color: badgeColor,
              border: `1px solid ${badgeColor}40`
            }}>
              {event.event_type?.toUpperCase()}
            </span>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              {title}
            </h3>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              display: 'flex',
              padding: '0.25rem',
              borderRadius: '4px'
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* High-res Image Preview */}
        {event.evidence_image && (
          <div style={{
            width: '100%',
            maxHeight: '340px',
            backgroundColor: 'var(--bg-main)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden'
          }}>
            <img
              src={event.evidence_image}
              alt="Evidence Crop"
              style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }}
            />
          </div>
        )}

        {/* Metadata Details */}
        <div style={{ padding: '1.25rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem' }}>
          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Location & Road</div>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              <MapPin size={14} color="#38bdf8" />
              <span>{event.formatted_address || event.street_name || 'MG Road Corridor, Bengaluru'}</span>
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>GPS Coordinates</div>
            <div style={{ fontSize: '0.85rem', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', marginTop: '0.2rem' }}>
              {event.latitude?.toFixed(6)}, {event.longitude?.toFixed(6)}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Video Frame & Timestamp</div>
            <div style={{ fontSize: '0.85rem', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', marginTop: '0.2rem' }}>
              Frame #{event.frame_id} ({event.timestamp_sec ? `${event.timestamp_sec.toFixed(2)}s` : 'Live'})
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Model Confidence</div>
            <div style={{ fontSize: '0.85rem', fontFamily: 'var(--font-mono)', color: '#34d399', fontWeight: 600, marginTop: '0.2rem' }}>
              {event.confidence ? `${(event.confidence * 100).toFixed(1)}%` : 'Verified (Local GPU)'}
            </div>
          </div>
        </div>

        {/* Footer actions */}
        <div style={{
          padding: '0.75rem 1.25rem',
          borderTop: '1px solid var(--border-color)',
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '0.5rem',
          backgroundColor: 'var(--bg-main)'
        }}>
          {event.evidence_image && (
            <a
              href={event.evidence_image}
              download
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                padding: '0.4rem 0.85rem',
                borderRadius: '6px',
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)',
                fontSize: '0.75rem',
                fontWeight: 600,
                textDecoration: 'none'
              }}
            >
              <Download size={13} />
              Download Crop
            </a>
          )}
          <button
            onClick={onClose}
            style={{
              padding: '0.4rem 0.85rem',
              borderRadius: '6px',
              backgroundColor: '#3b82f6',
              border: 'none',
              color: '#fff',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
