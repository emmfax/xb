# -*- coding: utf-8 -*-
"""小白机器人 - 在线版本检测引擎 (标准 GitHub Release / 国内加速镜像适配)"""
import os
import re
import json
import time
import urllib.request
import urllib.error
from astrbot.api.web import json_response
from .helpers import _err

try:
    from ... import store as ST
except ImportError:
    import store as ST

GITHUB_REPO = "emmfax/xb"
REPO_URL = f"https://github.com/{GITHUB_REPO}"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

_LAST_CHECK_RES = None
_LAST_CHECK_TIME = 0.0
_CHECK_CACHE_TTL = 10.0  # 10秒短缓存防频繁请求 GitHub 触发 RateLimit


def _get_local_version(plugin_base=""):
    try:
        base = plugin_base or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        meta_path = os.path.join(base, "metadata.yaml")
        if os.path.isfile(meta_path):
            for line in open(meta_path, "r", encoding="utf-8").readlines():
                if line.strip().startswith("version:"):
                    return line.split(":", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "0.68.27"


def _parse_version_tuple(v_str):
    m = re.findall(r"\d+", str(v_str or ""))
    return tuple(map(int, m)) if m else (0, 0, 0)


def check_latest_version(plugin_base=""):
    """
    双通道检测最新版本：
    1. GitHub main 分支 metadata.yaml (实时 Git 提交版本，支持 CDN 镜像加速)
    2. GitHub Releases 接口 (Release 打包版本)
    择优选取版本号最高者，并与本地版本进行元组比较。
    """
    local_ver = _get_local_version(plugin_base)
    headers = {
        "User-Agent": "XbBot-AutoUpdater/1.0",
        "Accept": "application/vnd.github.v3+json"
    }

    # 1. 优先尝试检测 main 分支 metadata.yaml（实时源码最新版，含多镜像容灾）
    main_ver = ""
    raw_meta_urls = [
        f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/metadata.yaml",
        f"https://mirror.ghproxy.com/https://raw.githubusercontent.com/{GITHUB_REPO}/main/metadata.yaml",
        f"https://raw.gitmirror.com/{GITHUB_REPO}/main/metadata.yaml"
    ]
    for url in raw_meta_urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    txt = resp.read().decode("utf-8")
                    for line in txt.splitlines():
                        if line.strip().startswith("version:"):
                            main_ver = line.split(":", 1)[1].strip().strip('"').strip("'")
                            break
                    if main_ver:
                        break
        except Exception:
            continue

    # 2. 检测 GitHub Releases 接口
    rel_ver = ""
    rel_name = ""
    rel_date = ""
    rel_body = ""
    try:
        req = urllib.request.Request(API_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                rel_ver = (data.get("tag_name") or data.get("name") or "").replace("v", "").strip()
                rel_name = data.get("name") or rel_ver
                rel_date = (data.get("published_at") or "")[:10]
                rel_body = data.get("body") or ""
    except Exception:
        pass

    # 3. 双通道择优：取版本号更高者
    if _parse_version_tuple(main_ver) >= _parse_version_tuple(rel_ver) and main_ver:
        best_ver = main_ver
        best_name = f"小白 v{main_ver} (Git main 源码更新)"
        best_date = time.strftime("%Y-%m-%d")
        best_body = "已检测到 GitHub 仓库 main 分支最新提交版本，可前往 AstrBot 插件管理面板一键更新或拉取代码。"
    elif rel_ver:
        best_ver = rel_ver
        best_name = rel_name or f"小白 v{rel_ver} 正式版"
        best_date = rel_date or time.strftime("%Y-%m-%d")
        best_body = rel_body or "请查看 GitHub Releases 更新说明。"
    else:
        best_ver = local_ver
        best_name = f"小白 {local_ver}"
        best_date = time.strftime("%Y-%m-%d")
        best_body = "当前已是最新版本。"

    has_update = _parse_version_tuple(best_ver) > _parse_version_tuple(local_ver)
    return {
        "ok": True,
        "current_version": local_ver,
        "latest_version": best_ver,
        "has_update": has_update,
        "release_name": best_name,
        "release_date": best_date,
        "changelog": best_body
    }


async def handle_version_check(request=None, plugin_base=""):
    """从云端检测是否有最新 Release 或 main 分支版本（完全异步化，绝不阻塞主事件循环）"""
    global _LAST_CHECK_RES, _LAST_CHECK_TIME
    now = time.time()
    if _LAST_CHECK_RES is not None and (now - _LAST_CHECK_TIME) < _CHECK_CACHE_TTL:
        return json_response(_LAST_CHECK_RES)

    import asyncio
    try:
        res = await asyncio.to_thread(check_latest_version, plugin_base)
    except Exception as e:
        res = {
            "current_version": _get_local_version(plugin_base),
            "latest_version": _get_local_version(plugin_base),
            "has_update": False,
            "error": str(e)
        }
    _LAST_CHECK_RES = res
    _LAST_CHECK_TIME = now
    return json_response(res)
