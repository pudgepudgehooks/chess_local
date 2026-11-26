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
  function pieceTransitions(before, after) {
    const removed = Object.keys(before).filter(square => before[square] !== after[square]);
    const added = Object.keys(after).filter(square => before[square] !== after[square]);
    return added.map(to => {
      let index = removed.findIndex(from => before[from] === after[to]);
      // Promotions (and undoing them) change the piece's symbol.
      if (index < 0) index = removed.findIndex(from => {
        const old = before[from], next = after[to];
        const white = old === old.toUpperCase();
        if (white !== (next === next.toUpperCase()) || Math.abs(from.charCodeAt(0) - to.charCodeAt(0)) > 1) return false;
        return (old.toLowerCase() === 'p' && /[qrbn]/i.test(next) && from[1] === (white ? '7' : '2') && to[1] === (white ? '8' : '1')) ||
          (next.toLowerCase() === 'p' && /[qrbn]/i.test(old) && from[1] === (white ? '8' : '1') && to[1] === (white ? '7' : '2'));
      });
      return index < 0 ? {to} : {from: removed.splice(index, 1)[0], to};
    });
  }
  class BoardSession {
    constructor(fen, intro=null) {
      this.originalFen = this.fen = fen;
      this.pendingId = this.handledId = this.uci = null;
      this.busy = this.solved = false;
      this.frames = []; this.index = 0;
      this.status = '';
      this.feedback = null;
      this.retryRequired = false;
      this.hintSquare = null;
      this.intro = intro;
      this.introPlaying = !!intro;
      if (intro) { this.fen = intro.fen; this.busy = true; }
    }
    revealIntro() {
      if (!this.introPlaying) return false;
      this.fen = this.originalFen;
      this.uci = this.intro.uci;
      return true;
    }
    finishIntro() {
      if (!this.introPlaying) return false;
      this.revealIntro();
      this.introPlaying = false;
      this.busy = false;
      return true;
    }
    showHint(square) {
      if (this.busy || this.solved || this.retryRequired || !/^[a-h][1-8]$/.test(square || '')) return false;
      this.hintSquare = square;
      return true;
    }
    get visibleFeedback() {
      return !this.solved || this.index === 0 ? this.feedback : null;
    }
    beginAttempt() {
      if (this.busy || this.solved || this.retryRequired) return false;
      this.status = '';
      this.feedback = null;
      return true;
    }
    start(uci, eventId, previews) {
      if (this.busy || this.solved || this.retryRequired || !previews[uci]) return false;
      this.fen = previews[uci]; this.uci = uci; this.pendingId = eventId;
      this.hintSquare = null;
      this.busy = true; this.status = 'Checking move…';
      this.feedback = null;
      return true;
    }
    receive(response) {
      if (!response || response.event_id === this.handledId ||
          (this.pendingId && response.event_id !== this.pendingId)) return false;
      const answeredMove = response.uci || this.uci || response.frames?.[0]?.uci;
      const attemptedFen = response.attempt_fen || (this.pendingId ? this.fen : null);
      this.handledId = response.event_id; this.pendingId = null;
      this.frames = response.frames || []; this.index = 0;
      this.solved = response.status === 'correct' && this.frames.length > 0;
      this.feedback = (this.solved || response.status === 'incorrect') && /^[a-h][1-8][a-h][1-8][qrbn]?$/.test(answeredMove || '')
        ? {square:answeredMove.slice(2,4), status:response.status} : null;
      if (this.feedback && response.status === 'incorrect' && response.repeat_game_mistake) this.feedback.repeated = true;
      this.introPlaying = false;
      this.busy = false;
      this.retryRequired = response.status === 'incorrect' && !!this.feedback && !!attemptedFen;
      this.fen = this.solved ? this.frames[0].fen : this.retryRequired ? attemptedFen : this.originalFen;
      this.uci = this.solved ? this.frames[0].uci : this.retryRequired ? answeredMove : null;
      this.correctMessage = response.message || 'Correct! Use Forward and Back to review the continuation.';
      this.status = this.solved ? this.correctMessage : response.message || 'The answer is incorrect, please try again';
      return true;
    }
    retry() {
      if (!this.retryRequired) return false;
      this.retryRequired = false;
      this.fen = this.originalFen;
      this.hintSquare = null;
      this.uci = null;
      this.feedback = null;
      this.status = '';
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
  const api = {placement, pieceTransitions, BoardSession};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ChessBoardState = api;
})(globalThis);
