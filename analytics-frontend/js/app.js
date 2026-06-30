/**
 * 主应用逻辑：Tab 切换、数据加载、UI 交互
 */

(function () {
  'use strict';

  // ── 状态 ───────────────────────────────────────────────────────────────────
  let currentMonth = null;
  let loadedTabs = new Set();

  // ── 工具函数 ───────────────────────────────────────────────────────────────
  function showToast(msg, dur = 2500) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.remove('hidden');
    setTimeout(() => t.classList.add('hidden'), dur);
  }

  function setLoading(containerId, msg = '加载中…') {
    const el = document.getElementById(containerId);
    if (el) el.innerHTML = `<div class="loading-mask"><span class="spinner">⟳</span>${msg}</div>`;
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

  // ── KPI 卡片渲染 ─────────────────────────────────────────────────────────
  function renderKpiCards(containerId, cards) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = cards.map(({ label, value, sub, color }) => `
      <div class="kpi-card ${color || ''}">
        <div class="label">${label}</div>
        <div class="value">${value}</div>
        ${sub ? `<div class="sub">${sub}</div>` : ''}
      </div>
    `).join('');
  }

  // ── 总览 ─────────────────────────────────────────────────────────────────
  async function loadOverview() {
    if (!currentMonth) return;
    try {
      const [overviewData, personData, scoreData] = await Promise.all([
        Api.getOverview(currentMonth),
        Api.getPersonEfficiency(currentMonth).catch(() => ({})),
        Api.getScoreStructure(currentMonth).catch(() => ({})),
      ]);

      if (!overviewData.has_data) {
        document.getElementById('kpi-cards').innerHTML =
          '<div class="loading-mask">暂无该月份数据，请上传 Excel 文件</div>';
        return;
      }

      renderKpiCards('kpi-cards', [
        { label: '数据截至', value: overviewData.latest_date || '-', color: '' },
        { label: '净增积分', value: fmt(overviewData.net_pts, 0), sub: '分', color: overviewData.net_pts >= 0 ? 'green' : 'red' },
        { label: '增量积分', value: fmt(overviewData.inc_pts, 0), sub: '分', color: '' },
        { label: '总高套数', value: fmt(overviewData.total_gaotao, 0), sub: '户', color: '' },
        { label: '人均激励', value: '¥' + fmt(overviewData.avg_incentive, 0), sub: '元/人', color: 'orange' },
        { label: '总激励', value: '¥' + fmt(overviewData.total_incentive, 0), sub: '元', color: '' },
        { label: '数据快照', value: overviewData.snapshot_count, sub: '次', color: '' },
      ]);

      Charts.renderOverviewPts('overview-pts-chart', scoreData);
      Charts.renderOverviewGaotao('overview-gaotao-chart', personData.wanmei_staff || []);
    } catch (e) {
      console.error('loadOverview', e);
      showToast('总览加载失败: ' + e.message);
    }
  }

  // ── 积分结构 ──────────────────────────────────────────────────────────────
  async function loadScore() {
    if (!currentMonth) return;
    try {
      const data = await Api.getScoreStructure(currentMonth);
      Charts.renderScorePie('score-pie-chart', data);
      Charts.renderScoreHealth('score-health-chart', data.health);
      Charts.renderScoreDistrictBar('score-district-bar', data.all_districts || []);
    } catch (e) {
      showToast('积分结构加载失败: ' + e.message);
    }
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
        { label: '时间进度', value: data.time_progress + '%', color: '' },
        { label: '剩余天数', value: data.remaining_days + '天', color: '' },
        { label: '当前净增积分', value: fmt(fc.current, 0), color: fc.current >= 0 ? 'green' : 'red' },
        { label: '日均积分', value: fmt(fc.daily_avg_actual, 1), sub: '分/天', color: '' },
        { label: '预测月末净增', value: fmt(fc.projected_month_end, 0), sub: '分（线性外推）', color: '' },
      ]);

      Charts.renderProgressBar('progress-bar-chart', data);
    } catch (e) {
      showToast('进度预测加载失败: ' + e.message);
    }
  }

  // ── 人员效能 ──────────────────────────────────────────────────────────────
  async function loadPerson() {
    if (!currentMonth) return;
    try {
      const data = await Api.getPersonEfficiency(currentMonth);
      Charts.renderPersonScatter('person-scatter-chart', data.staff_efficiency || []);
      Charts.renderPersonTier('person-tier-chart', data.incentive_tiers || []);
      Charts.renderCpPairs('cp-pairs-chart', data.cp_pairs || []);
    } catch (e) {
      showToast('人员效能加载失败: ' + e.message);
    }
  }

  // ── 县分对比 ──────────────────────────────────────────────────────────────
  async function loadCompare() {
    if (!currentMonth) return;
    try {
      const data = await Api.getBranchCompare(currentMonth);
      const branches = data.branches || [];
      Charts.renderBranchRank('branch-rank-chart', branches);
      Charts.renderBranchMultiBar('branch-multi-bar', branches);
    } catch (e) {
      showToast('县分对比加载失败: ' + e.message);
    }
  }

  // ── 风险预警 ──────────────────────────────────────────────────────────────
  async function loadRisk() {
    if (!currentMonth) return;
    try {
      const data = await Api.getRiskAlerts(currentMonth);
      const alerts = data.alerts || [];
      const alertsEl = document.getElementById('alert-cards');

      if (!alerts.length) {
        alertsEl.innerHTML = `
          <div class="alert-card green">
            <span class="alert-icon">✅</span>
            <div class="alert-body"><div class="title">当前无风险预警</div>
            <div class="desc">积分结构健康，各项指标在合理范围内</div></div>
          </div>`;
      } else {
        alertsEl.innerHTML = alerts.map(a => `
          <div class="alert-card ${a.level}">
            <span class="alert-icon">${a.level === 'red' ? '🔴' : '🟡'}</span>
            <div class="alert-body">
              <div class="title">${a.type}</div>
              <div class="desc">${a.desc}</div>
            </div>
            <span class="alert-badge">${a.value}</span>
          </div>`).join('');
      }

      Charts.renderRiskRatio('risk-ratio-chart', data);
      Charts.renderRiskHistory('risk-history-chart', data.historical_trend || []);
    } catch (e) {
      showToast('风险预警加载失败: ' + e.message);
    }
  }

  // ── 历史趋势 ──────────────────────────────────────────────────────────────
  async function loadTrend() {
    try {
      const data = await Api.getTrend(12);
      Charts.renderTrendPts('trend-pts-chart', data.pts_trend || []);
      Charts.renderTrendGaotao('trend-gaotao-chart', data.gaotao_trend || []);
    } catch (e) {
      showToast('历史趋势加载失败: ' + e.message);
    }
  }

  // ── 数据快照列表 ──────────────────────────────────────────────────────────
  async function loadSnapshots() {
    try {
      const rows = await Api.getSnapshots(200);
      const tbody = document.getElementById('snapshots-body');
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="7">暂无数据</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map(r => `
        <tr>
          <td>${r.id}</td>
          <td>${r.data_date}</td>
          <td>${r.month}</td>
          <td class="tag-${r.source_type}">${r.source_type === 'wanmei' ? '完美一单' : '营服报表'}</td>
          <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${r.source_file}">${r.source_file}</td>
          <td>${r.processed_at ? r.processed_at.slice(0, 19) : '-'}</td>
          <td><span class="badge badge-${r.trigger_by === 'watch' ? 'green' : r.trigger_by === 'upload' ? 'orange' : 'green'}">${
            { watch: '自动', upload: '上传', manual: '手动', auto: '自动' }[r.trigger_by] || r.trigger_by
          }</span></td>
        </tr>`).join('');
    } catch (e) {
      showToast('快照列表加载失败: ' + e.message);
    }
  }

  // ── Tab 切换 ──────────────────────────────────────────────────────────────
  const TAB_LOADERS = {
    overview: loadOverview,
    score: loadScore,
    progress: loadProgress,
    person: loadPerson,
    compare: loadCompare,
    risk: loadRisk,
    trend: loadTrend,
    snapshots: loadSnapshots,
  };

  function switchTab(tab) {
    document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.tab === tab));
    document.querySelectorAll('.tab-panel').forEach(el => {
      const id = el.id.replace('tab-', '');
      el.classList.toggle('hidden', id !== tab);
    });
    const loader = TAB_LOADERS[tab];
    if (loader) loader();
  }

  // ── 上传弹窗 ──────────────────────────────────────────────────────────────
  function initUploadModal() {
    const modal = document.getElementById('upload-modal');
    const closeBtn = document.getElementById('upload-close-btn');
    const fileInput = document.getElementById('file-input');
    const dropZone = document.getElementById('drop-zone');
    const resultsEl = document.getElementById('upload-results');

    document.getElementById('upload-btn').addEventListener('click', () => {
      modal.classList.remove('hidden');
      resultsEl.innerHTML = '';
    });
    closeBtn.addEventListener('click', () => {
      modal.classList.add('hidden');
      // 上传完成后刷新月份列表
      initMonthSelect().then(() => loadOverview());
    });
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.add('hidden'); });

    async function handleFiles(files) {
      resultsEl.innerHTML = '<div class="loading-mask"><span class="spinner">⟳</span>上传处理中…</div>';
      try {
        const { results } = await Api.uploadFiles(Array.from(files));
        resultsEl.innerHTML = results.map(r =>
          `<div class="upload-result-row ${r.status === 'ok' ? 'ok' : 'error'}">
            ${r.status === 'ok' ? '✅' : '❌'} ${r.file}：${r.msg}
          </div>`
        ).join('');
        showToast(`处理完成，共 ${results.length} 个文件`);
        await initMonthSelect();
      } catch (e) {
        resultsEl.innerHTML = `<div class="upload-result-row error">上传失败: ${e.message}</div>`;
      }
    }

    fileInput.addEventListener('change', () => handleFiles(fileInput.files));
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault(); dropZone.classList.remove('drag-over');
      handleFiles(e.dataTransfer.files);
    });
  }

  // ── 主初始化 ──────────────────────────────────────────────────────────────
  async function init() {
    await initMonthSelect();

    document.querySelectorAll('.nav-item').forEach(el => {
      el.addEventListener('click', () => switchTab(el.dataset.tab));
    });

    document.getElementById('month-select').addEventListener('change', (e) => {
      currentMonth = e.target.value;
      loadedTabs.clear();
      // 重新加载当前 Tab
      const activeTab = document.querySelector('.nav-item.active')?.dataset.tab || 'overview';
      switchTab(activeTab);
    });

    document.getElementById('refresh-btn').addEventListener('click', () => {
      loadedTabs.clear();
      const activeTab = document.querySelector('.nav-item.active')?.dataset.tab || 'overview';
      switchTab(activeTab);
      showToast('已刷新');
    });

    document.getElementById('export-btn').addEventListener('click', () => {
      if (!currentMonth) { showToast('请先选择月份'); return; }
      Api.exportExcel(currentMonth);
      showToast('正在生成Excel，请稍候…');
    });

    initUploadModal();

    // 加载默认 Tab
    switchTab('overview');
  }

  document.addEventListener('DOMContentLoaded', init);
})();
