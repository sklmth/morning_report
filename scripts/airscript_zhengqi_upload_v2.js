// 政企家庭专项走访统计第二版 — 多维表格 → 走访统计服务器推送

var SERVER_URL = 'https://shanguantang.site/zhengqi/upload-rows';
var FIELD_NAME = '客户经理姓名';
var FIELD_TYPE = '拜访对象类型';
var FIELD_DATE = '预约上门日期';
var FIELD_RESULT = '拜访结果（上门后回填）';
var FIELD_STATUS = '商机转化情况';
var FIELD_POINTS = '商机积分';
var FIELD_GAOTAO = '折合高套数量';

function main() {
    console.log('===== 开始读取政企走访第二版数据 =====');

    var activeView = Application.Selection.GetActiveView();
    if (!activeView) { console.log('无法获取当前活动视图'); return; }

    var sheetId = activeView.sheetId;
    if (sheetId === null || sheetId === undefined) {
        console.log('无法获取 SheetId');
        return;
    }

    var allRows = [], offset = null;
    do {
        var params = {
            SheetId: sheetId,
            PageSize: 100,
            Fields: [
                FIELD_NAME, FIELD_TYPE, FIELD_DATE, FIELD_RESULT,
                FIELD_STATUS, FIELD_POINTS, FIELD_GAOTAO
            ]
        };
        if (offset) params.Offset = offset;

        var result;
        try {
            result = Application.Record.GetRecords(params);
        } catch (e) {
            console.log('读取多维表失败：' + e.message);
            return;
        }
        if (!result) { console.log('GetRecords 没有返回数据'); return; }

        var records = result.records || [];
        console.log('本页读取：' + records.length + ' 条');
        offset = result.offset || null;

        for (var i = 0; i < records.length; i++) {
            var fields = records[i].fields || {};
            var row = {
                name: toStr(fields[FIELD_NAME]),
                type: toStr(fields[FIELD_TYPE]),
                appt_date: toDateStr(fields[FIELD_DATE]),
                result: toStr(fields[FIELD_RESULT]),
                opportunity_status: toStr(fields[FIELD_STATUS]),
                opportunity_points: toStr(fields[FIELD_POINTS]),
                opportunity_gaotao: toStr(fields[FIELD_GAOTAO])
            };
            if (!row.name && !row.type && !row.appt_date && !row.result
                    && !row.opportunity_status && !row.opportunity_points && !row.opportunity_gaotao) {
                continue;
            }
            allRows.push(row);
        }
    } while (offset);

    console.log('最终有效记录：' + allRows.length + ' 条');
    if (allRows.length === 0) { console.log('没有可上传的数据'); return; }

    var payload = {
        report_version: 'v2',
        rows: allRows,
        file_name: '政企标准化信息收集V3_第二版'
    };

    try {
        var response = HTTP.fetch(SERVER_URL, {
            method: 'POST',
            timeout: 30000,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (response.status < 200 || response.status >= 300) {
            console.log('服务器请求失败，HTTP ' + response.status + '：' + response.statusText);
            return;
        }
        var data = response.json();
        if (data && data.ok) {
            console.log('推送成功');
            if (data.rows !== undefined) console.log('服务器处理数量：' + data.rows);
            if (data.generated) console.log('生成结果：' + data.generated);
        } else {
            console.log('服务器返回业务错误' + (data && data.error ? '：' + data.error : ''));
        }
    } catch (e) {
        console.log('网络请求失败：' + e.message);
    }

    console.log('===== 脚本执行结束 =====');
}

function toStr(value) {
    return (value === null || value === undefined) ? '' : String(value).trim();
}

function toDateStr(value) {
    return value ? String(value).slice(0, 10).replace(/\//g, '-') : '';
}

main();
