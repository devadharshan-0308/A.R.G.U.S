import React, { useEffect, useRef } from 'react';
import L from 'leaflet';

export default function MapView({ events = [], onSelectEvidence, selectedEvent }) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersLayerRef = useRef(null);

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      // Default: Bengaluru coordinates
      const map = L.map(mapContainerRef.current, {
        center: [12.9716, 77.5946],
        zoom: 15,
        zoomControl: false,
        attributionControl: false
      });

      L.control.zoom({ position: 'bottomright' }).addTo(map);

      // CartoDB Dark Matter / OSM Tiles
      L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        subdomains: 'abcd',
      }).addTo(map);

      markersLayerRef.current = L.layerGroup().addTo(map);
      mapInstanceRef.current = map;
    }

    return () => {
      // Cleanup on unmount if needed
    };
  }, []);

  // Update Markers
  useEffect(() => {
    if (!mapInstanceRef.current || !markersLayerRef.current) return;

    const layer = markersLayerRef.current;
    layer.clearLayers();

    const validEvents = events.filter(e => e.latitude && e.longitude);

    validEvents.forEach((ev) => {
      let color = '#0E7C7B';
      let iconSymbol = '📍';
      let label = 'Incident';

      if (ev.event_type === 'pothole') {
        const sev = (ev.severity || '').toLowerCase();
        if (sev.includes('severe')) {
          color = '#B4363B';
          iconSymbol = '⚠️';
          label = 'Severe Pothole';
        } else if (sev.includes('mild')) {
          color = '#B8720A';
          iconSymbol = '🔶';
          label = 'Mild Pothole';
        } else {
          color = '#9C7A12';
          iconSymbol = '🟡';
          label = 'Shallow Pothole';
        }
      } else if (ev.event_type === 'violation') {
        color = '#7C3AED';
        iconSymbol = '🚨';
        label = ev.violation_type || 'Safety Alert';
      } else if (ev.event_type === 'plate') {
        color = '#0E7C7B';
        iconSymbol = '🚗';
        label = `Plate: ${ev.plate_text || 'Scanned'}`;
      }

      // Create Custom SVG Icon Pin
      const iconHtml = `
        <div class="custom-pin" style="background-color: ${color}; border: 2px solid #fff;">
          ${iconSymbol}
        </div>
      `;

      const customIcon = L.divIcon({
        className: 'custom-leaflet-marker',
        html: iconHtml,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        popupAnchor: [0, -18]
      });

      const marker = L.marker([ev.latitude, ev.longitude], { icon: customIcon });

      // Rich HTML Popup
      const evidenceHtml = ev.evidence_image 
        ? `<div style="margin-top: 8px; border-radius: 6px; overflow: hidden; border: 1px solid rgba(255,255,255,0.2);">
             <img src="${ev.evidence_image}" alt="Evidence" style="width: 100%; height: 110px; object-fit: cover; display: block;" />
           </div>`
        : '';

      const popupContent = `
        <div style="font-family: 'Inter', sans-serif; min-width: 180px; padding: 2px;">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 4px;">
            <span style="font-weight: 700; font-size: 0.85rem; color: ${color};">${label}</span>
            <span style="font-family: monospace; font-size: 0.7rem; color: #8A97A0;">${ev.timestamp_sec ? ev.timestamp_sec.toFixed(1) + 's' : ''}</span>
          </div>
          <div style="font-size: 0.75rem; color: #16212B; line-height: 1.3;">
            ${ev.formatted_address || ev.street_name || 'MG Road Corridor, Bengaluru'}
          </div>
          ${ev.is_school_zone ? `<span style="display: inline-block; margin-top: 4px; font-size: 0.65rem; background: rgba(124,58,237,0.12); color: #7C3AED; padding: 1px 5px; border-radius: 4px; border: 1px solid rgba(124,58,237,0.35);">🏫 School Zone</span>` : ''}
          ${ev.is_hospital_zone ? `<span style="display: inline-block; margin-top: 4px; font-size: 0.65rem; background: rgba(180,54,59,0.12); color: #B4363B; padding: 1px 5px; border-radius: 4px; border: 1px solid rgba(180,54,59,0.35);">🏥 Hospital Zone</span>` : ''}
          ${evidenceHtml}
        </div>
      `;

      marker.bindPopup(popupContent);
      marker.on('click', () => {
        if (onSelectEvidence && ev.evidence_image) {
          onSelectEvidence(ev);
        }
      });

      marker.addTo(layer);
    });

    // Auto pan to newest incident
    if (validEvents.length > 0) {
      const latest = validEvents[0];
      mapInstanceRef.current.panTo([latest.latitude, latest.longitude], { animate: true, duration: 0.5 });
    }
  }, [events, onSelectEvidence]);

  return (
    <div style={{
      width: '100%',
      height: '100%',
      position: 'relative',
      borderRadius: '10px',
      overflow: 'hidden',
      border: '1px solid var(--border-color)',
      backgroundColor: 'var(--bg-card)'
    }}>
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />
      
      {/* Map Overlay Badge */}
      <div style={{
        position: 'absolute',
        top: '12px',
        left: '12px',
        zIndex: 400,
        backgroundColor: 'rgba(255, 255, 255, 0.92)',
        backdropFilter: 'blur(6px)',
        border: '1px solid var(--border-color)',
        borderRadius: '6px',
        padding: '0.4rem 0.75rem',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        fontSize: '0.75rem',
        fontWeight: 600,
        color: 'var(--text-secondary)'
      }}>
        <span>📍 Live Geo-Track</span>
        <span style={{ color: '#0E7C7B' }}>{events.length} active markers</span>
      </div>
    </div>
  );
}
