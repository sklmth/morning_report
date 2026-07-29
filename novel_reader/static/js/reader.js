/* reader.js — reading preferences, sidebar, settings panel, progress */

const PREF_KEY = 'novel_reader_prefs';

const defaults = { theme: 'light', fontSize: 18, lineHeight: 1.9, font: 'song' };

function loadPrefs() {
  try { return { ...defaults, ...JSON.parse(localStorage.getItem(PREF_KEY)) }; }
  catch { return { ...defaults }; }
}
function savePrefs(p) { localStorage.setItem(PREF_KEY, JSON.stringify(p)); }

const FONTS = {
  song: '"Noto Serif SC","SimSun","宋体",Georgia,serif',
  hei:  '"PingFang SC","Microsoft YaHei","微软雅黑",sans-serif',
  kai:  '"KaiTi","楷体","STKaiti",Georgia,serif',
};

function applyPrefs(p) {
  const body = document.getElementById('readerBody');
  body.dataset.theme = p.theme;
  body.style.setProperty('--read-size',   p.fontSize + 'px');
  body.style.setProperty('--read-lh',     p.lineHeight);
  body.style.setProperty('--read-font',   FONTS[p.font] || FONTS.song);
  document.getElementById('fsValue').textContent = p.fontSize;
  document.getElementById('lhValue').textContent = p.lineHeight;
  document.querySelectorAll('.theme-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.theme === p.theme));
  document.querySelectorAll('.font-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.font === p.font));
}

// ── Init ────────────────────────────────────────────────────────────
const prefs = loadPrefs();
applyPrefs(prefs);

// ── Sidebar ──────────────────────────────────────────────────────────
const sidebar  = document.getElementById('readerSidebar');
const overlay  = document.getElementById('sidebarOverlay');

function openSidebar() {
  sidebar.classList.add('open');
  overlay.classList.add('active');
  // scroll active chapter into view
  const active = sidebar.querySelector('.sb-chap-item.active');
  if (active) active.scrollIntoView({ block: 'center' });
}
function closeSidebar() {
  sidebar.classList.remove('open');
  overlay.classList.remove('active');
}

document.getElementById('btnToggleSidebar').addEventListener('click', openSidebar);
document.getElementById('btnCloseSidebar').addEventListener('click', closeSidebar);
overlay.addEventListener('click', closeSidebar);

document.getElementById('sbSearch').addEventListener('input', function () {
  const q = this.value.toLowerCase();
  document.querySelectorAll('#sbChapList .sb-chap-item').forEach(li => {
    li.style.display = li.dataset.title.toLowerCase().includes(q) ? '' : 'none';
  });
});

// ── Settings panel ───────────────────────────────────────────────────
const settingsPanel = document.getElementById('settingsPanel');

document.getElementById('btnSettings').addEventListener('click', () =>
  settingsPanel.classList.toggle('open'));
document.getElementById('btnCloseSettings').addEventListener('click', () =>
  settingsPanel.classList.remove('open'));

// Font size
document.getElementById('fsPlus').addEventListener('click', () => {
  if (prefs.fontSize >= 28) return;
  prefs.fontSize += 1; applyPrefs(prefs); savePrefs(prefs);
});
document.getElementById('fsMinus').addEventListener('click', () => {
  if (prefs.fontSize <= 14) return;
  prefs.fontSize -= 1; applyPrefs(prefs); savePrefs(prefs);
});

// Line height
document.getElementById('lhPlus').addEventListener('click', () => {
  if (prefs.lineHeight >= 2.8) return;
  prefs.lineHeight = Math.round((prefs.lineHeight + 0.1) * 10) / 10;
  applyPrefs(prefs); savePrefs(prefs);
});
document.getElementById('lhMinus').addEventListener('click', () => {
  if (prefs.lineHeight <= 1.4) return;
  prefs.lineHeight = Math.round((prefs.lineHeight - 0.1) * 10) / 10;
  applyPrefs(prefs); savePrefs(prefs);
});

// Theme buttons
document.querySelectorAll('.theme-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    prefs.theme = btn.dataset.theme;
    applyPrefs(prefs); savePrefs(prefs);
  });
});

// Font buttons
document.querySelectorAll('.font-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    prefs.font = btn.dataset.font;
    applyPrefs(prefs); savePrefs(prefs);
  });
});

// ── Reading progress bar ─────────────────────────────────────────────
const progressBar = document.getElementById('readProgress');
function updateProgress() {
  const doc  = document.documentElement;
  const pct  = doc.scrollTop / (doc.scrollHeight - doc.clientHeight) * 100;
  progressBar.style.width = Math.min(100, pct) + '%';
}
window.addEventListener('scroll', updateProgress, { passive: true });
updateProgress();

// ── Auto-hide header on scroll ────────────────────────────────────────
const header = document.getElementById('readerHeader');
let lastY = 0, ticking = false;
window.addEventListener('scroll', () => {
  if (!ticking) {
    requestAnimationFrame(() => {
      const y = window.scrollY;
      if (y > lastY + 10 && y > 120)      header.classList.add('hidden');
      else if (y < lastY - 10 || y < 60)  header.classList.remove('hidden');
      lastY = y; ticking = false;
    });
    ticking = true;
  }
}, { passive: true });

// Show header on mouse near top
document.addEventListener('mousemove', e => {
  if (e.clientY < 60) header.classList.remove('hidden');
});

// ── Keyboard shortcuts ────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  const prevLink = document.querySelector('.nav-prev');
  const nextLink = document.querySelector('.nav-next');
  if ((e.key === 'ArrowLeft'  || e.key === 'PageUp')   && prevLink) location.href = prevLink.href;
  if ((e.key === 'ArrowRight' || e.key === 'PageDown') && nextLink) location.href = nextLink.href;
  if (e.key === 'Escape') { closeSidebar(); settingsPanel.classList.remove('open'); }
});
