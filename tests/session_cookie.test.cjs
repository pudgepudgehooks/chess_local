const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../session_component/session_cookie.js'), 'utf8');
let handler, stored = '', lastWrite = '', messages = [];
const parent = {postMessage(message) { messages.push(message); }};
const document = {};
Object.defineProperty(document, 'cookie', {
  get() { return stored; },
  set(value) { lastWrite = value; stored = value.includes('Max-Age=0;') ? '' : value.split(';')[0]; },
});
vm.runInNewContext(source, {window:{parent, addEventListener(type, fn) { handler = fn; }}, document});
const send = (command, sender=parent) => handler({source:sender, data:{type:'streamlit:render', args:{command}}});
const token = 'x'.repeat(43);
send({id:'write', token, max_age:43200});
assert(lastWrite.startsWith('__Host-chess_beta_session='));
assert(lastWrite.includes('Path=/; Max-Age=43200; Secure; SameSite=Strict'));
assert.equal(messages.at(-1).value.stored, true);
assert(!JSON.stringify(messages).includes(token), 'acknowledgements must never return bearer tokens');
const count = messages.length;
send({id:'write', token, max_age:43200});
send({id:'foreign', token, max_age:43200}, {});
send({id:'invalid', token:'bad;cookie=injection', max_age:43200});
assert.equal(messages.length, count, 'ignore replays, foreign frames, and invalid values');
send({id:'clear', token:'', max_age:0});
assert.equal(stored, '');
assert.equal(messages.at(-1).value.stored, true);
send({id:'capped', token, max_age:9999999});
assert(lastWrite.includes('Max-Age=43200;'), 'browser persistence cannot exceed server session lifetime');
let blockedHandler, blockedResult;
const blockedParent = {postMessage(message) { blockedResult = message; }};
vm.runInNewContext(source, {
  window:{parent:blockedParent, addEventListener(type, fn) { blockedHandler = fn; }},
  document:{get cookie() { return ''; }, set cookie(value) {}},
});
blockedHandler({source:blockedParent, data:{type:'streamlit:render', args:{command:{id:'blocked', token, max_age:43200}}}});
assert.equal(blockedResult.value.stored, false, 'blocked cookies must not be reported as saved');
console.log('Browser session cookie tests passed');
