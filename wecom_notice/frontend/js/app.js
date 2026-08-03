// ==================== 全局变量 ====================
const dateInput = document.querySelector('#target-date');
const ruleSelect = document.querySelector('#rule-select');
const preview = document.querySelector('#preview');
const policyText = document.querySelector('#recipient-policy');
let rules = [];
let allManagers = [];

// ==================== 工具函数 ====================
function localDate(offset = 1) {
  const value = new Date();
  value.setDate(value.getDate() + offset);
  return value.toISOString().slice(0, 10);
}

function setDateOffset(offset) {
  dateInput.value = localDate(offset);
  dateInput.dispatchEvent(new Event('change'));
}

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
}

function toast(message, duration = 3000) {
  const node = document.querySelector('#toast');
  node.textContent = message;
  node.classList.add('visible');
  setTimeout(() => node.classList.remove('visible'), duration);
}

function showLoading() {
  document.querySelector('#loading-overlay').classList.add('visible');
}

function hideLoading() {
  document.querySelector('#loading-overlay').classList.remove('visible');
}

function selectedRule() {
  return rules.find(rule => rule.rule_key === ruleSelect.value);
}

function policyName(policy) {
  const mapping = {
    customer_managers: '对应客户经理',
    management: '3 位经理/副经理',
    customer_managers_and_management: '对应客户经理 + 管理人员'
  };
  return mapping[policy?.target] || '未配置';
}

function formatFillStatus(status) {
  const mapping = {
    on_time: '<span class="badge ok">准时</span>',
    overtime: '<span class="badge warn">超时</span>',
    missing: '<span class="badge fail">漏填</span>'
  };
  return mapping[status] || status;
}

// ==================== 标签页切换 ====================
document.querySelectorAll('.tab-button').forEach(button => {
  button.addEventListener('click', () => {
    const targetTab = button.dataset.tab;

    // 切换按钮状态
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    button.classList.add('active');

    // 切换内容
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.querySelector(`#tab-${targetTab}`).classList.add('active');

    // 加载对应数据
    if (targetTab === 'statistics') {
      loadStatistics();
    } else if (targetTab === 'reminders') {
      loadReminders();
    } else if (targetTab === 'config') {
      loadSchedulerStatus();
    }
  });
});

// ==================== 总览页面渲染 ====================
function renderMetrics(summary) {
  document.querySelector('#metrics').innerHTML = [
    ['明日预约', summary.appointment_count, ''],
    ['已达标客户经理', summary.qualified_manager_count, 'good'],
    ['预约不足', summary.shortage_manager_count, 'warning'],
    ['需集中派单', summary.dispatch_count, ''],
    ['客户经理名单', summary.roster_count, ''],
  ].map(([label, value, cls]) =>
    `<div class="metric ${cls}"><span class="muted">${label}</span><span class="number">${value}</span></div>`
  ).join('');

  document.querySelector('#upload-status').textContent = summary.latest_upload
    ? `📅 最近上传：${summary.latest_upload}`
    : '⚠️ 暂无金山文档上传记录';

  document.querySelector('#progress-table').innerHTML = summary.manager_progress.map(item => {
    const gap = Math.max(0, 2 - item.booked);
    const team = item.team ? esc(item.team) : '未分组';
    const historyCounts = item.history_counts || { overtime: 0, missing: 0 };

    return `<tr>
      <td>${esc(item.name)}</td>
      <td>${team}</td>
      <td><strong>${item.booked}</strong></td>
      <td>${gap ? `<span class="badge warn">缺 ${gap} 户</span>` : '<span class="badge ok">0</span>'}</td>
      <td>${gap ? '<span class="badge warn">未达标</span>' : '<span class="badge ok">已达标</span>'}</td>
      <td>${historyCounts.overtime > 0 ? `<span class="badge warn">${historyCounts.overtime}</span>` : '-'}</td>
      <td>${historyCounts.missing > 0 ? `<span class="badge fail">${historyCounts.missing}</span>` : '-'}</td>
    </tr>`;
  }).join('');
}

function renderRecords(records) {
  document.querySelector('#record-count').textContent = `共 ${records.length} 条`;
  document.querySelector('#records-table').innerHTML = records.length
    ? records.map(record => `<tr>
        <td>${esc(record.manager_name)}</td>
        <td>${esc(record.company_name || '未填写')}</td>
        <td>${esc(record.contact_name_title || '未填写')}</td>
        <td>${esc(record.appointment_slot || '未填写')}</td>
        <td>${esc(record.opportunity_content || record.opportunity_type || '未填写')}</td>
        <td>${esc(record.delivery_staff_name || '未填写')}</td>
      </tr>`).join('')
    : '<tr><td colspan="6" class="muted">暂无记录</td></tr>';
}

function renderRoster(data) {
  // 客户经理按团队分组
  const teams = data.customer_managers.reduce((groups, person) => {
    const team = person.team || '未分组';
    (groups[team] ||= []).push(person);
    return groups;
  }, {});

  const customerManagers = Object.entries(teams)
    .map(([team, people]) => `
      <div class="roster-group">
        <strong>客户经理 - ${esc(team)}（${people.length}人）</strong>
        <div class="roster-names">${people.map(p => esc(p.name)).join('、')}</div>
      </div>
    `).join('');

  const management = `
    <div class="roster-group">
      <strong>经理/副经理（${data.manager_recipients.length}人）</strong>
      <div class="roster-names">${data.manager_recipients.map(p => esc(p.name)).join('、')}</div>
    </div>
  `;

  // 高端装维和智云工程师
  const deliveryStaff = data.delivery_staff || [];
  const gaozhuang = deliveryStaff.filter(p => p.role === 'gaozhuang');
  const zhiyun = deliveryStaff.filter(p => p.role === 'zhiyun');

  const gaozhuangHtml = gaozhuang.length ? `
    <div class="roster-group">
      <strong>高端装维（${gaozhuang.length}人）</strong>
      <div class="roster-names">${gaozhuang.map(p => esc(p.name)).join('、')}</div>
    </div>
  ` : '';

  const zhiyunHtml = zhiyun.length ? `
    <div class="roster-group">
      <strong>智云工程师（${zhiyun.length}人）</strong>
      <div class="roster-names">${zhiyun.map(p => esc(p.name)).join('、')}</div>
    </div>
  ` : '';

  document.querySelector('#roster').innerHTML = customerManagers + management + gaozhuangHtml + zhiyunHtml;

  const totalCount = data.customer_managers.length + data.manager_recipients.length + deliveryStaff.length;
  document.querySelector('#total-personnel').textContent = `共 ${totalCount} 人`;
}

function renderLogs(logs) {
  document.querySelector('#logs-table').innerHTML = logs.length
    ? logs.slice(0, 10).map(log => {
        const mentioned = JSON.parse(log.mentioned_json || '[]').map(p => p.name).join('、') || '-';
        return `<tr>
          <td>${esc(log.sent_at)}</td>
          <td>${esc(log.rule_key)}</td>
          <td>${log.status === 'success' ? '<span class="badge ok">成功</span>' : '<span class="badge fail">失败</span>'}</td>
          <td>${esc(mentioned)}</td>
        </tr>`;
      }).join('')
    : '<tr><td colspan="4" class="muted">暂无发送日志</td></tr>';
}

// ==================== 调度器状态 ====================
async function updateSchedulerStatus() {
  try {
    const status = await Api.schedulerStatus();
    const statusDot = document.querySelector('#status-dot');
    const statusText = document.querySelector('#status-text');

    if (status.running) {
      statusDot.classList.remove('inactive');
      statusDot.classList.add('active');
      statusText.textContent = '调度器运行中';
    } else {
      statusDot.classList.remove('active');
      statusDot.classList.add('inactive');
      statusText.textContent = '调度器已停止';
    }
  } catch (error) {
    console.error('获取调度器状态失败:', error);
  }
}

async function loadSchedulerStatus() {
  try {
    const status = await Api.schedulerStatus();
    const info = document.querySelector('#scheduler-info');

    if (status.running) {
      info.innerHTML = `
        <p><strong>✅ 调度器状态：</strong>运行中</p>
        <p><strong>📋 已注册任务：</strong>${status.jobs?.length || 0} 个</p>
        <p><strong>⏰ 任务列表：</strong></p>
        <ul style="margin: 8px 0; padding-left: 20px;">
          ${(status.jobs || []).map(job => `<li>${esc(job.name || job.id)} - 下次运行: ${esc(job.next_run_time || '未知')}</li>`).join('')}
        </ul>
      `;
    } else {
      info.innerHTML = `
        <p><strong>⏸️ 调度器状态：</strong>已停止</p>
        <p class="muted">点击"启动调度器"按钮开始自动通报</p>
      `;
    }
  } catch (error) {
    toast('加载调度器状态失败: ' + error.message);
  }
}

// ==================== 累计统计 ====================
async function loadStatistics() {
  try {
    const startDate = document.querySelector('#stats-start-date').value;
    const endDate = document.querySelector('#stats-end-date').value;
    const fillStatus = document.querySelector('#status-filter').value;

    // 加载累计统计数据
    const cumulative = await Api.cumulativeStats({ start_date: startDate, end_date: endDate });
    document.querySelector('#stat-ontime').textContent = cumulative.on_time || 0;
    document.querySelector('#stat-overtime').textContent = cumulative.overtime || 0;
    document.querySelector('#stat-missing').textContent = cumulative.missing || 0;
    document.querySelector('#stat-total').textContent = cumulative.total || 0;

    // 加载明细数据
    const details = await Api.statistics({ start_date: startDate, end_date: endDate, fill_status: fillStatus });

    document.querySelector('#statistics-table').innerHTML = details.statistics?.length
      ? details.statistics.map(stat => `<tr>
          <td>${esc(stat.date)}</td>
          <td>${esc(stat.manager_name)}</td>
          <td>${formatFillStatus(stat.fill_status)}</td>
          <td>${esc(stat.fill_time || '-')}</td>
          <td>${stat.reminder_count || 0}</td>
          <td>${stat.fill_count || 0}</td>
        </tr>`).join('')
      : '<tr><td colspan="6" class="muted">暂无统计数据</td></tr>';

  } catch (error) {
    toast('加载统计数据失败: ' + error.message);
  }
}

// ==================== 提醒日志 ====================
async function loadReminders() {
  try {
    const date = document.querySelector('#reminder-date').value;
    const managerName = document.querySelector('#reminder-manager').value;

    const result = await Api.reminders({ date, manager_name: managerName });

    document.querySelector('#reminders-table').innerHTML = result.logs?.length
      ? result.logs.map(log => `<tr>
          <td>${esc(log.reminded_at)}</td>
          <td>${esc(log.manager_name)}</td>
          <td><span class="badge ok">第 ${log.reminder_sequence} 次</span></td>
          <td>${log.current_count || 0}</td>
          <td>${log.overtime_count || 0}</td>
          <td>${log.missing_count || 0}</td>
        </tr>`).join('')
      : '<tr><td colspan="6" class="muted">暂无提醒日志</td></tr>';

  } catch (error) {
    toast('加载提醒日志失败: ' + error.message);
  }
}

// ==================== 主页面刷新 ====================
async function refresh() {
  const target = dateInput.value;
  try {
    showLoading();
    const [summary, records, roster, logData, deliveryStaff] = await Promise.all([
      Api.summary(target),
      Api.records(target),
      Api.roster(),
      Api.logs(),
      Api.deliveryStaff().catch(() => ({ gaozhuang: [], zhiyun: [] }))
    ]);

    // 合并交付人员到roster
    roster.delivery_staff = [...deliveryStaff.gaozhuang, ...deliveryStaff.zhiyun];

    renderMetrics(summary);
    renderRecords(records.records);
    renderRoster(roster);
    renderLogs(logData.logs);

    // 保存客户经理列表供提醒日志筛选使用
    allManagers = summary.manager_progress.map(m => m.name);
    updateManagerFilter();
  } catch (error) {
    toast('刷新失败: ' + error.message);
  } finally {
    hideLoading();
  }
}

function updateManagerFilter() {
  const select = document.querySelector('#reminder-manager');
  select.innerHTML = '<option value="">全部</option>' +
    allManagers.map(name => `<option value="${esc(name)}">${esc(name)}</option>`).join('');
}

// ==================== 通报预览和发送 ====================
async function loadRules() {
  const result = await Api.rules();
  rules = result.rules;
  ruleSelect.innerHTML = rules.map(rule =>
    `<option value="${esc(rule.rule_key)}">${esc(rule.name)}</option>`
  ).join('');
  updatePolicy();
}

function updatePolicy() {
  const rule = selectedRule();
  policyText.textContent = policyName(rule?.recipient_policy);
}

async function previewReport() {
  try {
    showLoading();
    const result = await Api.preview({
      rule_key: ruleSelect.value,
      target_date: dateInput.value
    });
    preview.value = result.message;
    policyText.textContent = `${policyName(result.rule.recipient_policy)}：${
      result.recipients.map(p => p.name).join('、') || '尚未配置手机号/企业微信 userid'
    }`;
    toast('预览生成成功', 2000);
  } catch (error) {
    toast('预览失败: ' + error.message);
  } finally {
    hideLoading();
  }
}

async function sendReport() {
  if (!preview.value && !window.confirm('还没有生成预览，仍要发送吗？')) return;

  try {
    showLoading();
    const result = await Api.send({
      rule_key: ruleSelect.value,
      target_date: dateInput.value
    });
    toast(`✅ 发送成功，已通知 ${result.mentioned.length} 人`, 3000);
    await refresh();
  } catch (error) {
    toast('发送失败: ' + error.message);
  } finally {
    hideLoading();
  }
}

// ==================== 调度器控制 ====================
async function startScheduler() {
  if (!confirm('确定要启动调度器吗？启动后将自动按照预设时间发送通报。')) return;

  try {
    showLoading();
    await Api.startScheduler();
    toast('✅ 调度器已启动', 3000);
    await updateSchedulerStatus();
    await loadSchedulerStatus();
  } catch (error) {
    toast('启动失败: ' + error.message);
  } finally {
    hideLoading();
  }
}

async function stopScheduler() {
  if (!confirm('确定要停止调度器吗？')) return;

  try {
    showLoading();
    await Api.stopScheduler();
    toast('⏸️ 调度器已停止', 3000);
    await updateSchedulerStatus();
    await loadSchedulerStatus();
  } catch (error) {
    toast('停止失败: ' + error.message);
  } finally {
    hideLoading();
  }
}

async function toggleScheduler() {
  try {
    const status = await Api.schedulerStatus();
    if (status.running) {
      await stopScheduler();
    } else {
      await startScheduler();
    }
  } catch (error) {
    toast('操作失败: ' + error.message);
  }
}

// ==================== Excel导出 ====================
function exportExcel() {
  const startDate = document.querySelector('#stats-start-date').value;
  const endDate = document.querySelector('#stats-end-date').value;

  try {
    Api.exportExcel({ start_date: startDate, end_date: endDate });
    toast('📥 Excel文件正在下载...', 2000);
  } catch (error) {
    toast('导出失败: ' + error.message);
  }
}

// ==================== 事件监听 ====================
dateInput.value = localDate();
document.querySelector('#stats-start-date').value = localDate(-7);
document.querySelector('#stats-end-date').value = localDate(0);
document.querySelector('#reminder-date').value = localDate(0);

ruleSelect.addEventListener('change', updatePolicy);
dateInput.addEventListener('change', refresh);
document.querySelector('#refresh').addEventListener('click', refresh);
document.querySelector('#toggle-scheduler').addEventListener('click', toggleScheduler);
document.querySelector('#preview-button').addEventListener('click', () => previewReport());
document.querySelector('#send-button').addEventListener('click', () => sendReport());
document.querySelector('#export-excel').addEventListener('click', exportExcel);
document.querySelector('#start-scheduler').addEventListener('click', startScheduler);
document.querySelector('#stop-scheduler').addEventListener('click', stopScheduler);

// ==================== 初始化 ====================
Promise.all([
  loadRules(),
  refresh(),
  updateSchedulerStatus()
]).catch(error => toast('初始化失败: ' + error.message));

// 定期更新调度器状态
setInterval(updateSchedulerStatus, 30000);
