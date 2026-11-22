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
      this.busy = false;
      this.fen = this.solved ? this.frames[0].fen : this.originalFen;
      this.uci = this.solved ? this.frames[0].uci : null;
      this.correctMessage = response.message || 'Correct! Use Forward and Back to review the continuation.';
      this.status = this.solved ? this.correctMessage : response.message || 'The answer is incorrect, please try again';
      return true;
    }
    advance() {
      if (!this.solved || this.index + 1 >= this.frames.length) return false;
      return this.goTo(this.index + 1);
    }
    retreat() {
      if (!this.solved || this.index < 0) return false;
      return this.goTo(this.index - 1);
    }
    goTo(index) {
      if (!this.solved || index < -1 || index >= this.frames.length) return false;
      this.index = index;
      this.fen = index < 0 ? this.originalFen : this.frames[index].fen;
      this.uci = index < 0 ? null : this.frames[index].uci;
      this.status = index < 0 ? 'Starting position.' :
        this.frames.length > 1 && index === this.frames.length - 1 ? 'Click Next Puzzle to proceed.' : this.correctMessage;
      return true;
    }
  }
  const api = {placement, BoardSession};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ChessBoardState = api;
})(globalThis);
