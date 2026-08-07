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
    sendRules: (body) => post('/report/send-rules', body),
    sendCustom: (body) => post('/report/send-custom', body),
    uploadPic:  (body) => post('/upload-pic', body),
    recipientOptions: () => req('/config/recipients'),

    // 调度器
    schedulerStatus: () => req('/scheduler/status'),
    startScheduler:  () => post('/scheduler/start', {}),
    stopScheduler:   () => post('/scheduler/stop', {}),
    triggerJob: (id) => post(`/scheduler/trigger/${id}`, {}),

    // 配置/名单
    roster: () => req('/config/roster'),

    // 运行日志
    sendLogs: (limit=20, offset=0) => req(`/send-logs?limit=${limit}&offset=${offset}`),

    // 应用设置
    settings:     () => req('/config/settings'),
    saveSettings: (body) => post('/config/settings', body),

    // 专项业绩
    perfStats:       (month, p = {}) => {
      const q = new URLSearchParams();
      if (p.left_date) q.set('left_date', p.left_date);
      if (p.right_date) q.set('right_date', p.right_date);
      const qs = q.toString();
      return req(`/performance/stats/${encodeURIComponent(month)}${qs?'?'+qs:''}`);
    },
    perfUpload:      (formData) => fetch('/api/performance/upload', {method:'POST', body:formData})
                       .then(r => r.json().then(b => { if (!r.ok) throw new Error(b.detail || `上传失败 ${r.status}`); return b; })),
    perfExport:      (month, uploadId) => { window.open(`/api/performance/stats/${encodeURIComponent(month)}/export?upload_id=${uploadId}`, '_blank'); },
    perfAwardConfigs:(month) => req(`/performance/award-configs/${encodeURIComponent(month)}`),
    saveAwardConfig: (body) => post('/performance/award-configs', body),
    deleteAwardConfig:(id)  => req(`/performance/award-configs/${id}`, {method:'DELETE'}),
    dispatchPerf:    (body) => post('/performance/dispatch', body),
    manualPerfPrize: (body) => post('/performance/manual-prize', body),
    revokeDispatch:  (id)   => post(`/performance/dispatch/${id}/revoke`, {}),
    perfDispatches:  (month) => req(`/performance/dispatches/${encodeURIComponent(month)}`),
  };
})();
