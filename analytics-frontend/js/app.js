/**
 * 主应用逻辑 v2 — 仅分析14个政企客户经理
 */
(function () {
  'use strict';

  let currentMonth = null;

  // ── 工具函数 ───────────────────────────────────────────────────────────────
  function showToast(msg, dur = 2500) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.remove('hidden');
    setTimeout(() => t.classList.add('hidden'), dur);
  }

  function fmt(v, decimals = 0) {
    if (v == null || isNaN(v)) return '-';
    return parseFloat(v).toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  // ── 月份选择器 ─────────────────────────────────────────────────────────────
  async function initMonthSelect() {
    try {
      const { months } = await Api.getMonths();
      const sel = document.getElementById('month-select');
      sel.innerHTML = '';
      if (!months || !months.length) {
        sel.innerHTML = '<option value="">暂无数据</option>';
        return;
      }
      months.forEach((m, i) => {
        const opt = document.createElement('option');
        opt.value = m; opt.textContent = m;
        if (i === 0) opt.selected = true;
        sel.appendChild(opt);
      });
      currentMonth = months[0];
    } catch (e) {
      console.error('initMonthSelect', e);
    }
  }

  // ── KPI 卡片 ───────────────────────────────────────────────────────────────
  function renderKpiCards(containerId, cards) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = cards.map(({ label, value, sub, color }) => `
      <div class="kpi-card ${color || ''}">
        <div class="kpi-label">${label}</div>
        <div class="kpi-value">${value}</div>
        ${sub ? `<div class="kpi-sub">${sub}</div>` : ''}
      </div>
    `).join('');
  }

  // ── 总览 ───────────────────────────────────────────────────────────────────
  async function loadOverview() {
    if (!currentMonth) return;
    try {
      const [ov, pe, sc] = await Promise.all([
        Api.getOverview(currentMonth),
        Api.getPersonEfficiency(currentMonth).catch(() => ({})),
        Api.getScoreStructure(currentMonth).catch(() => ({})),
      ]);

      if (!ov.has_data) {
        document.getElementById('kpi-cards').innerHTML =
          '<div class="loading-mask">暂无该月份数据，请点击右上角「上传数据」导入Excel</div>';
        return;
      }

      renderKpiCards('kpi-cards', [
        { label: '数据截至', value: ov.latest_date || '-' },
        { label: '团队净增积分', value: fmt(ov.net_pts, 0), sub: '分（端州政企）', color: ov.net_pts >= 0 ? 'success' : 'danger' },
        { label: '积分完成（14人）', value: fmt(ov.team_pts_done, 0), sub: '分（col13合计）' },
        { label: '积分落格率', value: (ov.completion_rate || 0) + '%', sub: '相对时间进度', color: ov.completion_rate >= 90 ? 'success' : ov.completion_rate >= 70 ? '' : 'danger' },
        { label: '团队总高套', value: fmt(ov.total_gaotao, 1), sub: '户（政企认领口径）' },
        { label: '人均激励', value: '¥' + fmt(ov.avg_incentive, 0), sub: '元/人', color: 'accent' },
        { label: '团队总激励', value: '¥' + fmt(ov.total_incentive, 0), sub: '元（14人合计）', color: 'accent' },
      ]);

      Charts.renderOverviewPts('overview-pts-chart', sc);
      Charts.renderOverviewGaotao('overview-gaotao-chart', pe.wanmei_staff || []);
    } catch (e) {
      console.error('loadOverview', e);
      showToast('加载失败: ' + e.message);
    }
  }

  // ── 人员业绩（核心页面）──────────────────────────────────────────────────
  async function loadPerson() {
    if (!currentMonth) return;
    try {
      const data = await Api.getPersonEfficiency(currentMonth);
      // 激励排名 — 核心图表
      Charts.renderPersonIncentive('person-incentive-chart', data.staff_efficiency || [], data.wanmei_staff || []);
      // 散点图 — 揽装积分 vs 高套
      Charts.renderPersonScatter('person-scatter-chart', data.staff_efficiency || [], data.wanmei_staff || []);
      // 高套+网关分布
      Charts.renderPersonGaotao('person-gaotao-chart', data.wanmei_staff || []);
    } catch (e) {
      showToast('人员业绩加载失败: ' + e.message);
    }
  }

  // ── 积分结构 ──────────────────────────────────────────────────────────────
  async function loadScore() {
    if (!currentMonth) return;
    try {
      const [scoreData, overviewData] = await Promise.all([
        Api.getScoreStructure(currentMonth),
        Api.getOverview(currentMonth),
      ]);
      // 积分饼图优先用overview的直接数据（更准确的净增积分分项）
      Charts.renderScorePie('score-pie-chart', { ...scoreData, ...overviewData });
      Charts.renderScoreDistrictBar('score-district-bar', scoreData.all_districts || []);
    } catch (e) { showToast('积分结构加载失败'); }
  }

  // ── 完成进度 ──────────────────────────────────────────────────────────────
  async function loadProgress() {
    if (!currentMonth) return;
    try {
      const data = await Api.getProgress(currentMonth);
      if (!data.has_data) {
        document.getElementById('progress-kpi-cards').innerHTML =
          '<div class="loading-mask">暂无进度数据</div>';
        return;
      }
      const fc = data.pts_forecast || {};
      renderKpiCards('progress-kpi-cards', [
        { label: '时间进度', value: data.time_progress + '%' },
        { label: '剩余天数', value: data.remaining_days + '天' },
        { label: '当前净增积分', value: fmt(fc.current, 0), sub: '分', color: fc.current >= 0 ? 'success' : 'danger' },
        { label: '日均积分', value: fmt(fc.daily_avg_actual, 1), sub: '分/天' },
        { label: '预测月末', value: fmt(fc.projected_month_end, 0), sub: '分（线性外推）' },
      ]);
      Charts.renderProgressBar('progress-bar-chart', data);
    } catch (e) { showToast('进度预测加载失败'); }
  }

  // ── 县分对比 ──────────────────────────────────────────────────────────────
  async function loadCompare() {
    if (!currentMonth) return;
    try {
      const data = await Api.getBranchCompare(currentMonth);
      Charts.renderBranchRank('branch-rank-chart', data.branches || []);
      Charts.renderBranchMultiBar('branch-multi-bar', data.branches || []);
    } catch (e) { showToast('县分对比加载失败'); }
  }

  // ── 风险预警 ──────────────────────────────────────────────────────────────
  async function loadRisk() {
    if (!currentMonth) return;
    try {
      const data = await Api.getRiskAlerts(currentMonth);
      const alerts = data.alerts || [];
      const el = document.getElementById('alert-cards');
      if (!alerts.length) {
        el.innerHTML = `<div class="alert-card green">
          <span class="alert-icon">✅</span>
          <div class="alert-body"><div class="title">当前无风险预警</div>
          <div class="desc">积分结构健康，各指标在合理范围内</div></div></div>`;
      } else {
        el.innerHTML = alerts.map(a => `
          <div class="alert-card ${a.level}">
            <span class="alert-icon">${a.level === 'red' ? '🔴' : '🟡'}</span>
            <div class="alert-body"><div class="title">${a.type}</div>
            <div class="desc">${a.desc}</div></div>
            <span class="alert-badge">${a.value}</span>
          </div>`).join('');
      }
      Charts.renderRiskRatio('risk-ratio-chart', data);
      Charts.renderRiskHistory('risk-history-chart', data.historical_trend || []);
    } catch (e) { showToast('风险预警加载失败'); }
  }

  // ── 趋势 ──────────────────────────────────────────────────────────────────
  async function loadTrend() {
    try {
      const data = await Api.getTrend(12);
      Charts.renderTrendPts('trend-pts-chart', data.pts_trend || []);
      Charts.renderTrendGaotao('trend-gaotao-chart', data.gaotao_trend || []);
    } catch (e) { showToast('趋势加载失败'); }
  }

  // ── 快照列表 ──────────────────────────────────────────────────────────────
  async function loadSnapshots() {
    try {
      const rows = await Api.getSnapshots(200);
      const tbody = document.getElementById('snapshots-body');
      if (!rows.length) { tbody.innerHTML = '<tr><td colspan="7">暂无数据</td></tr>'; return; }
      tbody.innerHTML = rows.map(r => `<tr>
        <td>${r.id}</td><td>${r.data_date}</td><td>${r.month}</td>
        <td class="tag-${r.source_type}">${r.source_type === 'wanmei' ? '完美一单' : '营服报表'}</td>
        <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${r.source_file}">${r.source_file}</td>
        <td>${(r.processed_at || '').slice(0, 19)}</td>
        <td><span class="badge badge-${r.trigger_by === 'watch' ? 'green' : 'orange'}">${
          {watch:'自动',upload:'上传',manual:'手动',initial:'初始',fix:'修复'}[r.trigger_by]||r.trigger_by
        }</span></td>
      </tr>`).join('');
    } catch (e) { showToast('快照加载失败'); }
  }

  // ── Tab 切换 ──────────────────────────────────────────────────────────────
  const LOADERS = { overview: loadOverview, person: loadPerson, score: loadScore,
    progress: loadProgress, compare: loadCompare, risk: loadRisk,
    trend: loadTrend, snapshots: loadSnapshots };

  function switchTab(tab) {
    document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.tab === tab));
    document.querySelectorAll('.tab-panel').forEach(el => el.classList.toggle('hidden', el.id !== 'tab-' + tab));
    if (LOADERS[tab]) LOADERS[tab]();
  }

  // ── 上传弹窗 ──────────────────────────────────────────────────────────────
  function initUpload() {
    const modal = document.getElementById('upload-modal');
    const results = document.getElementById('upload-results');
    document.getElementById('upload-btn').addEventListener('click', () => { modal.classList.remove('hidden'); results.innerHTML = ''; });
    document.getElementById('upload-close-btn').addEventListener('click', () => { modal.classList.add('hidden'); initMonthSelect().then(loadOverview); });
    modal.addEventListener('click', e => { if (e.target === modal) modal.classList.add('hidden'); });

    async function handle(files) {
      results.innerHTML = '<div class="loading-mask"><span class="spinner">⟳</span>解析中…</div>';
      try {
        const { results: res } = await Api.uploadFiles(Array.from(files));
        results.innerHTML = res.map(r => `<div class="upload-result-row ${r.status==='ok'?'ok':'error'}">${r.status==='ok'?'✅':'❌'} ${r.file}：${r.msg}</div>`).join('');
        showToast(`处理完成，${res.length}个文件`);
        await initMonthSelect();
      } catch (e) { results.innerHTML = `<div class="upload-result-row error">上传失败: ${e.message}</div>`; }
    }

    document.getElementById('file-input').addEventListener('change', e => handle(e.target.files));
    const dz = document.getElementById('drop-zone');
    dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag-over'); });
    dz.addEventListener('dragleave', () => dz.classList.remove('drag-over'));
    dz.addEventListener('drop', e => { e.preventDefault(); dz.classList.remove('drag-over'); handle(e.dataTransfer.files); });
  }

  // ── 初始化 ────────────────────────────────────────────────────────────────
  async function init() {
    await initMonthSelect();
    document.querySelectorAll('.nav-item').forEach(el => el.addEventListener('click', () => switchTab(el.dataset.tab)));
    document.getElementById('month-select').addEventListener('change', e => { currentMonth = e.target.value; switchTab(document.querySelector('.nav-item.active')?.dataset.tab || 'overview'); });
    document.getElementById('refresh-btn').addEventListener('click', () => { switchTab(document.querySelector('.nav-item.active')?.dataset.tab || 'overview'); showToast('已刷新'); });
    document.getElementById('export-btn').addEventListener('click', () => { if (currentMonth) Api.exportExcel(currentMonth); });
    initUpload();
    switchTab('overview');
  }

  document.addEventListener('DOMContentLoaded', init);
})();
