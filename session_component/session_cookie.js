/* The raw bearer token is confined to a Secure, host-only cookie, never a URL. */
const cookieName = '__Host-chess_beta_session';
const send = (type, data={}) => window.parent.postMessage({isStreamlitMessage:true, type, ...data}, '*');
let handled;
window.addEventListener('message', event => {
  if (event.source !== window.parent || event.data.type !== 'streamlit:render') return;
  const command = event.data.args?.command;
  if (!command || command.id === handled) return;
  if (command.token && !/^[A-Za-z0-9_-]{20,128}$/.test(command.token)) return;
  handled = command.id;
  let stored = false;
  try {
    const value = encodeURIComponent(command.token || '');
    const age = command.token ? Math.max(0, Math.min(43200, Number(command.max_age) || 0)) : 0;
    document.cookie = `${cookieName}=${value}; Path=/; Max-Age=${age}; Secure; SameSite=Strict`;
    const entry = document.cookie.split(';').map(part => part.trim()).find(part => part.startsWith(cookieName+'='));
    stored = command.token ? entry === `${cookieName}=${value}` : !entry;
  } catch (_) {}
  send('streamlit:setComponentValue', {value:{id:command.id, stored}, dataType:'json'});
});
send('streamlit:componentReady', {apiVersion:1});
send('streamlit:setFrameHeight', {height:0});
