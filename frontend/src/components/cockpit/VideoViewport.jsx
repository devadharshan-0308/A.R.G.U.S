import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, Camera, Maximize2, Minimize2, Video, RefreshCw, Zap } from 'lucide-react';
import { fetchVideos, triggerPipeline } from '../../services/api';

export default function VideoViewport({ onOpenEvidence }) {
  const [isPlaying, setIsPlaying] = useState(true);
  const [videos, setVideos] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState('pothole.mp4');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isTriggering, setIsTriggering] = useState(false);
  const videoRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    fetchVideos().then((list) => {
      if (list && list.length > 0) {
        setVideos(list);
        const firstInput = list.find((v) => v.type === 'input') || list[0];
        setSelectedVideo(firstInput.name);
      }
    });
  }, []);

  const handlePlayPause = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleRunPipeline = async () => {
    setIsTriggering(true);
    await triggerPipeline(selectedVideo, true);
    setTimeout(() => setIsTriggering(false), 2000);
  };

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!isFullscreen) {
      if (containerRef.current.requestFullscreen) {
        containerRef.current.requestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
    setIsFullscreen(!isFullscreen);
  };

  return (
    <div id="live-video-section" ref={containerRef} className="glass-panel rounded-2xl p-4 flex flex-col justify-between relative overflow-hidden select-none border border-slate-800/80 shadow-tactical">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Video className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-bold text-slate-100 tracking-wide">Live Video Feed (AI Detection Overlay)</h3>
        </div>
        <div className="flex items-center gap-3">
          {/* Stream Selector */}
          <div className="flex items-center gap-1.5 bg-slate-900/80 border border-slate-700/60 rounded-lg px-2 py-1 text-xs">
            <select
              value={selectedVideo}
              onChange={(e) => setSelectedVideo(e.target.value)}
              className="bg-transparent text-slate-200 focus:outline-none cursor-pointer"
            >
              {videos.length > 0 ? (
                videos.map((v, i) => (
                  <option key={i} value={v.name} className="bg-slate-900 text-slate-200">
                    {v.name} ({v.type})
                  </option>
                ))
              ) : (
                <option value="pothole.mp4">pothole.mp4</option>
              )}
            </select>
            <button
              onClick={handleRunPipeline}
              disabled={isTriggering}
              title="Run AI Pipeline on backend"
              className="ml-1 text-blue-400 hover:text-blue-300 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isTriggering ? 'animate-spin' : ''}`} />
            </button>
          </div>

          <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/30">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>Live</span>
          </div>
        </div>
      </div>

      {/* Main Video Viewport Canvas Container */}
      <div className="relative w-full h-[360px] bg-black rounded-xl overflow-hidden group border border-slate-800">
        {/* Timestamp Overlay */}
        <div className="absolute top-3 left-3 z-20 font-mono text-xs font-semibold text-white bg-black/60 backdrop-blur-md px-2.5 py-1 rounded border border-white/10 tracking-wider">
          03-09-2026 &nbsp; 09:42:18 &nbsp; Chennai
        </div>

        {/* HTML5 Video Element */}
        <video
          ref={videoRef}
          src={`/data/input/${selectedVideo}`}
          autoPlay
          loop
          muted
          playsInline
          className="w-full h-full object-cover"
        />

        {/* Simulated AI Detection Bounding Boxes Matching Reference Image */}
        <div className="absolute inset-0 pointer-events-none z-10">
          {/* Bounding Box 1: Pedestrian #8 (Left) */}
          <div className="absolute top-[35%] left-[6%] w-[12%] h-[40%] border-2 border-cyan-400 rounded-sm">
            <div className="absolute -top-6 left-0 bg-cyan-500 text-black font-extrabold text-[10px] px-1.5 py-0.5 rounded-t font-mono">
              Pedestrian #8
            </div>
          </div>

          {/* Bounding Box 2: Bus #12 (Center Top) */}
          <div className="absolute top-[20%] left-[25%] w-[22%] h-[38%] border-2 border-emerald-400 rounded-sm">
            <div className="absolute -top-6 left-0 bg-emerald-500 text-black font-extrabold text-[10px] px-1.5 py-0.5 rounded-t font-mono">
              Bus #12
            </div>
          </div>

          {/* Bounding Box 3: Car #27 */}
          <div className="absolute top-[35%] left-[33%] w-[12%] h-[24%] border-2 border-blue-400 rounded-sm">
            <div className="absolute -top-6 left-0 bg-blue-500 text-white font-extrabold text-[10px] px-1.5 py-0.5 rounded-t font-mono">
              Car #27
            </div>
          </div>

          {/* Bounding Box 4: Bike #45 */}
          <div className="absolute top-[36%] left-[41%] w-[8%] h-[22%] border-2 border-blue-400 rounded-sm">
            <div className="absolute -top-6 left-0 bg-blue-500 text-white font-extrabold text-[10px] px-1.5 py-0.5 rounded-t font-mono">
              Bike #45
            </div>
          </div>

          {/* Bounding Box 5: Pedestrian #9 (Right) */}
          <div className="absolute top-[38%] left-[47%] w-[8%] h-[32%] border-2 border-cyan-400 rounded-sm">
            <div className="absolute -top-6 left-0 bg-cyan-500 text-black font-extrabold text-[10px] px-1.5 py-0.5 rounded-t font-mono">
              Pedestrian #9
            </div>
          </div>

          {/* Bounding Box 6: Pothole 0.09 m² | 55 mm (Critical Red - Foreground Center) */}
          <div className="absolute bottom-[10%] left-[31%] w-[16%] h-[25%] border-2 border-red-500 bg-red-500/10 rounded-sm shadow-glow-red animate-pulse">
            <div className="absolute -top-6 left-0 bg-red-600 text-white font-extrabold text-[11px] px-2 py-0.5 rounded-t font-mono flex items-center gap-1">
              <span>Pothole</span>
              <span className="opacity-90 font-normal">0.09 m² | 55 mm</span>
            </div>
          </div>
        </div>

        {/* Video Control Bar Overlay */}
        <div className="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-black/90 via-black/60 to-transparent px-4 flex items-center justify-between z-20">
          <div className="flex items-center gap-3">
            <button
              onClick={handlePlayPause}
              className="text-white hover:text-blue-400 transition-colors p-1"
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <div className="flex items-center gap-1.5 text-xs text-slate-300 font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span>Live</span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={() => onOpenEvidence && onOpenEvidence()}
              className="text-slate-300 hover:text-white transition-colors p-1"
              title="Capture Evidence Snapshot"
            >
              <Camera className="w-4 h-4" />
            </button>
            <button
              onClick={toggleFullscreen}
              className="text-slate-300 hover:text-white transition-colors p-1"
              title="Fullscreen"
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>

            <div className="flex items-center gap-1 text-xs font-mono text-emerald-400 bg-slate-900/80 px-2 py-0.5 rounded border border-slate-700">
              <Zap className="w-3 h-3" />
              <span>Latency: 28 ms</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
