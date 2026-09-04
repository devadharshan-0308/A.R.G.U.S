import React from 'react';
import { X, MapPin, ExternalLink, ShieldCheck, FileText, Image as ImageIcon } from 'lucide-react';

export default function EvidenceModal({ incident, onClose }) {
  if (!incident) return null;

  const lat = incident.latitude || 13.082716;
  const lng = incident.longitude || 80.270708;
  const googleMapsUrl = `https://maps.google.com/?q=${lat},${lng}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
      <div className="bg-[#0f172a] border border-slate-700/80 rounded-2xl max-w-4xl w-full overflow-hidden shadow-2xl space-y-0 text-slate-100">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-[#0b0f19]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <span>Forensic Evidence Inspector</span>
                <span className="bg-red-600 text-white text-[10px] px-2 py-0.5 rounded font-mono font-bold">
                  {incident.severity_tag || 'P1 CRITICAL'}
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Audit Trail ID: <span className="font-mono text-slate-300">EV-CHN-2026-0841</span> · SHA-256 Verified
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content Grid: 4 Evidence Panels */}
        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[75vh] overflow-y-auto">
          {/* Panel 1: Raw Snapshot Capture */}
          <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-3 space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
              <span className="flex items-center gap-1.5"><ImageIcon className="w-3.5 h-3.5 text-blue-400" /> Panel 1: Raw Snapshot</span>
              <span className="text-[10px] text-slate-500 font-mono">1080p 30FPS</span>
            </div>
            <div className="h-44 bg-slate-900 rounded-lg overflow-hidden flex items-center justify-center relative border border-slate-800">
              {incident.thumbnail || incident.thumbnail_url ? (
                <img src={incident.thumbnail || incident.thumbnail_url} alt="Raw Frame" className="w-full h-full object-cover" />
              ) : (
                <div className="text-slate-500 text-xs font-mono">Camera Frame #184</div>
              )}
            </div>
          </div>

          {/* Panel 2: Preprocessed Depth / Binarization */}
          <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-3 space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
              <span className="flex items-center gap-1.5"><FileText className="w-3.5 h-3.5 text-amber-400" /> Panel 2: LiDAR Depth Mask</span>
              <span className="text-[10px] text-slate-500 font-mono">MiDaS v3.1</span>
            </div>
            <div className="h-44 bg-slate-950 rounded-lg overflow-hidden flex items-center justify-center relative border border-slate-800 p-2">
              <div className="w-full h-full bg-gradient-to-tr from-purple-900 via-indigo-800 to-yellow-500 rounded flex items-center justify-center opacity-80">
                <span className="bg-black/60 text-white text-[11px] font-mono font-bold px-3 py-1 rounded border border-white/20">
                  Volumetric Surface Area: 0.09 m²
                </span>
              </div>
            </div>
          </div>

          {/* Panel 3: Forensic Bounding Box Annotation */}
          <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-3 space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
              <span className="flex items-center gap-1.5"><ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> Panel 3: AI Annotation</span>
              <span className="text-[10px] text-emerald-400 font-mono font-bold">94.2% Conf</span>
            </div>
            <div className="h-36 bg-slate-900 rounded-lg p-3 space-y-1.5 text-xs text-slate-300 border border-slate-800 font-mono">
              <div><span className="text-slate-500">Defect Type:</span> <strong className="text-white">{incident.title || incident.severity_label}</strong></div>
              <div><span className="text-slate-500">IRC Code:</span> <span className="text-amber-400 font-bold">{incident.irc_code || 'IRC:82-2015'}</span></div>
              <div><span className="text-slate-500">Repair Action:</span> Mill & Inlay Bituminous Concrete</div>
              <div><span className="text-slate-500">Estimated Cost:</span> <span className="text-emerald-400 font-bold">₹4,500 INR</span></div>
              <div><span className="text-slate-500">Legal SLA:</span> <span className="text-red-400 font-bold">24 Hours (P1)</span></div>
            </div>
          </div>

          {/* Panel 4: Geospatial Metadata & Google Maps Action */}
          <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-3 space-y-3 flex flex-col justify-between">
            <div className="space-y-1.5 text-xs text-slate-300">
              <div className="flex items-center gap-1.5 text-slate-200 font-semibold mb-1">
                <MapPin className="w-4 h-4 text-red-500" />
                <span>Geospatial Location</span>
              </div>
              <div className="font-mono text-slate-200">{incident.location || incident.location_name || 'Anna Salai Corridor'}, Chennai</div>
              <div className="text-slate-400 font-mono text-[11px]">GPS: {lat.toFixed(6)}° N, {lng.toFixed(6)}° E</div>
              <div className="text-slate-400 text-[11px]">Geohash Cluster: 15m radius deduplicated</div>
            </div>

            <a
              href={googleMapsUrl}
              target="_blank"
              rel="noreferrer"
              className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs py-2.5 px-4 rounded-xl flex items-center justify-center gap-2 shadow-glow-blue transition-all text-center"
            >
              <MapPin className="w-4 h-4" />
              <span>Open Exact Location in Google Maps</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-[#0b0f19] flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors"
          >
            Close Evidence Inspector
          </button>
        </div>
      </div>
    </div>
  );
}
