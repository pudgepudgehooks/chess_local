/* Original, locally synthesized wooden piece-on-board tap. No external audio files. */
(function(root) {
  let context, impact;
  function play() {
    try {
      const AudioContext = root.AudioContext || root.webkitAudioContext;
      if (!AudioContext) return;
      if (!context || context.state === 'closed') {
        context = new AudioContext();
        impact = context.createBuffer(1, Math.ceil(context.sampleRate * 0.1), context.sampleRate);
        const samples = impact.getChannelData(0);
        const smoothing = 1 - Math.exp(-2 * Math.PI * 850 / context.sampleRate);
        let wood = 0;
        for (let i = 0; i < samples.length; i++) {
          const time = i / context.sampleRate;
          wood += smoothing * ((Math.random() * 2 - 1) - wood);
          const attack = Math.min(1, time / 0.0015);
          const body = 0.5 * Math.sin(2 * Math.PI * 190 * time) * Math.exp(-time * 90)
            + 0.18 * Math.sin(2 * Math.PI * 340 * time) * Math.exp(-time * 125);
          samples[i] = attack * (body + 0.75 * wood * Math.exp(-time * 100));
        }
      }
      const click = () => {
        if (context.state !== 'running') return;
        const now = context.currentTime;
        const source = context.createBufferSource();
        const filter = context.createBiquadFilter();
        const volume = context.createGain();
        source.buffer = impact;
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(1100, now);
        filter.Q.setValueAtTime(0.5, now);
        volume.gain.setValueAtTime(0.7, now);
        source.connect(filter);
        filter.connect(volume);
        volume.connect(context.destination);
        source.onended = () => { source.disconnect(); filter.disconnect(); volume.disconnect(); };
        source.start(now);
      };
      // Called only from user gestures, so mobile browsers can unlock audio.
      if (context.state === 'suspended') context.resume().then(click).catch(() => {});
      else click();
    } catch (_) {
      // Audio being unavailable must never block a move or navigation.
    }
  }
  root.ChessMoveSound = {play};
})(globalThis);
