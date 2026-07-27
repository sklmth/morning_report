/**
 * 政企标准化信息收集 → 走访统计服务器推送
 * 金山文档 AirScript（工具 → 自动化脚本）
 *
 * 使用方法：
 *   1. 打开金山文档「政企标准化信息收集」表格
 *      https://www.kdocs.cn/l/chO2jEtJUnDB
 *   2. 顶部菜单 → 工具 → 自动化脚本 → 新建脚本，粘贴此文件全部内容
 *   3. 点击运行；或设置「触发器 → 时间触发」每天早上自动推送
 *
 * 服务端接口：POST https://shanguantang.site/zhengqi/upload-rows
 * 处理结果：  https://shanguantang.site/ 首页下载
 */

const SERVER_URL = "https://shanguantang.site/zhengqi/upload-rows";

async function main() {
  const sheet = Application.Sheets.Item(1);
  const usedRange = sheet.UsedRange;
  const values = usedRange.Value;

  if (!values || values.length < 2) {
    Console.log("表格无数据");
    return;
  }

  // 第一行为表头
  const headers = values[0].map(h => (h || "").toString().trim().replace(/\n/g, ""));

  // 定位关键列（兼容 V2 / V3 列名）
  const COL_NAME   = findCol(headers, ["客户经理姓名", "填写人员姓名"]);
  const COL_TYPE   = findCol(headers, ["拜访对象类型"]);
  const COL_DATE   = findCol(headers, ["预约上门日期"]);
  const COL_RESULT = findCol(headers, ["拜访结果（上门后回填）", "拜访结果"]);

  if (COL_NAME === -1 || COL_TYPE === -1 || COL_DATE === -1) {
    Console.log("❌ 找不到关键列，实际表头：" + headers.join(" | "));
    return;
  }

  // 组装行数据（跳过表头行）
  const rows = [];
  for (let i = 1; i < values.length; i++) {
    const row = values[i];
    const name   = (row[COL_NAME]   || "").toString().trim();
    const type   = (row[COL_TYPE]   || "").toString().trim();
    const date   = formatDate(row[COL_DATE]);
    const result = COL_RESULT !== -1 ? (row[COL_RESULT] || "").toString().trim() : "";

    if (!name && !type) continue; // 跳过空行

    rows.push({ name, type, appt_date: date, result });
  }

  Console.log(`读取到 ${rows.length} 条记录，正在推送...`);

  let resp;
  try {
    resp = await fetch(SERVER_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows, file_name: "金山文档推送" }),
    });
  } catch (e) {
    Console.log("❌ 网络请求失败：" + e.message);
    return;
  }

  if (!resp.ok) {
    Console.log("❌ 推送失败，HTTP " + resp.status);
    return;
  }

  const result = await resp.json();
  if (result.ok) {
    Console.log(`✅ 推送成功！${result.rows} 位客户经理数据已处理，结果文件：${result.generated}`);
  } else {
    Console.log("❌ 服务器返回错误：" + result.error);
  }
}

// 在表头数组中查找候选列名（前4字模糊匹配）
function findCol(headers, candidates) {
  for (const name of candidates) {
    const idx = headers.findIndex(h => h.includes(name.slice(0, 4)));
    if (idx !== -1) return idx;
  }
  return -1;
}

// 把日期统一转为 "YYYY-MM-DD" 字符串
function formatDate(val) {
  if (!val) return "";
  if (typeof val === "string") {
    return val.replace(/\//g, "-").slice(0, 10);
  }
  if (typeof val === "number") {
    // Excel 序列日期（从 1900-01-00 起）
    const d = new Date((val - 25569) * 86400 * 1000);
    const y = d.getUTCFullYear();
    const m = String(d.getUTCMonth() + 1).padStart(2, "0");
    const day = String(d.getUTCDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }
  return String(val).slice(0, 10);
}

main();
