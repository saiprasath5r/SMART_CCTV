/**
 * Camera Stream, WebRTC Capture & Canvas HUD Bounding Box Renderer
 */
class CameraHUDController {
  constructor(videoElementId, canvasElementId) {
    this.video = document.getElementById(videoElementId);
    this.canvas = document.getElementById(canvasElementId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;

    this.stream = null;
    this.isStreaming = false;
    this.useSyntheticFeed = false;
    this.trackedPersons = [];
    this.fps = 0;

    this.onFrameReady = null; // WebSocket sender callback
    this.animationFrameId = null;
    this.lastFrameSendTime = 0;
    this.sendIntervalMs = 70; // ~14 FPS frame transmission to backend for optimal real-time AI throughput
  }

  async startWebcam(deviceId = null) {
    try {
      if (this.stream) {
        this.stream.getTracks().forEach(track => track.stop());
      }

      const constraints = {
        video: deviceId ? { deviceId: { exact: deviceId }, width: 1280, height: 720 } : { width: 1280, height: 720 }
      };

      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
      this.video.srcObject = this.stream;
      await this.video.play();
      this.isStreaming = true;
      this.useSyntheticFeed = false;

      this._resizeCanvas();
      this._startRenderLoop();
      return true;
    } catch (err) {
      console.warn("Could not access physical webcam:", err.message);
      console.log("Switching to High-Fidelity Synthetic CCTV Security Feed simulation.");
      this.startSyntheticFeed();
      return false;
    }
  }

  startSyntheticFeed() {
    this.isStreaming = true;
    this.useSyntheticFeed = true;
    this._resizeCanvas();
    this._startRenderLoop();
  }

  stopStream() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
    this.isStreaming = false;
  }

  _resizeCanvas() {
    if (!this.canvas) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = 1280;
    this.canvas.height = 720;
  }

  updateTrackedPersons(persons, fps = 0) {
    this.trackedPersons = persons || [];
    this.fps = fps;
  }

  _startRenderLoop() {
    const loop = (timestamp) => {
      if (!this.isStreaming) return;

      this._render();

      // Send frame over WebSocket if interval elapsed
      if (timestamp - this.lastFrameSendTime >= this.sendIntervalMs) {
        this.lastFrameSendTime = timestamp;
        this._captureAndSendFrame();
      }

      this.animationFrameId = requestAnimationFrame(loop);
    };
    this.animationFrameId = requestAnimationFrame(loop);
  }

  _captureAndSendFrame() {
    if (!this.onFrameReady || !this.ctx) return;

    try {
      // Create off-screen canvas for high-performance frame extraction
      const offscreen = document.createElement('canvas');
      offscreen.width = 640;
      offscreen.height = 360;
      const offCtx = offscreen.getContext('2d');

      if (this.useSyntheticFeed) {
        // Draw synthetic frame
        offCtx.drawImage(this.canvas, 0, 0, 640, 360);
      } else if (this.video && this.video.readyState >= 2) {
        offCtx.drawImage(this.video, 0, 0, 640, 360);
      } else {
        return;
      }

      const base64Data = offscreen.toDataURL('image/jpeg', 0.65);
      this.onFrameReady(base64Data);
    } catch (e) {
      console.warn("Frame capture error:", e);
    }
  }

  _render() {
    if (!this.ctx || !this.canvas) return;
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;

    // Clear canvas
    ctx.clearRect(0, 0, w, h);

    // 1. Draw video background
    if (!this.useSyntheticFeed && this.video && this.video.readyState >= 2) {
      ctx.drawImage(this.video, 0, 0, w, h);
    } else {
      // Synthetic Security Camera Feed Simulation
      this._renderSyntheticCCTV(ctx, w, h);
    }

    // 2. Draw Surveillance HUD Grid & Watermark
    this._renderHUDOverlay(ctx, w, h);

    // 3. Draw Tracked Faces & Bounding Boxes
    this._renderBoundingBoxes(ctx, w, h);
  }

  _renderSyntheticCCTV(ctx, w, h) {
    // Dark CCTV gradient room backdrop
    const grad = ctx.createLinearGradient(0, 0, w, h);
    grad.addColorStop(0, '#0a101d');
    grad.addColorStop(1, '#04070c');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);

    // Facility Architecture Perspective Lines
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.08)';
    ctx.lineWidth = 1;

    // Floor perspective grid
    ctx.beginPath();
    for (let x = 0; x <= w; x += 80) {
      ctx.moveTo(x, h);
      ctx.lineTo(w / 2 + (x - w / 2) * 0.3, h * 0.45);
    }
    for (let y = h * 0.45; y <= h; y += 40) {
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
    }
    ctx.stroke();

    // Security Gate Corridor
    ctx.strokeStyle = 'rgba(0, 255, 157, 0.15)';
    ctx.strokeRect(w * 0.35, h * 0.3, w * 0.3, h * 0.55);

    // Animated Simulated Visitor
    const t = Date.now() / 1000;
    const visitorX = w * 0.45 + Math.sin(t * 0.5) * 60;
    const visitorY = h * 0.38 + Math.cos(t * 0.3) * 15;

    // Draw Simulated Person Body & Head
    ctx.fillStyle = '#1e293b';
    ctx.beginPath();
    ctx.ellipse(visitorX + 45, visitorY + 120, 50, 70, 0, 0, Math.PI * 2);
    ctx.fill();

    // Head
    ctx.fillStyle = '#d4a373';
    ctx.beginPath();
    ctx.ellipse(visitorX + 45, visitorY + 45, 32, 40, 0, 0, Math.PI * 2);
    ctx.fill();

    // Eyes
    ctx.fillStyle = '#1e1b18';
    ctx.beginPath();
    ctx.arc(visitorX + 35, visitorY + 42, 3, 0, Math.PI * 2);
    ctx.arc(visitorX + 55, visitorY + 42, 3, 0, Math.PI * 2);
    ctx.fill();

    // Hair
    ctx.fillStyle = '#2c1810';
    ctx.beginPath();
    ctx.arc(visitorX + 45, visitorY + 30, 32, Math.PI, Math.PI * 2);
    ctx.fill();
  }

  _renderHUDOverlay(ctx, w, h) {
    // Scanline effect
    ctx.fillStyle = 'rgba(0, 0, 0, 0.12)';
    for (let y = 0; y < h; y += 4) {
      ctx.fillRect(0, y, w, 1);
    }

    // Top Right Telemetry & Timestamp
    const now = new Date();
    const timeStr = now.toISOString().replace('T', ' ').substr(0, 19);
    
    ctx.font = '13px "JetBrains Mono", monospace';
    ctx.fillStyle = 'rgba(0, 240, 255, 0.85)';
    ctx.textAlign = 'right';
    ctx.fillText(`CAM-01 [ZONE-A] | ${timeStr} | FPS: ${this.fps || 24}`, w - 24, 30);

    // Bottom Left Sector Coordinates
    ctx.textAlign = 'left';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.fillText('TARGET ACQUISITION: ACTIVE | AI INFERENCE: ONLINE', 24, h - 20);
  }

  _renderBoundingBoxes(ctx, w, h) {
    // Coordinate scale factors (Frame was 640x360, Canvas is 1280x720)
    const scaleX = w / 640;
    const scaleY = h / 360;

    for (const person of this.trackedPersons) {
      const [bx, by, bw, bh] = person.bbox;
      const x = bx * scaleX;
      const y = by * scaleY;
      const width = bw * scaleX;
      const height = bh * scaleY;

      const isAlert = person.is_loitering || person.threat_level === 'HIGH';
      const mainColor = isAlert ? '#ff0055' : '#00f0ff';
      const glowColor = isAlert ? 'rgba(255, 0, 85, 0.5)' : 'rgba(0, 240, 255, 0.4)';

      // 1. Glowing Bounding Box
      ctx.save();
      ctx.strokeStyle = mainColor;
      ctx.lineWidth = 2.5;
      ctx.shadowColor = glowColor;
      ctx.shadowBlur = isAlert ? 18 : 10;
      
      // Draw Box Corners (Cyberpunk Target Reticle)
      const cornerLen = Math.min(20, width * 0.25);
      
      ctx.beginPath();
      // Top Left
      ctx.moveTo(x, y + cornerLen);
      ctx.lineTo(x, y);
      ctx.lineTo(x + cornerLen, y);
      // Top Right
      ctx.moveTo(x + width - cornerLen, y);
      ctx.lineTo(x + width, y);
      ctx.lineTo(x + width, y + cornerLen);
      // Bottom Right
      ctx.moveTo(x + width, y + height - cornerLen);
      ctx.lineTo(x + width, y + height);
      ctx.lineTo(x + width - cornerLen, y + height);
      // Bottom Left
      ctx.moveTo(x + cornerLen, y + height);
      ctx.lineTo(x, y + height);
      ctx.lineTo(x, y + height - cornerLen);
      ctx.stroke();

      // Semi-transparent box border
      ctx.strokeStyle = isAlert ? 'rgba(255, 0, 85, 0.3)' : 'rgba(0, 240, 255, 0.25)';
      ctx.lineWidth = 1;
      ctx.strokeRect(x, y, width, height);

      // 2. Center Crosshair
      const cx = x + width / 2;
      const cy = y + height / 2;
      ctx.beginPath();
      ctx.moveTo(cx - 6, cy); ctx.lineTo(cx + 6, cy);
      ctx.moveTo(cx, cy - 6); ctx.lineTo(cx, cy + 6);
      ctx.strokeStyle = mainColor;
      ctx.stroke();

      // 3. Demographic & Status Header Badge above Face
      const badgeText = `${person.visitor_id} | ${person.gender} ${Math.round(person.gender_confidence * 100)}%`;
      const locationText = `📍 ${person.location || 'Sector A - Main Entrance'}`;
      const timerText = `⏱️ ${person.dwell_time}s ${isAlert ? '⚠️ LOITERING' : ''}`;
      
      ctx.font = 'bold 12px "JetBrains Mono", monospace';
      const textWidth = Math.max(
        ctx.measureText(badgeText).width, 
        ctx.measureText(locationText).width,
        ctx.measureText(timerText).width
      ) + 16;
      const badgeHeight = 50;
      const badgeY = Math.max(10, y - badgeHeight - 6);

      // Badge Background
      ctx.fillStyle = isAlert ? 'rgba(255, 0, 85, 0.88)' : 'rgba(10, 18, 30, 0.9)';
      ctx.strokeStyle = mainColor;
      ctx.lineWidth = 1;
      ctx.fillRect(x, badgeY, textWidth, badgeHeight);
      ctx.strokeRect(x, badgeY, textWidth, badgeHeight);

      // Badge Text
      ctx.fillStyle = isAlert ? '#ffffff' : '#00f0ff';
      ctx.fillText(badgeText, x + 8, badgeY + 14);

      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.fillStyle = isAlert ? '#ffe6ef' : '#ffb800';
      ctx.fillText(locationText, x + 8, badgeY + 28);
      
      ctx.font = '11px "JetBrains Mono", monospace';
      ctx.fillStyle = isAlert ? '#ffe6ef' : '#00ff9d';
      ctx.fillText(timerText, x + 8, badgeY + 42);

      ctx.restore();
    }
  }
}

window.CameraHUDController = CameraHUDController;
