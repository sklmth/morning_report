/**
 * 【诊断用 v3】探测 Application 结构和全局快捷变量
 */

function main() {
  // 1. Application 本身有哪些属性
  console.log("Application 类型: " + typeof Application);
  var appProps = [];
  for (var p in Application) { appProps.push(p); }
  console.log("Application 属性: " + (appProps.length ? appProps.join(", ") : "（空/不可枚举）"));

  // 2. 尝试 Object.keys
  try { console.log("Object.keys(Application): " + Object.keys(Application).join(", ")); } catch(e) {}

  // 3. 直接访问 ActiveSheet 的子属性（不管它是什么类型）
  var s = Application.ActiveSheet;
  console.log("ActiveSheet.Name: " + s.Name);
  console.log("ActiveSheet.Index: " + s.Index);
  console.log("ActiveSheet.UsedRange: " + s.UsedRange);

  // 4. 尝试 ActiveWorkbook
  try {
    var wb = Application.ActiveWorkbook;
    console.log("ActiveWorkbook 类型: " + typeof wb);
    var ws = wb.ActiveSheet;
    console.log("wb.ActiveSheet 类型: " + typeof ws);
    console.log("wb.ActiveSheet.Name: " + ws.Name);
    var ur = ws.UsedRange;
    console.log("wb.ActiveSheet.UsedRange: " + typeof ur + " | " + ur);
    if (ur) {
      console.log("UsedRange.Value: " + JSON.stringify(ur.Value).slice(0, 300));
    }
  } catch(e) { console.log("ActiveWorkbook 路径报错: " + e.message); }

  // 5. 尝试全局快捷变量（不带 Application 前缀）
  try { console.log("全局 ActiveSheet 类型: " + typeof ActiveSheet); } catch(e) { console.log("全局 ActiveSheet 不存在: " + e.message); }
  try {
    var gs = ActiveSheet;
    console.log("全局 ActiveSheet.Name: " + gs.Name);
    var ur2 = gs.UsedRange;
    console.log("全局 ActiveSheet.UsedRange: " + ur2);
    if (ur2) { console.log("UsedRange.Value: " + JSON.stringify(ur2.Value).slice(0, 300)); }
  } catch(e) { console.log("全局 ActiveSheet 报错: " + e.message); }

  // 6. 尝试 Sheets / Worksheets（金山文档是集合对象，不是函数）
  try {
    var sheets = Application.Sheets;
    console.log("Application.Sheets 类型: " + typeof sheets);
    console.log("Application.Sheets.Count: " + sheets.Count);
    var sh1 = sheets.Item(1);  // 使用 .Item(index) 方法
    console.log("Application.Sheets.Item(1).Name: " + sh1.Name);
  } catch(e) { console.log("Application.Sheets 报错: " + e.message); }

  try {
    var worksheets = Application.Worksheets;
    console.log("Application.Worksheets 类型: " + typeof worksheets);
    console.log("Application.Worksheets.Count: " + worksheets.Count);
    var ws1 = worksheets.Item(1);  // 使用 .Item(index) 方法
    console.log("Application.Worksheets.Item(1).Name: " + ws1.Name);
  } catch(e) { console.log("Application.Worksheets 报错: " + e.message); }
}

main();
