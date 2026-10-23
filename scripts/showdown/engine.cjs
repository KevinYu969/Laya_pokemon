// 只在本機執行官方 Showdown 引擎；stdin/stdout 為逐行 JSON。
const path = require('node:path');
const readline = require('node:readline');
const root = path.resolve(__dirname, '../..');
const Sim = require(path.join(root, '.local/showdown/node_modules/pokemon-showdown'));
let battle, previousLogLength = 0, randomState = 42;

function publicLog(lines) {
  const output = [];
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].startsWith('|split|')) {
      if (lines[i + 2]) output.push(lines[i + 2]);
      i += 2;
    } else output.push(lines[i]);
  }
  return output;
}

function monView(mon) {
  return {species: mon.species.name, level: mon.level, hp: mon.hp, maxhp: mon.maxhp,
    status: mon.status, fainted: mon.fainted, types: mon.getTypes()};
}

function response(extra = {}) {
  const me = battle.p1.active[0], opponent = battle.p2.active[0];
  const request = battle.p1.activeRequest;
  const choices = [];
  for (const [index, move] of (request?.active?.[0]?.moves || []).entries()) {
    if (move.disabled || move.pp === 0) continue;
    const info = battle.dex.moves.get(move.id || move.move);
    choices.push({id: `move ${index + 1}`, name: move.move, type: info.type,
      power: info.basePower, accuracy: info.accuracy, pp: move.pp, category: info.category});
  }
  const current = battle.log.length;
  const events = publicLog(battle.log.slice(previousLogLength));
  previousLogLength = current;
  return {turn: battle.turn, ended: battle.ended, winner: battle.winner || null,
    view: {p1: monView(me), p2: monView(opponent)},
    // 對手精確 HP 僅供觀戰；提供模型的 HP 為百分比，不給對手隱藏招式。
    observation: {turn: battle.turn, own: monView(me), opponent: {species: opponent.species.name,
      level: opponent.level, types: opponent.getTypes(), hp_percent: Math.ceil(opponent.hp / opponent.maxhp * 100), status: opponent.status}},
    choices, events, ...extra};
}

function start(seed) {
  randomState = seed >>> 0;
  const team1 = [{species: 'Pikachu', level: 20, moves: ['thunderbolt', 'quickattack', 'thunderwave', 'growl']}];
  const team2 = [{species: 'Squirtle', level: 20, moves: ['watergun', 'tackle', 'tailwhip', 'bubble']}];
  battle = new Sim.Battle({formatid: 'gen1customgame', seed: [1, 2, 3, seed & 65535],
    p1: {name: 'Laya CPU', team: Sim.Teams.pack(team1)},
    p2: {name: 'Seeded Random', team: Sim.Teams.pack(team2)}});
  return response({scenario: 'fixed-pikachu-vs-squirtle-level20', seed,
    showdown_version: require(path.join(root, '.local/showdown/node_modules/pokemon-showdown/package.json')).version});
}

function step(choice) {
  if (battle.ended) throw new Error('Battle already ended');
  const opponentMoves = battle.p2.activeRequest.active[0].moves
    .map((move, index) => ({move, index})).filter(({move}) => !move.disabled && move.pp !== 0);
  randomState = (Math.imul(randomState, 1664525) + 1013904223) >>> 0;
  const selected = opponentMoves[randomState % opponentMoves.length];
  const opponentChoice = `move ${selected.index + 1}`;
  if (!battle.choose('p1', choice)) throw new Error('Player choice rejected by Showdown');
  if (!battle.choose('p2', opponentChoice)) throw new Error('Opponent choice rejected by Showdown');
  return response({opponent_choice: opponentChoice});
}

readline.createInterface({input: process.stdin}).on('line', line => {
  try {
    const message = JSON.parse(line);
    let value;
    if (message.command === 'start') value = start(message.seed ?? 42);
    else if (message.command === 'step') value = step(message.choice);
    else if (message.command === 'replay') value = {log: publicLog(battle.log).join('\n')};
    else throw new Error('Unknown command');
    process.stdout.write(JSON.stringify(value) + '\n');
  } catch (error) {
    process.stdout.write(JSON.stringify({error: String(error.message)}) + '\n');
  }
});
