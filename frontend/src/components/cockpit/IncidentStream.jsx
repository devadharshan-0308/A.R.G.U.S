import React from 'react';
import { Radio, MapPin, ExternalLink } from 'lucide-react';

export default function IncidentStream({ incidents = [], onOpenEvidence }) {
  // Default items matching reference image if incidents array is empty
  const defaultCards = [
    {
      id: 'card-1',
      severity_tag: 'P1',
      severity_bg: 'bg-red-600',
      time_str: '09:42 AM',
      title: 'Severe Pothole',
      location: 'Anna Salai',
      metric_label: '0.09 m² | 55 mm',
      thumbnail_url: 'https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=400&auto=format&fit=crop&q=60&ixlib=rb-4.0.3',
      irc_code: 'IRC: 82'
    },
    {
      id: 'card-2',
      severity_tag: 'P2',
      severity_bg: 'bg-amber-500',
      time_str: '09:40 AM',
      title: 'Damaged Divider',
      location: 'Nungambakkam High Rd',
      metric_label: 'IRC: 82',
      thumbnail_url: 'https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=400&auto=format&fit=crop&q=60&ixlib=rb-4.0.3',
      irc_code: 'IRC: 119'
    },
    {
      id: 'card-3',
      severity_tag: 'P3',
      severity_bg: 'bg-blue-500',
      time_str: '09:38 AM',
      title: 'Faded Zebra Crossing',
      location: 'T. Nagar',
      metric_label: 'IRC: 35',
      thumbnail_url: 'https://images.unsplash.com/photo-1502877338535-766e1452684a?w=400&auto=format&fit=crop&q=60&ixlib=rb-4.0.3',
      irc_code: 'IRC: 35'
    },
    {
      id: 'card-4',
      severity_tag: 'P1',
      severity_bg: 'bg-red-600',
      time_str: '09:35 AM',
      title: 'Rash Driving',
      location: 'GST Road',
      metric_label: 'TN-09-AB-1234',
      thumbnail_url: 'https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?w=400&auto=format&fit=crop&q=60&ixlib=rb-4.0.3',
      irc_code: 'MoRTH'
    },
    {
      id: 'card-5',
      severity_tag: 'P1',
      severity_bg: 'bg-red-600',
      time_str: '09:33 AM',
      title: 'Pedestrian in School Zone',
      location: 'Guindy',
      metric_label: 'High Risk',
      thumbnail_url: 'https://images.unsplash.com/photo-1494515843206-f3117d3f51b7?w=400&auto=format&fit=crop&q=60&ixlib=rb-4.0.3',
      irc_code: 'SAFETY'
    }
  ];

  const cardsToDisplay = incidents.length > 0 ? incidents : defaultCards;

  return (
    <div id="live-incidents-section" className="glass-panel rounded-2xl p-4 select-none border border-slate-800/80 shadow-tactical">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Radio className="w-4 h-4 text-blue-400 animate-pulse" />
          <h3 className="text-sm font-bold text-slate-100 tracking-wide">Live Incident Stream (Real-time)</h3>
        </div>
        <button 
          onClick={() => onOpenEvidence && onOpenEvidence(cardsToDisplay[0])}
          className="text-xs font-semibold text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
        >
          <span>View All</span>
          <ExternalLink className="w-3 h-3" />
        </button>
      </div>

      {/* Horizontal Cards Container */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {cardsToDisplay.slice(0, 5).map((card, index) => {
          const sevTag = card.severity_tag || (card.severity && card.severity.includes('severe') ? 'P1' : 'P2');
          const sevBg = sevTag === 'P1' ? 'bg-red-600' : (sevTag === 'P2' ? 'bg-amber-500' : 'bg-blue-500');

          return (
            <div
              key={card.id || index}
              onClick={() => onOpenEvidence && onOpenEvidence(card)}
              className="bg-[#0e1626] border border-slate-800 hover:border-slate-600 rounded-xl overflow-hidden cursor-pointer transition-all hover:scale-[1.02] shadow-md group flex flex-col justify-between"
            >
              {/* Card Image Thumbnail + Severity Badge */}
              <div className="relative h-28 bg-slate-900 overflow-hidden">
                {card.thumbnail || card.thumbnail_url ? (
                  <img
                    src={card.thumbnail || card.thumbnail_url}
                    alt={card.title || card.severity_label}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    onError={(e) => {
                      e.target.style.display = 'none';
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-slate-900 text-slate-600">
                    <Radio className="w-8 h-8 opacity-40" />
                  </div>
                )}

                {/* Top Badges */}
                <div className="absolute top-2 left-2 flex items-center gap-1 z-10">
                  <span className={`${sevBg} text-white font-extrabold text-[10px] px-2 py-0.5 rounded shadow-md`}>
                    {sevTag}
                  </span>
                </div>

                <div className="absolute top-2 right-2 bg-black/70 backdrop-blur-md text-slate-300 font-mono text-[10px] font-semibold px-2 py-0.5 rounded border border-white/10">
                  {card.time_str || card.timestamp_sec || '09:42 AM'}
                </div>
              </div>

              {/* Card Footer Text Metadata */}
              <div className="p-3 space-y-1">
                <div className="font-bold text-xs text-white truncate group-hover:text-blue-400 transition-colors">
                  {card.title || card.severity_label || 'Pothole Alert'}
                </div>

                <div className="flex items-center gap-1 text-[11px] text-slate-400 truncate">
                  <MapPin className="w-3 h-3 text-slate-500 shrink-0" />
                  <span className="truncate">{card.location || card.location_name || 'Anna Salai'}</span>
                </div>

                <div className="pt-1.5 flex items-center justify-between text-[10px] border-t border-slate-800/80">
                  <span className="font-mono text-red-400 font-bold">{card.metric_label || card.dimension_str || '0.09 m²'}</span>
                  <span className="text-slate-400 font-semibold">{card.irc_code || 'IRC: 82'}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
