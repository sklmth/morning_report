/**
 * ECharts 图表渲染模块 v2
 * 仅展示14个政企客户经理相关图表
 */
const Charts = (() => {
  'use strict';
  const _inst = {};

  const C = {
    primary:'#1e3a5f', mid:'#2563a8', light:'#3b82c4',
    accent:'#f59e0b', success:'#059669', danger:'#dc2626',
    muted:'#94a3b8', text:'#0f172a', sub:'#475569', border:'#e2e8f0',
    palette:['#1e3a5f','#2563a8','#3b82c4','#f59e0b','#059669',
             '#f97316','#dc2626','#7c3aed','#0891b2','#be185d',
             '#065f46','#78350f','#1e40af','#6b21a8'],
  };

  function _init(id) {
    if (_inst[id]) _inst[id].dispose();
    const el = document.getElementById(id);
    if (!el) return null;
    _inst[id] = echarts.init(el, null, { renderer: 'canvas' });
    return _inst[id];
  }

  const _T = (text, sub) => ({
    text, subtext: sub||'', left:'center', top:10,
    textStyle:{ fontSize:13, fontWeight:700, color:C.primary, fontFamily:'"PingFang SC","微软雅黑",sans-serif' },
    subtextStyle:{ fontSize:11, color:C.muted },
  });

  const _tip = (trigger='axis') => ({
    trigger,
    backgroundColor:'rgba(15,23,42,.92)',
    borderColor:'transparent',
    textStyle:{ color:'#fff', fontSize:12 },
    extraCssText:'border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,.3);padding:10px 14px',
  });

  window.addEventListener('resize', () => Object.values(_inst).forEach(c => c?.resize()));

  // ══════════════════════════════════════
  // 1. 总览：端州政企净增积分构成
  //    data = overview API 返回的对象（含 net_pts/base_pts/twin_pts/other_pts）
  // ══════════════════════════════════════
  function renderOverviewPts(id, data) {
    const c = _init(id); if (!c) return;
    // 优先用overview数据，退回score结构数据
    const net   = data?.net_pts   ?? data?.duanzhou?.net_pts   ?? 0;
    const base  = data?.base_pts  ?? data?.duanzhou?.base_pts  ?? 0;
    const twin  = data?.twin_pts  ?? data?.duanzhou?.twin_pts  ?? 0;
    const other = data?.other_pts ?? data?.duanzhou?.other_pts ?? 0;

    // 分片可能为负（如双线拆机/降值大于新增）。饼图无法原生绘制负数弧，
    // 故用绝对值作弧长，raw 保留带符号原值用于标签/tooltip，占比按净增合计计算。
    const _seg = (name, raw, color) => ({
      name, value: Math.abs(raw), raw,
      itemStyle: { color: raw < 0 ? C.danger : color },
    });
    const _pct = raw => net ? (raw / net * 100).toFixed(1) : '0.0';
    c.setOption({
      title: _T('端州政企净增积分', `合计 ${(+net).toFixed(2)} 分`),
      tooltip: { ..._tip('item'), formatter: p =>
        `${p.name}<br/>积分：${(+p.data.raw).toFixed(2)} 分<br/>占净增：${_pct(p.data.raw)}%` },
      legend: { bottom:8, textStyle:{ fontSize:11, color:C.sub } },
      series:[{
        type:'pie', radius:['40%','68%'], center:['50%','52%'],
        data:[
          _seg('基本面', base, C.primary),
          _seg('双线', twin, C.accent),
          _seg('其他业务', other, C.success),
        ].filter(d => d.value > 0),
        emphasis:{ itemStyle:{ shadowBlur:10, shadowColor:'rgba(0,0,0,.2)' } },
        label:{ formatter: p => `${p.name}\n${_pct(p.data.raw)}%\n${(+p.data.raw).toFixed(0)}分`, fontSize:11, color:C.text },
        labelLine:{ length:10, length2:6 },
      }]
    });
  }

  // ══════════════════════════════════════
  // 2. 总览：高套月累分布
  // ══════════════════════════════════════
  function renderOverviewGaotao(id, wm) {
    const c = _init(id); if (!c || !wm?.length) return;
    const sorted = [...wm].sort((a,b) => ((b.new_gaotao||0)+(b.stock_gaotao||0)) - ((a.new_gaotao||0)+(a.stock_gaotao||0)));
    c.setOption({
      title: _T('政企高套月累完成'),
      tooltip: { ..._tip(), formatter: params => {
        const d = sorted[params[0].dataIndex];
        return d ? `${d.name}<br/>新增高套：${d.new_gaotao||0} 户<br/>存量高套：${d.stock_gaotao||0} 户<br/>合计：${((d.new_gaotao||0)+(d.stock_gaotao||0)).toFixed(1)} 户` : '';
      }},
      legend:{ bottom:4, textStyle:{ fontSize:11 } },
      grid:{ left:48, right:16, top:52, bottom:50 },
      xAxis:{ type:'category', data:sorted.map(d=>d.name),
        axisLabel:{ fontSize:10, rotate:35, color:C.sub },
        axisLine:{ lineStyle:{ color:C.border } } },
      yAxis:{ type:'value', name:'户',
        nameTextStyle:{ fontSize:11, color:C.muted },
        axisLine:{ show:false },
        splitLine:{ lineStyle:{ color:C.border, type:'dashed' } } },
      series:[
        { name:'新增高套', type:'bar', stack:'g', data:sorted.map(d=>+(d.new_gaotao||0).toFixed(2)), color:C.primary, barMaxWidth:26 },
        { name:'存量高套', type:'bar', stack:'g', data:sorted.map(d=>+(d.stock_gaotao||0).toFixed(2)), color:C.success, barMaxWidth:26 },
      ]
    });
  }

  // ══════════════════════════════════════
  // 3. 人员业绩：激励排名（核心图）
  //    merged: staff_efficiency + wanmei_staff
  // ══════════════════════════════════════
  function renderPersonIncentive(id, staffEff, wm) {
    const c = _init(id); if (!c) return;

    // 合并两张表，以姓名为键
    const map = {};
    (wm||[]).forEach(d => { map[d.name] = { ...map[d.name], ...d }; });
    (staffEff||[]).forEach(d => { map[d.name] = { ...map[d.name], ...d }; });
    const people = Object.values(map).sort((a,b) => (b.predicted_incentive||0) - (a.predicted_incentive||0));

    if (!people.length) { c.showLoading({ text:'暂无数据', color:C.mid }); return; }

    c.setOption({
      title: _T('14人激励排名', '激励来源：071人员统计 · 计件激励金额'),
      legend: { bottom: 4, textStyle: { fontSize: 11 } },
      tooltip: { ..._tip('axis'), formatter: params => {
        const p = people[params[0].dataIndex];
        return `<b>${p.name}</b><br/>
          激励金额：¥${(p.predicted_incentive||0).toFixed(0)}<br/>
          揽装积分：${(p.device_pts||p.inc_pts_total||0).toFixed(0)} 分<br/>
          综合高套：${((p.new_gaotao||0)+(p.stock_gaotao||0)).toFixed(1)} 户`;
      }},
      grid:{ left:70, right:90, top:62, bottom:50 },
      xAxis:{ type:'category', data:people.map(d=>d.name),
        axisLabel:{ fontSize:11, color:C.sub, rotate:0 },
        axisLine:{ lineStyle:{ color:C.border } } },
      yAxis:[
        { type:'value', name:'激励(元)',
          nameTextStyle:{ fontSize:11, color:C.muted },
          axisLine:{ show:false },
          splitLine:{ lineStyle:{ color:C.border, type:'dashed' } } },
        { type:'value', name:'积分',
          nameTextStyle:{ fontSize:11, color:C.muted },
          axisLine:{ show:false },
          splitLine:{ show:false } },
      ],
      series:[
        {
          name:'激励金额', type:'bar', barMaxWidth:32,
          data: people.map((d,i) => ({
            value: +(d.predicted_incentive||0).toFixed(0),
            itemStyle:{ color: C.palette[i % C.palette.length] }
          })),
          label:{ show:true, position:'top', formatter: p => `¥${(+p.value).toLocaleString()}`, fontSize:10, color:C.sub },
        },
        {
          name:'揽装积分', type:'line', yAxisIndex:1, smooth:true,
          data: people.map(d => +(d.device_pts||d.inc_pts_total||0).toFixed(0)),
          lineStyle:{ color:C.accent, width:2 },
          itemStyle:{ color:C.accent },
          symbol:'circle', symbolSize:5,
        },
      ]
    });
  }

  // ══════════════════════════════════════
  // 4. 人员业绩：揽装积分 × 高套 散点图
  // ══════════════════════════════════════
  function renderPersonScatter(id, staffEff, wm) {
    const c = _init(id); if (!c) return;

    const map = {};
    (wm||[]).forEach(d => { map[d.name] = { ...map[d.name], ...d }; });
    (staffEff||[]).forEach(d => { map[d.name] = { ...map[d.name], ...d }; });
    const people = Object.values(map);

    c.setOption({
      title: _T('揽装积分 × 综合高套', '气泡大小=激励金额'),
      tooltip: { ..._tip('item'), formatter: p => {
        const d = p.data;
        return `<b>${d[3]}</b><br/>揽装积分：${d[0]} 分<br/>综合高套：${d[1]} 户<br/>激励金额：¥${d[2].toLocaleString()}`;
      }},
      xAxis:{ name:'揽装积分(分)', nameTextStyle:{ fontSize:11 }, axisLine:{ lineStyle:{ color:C.border } },
        splitLine:{ lineStyle:{ color:C.border, type:'dashed' } } },
      yAxis:{ name:'综合高套(户)', nameTextStyle:{ fontSize:11 }, axisLine:{ lineStyle:{ color:C.border } },
        splitLine:{ lineStyle:{ color:C.border, type:'dashed' } } },
      series:[{
        type:'scatter',
        data: people.map((d,i) => [
          +(d.device_pts||d.inc_pts_total||0).toFixed(0),
          +((d.new_gaotao||0)+(d.stock_gaotao||0)).toFixed(1),
          +(d.predicted_incentive||0).toFixed(0),
          d.name,
        ]),
        // 气泡大小按激励金额线性映射，确保范围可见
        symbolSize: (function() {
          const allVals = people.map(d => d.predicted_incentive || 0);
          const minV = Math.min(...allVals), maxV = Math.max(...allVals);
          const span = maxV - minV || 1;
          return d => 14 + (d[2] - minV) / span * 36;  // 映射到 [14, 50]
        })(),
        itemStyle:{ opacity:.85, color: C.mid },
        label:{ show:true, formatter: p => p.data[3], position:'top', fontSize:10, color:C.sub },
      }]
    });
  }

  // ══════════════════════════════════════
  // 5. 人员业绩：高套 + 网关分布
  // ══════════════════════════════════════
  function renderPersonGaotao(id, wm) {
    const c = _init(id); if (!c || !wm?.length) return;
    const sorted = [...wm].sort((a,b) => ((b.new_gaotao||0)+(b.stock_gaotao||0)) - ((a.new_gaotao||0)+(a.stock_gaotao||0)));
    c.setOption({
      title: _T('高套发展 + 全光网关分布'),
      tooltip: { ..._tip(), formatter: params => {
        const d = sorted[params[0].dataIndex];
        return d ? `<b>${d.name}</b><br/>新增高套：${d.new_gaotao||0} 户<br/>存量高套：${d.stock_gaotao||0} 户<br/>全光网关：${d.gateway_count||0} 台` : '';
      }},
      legend:{ bottom:4, textStyle:{ fontSize:11 } },
      grid:{ left:48, right:48, top:52, bottom:50 },
      xAxis:{ type:'category', data:sorted.map(d=>d.name),
        axisLabel:{ fontSize:10, rotate:35, color:C.sub },
        axisLine:{ lineStyle:{ color:C.border } } },
      yAxis:[
        { type:'value', name:'高套(户)', nameTextStyle:{ fontSize:11,color:C.muted }, axisLine:{ show:false }, splitLine:{ lineStyle:{ color:C.border, type:'dashed' } } },
        { type:'value', name:'网关(台)', nameTextStyle:{ fontSize:11,color:C.muted }, axisLine:{ show:false }, splitLine:{ show:false } },
      ],
      series:[
        { name:'新增高套', type:'bar', stack:'g', data:sorted.map(d=>+(d.new_gaotao||0).toFixed(2)), color:C.primary, barMaxWidth:26 },
        { name:'存量高套', type:'bar', stack:'g', data:sorted.map(d=>+(d.stock_gaotao||0).toFixed(2)), color:C.success, barMaxWidth:26 },
        { name:'全光网关', type:'line', yAxisIndex:1, smooth:true,
          data:sorted.map(d=>+(d.gateway_count||0).toFixed(0)),
          lineStyle:{ color:C.accent, width:2 }, itemStyle:{ color:C.accent }, symbol:'circle', symbolSize:6 },
      ]
    });
  }

  // ══════════════════════════════════════
  // 6. 积分结构：饼图
  // ══════════════════════════════════════
  function renderScorePie(id, data) {
    const c = _init(id); if (!c) return;
    const dz = data?.duanzhou || {};
    // 优先用端州直接数据（overview格式）
    const net         = dz.net_pts ?? data?.net_pts ?? 0;
    const base_mobile = dz.base_mobile ?? 0;
    const base_bb     = dz.base_bb ?? 0;
    const base_phone  = dz.base_phone ?? 0;   // 固话，通常为负
    const base_itv    = dz.base_itv ?? 0;     // ITV，可能为负
    const twin_inet   = dz.twin_inet ?? 0;    // 双线互专，可能为负
    const twin_net    = dz.twin_net ?? 0;     // 双线组网，可能为负
    const other_pts   = dz.other_pts ?? data?.other_pts ?? 0;

    // 展示重要分项：基本面前四项(移动/宽带/固话/ITV) + 双线(互专/组网) + 其他业务。
    // 各分项加总不等于净增合计（含智家、基本面存量调整等），剩余归入"其他"分片，
    // 使环图各弧长加起来正好等于净增合计。负值分片用红色，弧长取绝对值。
    const parts = [
      ['移动',       base_mobile, C.primary],
      ['宽带',       base_bb,     C.mid],
      ['固话',       base_phone,  C.light],
      ['ITV',        base_itv,    C.palette[7]],
      ['双线(互专)', twin_inet,   C.accent],
      ['双线(组网)', twin_net,    C.palette[5]],
      ['其他业务',   other_pts,   C.success],
    ];
    const shown = parts.reduce((s, p) => s + p[1], 0);
    parts.push(['其他', +(net - shown).toFixed(2), C.muted]);

    const _pct = raw => net ? (raw / net * 100).toFixed(1) : '0.0';
    const _seg = ([name, raw, color]) => ({
      name, value: Math.abs(raw), raw,
      itemStyle: { color: raw < 0 ? C.danger : color },
    });
    c.setOption({
      title: _T('端州政企净增积分结构详解', '来源：完美一单 · 区县责任田积分(月）端州行'),
      tooltip: { ..._tip('item'), formatter: p =>
        `${p.name}<br/>积分：${(+p.data.raw).toFixed(2)} 分<br/>占净增：${_pct(p.data.raw)}%` },
      legend: { bottom:8, textStyle:{ fontSize:10 } },
      series:[{
        type:'pie', radius:['35%','65%'], center:['50%','50%'],
        data: parts.map(_seg).filter(d => d.value > 0),
        label:{ formatter: p => `${p.name}\n${_pct(p.data.raw)}%\n${(+p.data.raw).toFixed(0)}分`, fontSize:10, color:C.text },
      }]
    });
  }

  // 7. 积分结构：健康度仪表盘
  function renderScoreHealth(id, health) {
    const c = _init(id); if (!c) return;
    c.setOption({
      title: _T('存量流失健康度'),
      series:[
        { name:'拆机占比', type:'gauge', center:['17%','55%'], radius:'42%', min:0, max:60,
          axisLine:{ lineStyle:{ width:8, color:[[.3,C.success],[.5,C.accent],[1,C.danger]] } },
          pointer:{ length:'55%' }, detail:{ formatter:'{value}%', fontSize:12 },
          title:{ fontSize:11, offsetCenter:[0,'80%'] },
          data:[{ value:health?.churn_ratio||0, name:'拆机' }] },
        { name:'降值占比', type:'gauge', center:['50%','55%'], radius:'42%', min:0, max:50,
          axisLine:{ lineStyle:{ width:8, color:[[.25,C.success],[.5,C.accent],[1,C.danger]] } },
          pointer:{ length:'55%' }, detail:{ formatter:'{value}%', fontSize:12 },
          title:{ fontSize:11, offsetCenter:[0,'80%'] },
          data:[{ value:health?.decline_ratio||0, name:'降值' }] },
        { name:'到期占比', type:'gauge', center:['83%','55%'], radius:'42%', min:0, max:80,
          axisLine:{ lineStyle:{ width:8, color:[[.4,C.success],[.625,C.accent],[1,C.danger]] } },
          pointer:{ length:'55%' }, detail:{ formatter:'{value}%', fontSize:12 },
          title:{ fontSize:11, offsetCenter:[0,'80%'] },
          data:[{ value:health?.expire_ratio||0, name:'到期' }] },
      ]
    });
  }

  // 8. 积分结构：全市县分积分对比
  function renderScoreDistrictBar(id, districts) {
    const c = _init(id); if (!c || !districts?.length) return;
    const sorted = [...districts].sort((a,b) => (b.net_pts||0) - (a.net_pts||0));
    c.setOption({
      title: _T('全市各县分净增积分对比'),
      tooltip: _tip(),
      grid:{ left:90, right:40, top:52, bottom:24 },
      xAxis:{ type:'value', name:'分', nameTextStyle:{ fontSize:11 } },
      yAxis:{ type:'category', data:sorted.map(d=>d.district.replace('分公司','').replace('(区县其它)','')), axisLabel:{ fontSize:11 } },
      series:[{ name:'净增积分', type:'bar', barMaxWidth:22,
        data:sorted.map(d=>({
          value:+(d.net_pts||0).toFixed(1),
          itemStyle:{ color: d.district.includes('端州') ? C.accent : C.mid }
        })),
        label:{ show:true, position:'right', fontSize:10 },
      }]
    });
  }

  // 9. 完成进度：14人进度条形图
  function renderProgressBar(id, data) {
    const c = _init(id); if (!c) return;
    const people = (data.person_progress||[]).sort((a,b)=>(b.inc_pts||0)-(a.inc_pts||0));
    if (!people.length) return;
    const tp = data.time_progress||0;
    c.setOption({
      title: _T(`14人积分完成进度`, `时间进度 ${tp}% · 数据截至 ${data.latest_date||''}`),
      tooltip: { ..._tip(), formatter: params => {
        const p = people[params[0]?.dataIndex];
        return p ? `<b>${p.name}</b><br/>当前积分：${p.inc_pts} 分<br/>预测月末：${p.projected_pts_month} 分<br/>激励：¥${p.predicted_incentive||0}` : '';
      }},
      grid:{ left:60, right:100, top:60, bottom:30 },
      xAxis:{ type:'value', name:'积分', nameTextStyle:{ fontSize:11 },
        splitLine:{ lineStyle:{ color:C.border, type:'dashed' } } },
      yAxis:{ type:'category', data:people.map(d=>d.name), axisLabel:{ fontSize:11 } },
      series:[{
        name:'当前积分', type:'bar', barMaxWidth:20,
        data:people.map(d=>({
          value:+(d.inc_pts||0).toFixed(0),
          itemStyle:{ color: d.status==='green'?C.success : d.status==='yellow'?C.accent : C.danger }
        })),
        label:{ show:true, position:'right',
          formatter: p => `${people[p.dataIndex]?.status==='green'?'✓':people[p.dataIndex]?.status==='yellow'?'△':'✕'} ${p.value}`,
          fontSize:10, color:C.sub },
      }]
    });
  }

  // 10. 县分对比：排名
  function renderBranchRank(id, branches) { renderScoreDistrictBar(id, branches); }

  // 11. 县分对比：多维柱图
  function renderBranchMultiBar(id, branches) {
    const c = _init(id); if (!c || !branches?.length) return;
    const top = branches.slice(0,9);
    c.setOption({
      title: _T('各县分业务维度对比'),
      tooltip: _tip(), legend:{ bottom:0, textStyle:{ fontSize:10 } },
      grid:{ left:52, right:16, top:52, bottom:48 },
      xAxis:{ type:'category', data:top.map(d=>d.district.replace('分公司','')), axisLabel:{ fontSize:10, rotate:20 }, axisLine:{ lineStyle:{ color:C.border } } },
      yAxis:{ type:'value', nameTextStyle:{ fontSize:11 }, splitLine:{ lineStyle:{ color:C.border, type:'dashed' } } },
      series:[
        { name:'基本面', type:'bar', barMaxWidth:22, data:top.map(d=>+(d.base_pts||0).toFixed(0)), color:C.primary },
        { name:'双线', type:'bar', barMaxWidth:22, data:top.map(d=>+(d.twin_pts||0).toFixed(0)), color:C.accent },
        { name:'其他', type:'bar', barMaxWidth:22, data:top.map(d=>+(d.other_pts||0).toFixed(0)), color:C.success },
      ]
    });
  }

  // 12. 风险：流失玫瑰图
  function renderRiskRatio(id, data) {
    const c = _init(id); if (!c) return;
    const r = data?.duanzhou_risk || {};
    c.setOption({
      title: _T('存量流失结构'),
      tooltip: { ..._tip('item'), formatter:'{b}: {c} 分 ({d}%)' },
      series:[{
        type:'pie', radius:['25%','62%'], roseType:'area',
        data:[
          { name:'到期积分', value:Math.abs(r.base_expire||0) },
          { name:'降值积分', value:Math.abs(r.base_decline||0) },
          { name:'拆机积分', value:Math.abs(r.base_churn||0) },
          { name:'双线降值', value:Math.abs(r.twin_decline||0) },
          { name:'双线拆机', value:Math.abs(r.twin_churn||0) },
        ].filter(d=>d.value>0),
        color:[C.danger,'#f97316','#fb923c','#fbbf24','#fde68a'],
        label:{ formatter:'{b}\n{d}%', fontSize:10 },
      }]
    });
  }

  // 13. 风险：历史趋势
  function renderRiskHistory(id, historical) {
    const c = _init(id); if (!c || !historical?.length) return;
    const rev = [...historical].reverse();
    c.setOption({
      title: _T('近期积分健康趋势'),
      tooltip: _tip(), legend:{ bottom:4, textStyle:{ fontSize:11 } },
      grid:{ left:56, right:16, top:52, bottom:48 },
      xAxis:{ type:'category', data:rev.map(d=>d.month), axisLabel:{ fontSize:11 } },
      yAxis:{ type:'value', splitLine:{ lineStyle:{ color:C.border, type:'dashed' } } },
      series:[
        { name:'净增积分', type:'line', smooth:true, data:rev.map(d=>+(d.net_pts||0).toFixed(0)), color:C.primary, lineStyle:{ width:2 } },
        { name:'增量积分', type:'line', smooth:true, data:rev.map(d=>+(d.inc_pts||0).toFixed(0)), color:C.success },
        { name:'拆机积分', type:'line', smooth:true, data:rev.map(d=>+(d.base_churn||0).toFixed(0)), color:C.danger },
      ]
    });
  }

  // 14. 趋势：积分月度折线
  function renderTrendPts(id, pts) {
    const c = _init(id); if (!c || !pts?.length) return;
    c.setOption({
      title: _T('端州月度积分趋势'),
      tooltip: _tip(), legend:{ bottom:4, textStyle:{ fontSize:11 } },
      grid:{ left:56, right:16, top:52, bottom:48 },
      xAxis:{ type:'category', data:pts.map(d=>d.month), axisLabel:{ fontSize:11 } },
      yAxis:{ type:'value', name:'积分', nameTextStyle:{ fontSize:11 }, splitLine:{ lineStyle:{ color:C.border, type:'dashed' } } },
      series:[
        { name:'净增积分', type:'line', smooth:true, data:pts.map(d=>+(d.net_pts||0).toFixed(0)), color:C.primary, lineStyle:{ width:2.5 }, symbol:'circle', symbolSize:6 },
        { name:'增量积分', type:'line', smooth:true, data:pts.map(d=>+(d.inc_pts||0).toFixed(0)), color:C.success, lineStyle:{ width:2 } },
        { name:'基本面', type:'bar', data:pts.map(d=>+(d.base_pts||0).toFixed(0)), color:'rgba(30,58,95,.2)', barMaxWidth:20 },
        { name:'双线', type:'bar', data:pts.map(d=>+(d.twin_pts||0).toFixed(0)), color:'rgba(245,158,11,.35)', barMaxWidth:20 },
      ]
    });
  }

  // 15. 趋势：高套月度折线
  function renderTrendGaotao(id, gaotao) {
    const c = _init(id); if (!c || !gaotao?.length) return;
    c.setOption({
      title: _T('高套发展月度趋势'),
      tooltip: _tip(), legend:{ bottom:4, textStyle:{ fontSize:11 } },
      grid:{ left:48, right:48, top:52, bottom:48 },
      xAxis:{ type:'category', data:gaotao.map(d=>d.month), axisLabel:{ fontSize:11 } },
      yAxis:[
        { type:'value', name:'高套(户)', nameTextStyle:{ fontSize:11 }, splitLine:{ lineStyle:{ color:C.border, type:'dashed' } } },
        { type:'value', name:'人数', nameTextStyle:{ fontSize:11 }, splitLine:{ show:false } },
      ],
      series:[
        { name:'新增高套', type:'bar', data:gaotao.map(d=>+(d.new_gaotao||0).toFixed(0)), color:C.primary, barMaxWidth:20 },
        { name:'存量高套', type:'bar', data:gaotao.map(d=>+(d.stock_gaotao||0).toFixed(0)), color:C.success, barMaxWidth:20 },
        { name:'参与人数', type:'line', yAxisIndex:1, data:gaotao.map(d=>d.person_count||0), color:C.accent, lineStyle:{ width:2 } },
      ]
    });
  }

  return {
    renderOverviewPts, renderOverviewGaotao,
    renderPersonIncentive, renderPersonScatter, renderPersonGaotao,
    renderScorePie, renderScoreHealth, renderScoreDistrictBar,
    renderProgressBar, renderBranchRank, renderBranchMultiBar,
    renderRiskRatio, renderRiskHistory, renderTrendPts, renderTrendGaotao,
  };
})();
