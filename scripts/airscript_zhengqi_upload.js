/**
 * 政企标准化信息收集V3
 * 多维表格 → 走访统计服务器推送
 *
 * 功能：
 * 1. 自动获取当前多维表 SheetId
 * 2. 分页读取全部记录
 * 3. 提取客户经理、拜访类型、预约日期、拜访结果
 * 4. POST 到服务器
 */

var SERVER_URL =
    'https://shanguantang.site/zhengqi/upload-rows';


// ==============================
// 多维表字段名
// ==============================

var FIELD_NAME =
    '客户经理姓名';

var FIELD_TYPE =
    '拜访对象类型';

var FIELD_DATE =
    '预约上门日期';

var FIELD_RESULT =
    '拜访结果（上门后回填）';


// ==============================
// 主程序
// ==============================

function main() {

    console.log(
        '===== 开始读取政企走访数据 ====='
    );


    // ==============================
    // 1. 获取当前多维表
    // ==============================

    var activeView =
        Application.Selection.GetActiveView();


    if (!activeView) {

        console.log(
            '❌ 无法获取当前活动视图'
        );

        return;
    }


    var sheetId =
        activeView.sheetId;


    if (
        sheetId === null ||
        sheetId === undefined
    ) {

        console.log(
            '❌ 无法获取 SheetId'
        );

        return;
    }


    console.log(
        '✅ 当前 SheetId：' +
        sheetId
    );


    // ==============================
    // 2. 分页读取
    // ==============================

    var allRows = [];

    var offset = null;


    do {

        var params = {

            SheetId: sheetId,

            PageSize: 100,

            Fields: [

                FIELD_NAME,

                FIELD_TYPE,

                FIELD_DATE,

                FIELD_RESULT
            ]
        };


        if (offset) {

            params.Offset =
                offset;
        }


        var result;

        try {

            result =
                Application.Record
                    .GetRecords(
                        params
                    );

        } catch (e) {

            console.log(
                '❌ 读取多维表失败：' +
                e.message
            );

            return;
        }


        if (!result) {

            console.log(
                '❌ GetRecords 没有返回数据'
            );

            return;
        }


        var records =
            result.records || [];


        console.log(
            '本页读取：' +
            records.length +
            ' 条'
        );


        // 下一页 offset
        offset =
            result.offset || null;


        // ==============================
        // 3. 整理记录
        // ==============================

        for (
            var i = 0;
            i < records.length;
            i++
        ) {

            var fields =
                records[i].fields || {};


            var name =
                toStr(
                    fields[
                        FIELD_NAME
                    ]
                );


            var type =
                toStr(
                    fields[
                        FIELD_TYPE
                    ]
                );


            var apptDate =
                toDateStr(
                    fields[
                        FIELD_DATE
                    ]
                );


            var visitResult =
                toStr(
                    fields[
                        FIELD_RESULT
                    ]
                );


            /*
             * 完全空白记录跳过
             *
             * 这里不能只判断 name/type，
             * 避免以后某些有效记录被误删。
             */
            if (
                !name &&
                !type &&
                !apptDate &&
                !visitResult
            ) {
                continue;
            }


            allRows.push({

                name:
                    name,

                type:
                    type,

                appt_date:
                    apptDate,

                result:
                    visitResult
            });
        }


    } while (offset);


    // ==============================
    // 4. 检查结果
    // ==============================

    console.log(
        '✅ 最终有效记录：' +
        allRows.length +
        ' 条'
    );


    if (
        allRows.length === 0
    ) {

        console.log(
            '⚠️ 没有可上传的数据'
        );

        return;
    }


    // ==============================
    // 5. 构造上传数据
    // ==============================

    var payload = {

        rows:
            allRows,

        file_name:
            '政企标准化信息收集V3'
    };


    console.log(
        '正在向服务器推送数据...'
    );


    // ==============================
    // 6. HTTP POST
    // ==============================

    try {

        var response =
            HTTP.fetch(
                SERVER_URL,
                {

                    method:
                        'POST',

                    timeout:
                        30000,

                    headers: {

                        'Content-Type':
                            'application/json'
                    },

                    body:
                        JSON.stringify(
                            payload
                        )
                }
            );


        // ==============================
        // 7. 检查 HTTP 状态
        // ==============================

        if (
            response.status < 200 ||
            response.status >= 300
        ) {

            console.log(
                '❌ 服务器请求失败'
            );

            console.log(
                'HTTP 状态码：' +
                response.status
            );

            console.log(
                '状态信息：' +
                response.statusText
            );

            return;
        }


        // ==============================
        // 8. 读取服务器 JSON
        // ==============================

        var data;

        try {

            data =
                response.json();

        } catch (e) {

            console.log(
                '❌ 服务器返回的不是有效 JSON'
            );

            console.log(
                '解析错误：' +
                e.message
            );

            return;
        }


        // ==============================
        // 9. 判断服务器业务结果
        // ==============================

        if (
            data &&
            data.ok
        ) {

            console.log(
                '✅ 推送成功'
            );


            if (
                data.rows !==
                undefined
            ) {

                console.log(
                    '服务器处理数量：' +
                    data.rows
                );
            }


            if (
                data.generated
            ) {

                console.log(
                    '生成结果：' +
                    data.generated
                );
            }


        } else {

            console.log(
                '❌ 服务器返回业务错误'
            );


            if (
                data &&
                data.error
            ) {

                console.log(
                    '错误信息：' +
                    data.error
                );
            }
        }


    } catch (e) {

        console.log(
            '❌ 网络请求失败：' +
            e.message
        );
    }


    console.log(
        '===== 脚本执行结束 ====='
    );
}


// ==============================
// 普通字段转字符串
// ==============================

function toStr(v) {

    if (
        v === null ||
        v === undefined
    ) {

        return '';
    }


    return String(v).trim();
}


// ==============================
// 日期统一 YYYY-MM-DD
// ==============================

function toDateStr(v) {

    if (!v) {

        return '';
    }


    return String(v)
        .slice(0, 10)
        .replace(/\//g, '-');
}


// ==============================
// 执行
// ==============================

main();
