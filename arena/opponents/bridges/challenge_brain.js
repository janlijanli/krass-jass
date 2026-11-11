'use strict';
/*
 * Drives a webplatformz/challenge JavaScript client's decision code ("brain") from a list of
 * challenge-protocol messages, one request per stdin line, one answer per stdout line.
 *
 *   node challenge_brain.js <client dir>      e.g. /home/user/ext/edualc_DonaldTrumpf/client
 *
 * Each line is the whole message history one seat would have received from the challenge server
 * for the decision at hand (DEAL_CARDS, BROADCAST_TRUMPF, PLAYED_CARDS, BROADCAST_STICH, ... and a
 * final REQUEST_TRUMPF or REQUEST_CARD). The bot's modules are reloaded for every line, so no state
 * survives between decisions: the history *is* the state, exactly as our stateless agents see it.
 *
 * The dispatch below is the client's own `client/bot.js` switch transcribed: that file pulls in
 * `shared/messages/*`, which is ES-module source the original only runs after a Babel build, and
 * the switch is all bot.js adds over the brain. Nothing of the client is copied here.
 */
const path = require('path');
const readline = require('readline');

const dir = path.resolve(process.argv[2]);
const write = process.stdout.write.bind(process.stdout);
// The client logs every decision to stdout; keep stdout for answers only.
console.log = () => {};
console.info = () => {};
console.warn = () => {};

function fresh() {
    for (const key of Object.keys(require.cache)) {
        if (key.startsWith(dir)) delete require.cache[key];
    }
    return {
        Brain: require(path.join(dir, 'logic/brain.js')),
        Card: require(path.join(dir, 'shared/deck/card.js')),
    };
}

function run(messages) {
    const {Brain, Card} = fresh();
    const brain = Brain.create();
    let hand = [];
    for (const m of messages) {
        const data = m.data;
        switch (m.type) {
        case 'DEAL_CARDS':
            hand = data.map(c => Card.create(c.number, c.color));
            brain.resetPlayedCards(hand);
            break;
        case 'BROADCAST_TRUMPF':
            brain.gameMode(data);
            break;
        case 'PLAYED_CARDS': {
            const last = data[data.length - 1];
            brain.registerCardWasPlayed(last, data);
            hand = hand.filter(c => c.number !== last.number || c.color !== last.color);
            break;
        }
        case 'BROADCAST_STICH':
            brain.registerStichCompleted(data);
            break;
        case 'REQUEST_TRUMPF':
            return {type: 'CHOOSE_TRUMPF', data: brain.chooseTrumpf(hand, data)};
        case 'REQUEST_CARD': {
            const card = brain.chooseCard(hand, data);
            return {type: 'CHOOSE_CARD', data: card ? {number: card.number, color: card.color} : null};
        }
        default:
            break;
        }
    }
    return {error: 'history ended without a request'};
}

const rl = readline.createInterface({input: process.stdin});
rl.on('line', line => {
    let answer;
    try {
        answer = run(JSON.parse(line));
    } catch (e) {
        answer = {error: String(e && e.stack || e)};
    }
    write(JSON.stringify(answer) + '\n');
});
