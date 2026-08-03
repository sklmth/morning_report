// ===== API 工具层 =====
const Api = (() => {
  const base = '/api';

  async function req(path, opts = {}) {
    const res = await fetch(base + path, opts);
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || `请求失败 ${res.status}`);
    return body;
  }

  const post = (path, data) => req(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  return {
    // 今日预约
    summary: (date) => req(`/summary?date=${encodeURIComponent(date)}`),
    records: (date) => req(`/records?date=${encodeURIComponent(date)}`),

    // 统计
    cumulativeStats: (p = {}) => {
      const q = new URLSearchParams();
      if (p.start_date) q.set('start_date', p.start_date);
      if (p.end_date)   q.set('end_date',   p.end_date);
      return req(`/statistics/cumulative?${q}`);
    },
    exportExcel: (p = {}) => {
      const q = new URLSearchParams();
      if (p.start_date) q.set('start_date', p.start_date);
      if (p.end_date)   q.set('end_date',   p.end_date);
      window.open(`${base}/statistics/export?${q}`, '_blank');
    },

    // 发送通报
    rules:   () => req('/config/rules'),
    preview: (body) => post('/report/preview', body),
    send:    (body) => post('/report/send', body),

    // 调度器
    schedulerStatus: () => req('/scheduler/status'),
    startScheduler:  () => post('/scheduler/start', {}),
    stopScheduler:   () => post('/scheduler/stop', {}),
    triggerJob: (id) => post(`/scheduler/trigger/${id}`, {}),

    // 配置/名单
    roster: () => req('/config/roster'),

    // 运行日志
    sendLogs: (limit=100) => req(`/send-logs?limit=${limit}`),

    // 应用设置
    settings:     () => req('/config/settings'),
    saveSettings: (body) => post('/config/settings', body),
  };
})();
