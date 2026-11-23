/* Original, locally synthesized piece-on-board click. No external audio files. */
(function(root) {
  let context, impact;
  function play() {
    try {
      const AudioContext = root.AudioContext || root.webkitAudioContext;
      if (!AudioContext) return;
      if (!context || context.state === 'closed') {
        context = new AudioContext();
        impact = context.createBuffer(1, Math.ceil(context.sampleRate * 0.085), context.sampleRate);
        const samples = impact.getChannelData(0);
        for (let i = 0; i < samples.length; i++) {
          const time = i / context.sampleRate;
          samples[i] = (Math.random() * 2 - 1) * Math.exp(-time * 75);
        }
      }
      const click = () => {
        if (context.state !== 'running') return;
        const now = context.currentTime;
        const source = context.createBufferSource();
        const filter = context.createBiquadFilter();
        const volume = context.createGain();
        source.buffer = impact;
        filter.type = 'bandpass';
        filter.frequency.setValueAtTime(1600, now);
        filter.Q.setValueAtTime(0.7, now);
        volume.gain.setValueAtTime(0.6, now);
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
