/**
 * 政企标准化信息收集 → 家庭专项走访统计：AirScript 上传脚本
 * ============================================================
 * 在金山文档（AirSheet）里定时/手动运行，把当前工作表的 4 个关键列
 * 读成 JSON 行，POST 到服务器的 /zhengqi/upload-rows 接口。
 *
 * 为什么是 JSON 行而不是传文件：
 *   AirScript 无法把工作簿导出成 xlsx 字节，且禁止请求 IP / 带端口的 URL。
 *   统计只依赖 4 列（见下），因此直接读单元格发 JSON 最稳、无授权坑。
 *
 * 使用前：
 *   1. AirScript 编辑器 → 右侧「服务」→ 添加「网络 API」，填入 SERVER_URL 的域名
 *   2. 把 SERVER_URL 改成你的 HTTPS 域名接口（必须 https、不带端口、不用 IP）
 *   3. 确认下面的列号与实际表头一致（默认 E/G/K/T）
 *   4. 若表格第 1 行是表头，HEADER_ROWS 保持 1
 */

function main() {
  // ⚠️ 改成你的 HTTPS 反代域名，例如 https://report.example.com/zhengqi/upload-rows
  const SERVER_URL = 'https://your-domain.example.com/zhengqi/upload-rows';

  // 如接口需要令牌，填在这里；不需要就留空字符串
  const TOKEN = '';

  // 列号（1 基）：E=5 姓名, G=7 拜访对象类型, K=11 预约上门日期, T=20 拜访结果
  const COL = { name: 5, type: 7, appt_date: 11, result: 20 };
  const HEADER_ROWS = 1; // 表头占的行数

  const sheet = Application.ActiveWorkbook.ActiveSheet;
  const usedRange = sheet.UsedRange;
  const lastRow = usedRange.Row + usedRange.Rows.Count - 1;

  const rows = [];
  for (let r = HEADER_ROWS + 1; r <= lastRow; r++) {
    const name = readCell(sheet, r, COL.name);
    const type = readCell(sheet, r, COL.type);
    // 整行姓名和类型都空，视为空行，跳过
    if (!name && !type) continue;
    rows.push({
      name: name,
      type: type,
      appt_date: readCell(sheet, r, COL.appt_date),
      result: readCell(sheet, r, COL.result),
    });
  }

  if (rows.length === 0) {
    console.log('没有可上传的数据行。');
    return { success: false, message: '空数据' };
  }

  return send(SERVER_URL, TOKEN, rows);
}

/** 读单元格并归一化成字符串：日期转成 YYYY-MM-DD，其余去空白。 */
function readCell(sheet, row, col) {
  const cell = sheet.Range(sheet.Cells(row, col).Address());
  let v = cell.Value2;
  if (v === null || v === undefined) return '';
  // AirSheet 日期为从 1899-12-30 起的序列号
  if (typeof v === 'number' && isDateColumn(cell)) {
    return serialToDate(v);
  }
  return String(v).trim();
}

/** 单元格数字格式含日期标记时，按日期解释。 */
function isDateColumn(cell) {
  const fmt = String(cell.NumberFormat || '');
  return /[ymd]/i.test(fmt) && !/[eE]\+/.test(fmt);
}

/** Excel 日期序列号 → YYYY-MM-DD */
function serialToDate(serial) {
  const ms = Math.round((serial - 25569) * 86400 * 1000); // 25569 = 1970-01-01 的序列号
  const d = new Date(ms);
  const p = (n) => String(n).padStart(2, '0');
  return d.getUTCFullYear() + '-' + p(d.getUTCMonth() + 1) + '-' + p(d.getUTCDate());
}

/** POST JSON 行到服务器。 */
function send(url, token, rows) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = 'Bearer ' + token;

  try {
    const resp = HTTP.fetch(url, {
      method: 'POST',
      timeout: 60000,
      headers: headers,
      body: JSON.stringify({ rows: rows, file_name: '政企标准化信息收集.json' }),
    });
    const status = resp.status;
    const text = resp.text();
    console.log('行数：' + rows.length + '，HTTP ' + status);
    console.log('服务器返回：' + text);
    if (status < 200 || status >= 300) {
      throw new Error('上传失败 HTTP ' + status + '：' + text);
    }
    return { success: true, status: status, sent: rows.length, message: text };
  } catch (e) {
    console.log('上传异常：' + e.message);
    return { success: false, message: e.message };
  }
}

return main();
