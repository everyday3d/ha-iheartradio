#!/usr/bin/env node
/**
 * iHeartRadio — Automated Home Assistant Deploy & Cache-Buster Pipeline
 *
 * 1. Atomically copies `iheartradio-card.js` and all `custom_components/iheartradio` files to HA shares.
 * 2. Connects to Home Assistant WebSocket API to bust Lovelace in-memory resource cache (`/local/iheartradio-card.js?v=<timestamp>`).
 * 3. Reloads any active `iheartradio` integration entry.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');

const SRC_CC_DIR = path.join(REPO_ROOT, 'custom_components', 'iheartradio');
const SRC_CARD = path.join(SRC_CC_DIR, 'iheartradio-card.js');
const HA_HOST = process.env.HA_HOST || '192.168.1.207';
const HA_PORT = process.env.HA_PORT || 8123;
const HA_SHARE = process.env.HA_SHARE || '\\\\HOMEASSISTANT\\config';
const DEST_CC_DIR = path.join(HA_SHARE, 'custom_components', 'iheartradio');
const DEST_WWW_CARD = path.join(HA_SHARE, 'www', 'iheartradio-card.js');
const DEST_HACS_DIR = path.join(HA_SHARE, 'www', 'community', 'ha-iheartradio');
const DEST_HACS_CARD = path.join(DEST_HACS_DIR, 'iheartradio-card.js');

const HA_TOKEN_FILE = process.env.HA_TOKEN_FILE || 'C:\\claude\\ha-token.txt';
const HA_TOKEN = (process.env.HA_TOKEN || (fs.existsSync(HA_TOKEN_FILE) ? fs.readFileSync(HA_TOKEN_FILE, 'utf8') : '')).trim();

function copyDirRecursive(srcDir, destDir) {
  if (!fs.existsSync(destDir)) {
    fs.mkdirSync(destDir, { recursive: true });
  }
  const entries = fs.readdirSync(srcDir, { withFileTypes: true });
  let count = 0;
  for (const entry of entries) {
    if (entry.name === '__pycache__' || entry.name.endsWith('.pyc')) continue;
    const srcPath = path.join(srcDir, entry.name);
    const destPath = path.join(destDir, entry.name);
    if (entry.isDirectory()) {
      count += copyDirRecursive(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
      count++;
    }
  }
  return count;
}

async function main() {
  console.log('\n========================================================');
  console.log(' 🚀 IHEARTRADIO — HA DEPLOY & LOVELACE CACHE-BUSTER');
  console.log('========================================================\n');

  if (!fs.existsSync(SRC_CARD)) {
    console.error(`❌ Source card not found at ${SRC_CARD}`);
    process.exit(1);
  }
  if (!HA_TOKEN) {
    console.error(`❌ No Home Assistant token: set HA_TOKEN or put one in ${HA_TOKEN_FILE}`);
    process.exit(1);
  }

  const stat = fs.statSync(SRC_CARD);
  const fileSizeKb = (stat.size / 1024).toFixed(1);
  const versionTag = Date.now();
  console.log(`📦 Source card bundle: ${fileSizeKb} KB (${stat.size} bytes)`);

  // Step 1: Copy custom_components/iheartradio and www/iheartradio-card.js
  console.log('\n[1/3] Copying integration & card bundle to Home Assistant shares...');
  try {
    const count = copyDirRecursive(SRC_CC_DIR, DEST_CC_DIR);
    console.log(`  ✅ Synced ${count} files to ${DEST_CC_DIR}`);
  } catch (err) {
    console.warn(`  ⚠️ Could not copy to ${DEST_CC_DIR}: ${err.message}`);
  }

  try {
    fs.copyFileSync(SRC_CARD, DEST_WWW_CARD);
    console.log(`  ✅ Synced: ${DEST_WWW_CARD}`);
  } catch (err) {
    console.warn(`  ⚠️ Could not copy to ${DEST_WWW_CARD}: ${err.message}`);
  }

  if (fs.existsSync(DEST_HACS_DIR)) {
    try {
      fs.copyFileSync(SRC_CARD, DEST_HACS_CARD);
      console.log(`  ✅ Synced: ${DEST_HACS_CARD}`);
    } catch (err) {}
  }

  // Step 2: Update Lovelace resources via WebSocket to /local/iheartradio-card.js?v=<timestamp>
  console.log('\n[2/3] Updating Home Assistant Lovelace resource & reloading integration...');
  const targetUrl = `/local/iheartradio-card.js?v=${versionTag}`;

  try {
    await updateLovelaceAndReloadWs(targetUrl);
  } catch (err) {
    console.error(`  ❌ WebSocket update failed: ${err.message}`);
  }

  console.log('\n========================================================');
  console.log(' 🎉 DEPLOYMENT COMPLETE — LIVE HA UPDATED & CACHE BUSTED!');
  console.log(` 🌐 Active Resource: ${targetUrl}`);
  console.log('========================================================\n');
}

function updateLovelaceAndReloadWs(targetUrl) {
  return new Promise((resolve, reject) => {
    const ws = new globalThis.WebSocket(`ws://${HA_HOST}:${HA_PORT}/api/websocket`);
    let msgId = 1;
    let listResId = 0;
    let entriesResId = 0;

    const timeout = setTimeout(() => {
      ws.close();
      reject(new Error('WebSocket connection timed out after 12s'));
    }, 12000);

    ws.onmessage = async (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch (e) {
        return;
      }

      if (msg.type === 'auth_required') {
        ws.send(JSON.stringify({ type: 'auth', access_token: HA_TOKEN }));
      } else if (msg.type === 'auth_ok') {
        listResId = msgId++;
        ws.send(JSON.stringify({ id: listResId, type: 'lovelace/resources' }));
      } else if (msg.id === listResId) {
        const items = Array.isArray(msg.result) ? msg.result : [];
        const matching = items.filter(r => (r.url || '').includes('iheartradio-card.js'));
        if (matching.length > 0) {
          const primary = matching[0];
          ws.send(JSON.stringify({
            id: msgId++,
            type: 'lovelace/resources/update',
            resource_id: primary.id,
            url: targetUrl,
            res_type: 'module'
          }));
          console.log(`  ✅ Updated Lovelace resource [${primary.id}] -> ${targetUrl}`);
          for (let i = 1; i < matching.length; i++) {
            ws.send(JSON.stringify({
              id: msgId++,
              type: 'lovelace/resources/delete',
              resource_id: matching[i].id
            }));
            console.log(`  🧹 Removed duplicate Lovelace resource [${matching[i].id}] (${matching[i].url})`);
          }
        } else {
          ws.send(JSON.stringify({
            id: msgId++,
            type: 'lovelace/resources/create',
            url: targetUrl,
            res_type: 'module'
          }));
          console.log(`  ✅ Created Lovelace resource -> ${targetUrl}`);
        }
        entriesResId = msgId++;
        ws.send(JSON.stringify({ id: entriesResId, type: 'config_entries/get' }));
      } else if (msg.id === entriesResId) {
        const entries = Array.isArray(msg.result) ? msg.result : [];
        const ihrEntries = entries.filter(e => e.domain === 'iheartradio');
        for (const entry of ihrEntries) {
          if (entry.entry_id) {
            try {
              const res = await fetch(`http://${HA_HOST}:${HA_PORT}/api/config/config_entries/entry/${entry.entry_id}/reload`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${HA_TOKEN}` }
              });
              console.log(`  ✅ Reloaded iheartradio config entry (${entry.entry_id}) -> HTTP ${res.status}`);
            } catch (e) {}
          }
        }
        clearTimeout(timeout);
        ws.close();
        resolve(true);
      }
    };

    ws.onerror = (err) => {
      clearTimeout(timeout);
      reject(err);
    };
  });
}

main().catch(err => {
  console.error('Fatal deployment error:', err);
  process.exit(1);
});
