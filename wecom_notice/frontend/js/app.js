const dateInput = document.querySelector('#target-date');
const ruleSelect = document.querySelector('#rule-select');
const preview = document.querySelector('#preview');
const adminToken = document.querySelector('#admin-token');
const policyText = document.querySelector('#recipient-policy');
let rules = [];

function localDate(offset = 1) {
  const value = new Date();
  value.setDate(value.getDate() + offset);
  return value.toISOString().slice(0, 10);
}
function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
}
function toast(message) {
  const node = document.querySelector('#toast');
  node.textContent = message; node.classList.add('visible');
  setTimeout(() => node.classList.remove('visible'), 2600);
}
function selectedRule() { return rules.find(rule => rule.rule_key === ruleSelect.value); }
function policyName(policy) {
  return { customer_managers: '对应客户经理', management: '3 位经理/副经理', customer_managers_and_management: '对应客户经理 + 管理人员' }[policy?.target] || '未配置';
}
function renderMetrics(summary) {
  document.querySelector('#metrics').innerHTML = [
    ['明日预约', summary.appointment_count, ''],
    ['已达标客户经理', summary.qualified_manager_count, 'good'],
    ['预约不足', summary.shortage_manager_count, 'warning'],
    ['需集中派单', summary.dispatch_count, ''],
    ['客户经理名单', summary.roster_count, ''],
  ].map(([label, value, cls]) => `<div class="metric ${cls}"><span class="muted">${label}</span><span class="number">${value}</span></div>`).join('');
  document.querySelector('#upload-status').textContent = summary.latest_upload ? `最近上传：${summary.latest_upload}` : '暂无金山文档上传记录';
  document.querySelector('#progress-table').innerHTML = summary.manager_progress.map(item => {
    const gap = Math.max(0, 2 - item.booked);
    return `<tr><td>${esc(item.name)}</td><td>${item.booked}</td><td>${gap ? `<span class="badge warn">缺 ${gap} 户</span>` : '0'}</td><td>${gap ? '<span class="badge warn">未达标</span>' : '<span class="badge ok">已达标</span>'}</td></tr>`;
  }).join('');
}
function renderRecords(records) {
  document.querySelector('#records-table').innerHTML = records.length ? records.map(record => `<tr><td>${esc(record.manager_name)}</td><td>${esc(record.company_name || '未填写')}</td><td>${esc(record.contact_name_title || '未填写')}</td><td>${esc(record.appointment_slot || '未填写')}</td><td>${esc(record.opportunity_content || record.opportunity_type || '未填写')}</td><td>${esc(record.delivery_staff_name || '未填写')}</td></tr>`).join('') : '<tr><td colspan="6" class="muted">暂无记录</td></tr>';
}
function renderRoster(data) {
  document.querySelector('#roster').innerHTML = `<div class="roster-group"><strong>客户经理（${data.customer_managers.length}）</strong><div class="roster-names">${data.customer_managers.map(person => esc(person.name)).join('、')}</div></div><div class="roster-group"><strong>经理/副经理（${data.manager_recipients.length}）</strong><div class="roster-names">${data.manager_recipients.map(person => esc(person.name)).join('、')}</div></div>`;
}
function renderLogs(logs) {
  document.querySelector('#logs-table').innerHTML = logs.length ? logs.map(log => `<tr><td>${esc(log.sent_at)}</td><td>${esc(log.rule_key)}</td><td>${log.status === 'success' ? '<span class="badge ok">成功</span>' : '<span class="badge fail">失败</span>'}</td><td>${esc(JSON.parse(log.mentioned_json || '[]').map(person => person.name).join('、'))}</td><td>${esc(log.error)}</td></tr>`).join('') : '<tr><td colspan="5" class="muted">暂无发送日志</td></tr>';
}
async function refresh() {
  const target = dateInput.value;
  try {
    const [summary, records, roster, logData] = await Promise.all([Api.summary(target), Api.records(target), Api.roster(), Api.logs()]);
    renderMetrics(summary); renderRecords(records.records); renderRoster(roster); renderLogs(logData.logs);
  } catch (error) { toast(error.message); }
}
async function loadRules() {
  const result = await Api.rules(); rules = result.rules;
  ruleSelect.innerHTML = rules.map(rule => `<option value="${esc(rule.rule_key)}">${esc(rule.name)}</option>`).join('');
  updatePolicy();
}
function updatePolicy() { const rule = selectedRule(); policyText.textContent = policyName(rule?.recipient_policy); }
async function previewReport() {
  const result = await Api.preview({ rule_key: ruleSelect.value, target_date: dateInput.value });
  preview.value = result.message; policyText.textContent = `${policyName(result.rule.recipient_policy)}：${result.recipients.map(person => person.name).join('、') || '尚未配置手机号/企业微信 userid'}`;
}
async function sendReport() {
  if (!preview.value && !window.confirm('还没有生成预览，仍要发送吗？')) return;
  const result = await Api.send({ rule_key: ruleSelect.value, target_date: dateInput.value }, adminToken.value);
  toast(`发送成功，已通知 ${result.mentioned.length} 人`); await refresh();
}
dateInput.value = localDate();
ruleSelect.addEventListener('change', updatePolicy);
dateInput.addEventListener('change', refresh);
document.querySelector('#refresh').addEventListener('click', refresh);
document.querySelector('#preview-button').addEventListener('click', () => previewReport().catch(error => toast(error.message)));
document.querySelector('#send-button').addEventListener('click', () => sendReport().catch(error => toast(error.message)));
Promise.all([loadRules(), refresh()]).catch(error => toast(error.message));
