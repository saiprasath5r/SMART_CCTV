/**
 * Web Audio API Synthesizer for Security Alarm Siren & HUD Audio Cues
 */
class AudioAlarmController {
  constructor() {
    this.ctx = null;
    this.isMuted = false;
    this.isPlayingSiren = false;
    this.sirenOsc = null;
  }

  _initContext() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  toggleMute() {
    this.isMuted = !this.isMuted;
    if (this.isMuted && this.isPlayingSiren) {
      this.stopSiren();
    }
    return this.isMuted;
  }

  playBeep(freq = 880, type = 'sine', duration = 0.12) {
    if (this.isMuted) return;
    try {
      this._initContext();
      if (!this.ctx) return;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);

      gain.gain.setValueAtTime(0.15, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch (e) {
      console.warn("Audio playBeep error:", e);
    }
  }

  playSiren(durationSeconds = 4.0) {
    if (this.isMuted || this.isPlayingSiren) return;
    try {
      this._initContext();
      if (!this.ctx) return;

      this.isPlayingSiren = true;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'sawtooth';
      gain.gain.setValueAtTime(0.2, this.ctx.currentTime);

      // Frequency modulation for police/facility emergency siren (650Hz <-> 950Hz)
      const now = this.ctx.currentTime;
      for (let i = 0; i < durationSeconds; i += 0.5) {
        osc.frequency.setValueAtTime(650, now + i);
        osc.frequency.linearRampToValueAtTime(950, now + i + 0.25);
        osc.frequency.linearRampToValueAtTime(650, now + i + 0.5);
      }

      gain.gain.setValueAtTime(0.25, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + durationSeconds);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start();
      osc.stop(now + durationSeconds);

      this.sirenOsc = osc;
      setTimeout(() => {
        this.isPlayingSiren = false;
      }, durationSeconds * 1000);
    } catch (e) {
      console.warn("Audio playSiren error:", e);
      this.isPlayingSiren = false;
    }
  }

  stopSiren() {
    if (this.sirenOsc) {
      try {
        this.sirenOsc.stop();
      } catch (e) {}
      this.sirenOsc = null;
    }
    this.isPlayingSiren = false;
  }
}

window.audioAlarm = new AudioAlarmController();
