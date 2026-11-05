'use strict';

const fs = require('fs');
const ACCOUNT = /^[A-Z]{2}[0-9]{6,32}(?![\s\S])/;

function validateAuthz(config) {
  if (!config || !Array.isArray(config.principals)) throw new Error('invalid notify auth configuration');
  const seen = new Set();
  return { principals: config.principals.map(p => {
    if (!p || typeof p.name !== 'string' || !p.name.trim() ||
        (p.role !== 'send' && p.role !== 'outbox') ||
        typeof p.token_sha256 !== 'string' || !/^[a-fA-F0-9]{64}(?![\s\S])/.test(p.token_sha256) ||
        !Array.isArray(p.accounts) || p.accounts.some(a => typeof a !== 'string' || !ACCOUNT.test(a))) {
      throw new Error('invalid notify auth configuration');
    }
    const hash = p.token_sha256.toLowerCase();
    const key = p.role + ':' + hash;
    if (seen.has(key)) throw new Error('invalid notify auth configuration');
    seen.add(key);
    return { name: p.name, role: p.role, token_sha256: hash, accounts: p.accounts.slice() };
  }) };
}

function loadAuthz(file) {
  try {
    return validateAuthz(JSON.parse(fs.readFileSync(file, 'utf8')));
  } catch (err) {
    return null;
  }
}

module.exports = { ACCOUNT, validateAuthz, loadAuthz };
