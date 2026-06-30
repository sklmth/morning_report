/**
 * ECharts 图表渲染模块
 * 每个函数接收数据，渲染到指定 DOM id
 */

const Charts = (() => {
  const instances = {};

  function _init(id) {
    if (instances[id]) instances[id].dispose();
    const el = document.getElementById(id);
    if (!el) return null;
    instances[id] = echarts.init(el, null, { renderer: 'canvas' });
    return instances[id];
  }

  const COLOR_PRIMARY = ['#1F4E79','#2E75B6','#5BA3D0','#A8CCE8','#E2A317','#C55A11','#375623','#70AD47'];
  const COLOR_HEALTH  = ['#C00000','#E2A317','#375623'];

  // ── 总览：积分结构简要饼图 ──────────────────────────────────────────────────
  function renderOverviewPts(id, data) {
    const c = _init(id);
    if (!c) return;
    const dz = data.duanzhou || {};
    c.setOption({
      title: { text: '积分来源构成', left: 'center', top: 8, textStyle: { fontSize: 13, color: '#1F4E79' } },
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { bottom: 0, textStyle: { fontSize: 11 } },
      series: [{
        type: 'pie', radius: ['40%', '65%'], center: ['50%', '50%'],
        data: [
          { name: '基本面', value: Math.max(0, dz.base_pts || 0) },
          { name: '双线', value: Math.max(0, dz.twin_pts || 0) },
          { name: '其他业务', value: Math.max(0, dz.other_pts || 0) },
        ].filter(d => d.value > 0),
        color: COLOR_PRIMARY,
        label: { formatter: '{b}\n{d}%', fontSize: 11 },
      }]
    });
  }

  // ── 总览：高套人员分布柱图 ──────────────────────────────────────────────────
  function renderOverviewGaotao(id, wanmeiStaff) {
    const c = _init(id);
    if (!c || !wanmeiStaff?.length) return;
    const sorted = [...wanmeiStaff].sort((a, b) => ((b.new_gaotao||0)+(b.stock_gaotao||0)) - ((a.new_gaotao||0)+(a.stock_gaotao||0)));
    const top = sorted.slice(0, 12);
    c.setOption({
      title: { text: '人员高套完成（月累）', left: 'center', top: 8, textStyle: { fontSize: 13, color: '#1F4E79' } },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, textStyle: { fontSize: 11 } },
      grid: { left: 60, right: 20, top: 40, bottom: 50 },
      xAxis: { type: 'category', data: top.map(d => d.name), axisLabel: { fontSize: 11, rotate: 30 } },
      yAxis: { type: 'value', name: '户', nameTextStyle: { fontSize: 11 } },
      series: [
        { name: '新增高套', type: 'bar', stack: 'g', data: top.map(d => d.new_gaotao || 0), color: '#1F4E79' },
        { name: '存量高套', type: 'bar', stack: 'g', data: top.map(d => d.stock_gaotao || 0), color: '#70AD47' },
      ]
    });
  }

  // ── 积分结构：多维饼图 ─────────────────────────────────────────────────────
  function renderScorePie(id, data) {
    const c = _init(id);
    if (!c) return;
    const dz = data.duanzhou || {};
    const flow = [
      { name: '到期积分', value: Math.abs(dz.base_expire || 0) },
      { name: '降值积分', value: Math.abs(dz.base_decline || 0) },
      { name: '拆机积分', value: Math.abs(dz.base_churn || 0) },
    ];
    c.setOption({
      title: { text: '积分结构分析（端州）', left: 'center', top: 6, textStyle: { fontSize: 13, color: '#1F4E79' } },
      tooltip: { trigger: 'item', formatter: '{b}: {c}分 ({d}%)' },
      legend: { bottom: 4, textStyle: { fontSize: 11 } },
      series: [{
        type: 'pie', radius: ['35%', '60%'], center: ['50%', '50%'],
        data: [
          { name: '基本面', value: Math.max(0, dz.base_pts || 0) },
          { name: '  移动', value: Math.max(0, dz.base_mobile || 0) },
          { name: '  宽带', value: Math.max(0, dz.base_bb || 0) },
          { name: '双线', value: Math.max(0, dz.twin_pts || 0) },
          { name: '  互专', value: Math.max(0, dz.twin_inet || 0) },
          { name: '  组网', value: Math.max(0, dz.twin_net || 0) },
          { name: '其他', value: Math.max(0, dz.other_pts || 0) },
        ].filter(d => d.value > 0),
        color: COLOR_PRIMARY,
        label: { formatter: '{b}\n{d}%', fontSize: 10 },
      }]
    });
  }

  // ── 积分结构：健康度仪表盘 ─────────────────────────────────────────────────
  function renderScoreHealth(id, health) {
    const c = _init(id);
    if (!c) return;
    c.setOption({
      title: { text: '存量流失健康度', left: 'center', top: 6, textStyle: { fontSize: 13, color: '#1F4E79' } },
      tooltip: { formatter: '{a} <br/>{b}: {c}%' },
      series: [
        {
          name: '拆机占比', type: 'gauge', center: ['16%', '55%'], radius: '45%',
          min: 0, max: 60,
          axisLine: { lineStyle: { width: 8, color: [[0.3, '#375623'], [0.5, '#E2A317'], [1, '#C00000']] } },
          pointer: { length: '60%' }, detail: { formatter: '{value}%', fontSize: 12 },
          title: { fontSize: 11, offsetCenter: [0, '80%'] },
          data: [{ value: health?.churn_ratio || 0, name: '拆机占比' }]
        },
        {
          name: '降值占比', type: 'gauge', center: ['50%', '55%'], radius: '45%',
          min: 0, max: 50,
          axisLine: { lineStyle: { width: 8, color: [[0.25, '#375623'], [0.5, '#E2A317'], [1, '#C00000']] } },
          pointer: { length: '60%' }, detail: { formatter: '{value}%', fontSize: 12 },
          title: { fontSize: 11, offsetCenter: [0, '80%'] },
          data: [{ value: health?.decline_ratio || 0, name: '降值占比' }]
        },
        {
          name: '到期占比', type: 'gauge', center: ['84%', '55%'], radius: '45%',
          min: 0, max: 80,
          axisLine: { lineStyle: { width: 8, color: [[0.4, '#375623'], [0.625, '#E2A317'], [1, '#C00000']] } },
          pointer: { length: '60%' }, detail: { formatter: '{value}%', fontSize: 12 },
          title: { fontSize: 11, offsetCenter: [0, '80%'] },
          data: [{ value: health?.expire_ratio || 0, name: '到期占比' }]
        }
      ]
    });
  }

  // ── 积分结构：各县分积分对比 ──────────────────────────────────────────────
  function renderScoreDistrictBar(id, allDistricts) {
    const c = _init(id);
    if (!c || !allDistricts?.length) return;
    const sorted = [...allDistricts].sort((a, b) => (b.net_pts || 0) - (a.net_pts || 0));
    c.setOption({
      title: { text: '全市各县分净增积分对比', left: 'center', top: 6, textStyle: { fontSize: 13, color: '#1F4E79' } },
      tooltip: { trigger: 'axis' },
      grid: { left: 90, right: 20, top: 40, bottom: 30 },
      xAxis: { type: 'value', name: '分', nameTextStyle: { fontSize: 11 } },
      yAxis: { type: 'category', data: sorted.map(d => d.district.replace('分公司', '').replace('(区县其它)', '')),
               axisLabel: { fontSize: 11 } },
      series: [
        { name: '净增积分', type: 'bar', data: sorted.map(d => +(d.net_pts || 0).toFixed(1)),
          itemStyle: { color: (p) => p.name.includes('端州') ? '#E2A317' : '#2E75B6' },
          label: { show: true, position: 'right', fontSize: 10 } },
      ]
    });
  }

  // ── 进度预测：人员进度横向条形图 ───────────────────────────────────────────
  function renderProgressBar(id, data) {
    const c = _init(id);
    if (!c) return;
    const people = data.person_progress || [];
    if (!people.length) return;
    const sorted = [...people].sort((a, b) => (b.inc_pts || 0) - (a.inc_pts || 0));
    const timeProg = data.time_progress || 0;
    c.setOption({
      title: { text: `人员积分完成进度（时间进度 ${timeProg}%）`, left: 'center', top: 6, textStyle: { fontSize: 13, color: '#1F4E79' } },
      tooltip: { trigger: 'axis', formatter: (params) => {
        const p = people.find(x => x.name === params[0]?.name || x.name === sorted[params[0]?.dataIndex]?.name);
        return p ? `${p.name}<br/>当前积分: ${p.inc_pts}<br/>预测月末: ${p.projected_pts_month}<br/>预计激励: ¥${p.predicted_incentive}` : '';
      }},
      legend: { bottom: 4, textStyle: { fontSize: 11 } },
      grid: { left: 60, right: 100, top: 40, bottom: 50 },
      xAxis: { type: 'value', name: '积分', nameTextStyle: { fontSize: 11 } },
      yAxis: { type: 'category', data: sorted.map(d => d.name), axisLabel: { fontSize: 11 } },
      series: [
        {
          name: '当前积分', type: 'bar',
          data: sorted.map(d => ({ value: +(d.inc_pts || 0).toFixed(1), itemStyle: {
            color: d.status === 'green' ? '#375623' : d.status === 'yellow' ? '#E2A317' : '#C00000'
          }})),
          label: { show: true, position: 'right', fontSize: 10,
            formatter: (p) => `${sorted[p.dataIndex]?.status === 'green' ? '✓' : sorted[p.dataIndex]?.status === 'yellow' ? '△' : '✕'}` }
        },
        {
          name: '预测月末', type: 'bar', barGap: '30%',
          data: sorted.map(d => +(d.projected_pts_month || 0).toFixed(1)),
          itemStyle: { color: 'rgba(30,80,130,0.25)', borderColor: '#2E75B6', borderWidth: 1 }
        }
      ]
    });
  }

  // ── 人员效能：散点图 ─────────────────────────────────────────────────────
  function renderPersonScatter(id, staffData) {
    const c = _init(id);
    if (!c || !staffData?.length) return;
    c.setOption({
      title: { text: '揽装积分 × 综合高套（气泡=预计激励）', left: 'center', top: 6, textStyle: { fontSize: 13, color: '#1F4E79' } },
      tooltip: {
        trigger: 'item',
        formatter: (p) => `${p.data[3]}<br/>揽装积分: ${p.data[0]}<br/>综合高套: ${p.data[1]}<br/>预计激励: ¥${p.data[2]}`
      },
      xAxis: { name: '揽装积分', nameTextStyle: { fontSize: 11 } },
      yAxis: { name: '综合高套', nameTextStyle: { fontSize: 11 } },
      series: [{
        type: 'scatter',
        data: staffData.map(s => [
          +(s.device_pts || 0).toFixed(1),
          +(s.total_gaotao || 0).toFixed(1),
          +(s.predicted_incentive || 0).toFixed(0),
          s.name
        ]),
        symbolSize: (d) => Math.min(60, Math.max(12, Math.sqrt(d[2] / 100))),
        itemStyle: { color: '#2E75B6', opacity: 0.75 },
        label: { show: true, formatter: (p) => p.data[3], position: 'top', fontSize: 10 }
      }]
    });
  }

  // ── 人员效能：激励档位堆叠柱图 ──────────────────────────────────────────
  function renderPersonTier(id, tierData) {
    const c = _init(id);
    if (!c || !tierData?.length) return;
    const sorted = [...tierData].sort((a, b) => (b.dev_incentive || 0) - (a.dev_incentive || 0));
    c.setOption({
      title: { text: '高套激励档位构成', left: 'center', top: 6, textStyle: { fontSize: 13, color: '#1F4E79' } },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 4, textStyle: { fontSize: 11 } },
      grid: { left: 60, right: 20, top: 40, bottom: 50 },
      xAxis: { type: 'category', data: sorted.map(d => d.name), axisLabel: { fontSize: 10, rotate: 30 } },
      yAxis: { type: 'value', name: '积分', nameTextStyle: { fontSize: 11 } },
      series: [
        { name: '129-168档', type: 'bar', stack: 'tier', data: sorted.map(d => +(d.tier_129 || 0).toFixed(1)), color: '#70AD47' },
        { name: '169-198档', type: 'bar', stack: 'tier', data: sorted.map(d => +(d.tier_169 || 0).toFixed(1)), color: '#E2A317' },
        { name: '199+档',    type: 'bar', stack: 'tier', data: sorted.map(d => +(d.tier_199 || 0).toFixed(1)), color: '#C00000' },
      ]
    });
  }

  // ── CP对效能：条形图 ─────────────────────────────────────────────────────
  function renderCpPairs(id, cpData) {
    const c = _init(id);
    if (!c || !cpData?.length) return;
    const sorted = [...cpData].sort((a, b) => (b.completion_rate || 0) - (a.completion_rate || 0));
    c.setOption({
      title: { text: 'CP对积分完成率排名', left: 'center', top: 6, textStyle: { fontSize: 13, color: '#1F4E79' } },
      tooltip: { trigger: 'axis', formatter: (p) => {
        const cp = sorted[p[0]?.dataIndex];
        return cp ? `${cp.sales_name}+${cp.install_name}<br/>完成率: ${cp.completion_rate}%<br/>实际积分: ${cp.cp_pts_total}` : '';
      }},
      grid: { left: 140, right: 60, top: 40, bottom: 30 },
      xAxis: { type: 'value', max: 150, name: '完成率(%)', nameTextStyle: { fontSize: 11 },
        axisLine: { lineStyle: { color: '#ccc' } },
        splitLine: [{ lineStyle: { type: 'dashed' } }] },
      yAxis: { type: 'category', data: sorted.map(d => `${d.sales_name}/${d.install_name}`),
               axisLabel: { fontSize: 10 } },
      series: [{
        type: 'bar',
        data: sorted.map(d => ({
          value: d.completion_rate || 0,
          itemStyle: { color: d.completion_rate >= 100 ? '#375623' : d.completion_rate >= 80 ? '#E2A317' : '#C00000' }
        })),
        markLine: { data: [{ xAxis: 100, lineStyle: { color: '#C00000', type: 'dashed' } }],
          label: { formatter: '目标线100%' } },
        label: { show: true, position: 'right', formatter: '{c}%', fontSize: 10 }
      }]
    });
  }

  // ── 县分横向：积分对比 ─────────────────────────────────────────────────────
  function renderBranchRank(id, branches) {
    renderScoreDistrictBar(id, branches);
  }

  // ── 县分横向：多维对比雷达图 ──────────────────────────────────────────────
  function renderBranchMultiBar(id, branches) {
    const c = _init(id);
    if (!c || !branches?.length) return;
    const top5 = branches.slice(0, 7);
    c.setOption({
      title: { text: '各县分业务维度对比（TOP7）', left: 'center', top: 6, textStyle: { fontSize: 13, color: '#1F4E79' } },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, textStyle: { fontSize: 10 } },
      grid: { left: 60, right: 20, top: 40, bottom: 50 },
      xAxis: { type: 'category', data: top5.map(d => d.district.replace('分公司', '')), axisLabel: { fontSize: 11 } },
      yAxis: { type: 'value', nameTextStyle: { fontSize: 11 } },
      series: [
        { name: '基本面', type: 'bar', barMaxWidth: 30, data: top5.map(d => +(d.base_pts || 0).toFixed(1)), color: '#1F4E79' },
        { name: '双线', type: 'bar', barMaxWidth: 30, data: top5.map(d => +(d.twin_pts || 0).toFixed(1)), color: '#E2A317' },
        { name: '其他', type: 'bar', barMaxWidth: 30, data: top5.map(d => +(d.other_pts || 0).toFixed(1)), color: '#70AD47' },
      ]
    });
  }

  // ── 风险：流失比例玫瑰图 ──────────────────────────────────────────────────
  function renderRiskRatio(id, riskData) {
    const c = _init(id);
    if (!c) return;
    const r = riskData.duanzhou_risk || {};
    c.setOption({
      title: { text: '存量流失结构', left: 'center', top: 6, textStyle: { fontSize: 13, color: '#1F4E79' } },
      tooltip: { trigger: 'item', formatter: '{b}: {c}分 ({d}%)' },
      series: [{
        type: 'pie', radius: ['30%', '65%'], roseType: 'area',
        data: [
          { name: '到期积分', value: Math.abs(r.base_expire || 0) },
          { name: '降值积分', value: Math.abs(r.base_decline || 0) },
          { name: '拆机积分', value: Math.abs(r.base_churn || 0) },
          { name: '双线降值', value: Math.abs(r.twin_decline || 0) },
          { name: '双线拆机', value: Math.abs(r.twin_churn || 0) },
        ].filter(d => d.value > 0),
        color: ['#C00000', '#E2A317', '#FF6B6B', '#FFA500', '#FFCC99'],
        label: { formatter: '{b}\n{d}%', fontSize: 10 }
      }]
    });
  }

  // ── 风险：历史趋势 ────────────────────────────────────────────────────────
  function renderRiskHistory(id, historical) {
    const c = _init(id);
    if (!c || !historical?.length) return;
    const rev = [...historical].reverse();
    c.setOption({
      title: { text: '近期积分健康趋势', left: 'center', top: 6, textStyle: { fontSize: 13, color: '#1F4E79' } },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 4, textStyle: { fontSize: 11 } },
      grid: { left: 60, right: 20, top: 40, bottom: 50 },
      xAxis: { type: 'category', data: rev.map(d => d.month), axisLabel: { fontSize: 11 } },
      yAxis: { type: 'value', nameTextStyle: { fontSize: 11 } },
      series: [
        { name: '净增积分', type: 'line', data: rev.map(d => +(d.net_pts || 0).toFixed(1)), smooth: true, color: '#1F4E79' },
        { name: '增量积分', type: 'line', data: rev.map(d => +(d.inc_pts || 0).toFixed(1)), smooth: true, color: '#70AD47' },
        { name: '拆机积分', type: 'line', data: rev.map(d => +(d.base_churn || 0).toFixed(1)), smooth: true, color: '#C00000' },
      ]
    });
  }

  // ── 趋势：积分折线图 ─────────────────────────────────────────────────────
  function renderTrendPts(id, ptsTrend) {
    const c = _init(id);
    if (!c || !ptsTrend?.length) return;
    c.setOption({
      title: { text: '端州分公司月度积分趋势', left: 'center', top: 6, textStyle: { fontSize: 13, color: '#1F4E79' } },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 4, textStyle: { fontSize: 11 } },
      grid: { left: 60, right: 20, top: 40, bottom: 50 },
      xAxis: { type: 'category', data: ptsTrend.map(d => d.month), axisLabel: { fontSize: 11 } },
      yAxis: { type: 'value', name: '积分', nameTextStyle: { fontSize: 11 } },
      series: [
        { name: '净增积分', type: 'line', data: ptsTrend.map(d => +(d.net_pts || 0).toFixed(1)), smooth: true, color: '#1F4E79', lineStyle: { width: 2 }, symbol: 'circle' },
        { name: '增量积分', type: 'line', data: ptsTrend.map(d => +(d.inc_pts || 0).toFixed(1)), smooth: true, color: '#70AD47', lineStyle: { width: 2 } },
        { name: '基本面',   type: 'bar',  data: ptsTrend.map(d => +(d.base_pts || 0).toFixed(1)), color: 'rgba(46,117,182,0.3)' },
        { name: '双线',     type: 'bar',  data: ptsTrend.map(d => +(d.twin_pts || 0).toFixed(1)), color: 'rgba(226,163,23,0.5)' },
      ]
    });
  }

  // ── 趋势：高套折线图 ─────────────────────────────────────────────────────
  function renderTrendGaotao(id, gaotaoTrend) {
    const c = _init(id);
    if (!c || !gaotaoTrend?.length) return;
    c.setOption({
      title: { text: '高套发展月度趋势', left: 'center', top: 6, textStyle: { fontSize: 13, color: '#1F4E79' } },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 4, textStyle: { fontSize: 11 } },
      grid: { left: 50, right: 20, top: 40, bottom: 50 },
      xAxis: { type: 'category', data: gaotaoTrend.map(d => d.month), axisLabel: { fontSize: 11 } },
      yAxis: [
        { type: 'value', name: '高套(户)', nameTextStyle: { fontSize: 11 } },
        { type: 'value', name: '人数', nameTextStyle: { fontSize: 11 } }
      ],
      series: [
        { name: '新增高套', type: 'bar', data: gaotaoTrend.map(d => +(d.new_gaotao || 0).toFixed(1)), color: '#1F4E79' },
        { name: '存量高套', type: 'bar', data: gaotaoTrend.map(d => +(d.stock_gaotao || 0).toFixed(1)), color: '#70AD47' },
        { name: '参与人数', type: 'line', yAxisIndex: 1, data: gaotaoTrend.map(d => d.person_count || 0), color: '#E2A317', lineStyle: { width: 2 } }
      ]
    });
  }

  // 窗口 resize 时自适应
  window.addEventListener('resize', () => {
    Object.values(instances).forEach(c => c && c.resize());
  });

  return {
    renderOverviewPts, renderOverviewGaotao,
    renderScorePie, renderScoreHealth, renderScoreDistrictBar,
    renderProgressBar,
    renderPersonScatter, renderPersonTier, renderCpPairs,
    renderBranchRank, renderBranchMultiBar,
    renderRiskRatio, renderRiskHistory,
    renderTrendPts, renderTrendGaotao,
  };
})();
