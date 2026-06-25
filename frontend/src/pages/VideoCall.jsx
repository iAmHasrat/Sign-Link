import { Maximize, Mic, MicOff, PhoneOff, Video, VideoOff } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { LandmarkOverlay } from '../components/LandmarkOverlay.jsx';
import { useAuth } from '../contexts/AuthContext.jsx';
import { useI18n } from '../contexts/I18nContext.jsx';
import { detectLandmarks } from '../services/landmarks.js';

const rtcConfig = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };
const cameraConstraints = {
  width: { ideal: 640, max: 640 },
  height: { ideal: 480, max: 480 },
  frameRate: { ideal: 24, max: 30 }
};
const captureSize = { width: 640, height: 480 };
const detectionIntervalMs = 100;
const detectionJpegQuality = 0.62;

function logPeerState(pc) {
  console.log('ICE state:', pc.iceConnectionState);
  console.log('Connection state:', pc.connectionState);
  console.log('Signaling state:', pc.signalingState);
}

export function VideoCall() {
  const { peerId } = useParams();
  const { socket } = useAuth();
  const { t } = useI18n();
  const [receiverId, setReceiverId] = useState(peerId || '');
  const [callId, setCallId] = useState(null);
  const [status, setStatus] = useState('Ready');
  const [audioOn, setAudioOn] = useState(true);
  const [videoOn, setVideoOn] = useState(true);
  const [seconds, setSeconds] = useState(0);
  const [mediaReady, setMediaReady] = useState(false);
  const localVideo = useRef(null);
  const remoteVideo = useRef(null);
  const captureCanvas = useRef(null);
  const landmarkOverlay = useRef(null);
  const localStream = useRef(null);
  const mediaRequest = useRef(null);
  const peer = useRef(null);
  const callIdRef = useRef(null);
  const pendingIceCandidates = useRef([]);
  const detectionAbort = useRef(null);
  const detectionMetrics = useRef({
    droppedFrames: 0,
    lastLogAt: performance.now(),
    processedFrames: 0,
    totalDetectionMs: 0
  });

  useEffect(() => setReceiverId(peerId || ''), [peerId]);

  useEffect(() => {
    callIdRef.current = callId;
  }, [callId]);

  useEffect(() => {
    let timer;
    if (status === 'Connected') timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [status]);

  useEffect(() => {
    if (!mediaReady || !localStream.current || !videoOn) {
      landmarkOverlay.current?.clear();
      landmarkOverlay.current?.setStatus('Landmark service idle');
      return;
    }

    let cancelled = false;
    let busy = false;
    let firstDetectionLogged = false;
    const timer = setInterval(async () => {
      if (busy) {
        detectionMetrics.current.droppedFrames += 1;
        return;
      }
      if (!localVideo.current || !captureCanvas.current) return;
      if (!localVideo.current.videoWidth || !localVideo.current.videoHeight) return;

      busy = true;
      const startedAt = performance.now();
      detectionAbort.current = new AbortController();
      try {
        const canvas = captureCanvas.current;
        if (canvas.width !== captureSize.width) canvas.width = captureSize.width;
        if (canvas.height !== captureSize.height) canvas.height = captureSize.height;
        const context = canvas.getContext('2d', { alpha: false, desynchronized: true });
        context.drawImage(localVideo.current, 0, 0, captureSize.width, captureSize.height);
        const result = await detectLandmarks(
          canvas.toDataURL('image/jpeg', detectionJpegQuality),
          { signal: detectionAbort.current.signal }
        );
        if (!cancelled) {
          const elapsed = performance.now() - startedAt;
          const metrics = detectionMetrics.current;
          metrics.processedFrames += 1;
          metrics.totalDetectionMs += elapsed;
          landmarkOverlay.current?.draw(result);
          landmarkOverlay.current?.setStatus(`${result.status.handsDetected} hand(s), ${result.status.facesDetected} face(s)`);

          if (!firstDetectionLogged) {
            firstDetectionLogged = true;
            console.log('[MediaPipe] First landmark response time:', Math.round(elapsed), 'ms');
          }

          const now = performance.now();
          if (now - metrics.lastLogAt >= 5000) {
            const secondsSinceLog = (now - metrics.lastLogAt) / 1000;
            const fps = metrics.processedFrames / secondsSinceLog;
            const averageMs = metrics.processedFrames
              ? metrics.totalDetectionMs / metrics.processedFrames
              : 0;
            console.log('[MediaPipe] Detection FPS:', fps.toFixed(1));
            console.log('[MediaPipe] Average detection time:', Math.round(averageMs), 'ms');
            console.log('[MediaPipe] Dropped frames:', metrics.droppedFrames);
            metrics.droppedFrames = 0;
            metrics.lastLogAt = now;
            metrics.processedFrames = 0;
            metrics.totalDetectionMs = 0;
          }
        }
      } catch (error) {
        if (!cancelled && error.name !== 'CanceledError' && error.name !== 'AbortError') {
          landmarkOverlay.current?.setStatus('Landmark service unavailable');
        }
      } finally {
        detectionAbort.current = null;
        busy = false;
      }
    }, detectionIntervalMs);

    return () => {
      cancelled = true;
      detectionAbort.current?.abort();
      clearInterval(timer);
      landmarkOverlay.current?.clear();
    };
  }, [mediaReady, videoOn]);

  useEffect(() => {
    if (!socket) return;
    socket.on('incoming-call', handleIncomingCall);
    socket.on('call-accepted', handleCallAccepted);
    socket.on('call-rejected', () => {
      console.log('[WebRTC] Call rejected');
      setStatus('Rejected');
    });
    socket.on('answer', handleAnswer);
    socket.on('ice-candidate', handleIceCandidate);
    socket.on('call-ended', endLocalCall);
    return () => {
      socket.off('incoming-call', handleIncomingCall);
      socket.off('call-accepted', handleCallAccepted);
      socket.off('call-rejected');
      socket.off('answer', handleAnswer);
      socket.off('ice-candidate', handleIceCandidate);
      socket.off('call-ended');
    };
  }, [socket]);

  async function ensureMedia(executionPath) {
    if (localStream.current) {
      console.log(`[VideoCall] Reusing existing local media stream from ${executionPath}`);
      if (localVideo.current && localVideo.current.srcObject !== localStream.current) {
        localVideo.current.srcObject = localStream.current;
      }
      return localStream.current;
    }

    if (mediaRequest.current) {
      console.log(`[VideoCall] Reusing in-flight getUserMedia request from ${executionPath}`);
      return mediaRequest.current;
    }

    console.log(`[VideoCall] Calling getUserMedia from ${executionPath}`);
    mediaRequest.current = navigator.mediaDevices
      .getUserMedia({ video: cameraConstraints, audio: true })
      .then((stream) => {
        localStream.current = stream;
        if (localVideo.current) localVideo.current.srcObject = stream;
        setMediaReady(true);
        const videoTrack = stream.getVideoTracks()[0];
        console.log('[MediaPipe] Camera settings:', videoTrack?.getSettings?.());
        return stream;
      })
      .finally(() => {
        mediaRequest.current = null;
      });

    await mediaRequest.current;
    return localStream.current;
  }

  function attachPeerDiagnostics(pc) {
    pc.oniceconnectionstatechange = () => logPeerState(pc);
    pc.onconnectionstatechange = () => logPeerState(pc);
    pc.onsignalingstatechange = () => logPeerState(pc);
  }

  async function flushPendingIceCandidates(pc) {
    if (!pc.remoteDescription) return;

    while (pendingIceCandidates.current.length) {
      const candidate = pendingIceCandidates.current.shift();
      console.log('[WebRTC] Adding queued ICE candidate');
      await pc.addIceCandidate(candidate);
      logPeerState(pc);
    }
  }

  async function addIceCandidateSafely(candidate) {
    console.log('ICE candidate received');
    const pc = peer.current;

    if (!pc) {
      console.log('[WebRTC] Queueing ICE candidate because peer connection is not ready');
      pendingIceCandidates.current.push(candidate);
      return;
    }

    if (!pc.remoteDescription) {
      console.log('[WebRTC] Queueing ICE candidate because remote description is not set');
      pendingIceCandidates.current.push(candidate);
      logPeerState(pc);
      return;
    }

    await pc.addIceCandidate(candidate);
    console.log('[WebRTC] ICE candidate added');
    logPeerState(pc);
  }

  async function createPeer(targetUserId, executionPath) {
    const stream = await ensureMedia(executionPath);
    console.log('[WebRTC] Creating RTCPeerConnection', rtcConfig);
    const pc = new RTCPeerConnection(rtcConfig);
    attachPeerDiagnostics(pc);

    stream.getTracks().forEach((track) => {
      console.log('[WebRTC] Adding local track', {
        kind: track.kind,
        enabled: track.enabled,
        readyState: track.readyState
      });
      pc.addTrack(track, stream);
    });

    pc.ontrack = (event) => {
      console.log('Remote track received');
      console.log('[WebRTC] Remote track detail', {
        kind: event.track.kind,
        streams: event.streams.length,
        remoteVideoRefExists: Boolean(remoteVideo.current)
      });

      if (remoteVideo.current && event.streams[0]) {
        remoteVideo.current.srcObject = event.streams[0];
        remoteVideo.current.play?.().catch((error) => {
          console.log('[WebRTC] Remote video play() failed', error);
        });
      }
      logPeerState(pc);
    };

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        console.log('ICE candidate generated');
        console.log('[WebRTC] Emitting ICE candidate', {
          receiverId: Number(targetUserId),
          callId: callIdRef.current,
          candidateType: event.candidate.type,
          protocol: event.candidate.protocol
        });
        socket?.emit('ice-candidate', {
          receiverId: Number(targetUserId),
          callId: callIdRef.current,
          candidate: event.candidate
        });
      }
    };
    peer.current = pc;
    logPeerState(pc);
    return pc;
  }

  async function handleCallAccepted({ answer, callId: nextCallId }) {
    console.log('Received answer');
    callIdRef.current = nextCallId;
    setCallId(nextCallId);

    if (!peer.current) {
      console.log('[WebRTC] Cannot apply answer because peer connection is missing');
      return;
    }

    await peer.current.setRemoteDescription(answer);
    await flushPendingIceCandidates(peer.current);
    logPeerState(peer.current);
    setStatus('Connected');
  }

  async function handleAnswer({ answer }) {
    console.log('Received answer');
    if (!peer.current) {
      console.log('[WebRTC] Cannot apply generic answer because peer connection is missing');
      return;
    }

    await peer.current.setRemoteDescription(answer);
    await flushPendingIceCandidates(peer.current);
    logPeerState(peer.current);
    setStatus('Connected');
  }

  async function handleIceCandidate({ candidate }) {
    if (candidate) await addIceCandidateSafely(candidate);
  }

  async function startCall() {
    if (!receiverId) return;
    setSeconds(0);
    setStatus('Calling');
    pendingIceCandidates.current = [];
    const pc = await createPeer(receiverId, 'startCall -> createPeer -> ensureMedia');
    console.log('Creating offer');
    const offer = await pc.createOffer();
    console.log('Offer created');
    await pc.setLocalDescription(offer);
    logPeerState(pc);
    console.log('[WebRTC] Emitting incoming-call with offer', { receiverId: Number(receiverId) });
    socket.emit('incoming-call', { receiverId: Number(receiverId), offer }, (ack) => {
      console.log('[WebRTC] incoming-call ack', ack);
      if (ack?.callId) {
        callIdRef.current = ack.callId;
        setCallId(ack.callId);
      }
    });
  }

  async function handleIncomingCall({ callerId, callId: nextCallId, offer }) {
    console.log('Received offer');
    console.log('[WebRTC] Incoming call payload', { callerId, callId: nextCallId, hasOffer: Boolean(offer) });
    setReceiverId(String(callerId));
    callIdRef.current = nextCallId;
    setCallId(nextCallId);
    setSeconds(0);
    setStatus('Incoming');
    pendingIceCandidates.current = [];
    const accepted = window.confirm('Accept incoming video call?');
    if (!accepted) {
      socket.emit('call-rejected', { callerId, callId: nextCallId });
      return setStatus('Rejected');
    }
    const pc = await createPeer(callerId, 'handleIncomingCall accepted -> createPeer -> ensureMedia');
    await pc.setRemoteDescription(offer);
    await flushPendingIceCandidates(pc);
    logPeerState(pc);
    console.log('Creating answer');
    const answer = await pc.createAnswer();
    console.log('Answer created');
    await pc.setLocalDescription(answer);
    logPeerState(pc);
    console.log('[WebRTC] Emitting call-accepted with answer', { callerId, callId: nextCallId });
    socket.emit('call-accepted', { callerId, callId: nextCallId, answer });
    setStatus('Connected');
  }

  function toggleAudio() {
    localStream.current?.getAudioTracks().forEach((track) => (track.enabled = !audioOn));
    setAudioOn(!audioOn);
  }

  function toggleVideo() {
    localStream.current?.getVideoTracks().forEach((track) => (track.enabled = !videoOn));
    setVideoOn(!videoOn);
  }

  function endLocalCall() {
    peer.current?.close();
    peer.current = null;
    mediaRequest.current = null;
    detectionAbort.current?.abort();
    localStream.current?.getTracks().forEach((track) => track.stop());
    localStream.current = null;
    if (localVideo.current) localVideo.current.srcObject = null;
    if (remoteVideo.current) remoteVideo.current.srcObject = null;
    landmarkOverlay.current?.clear();
    landmarkOverlay.current?.setStatus('Landmark service idle');
    setMediaReady(false);
    setStatus('Ended');
  }

  function endCall() {
    if (receiverId) socket?.emit('call-ended', { receiverId: Number(receiverId), callId });
    endLocalCall();
  }

  return (
    <section className="call-page">
      <div className="call-toolbar">
        <label className="field compact">
          <span>Receiver ID</span>
          <input value={receiverId} onChange={(e) => setReceiverId(e.target.value)} />
        </label>
        <div className="call-status">{status} · {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}</div>
        <button className="primary-button" onClick={startCall}><Video size={18} />{t('startCall')}</button>
      </div>
      <div className="video-grid">
        <video ref={remoteVideo} autoPlay playsInline className="remote-video" aria-label="Remote participant video" />
        <video ref={localVideo} autoPlay muted playsInline className="local-video" aria-label="Your camera preview" />
        <LandmarkOverlay ref={landmarkOverlay} />
        <canvas ref={captureCanvas} className="hidden-canvas" />
      </div>
      <div className="call-controls">
        <button className="icon-button" onClick={toggleAudio} aria-label="Toggle audio">{audioOn ? <Mic /> : <MicOff />}</button>
        <button className="icon-button" onClick={toggleVideo} aria-label="Toggle video">{videoOn ? <Video /> : <VideoOff />}</button>
        <button className="danger-button" onClick={endCall}><PhoneOff size={18} />{t('end')}</button>
        <button className="icon-button" onClick={() => remoteVideo.current?.requestFullscreen()} aria-label="Fullscreen"><Maximize /></button>
      </div>
    </section>
  );
}
