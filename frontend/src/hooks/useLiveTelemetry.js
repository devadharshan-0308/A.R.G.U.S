import { useState, useEffect } from 'react';
import { createTelemetrySocket } from '../services/websocket';
import { fetchStats } from '../services/api';

export function useLiveTelemetry() {
  const [connectionStatus, setConnectionStatus] = useState('CONNECTING');
  const [latestMetric, setLatestMetric] = useState({
    speed_kmh: 32,
    speed_limit_kmh: 40,
    is_school_zone: true,
    congestion_index: 45,
    latitude: 13.0827,
    longitude: 80.2707,
    bus_id: 'TN-MTC-BUS-104',
    route_code: '21G',
    route_name: 'Anna Salai → Broadway',
    latency_ms: 28,
    vehicle_counts: {
      car: 6,
      bus: 2,
      truck: 1,
      motorcycle: 8,
      person: 2
    }
  });

  const [incidents, setIncidents] = useState([
    {
      id: 'p1-demo-1',
      event_type: 'pothole',
      severity_tag: 'P1',
      severity_label: 'Severe Pothole',
      location_name: 'Anna Salai',
      time_str: '09:42 AM',
      dimension_str: '0.09 m² | 55 mm',
      thumbnail: '/data/input/pothole.mp4',
      irc_code: 'IRC:82',
      latitude: 13.082716,
      longitude: 80.270708
    },
    {
      id: 'p2-demo-2',
      event_type: 'violation',
      severity_tag: 'P2',
      severity_label: 'Damaged Divider',
      location_name: 'Nungambakkam High Rd',
      time_str: '09:40 AM',
      dimension_str: 'IRC: 82',
      thumbnail: '',
      irc_code: 'IRC: 119',
      latitude: 13.0612,
      longitude: 80.2415
    },
    {
      id: 'p3-demo-3',
      event_type: 'violation',
      severity_tag: 'P3',
      severity_label: 'Faded Zebra Crossing',
      location_name: 'T. Nagar',
      time_str: '09:38 AM',
      dimension_str: 'IRC: 35',
      thumbnail: '',
      irc_code: 'IRC: 35',
      latitude: 13.0418,
      longitude: 80.2341
    },
    {
      id: 'p1-demo-4',
      event_type: 'plate',
      severity_tag: 'P1',
      severity_label: 'Rash Driving',
      location_name: 'GST Road',
      time_str: '09:35 AM',
      dimension_str: 'TN-09-AB-1234',
      thumbnail: '',
      irc_code: 'MoRTH',
      latitude: 12.9815,
      longitude: 80.1982
    },
    {
      id: 'p1-demo-5',
      event_type: 'violation',
      severity_tag: 'P1',
      severity_label: 'Pedestrian in School Zone',
      location_name: 'Guindy',
      time_str: '09:33 AM',
      dimension_str: 'High Risk',
      thumbnail: '',
      irc_code: 'SAFETY',
      latitude: 13.0067,
      longitude: 80.2020
    }
  ]);

  const [stats, setStats] = useState(null);

  useEffect(() => {
    // Initial hydration from backend REST
    fetchStats().then(data => {
      if (data) setStats(data);
    });

    const cleanup = createTelemetrySocket(
      (message) => {
        if (message.event_type === 'metric') {
          setLatestMetric((prev) => ({
            ...prev,
            ...message,
            speed_kmh: message.speed_kmh !== undefined ? Math.round(message.speed_kmh) : prev.speed_kmh,
            congestion_index: message.congestion_index !== undefined ? Math.round(message.congestion_index) : prev.congestion_index,
          }));
        } else {
          // New incident event arriving via WS
          const newIncident = {
            id: message.id || `ws-${Date.now()}`,
            event_type: message.event_type,
            severity_tag: message.severity && message.severity.includes('severe') ? 'P1' : (message.severity === 'HIGH' ? 'P2' : 'P3'),
            severity_label: message.severity || message.violation_type || 'Road Distress',
            location_name: message.street_name || 'Anna Salai',
            time_str: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            dimension_str: message.area_ratio ? `${(message.area_ratio * 1.2).toFixed(2)} m² | 55 mm` : (message.plate_text || 'IRC: 82'),
            thumbnail: message.evidence_image || '',
            latitude: message.latitude || 13.0827,
            longitude: message.longitude || 80.2707
          };

          setIncidents((prev) => [newIncident, ...prev.slice(0, 24)]);
        }
      },
      (status) => {
        setConnectionStatus(status);
      }
    );

    return () => cleanup();
  }, []);

  return {
    connectionStatus,
    latestMetric,
    incidents,
    stats
  };
}
