/**
 * CCTV Surveillance & Security AI - Main Dashboard Application Controller
 */

class SurveillanceDashboardApp {
  constructor() {
    this.ws = null;
    this.cameraHUD = null;
    this.isReconnecting = false;
    this.activeAlertTimeout = null;

    // Elements
    this.elements = {
      // Metrics
      occupantsCount: document.getElementById('occupantsCount'),
      maleCount: document.getElementById('maleCount'),
      femaleCount: document.getElementById('femaleCount'),
      avgDwellTime: document.getElementById('avgDwellTime'),
      alertsCount: document.getElementById('alertsCount'),
      systemClock: document.getElementById('systemClock'),
      systemStatusDot: document.getElementById('systemStatusDot'),
      systemStatusText: document.getElementById('systemStatusText'),

      // Alert Banner
      alertBanner: document.getElementById('alertBanner'),
      alertBannerMsg: document.getElementById('alertBannerMsg'),
      dismissAlertBtn: document.getElementById('dismissAlertBtn'),

      // Voice Agent
      sentinelOrb: document.getElementById('sentinelOrb'),
      sentinelStateText: document.getElementById('sentinelStateText'),
      dialogueStream: document.getElementById('dialogueStream'),
      inquiryTextInput: document.getElementById('inquiryTextInput'),
      sendInquiryBtn: document.getElementById('sendInquiryBtn'),
      micToggleBtn: document.getElementById('micToggleBtn'),

      // Tables & Feeds
      visitorTableBody: document.getElementById('visitorTableBody'),
      alertsTimeline: document.getElementById('alertsTimeline'),
      exportCsvBtn: document.getElementById('exportCsvBtn'),

      // Camera Controls
      cameraSelect: document.getElementById('cameraSelect'),
      startCameraBtn: document.getElementById('startCameraBtn'),
      panicBtn: document.getElementById('panicBtn'),
      muteAudioBtn: document.getElementById('muteAudioBtn'),

      // Settings Modal
      settingsBtn: document.getElementById('settingsBtn'),
      settingsModal: document.getElementById('settingsModal'),
      closeSettingsBtn: document.getElementById('closeSettingsBtn'),
      saveSettingsBtn: document.getElementById('saveSettingsBtn'),
      geminiKeyInput: document.getElementById('geminiKeyInput'),
      twilioSidInput: document.getElementById('twilioSidInput'),
      twilioTokenInput: document.getElementById('twilioTokenInput'),
      twilioFromInput: document.getElementById('twilioFromInput'),
      twilioToInput: document.getElementById('twilioToInput'),
      loiterThresholdInput: document.getElementById('loiterThresholdInput')
    };

    this.init();
  }

  async init() {
    this._startClock();
    this._initCameraAndHUD();
    this._initVoiceAgent();
    this._initWebSocket();
    this._bindEvents();
    this._populateCameraList();
    this.refreshVisitorLogs();
    this.refreshStats();

    // Periodic automatic database stats & visitor register refresh
    setInterval(() => {
      this.refreshStats();
      this.refreshVisitorLogs();
    }, 2000);
  }

  _startClock() {
    const update = () => {
      const now = new Date();
      if (this.elements.systemClock) {
        this.elements.systemClock.innerText = now.toTimeString().split(' ')[0] + ' UTC';
      }
    };
    update();
    setInterval(update, 1000);
  }

  _initCameraAndHUD() {
    this.cameraHUD = new window.CameraHUDController('cameraVideo', 'overlayCanvas');
    
    // Wire up frame sending callback
    this.cameraHUD.onFrameReady = (base64Frame) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({
          type: 'frame',
          frame: base64Frame
        }));
      }
    };

    // Auto-start camera or simulation
    this.cameraHUD.startWebcam();
  }

  _initVoiceAgent() {
    // State change callback
    window.voiceAgent.onStateChange = (state) => {
      if (!this.elements.sentinelOrb || !this.elements.sentinelStateText) return;

      this.elements.sentinelOrb.className = 'sentinel-orb';
      if (state === 'speaking') {
        this.elements.sentinelOrb.classList.add('speaking');
        this.elements.sentinelStateText.innerText = 'Vocalizing Safety Response...';
      } else if (state === 'listening') {
        this.elements.sentinelOrb.classList.add('listening');
        this.elements.sentinelStateText.innerText = 'Listening for Visitor Voice...';
        if (this.elements.micToggleBtn) this.elements.micToggleBtn.classList.add('recording');
      } else {
        this.elements.sentinelStateText.innerText = 'AI Sentinel Monitoring • Standby';
        if (this.elements.micToggleBtn) this.elements.micToggleBtn.classList.remove('recording');
      }
    };

    // Dialogue message callback
    window.voiceAgent.onDialogueMessage = (sender, text, visitorId, threat = 'LOW') => {
      this._appendDialogueMessage(sender, text, visitorId, threat);
    };
  }

  _initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/stream`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log("[WebSocket] Connected to Surveillance AI Server.");
      this._setSystemStatus('ONLINE', 'active');
      this.isReconnecting = false;
    };

    this.ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'detection_result') {
          this._handleDetectionResult(payload);
        }
      } catch (err) {
        console.warn("[WebSocket] Error processing message:", err);
      }
    };

    this.ws.onclose = () => {
      console.warn("[WebSocket] Connection lost. Attempting reconnect in 2s...");
      this._setSystemStatus('RECONNECTING', 'warning');
      if (!this.isReconnecting) {
        this.isReconnecting = true;
        setTimeout(() => this._initWebSocket(), 2000);
      }
    };

    this.ws.onerror = (err) => {
      console.error("[WebSocket] Error:", err);
      this._setSystemStatus('ERROR', 'danger');
    };
  }

  _setSystemStatus(text, dotClass) {
    if (this.elements.systemStatusText) this.elements.systemStatusText.innerText = text;
    if (this.elements.systemStatusDot) {
      this.elements.systemStatusDot.className = `status-dot ${dotClass}`;
    }
  }

  _handleDetectionResult(data) {
    // 1. Update Metrics
    if (this.elements.occupantsCount) this.elements.occupantsCount.innerText = data.occupants;
    if (this.elements.maleCount) this.elements.maleCount.innerText = data.males;
    if (this.elements.femaleCount) this.elements.femaleCount.innerText = data.females;

    // 2. Update Canvas Bounding Boxes & HUD
    this.cameraHUD.updateTrackedPersons(data.tracked_persons, data.fps);

    // Track active target for AI agent
    if (data.tracked_persons && data.tracked_persons.length > 0) {
      const activePerson = data.tracked_persons[0];
      window.CURRENT_ACTIVE_GENDER = activePerson.gender;
      window.CURRENT_ACTIVE_LOCATION = activePerson.location;
      window.CURRENT_DWELL_TIME = activePerson.dwell_time;
      window.IS_CURRENT_LOITERING = activePerson.is_loitering;
    }

    // 3. Check for New Visitors -> Trigger Web Speech Voice Greeting
    if (data.new_visitors && data.new_visitors.length > 0) {
      const firstNew = data.new_visitors[0];
      window.audioAlarm.playBeep(880, 'sine', 0.15);
      window.voiceAgent.triggerWelcomePrompt(firstNew.visitor_id);
      this.refreshVisitorLogs();
    }

    // 4. Check for Loitering Anomalies -> Trigger Red Alert Banner & Audio Siren
    if (data.loitering_alerts && data.loitering_alerts.length > 0) {
      for (const alert of data.loitering_alerts) {
        this.triggerRedAlertBanner(alert.message);
        window.audioAlarm.playSiren(4.0);
        this._addAlertTimelineEntry(alert.message, 'LOITERING');
      }
      this.refreshVisitorLogs();
      this.refreshStats();
    }
  }

  triggerRedAlertBanner(message) {
    if (!this.elements.alertBanner) return;
    this.elements.alertBannerMsg.innerText = message;
    this.elements.alertBanner.classList.add('active');

    if (this.activeAlertTimeout) clearTimeout(this.activeAlertTimeout);
    this.activeAlertTimeout = setTimeout(() => {
      this.elements.alertBanner.classList.remove('active');
    }, 12000);
  }

  _appendDialogueMessage(sender, text, visitorId, threat = 'LOW') {
    if (!this.elements.dialogueStream) return;

    const msgDiv = document.createElement('div');
    msgDiv.className = `msg-bubble ${sender}`;

    const headerDiv = document.createElement('div');
    headerDiv.className = 'msg-header';
    headerDiv.innerHTML = `
      <span>${sender === 'ai' ? 'SMART CCTV SENTINEL' : `${visitorId}`}</span>
      <span>${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
    `;

    const bodyDiv = document.createElement('div');
    bodyDiv.className = 'msg-body';
    bodyDiv.innerText = text;

    msgDiv.appendChild(headerDiv);
    msgDiv.appendChild(bodyDiv);

    if (threat === 'HIGH') {
      const threatTag = document.createElement('span');
      threatTag.className = 'badge badge-high';
      threatTag.style.marginTop = '6px';
      threatTag.innerText = 'HIGH THREAT DETECTED';
      msgDiv.appendChild(threatTag);
    }

    this.elements.dialogueStream.appendChild(msgDiv);
    this.elements.dialogueStream.scrollTop = this.elements.dialogueStream.scrollHeight;
  }

  _addAlertTimelineEntry(message, type = 'SECURITY') {
    if (!this.elements.alertsTimeline) return;

    const entry = document.createElement('div');
    entry.className = `alert-entry ${type === 'LOITERING' ? 'warning' : ''}`;
    entry.innerHTML = `
      <span class="alert-entry-time">${new Date().toLocaleTimeString()}</span>
      <span class="alert-entry-msg">${message}</span>
    `;

    this.elements.alertsTimeline.prepend(entry);
  }

  async refreshStats() {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      if (data.status === 'success') {
        const s = data.data;
        if (this.elements.avgDwellTime) this.elements.avgDwellTime.innerText = s.avg_dwell_time;
        if (this.elements.alertsCount) this.elements.alertsCount.innerText = s.total_alerts;
      }
    } catch (e) {
      console.warn("Error loading stats:", e);
    }
  }

  async refreshVisitorLogs() {
    try {
      const res = await fetch('/api/visitors?limit=25');
      const data = await res.json();
      if (data.status === 'success' && this.elements.visitorTableBody) {
        this.elements.visitorTableBody.innerHTML = '';

        for (const v of data.data) {
          const row = document.createElement('tr');
          const genderBadgeClass = v.gender === 'Male' ? 'badge-male' : (v.gender === 'Female' ? 'badge-female' : 'badge-safe');
          const loiterBadge = v.is_loitering ? '<span class="badge badge-loiter">LOITERING</span>' : '<span class="badge badge-safe">NORMAL</span>';
          const snapshotImg = v.snapshot_path 
            ? `<img src="${v.snapshot_path}" class="snapshot-thumb" alt="Face" onerror="this.src='/static/img/face_placeholder.svg'"/>`
            : `<div class="snapshot-thumb" style="display:flex;align-items:center;justify-content:center;color:#666;font-size:10px;">NO IMG</div>`;

          row.innerHTML = `
            <td>${snapshotImg}</td>
            <td><strong>${v.visitor_id}</strong><br><span style="font-size:11px;color:#94a3b8">${v.visitor_name || 'Anonymous'}</span></td>
            <td><span class="badge ${genderBadgeClass}">${v.gender} (${Math.round(v.gender_confidence * 100)}%)</span></td>
            <td><span class="badge" style="background:rgba(255,184,0,0.12);color:#ffb800;border:1px solid rgba(255,184,0,0.3)">📍 ${v.location || 'Sector A - Main Entrance'}</span></td>
            <td>${Math.round(v.duration_seconds)}s</td>
            <td>${loiterBadge}</td>
            <td>${v.purpose_of_visit || 'Unstated'}</td>
            <td><span class="badge ${v.threat_level === 'HIGH' ? 'badge-high' : 'badge-safe'}">${v.threat_level}</span></td>
          `;
          this.elements.visitorTableBody.appendChild(row);
        }
      }
    } catch (e) {
      console.warn("Error refreshing visitor logs:", e);
    }
  }

  async _populateCameraList() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = devices.filter(d => d.kind === 'videoinput');

      if (this.elements.cameraSelect) {
        this.elements.cameraSelect.innerHTML = '';
        
        videoDevices.forEach((dev, idx) => {
          const opt = document.createElement('option');
          opt.value = dev.deviceId;
          opt.innerText = dev.label || `Camera ${idx + 1}`;
          this.elements.cameraSelect.appendChild(opt);
        });

        const simOpt = document.createElement('option');
        simOpt.value = 'synthetic';
        simOpt.innerText = 'Simulation: High-Fidelity CCTV Test Feed';
        this.elements.cameraSelect.appendChild(simOpt);
      }
    } catch (e) {
      console.warn("Could not enumerate devices:", e);
    }
  }

  _bindEvents() {
    // 1. Text Inquiry Submit
    const handleSendInquiry = () => {
      const input = this.elements.inquiryTextInput;
      if (input && input.value.trim()) {
        const text = input.value.trim();
        input.value = '';
        window.voiceAgent.handleUserStatement(text);
      }
    };

    if (this.elements.sendInquiryBtn) {
      this.elements.sendInquiryBtn.addEventListener('click', handleSendInquiry);
    }
    if (this.elements.inquiryTextInput) {
      this.elements.inquiryTextInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSendInquiry();
      });
    }

    // 2. Microphone Voice Toggle
    if (this.elements.micToggleBtn) {
      this.elements.micToggleBtn.addEventListener('click', () => {
        window.voiceAgent.toggleListening();
      });
    }

    // 3. Panic / Manual Alert Button
    if (this.elements.panicBtn) {
      this.elements.panicBtn.addEventListener('click', async () => {
        window.audioAlarm.playSiren(5.0);
        this.triggerRedAlertBanner("EMERGENCY: MANUAL SECURITY PANIC BUTTON TRIGGERED BY OPERATOR!");
        
        try {
          await fetch('/api/alerts/trigger', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              visitor_id: "OPERATOR_ALERT",
              alert_type: "MANUAL_PANIC",
              message: "EMERGENCY PANIC ALERT triggered from Dashboard."
            })
          });
          this.refreshStats();
        } catch (e) {
          console.error("Error triggering panic alert:", e);
        }
      });
    }

    // 4. Mute Audio Button
    if (this.elements.muteAudioBtn) {
      this.elements.muteAudioBtn.addEventListener('click', () => {
        const isMuted = window.audioAlarm.toggleMute();
        this.elements.muteAudioBtn.innerText = isMuted ? '🔇 Audio Muted' : '🔊 Audio Alarm ON';
      });
    }

    // 5. Dismiss Alert Banner
    if (this.elements.dismissAlertBtn) {
      this.elements.dismissAlertBtn.addEventListener('click', () => {
        if (this.elements.alertBanner) this.elements.alertBanner.classList.remove('active');
        window.audioAlarm.stopSiren();
      });
    }

    // 6. Camera Switcher
    if (this.elements.cameraSelect) {
      this.elements.cameraSelect.addEventListener('change', (e) => {
        const val = e.target.value;
        if (val === 'synthetic') {
          this.cameraHUD.startSyntheticFeed();
        } else {
          this.cameraHUD.startWebcam(val);
        }
      });
    }

    // 7. CSV Export Download
    if (this.elements.exportCsvBtn) {
      this.elements.exportCsvBtn.addEventListener('click', () => {
        window.location.href = '/api/logs/export.csv';
      });
    }

    // 8. Settings Modal
    if (this.elements.settingsBtn && this.elements.settingsModal) {
      this.elements.settingsBtn.addEventListener('click', async () => {
        this.elements.settingsModal.classList.add('open');
        try {
          const res = await fetch('/api/config');
          const cfg = await res.json();
          if (this.elements.loiterThresholdInput) this.elements.loiterThresholdInput.value = cfg.loiter_threshold_seconds || 15;
          if (this.elements.twilioFromInput) this.elements.twilioFromInput.value = cfg.twilio_from_number || '';
          if (this.elements.twilioToInput) this.elements.twilioToInput.value = cfg.twilio_to_number || '';
        } catch (e) {}
      });
    }

    if (this.elements.closeSettingsBtn && this.elements.settingsModal) {
      this.elements.closeSettingsBtn.addEventListener('click', () => {
        this.elements.settingsModal.classList.remove('open');
      });
    }

    if (this.elements.saveSettingsBtn) {
      this.elements.saveSettingsBtn.addEventListener('click', async () => {
        const payload = {};
        if (this.elements.geminiKeyInput && this.elements.geminiKeyInput.value.trim()) {
          payload.gemini_api_key = this.elements.geminiKeyInput.value.trim();
        }
        if (this.elements.twilioSidInput && this.elements.twilioSidInput.value.trim()) {
          payload.twilio_account_sid = this.elements.twilioSidInput.value.trim();
        }
        if (this.elements.twilioTokenInput && this.elements.twilioTokenInput.value.trim()) {
          payload.twilio_auth_token = this.elements.twilioTokenInput.value.trim();
        }
        if (this.elements.twilioFromInput) {
          payload.twilio_from_number = this.elements.twilioFromInput.value.trim();
        }
        if (this.elements.twilioToInput) {
          payload.twilio_to_number = this.elements.twilioToInput.value.trim();
        }
        if (this.elements.loiterThresholdInput) {
          payload.loitering_threshold_seconds = parseInt(this.elements.loiterThresholdInput.value) || 15;
        }

        try {
          const res = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          const result = await res.json();
          alert(result.message || "Settings updated!");
          if (this.elements.settingsModal) this.elements.settingsModal.classList.remove('open');
        } catch (e) {
          alert("Error saving settings: " + e.message);
        }
      });
    }
  }
}

// Global initialization on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.dashboardApp = new SurveillanceDashboardApp();
  window.refreshVisitorLogs = () => window.dashboardApp.refreshVisitorLogs();
});
