import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Navbar from './components/Navbar';
import KpiRow from './components/KpiRow';
import MapView from './components/MapView';
import IncidentFeed from './components/IncidentFeed';
import TrafficCharts from './components/TrafficCharts';
import EvidenceModal from './components/EvidenceModal';
import { fetchStats, fetchPotholes, fetchViolations, fetchPlates, fetchMetrics } from './services/api';
import { SmartCityWebSocket } from './services/websocket';
import { AlertCircle, Radio, BarChart3, ListFilter } from 'lucide-react';

export default function App() {
  const [connectionStatus, setConnectionStatus] = useState('DISCONNECTED');
  const [stats, setStats] = useState(null);
  const [events, setEvents] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [activeFilter, setActiveFilter] = useState('all');
  const [activeTab, setActiveTab] = useState('feed'); // 'feed' | 'analytics'
  const [selectedEvidence, setSelectedEvidence] = useState(null);
  const [wsClient, setWsClient] = useState(null);

  // Initial Data Hydration from REST
  const loadInitialData = useCallback(async () => {
    try {
      const [statsData, potholesData, violationsData, platesData, metricsData] = await Promise.allSettled([
        fetchStats(),
        fetchPotholes(null, 50),
        fetchViolations(null, 50),
        fetchPlates('', 50),
        fetchMetrics(100)
      ]);

      if (statsData.status === 'fulfilled') setStats(statsData.value);
      if (metricsData.status === 'fulfilled') setMetrics(metricsData.value || []);

      const allInitial = [];
      if (potholesData.status === 'fulfilled') {
        potholesData.value.forEach(p => allInitial.push({ ...p, event_type: 'pothole' }));
      }
      if (violationsData.status === 'fulfilled') {
        violationsData.value.forEach(v => allInitial.push({ ...v, event_type: 'violation' }));
      }
      if (platesData.status === 'fulfilled') {
        platesData.value.forEach(pl => allInitial.push({ ...pl, event_type: 'plate' }));
      }

      // Sort by newest timestamp / ID descending
      allInitial.sort((a, b) => (b.id || 0) - (a.id || 0));
      setEvents(allInitial);
    } catch (err) {
      console.warn('Initial data load error:', err);
    }
  }, []);

  // Initialize Reconnecting WebSocket
  useEffect(() => {
    loadInitialData();

    const client = new SmartCityWebSocket(
      null, // uses window.location host
      (incomingEvent) => {
        // Handle incoming live broadcast
        if (incomingEvent.event_type === 'metric') {
          setMetrics(prev => [...prev.slice(-49), incomingEvent]);
        } else {
          setEvents(prev => [incomingEvent, ...prev.slice(0, 199)]);
          
          // Increment relevant KPI stats dynamically
          setStats(prev => {
            const cur = prev || { total_potholes: 0, severe_potholes: 0, total_violations: 0, unique_plates_scanned: 0, school_zone_critical_alerts: 0 };
            if (incomingEvent.event_type === 'pothole') {
              const isSev = (incomingEvent.severity || '').toLowerCase().includes('severe');
              return {
                ...cur,
                total_potholes: cur.total_potholes + 1,
                severe_potholes: isSev ? cur.severe_potholes + 1 : cur.severe_potholes
              };
            } else if (incomingEvent.event_type === 'violation') {
              return {
                ...cur,
                total_violations: cur.total_violations + 1,
                school_zone_critical_alerts: incomingEvent.is_school_zone ? cur.school_zone_critical_alerts + 1 : cur.school_zone_critical_alerts
              };
            } else if (incomingEvent.event_type === 'plate') {
              return {
                ...cur,
                unique_plates_scanned: cur.unique_plates_scanned + 1
              };
            }
            return cur;
          });
        }
      },
      (status) => {
        setConnectionStatus(status);
      }
    );

    client.connect();
    setWsClient(client);

    return () => {
      client.disconnect();
    };
  }, [loadInitialData]);

  const handleReconnect = () => {
    if (wsClient) {
      wsClient.connect();
      loadInitialData();
    }
  };

  // Filtered event list
  const filteredEvents = useMemo(() => {
    if (activeFilter === 'potholes') return events.filter(e => e.event_type === 'pothole');
    if (activeFilter === 'violations') return events.filter(e => e.event_type === 'violation');
    if (activeFilter === 'plates') return events.filter(e => e.event_type === 'plate');
    return events;
  }, [events, activeFilter]);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: 'var(--bg-main)' }}>
      {/* Topbar */}
      <Navbar
        connectionStatus={connectionStatus}
        onReconnect={handleReconnect}
        stats={stats}
        activeFilter={activeFilter}
        setActiveFilter={setActiveFilter}
      />

      {/* Offline Alert Banner */}
      {connectionStatus === 'DISCONNECTED' && (
        <div style={{
          backgroundColor: 'rgba(239, 68, 68, 0.12)',
          borderBottom: '1px solid rgba(239, 68, 68, 0.3)',
          padding: '0.5rem 1.5rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.6rem',
          fontSize: '0.8rem',
          color: '#fca5a5'
        }}>
          <AlertCircle size={15} color="#ef4444" />
          <span>
            Backend server not detected at <code style={{ fontFamily: 'var(--font-mono)' }}>http://localhost:8000</code>. Start it with <strong style={{ color: '#fff' }}>python server.py</strong> to enable real-time ingestion.
          </span>
        </div>
      )}

      {/* KPI Stats Row */}
      <KpiRow stats={stats} />

      {/* Main Split Content Area */}
      <main style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr)',
        gap: '1rem',
        padding: '0.75rem 1.5rem 1.5rem 1.5rem',
        minHeight: '620px'
      }}>
        {/* Left: GIS Map View */}
        <section style={{ height: '100%', minHeight: '520px' }}>
          <MapView
            events={filteredEvents}
            onSelectEvidence={setSelectedEvidence}
            selectedEvent={selectedEvidence}
          />
        </section>

        {/* Right: Tabbed Incident Feed & Telemetry Charts */}
        <section style={{
          backgroundColor: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '10px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
        }}>
          {/* Tab Header */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid var(--border-color)',
            backgroundColor: 'var(--bg-main)',
            padding: '0.5rem 1rem'
          }}>
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              <button
                onClick={() => setActiveTab('feed')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  padding: '0.4rem 0.8rem',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  borderRadius: '6px',
                  border: 'none',
                  cursor: 'pointer',
                  backgroundColor: activeTab === 'feed' ? 'var(--bg-card)' : 'transparent',
                  color: activeTab === 'feed' ? '#38bdf8' : 'var(--text-muted)',
                  borderBottom: activeTab === 'feed' ? '2px solid #38bdf8' : '2px solid transparent'
                }}
              >
                <Radio size={13} className={connectionStatus === 'CONNECTED' ? 'animate-pulse-glow' : ''} />
                <span>Live Evidence Feed</span>
                <span style={{
                  fontSize: '0.65rem',
                  padding: '0.1rem 0.35rem',
                  backgroundColor: 'var(--bg-main)',
                  borderRadius: '10px',
                  color: 'var(--text-secondary)'
                }}>
                  {filteredEvents.length}
                </span>
              </button>

              <button
                onClick={() => setActiveTab('analytics')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  padding: '0.4rem 0.8rem',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  borderRadius: '6px',
                  border: 'none',
                  cursor: 'pointer',
                  backgroundColor: activeTab === 'analytics' ? 'var(--bg-card)' : 'transparent',
                  color: activeTab === 'analytics' ? '#38bdf8' : 'var(--text-muted)',
                  borderBottom: activeTab === 'analytics' ? '2px solid #38bdf8' : '2px solid transparent'
                }}
              >
                <BarChart3 size={13} />
                <span>Traffic Analytics</span>
              </button>
            </div>

            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
              Auto-updating
            </span>
          </div>

          {/* Tab Content */}
          <div style={{ flex: 1, padding: '1rem', overflow: 'hidden' }}>
            {activeTab === 'feed' ? (
              <IncidentFeed
                events={filteredEvents}
                onSelectEvidence={setSelectedEvidence}
              />
            ) : (
              <TrafficCharts metrics={metrics} trafficTotals={stats?.traffic_totals} />
            )}
          </div>
        </section>
      </main>

      {/* Zoomed-in Evidence Inspection Modal */}
      {selectedEvidence && (
        <EvidenceModal
          event={selectedEvidence}
          onClose={() => setSelectedEvidence(null)}
        />
      )}
    </div>
  );
}
