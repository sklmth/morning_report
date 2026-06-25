"""
OpenClaw bridge for morning_report.

This module exposes deterministic CLI entry points so an OpenClaw session can:
  - fetch the latest report or a report by date
  - inspect attached files and decide whether they match a morning report batch
  - process files, reuse the existing report pipeline, and persist results

The bridge keeps the model out of the low-level workflow details.
"""

import argparse
import contextlib
import io
import json
import os
import sys


SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import report_core  # noqa: E402
import server as _srv  # noqa: E402
from storage import ReportStore  # noqa: E402


def _build_context():
    _srv._load_dotenv  # trigger module side effects
    cfg = _srv.load_config()
    store = ReportStore(cfg["db_path"])
    return cfg, store


def _normalize_report(report):
    if not report:
        return None
    images = []
    for item in report.get("images") or []:
        if isinstance(item, dict):
            images.append({
                "title": item.get("title", ""),
                "path": item.get("path", ""),
            })
    return {
        "id": report.get("id"),
        "created_at": report.get("created_at", ""),
        "source": report.get("source", ""),
        "subject": report.get("subject", ""),
        "sender": report.get("sender", ""),
        "status": report.get("status", ""),
        "message": report.get("message", ""),
        "input_files": report.get("input_files") or [],
        "output_xlsx": report.get("output_xlsx", ""),
        "image_dir": report.get("image_dir", ""),
        "images": images,
        "report_text": report.get("report_text", ""),
        "written_sheets": report.get("written_sheets") or [],
    }


def _print_json(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _report_matches_date(report, date_prefix):
    created_at = (report.get("created_at") or "")[:10]
    return created_at == date_prefix


def cmd_latest(store):
    report = _normalize_report(store.latest_report())
    if not report:
        return {"ok": False, "error": "no_reports"}
    return {"ok": True, "report": report}


def cmd_date(store, date_prefix):
    reports = [_normalize_report(r) for r in store.list_reports(limit=200)]
    matched = [r for r in reports if r and _report_matches_date(r, date_prefix)]
    if not matched:
        return {"ok": False, "error": "not_found", "date": date_prefix}
    return {"ok": True, "report": matched[0], "matched": matched[:10]}


def cmd_inspect(file_paths):
    abs_paths = [os.path.abspath(p) for p in file_paths]
    inputs = report_core.classify_inputs(abs_paths)
    return {
        "ok": True,
        "input_files": abs_paths,
        "classified": {k: os.path.abspath(v) for k, v in inputs.items()},
        "has_required_kind": bool({"wanmei", "yingfu"} & set(inputs.keys())),
        "should_process": bool({"wanmei", "yingfu"} & set(inputs.keys())),
        "reason": (
            "matched_supported_report_types"
            if {"wanmei", "yingfu"} & set(inputs.keys())
            else "no_supported_report_type_detected"
        ),
    }


def cmd_process(cfg, store, file_paths, source="wechat", send_wechat=False):
    abs_paths = [os.path.abspath(p) for p in file_paths]
    log_buffer = io.StringIO()
    with contextlib.redirect_stdout(log_buffer):
        result = _srv.process_files(abs_paths, cfg, send_wechat=send_wechat)
    if result.get("status") != "skipped":
        store.add_report(
            source=source,
            subject="OpenClaw 处理",
            sender="",
            **result,
        )
    return {
        "ok": True,
        "source": source,
        "result": result,
        "logs": log_buffer.getvalue().splitlines(),
    }


def cmd_ingest(cfg, store, file_paths, source="wechat"):
    inspection = cmd_inspect(file_paths)
    if not inspection["should_process"]:
        return {
            "ok": True,
            "processed": False,
            "inspection": inspection,
        }
    processed = cmd_process(cfg, store, file_paths, source=source, send_wechat=False)
    return {
        "ok": True,
        "processed": True,
        "inspection": inspection,
        "processed_report": processed["result"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="morning_report OpenClaw bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("latest", help="Return the latest stored report")

    p_date = sub.add_parser("date", help="Return the latest stored report on a given date")
    p_date.add_argument("date", help="YYYY-MM-DD")

    p_inspect = sub.add_parser("inspect", help="Inspect attached files without processing")
    p_inspect.add_argument("files", nargs="+", help="Input file paths")

    p_process = sub.add_parser("process", help="Process input files and store the result")
    p_process.add_argument("files", nargs="+", help="Input file paths")
    p_process.add_argument("--source", default="wechat", help="Report source label")
    p_process.add_argument("--send-wechat", action="store_true", help="Also send via the configured Weixin command")

    p_ingest = sub.add_parser("ingest", help="Inspect first, then process only supported report files")
    p_ingest.add_argument("files", nargs="+", help="Input file paths")
    p_ingest.add_argument("--source", default="wechat", help="Report source label")

    args = parser.parse_args(argv)
    cfg, store = _build_context()

    if args.command == "latest":
        payload = cmd_latest(store)
    elif args.command == "date":
        payload = cmd_date(store, args.date)
    elif args.command == "inspect":
        payload = cmd_inspect(args.files)
    elif args.command == "process":
        payload = cmd_process(cfg, store, args.files, source=args.source, send_wechat=args.send_wechat)
    elif args.command == "ingest":
        payload = cmd_ingest(cfg, store, args.files, source=args.source)
    else:
        parser.error("unknown command")
        return 2

    _print_json(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
