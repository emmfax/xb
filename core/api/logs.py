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
        limit_str = get_req_query(request, "limit", "200")
        level = get_req_query(request, "level", "")
        keyword = get_req_query(request, "keyword", "")
        
        try:
            limit = int(limit_str)
        except Exception:
            limit = 200

        data = logger.get_logs(limit=limit, level=level, keyword=keyword)
        return json_response({
            "status": "ok",
            "result": data
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
            with open(log_path, "rb") as f:
                content = f.read()
        else:
            content = b""

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"xb_logs_{ts}.log"
        resp = _raw_file_response(content, filename)
        if resp is not None:
            return resp
        
        # Fallback to json if raw response not supported
        return json_response({
            "filename": filename,
            "content": content.decode("utf-8", errors="replace")
        })
    except Exception as e:
        return _err(f"导出日志失败: {e}", 500)
