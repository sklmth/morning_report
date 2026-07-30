const Api = (() => {
  const base = '/api';
  async function request(path, options = {}) {
    const response = await fetch(base + path, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `请求失败：${response.status}`);
    return body;
  }
  const json = (method, path, body, token) => request(path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { 'X-Admin-Token': token } : {}) },
    body: JSON.stringify(body),
  });
  return {
    summary: (date) => request(`/summary?date=${encodeURIComponent(date)}`),
    records: (date) => request(`/records?date=${encodeURIComponent(date)}`),
    rules: () => request('/config/rules'),
    roster: () => request('/config/roster'),
    logs: () => request('/send-logs'),
    preview: (body) => json('POST', '/report/preview', body),
    send: (body, token) => json('POST', '/report/send', body, token),
  };
})();
