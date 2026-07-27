/**
 * 政企标准化信息收集V3（多维表格）→ 走访统计服务器推送
 * AirScript 1.0 — 工具 → 自动化脚本
 *
 * 使用前：
 *   1. 在金山文档打开「政企标准化信息收集V3」多维表格
 *   2. 工具 → 自动化脚本 → 新建脚本，粘贴此文件全部内容
 *   3. 右侧「服务」→ 添加「网络 API」，填入 shanguantang.site
 *   4. 点击运行，或设置触发器定时推送
 */

var SERVER_URL = 'https://shanguantang.site/zhengqi/upload-rows';

// 多维表格字段名（与表头列名严格对应）
var FIELD_NAME   = '客户经理姓名';
var FIELD_TYPE   = '拜访对象类型';
var FIELD_DATE   = '预约上门日期';
var FIELD_RESULT = '拜访结果（上门后回填）';

function main() {
  var sheet = Application.ActiveSheet;

  var allRows = [];
  var offset  = null;

  // 分页读取全部记录（不限定视图，读取所有行）
  do {
    var params = {
      MaxRecords: 500,
      Fields:     [FIELD_NAME, FIELD_TYPE, FIELD_DATE, FIELD_RESULT],
    };
    if (offset) params.Offset = offset;

    var result  = sheet.Record.GetRecords(params);
    var records = result.records || [];
    offset      = result.nextOffset || null;

    for (var i = 0; i < records.length; i++) {
      var rec  = records[i];
      var name = toStr(rec[FIELD_NAME]);
      var type = toStr(rec[FIELD_TYPE]);
      if (!name && !type) continue;
      allRows.push({
        name:     name,
        type:     type,
        appt_date: toDateStr(rec[FIELD_DATE]),
        result:   toStr(rec[FIELD_RESULT]),
      });
    }
  } while (offset);

  if (allRows.length === 0) {
    console.log('没有可上传的数据行。');
    return;
  }

  console.log('读取到 ' + allRows.length + ' 条记录，正在推送...');

  return fetch(SERVER_URL, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ rows: allRows, file_name: '政企标准化信息收集V3' }),
  }).then(function(resp) {
    if (!resp.ok) {
      console.log('❌ 推送失败，HTTP ' + resp.status);
      return null;
    }
    return resp.json();
  }).then(function(data) {
    if (!data) return;
    if (data.ok) {
      console.log('✅ 推送成功！' + data.rows + ' 位客户经理，结果文件：' + data.generated);
    } else {
      console.log('❌ 服务器错误：' + data.error);
    }
  }).catch(function(e) {
    console.log('❌ 网络请求失败：' + e.message);
  });
}

function toStr(v) {
  if (v === null || v === undefined) return '';
  return String(v).trim();
}

// 多维表格日期字段返回 "YYYY-MM-DD" 或 "YYYY/MM/DD" 字符串，统一转为 "YYYY-MM-DD"
function toDateStr(v) {
  if (!v) return '';
  return String(v).slice(0, 10).replace(/\//g, '-');
}

main();
