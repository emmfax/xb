# -*- coding: utf-8 -*-
"""群组开关 API — 总开关 + 按群开关"""
import json
from astrbot.api.web import json_response

try:
    from ... import store as ST
except ImportError:
    import store as ST

async def handle_groups_list(request=None):
    gids = set()
    try:
        if ST._DB is not None:
            for (gid,) in ST._DB.execute("SELECT DISTINCT gid FROM wallet").fetchall():
                if str(gid).isdigit(): gids.add(str(gid))
            for (gid,) in ST._DB.execute("SELECT DISTINCT gid FROM accounts").fetchall():
                if str(gid).isdigit(): gids.add(str(gid))
            for (gid,) in ST._DB.execute("SELECT DISTINCT gid FROM groups").fetchall():
                if str(gid).isdigit(): gids.add(str(gid))
    except Exception:
        pass
    try:
        sec = ST._CONFIG.get("群组开关配置") if hasattr(ST, "_CONFIG") and isinstance(ST._CONFIG, dict) else {}
        if isinstance(sec, dict):
            for k in sec.keys():
                if str(k).isdigit():
                    gids.add(str(k))
    except Exception:
        pass

    out = []
    for gid in sorted(gids, key=lambda x: int(x) if str(x).isdigit() else 0):
        enabled = ST.cfg("群组开关配置", str(gid), "真") != "假"
        cnt = 0
        try:
            if ST._DB is not None and str(gid).isdigit():
                cnt = ST._DB.execute("SELECT COUNT(DISTINCT qq) FROM wallet WHERE gid=?", (int(gid),)).fetchone()[0]
        except Exception:
            cnt = 0
        out.append({"gid": str(gid), "enabled": enabled, "member_count": int(cnt or 0), "is_test": str(gid) == "999999"})
    
    total_enabled = ST.cfg("总开关配置", "总开关", "真") == "真"
    return json_response({"total_enabled": total_enabled, "groups": out})

async def handle_groups_toggle(request):
    data = {}
    try:
        data = await request.json()
    except Exception:
        try:
            data = await request.post()
        except Exception:
            data = {}
    gid = str(data.get("gid", "") or data.get("group_id", "") or "").strip()
    enabled = data.get("enabled")
    if isinstance(enabled, str):
        enabled = enabled.strip() not in ("假", "false", "False", "0", "off")
    else:
        enabled = bool(enabled) if enabled is not None else True

    if gid in ("total", "__total__", "总开关"):
        ST._CONFIG.setdefault("总开关配置", {})
        ST._CONFIG["总开关配置"]["总开关"] = "真" if enabled else "假"
        try: ST.save_config()
        except Exception: pass
        try: ST.sync_astrbot_config(ST._CONFIG)
        except Exception: pass
        return json_response({"ok": True, "total_enabled": enabled})

    if not gid or not gid.isdigit():
        return json_response({"ok": False, "msg": "群号必填且需为纯数字"}, status=400)

    ST._CONFIG.setdefault("群组开关配置", {})
    ST._CONFIG["群组开关配置"][gid] = "真" if enabled else "假"
    try: ST.save_config()
    except Exception: pass
    try: ST.sync_astrbot_config(ST._CONFIG)
    except Exception: pass
    try: ST.recall_set(f"group_switch_{gid}", "1" if enabled else "0")
    except Exception: pass

    # 同步初始化 group 实体
    try:
        grp = ST.group(gid)
        ST.save_group(gid)
    except Exception:
        pass

    return json_response({"ok": True, "gid": gid, "enabled": enabled})

async def handle_groups_delete(request):
    data = {}
    try:
        data = await request.json()
    except Exception:
        try:
            data = await request.post()
        except Exception:
            data = {}
    gid = str(data.get("gid", "") or data.get("group_id", "") or "").strip()
    if not gid or not gid.isdigit():
        return json_response({"ok": False, "msg": "群号必填且需为纯数字"}, status=400)
    try:
        sec = ST._CONFIG.get("群组开关配置") if hasattr(ST, "_CONFIG") and isinstance(ST._CONFIG, dict) else {}
        if isinstance(sec, dict) and gid in sec:
            sec.pop(gid, None)
        try: ST.save_config()
        except Exception: pass
        try: ST.sync_astrbot_config(ST._CONFIG)
        except Exception: pass
        try: ST.recall_set(f"group_switch_{gid}", "1")
        except Exception: pass
        return json_response({"ok": True, "gid": gid, "deleted": True})
    except Exception as e:
        return json_response({"ok": False, "msg": str(e)}, status=500)
