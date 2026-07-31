// 企业微信通报：金山多维表格完整记录上传
var SERVER_URL = 'https://shanguantang.site/api/airscript/upload';
var FIELDS = [
    '客户经理姓名', '拜访对象类型', '企业名称', '拜访对象姓名+职位', '拜访对象手机号',
    '预约上门日期', '预约时间段', '是否需要集中派单', '预约交付人员姓名', '商机类型',
    '商机类型:补充填空', '商机内容（上门计划）', '智慧座舱图是否已发群', '豆包BEIK图是否已发群',
    '拜访结果（上门后回填）', '实际上门拜访日期', '拜访情况', '商机转化情况', '商机积分', '折合高套数量',
    '计划受理时间', '改约时间', '改约原因/无法上门原因'
];

function main() {
    var activeView = Application.Selection.GetActiveView();
    if (!activeView || activeView.sheetId === null || activeView.sheetId === undefined) {
        console.log('无法获取当前活动视图或 SheetId');
        return;
    }
    var allRows = [], offset = null;
    do {
        var params = { SheetId: activeView.sheetId, PageSize: 100, Fields: FIELDS };
        if (offset) params.Offset = offset;
        var result;
        try { result = Application.Record.GetRecords(params); }
        catch (e) { console.log('读取多维表失败：' + e.message); return; }
        if (!result) { console.log('GetRecords 没有返回数据'); return; }
        offset = result.offset || null;
        var records = result.records || [];
        for (var i = 0; i < records.length; i++) {
            var item = records[i];
            var fields = item.fields || {};
            var hasValue = false;
            for (var j = 0; j < FIELDS.length; j++) {
                if (toStr(fields[FIELDS[j]])) { hasValue = true; break; }
            }
            if (!hasValue) continue;
            allRows.push({ record_id: toStr(item.record_id || item.id), fields: fields });
        }
        console.log('本页读取：' + records.length + ' 条');
    } while (offset);

    if (!allRows.length) { console.log('没有可上传的数据'); return; }
    var payload = {
        source: 'ks_bitable',
        report_version: 'wecom_notice_v1',
        file_name: '政企标准化信息收集V3',
        sheet_id: String(activeView.sheetId),
        rows: allRows
    };
    var headers = { 'Content-Type': 'application/json' };
    try {
        var response = HTTP.fetch(SERVER_URL, {
            method: 'POST', timeout: 30000, headers: headers, body: JSON.stringify(payload)
        });
        if (response.status < 200 || response.status >= 300) {
            console.log('服务器请求失败，HTTP ' + response.status + '：' + response.statusText); return;
        }
        var data = response.json();
        if (data && data.ok) {
            console.log('上传成功：接收 ' + data.received + '，新增 ' + data.inserted + '，更新 ' + data.updated + '，跳过 ' + data.skipped);
        } else {
            console.log('服务器返回业务错误：' + (data && data.detail ? data.detail : '未知错误'));
        }
    } catch (e) { console.log('网络请求失败：' + e.message); }
}
function toStr(value) { return value === null || value === undefined ? '' : String(value).trim(); }
main();
