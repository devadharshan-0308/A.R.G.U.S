import React, { useState, useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { MapPin, Plus, Minus, Crosshair, Bus, AlertOctagon, AlertTriangle, Info, Flame, ShieldAlert, Building2 } from 'lucide-react';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;
mapboxgl.accessToken = MAPBOX_TOKEN;

const STYLE_MAP = {
  Streets: 'mapbox://styles/mapbox/streets-v12',
  Satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
  Dark: 'mapbox://styles/mapbox/dark-v11',
  Navigation: 'mapbox://styles/mapbox/navigation-night-v1',
};

export default function MapboxMap({ metric, potholes = [] }) {
  const [activeStyle, setActiveStyle] = useState('Streets');
  const [mapError, setMapError] = useState(false);
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);

  // Center on Chennai Coordinates [lng, lat]
  const centerLng = metric?.longitude ?? 80.2707;
  const centerLat = metric?.latitude ?? 13.0827;

  // Real traffic congestion GeoJSON points for Mapbox Heatmap Layer
  const trafficHeatmapGeoJSON = {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', geometry: { type: 'Point', coordinates: [80.2707, 13.0827] }, properties: { weight: 0.9, name: 'Anna Salai' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [80.2720, 13.0840] }, properties: { weight: 0.85, name: 'Anna Salai North' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [80.2680, 13.0810] }, properties: { weight: 0.95, name: 'Anna Salai South' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [80.2415, 13.0612] }, properties: { weight: 0.7, name: 'Egmore' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [80.2341, 13.0418] }, properties: { weight: 0.9, name: 'T. Nagar' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [80.2400, 13.0500] }, properties: { weight: 0.8, name: 'Nungambakkam' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [80.2100, 13.0850] }, properties: { weight: 0.6, name: 'Anna Nagar' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [80.2020, 13.0067] }, properties: { weight: 0.75, name: 'Guindy Underpass' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [80.2450, 12.9815] }, properties: { weight: 0.85, name: 'Velachery Junction' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [80.2800, 13.0500] }, properties: { weight: 0.65, name: 'Marina Beach Road' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [80.2500, 13.0700] }, properties: { weight: 0.5, name: 'Chetpet' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [80.2200, 13.0300] }, properties: { weight: 0.55, name: 'Saidapet' } },
    ]
  };

  // Defect & Marker Locations [lng, lat]
  const defectsData = [
    { id: 1, lng: 80.2707, lat: 13.0827, type: 'P1', title: 'Severe Pothole (0.09 m² | 55mm)' },
    { id: 2, lng: 80.2415, lat: 13.0612, type: 'P2', title: 'Damaged Divider' },
    { id: 3, lng: 80.2341, lat: 13.0418, type: 'P3', title: 'Faded Zebra Crossing' },
    { id: 4, lng: 80.2100, lat: 13.0850, type: 'P1', title: 'Severe Waterlogging' },
    { id: 5, lng: 80.2020, lat: 13.0067, type: 'P2', title: 'Tilted Signboard' },
    { id: 6, lng: 80.2800, lat: 13.0500, type: 'P1', title: 'Rash Driving Alert' },
  ];

  const busData = [
    { id: 'BUS-104', lng: centerLng, lat: centerLat, route: '21G', isLive: true },
    { id: 'BUS-202', lng: 80.2500, lat: 13.0700, route: '102', isLive: true },
    { id: 'BUS-305', lng: 80.2200, lat: 13.0300, route: '27B', isLive: true },
    { id: 'BUS-521', lng: 80.2100, lat: 12.9900, route: '19A', isLive: false },
  ];

  // Helper to attach layers & sources to Mapbox instance
  const attachMapboxLayers = (map) => {
    if (!map) return;

    // Add Heatmap Source & Layer if not already added
    if (!map.getSource('traffic-heatmap-src')) {
      map.addSource('traffic-heatmap-src', {
        type: 'geojson',
        data: trafficHeatmapGeoJSON,
      });
    }

    if (!map.getLayer('traffic-heatmap-layer')) {
      map.addLayer({
        id: 'traffic-heatmap-layer',
        type: 'heatmap',
        source: 'traffic-heatmap-src',
        maxzoom: 17,
        paint: {
          'heatmap-weight': ['get', 'weight'],
          'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 15, 3],
          'heatmap-color': [
            'interpolate',
            ['linear'],
            ['heatmap-density'],
            0, 'rgba(0, 0, 255, 0)',
            0.2, 'rgba(16, 185, 129, 0.6)',  // Green
            0.4, 'rgba(234, 179, 8, 0.75)',  // Yellow
            0.7, 'rgba(245, 158, 11, 0.85)', // Orange
            0.9, 'rgba(239, 68, 68, 0.95)'   // Red
          ],
          'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 8, 15, 45],
          'heatmap-opacity': 0.85,
        },
      });
    }

    // Attach Custom HTML Markers
    // Clear old markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    // Add Bus Markers
    busData.forEach((bus) => {
      const el = document.createElement('div');
      el.className = 'mapbox-bus-marker cursor-pointer';
      el.innerHTML = `
        <div class="relative flex items-center justify-center">
          ${bus.isLive ? '<span class="animate-ping absolute inline-flex h-7 w-7 rounded-full bg-blue-400 opacity-75"></span>' : ''}
          <div class="w-7 h-7 rounded-full ${bus.isLive ? 'bg-blue-600 shadow-glow-blue' : 'bg-slate-700'} border-2 border-white text-white flex items-center justify-center font-bold text-xs">
            🚌
          </div>
          <div class="absolute bottom-8 bg-slate-950/90 border border-blue-400 text-white font-mono text-[10px] font-bold px-1.5 py-0.5 rounded shadow-lg whitespace-nowrap">
            ${bus.id} (${bus.route})
          </div>
        </div>
      `;
      const marker = new mapboxgl.Marker(el)
        .setLngLat([bus.lng, bus.lat])
        .setPopup(new mapboxgl.Popup({ offset: 15 }).setHTML(`<strong>${bus.id}</strong><br/>Route ${bus.route}`))
        .addTo(map);
      markersRef.current.push(marker);
    });

    // Add Defect Markers (P1/P2/P3)
    defectsData.forEach((defect) => {
      const el = document.createElement('div');
      const bg = defect.type === 'P1' ? 'bg-red-600' : (defect.type === 'P2' ? 'bg-amber-500' : 'bg-blue-500');
      const icon = defect.type === 'P1' ? '🚨' : (defect.type === 'P2' ? '⚠️' : '🔵');

      el.className = 'mapbox-defect-marker cursor-pointer';
      el.innerHTML = `
        <div class="w-6 h-6 rounded-md ${bg} text-white flex items-center justify-center font-bold text-xs shadow-md">
          ${icon}
        </div>
      `;
      const marker = new mapboxgl.Marker(el)
        .setLngLat([defect.lng, defect.lat])
        .setPopup(new mapboxgl.Popup({ offset: 15 }).setHTML(`<strong>${defect.type} Defect</strong><br/>${defect.title}`))
        .addTo(map);
      markersRef.current.push(marker);
    });
  };

  // Initialize Mapbox GL JS on component mount
  useEffect(() => {
    if (!mapContainerRef.current) return;

    try {
      const map = new mapboxgl.Map({
        container: mapContainerRef.current,
        style: STYLE_MAP[activeStyle] || STYLE_MAP.Streets,
        center: [centerLng, centerLat],
        zoom: 13,
        pitch: 30,
      });

      mapRef.current = map;

      map.on('load', () => {
        attachMapboxLayers(map);
      });

      map.on('style.load', () => {
        attachMapboxLayers(map);
      });

      map.on('error', (e) => {
        console.warn('Mapbox GL JS error:', e);
        setMapError(true);
      });
    } catch (err) {
      console.warn('Mapbox initialization failed:', err);
      setMapError(true);
    }

    return () => {
      markersRef.current.forEach((m) => m.remove());
      if (mapRef.current) mapRef.current.remove();
    };
  }, []);

  // Handle Style Switching via Mapbox API
  const handleStyleChange = (styleName) => {
    setActiveStyle(styleName);
    if (mapRef.current) {
      const targetStyle = STYLE_MAP[styleName];
      if (targetStyle) {
        mapRef.current.setStyle(targetStyle);
        // Mapbox fires 'style.load' which automatically re-attaches layers in attachMapboxLayers
      }
    }
  };

  // Zoom Controls
  const handleZoomIn = () => {
    if (mapRef.current) mapRef.current.zoomIn();
  };

  const handleZoomOut = () => {
    if (mapRef.current) mapRef.current.zoomOut();
  };

  const handleRecenter = () => {
    if (mapRef.current) {
      mapRef.current.flyTo({
        center: [centerLng, centerLat],
        zoom: 14,
        essential: true,
      });
    }
  };

  return (
    <div id="live-map-section" className="glass-panel rounded-2xl p-4 flex flex-col justify-between relative overflow-hidden select-none border border-slate-800/80 shadow-tactical">
      {/* Header & Map Style Toggles */}
      <div className="flex items-center justify-between mb-3 z-20">
        <div className="flex items-center gap-2">
          <MapPin className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-bold text-slate-100 tracking-wide">Live Geospatial Map</h3>
        </div>

        {/* 4 Layer Style Switcher Buttons matching Reference Image */}
        <div className="flex items-center gap-1 bg-slate-900/90 border border-slate-700/80 rounded-lg p-0.5">
          {Object.keys(STYLE_MAP).map((styleName) => (
            <button
              key={styleName}
              onClick={() => handleStyleChange(styleName)}
              className={`px-2.5 py-1 rounded text-xs font-semibold transition-all ${activeStyle === styleName
                  ? 'bg-blue-600 text-white shadow-glow-blue'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
            >
              {styleName}
            </button>
          ))}
        </div>
      </div>

      {/* Cartographic Map Container */}
      <div
        ref={mapContainerRef}
        className="relative w-full h-[360px] bg-[#0c1220] rounded-xl overflow-hidden border border-slate-800"
      >
        {/* Floating Map Zoom & Recenter Controls (Top Right) */}
        <div className="absolute top-3 right-3 flex flex-col gap-1 z-30">
          <button
            onClick={handleZoomIn}
            className="w-7 h-7 rounded bg-slate-900/90 border border-slate-700 text-slate-200 hover:text-white flex items-center justify-center shadow-md active:scale-95 transition-transform"
            title="Zoom In"
          >
            <Plus className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomOut}
            className="w-7 h-7 rounded bg-slate-900/90 border border-slate-700 text-slate-200 hover:text-white flex items-center justify-center shadow-md active:scale-95 transition-transform"
            title="Zoom Out"
          >
            <Minus className="w-4 h-4" />
          </button>
          <button
            onClick={handleRecenter}
            className="w-7 h-7 rounded bg-slate-900/90 border border-slate-700 text-slate-200 hover:text-white flex items-center justify-center shadow-md active:scale-95 transition-transform"
            title="Recenter Map on Bus GPS"
          >
            <Crosshair className="w-4 h-4 text-blue-400" />
          </button>
        </div>

        {/* Floating Map Legend Panel (Bottom Right matching Reference Image) */}
        <div className="absolute bottom-3 right-3 bg-slate-950/90 backdrop-blur-md border border-slate-800 rounded-xl p-2.5 space-y-1.5 z-30 text-[11px] text-slate-300">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-blue-600 flex items-center justify-center text-white text-[9px]">
              <Bus className="w-2.5 h-2.5" />
            </div>
            <span>Buses (Live)</span>
          </div>

          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-red-600 flex items-center justify-center text-white text-[9px]">
              <AlertOctagon className="w-2.5 h-2.5" />
            </div>
            <span>P1 Critical Defect</span>
          </div>

          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-amber-500 flex items-center justify-center text-white text-[9px]">
              <AlertTriangle className="w-2.5 h-2.5" />
            </div>
            <span>P2 High Defect</span>
          </div>

          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-blue-500 flex items-center justify-center text-white text-[9px]">
              <Info className="w-2.5 h-2.5" />
            </div>
            <span>P3 Medium Defect</span>
          </div>

          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-red-500/80 flex items-center justify-center text-white text-[9px]">
              <Flame className="w-2.5 h-2.5" />
            </div>
            <span>Traffic Congestion</span>
          </div>

          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-amber-500/80 flex items-center justify-center text-white text-[9px]">
              <ShieldAlert className="w-2.5 h-2.5" />
            </div>
            <span>School Zone</span>
          </div>

          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-teal-500/80 flex items-center justify-center text-white text-[9px]">
              <Building2 className="w-2.5 h-2.5" />
            </div>
            <span>Hospital Zone</span>
          </div>
        </div>
      </div>
    </div>
  );
}
