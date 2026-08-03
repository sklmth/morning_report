const Api = (() => {
  const base = '/api';

  async function request(path, options = {}) {
    const response = await fetch(base + path, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `请求失败：${response.status}`);
    return body;
  }

  const json = (method, path, body) => request(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  return {
    // 原有API
    summary: (date) => request(`/summary?date=${encodeURIComponent(date)}`),
    records: (date) => request(`/records?date=${encodeURIComponent(date)}`),
    rules: () => request('/config/rules'),
    roster: () => request('/config/roster'),
    logs: () => request('/send-logs'),
    preview: (body) => json('POST', '/report/preview', body),
    send: (body) => json('POST', '/report/send', body),

    // 新增API - 累计统计
    statistics: (params = {}) => {
      const query = new URLSearchParams();
      if (params.start_date) query.set('start_date', params.start_date);
      if (params.end_date) query.set('end_date', params.end_date);
      if (params.fill_status) query.set('fill_status', params.fill_status);
      if (params.manager_name) query.set('manager_name', params.manager_name);
      return request(`/statistics/details?${query}`);
    },

    cumulativeStats: (params = {}) => {
      const query = new URLSearchParams();
      if (params.start_date) query.set('start_date', params.start_date);
      if (params.end_date) query.set('end_date', params.end_date);
      return request(`/statistics/cumulative?${query}`);
    },

    exportExcel: (params = {}) => {
      const query = new URLSearchParams();
      if (params.start_date) query.set('start_date', params.start_date);
      if (params.end_date) query.set('end_date', params.end_date);
      const url = `${base}/statistics/export?${query}`;
      // 触发文件下载
      window.open(url, '_blank');
    },

    // 新增API - 提醒日志
    reminders: (params = {}) => {
      const query = new URLSearchParams();
      if (params.date) query.set('date', params.date);
      if (params.manager_name) query.set('manager_name', params.manager_name);
      return request(`/reminders/logs?${query}`);
    },

    // 新增API - 调度器管理
    schedulerStatus: () => request('/scheduler/status'),
    startScheduler: () => json('POST', '/scheduler/start', {}),
    stopScheduler: () => json('POST', '/scheduler/stop', {}),
    triggerJob: (jobId) => json('POST', `/scheduler/trigger/${jobId}`, {}),

    // 新增API - 交付人员配置
    deliveryStaff: () => request('/config/delivery-staff'),
  };
})();
