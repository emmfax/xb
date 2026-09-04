# -*- coding: utf-8 -*-
"""
WebUI 插件日志 API
GET  /{PLUGIN_ID}/logs        - 分页/过滤获取最近日志行
POST /{PLUGIN_ID}/logs/clear  - 清空日志
GET  /{PLUGIN_ID}/logs/export - 导出日志文件
"""
import os
import datetime
try:
    from astrbot.api.web import json_response
except ImportError:
    import json
    def json_response(data, status=200):
        return {"data": data, "status": status}
from .helpers import _err, _raw_file_response, get_req_query
from .. import logger


async def handle_logs_get(request=None):
    try:
        from .helpers import get_req_json
        body = await get_req_json(request, {})
        limit_str = get_req_query(request, "limit", "") or (body.get("limit") if isinstance(body, dict) else "") or "200"
        level = get_req_query(request, "level", "") or (body.get("level") if isinstance(body, dict) else "") or ""
        keyword = get_req_query(request, "keyword", "") or (body.get("keyword") if isinstance(body, dict) else "") or ""
        
        try:
            limit = int(limit_str)
        except Exception:
            limit = 200

        data = logger.get_logs(limit=limit, level=level, keyword=keyword)
        return json_response({
            "status": "ok",
            "result": data,
            "logs": data.get("logs", []),
            "count": data.get("count", 0),
            "total_lines": data.get("total_lines", 0),
            "file_size_kb": data.get("file_size_kb", 0),
            "max_file_mb": data.get("max_file_mb", 2.0),
        })
    except Exception as e:
        return _err(f"获取日志失败: {e}", 500)


async def handle_logs_clear(request=None):
    try:
        ok = logger.clear_logs()
        if ok:
            return json_response({"status": "ok", "message": "插件日志已清空"})
        else:
            return _err("清空日志失败", 500)
    except Exception as e:
        return _err(f"清空日志异常: {e}", 500)


async def handle_logs_export(request=None):
    try:
        log_path = logger.get_log_file_path()
        if os.path.isfile(log_path):
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                content_str = f.read()
        else:
            content_str = ""

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"xb_logs_{ts}.log"

        return json_response({
            "status": "ok",
            "filename": filename,
            "content": content_str
        })
    except Exception as e:
        return _err(f"导出日志失败: {e}", 500)
