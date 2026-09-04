import React, { useState } from 'react';
import { ShieldAlert, Search, Car, FileCheck, MapPin } from 'lucide-react';

export default function SecurityHubPage({ onOpenEvidence }) {
  const [searchQuery, setSearchQuery] = useState('');

  const samplePlates = [
    { plate: 'TN-09-AB-1234', state: 'Tamil Nadu', rto: 'Chennai Central', conf: '94.2%', speed: '62 km/h', flag: 'Speeding / Rash Driving', time: '09:35 AM', location: 'GST Road' },
    { plate: 'TN-07-BV-9021', state: 'Tamil Nadu', rto: 'Chennai South', conf: '91.8%', speed: '42 km/h', flag: 'Clear', time: '09:28 AM', location: 'Anna Salai' },
    { plate: 'KA-01-MJ-4021', state: 'Karnataka', rto: 'Bengaluru Central', conf: '88.5%', speed: '55 km/h', flag: 'Stolen Hotlist Tag', time: '09:15 AM', location: 'OMR IT Highway' },
    { plate: 'DL-03-CC-1122', state: 'Delhi', rto: 'New Delhi', conf: '95.0%', speed: '38 km/h', flag: 'Clear', time: '08:50 AM', location: 'ECR Corridor' },
  ];

  const filtered = samplePlates.filter(p => p.plate.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div className="p-4 space-y-4 max-w-[1920px] mx-auto animate-fadeIn select-none">
      {/* Top Header */}
      <div className="bg-[#0d1322] border border-slate-800 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-red-600/20 border border-red-500/40 flex items-center justify-center text-red-400">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-base font-bold text-white">Security & Hit-and-Run Forensic Hub</h1>
            <p className="text-xs text-slate-400">MoRTH Indian Registration Plate Recognition (ANPR) & Offending Vehicle Dossier</p>
          </div>
        </div>

        {/* Search Bar */}
        <div className="flex items-center gap-2 bg-[#131b2e] border border-slate-700/60 rounded-xl px-3.5 py-2 w-72">
          <Search className="w-4 h-4 text-slate-400 shrink-0" />
          <input
            type="text"
            placeholder="Search Plate (e.g. TN-09)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-transparent text-xs text-white placeholder-slate-500 focus:outline-none w-full"
          />
        </div>
      </div>

      {/* Plate Passage Log Table */}
      <div className="glass-panel rounded-2xl p-6 border border-slate-800">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <Car className="w-4 h-4 text-blue-400" />
            <span>MoRTH Recognized Plate Log ({filtered.length})</span>
          </h2>
        </div>

        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-[#0b0f19] text-slate-400 uppercase font-mono text-[10px] border-b border-slate-800">
            <tr>
              <th className="py-3 px-4">Synthesized Plate</th>
              <th className="py-3 px-4">State / RTO</th>
              <th className="py-3 px-4">OCR Confidence</th>
              <th className="py-3 px-4">Tracked Speed</th>
              <th className="py-3 px-4">Safety Flag</th>
              <th className="py-3 px-4">Timestamp & Location</th>
              <th className="py-3 px-4 text-right">Dossier</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80 font-mono">
            {filtered.map((row, idx) => (
              <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                <td className="py-3 px-4 font-bold text-white text-sm">{row.plate}</td>
                <td className="py-3 px-4 font-sans text-slate-300">{row.state} ({row.rto})</td>
                <td className="py-3 px-4 text-emerald-400 font-bold">{row.conf}</td>
                <td className="py-3 px-4 text-slate-200">{row.speed}</td>
                <td className="py-3 px-4">
                  <span className={`px-2.5 py-1 rounded text-[10px] font-bold ${
                    row.flag.includes('Clear') ? 'bg-slate-800 text-slate-400' : 'bg-red-500/20 text-red-400 border border-red-500/30'
                  }`}>
                    {row.flag}
                  </span>
                </td>
                <td className="py-3 px-4 font-sans text-slate-400">
                  <div>{row.time}</div>
                  <div className="text-[10px] text-slate-500 flex items-center gap-1"><MapPin className="w-3 h-3 text-red-500" /> {row.location}</div>
                </td>
                <td className="py-3 px-4 text-right">
                  <button
                    onClick={() => onOpenEvidence && onOpenEvidence({ title: `Plate Dossier: ${row.plate}`, severity_tag: 'P1', severity_label: row.flag, location_name: row.location, irc_code: 'MoRTH ANPR' })}
                    className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 ml-auto transition-colors"
                  >
                    <FileCheck className="w-3.5 h-3.5" />
                    <span>View Dossier</span>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
