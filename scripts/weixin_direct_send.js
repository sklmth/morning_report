#!/usr/bin/env node
/**
 * Direct Weixin sender for morning_report.
 *
 * Bypasses `openclaw message send`, because OpenClaw core may accept an
 * openclaw-weixin-looking channel and return a Message ID without invoking the
 * real Weixin plugin. This script reuses the plugin's stored account token and
 * context-token files, then calls the same Weixin HTTP APIs as the plugin.
 */

const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');

const DEFAULT_BASE_URL = 'https://ilinkai.weixin.qq.com';
const CDN_BASE_URL = 'https://novac2c.cdn.weixin.qq.com/c2c';
const CHANNEL_VERSION = '2.4.4';
const ILINK_APP_ID = 'bot';
const ILINK_APP_CLIENT_VERSION = 0x00020404;
const MESSAGE_TYPE_BOT = 2;
const MESSAGE_STATE_FINISH = 2;
const ITEM_TEXT = 1;
const ITEM_IMAGE = 2;
const ITEM_FILE = 4;
const ITEM_VIDEO = 5;
const UPLOAD_MEDIA_IMAGE = 1;
const UPLOAD_MEDIA_VIDEO = 2;
const UPLOAD_MEDIA_FILE = 3;
const DEFAULT_API_TIMEOUT_MS = 15_000;
const UPLOAD_MAX_RETRIES = 3;

function usage() {
  console.error(`Usage:
  node scripts/weixin_direct_send.js --to <user@im.wechat> [--account <accountId>] --message <text>
  node scripts/weixin_direct_send.js --to <user@im.wechat> [--account <accountId>] --media <path> [--message <caption>]

Options:
  --state-dir <dir>      OpenClaw state dir, default /root/.openclaw
  --config <path>        OpenClaw config, default <state-dir>/openclaw.json
  --json                 Print JSON result (always enabled for success/failure)
  --dry-run              Validate account/context and print planned action only
  --no-context           Do not send context_token to Weixin
`);
  process.exit(2);
}

function parseArgs(argv) {
  const out = { json: false, dryRun: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--json') { out.json = true; continue; }
    if (a === '--dry-run') { out.dryRun = true; continue; }
    if (a === '--no-context') { out.noContext = true; continue; }
    if (!a.startsWith('--')) usage();
    const key = a.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    const val = argv[++i];
    if (val == null) usage();
    out[key] = val;
  }
  if (!out.to) usage();
  if (!out.message && !out.media) usage();
  return out;
}

function fail(message, detail) {
  console.error(JSON.stringify({ ok: false, error: message, ...(detail ? { detail: String(detail) } : {}) }));
  process.exit(1);
}

function readJson(file, fallback = null) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); }
  catch { return fallback; }
}

function normalizeAccountId(id) {
  return String(id || '').replace(/@/g, '-').replace(/\./g, '-');
}

function loadOpenClawConfig(configPath) {
  return readJson(configPath, {});
}

function listAccountIds(stateDir) {
  const p = path.join(stateDir, 'openclaw-weixin', 'accounts.json');
  const ids = readJson(p, []);
  return Array.isArray(ids) ? ids.filter((x) => typeof x === 'string' && x.trim()) : [];
}

function resolveAccount({ stateDir, cfg, accountId }) {
  const ids = listAccountIds(stateDir);
  let id = accountId || cfg.channels?.['openclaw-weixin']?.accountId;
  if (!id && ids.length === 1) id = ids[0];
  if (!id) throw new Error(`no Weixin account id found; indexed accounts=${ids.join(',') || '<none>'}`);
  id = normalizeAccountId(id);

  const accountPath = path.join(stateDir, 'openclaw-weixin', 'accounts', `${id}.json`);
  const accountData = readJson(accountPath, null);
  if (!accountData?.token) throw new Error(`Weixin account is not configured or token missing: ${id}`);
  const section = cfg.channels?.['openclaw-weixin'] || {};
  const accountCfg = section.accounts?.[id] || section;
  if (accountCfg.enabled === false) throw new Error(`Weixin account disabled: ${id}`);
  return {
    accountId: id,
    userId: String(accountData.userId || ''),
    token: String(accountData.token),
    baseUrl: accountData.baseUrl || DEFAULT_BASE_URL,
    cdnBaseUrl: accountCfg.cdnBaseUrl || CDN_BASE_URL,
  };
}

function loadContextToken(stateDir, accountId, to) {
  const p = path.join(stateDir, 'openclaw-weixin', 'accounts', `${accountId}.context-tokens.json`);
  const data = readJson(p, {});
  return typeof data[to] === 'string' && data[to] ? data[to] : undefined;
}

function baseInfo() {
  return { channel_version: CHANNEL_VERSION, bot_agent: 'OpenClaw' };
}

function ensureTrailingSlash(url) { return url.endsWith('/') ? url : `${url}/`; }
function randomWechatUin() {
  return Buffer.from(String(crypto.randomBytes(4).readUInt32BE(0)), 'utf8').toString('base64');
}
function buildHeaders(token) {
  return {
    'Content-Type': 'application/json',
    AuthorizationType: 'ilink_bot_token',
    'X-WECHAT-UIN': randomWechatUin(),
    'iLink-App-Id': ILINK_APP_ID,
    'iLink-App-ClientVersion': String(ILINK_APP_CLIENT_VERSION),
    Authorization: `Bearer ${token}`,
  };
}

async function postJson({ baseUrl, endpoint, token, body, timeoutMs = DEFAULT_API_TIMEOUT_MS, label }) {
  const url = new URL(endpoint, ensureTrailingSlash(baseUrl));
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url.toString(), {
      method: 'POST',
      headers: buildHeaders(token),
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    const text = await res.text();
    if (!res.ok) throw new Error(`${label} ${res.status}: ${text}`);
    const parsed = text ? JSON.parse(text) : {};
    if (parsed && typeof parsed === 'object') {
      const ret = parsed.ret ?? parsed.errcode;
      if (ret != null && Number(ret) !== 0) {
        throw new Error(`${label} business error: ${JSON.stringify(parsed)}`);
      }
    }
    return parsed;
  } finally {
    clearTimeout(timer);
  }
}

function generateId() { return `openclaw-weixin:${Date.now()}-${crypto.randomBytes(4).toString('hex')}`; }
function aesEcbPaddedSize(n) { return Math.ceil((n + 1) / 16) * 16; }
function encryptAesEcb(buf, key) {
  const cipher = crypto.createCipheriv('aes-128-ecb', key, null);
  return Buffer.concat([cipher.update(buf), cipher.final()]);
}
function md5(buf) { return crypto.createHash('md5').update(buf).digest('hex'); }

function mimeFromFilename(filename) {
  const ext = path.extname(filename).toLowerCase();
  return {
    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp',
    '.mp4': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm', '.mkv': 'video/x-matroska', '.avi': 'video/x-msvideo',
  }[ext] || 'application/octet-stream';
}

async function uploadMedia({ filePath, to, account, mediaType }) {
  const plaintext = await fsp.readFile(filePath);
  const filekey = crypto.randomBytes(16).toString('hex');
  const aeskey = crypto.randomBytes(16);
  const rawsize = plaintext.length;
  const filesize = aesEcbPaddedSize(rawsize);
  const resp = await postJson({
    baseUrl: account.baseUrl,
    endpoint: 'ilink/bot/getuploadurl',
    token: account.token,
    label: 'getUploadUrl',
    body: {
      filekey,
      media_type: mediaType,
      to_user_id: to,
      rawsize,
      rawfilemd5: md5(plaintext),
      filesize,
      no_need_thumb: true,
      aeskey: aeskey.toString('hex'),
      base_info: baseInfo(),
    },
  });
  const uploadUrl = resp.upload_full_url || (resp.upload_param
    ? `${account.cdnBaseUrl}/upload?encrypted_query_param=${encodeURIComponent(resp.upload_param)}&filekey=${encodeURIComponent(filekey)}`
    : '');
  if (!uploadUrl) throw new Error(`getUploadUrl returned no upload URL: ${JSON.stringify(resp)}`);
  const ciphertext = encryptAesEcb(plaintext, aeskey);
  let lastErr;
  for (let attempt = 1; attempt <= UPLOAD_MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(uploadUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/octet-stream' },
        body: new Uint8Array(ciphertext),
      });
      if (res.status !== 200) {
        const errText = res.headers.get('x-error-message') || await res.text();
        throw new Error(`CDN upload ${res.status}: ${errText}`);
      }
      const downloadParam = res.headers.get('x-encrypted-param');
      if (!downloadParam) throw new Error('CDN upload response missing x-encrypted-param header');
      return { filekey, downloadEncryptedQueryParam: downloadParam, aeskey: aeskey.toString('hex'), fileSize: rawsize, fileSizeCiphertext: filesize };
    } catch (e) {
      lastErr = e;
      if (attempt === UPLOAD_MAX_RETRIES || /CDN upload 4\d\d/.test(String(e.message))) throw e;
    }
  }
  throw lastErr;
}

async function sendMessage({ account, to, items, contextToken }) {
  let lastId = '';
  const responses = [];
  for (const item of items) {
    lastId = generateId();
    const response = await postJson({
      baseUrl: account.baseUrl,
      endpoint: 'ilink/bot/sendmessage',
      token: account.token,
      label: 'sendMessage',
      body: {
        msg: {
          from_user_id: '',
          to_user_id: to,
          client_id: lastId,
          message_type: MESSAGE_TYPE_BOT,
          message_state: MESSAGE_STATE_FINISH,
          item_list: [item],
          context_token: contextToken,
        },
        base_info: baseInfo(),
      },
    });
    responses.push(response);
  }
  return { messageId: lastId, responses };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const stateDir = args.stateDir || process.env.OPENCLAW_STATE_DIR || '/root/.openclaw';
  const cfgPath = args.config || process.env.OPENCLAW_CONFIG || path.join(stateDir, 'openclaw.json');
  const cfg = loadOpenClawConfig(cfgPath);
  const account = resolveAccount({ stateDir, cfg, accountId: args.account });
  if (account.userId && args.to === account.userId) {
    throw new Error(
      `target ${args.to} is the logged-in Weixin account userId for ${account.accountId}; ` +
      'use a recipient/peer id instead of the sender self id'
    );
  }
  const contextToken = args.noContext ? undefined : loadContextToken(stateDir, account.accountId, args.to);
  if (!args.noContext && !contextToken) {
    throw new Error(`missing context token for ${args.to}; ask the recipient to message the bot once, or wait for inbound polling`);
  }

  if (args.dryRun) {
    console.log(JSON.stringify({ ok: true, dryRun: true, channel: 'openclaw-weixin', handledBy: 'weixin-direct', accountId: account.accountId, accountUserId: account.userId || null, to: args.to, hasContextToken: Boolean(contextToken), media: args.media || null, messageLength: (args.message || '').length }));
    return;
  }

  const items = [];
  if (args.message) items.push({ type: ITEM_TEXT, text_item: { text: args.message } });
  if (args.media) {
    const abs = path.resolve(args.media);
    if (!fs.existsSync(abs)) throw new Error(`media file not found: ${abs}`);
    const mime = mimeFromFilename(abs);
    const mediaType = mime.startsWith('video/') ? UPLOAD_MEDIA_VIDEO : (mime.startsWith('image/') ? UPLOAD_MEDIA_IMAGE : UPLOAD_MEDIA_FILE);
    const uploaded = await uploadMedia({ filePath: abs, to: args.to, account, mediaType });
    if (mediaType === UPLOAD_MEDIA_IMAGE) {
      items.push({ type: ITEM_IMAGE, image_item: { media: { encrypt_query_param: uploaded.downloadEncryptedQueryParam, aes_key: Buffer.from(uploaded.aeskey).toString('base64'), encrypt_type: 1 }, mid_size: uploaded.fileSizeCiphertext } });
    } else if (mediaType === UPLOAD_MEDIA_VIDEO) {
      items.push({ type: ITEM_VIDEO, video_item: { media: { encrypt_query_param: uploaded.downloadEncryptedQueryParam, aes_key: Buffer.from(uploaded.aeskey).toString('base64'), encrypt_type: 1 }, video_size: uploaded.fileSizeCiphertext } });
    } else {
      items.push({ type: ITEM_FILE, file_item: { media: { encrypt_query_param: uploaded.downloadEncryptedQueryParam, aes_key: Buffer.from(uploaded.aeskey).toString('base64'), encrypt_type: 1 }, file_name: path.basename(abs), len: String(uploaded.fileSize) } });
    }
  }
  const result = await sendMessage({ account, to: args.to, items, contextToken });
  console.log(JSON.stringify({
    ok: true,
    channel: 'openclaw-weixin',
    handledBy: 'weixin-direct',
    via: 'weixin-http-api',
    accountId: account.accountId,
    to: args.to,
    messageId: result.messageId,
    apiResponses: result.responses,
  }));
}

main().catch((err) => fail(err.message || String(err), err.stack));
