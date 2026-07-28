// 政企标准化信息收集V3 — 多维表格 → 走访统计服务器推送

var SERVER_URL = 'https://shanguantang.site/zhengqi/upload-rows';
var FIELD_NAME   = '客户经理姓名';
var FIELD_TYPE   = '拜访对象类型';
var FIELD_DATE   = '预约上门日期';
var FIELD_RESULT = '拜访结果（上门后回填）';

function main() {
    console.log('===== 开始读取政企走访数据 =====');

    var activeView = Application.Selection.GetActiveView();
    if (!activeView) { console.log('❌ 无法获取当前活动视图'); return; }

    var sheetId = activeView.sheetId;
    if (sheetId === null || sheetId === undefined) { console.log('❌ 无法获取 SheetId'); return; }
    console.log('✅ 当前 SheetId：' + sheetId);

    var allRows = [], offset = null;

    do {
        var params = {
            SheetId: sheetId,
            PageSize: 100,
            Fields: [FIELD_NAME, FIELD_TYPE, FIELD_DATE, FIELD_RESULT]
        };
        if (offset) params.Offset = offset;

        var result;
        try {
            result = Application.Record.GetRecords(params);
        } catch (e) {
            console.log('❌ 读取多维表失败：' + e.message);
            return;
        }
        if (!result) { console.log('❌ GetRecords 没有返回数据'); return; }

        var records = result.records || [];
        console.log('本页读取：' + records.length + ' 条');
        offset = result.offset || null;

        for (var i = 0; i < records.length; i++) {
            var f = records[i].fields || {};
            var name = toStr(f[FIELD_NAME]);
            var type = toStr(f[FIELD_TYPE]);
            var apptDate = toDateStr(f[FIELD_DATE]);
            var visitResult = toStr(f[FIELD_RESULT]);
            // 四个字段全空则跳过
            if (!name && !type && !apptDate && !visitResult) continue;
            allRows.push({ name: name, type: type, appt_date: apptDate, result: visitResult });
        }
    } while (offset);

    console.log('✅ 最终有效记录：' + allRows.length + ' 条');
    if (allRows.length === 0) { console.log('⚠️ 没有可上传的数据'); return; }

    var payload = { rows: allRows, file_name: '政企标准化信息收集V3' };
    console.log('正在向服务器推送数据...');

    try {
        var response = HTTP.fetch(SERVER_URL, {
            method: 'POST',
            timeout: 30000,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.status < 200 || response.status >= 300) {
            console.log('❌ 服务器请求失败，HTTP ' + response.status + '：' + response.statusText);
            return;
        }

        var data;
        try {
            data = response.json();
        } catch (e) {
            console.log('❌ 服务器返回的不是有效 JSON：' + e.message);
            return;
        }

        if (data && data.ok) {
            console.log('✅ 推送成功');
            if (data.rows !== undefined) console.log('服务器处理数量：' + data.rows);
            if (data.generated) console.log('生成结果：' + data.generated);
        } else {
            console.log('❌ 服务器返回业务错误' + (data && data.error ? '：' + data.error : ''));
        }
    } catch (e) {
        console.log('❌ 网络请求失败：' + e.message);
    }

    console.log('===== 脚本执行结束 =====');
}

function toStr(v) {
    return (v === null || v === undefined) ? '' : String(v).trim();
}

function toDateStr(v) {
    return v ? String(v).slice(0, 10).replace(/\//g, '-') : '';
}

main();
