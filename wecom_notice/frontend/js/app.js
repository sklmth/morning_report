// ================================
// 现代化Dashboard - 主应用逻辑
// ================================

// 全局状态
const state = {
  currentView: 'overview',
  targetDate: '',
  schedulerStatus: null,
  managers: [],
  rules: []
};

// 工具函数
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

// Toast通知
function toast(message, duration = 3000) {
  const toastEl = $('#toast');
  toastEl.textContent = message;
  toastEl.classList.add('show');
  
  setTimeout(() => {
    toastEl.classList.remove('show');
  }, duration);
}

// 加载遮罩
function showLoading() {
  $('#loading-overlay').classList.add('show');
}

function hideLoading() {
  $('#loading-overlay').classList.remove('show');
}

// 日期格式化
function formatDate(dateStr) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

function formatTime(dateStr) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

// 获取明天日期
function tomorrow() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  return date.toISOString().split('T')[0];
}

// 设置日期偏移
function setDateOffset(days) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  const dateStr = date.toISOString().split('T')[0];
  $('#target-date').value = dateStr;
  state.targetDate = dateStr;
  loadOverview();
}

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
  console.log('🚀 预约通报系统启动');
  
  // 初始化日期
  state.targetDate = tomorrow();
  $('#target-date').value = state.targetDate;
  
  // 初始化统计日期
  const today = new Date().toISOString().split('T')[0];
  $('#stats-start-date').value = today;
  $('#stats-end-date').value = today;
  $('#reminder-date').value = today;
  $('#send-date').value = state.targetDate;
  
  // 绑定事件
  bindEvents();
  
  // 加载初始数据
  await loadInitialData();
  
  // 定时更新调度器状态
  setInterval(updateSchedulerStatus, 30000);
  
  console.log('✅ 系统初始化完成');
});

// 绑定事件
function bindEvents() {
  // 侧边栏导航
  $$('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const view = item.dataset.view;
      switchView(view);
    });
  });
  
  // 移动端菜单切换
  $('#mobile-menu-toggle')?.addEventListener('click', () => {
    $('.sidebar').classList.toggle('open');
  });
  
  // 刷新按钮
  $('#refresh-btn')?.addEventListener('click', () => {
    loadCurrentView();
  });
  
  // 日期选择
  $('#target-date')?.addEventListener('change', (e) => {
    state.targetDate = e.target.value;
    loadOverview();
  });
  
  // 调度器控制
  $('#start-scheduler-btn')?.addEventListener('click', startScheduler);
  $('#stop-scheduler-btn')?.addEventListener('click', stopScheduler);
}

// 加载初始数据
async function loadInitialData() {
  showLoading();
  try {
    await Promise.all([
      updateSchedulerStatus(),
      loadOverview(),
      loadRules(),
      loadManagers()
    ]);
  } catch (error) {
    console.error('初始化数据加载失败:', error);
    toast('❌ 数据加载失败，请刷新重试');
  } finally {
    hideLoading();
  }
}

// 切换视图
function switchView(viewName) {
  // 更新导航状态
  $$('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.view === viewName);
  });
  
  // 切换视图
  $$('.view').forEach(view => {
    view.classList.toggle('active', view.id === `view-${viewName}`);
  });
  
  // 更新页面标题
  const titles = {
    overview: '总览',
    statistics: '统计分析',
    reminders: '提醒日志',
    send: '发送通报',
    scheduler: '调度器',
    config: '配置'
  };
  $('#page-title').textContent = titles[viewName] || viewName;
  
  state.currentView = viewName;
  
  // 加载视图数据
  loadCurrentView();
}

// 加载当前视图
async function loadCurrentView() {
  const loaders = {
    overview: loadOverview,
    statistics: () => {}, // 按需加载
    reminders: () => {}, // 按需加载
    send: loadSendView,
    scheduler: loadSchedulerView,
    config: loadConfigView
  };
  
  const loader = loaders[state.currentView];
  if (loader) {
    await loader();
  }
}

// ================================
// 总览视图
// ================================
async function loadOverview() {
  try {
    showLoading();
    
    // 加载汇总数据
    const summary = await Api.summary(state.targetDate);
    
    // 更新上传状态
    if (summary.last_upload) {
      const uploadTime = formatTime(summary.last_upload.upload_time);
      $('#last-update').textContent = `最后更新: ${uploadTime}`;
    }
    
    // 渲染统计卡片
    renderStatCards(summary);
    
    // 渲染客户经理网格
    renderManagerGrid(summary.manager_progress || []);
    
    // 渲染预约记录
    renderRecordsTable(summary.records || []);
    
  } catch (error) {
    console.error('加载总览失败:', error);
    toast('❌ 加载失败: ' + error.message);
  } finally {
    hideLoading();
  }
}

// 渲染统计卡片
function renderStatCards(summary) {
  // 计算统计数据
  const total = (summary.cumulative?.on_time || 0) + 
                (summary.cumulative?.overtime || 0) + 
                (summary.cumulative?.missing || 0);
  
  const onTime = summary.cumulative?.on_time || 0;
  const overtime = summary.cumulative?.overtime || 0;
  const missing = summary.cumulative?.missing || 0;
  const today = summary.records?.length || 0;
  
  // 更新数值
  $('#stat-ontime').textContent = onTime;
  $('#stat-overtime').textContent = overtime;
  $('#stat-missing').textContent = missing;
  $('#stat-today').textContent = today;
  
  // 更新进度环
  updateProgressRing('ring-ontime', total > 0 ? onTime / total : 0);
  updateProgressRing('ring-overtime', total > 0 ? overtime / total : 0);
  updateProgressRing('ring-missing', total > 0 ? missing / total : 0);
  
  // 更新提示文本
  if (onTime > overtime + missing) {
    $('#stat-ontime-change').textContent = '真棒！继续保持 🎉';
  } else {
    $('#stat-ontime-change').textContent = '还需努力哦 💪';
  }
  
  if (overtime > 0) {
    $('#stat-overtime-change').textContent = `稍微晚了点 😅`;
  } else {
    $('#stat-overtime-change').textContent = '暂无超时 ✨';
  }
  
  if (missing > 0) {
    $('#stat-missing-change').textContent = `记得提醒哦 📢`;
  } else {
    $('#stat-missing-change').textContent = '全部填报 🎊';
  }
}

// 更新进度环
function updateProgressRing(id, progress) {
  const ring = $(`#${id}`);
  if (!ring) return;
  
  const circumference = 2 * Math.PI * 26; // r=26
  const offset = circumference - (progress * circumference);
  ring.style.strokeDashoffset = offset;
}



// 渲染客户经理网格
function renderManagerGrid(managers) {
  const grid = document.getElementById('manager-grid');
  if (!grid) return;
  
  if (!managers || managers.length === 0) {
    grid.innerHTML = '<div class="empty-state" style="grid-column: 1/-1;"><div class="empty-icon">👥</div><p>暂无客户经理数据</p></div>';
    return;
  }
  
  grid.innerHTML = managers.map(m => {
    const booked = m.booked || 0;
    const target = 2;
    const progress = Math.min((booked / target) * 100, 100);
    const sufficient = booked >= target;
    const historyOvertime = m.history_counts?.overtime || 0;
    const historyMissing = m.history_counts?.missing || 0;
    const initial = m.name.charAt(0);
    
    return `
      <div class="manager-card ${sufficient ? '' : 'insufficient'}">
        <div class="manager-header">
          <div class="manager-info">
            <div class="manager-avatar">${initial}</div>
            <div class="manager-details">
              <h4>${m.name}</h4>
              <span class="manager-team">${m.team || '未分组'}</span>
            </div>
          </div>
          <span class="manager-status ${sufficient ? 'sufficient' : 'insufficient'}">
            ${sufficient ? '✅ 已达标' : '⚠️ 未达标'}
          </span>
        </div>
        <div class="manager-progress">
          <div class="progress-info">
            <span class="progress-label">预约进度</span>
            <span class="progress-value">${booked} / ${target} 户</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" style="width: ${progress}%"></div>
          </div>
        </div>
        <div class="manager-stats">
          <div class="stat-item">
            <div class="stat-item-value">${booked}</div>
            <div class="stat-item-label">已预约</div>
          </div>
          <div class="stat-item">
            <div class="stat-item-value">${historyOvertime}</div>
            <div class="stat-item-label">历史超时</div>
          </div>
          <div class="stat-item">
            <div class="stat-item-value">${historyMissing}</div>
            <div class="stat-item-label">历史漏填</div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// 渲染预约记录表格
function renderRecordsTable(records) {
  const tbody = document.getElementById('records-table');
  const countEl = document.getElementById('record-count');
  if (!tbody) return;
  
  countEl.textContent = '共 ' + records.length + ' 条记录';
  
  if (records.length === 0) {
    tbody.innerHTML = '<tr class="empty-state"><td colspan="7"><div class="empty-icon">📭</div><p>暂无预约记录</p></td></tr>';
    return;
  }
  
  tbody.innerHTML = records.map(r => {
    let statusBadge = '';
    if (r.visit_result) {
      statusBadge = '<span class="badge badge-success">已回填</span>';
    } else if (r.reschedule_time) {
      statusBadge = '<span class="badge badge-warning">已改约</span>';
    } else {
      statusBadge = '<span class="badge badge-info">待拜访</span>';
    }
    
    return `
      <tr>
        <td><strong>${r.manager_name || '-'}</strong></td>
        <td>${r.company_name || '-'}</td>
        <td>${r.contact_name || '-'}</td>
        <td>${r.time_slot || '-'}</td>
        <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;">${r.opportunity_content || '-'}</td>
        <td>${r.delivery_staff || '-'}</td>
        <td>${statusBadge}</td>
      </tr>
    `;
  }).join('');
}

// 统计分析
async function loadStatistics() {
  const startDate = document.getElementById('stats-start-date').value;
  const endDate = document.getElementById('stats-end-date').value;
  
  if (!startDate || !endDate) {
    toast('请选择日期范围');
    return;
  }
  
  try {
    showLoading();
    const stats = await Api.cumulativeStats({ start_date: startDate, end_date: endDate });
    renderStatistics(stats);
    toast('✅ 统计数据已加载');
  } catch (error) {
    console.error('加载统计失败:', error);
    toast('❌ 加载失败: ' + error.message);
  } finally {
    hideLoading();
  }
}

function renderStatistics(stats) {
  const summaryEl = document.getElementById('stats-summary');
  const tableEl = document.getElementById('statistics-table');
  
  if (!stats || !stats.details) {
    tableEl.innerHTML = '<tr class="empty-state"><td colspan="6"><div class="empty-icon">📊</div><p>该时间范围内暂无统计数据</p></td></tr>';
    return;
  }
  
  if (summaryEl) {
    const total = stats.total_on_time + stats.total_overtime + stats.total_missing;
    const onTimeRate = total > 0 ? ((stats.total_on_time / total) * 100).toFixed(1) : 0;
    
    summaryEl.innerHTML = `
      <div class="stats-grid" style="margin-bottom: 0;">
        <div class="stat-card primary">
          <div class="stat-icon">✅</div>
          <div class="stat-content">
            <h3 class="stat-label">准时填报</h3>
            <div class="stat-value">${stats.total_on_time}</div>
            <p class="stat-change">次</p>
          </div>
        </div>
        <div class="stat-card warning">
          <div class="stat-icon">⏰</div>
          <div class="stat-content">
            <h3 class="stat-label">超时填报</h3>
            <div class="stat-value">${stats.total_overtime}</div>
            <p class="stat-change">次</p>
          </div>
        </div>
        <div class="stat-card danger">
          <div class="stat-icon">❌</div>
          <div class="stat-content">
            <h3 class="stat-label">漏填记录</h3>
            <div class="stat-value">${stats.total_missing}</div>
            <p class="stat-change">次</p>
          </div>
        </div>
        <div class="stat-card info">
          <div class="stat-icon">📊</div>
          <div class="stat-content">
            <h3 class="stat-label">准时率</h3>
            <div class="stat-value">${onTimeRate}%</div>
            <p class="stat-change">整体表现</p>
          </div>
        </div>
      </div>
    `;
  }
  
  tableEl.innerHTML = stats.details.map(d => {
    const total = d.on_time + d.overtime + d.missing;
    const rate = total > 0 ? ((d.on_time / total) * 100).toFixed(1) : 0;
    
    return `
      <tr>
        <td><strong>${d.manager_name}</strong></td>
        <td>${d.team || '-'}</td>
        <td><span class="badge badge-success">${d.on_time}</span></td>
        <td><span class="badge badge-warning">${d.overtime}</span></td>
        <td><span class="badge badge-danger">${d.missing}</span></td>
        <td><strong>${rate}%</strong></td>
      </tr>
    `;
  }).join('');
}

async function exportExcel() {
  const startDate = document.getElementById('stats-start-date').value;
  const endDate = document.getElementById('stats-end-date').value;
  
  if (!startDate || !endDate) {
    toast('请选择日期范围');
    return;
  }
  
  try {
    showLoading();
    toast('📥 正在生成Excel文件...');
    await Api.exportExcel({ start_date: startDate, end_date: endDate });
    toast('✅ Excel文件已下载');
  } catch (error) {
    console.error('导出失败:', error);
    toast('❌ 导出失败: ' + error.message);
  } finally {
    hideLoading();
  }
}

// 提醒日志
async function loadReminders() {
  const date = document.getElementById('reminder-date').value;
  const manager = document.getElementById('reminder-manager').value;
  
  try {
    showLoading();
    const reminders = await Api.reminders({ date, manager_name: manager });
    renderReminders(reminders);
    toast('✅ 提醒日志已加载');
  } catch (error) {
    console.error('加载提醒日志失败:', error);
    toast('❌ 加载失败: ' + error.message);
  } finally {
    hideLoading();
  }
}

function renderReminders(reminders) {
  const timeline = document.getElementById('reminders-timeline');
  
  if (!reminders || reminders.length === 0) {
    timeline.innerHTML = '<div class="empty-state"><div class="empty-icon">🔔</div><p>该条件下暂无提醒日志</p></div>';
    return;
  }
  
  timeline.innerHTML = reminders.map(r => `
    <div class="timeline-item">
      <div class="timeline-content">
        <div class="timeline-header">
          <span class="timeline-title">${r.manager_name || '系统'}</span>
          <span class="timeline-time">${formatTime(r.reminder_time)}</span>
        </div>
        <div class="timeline-body">
          <p><strong>提醒类型:</strong> ${r.fill_status === 'on_time' ? '✅ 准时' : r.fill_status === 'overtime' ? '⏰ 超时' : '❌ 漏填'}</p>
          <p><strong>预约日期:</strong> ${r.appointment_date}</p>
          ${r.booked_count !== null ? `<p><strong>已预约:</strong> ${r.booked_count} 户</p>` : ''}
        </div>
      </div>
    </div>
  `).join('');
}

// 发送通报视图
async function loadSendView() {
  await loadRules();
}

async function loadRules() {
  try {
    const rules = await Api.rules();
    state.rules = rules;
    
    const select = document.getElementById('rule-select');
    if (select) {
      select.innerHTML = '<option value="">请选择规则</option>' + 
        rules.map(r => `<option value="${r.rule_key}">${r.rule_name}</option>`).join('');
    }
  } catch (error) {
    console.error('加载规则失败:', error);
  }
}

async function previewReport() {
  const ruleKey = document.getElementById('rule-select').value;
  const date = document.getElementById('send-date').value;
  const previewContent = document.getElementById('preview-content');
  
  if (!ruleKey || !date) {
    previewContent.innerHTML = '<div class="preview-empty"><span class="empty-icon">📄</span><p>请选择规则和日期以预览消息</p></div>';
    return;
  }
  
  try {
    showLoading();
    const report = await Api.preview({ rule_key: ruleKey, date });
    
    if (!report || !report.items || report.items.length === 0) {
      previewContent.innerHTML = '<div class="preview-empty"><span class="empty-icon">✅</span><p>当前无需发送通报（所有人已达标）</p></div>';
    } else {
      previewContent.textContent = report.message;
    }
  } catch (error) {
    console.error('预览失败:', error);
    previewContent.innerHTML = '<div class="preview-empty"><span class="empty-icon">❌</span><p>预览失败: ' + error.message + '</p></div>';
  } finally {
    hideLoading();
  }
}

async function sendReport() {
  const ruleKey = document.getElementById('rule-select').value;
  const date = document.getElementById('send-date').value;
  
  if (!ruleKey || !date) {
    toast('请选择规则和日期');
    return;
  }
  
  if (!confirm('确定要发送此通报到企业微信吗？')) {
    return;
  }
  
  try {
    showLoading();
    toast('📤 正在发送通报...');
    await Api.sendReport({ rule_key: ruleKey, date });
    toast('✅ 通报已成功发送');
    document.getElementById('preview-content').innerHTML = '<div class="preview-empty"><span class="empty-icon">✅</span><p>通报已发送成功</p></div>';
  } catch (error) {
    console.error('发送失败:', error);
    toast('❌ 发送失败: ' + error.message);
  } finally {
    hideLoading();
  }
}

// 调度器视图
async function loadSchedulerView() {
  await loadSchedulerStatus();
}

async function updateSchedulerStatus() {
  try {
    const status = await Api.schedulerStatus();
    state.schedulerStatus = status;
    
    // 更新侧边栏状态
    const indicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');
    
    if (status.running) {
      indicator.className = 'status-indicator running';
      statusText.textContent = '运行中';
    } else {
      indicator.className = 'status-indicator stopped';
      statusText.textContent = '已停止';
    }
  } catch (error) {
    console.error('获取调度器状态失败:', error);
  }
}

async function loadSchedulerStatus() {
  try {
    const status = await Api.schedulerStatus();
    state.schedulerStatus = status;
    
    const infoEl = document.getElementById('scheduler-info');
    const jobsEl = document.getElementById('jobs-grid');
    
    if (infoEl) {
      infoEl.innerHTML = `
        <div class="info-item">
          <div class="info-item-icon">${status.running ? '▶️' : '⏸️'}</div>
          <div class="info-item-value">${status.running ? '运行中' : '已停止'}</div>
          <div class="info-item-label">调度器状态</div>
        </div>
        <div class="info-item">
          <div class="info-item-icon">📋</div>
          <div class="info-item-value">${status.jobs ? status.jobs.length : 0}</div>
          <div class="info-item-label">定时任务</div>
        </div>
        <div class="info-item">
          <div class="info-item-icon">⏰</div>
          <div class="info-item-value">${status.jobs ? status.jobs.filter(j => j.next_run_time).length : 0}</div>
          <div class="info-item-label">待执行</div>
        </div>
      `;
    }
    
    if (jobsEl && status.jobs) {
      jobsEl.innerHTML = status.jobs.map(job => `
        <div class="job-card">
          <div class="job-header">
            <div>
              <div class="job-title">${job.name || job.id}</div>
              <div class="job-schedule">⏰ ${job.trigger || '未设置'}</div>
            </div>
            <div class="job-actions">
              <button class="job-btn" onclick="triggerJob('${job.id}')" title="立即执行">▶️</button>
            </div>
          </div>
          <div class="job-info">
            ${job.next_run_time ? `下次执行: ${formatTime(job.next_run_time)}` : '未安排'}
          </div>
        </div>
      `).join('');
    }
  } catch (error) {
    console.error('加载调度器状态失败:', error);
    toast('❌ 加载失败: ' + error.message);
  }
}

async function startScheduler() {
  if (!confirm('确定要启动调度器吗？启动后将按预设时间自动发送通报。')) {
    return;
  }
  
  try {
    showLoading();
    await Api.startScheduler();
    toast('✅ 调度器已启动');
    await updateSchedulerStatus();
    await loadSchedulerStatus();
  } catch (error) {
    console.error('启动失败:', error);
    toast('❌ 启动失败: ' + error.message);
  } finally {
    hideLoading();
  }
}

async function stopScheduler() {
  if (!confirm('确定要停止调度器吗？停止后将不会自动发送通报。')) {
    return;
  }
  
  try {
    showLoading();
    await Api.stopScheduler();
    toast('✅ 调度器已停止');
    await updateSchedulerStatus();
    await loadSchedulerStatus();
  } catch (error) {
    console.error('停止失败:', error);
    toast('❌ 停止失败: ' + error.message);
  } finally {
    hideLoading();
  }
}

async function triggerJob(jobId) {
  if (!confirm(`确定要立即执行任务 ${jobId} 吗？`)) {
    return;
  }
  
  try {
    showLoading();
    toast('⚙️ 正在执行任务...');
    await Api.triggerJob(jobId);
    toast('✅ 任务执行成功');
  } catch (error) {
    console.error('执行失败:', error);
    toast('❌ 执行失败: ' + error.message);
  } finally {
    hideLoading();
  }
}

// 配置视图
async function loadConfigView() {
  await loadManagers();
  await loadDeliveryStaff();
}

async function loadManagers() {
  try {
    const data = await Api.deliveryStaff();
    state.managers = data.customer_managers || [];
    
    const managersGrid = document.getElementById('managers-grid');
    if (managersGrid) {
      managersGrid.innerHTML = state.managers.map(m => {
        const initial = m.name.charAt(0);
        const colors = ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b'];
        const color = colors[Math.floor(Math.random() * colors.length)];
        
        return `
          <div class="personnel-card">
            <div class="personnel-avatar" style="background: ${color};">${initial}</div>
            <div class="personnel-name">${m.name}</div>
            <div class="personnel-role">${m.team || '客户经理'}</div>
            ${m.mobile ? `<div class="personnel-contact">${m.mobile}</div>` : ''}
          </div>
        `;
      }).join('');
    }
    
    // 更新提醒日志的客户经理选择器
    const reminderSelect = document.getElementById('reminder-manager');
    if (reminderSelect) {
      reminderSelect.innerHTML = '<option value="">全部客户经理</option>' +
        state.managers.map(m => `<option value="${m.name}">${m.name}</option>`).join('');
    }
  } catch (error) {
    console.error('加载客户经理失败:', error);
  }
}

async function loadDeliveryStaff() {
  try {
    const data = await Api.deliveryStaff();
    
    const gaozhuangGrid = document.getElementById('gaozhuang-grid');
    if (gaozhuangGrid && data.gaozhuang_staff) {
      gaozhuangGrid.innerHTML = data.gaozhuang_staff.map(s => {
        const initial = s.name.charAt(0);
        return `
          <div class="personnel-card">
            <div class="personnel-avatar" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">${initial}</div>
            <div class="personnel-name">${s.name}</div>
            <div class="personnel-role">高端装维</div>
            ${s.mobile ? `<div class="personnel-contact">${s.mobile}</div>` : ''}
          </div>
        `;
      }).join('');
    }
    
    const zhiyunGrid = document.getElementById('zhiyun-grid');
    if (zhiyunGrid && data.zhiyun_engineers) {
      zhiyunGrid.innerHTML = data.zhiyun_engineers.map(e => {
        const initial = e.name.charAt(0);
        return `
          <div class="personnel-card">
            <div class="personnel-avatar" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">${initial}</div>
            <div class="personnel-name">${e.name}</div>
            <div class="personnel-role">智云工程师</div>
            ${e.mobile ? `<div class="personnel-contact">${e.mobile}</div>` : ''}
          </div>
        `;
      }).join('');
    }
  } catch (error) {
    console.error('加载交付人员失败:', error);
  }
}

console.log('📱 预约通报系统 v2.0 - 现代化Dashboard');
