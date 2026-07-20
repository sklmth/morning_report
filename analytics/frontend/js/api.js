/**
 * Analytics API 调用封装
 * 所有请求走相对路径 /api/，由 nginx 代理到内部 FastAPI
 */

const BASE = '/api';

async function _fetch(path, opts = {}) {
  const res = await fetch(BASE + path, opts);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${path} failed: ${res.status} ${text}`);
  }
  return res.json();
}

const Api = {
  getMonths: () => _fetch('/months'),
  getOverview: (month) => _fetch(`/overview${month ? '?month=' + month : ''}`),
  getSnapshots: (limit = 100) => _fetch(`/snapshots?limit=${limit}`),
  getScoreStructure: (month) => _fetch(`/analysis/score-structure?month=${month}`),
  getProgress: (month) => _fetch(`/analysis/progress?month=${month}`),
  getPersonEfficiency: (month) => _fetch(`/analysis/person-efficiency?month=${month}`),
  getBranchCompare: (month) => _fetch(`/analysis/branch-compare?month=${month}`),
  getRiskAlerts: (month) => _fetch(`/analysis/risk-alerts?month=${month}`),
  getTrend: (months = 6) => _fetch(`/analysis/trend?months=${months}`),

  uploadFiles: async (files) => {
    const form = new FormData();
    for (const f of files) form.append('files', f);
    const res = await fetch(BASE + '/upload', { method: 'POST', body: form });
    if (!res.ok) throw new Error('上传失败');
    return res.json();
  },

  exportExcel: (month) => {
    window.location.href = BASE + `/export/excel?month=${month}`;
  },
};
