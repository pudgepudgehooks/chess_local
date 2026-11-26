/* Crisp wooden piece-on-board tap with a short, non-resonant impact. */
(function(root) {
  let context, impact, enabled = true;
  function setEnabled(value) { enabled = value !== false; }
  function play() {
    if (!enabled) return;
    try {
      const AudioContext = root.AudioContext || root.webkitAudioContext;
      if (!AudioContext) return;
      if (!context || context.state === 'closed') {
        context = new AudioContext();
        impact = context.createBuffer(1, Math.ceil(context.sampleRate * 0.075), context.sampleRate);
        const samples = impact.getChannelData(0);
        const smoothing = 1 - Math.exp(-2 * Math.PI * 1800 / context.sampleRate);
        let wood = 0;
        for (let i = 0; i < samples.length; i++) {
          const time = i / context.sampleRate;
          wood += smoothing * ((Math.random() * 2 - 1) - wood);
          const attack = Math.min(1, time / 0.0006);
          const body = 0.36 * Math.sin(2 * Math.PI * 230 * time) * Math.exp(-time * 110)
            + 0.14 * Math.sin(2 * Math.PI * 430 * time) * Math.exp(-time * 150);
          samples[i] = attack * (body + 0.95 * wood * Math.exp(-time * 180));
        }
      }
      const click = () => {
        if (!enabled || context.state !== 'running') return;
        const now = context.currentTime;
        const source = context.createBufferSource();
        const filter = context.createBiquadFilter();
        const volume = context.createGain();
        source.buffer = impact;
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(2200, now);
        filter.Q.setValueAtTime(0.5, now);
        volume.gain.setValueAtTime(0.8, now);
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
  root.ChessMoveSound = {play, setEnabled};
})(globalThis);
