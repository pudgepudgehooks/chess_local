const {placement, pieceTransitions, BoardSession} = ChessBoardState;
const board = document.getElementById('board'), status = document.getElementById('status');
const ghost = document.getElementById('ghost'), promotion = document.getElementById('promotion');
const navigation = document.getElementById('continuation'), back = document.getElementById('back'), forward = document.getElementById('forward');
let args = null, session = null, selected = null, drag = null, suppressClick = false;
let renderedFen = null, renderedWhite = null;
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
  board.querySelectorAll('.dragging').forEach(square => square.classList.remove('dragging'));
  highlights(); height();
}
function render({animate=true, drop=null}={}) {
  const pieces = placement(session.fen);
  const files = args.white ? 'abcdefgh' : 'hgfedcba', ranks = args.white ? '87654321' : '12345678';
  const changed = renderedFen !== session.fen || renderedWhite !== args.white;
  if (changed) {
    const previous = renderedFen && renderedWhite === args.white ? placement(renderedFen) : {};
    const origins = {};
    for (const square of board.children) {
      const svg = square.querySelector('svg');
      if (svg) origins[square.dataset.square] = svg.getBoundingClientRect();
    }
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
    renderedFen = session.fen; renderedWhite = args.white;
    if (animate && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      for (const {from, to} of pieceTransitions(previous, pieces)) {
        const square = board.querySelector(`[data-square="${to}"]`), svg = square.querySelector('svg');
        const origin = drop?.to === to ? drop.rect : origins[from];
        if (!svg || !origin || !svg.animate) continue;
        const destination = svg.getBoundingClientRect();
        square.style.zIndex = '2';
        const animation = svg.animate([
          {transform:`translate(${origin.left - destination.left}px, ${origin.top - destination.top}px)`},
          {transform:'translate(0, 0)'},
        ], {duration:drop?.to === to ? 110 : 220, easing:'cubic-bezier(0.22, 0.61, 0.36, 1)'});
        animation.onfinish = animation.oncancel = () => { square.style.zIndex = ''; };
      }
    }
  } else {
    // Keep in-flight animations alive when Streamlit acknowledges the same move.
    for (const square of board.children) {
      const piece = args.assets[pieces[square.dataset.square]];
      square.setAttribute('aria-label', square.dataset.square+' '+(piece ? piece.label : t('empty')));
    }
  }
  highlights();
  status.textContent = t(session.status, args.response?.message_values || {});
  if (session.solved && session.index >= 0 && session.index < session.frames.length - 1) {
    status.textContent += ' '+t('Step {step}/{total}: {move}', {step:session.index+1, total:session.frames.length, move:session.frames[session.index].san});
  }
  navigation.hidden = !session.solved;
  back.disabled = session.index < 0; back.textContent = '← '+t('Back');
  forward.disabled = session.index >= session.frames.length - 1; forward.textContent = t('Forward')+' →';
  height();
}
function submit(uci, dropRect=null) {
  const eventId = crypto.randomUUID();
  if (!session.start(uci, eventId, args.previews)) return;
  deselect(); render({drop:dropRect ? {to:uci.slice(2,4), rect:dropRect} : null});
  ChessMoveSound.play();
  send('streamlit:setComponentValue', {value:{uci, fen:args.fen, event_id:eventId}, dataType:'json'});
}
function attempt(from, to, dropRect=null) {
  if (session.busy || session.solved) return;
  const moves = args.legal.filter(m => m.slice(0,4) === from+to);
  if (!moves.length) { deselect(); session.status='Illegal move. Try another destination.'; render(); return; }
  if (moves.length === 1) { submit(moves[0], dropRect); return; }
  promotion.hidden=false;
  const choices=document.getElementById('choices'); choices.replaceChildren();
  for (const code of ['q','r','b','n']) {
    const move=moves.find(m => m[4] === code); if (!move) continue;
    const button=document.createElement('button'); button.textContent=t({q:'Queen',r:'Rook',b:'Bishop',n:'Knight'}[code]);
    button.onclick=() => submit(move, dropRect); choices.append(button);
  }
  const cancel=document.createElement('button'); cancel.textContent=t('Cancel'); cancel.onclick=deselect; choices.append(cancel);
  status.textContent=t('Choose your promotion piece.'); height();
}
function select(square) {
  if (session.busy || session.solved) return;
  if (selected && selected !== square) { attempt(selected,square); return; }
  if (args.pieces[square]?.own) {
    session.beginAttempt();
    selected=selected===square ? null : square; promotion.hidden=true;
    status.textContent=t(session.status); highlights();
  }
}
board.addEventListener('click', e => {
  if (suppressClick) { suppressClick=false; return; }
  const square=e.target.closest('[data-square]'); if (square) select(square.dataset.square);
});
board.addEventListener('pointerdown', e => {
  if (session.busy || session.solved) return;
  const square=e.target.closest('[data-square]'); if (!square || e.button !== 0) return;
  const from=square.dataset.square; if (!args.pieces[from]?.own) return;
  session.beginAttempt(); status.textContent=t(session.status);
  drag={from,x:e.clientX,y:e.clientY,moved:false,id:e.pointerId}; board.setPointerCapture(e.pointerId);
});
board.addEventListener('pointermove', e => {
  if (!drag) return;
  if (Math.hypot(e.clientX-drag.x,e.clientY-drag.y)>5) drag.moved=true;
  if (drag.moved) {
    selected=drag.from; highlights();
    const origin=board.querySelector(`[data-square="${drag.from}"]`), rect=origin.getBoundingClientRect();
    origin.classList.add('dragging');
    ghost.innerHTML=args.pieces[drag.from].svg; ghost.style.width=(rect.width*0.88)+'px'; ghost.style.height=(rect.height*0.88)+'px';
    ghost.hidden=false; ghost.style.left=e.clientX+'px'; ghost.style.top=e.clientY+'px';
  }
});
board.addEventListener('pointerup', e => {
  if (!drag) return;
  const current=drag;
  const dropRect = !ghost.hidden ? ghost.querySelector('svg')?.getBoundingClientRect() : null;
  drag=null; ghost.hidden=true;
  board.querySelectorAll('.dragging').forEach(square => square.classList.remove('dragging'));
  if (board.hasPointerCapture(e.pointerId)) board.releasePointerCapture(e.pointerId);
  if (!current.moved) return;
  suppressClick=true; setTimeout(() => suppressClick=false,0);
  const target=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-square]');
  if (target && target.dataset.square !== current.from) attempt(current.from,target.dataset.square,dropRect);
  else deselect();
});
board.addEventListener('pointercancel', deselect);
document.addEventListener('keydown', e => { if (e.key==='Escape') deselect(); });
back.onclick=() => { if (session.retreat()) { render(); ChessMoveSound.play(); } };
forward.onclick=() => { if (session.advance()) { render(); ChessMoveSound.play(); } };
window.addEventListener('message', e => {
  if (e.source!==window.parent || e.data.type!=='streamlit:render') return;
  const incoming=e.data.args;
  const contextChanged=!session || session.originalFen!==incoming.fen;
  if (contextChanged) session=new BoardSession(incoming.fen);
  args=incoming;
  if (e.data.theme?.textColor) document.documentElement.style.setProperty('--app-text', e.data.theme.textColor);
  for (const [name, variable] of Object.entries({
    'square light':'--board-light', 'square dark':'--board-dark', 'margin':'--board-border',
    'square light lastmove':'--board-light-last', 'square dark lastmove':'--board-dark-last',
  })) {
    if (args.colors?.[name]) document.documentElement.style.setProperty(variable, args.colors[name]);
  }
  document.documentElement.lang=args.language==='zh' ? 'zh-CN' : 'en';
  board.setAttribute('aria-label',t('Chess puzzle board'));
  promotion.querySelector('strong').textContent=t('Promote to:');
  const received=session.receive(args.response);
  // An unrelated rerun must preserve an unacknowledged drop or current playback step.
  if (contextChanged || received || !drag) render({animate:!contextChanged});
  if (received) deselect();
});
new ResizeObserver(height).observe(document.getElementById('wrap'));
send('streamlit:componentReady',{apiVersion:1}); height();
