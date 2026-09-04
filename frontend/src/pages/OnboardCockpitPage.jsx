import React from 'react';
import TelemetryRow from '../components/cockpit/TelemetryRow';
import VideoViewport from '../components/cockpit/VideoViewport';
import MapboxMap from '../components/cockpit/MapboxMap';
import IncidentStream from '../components/cockpit/IncidentStream';
import VehicleAnalytics from '../components/cockpit/VehicleAnalytics';
import FleetStatus from '../components/cockpit/FleetStatus';

export default function OnboardCockpitPage({ metric, incidents, onOpenEvidence, onSelectBus }) {
  return (
    <div className="p-4 space-y-4 max-w-[1920px] mx-auto animate-fadeIn">
      {/* 1. Top Row: 6 Telemetry KPI Cards */}
      <TelemetryRow metric={metric} />

      {/* 2. Middle Row: 2 Large Split Panels (Video & Map) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <VideoViewport onOpenEvidence={onOpenEvidence} />
        <MapboxMap metric={metric} potholes={incidents} />
      </div>

      {/* 3. Bottom Row: 3 Panels Grid (Incident Stream 50% | Vehicle Analytics 25% | Fleet Status 25%) */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Incident Stream Spans 2 Columns (~50%) */}
        <div className="lg:col-span-2">
          <IncidentStream incidents={incidents} onOpenEvidence={onOpenEvidence} />
        </div>

        {/* Vehicle Analytics (25%) */}
        <div className="lg:col-span-1">
          <VehicleAnalytics metrics={metric} />
        </div>

        {/* Fleet Status (25%) */}
        <div className="lg:col-span-1">
          <FleetStatus onSelectBus={onSelectBus} />
        </div>
      </div>
    </div>
  );
}
