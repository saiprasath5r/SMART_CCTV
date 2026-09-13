/**
 * Web Speech API Orchestrator (SpeechSynthesis & SpeechRecognition)
 * Powers the interactive Safety AI Sentinel ("AEGIS")
 */
class VoiceAgentController {
  constructor() {
    this.synth = window.speechSynthesis || null;
    this.recognition = null;
    this.isListening = false;
    this.isSpeaking = false;
    this.activeVisitorId = "VISITOR-001";
    this.defaultVoice = null;

    this.onDialogueMessage = null; // Callback for UI updates
    this.onStateChange = null;     // Callback for orb animation states

    this._initSpeechRecognition();
    this._loadVoices();
  }

  _loadVoices() {
    if (!this.synth) return;
    const populate = () => {
      const voices = this.synth.getVoices();
      // Try to find natural authoritative sounding voice
      this.defaultVoice = voices.find(v => (v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha') || v.name.includes('David')))) || voices[0];
    };
    populate();
    if (this.synth.onvoiceschanged !== undefined) {
      this.synth.onvoiceschanged = populate;
    }
  }

  _initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      this.recognition = new SpeechRecognition();
      this.recognition.continuous = false;
      this.recognition.interimResults = true;
      this.recognition.lang = 'en-US';

      this.recognition.onstart = () => {
        this.isListening = true;
        if (this.onStateChange) this.onStateChange('listening');
      };

      this.recognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }

        const currentText = finalTranscript || interimTranscript;
        const inputElem = document.getElementById('inquiryTextInput');
        if (inputElem) inputElem.value = currentText;

        if (finalTranscript) {
          this.handleUserStatement(finalTranscript.trim());
        }
      };

      this.recognition.onerror = (event) => {
        console.warn("Speech recognition error:", event.error);
        this.isListening = false;
        if (this.onStateChange) this.onStateChange('idle');
      };

      this.recognition.onend = () => {
        this.isListening = false;
        if (this.onStateChange && !this.isSpeaking) this.onStateChange('idle');
      };
    } else {
      console.warn("Web SpeechRecognition is not supported in this browser environment. Manual text input will be active.");
    }
  }

  speak(text, onComplete = null) {
    if (!this.synth) {
      if (onComplete) onComplete();
      return;
    }

    // Cancel existing speech
    this.synth.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    if (this.defaultVoice) utterance.voice = this.defaultVoice;
    utterance.rate = 1.02;
    utterance.pitch = 0.98;

    utterance.onstart = () => {
      this.isSpeaking = true;
      if (this.onStateChange) this.onStateChange('speaking');
    };

    utterance.onend = () => {
      this.isSpeaking = false;
      if (this.onStateChange) this.onStateChange('idle');
      if (onComplete) onComplete();
    };

    utterance.onerror = (e) => {
      console.warn("Speech synthesis error:", e);
      this.isSpeaking = false;
      if (this.onStateChange) this.onStateChange('idle');
      if (onComplete) onComplete();
    };

    this.synth.speak(utterance);
  }

  triggerWelcomePrompt(visitorId = "VISITOR-001") {
    this.activeVisitorId = visitorId;
    const promptText = window.DEFAULT_SAFETY_PROMPT || "Welcome. For safety purposes, please state your name and purpose of visit.";
    
    // Log AI prompt to chat dialogue
    if (this.onDialogueMessage) {
      this.onDialogueMessage('ai', promptText, visitorId);
    }

    // Speak prompt, then automatically listen for visitor's voice response
    this.speak(promptText, () => {
      setTimeout(() => {
        this.startListening();
      }, 500);
    });
  }

  startListening() {
    if (!this.recognition || this.isListening) return;
    try {
      this.recognition.start();
    } catch (e) {
      console.warn("Error starting speech recognition:", e);
    }
  }

  stopListening() {
    if (!this.recognition || !this.isListening) return;
    try {
      this.recognition.stop();
    } catch (e) {}
    this.isListening = false;
    if (this.onStateChange) this.onStateChange('idle');
  }

  toggleListening() {
    if (this.isListening) {
      this.stopListening();
    } else {
      this.startListening();
    }
  }

  async handleUserStatement(statement) {
    if (!statement) return;
    
    // Log visitor's reply in UI
    if (this.onDialogueMessage) {
      this.onDialogueMessage('visitor', statement, this.activeVisitorId);
    }

    // Call Backend Interrogate Endpoint
    try {
      const response = await fetch('/api/agent/interrogate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          visitor_id: this.activeVisitorId,
          transcript: statement,
          gender: window.CURRENT_ACTIVE_GENDER || "Undetermined",
          location: window.CURRENT_ACTIVE_LOCATION || "Sector A - Main Entrance",
          dwell_time: window.CURRENT_DWELL_TIME || 0.0,
          is_loitering: window.IS_CURRENT_LOITERING || false
        })
      });

      const res = await response.json();
      if (res.status === 'success' && res.data) {
        const aiData = res.data;
        const reply = aiData.reply_speech || "Your details have been logged.";
        
        // Log AI reply in UI
        if (this.onDialogueMessage) {
          this.onDialogueMessage('ai', reply, this.activeVisitorId, aiData.threat_level);
        }

        // Speak AI response
        this.speak(reply);

        // Refresh visitor tables & stats
        if (window.refreshVisitorLogs) {
          window.refreshVisitorLogs();
        }
      }
    } catch (e) {
      console.error("Error communicating with AI Safety Agent:", e);
    }
  }
}

window.voiceAgent = new VoiceAgentController();
