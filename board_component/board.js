const {placement, BoardSession} = ChessBoardState;
const board = document.getElementById('board'), status = document.getElementById('status');
const ghost = document.getElementById('ghost'), promotion = document.getElementById('promotion');
const replay = document.getElementById('replay');
let args = null, session = null, selected = null, drag = null, suppressClick = false, timer = null;
const send = (type, data={}) => window.parent.postMessage({isStreamlitMessage:true, type, ...data}, '*');
const t = (message, values={}) => (args?.labels?.[message] || message).replace(/\{(\w+)\}/g, (_, key) => values[key] ?? `{${key}}`);
function height() { send('streamlit:setFrameHeight', {height:document.getElementById('wrap').scrollHeight + 8}); }
function highlights() {
  for (const square of board.children) {
    square.classList.toggle('selected', square.dataset.square === selected);
    square.classList.toggle('target', !!selected && args.legal.some(m => m.slice(0,2) === selected && m.slice(2,4) === square.dataset.square));
  }
}
function deselect() {
  selected = null; drag = null; ghost.hidden = true; promotion.hidden = true;
  highlights(); height();
}
function render() {
  const pieces = placement(session.fen);
  const files = args.white ? 'abcdefgh' : 'hgfedcba', ranks = args.white ? '87654321' : '12345678';
  board.replaceChildren();
  for (let row=0; row<8; row++) for (let col=0; col<8; col++) {
    const square = files[col]+ranks[row], piece = args.assets[pieces[square]];
    const button = document.createElement('button'); button.type = 'button'; button.dataset.square = square;
    button.className = 'square' + ((files.charCodeAt(col)-97+Number(ranks[row]))%2 === 1 ? ' dark' : '');
    if (session.uci && [session.uci.slice(0,2), session.uci.slice(2,4)].includes(square)) button.classList.add('last');
    button.setAttribute('aria-label', square+' '+(piece ? piece.label : t('empty')));
    if (piece) button.innerHTML = piece.svg;
    if (col === 0) { const label=document.createElement('span'); label.className='coord rank'; label.textContent=ranks[row]; button.append(label); }
    if (row === 7) { const label=document.createElement('span'); label.className='coord file'; label.textContent=files[col]; button.append(label); }
    board.append(button);
  }
  highlights();
  status.textContent = t(session.status);
  if (session.solved && session.frames.length > 1) {
    status.textContent += ' '+t('Step {step}/{total}: {move}', {step:session.index+1, total:session.frames.length, move:session.frames[session.index].san});
  }
  replay.hidden = !session.solved || session.frames.length < 2;
  replay.disabled = session.busy; replay.textContent = t('Replay solution');
  height();
}
function play() {
  clearTimeout(timer);
  if (!session.busy || !session.solved) return;
  timer = setTimeout(() => {
    const frame = session.frames[session.index+1];
    const from = board.querySelector(`[data-square="${frame.uci.slice(0,2)}"]`);
    const rect = from?.getBoundingClientRect();
    const asset = args.assets[placement(session.fen)[frame.uci.slice(0,2)]];
    if (!session.advance()) return;
    render();
    const destination = board.querySelector(`[data-square="${frame.uci.slice(2,4)}"]`);
    if (rect && asset && destination && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const end = destination.getBoundingClientRect(); destination.classList.add('moving-hidden');
      ghost.innerHTML=asset.svg; ghost.style.width=rect.width+'px'; ghost.style.height=rect.height+'px';
      ghost.style.left=(end.x+end.width/2)+'px'; ghost.style.top=(end.y+end.height/2)+'px'; ghost.hidden=false;
      ghost.animate([{translate:`${rect.x-end.x}px ${rect.y-end.y}px`}, {translate:'0px 0px'}], {duration:300}).onfinish=() => {
        ghost.hidden=true; destination.classList.remove('moving-hidden');
      };
    }
    play();
  }, 1100);
}
function submit(uci) {
  const eventId = crypto.randomUUID();
  if (!session.start(uci, eventId, args.previews)) return;
  deselect(); render();
  send('streamlit:setComponentValue', {value:{uci, fen:args.fen, event_id:eventId}, dataType:'json'});
}
function attempt(from, to) {
  if (session.busy || session.solved) return;
  const moves = args.legal.filter(m => m.slice(0,4) === from+to);
  if (!moves.length) { deselect(); session.status='Illegal move. Try another destination.'; render(); return; }
  if (moves.length === 1) { submit(moves[0]); return; }
  promotion.hidden=false;
  const choices=document.getElementById('choices'); choices.replaceChildren();
  for (const code of ['q','r','b','n']) {
    const move=moves.find(m => m[4] === code); if (!move) continue;
    const button=document.createElement('button'); button.textContent=t({q:'Queen',r:'Rook',b:'Bishop',n:'Knight'}[code]);
    button.onclick=() => submit(move); choices.append(button);
  }
  const cancel=document.createElement('button'); cancel.textContent=t('Cancel'); cancel.onclick=deselect; choices.append(cancel);
  status.textContent=t('Choose your promotion piece.'); height();
}
function select(square) {
  if (session.busy || session.solved) return;
  if (selected && selected !== square) { attempt(selected,square); return; }
  if (args.pieces[square]?.own) { selected=selected===square ? null : square; promotion.hidden=true; highlights(); }
}
board.addEventListener('click', e => {
  if (suppressClick) { suppressClick=false; return; }
  const square=e.target.closest('[data-square]'); if (square) select(square.dataset.square);
});
board.addEventListener('pointerdown', e => {
  if (session.busy || session.solved) return;
  const square=e.target.closest('[data-square]'); if (!square || e.button !== 0) return;
  const from=square.dataset.square; if (!args.pieces[from]?.own) return;
  drag={from,x:e.clientX,y:e.clientY,moved:false,id:e.pointerId}; board.setPointerCapture(e.pointerId);
});
board.addEventListener('pointermove', e => {
  if (!drag) return;
  if (Math.hypot(e.clientX-drag.x,e.clientY-drag.y)>5) drag.moved=true;
  if (drag.moved) {
    selected=drag.from; highlights();
    const origin=board.querySelector(`[data-square="${drag.from}"]`), rect=origin.getBoundingClientRect();
    ghost.innerHTML=args.pieces[drag.from].svg; ghost.style.width=rect.width+'px'; ghost.style.height=rect.height+'px';
    ghost.hidden=false; ghost.style.left=e.clientX+'px'; ghost.style.top=e.clientY+'px';
  }
});
board.addEventListener('pointerup', e => {
  if (!drag) return;
  const current=drag; drag=null; ghost.hidden=true;
  if (board.hasPointerCapture(e.pointerId)) board.releasePointerCapture(e.pointerId);
  if (!current.moved) return;
  suppressClick=true; setTimeout(() => suppressClick=false,0);
  const target=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-square]');
  if (target && target.dataset.square !== current.from) attempt(current.from,target.dataset.square);
  else deselect();
});
board.addEventListener('pointercancel', deselect);
document.addEventListener('keydown', e => { if (e.key==='Escape') deselect(); });
replay.onclick=() => { if (session.replay()) { render(); play(); } };
window.addEventListener('message', e => {
  if (e.source!==window.parent || e.data.type!=='streamlit:render') return;
  const incoming=e.data.args;
  const contextChanged=!session || session.originalFen!==incoming.fen;
  if (contextChanged) { clearTimeout(timer); session=new BoardSession(incoming.fen); }
  args=incoming;
  document.documentElement.lang=args.language==='zh' ? 'zh-CN' : 'en';
  board.setAttribute('aria-label',t('Chess puzzle board'));
  promotion.querySelector('strong').textContent=t('Promote to:');
  const received=session.receive(args.response);
  // An unrelated rerun must preserve an unacknowledged drop or current playback step.
  if (contextChanged || received || !drag) render();
  if (received) { deselect(); play(); }
});
new ResizeObserver(height).observe(document.getElementById('wrap'));
send('streamlit:componentReady',{apiVersion:1}); height();
