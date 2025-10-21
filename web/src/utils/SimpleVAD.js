// Simple JavaScript VAD using Web Audio API
// Works with COEP/COOP headers, no WASM required

export class SimpleVAD {
  constructor(options = {}) {
    this.onSpeechStart = options.onSpeechStart || (() => {});
    this.onSpeechEnd = options.onSpeechEnd || (() => {});
    this.onVADMisfire = options.onVADMisfire || (() => {});

    // Tunable parameters
    this.energyThreshold = options.energyThreshold || 0.002;
    this.minSpeechFrames = options.minSpeechFrames || 5;
    this.minSilenceFrames = options.minSilenceFrames || 20;
    this.frameSize = 512;

    this.isSpeaking = false;
    this.speechFrames = 0;
    this.silenceFrames = 0;
    this.audioBuffer = [];
    this.stream = null;
    this.audioContext = null;
    this.analyser = null;
    this.processor = null;
    this.source = null;
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: 16000,
        echoCancellation: true,
        noiseSuppression: true
      }
    });

    this.audioContext = new AudioContext({ sampleRate: 16000 });
    this.source = this.audioContext.createMediaStreamSource(this.stream);
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 2048;
    this.analyser.smoothingTimeConstant = 0.8;

    this.processor = this.audioContext.createScriptProcessor(this.frameSize, 1, 1);

    this.source.connect(this.analyser);
    this.analyser.connect(this.processor);
    this.processor.connect(this.audioContext.destination);

    this.processor.onaudioprocess = (e) => this.processAudio(e);
  }

  processAudio(e) {
    const inputData = e.inputBuffer.getChannelData(0);

    // Calculate energy
    let energy = 0;
    for (let i = 0; i < inputData.length; i++) {
      energy += inputData[i] * inputData[i];
    }
    energy = Math.sqrt(energy / inputData.length);

    const isSpeech = energy > this.energyThreshold;

    if (isSpeech) {
      this.speechFrames++;
      this.silenceFrames = 0;

      // Collect audio
      this.audioBuffer.push(new Float32Array(inputData));

      // Start speech if threshold reached
      if (!this.isSpeaking && this.speechFrames >= this.minSpeechFrames) {
        this.isSpeaking = true;
        this.onSpeechStart();
      }
    } else {
      this.silenceFrames++;

      if (this.isSpeaking) {
        this.audioBuffer.push(new Float32Array(inputData));

        // End speech if silence threshold reached
        if (this.silenceFrames >= this.minSilenceFrames) {
          this.isSpeaking = false;
          this.speechFrames = 0;

          // Concatenate audio buffer
          const totalLength = this.audioBuffer.reduce((sum, arr) => sum + arr.length, 0);
          const combined = new Float32Array(totalLength);
          let offset = 0;
          for (const chunk of this.audioBuffer) {
            combined.set(chunk, offset);
            offset += chunk.length;
          }

          if (combined.length > this.frameSize * this.minSpeechFrames) {
            this.onSpeechEnd(combined);
          } else {
            this.onVADMisfire();
          }

          this.audioBuffer = [];
        }
      } else {
        this.speechFrames = Math.max(0, this.speechFrames - 1);
      }
    }
  }

  pause() {
    if (this.processor) {
      this.processor.disconnect();
    }
    if (this.source) {
      this.source.disconnect();
    }
    if (this.analyser) {
      this.analyser.disconnect();
    }
    if (this.audioContext) {
      this.audioContext.close();
    }
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
    }
  }
}
