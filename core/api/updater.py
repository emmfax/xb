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
    return "0.67.4"


def _parse_version_tuple(v_str):
    m = re.findall(r"\d+", str(v_str or ""))
    return tuple(map(int, m)) if m else (0, 0, 0)


async def handle_version_check(request, plugin_base=""):
    """从云端检测是否有最新 Release 版本"""
    global _LAST_CHECK_RES, _LAST_CHECK_TIME
    now = time.time()
    if _LAST_CHECK_RES is not None and (now - _LAST_CHECK_TIME) < _CHECK_CACHE_TTL:
        return json_response(_LAST_CHECK_RES)

    local_ver = _get_local_version(plugin_base)
    headers = {
        "User-Agent": "XbBot-AutoUpdater/1.0",
        "Accept": "application/vnd.github.v3+json"
    }

    remote_tag = ""
    release_name = ""
    release_date = ""
    changelog = ""

    # 1. 优先尝试从 GitHub Release 接口拉取
    try:
        req = urllib.request.Request(API_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                remote_tag = data.get("tag_name") or data.get("name") or ""
                release_name = data.get("name") or remote_tag
                release_date = (data.get("published_at") or "")[:10]
                changelog = data.get("body") or "暂无详细更新日志。"
    except Exception:
        pass

    # 2. 备选方案：若无 Release 或网络受限，通过国内镜像拉取 main 分支 metadata.yaml
    if not remote_tag:
        raw_meta_urls = [
            f"https://mirror.ghproxy.com/https://raw.githubusercontent.com/{GITHUB_REPO}/main/metadata.yaml",
            f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/metadata.yaml"
        ]
        for url in raw_meta_urls:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=4) as resp:
                    if resp.status == 200:
                        txt = resp.read().decode("utf-8")
                        for line in txt.splitlines():
                            if line.strip().startswith("version:"):
                                remote_tag = line.split(":", 1)[1].strip().strip('"').strip("'")
                                break
                        if remote_tag:
                            release_name = f"小白 {remote_tag} 最新版本"
                            release_date = time.strftime("%Y-%m-%d")
                            changelog = "请关注版本 Release 更新说明与特性。"
                            break
            except Exception:
                continue

    if not remote_tag:
        remote_tag = local_ver
        release_name = f"小白 {local_ver} 当前已是最新"
        changelog = "当前已是最新版本。"

    # 版本对比
    has_update = _parse_version_tuple(remote_tag) > _parse_version_tuple(local_ver)

    res = {
        "ok": True,
        "current_version": local_ver,
        "latest_version": remote_tag,
        "has_update": has_update,
        "release_name": release_name,
        "release_date": release_date,
        "changelog": changelog
    }

    _LAST_CHECK_RES = res
    _LAST_CHECK_TIME = now
    return json_response(res)
