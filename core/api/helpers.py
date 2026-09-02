# -*- coding: utf-8 -*-
"""API helpers — _err / _raw_file_response / get_req_query / get_req_json 统一出口"""
from astrbot.api.web import json_response, error_response as _orig_error_response


def _err(msg, code=500):
    try:
        return _orig_error_response(msg, code)
    except TypeError:
        try:
            return _orig_error_response(msg)
        except Exception:
            return json_response({"error": msg, "code": code})


def _raw_file_response(data_bytes, filename):
    try:
        from aiohttp.web import Response as AioResponse  # type: ignore
        return AioResponse(body=data_bytes, headers={"Content-Disposition": f'attachment; filename="{filename}"', "Content-Type": "application/octet-stream"})
    except Exception:
        pass
    try:
        from quart import Response as QuartResponse  # type: ignore
        return QuartResponse(data_bytes, headers={"Content-Disposition": f'attachment; filename="{filename}"'}, mimetype="application/octet-stream")
    except Exception:
        pass
    try:
        from starlette.responses import Response as StarResponse  # type: ignore
        return StarResponse(content=data_bytes, headers={"Content-Disposition": f'attachment; filename="{filename}"'}, media_type="application/octet-stream")
    except Exception:
        pass
    return None


def get_req_query(request, key, default=""):
    """跨框架安全提取 URL 查询参数 (支持 aiohttp / quart / starlette / dict / None)"""
    if request is None:
        return default
    try:
        if hasattr(request, "query") and request.query is not None:
            v = request.query.get(key, default)
            return str(v) if v is not None else default
    except Exception:
        pass
    try:
        if hasattr(request, "args") and request.args is not None:
            v = request.args.get(key, default)
            return str(v) if v is not None else default
    except Exception:
        pass
    try:
        if hasattr(request, "query_params") and request.query_params is not None:
            v = request.query_params.get(key, default)
            return str(v) if v is not None else default
    except Exception:
        pass
    try:
        if isinstance(request, dict):
            v = request.get(key, default)
            return str(v) if v is not None else default
    except Exception:
        pass
    return default


async def get_req_json(request, default=None):
    """跨框架安全提取 JSON Body (支持 aiohttp / quart / starlette / dict / None)"""
    if default is None:
        default = {}
    if request is None:
        return default
    if isinstance(request, dict):
        return request
    try:
        if hasattr(request, "json"):
            if callable(request.json):
                res = await request.json()
                return res if isinstance(res, dict) else default
            elif isinstance(request.json, dict):
                return request.json
    except Exception:
        pass
    try:
        if hasattr(request, "post") and callable(request.post):
            res = await request.post()
            return dict(res) if res else default
    except Exception:
        pass
    return default
