/* Pure board interaction state, shared by the browser and regression tests. */
(function(root) {
  function placement(fen) {
    const squares = {};
    fen.split(' ')[0].split('/').forEach((rank, row) => {
      let file = 0;
      for (const symbol of rank) {
        if (/^[1-8]$/.test(symbol)) file += Number(symbol);
        else squares['abcdefgh'[file++] + (8 - row)] = symbol;
      }
    });
    return squares;
  }
  class BoardSession {
    constructor(fen) {
      this.originalFen = this.fen = fen;
      this.pendingId = this.handledId = this.uci = null;
      this.busy = this.solved = false;
      this.frames = []; this.index = 0;
      this.status = '';
    }
    beginAttempt() {
      if (this.busy || this.solved) return false;
      this.status = '';
      return true;
    }
    start(uci, eventId, previews) {
      if (this.busy || this.solved || !previews[uci]) return false;
      this.fen = previews[uci]; this.uci = uci; this.pendingId = eventId;
      this.busy = true; this.status = 'Checking move…';
      return true;
    }
    receive(response) {
      if (!response || response.event_id === this.handledId ||
          (this.pendingId && response.event_id !== this.pendingId)) return false;
      this.handledId = response.event_id; this.pendingId = null;
      this.frames = response.frames || []; this.index = 0;
      this.solved = response.status === 'correct' && this.frames.length > 0;
      this.busy = this.solved && this.frames.length > 1;
      this.fen = this.solved ? this.frames[0].fen : this.originalFen;
      this.uci = this.solved ? this.frames[0].uci : null;
      this.status = response.message || (this.solved ? 'Correct! Watch the continuation.' : 'The answer is incorrect, please try again');
      return true;
    }
    advance() {
      if (!this.solved || this.index + 1 >= this.frames.length) return false;
      this.index++;
      this.fen = this.frames[this.index].fen; this.uci = this.frames[this.index].uci;
      this.busy = this.index + 1 < this.frames.length;
      if (!this.busy) this.status = 'Click Next Puzzle to proceed.';
      return true;
    }
    replay() {
      if (!this.solved || this.frames.length < 2) return false;
      this.index = 0; this.fen = this.frames[0].fen; this.uci = this.frames[0].uci;
      this.busy = true; this.status = 'Correct! Watch the continuation.';
      return true;
    }
  }
  const api = {placement, BoardSession};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ChessBoardState = api;
})(globalThis);
