"""
测试管理者详细通报示例
"""
import sys
from pathlib import Path
from datetime import date

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from wecom_notice.db import init_db, upsert_records
from wecom_notice.reporter import build_manager_detailed_notice

# 初始化数据库
init_db()

# 创建测试数据
test_date = date.today().isoformat()

test_records = [
    # 麦海芬 - 2户
    {
        "source_record_id": "test_001",
        "payload_hash": "hash_001",
        "manager_name": "麦海芬",
        "object_type": "党政军",
        "company_name": "端州区政府",
        "contact_name_title": "张主任",
        "contact_mobile": "13800138001",
        "appointment_date": test_date,
        "appointment_slot": "上午",
        "need_dispatch": "是",
        "delivery_staff_name": "程庆德",
        "opportunity_type": "政务云",
        "opportunity_type_extra": "",
        "opportunity_content": "政务云平台扩容升级，预计投资50万元，包含服务器采购、网络改造等",
        "cockpit_sent": "否",
        "doubao_beik_sent": "否",
        "visit_result": "",
        "actual_visit_date": "",
        "visit_situation": "",
        "images_json": "[]",
        "conversion_status": "",
        "opportunity_points": 0,
        "gaotao_count": 0,
        "planned_accept_time": "",
        "reschedule_time": "",
        "reschedule_reason": "",
        "raw_json": "{}"
    },
    {
        "source_record_id": "test_002",
        "payload_hash": "hash_002",
        "manager_name": "麦海芬",
        "object_type": "党政军",
        "company_name": "端州区教育局",
        "contact_name_title": "李局长",
        "contact_mobile": "13800138002",
        "appointment_date": test_date,
        "appointment_slot": "下午",
        "need_dispatch": "是",
        "delivery_staff_name": "零樑",
        "opportunity_type": "智慧校园",
        "opportunity_type_extra": "",
        "opportunity_content": "智慧校园建设项目",
        "cockpit_sent": "否",
        "doubao_beik_sent": "否",
        "visit_result": "",
        "actual_visit_date": "",
        "visit_situation": "",
        "images_json": "[]",
        "conversion_status": "",
        "opportunity_points": 0,
        "gaotao_count": 0,
        "planned_accept_time": "",
        "reschedule_time": "",
        "reschedule_reason": "",
        "raw_json": "{}"
    },
    # 李东 - 3户
    {
        "source_record_id": "test_003",
        "payload_hash": "hash_003",
        "manager_name": "李东",
        "object_type": "大中企业",
        "company_name": "肇庆移动公司",
        "contact_name_title": "王经理",
        "contact_mobile": "13800138003",
        "appointment_date": test_date,
        "appointment_slot": "上午",
        "need_dispatch": "是",
        "delivery_staff_name": "刘奇峻",
        "opportunity_type": "5G专网",
        "opportunity_type_extra": "",
        "opportunity_content": "5G专网建设，覆盖厂区和办公区域",
        "cockpit_sent": "否",
        "doubao_beik_sent": "否",
        "visit_result": "",
        "actual_visit_date": "",
        "visit_situation": "",
        "images_json": "[]",
        "conversion_status": "",
        "opportunity_points": 0,
        "gaotao_count": 0,
        "planned_accept_time": "",
        "reschedule_time": "",
        "reschedule_reason": "",
        "raw_json": "{}"
    },
    {
        "source_record_id": "test_004",
        "payload_hash": "hash_004",
        "manager_name": "李东",
        "object_type": "党政军",
        "company_name": "肇庆邮政局",
        "contact_name_title": "",
        "contact_mobile": "",
        "appointment_date": test_date,
        "appointment_slot": "下午",
        "need_dispatch": "否",
        "delivery_staff_name": "",
        "opportunity_type": "信息化改造",
        "opportunity_type_extra": "",
        "opportunity_content": "邮政信息化改造，包括营业厅智能化升级、后台系统对接、监控系统部署等内容",
        "cockpit_sent": "否",
        "doubao_beik_sent": "否",
        "visit_result": "",
        "actual_visit_date": "",
        "visit_situation": "",
        "images_json": "[]",
        "conversion_status": "",
        "opportunity_points": 0,
        "gaotao_count": 0,
        "planned_accept_time": "",
        "reschedule_time": "",
        "reschedule_reason": "",
        "raw_json": "{}"
    },
    {
        "source_record_id": "test_005",
        "payload_hash": "hash_005",
        "manager_name": "李东",
        "object_type": "大中企业",
        "company_name": "某某科技公司",
        "contact_name_title": "陈总",
        "contact_mobile": "13800138005",
        "appointment_date": test_date,
        "appointment_slot": "下午",
        "need_dispatch": "是",
        "delivery_staff_name": "何而恒",
        "opportunity_type": "云桌面",
        "opportunity_type_extra": "",
        "opportunity_content": "",
        "cockpit_sent": "否",
        "doubao_beik_sent": "否",
        "visit_result": "",
        "actual_visit_date": "",
        "visit_situation": "",
        "images_json": "[]",
        "conversion_status": "",
        "opportunity_points": 0,
        "gaotao_count": 0,
        "planned_accept_time": "",
        "reschedule_time": "",
        "reschedule_reason": "",
        "raw_json": "{}"
    },
    # 张小敏 - 2户
    {
        "source_record_id": "test_006",
        "payload_hash": "hash_006",
        "manager_name": "张小敏",
        "object_type": "党政军",
        "company_name": "端州区人民医院",
        "contact_name_title": "赵院长",
        "contact_mobile": "13800138006",
        "appointment_date": test_date,
        "appointment_slot": "上午",
        "need_dispatch": "是",
        "delivery_staff_name": "龙家宝",
        "opportunity_type": "医疗信息化",
        "opportunity_type_extra": "",
        "opportunity_content": "",
        "cockpit_sent": "否",
        "doubao_beik_sent": "否",
        "visit_result": "",
        "actual_visit_date": "",
        "visit_situation": "",
        "images_json": "[]",
        "conversion_status": "",
        "opportunity_points": 0,
        "gaotao_count": 0,
        "planned_accept_time": "",
        "reschedule_time": "",
        "reschedule_reason": "",
        "raw_json": "{}"
    },
    {
        "source_record_id": "test_007",
        "payload_hash": "hash_007",
        "manager_name": "张小敏",
        "object_type": "党政军",
        "company_name": "肇庆中学",
        "contact_name_title": "周校长",
        "contact_mobile": "13800138007",
        "appointment_date": test_date,
        "appointment_slot": "下午",
        "need_dispatch": "是",
        "delivery_staff_name": "魏垚晖",
        "opportunity_type": "智慧校园",
        "opportunity_type_extra": "",
        "opportunity_content": "校园网络升级改造项目",
        "cockpit_sent": "否",
        "doubao_beik_sent": "否",
        "visit_result": "",
        "actual_visit_date": "",
        "visit_situation": "",
        "images_json": "[]",
        "conversion_status": "",
        "opportunity_points": 0,
        "gaotao_count": 0,
        "planned_accept_time": "",
        "reschedule_time": "",
        "reschedule_reason": "",
        "raw_json": "{}"
    },
    # 邓天群 - 0户（测试未完成填报）
]

# 插入测试数据
print("插入测试数据...")
result = upsert_records(test_records)
print(f"插入结果: {result}")

# 生成详细通报
print("\n生成管理者详细通报...\n")
report = build_manager_detailed_notice(test_date, required=2)

# 输出到文件避免编码问题
output_file = Path(__file__).parent / "test_detailed_notice_output.txt"
with open(output_file, "w", encoding="utf-8") as f:
    f.write("=" * 80 + "\n")
    f.write(report["message"])
    f.write("\n" + "=" * 80 + "\n")
    f.write(f"\n通报摘要:\n")
    f.write(f"  - 应发送: {report['should_send']}\n")
    f.write(f"  - 未完成人数: {report['today_summary']['not_filled']}\n")
    f.write(f"  - 已完成人数: {report['today_summary']['filled']}\n")

print(f"详细通报已输出到: {output_file}")
print("请查看文件内容")
