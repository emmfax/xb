# -*- coding: utf-8 -*-
"""API helpers — _err / _raw_file_response 统一出口"""
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
