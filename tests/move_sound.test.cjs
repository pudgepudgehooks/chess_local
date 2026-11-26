const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
let created = 0, played = 0, resume;
let initialState = 'running';
class AudioContext {
  constructor() { created++; this.state = initialState; this.sampleRate = 1000; this.currentTime = 0; }
  createBuffer() { return {getChannelData:() => new Float32Array(75)}; }
  createBufferSource() { return {connect(){}, disconnect(){}, start(){played++;}}; }
  createBiquadFilter() { return {frequency:{setValueAtTime(){}}, Q:{setValueAtTime(){}}, connect(){}, disconnect(){}}; }
  createGain() { return {gain:{setValueAtTime(){}}, connect(){}, disconnect(){}}; }
  resume() { this.state = 'running'; return {then:fn=>{resume=fn; return {catch(){}};}}; }
}
const source = fs.readFileSync('board_component/move_sound.js', 'utf8');
let scope = {AudioContext};
vm.runInNewContext(source, scope);
scope.ChessMoveSound.setEnabled(false);
scope.ChessMoveSound.play();
assert.equal(created, 0, 'muting avoids even creating an audio context');
scope.ChessMoveSound.setEnabled(true);
scope.ChessMoveSound.play();
assert.equal(played, 1);
scope.ChessMoveSound.setEnabled(false);
scope.ChessMoveSound.play();
assert.equal(played, 1, 'muting stops subsequent move/navigation taps');
initialState = 'suspended';
scope = {AudioContext};
vm.runInNewContext(source, scope);
scope.ChessMoveSound.play();
scope.ChessMoveSound.setEnabled(false);
resume();
assert.equal(played, 1, 'muting also cancels a tap waiting for audio unlock');
console.log('Move sound tests passed');
