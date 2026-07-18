import { Camera as CameraIcon, Play, Pause, RefreshCw, Cpu, Activity } from 'lucide-react';
import { useEffect, useRef, useState, useCallback } from 'react';
import { useI18n } from '../contexts/I18nContext.jsx';
import { RECOGNITION_WS_URL } from '../config/network.js';
import { FilesetResolver, GestureRecognizer } from '@mediapipe/tasks-vision';

export function Translation() {
  const { t } = useI18n();
  const [status, setStatus] = useState('Disconnected');
  const [predictedWord, setPredictedWord] = useState('');
  const [confidence, setConfidence] = useState(0.0);
  const [glosses, setGlosses] = useState([]);
  const [sentence, setSentence] = useState('');
  const [paragraph, setParagraph] = useState('');
  const [mode, setMode] = useState('browser'); // 'browser' or 'server'
  const [isPaused, setIsPaused] = useState(false);
  
  // Stats
  const [fps, setFps] = useState(0);
  const [latency, setLatency] = useState(0);
  const [frameCount, setFrameCount] = useState(0);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const mpHolisticRef = useRef(null);
  const mpCameraRef = useRef(null);
  
  const frameTimes = useRef([]);
  const latencyStartTimes = useRef(new Map());
  const requestCount = useRef(0);

  // Initialize WebSocket connection
  const connectWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    setStatus('Connecting...');
    const ws = new WebSocket(RECOGNITION_WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WebSocket] Connected to translation stream');
      setStatus('Connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Handle predicted result
        if (data.word !== undefined) {
          setPredictedWord(data.word);
          setConfidence(data.confidence);
          
          if (data.final === true) {
            setParagraph((prev) => {
              const cleaned = prev ? prev.trim() : '';
              return cleaned ? `${cleaned} ${data.sentence.trim()}` : data.sentence.trim();
            });
            setSentence('');
            setGlosses([]);
          } else {
            setGlosses(data.glosses || []);
            if (data.sentence) {
              setSentence(data.sentence);
            }
          }
        }

        // Calculate latency
        const frameId = data.frameId || data.glosses?.length;
        if (latencyStartTimes.current.has(frameId)) {
          const startTime = latencyStartTimes.current.get(frameId);
          setLatency(Math.round(performance.now() - startTime));
          latencyStartTimes.current.delete(frameId);
        }
      } catch (err) {
        console.error('[WebSocket] Error parsing response:', err);
      }
    };

    ws.onerror = (err) => {
      console.error('[WebSocket] Socket error:', err);
      setStatus('Connection Error');
    };

    ws.onclose = () => {
      console.log('[WebSocket] Connection closed');
      setStatus('Disconnected');
    };
  }, []);

  // Send payload to WebSocket
  const sendFramePayload = useCallback((payload) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN || isPaused) return;

    requestCount.current += 1;
    const frameId = requestCount.current;
    latencyStartTimes.current.set(frameId, performance.now());

    wsRef.current.send(JSON.stringify({
      ...payload,
      frameId
    }));

    // Update FPS tracking
    const now = performance.now();
    frameTimes.current.push(now);
    // Keep frame times within last 1 second
    while (frameTimes.current.length && frameTimes.current[0] < now - 1000) {
      frameTimes.current.shift();
    }
    setFps(frameTimes.current.length);
    setFrameCount((c) => c + 1);
  }, [isPaused]);

  // Clean canvas overlay
  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  };

  // Browser MediaPipe onResults callback
  const onResults = useCallback((results) => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;

    const ctx = canvas.getContext('2d');
    if (canvas.width !== video.videoWidth) canvas.width = video.videoWidth;
    if (canvas.height !== video.videoHeight) canvas.height = video.videoHeight;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw MediaPipe skeletons using CDN drawing utils
    if (window.drawConnectors && window.drawLandmarks) {
      // 1. Draw Pose
      if (results.poseLandmarks) {
        window.drawConnectors(ctx, results.poseLandmarks, window.POSE_CONNECTIONS, {
          color: '#3b82f6',
          lineWidth: 2
        });
        window.drawLandmarks(ctx, results.poseLandmarks, {
          color: '#60a5fa',
          lineWidth: 1,
          radius: 3
        });
      }
      // 2. Draw Left Hand
      if (results.leftHandLandmarks) {
        window.drawConnectors(ctx, results.leftHandLandmarks, window.HAND_CONNECTIONS, {
          color: '#10b981',
          lineWidth: 3
        });
        window.drawLandmarks(ctx, results.leftHandLandmarks, {
          color: '#34d399',
          lineWidth: 1,
          radius: 4
        });
      }
      // 3. Draw Right Hand
      if (results.rightHandLandmarks) {
        window.drawConnectors(ctx, results.rightHandLandmarks, window.HAND_CONNECTIONS, {
          color: '#eab308',
          lineWidth: 3
        });
        window.drawLandmarks(ctx, results.rightHandLandmarks, {
          color: '#fde047',
          lineWidth: 1,
          radius: 4
        });
      }
    }

    // Stream the 55 landmarks (filtered and centered by python backend)
    sendFramePayload({
      type: 'landmarks',
      landmarks: {
        pose: results.poseLandmarks || null,
        left_hand: results.leftHandLandmarks || null,
        right_hand: results.rightHandLandmarks || null
      }
    });
  }, [sendFramePayload]);

  // Server mode frame capture and loop
  const runServerCaptureLoop = useCallback(() => {
    let active = true;
    const captureCanvas = document.createElement('canvas');

    const captureFrame = async () => {
      const video = videoRef.current;
      if (!video || !active) return;
      if (video.paused || video.ended) {
        requestAnimationFrame(captureFrame);
        return;
      }

      if (video.videoWidth && mode === 'server' && status === 'Connected') {
        captureCanvas.width = 320; // Reduced resolution for fast server-side processing
        captureCanvas.height = 240;
        const ctx = captureCanvas.getContext('2d');
        ctx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
        const dataUrl = captureCanvas.toDataURL('image/jpeg', 0.60);

        sendFramePayload({
          type: 'frame',
          image: dataUrl
        });
      }

      // Capture every 100ms
      setTimeout(() => {
        if (active) requestAnimationFrame(captureFrame);
      }, 100);
    };

    requestAnimationFrame(captureFrame);

    return () => {
      active = false;
    };
  }, [mode, status, sendFramePayload]);

  // Setup MediaPipe Holistic browser instance
  useEffect(() => {
    if (mode !== 'browser' || !videoRef.current) return;

    if (!window.Holistic || !window.Camera) {
      console.warn('[MediaPipe] Holistic CDN scripts not fully loaded yet.');
      return;
    }

    try {
      console.log('[MediaPipe] Initializing Holistic tracker...');
      const holisticTracker = new window.Holistic({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/holistic/${file}`
      });

      holisticTracker.setOptions({
        modelComplexity: 1,
        smoothLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5
      });

      holisticTracker.onResults(onResults);
      mpHolisticRef.current = holisticTracker;

      console.log('[MediaPipe] Launching local Camera stream...');
      const camera = new window.Camera(videoRef.current, {
        onFrame: async () => {
          if (videoRef.current && mode === 'browser' && status === 'Connected' && !isPaused) {
            await holisticTracker.send({ image: videoRef.current });
          }
        },
        width: 640,
        height: 480
      });

      camera.start().then(() => {
        console.log('[MediaPipe] Camera pipeline started.');
      });
      mpCameraRef.current = camera;
    } catch (err) {
      console.error('[MediaPipe] Initialization error:', err);
    }

    return () => {
      console.log('[MediaPipe] Stopping Holistic tracker...');
      mpCameraRef.current?.stop();
      mpCameraRef.current = null;
      mpHolisticRef.current?.close();
      mpHolisticRef.current = null;
      clearCanvas();
    };
  }, [mode, status, isPaused, onResults]);

  // Setup Server-side fallback capture loop
  useEffect(() => {
    if (mode !== 'server' || !videoRef.current) return;

    let stopLoop = () => {};
    
    // Acquire webcam stream
    navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
      .then((stream) => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().then(() => {
            stopLoop = runServerCaptureLoop();
          });
        }
      })
      .catch((err) => {
        console.error('[Camera] Access failed:', err);
      });

    return () => {
      stopLoop();
      if (videoRef.current?.srcObject) {
        const tracks = videoRef.current.srcObject.getTracks();
        tracks.forEach((track) => track.stop());
        videoRef.current.srcObject = null;
      }
    };
  }, [mode, runServerCaptureLoop]);

  // Connect WebSocket on mount
  useEffect(() => {
    connectWebSocket();
    return () => {
      wsRef.current?.close();
    };
  }, [connectWebSocket]);

  // Reset the translation session on backend
  const handleReset = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'reset' }));
    }
    setPredictedWord('');
    setConfidence(0.0);
    setGlosses([]);
    setSentence('');
    setParagraph('');
    clearCanvas();
  };

  return (
    <section className="p-6 max-w-6xl mx-auto space-y-6 text-slate-100 min-h-[calc(100vh-80px)] bg-slate-950/20 rounded-2xl border border-slate-800/40 backdrop-blur-xl">
      {/* Header Controls */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-slate-900/40 p-4 rounded-xl border border-slate-800/30">
        <div>
          <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-400 via-emerald-400 to-yellow-400 bg-clip-text text-transparent">
            {t('translation')}
          </h2>
          <p className="text-sm text-slate-400 mt-1">Real-time sign language translation pipeline</p>
        </div>

        <div className="flex flex-wrap gap-2 items-center">
          {/* Mode Selector */}
          <button
            onClick={() => setMode((m) => (m === 'browser' ? 'server' : 'browser'))}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold"
          >
            <Cpu size={14} className={mode === 'browser' ? 'text-emerald-400' : 'text-blue-400'} />
            <span>Mode: {mode === 'browser' ? 'Browser (Fast)' : 'Server (Fallback)'}</span>
          </button>

          {/* Pause Toggle */}
          <button
            onClick={() => setIsPaused((p) => !p)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold ${
              isPaused
                ? 'bg-amber-600/20 border-amber-500 text-amber-300'
                : 'bg-slate-800 hover:bg-slate-700 border-slate-700'
            }`}
          >
            {isPaused ? <Play size={14} /> : <Pause size={14} />}
            <span>{isPaused ? 'Resume' : 'Pause'}</span>
          </button>

          {/* Reset Button */}
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-rose-400"
          >
            <RefreshCw size={14} />
            <span>Reset</span>
          </button>

          {/* Reconnect WS */}
          <button
            onClick={connectWebSocket}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-emerald-400"
          >
            Reconnect
          </button>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Camera / Visualizer Column */}
        <div className="lg:col-span-2 space-y-4">
          <div className="relative rounded-2xl overflow-hidden aspect-video bg-slate-900 border border-slate-850 shadow-2xl flex items-center justify-center">
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="absolute inset-0 w-full h-full object-cover transform -scale-x-100"
              aria-label="Signing Camera Feed"
            />
            <canvas
              ref={canvasRef}
              className="absolute inset-0 w-full h-full object-cover z-10 pointer-events-none transform -scale-x-100"
            />
            {status !== 'Connected' && (
              <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-sm gap-2">
                <Activity className="animate-pulse text-blue-400" size={32} />
                <span className="font-semibold text-slate-300">{status}</span>
                <span className="text-xs text-slate-500">Ensure backend services are running on ports 8000 and 8001</span>
              </div>
            )}
            {isPaused && (
              <div className="absolute inset-0 z-20 flex items-center justify-center bg-amber-950/40 backdrop-blur-[2px]">
                <span className="px-4 py-2 bg-amber-600 border border-amber-400 rounded-xl font-bold text-amber-100 flex items-center gap-2 shadow-lg">
                  <Pause size={16} /> PAUSED
                </span>
              </div>
            )}
          </div>

          {/* Stats Bar */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-slate-900/30 border border-slate-800/40 p-3 rounded-xl text-center">
              <span className="block text-xs text-slate-400">Stream FPS</span>
              <strong className="text-xl text-blue-400">{fps}</strong>
            </div>
            <div className="bg-slate-900/30 border border-slate-800/40 p-3 rounded-xl text-center">
              <span className="block text-xs text-slate-400">Latency (RTT)</span>
              <strong className="text-xl text-emerald-400">{latency} ms</strong>
            </div>
            <div className="bg-slate-900/30 border border-slate-800/40 p-3 rounded-xl text-center">
              <span className="block text-xs text-slate-400">Total Frames</span>
              <strong className="text-xl text-yellow-400">{frameCount}</strong>
            </div>
            <div className="bg-slate-900/30 border border-slate-800/40 p-3 rounded-xl text-center">
              <span className="block text-xs text-slate-400">Active Gloss</span>
              <strong className="text-xl text-rose-400">{glosses.length}</strong>
            </div>
          </div>
        </div>

        {/* Translation captions / outputs Column */}
        <div className="space-y-6">
          {/* Live prediction status card */}
          <div className="bg-slate-900/40 border border-slate-800/40 p-5 rounded-2xl shadow-xl flex flex-col justify-between min-h-[160px] relative overflow-hidden">
            <div className="absolute top-0 right-0 p-3">
              <div className={`w-3.5 h-3.5 rounded-full ${status === 'Connected' ? 'bg-emerald-500 animate-ping' : 'bg-rose-500'}`} />
            </div>
            <div>
              <span className="text-xs uppercase tracking-wider text-slate-400 font-semibold block">Live Prediction</span>
              <h3 className="text-4xl font-extrabold text-white mt-3 truncate min-h-[48px]">
                {predictedWord || <span className="text-slate-600 italic">Waiting...</span>}
              </h3>
            </div>
            <div className="mt-4 flex items-center justify-between border-t border-slate-800/60 pt-3">
              <span className="text-xs text-slate-400">Confidence Score</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold">{Math.round(confidence * 100)}%</span>
                <div className="w-16 bg-slate-800 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-emerald-500 to-emerald-300 h-full rounded-full transition-all duration-150"
                    style={{ width: `${confidence * 100}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Recognized word history capsule stream */}
          <div className="bg-slate-900/40 border border-slate-800/40 p-5 rounded-2xl shadow-xl flex flex-col gap-3 min-h-[180px]">
            <span className="text-xs uppercase tracking-wider text-slate-400 font-semibold block">Glosses Sequence</span>
            <div className="flex flex-wrap gap-2 overflow-y-auto max-h-[120px] p-1.5 rounded-lg bg-slate-950/40 border border-slate-900/80">
              {glosses.length === 0 ? (
                <span className="text-xs text-slate-500 italic">No signs detected yet. Sign continuously in front of the camera.</span>
              ) : (
                glosses.map((word, idx) => (
                  <span
                    key={`${word}-${idx}`}
                    className="px-2.5 py-1 rounded-md bg-blue-500/10 text-blue-300 border border-blue-500/20 text-xs font-bold uppercase animate-fade-in"
                  >
                    {word}
                  </span>
                ))
              )}
            </div>
          </div>

          {/* Prompt Engineered LLM Natural Sentence */}
          <div className="bg-slate-900/40 border border-slate-800/40 p-5 rounded-2xl shadow-xl space-y-3">
            <span className="text-xs uppercase tracking-wider text-slate-400 font-semibold block">Natural Sentence Translation</span>
            <div className="p-4 bg-slate-950/80 border border-emerald-500/20 rounded-xl min-h-[96px] flex items-center">
              <p className="text-lg font-medium leading-relaxed">
                {paragraph || sentence ? (
                  <>
                    {paragraph && <span className="text-slate-400 mr-1.5">{paragraph}</span>}
                    {sentence && <span className="text-emerald-300">{sentence}</span>}
                  </>
                ) : (
                  <span className="text-slate-600 italic">The translated English sentence will appear here in real-time.</span>
                )}
              </p>
            </div>
          </div>
        </div>

      </div>
    </section>
  );
}
