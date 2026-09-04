import React, { useState } from 'react';
import Navbar from './components/common/Navbar';
import Sidebar from './components/common/Sidebar';
import SystemAnnouncement from './components/common/SystemAnnouncement';

import OnboardCockpitPage from './pages/OnboardCockpitPage';
import CentralGisPage from './pages/CentralGisPage';
import PwdMaintenancePage from './pages/PwdMaintenancePage';
import TrafficAnalyticsPage from './pages/TrafficAnalyticsPage';
import SecurityHubPage from './pages/SecurityHubPage';

import EvidenceModal from './components/common/EvidenceModal';
import PwdModal from './components/common/PwdModal';

import { useLiveTelemetry } from './hooks/useLiveTelemetry';

export default function App() {
  const [activeTab, setActiveTab] = useState('cockpit');
  const [activeSideItem, setActiveSideItem] = useState('monitor');
  const [selectedEvidence, setSelectedEvidence] = useState(null);
  const [isPwdModalOpen, setIsPwdModalOpen] = useState(false);

  const { connectionStatus, latestMetric, incidents } = useLiveTelemetry();

  const handleOpenEvidence = (incidentItem) => {
    setSelectedEvidence(incidentItem || incidents[0]);
  };

  const handleCloseEvidence = () => {
    setSelectedEvidence(null);
  };

  const handleOpenPwdModal = () => {
    setIsPwdModalOpen(true);
  };

  const handleClosePwdModal = () => {
    setIsPwdModalOpen(false);
  };

  return (
    <div className="min-h-screen bg-[#0a0e1a] text-slate-100 flex flex-col justify-between selection:bg-blue-600 selection:text-white">
      {/* Top Command Navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenPwdModal={handleOpenPwdModal}
      />

      {/* Main Body Content (Sidebar + Active Viewport) */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Navigation Sidebar */}
        <Sidebar
          activeSideItem={activeSideItem}
          setActiveSideItem={setActiveSideItem}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          onOpenPwdModal={handleOpenPwdModal}
          connectionStatus={connectionStatus}
        />

        {/* Center Main Viewport */}
        <main className="flex-1 overflow-y-auto bg-[#0a0e1a]">
          {activeTab === 'cockpit' && (
            <OnboardCockpitPage
              metric={latestMetric}
              incidents={incidents}
              onOpenEvidence={handleOpenEvidence}
              onSelectBus={(busId) => console.log('Selected bus:', busId)}
            />
          )}

          {activeTab === 'gis' && (
            <CentralGisPage
              metric={latestMetric}
              incidents={incidents}
              onOpenEvidence={handleOpenEvidence}
              onSelectBus={(busId) => setActiveTab('cockpit')}
            />
          )}

          {activeTab === 'pwd' && (
            <PwdMaintenancePage onClose={() => setActiveTab('cockpit')} />
          )}

          {activeTab === 'traffic' && (
            <TrafficAnalyticsPage metric={latestMetric} />
          )}

          {(activeTab === 'security' || activeTab === 'analytics' || activeTab === 'reports' || activeTab === 'settings') && (
            <SecurityHubPage onOpenEvidence={handleOpenEvidence} />
          )}
        </main>
      </div>

      {/* Bottom Announcement Ticker */}
      <SystemAnnouncement />

      {/* Modals */}
      {selectedEvidence && (
        <EvidenceModal incident={selectedEvidence} onClose={handleCloseEvidence} />
      )}

      {isPwdModalOpen && (
        <PwdModal onClose={handleClosePwdModal} />
      )}
    </div>
  );
}
