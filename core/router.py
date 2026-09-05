# -*- coding: utf-8 -*-
"""Layer 3 — Router Layer
统一指令路由：自定义/别名 → 指令开关 → 系统开关守卫 → 9引擎 → 超管
保持与 main.handle 完全一致的语义，供 XbBot 调度。
"""
import random

_REPLY_OVERRIDE_SEC = "指令回复配置"
_DEFAULT_MARKERS = ("{回复}", "{默认}", "默认", "默认回复")
_CUSTOM_SEC = "自定义指令配置"
_DISABLE_SEC = "指令启用配置"
_SYS_ENG = {'slave': '奴隶', 'sign': '签到', 'bank': '银行', 'ent': '娱乐', 'spirit': '精灵', 'ride': '坐骑', 'guild': '帮派', 'superadmin': '超管', 'chat': '聊天', 'adventure': '冒险'}

_MAIN_MENU = (
    "★ 小白主菜单 ★\r\n"
    "----------------\r\n"
    "| ❤️ 签到系统 | ✨ 精灵系统 |\r\n"
    "| 🎮 娱乐系统 | 🏦 银行系统 |\r\n"
    "| ⛓️ 奴隶系统 | 🏍️ 坐骑系统 |\r\n"
    "| ⚔️ 帮派系统 | 🗺️ 冒险系统 |\r\n"
    "----------------\r\n"
    "发送系统关键词打开菜单，如【签到系统】【精灵系统】"
)


def _resolve_reply(cand, reply):
    if cand in _DEFAULT_MARKERS:
        return reply
    if "{回复}" in cand:
        return cand.replace("{回复}", reply)
    if "{默认}" in cand:
        return cand.replace("{默认}", reply)
    return cand


def apply_reply_override(raw, reply, store):
    try:
        if not raw or not reply:
            return reply
        raw = str(raw).strip()
        sec = store._CONFIG.get(_REPLY_OVERRIDE_SEC) if hasattr(store, "_CONFIG") else None
        if not isinstance(sec, dict):
            return reply
        try:
            kws = list(_custom_idx(store).get("ovr") or ())
            _indexed = True
        except Exception:
            kws = []
            _indexed = False
        if not kws:
            # 回退：无索引时逐项最长匹配（语义与旧版一致）
            hit = None
            for k in sec.keys():
                k = str(k)
                if isinstance(sec[k], str) and str(sec[k]).strip() and raw.startswith(k) and (hit is None or len(k) > len(hit)):
                    hit = k
            if hit is None:
                return reply
        elif _indexed:
            # 索引已按长度降序，首个命中即最长
            hit = None
            for k in kws:
                if raw.startswith(k):
                    hit = k
                    break
            if hit is None:
                return reply
        tpl = str(sec[hit])
        cands = [c.strip() for c in tpl.split("|") if c.strip()]
        if not cands:
            return reply
        cand = random.choice(cands) if len(cands) > 1 else cands[0]
        return _resolve_reply(cand, reply)
    except Exception:
        return reply


_GUARD_CACHE = {}
_GUARD_CACHE_TTL = 5.0  # 5s 缓存，千群每消息 18次kv/config读→命中后0次DB；由 _bump_config_ver 主动清空
_GUARD_CACHE_MAX = 5000  # 无界增长防护：千群×9系统键超限淘汰最旧一半
_GUARD_BATCH_TTL = 2.0  # 同 gid 批量复用：2s 内9引擎守卫共享一次计算，突发消息0重复计算
import time as _t_guard

def _sys_off(gid, engine, store):
    sysname = _SYS_ENG.get(engine)
    if not sysname:
        return False
    key = ("swf", str(gid), sysname)
    try:
        hit = _GUARD_CACHE.get(key)
        if hit and _t_guard.time() - hit[0] < _GUARD_CACHE_TTL:
            return hit[1]
    except Exception:
        pass
    try:
        val = store.recall_get("swf_%s_%s" % (gid, sysname), "1") == "0"
        try:
            _GUARD_CACHE[key] = (_t_guard.time(), val)
            if len(_GUARD_CACHE) > _GUARD_CACHE_MAX:
                # 淘汰最旧一半，防千群常驻内存无限涨
                try:
                    _old = sorted(_GUARD_CACHE.items(), key=lambda x: x[1][0])[:_GUARD_CACHE_MAX // 2]
                    for _k, _v in _old:
                        _GUARD_CACHE.pop(_k, None)
                except Exception:
                    pass
        except Exception:
            pass
        return val
    except Exception:
        return False


def _cfg_sys_off(engine, store):
    sysname = _SYS_ENG.get(engine)
    if not sysname:
        return False
    key = ("cfg", sysname)
    try:
        hit = _GUARD_CACHE.get(key)
        if hit and _t_guard.time() - hit[0] < _GUARD_CACHE_TTL:
            return hit[1]
    except Exception:
        pass
    try:
        val = store.cfg("系统开关配置", sysname + "系统", "真") != "真"
        try:
            _GUARD_CACHE[key] = (_t_guard.time(), val)
        except Exception:
            pass
        return val
    except Exception:
        return False


def _guard(gid, engine, is_admin, raw, store):
    if is_admin:
        return None
    sysname = _SYS_ENG.get(engine, engine)
    # 群开关 gacha/守卫缓存需在配置变更时失效，由 store._bump_config_ver 清空 _GUARD_CACHE
    if _cfg_sys_off(engine, store):
        return "【%s系统】已经被关闭了，无法使用该功能！" % sysname
    if _sys_off(gid, engine, store):
        return "【%s系统】已经被关闭了，无法使用该功能！\r\n如需开启，请发送【%s开关】开启！" % (sysname, sysname)
    return None

def clear_guard_cache():
    try:
        _GUARD_CACHE.clear()
    except Exception:
        pass
    try:
        _GUARD_BATCH_CACHE.clear()
    except Exception:
        pass

_GUARD_BATCH_CACHE = {}  # gid -> (ts, {engine: blocked_msg_or_None})

def _batch_guard_map(gid, is_admin, store):
    # 批量预计算9引擎守卫结果，0.3s内同gid复用，避免每引擎2次kv读
    if is_admin:
        return {}
    try:
        now = _t_guard.time()
        hit = _GUARD_BATCH_CACHE.get(str(gid))
        if hit and now - hit[0] < _GUARD_BATCH_TTL:
            return hit[1]
    except Exception:
        hit = None
    res = {}
    for eng in ("slave", "sign", "bank", "ent", "spirit", "ride", "guild", "adventure", "superadmin"):
        msg = _guard(gid, eng, is_admin, "", store)
        res[eng] = msg  # None表示放行
    try:
        _GUARD_BATCH_CACHE[str(gid)] = (now, res)
    except Exception:
        pass
    return res

_ENGINE_CMDS = {}

def _get_engine_cmds(engine, store=None):
    if engine not in _ENGINE_CMDS:
        try:
            from .config import _collect_commands
            import os
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            all_cmds = _collect_commands(base, store)
            if all_cmds:
                _ENGINE_CMDS.update(all_cmds)
        except Exception:
            pass
    return _ENGINE_CMDS.get(engine, [])

def _matches_engine(raw, engine, store=None):
    if not raw:
        return False
    rt = str(raw).strip()
    sysname = _SYS_ENG.get(engine, engine)
    if store and hasattr(store, "wake"):
        try:
            wakes = store.wake(sysname + "系统", sysname + "系统")
            if rt in wakes:
                return True
        except Exception:
            pass
    if rt in (sysname + "系统", sysname + "菜单", sysname + "帮助"):
        return True
    cmds = _get_engine_cmds(engine, store)
    for c in cmds:
        if c and rt.startswith(c):
            return True
    return False


def _multi_reply(reply_tpl):
    try:
        cands = [c.strip() for c in str(reply_tpl).split("|") if c.strip()]
        return random.choice(cands) if cands else reply_tpl
    except Exception:
        return reply_tpl


def _render_vars(tpl, gid, qq, store):
    try:
        import datetime as _dt
        name = qq
        try:
            from ..engines import slave as _sl  # type: ignore
            name = _sl.NOTE_NAMES.get(str(qq), str(qq))
        except Exception:
            try:
                import slave as _sl2  # type: ignore
                name = _sl2.NOTE_NAMES.get(str(qq), str(qq))
            except Exception:
                pass
        coin = ""
        try:
            coin = store.coin_name() if hasattr(store, "coin_name") else "金币"
        except Exception:
            coin = "金币"
        now = _dt.datetime.now()
        vars_map = {
            "{name}": str(name), "{qq}": str(qq), "{gid}": str(gid),
            "{group}": str(gid), "{time}": now.strftime("%H:%M:%S"),
            "{date}": now.strftime("%Y-%m-%d"), "{datetime}": now.strftime("%Y-%m-%d %H:%M:%S"),
            "{coin}": str(coin), "{金币}": str(coin),
        }
        for k, v in vars_map.items():
            if k in tpl:
                tpl = tpl.replace(k, v)
        # {at} -> @qq
        if "{at}" in tpl:
            tpl = tpl.replace("{at}", f"[CQ:at,qq={qq}]")
        return tpl
    except Exception:
        return tpl


_CUSTOM_IDX = {"ver": -1, "cmds": (), "dis": (), "ovr": ()}

def _custom_idx(store):
    """自定义/禁用/回复覆盖三表统一索引：按触发词长度降序预排，配置版本变更时重建。
    每消息三遍全量遍历 O(3C) → 一次索引命中，C=50 时约省 0.1-0.3ms。"""
    try:
        ver = getattr(store, "_CONFIG_VER", -1)
    except Exception:
        ver = -1
    try:
        if _CUSTOM_IDX.get("ver") == ver and ver != -1:
            return _CUSTOM_IDX
    except Exception:
        pass
    cmds, dis, ovr = (), (), ()
    try:
        sec = store._CONFIG.get(_CUSTOM_SEC) if hasattr(store, "_CONFIG") else None
        if isinstance(sec, dict):
            cmds = tuple(sorted((str(t) for t in sec.keys() if str(t)), key=len, reverse=True))
    except Exception:
        pass
    try:
        sec2 = store._CONFIG.get(_DISABLE_SEC) if hasattr(store, "_CONFIG") else None
        if isinstance(sec2, dict):
            dis = tuple(sorted((str(k) for k, v in sec2.items() if str(k) and (str(v).strip() == "假" or str(v).strip().lower() in ("0", "false"))), key=len, reverse=True))
    except Exception:
        pass
    try:
        sec3 = store._CONFIG.get(_REPLY_OVERRIDE_SEC) if hasattr(store, "_CONFIG") else None
        if isinstance(sec3, dict):
            ovr = tuple(sorted((str(k) for k in sec3.keys() if isinstance(sec3[k], str) and str(sec3[k]).strip()), key=len, reverse=True))
    except Exception:
        pass
    try:
        _CUSTOM_IDX["ver"], _CUSTOM_IDX["cmds"], _CUSTOM_IDX["dis"], _CUSTOM_IDX["ovr"] = ver, cmds, dis, ovr
    except Exception:
        pass
    return _CUSTOM_IDX


def _custom_cmd(raw, store):
    try:
        sec = store._CONFIG.get(_CUSTOM_SEC) if hasattr(store, "_CONFIG") else None
        if not isinstance(sec, dict):
            return None, raw
        raw = str(raw or "")
        hit = None
        try:
            _cmds = _custom_idx(store).get("cmds") or ()
        except Exception:
            _cmds = ()
        if _cmds:
            for t in _cmds:
                if raw.startswith(t):
                    hit = t
                    break
        else:
            for t in sec.keys():
                t = str(t)
                if t and raw.startswith(t) and (hit is None or len(t) > len(hit)):
                    hit = t
        if hit is None:
            return None, raw
        e = sec[hit]
        e = e if isinstance(e, dict) else {"reply": str(e)}
        cmd = str(e.get("command", "") or "").strip()
        reply = str(e.get("reply", "") or "").strip()
        rest = raw[len(hit):].strip()
        if cmd:
            return None, (cmd + (" " if rest else "") + rest)
        if reply:
            # 变量渲染 + 多回复随机（纯自定义支持 {name}/{qq}/{gid}/{time}/{coin}/{at} 等）
            try:
                # _custom_cmd 在路由层无 gid/qq 上下文时由 handle 传入 rest，此处先多选再渲染
                # 实际渲染在 handle 层带 gid/qq 时更准，这里仅做初步多选
                reply = _multi_reply(reply)
                # 尝试在 handle 层二次渲染（带真实 gid/qq），此处若能取到 store 的 gid/qq 透传则直接渲染
                # 保持兼容：若 reply 含 { 则留到 handle 再渲染
            except Exception:
                pass
            return reply, raw
        return None, raw
    except Exception:
        return None, raw


def _cmd_disabled(raw, store):
    try:
        raw = str(raw or "")
        try:
            _dis = _custom_idx(store).get("dis") or ()
        except Exception:
            _dis = ()
        if _dis:
            for k in _dis:
                if raw.startswith(k):
                    return k
            return None
        sec = store._CONFIG.get(_DISABLE_SEC) if hasattr(store, "_CONFIG") else None
        if not isinstance(sec, dict):
            return None
        hit = None
        for k, v in sec.items():
            k = str(k)
            if not k:
                continue
            if not (str(v).strip() == "假" or str(v).strip().lower() in ("0", "false")):
                continue
            if raw.startswith(k) and (hit is None or len(k) > len(hit)):
                hit = k
        return hit
    except Exception:
        return None


def handle(gid, qq, raw, is_private=False, is_admin=False, store=None, engines=None, chat_mod=None, superadmin_mod=None):
    # 总开关：完全静默，包括超管，最高优先级
    try:
        if store and store.cfg("总开关配置", "总开关", "真") != "真":
            return None
    except Exception:
        pass
    # 群组开关：按 gid 静默，包括超管，仅群聊
    if not is_private and gid and store:
        try:
            if store.cfg("群组开关配置", str(gid), "真") != "真":
                return None
        except Exception:
            pass
    # 维护开关
    try:
        if store and store.cfg("维护配置", "维护开关", "假") == "真" and not is_admin:
            return store.cfg("维护配置", "维护信息", "🚧 维护中，仅超管可用，请稍后再试。")
    except Exception:
        pass
    if is_private:
        try:
            if chat_mod:
                return chat_mod.handle(qq, raw)
        except Exception:
            pass
        if engines and "chat" in engines:
            try:
                return engines["chat"].handle(qq, raw)
            except Exception:
                pass
        return None
    if raw.strip() in ("主菜单", "菜单", "系统菜单"):
        return _MAIN_MENU
    if not is_private and store:
        try:
            creply, raw = _custom_cmd(raw, store)
            if creply:
                # 纯自定义变量渲染（{name}/{qq}/{gid}/{time}/{coin}/{at}）且不再走名字前缀在 main 已跳过
                try:
                    creply = _render_vars(creply, gid, qq, store)
                except Exception:
                    pass
                return creply
        except Exception:
            pass
    dis = _cmd_disabled(raw, store) if store else None
    if dis:
        return "【指令】「%s」已被禁用，无法使用该功能！如需开启，请在指令页勾选启用。" % dis
    # 依次分发 9 引擎（批量守卫预计算，单消息18次读→0次）
    _batch_map = _batch_guard_map(gid, is_admin, store) if store and not is_private else {}
    if engines:
        for _eng in ("slave", "sign", "bank", "ent", "spirit", "ride", "guild", "adventure"):
            fn = engines.get(_eng)
            if not fn:
                continue
            matched = _matches_engine(raw, _eng, store)
            g = _batch_map.get(_eng) if _batch_map else (_guard(gid, _eng, is_admin, raw, store) if store else None)
            if g:
                if matched:
                    return g
                continue
            try:
                r = fn.handle(gid, qq, raw) if hasattr(fn, "handle") else fn(gid, qq, raw)
            except Exception as e:
                import traceback
                err_tb = traceback.format_exc()
                try:
                    from .logger import error as _log_err
                    _log_err(f"[{_eng}] handle异常: {e}\n{err_tb}")
                except Exception:
                    pass
                # 若消息明确匹配该系统指令却执行崩溃，绝不可静默吞掉！向用户反馈错误提示
                # 底层存储异常必须优雅降级为繁忙提示，严禁向群聊暴露 database is locked / rollback 等原始DB错误
                if matched:
                    sysname = _SYS_ENG.get(_eng, _eng)
                    try:
                        msg_l = str(e).lower()
                    except Exception:
                        msg_l = ""
                    if any(k in msg_l for k in ("database", "locked", "rollback", "transaction", "sqlite", "misuse", "owner", "not defined")):
                        return f"【{sysname}系统】当前人数较多，系统繁忙，请稍后重试~"
                    return f"【{sysname}系统】处理指令时出现异常，请稍后重试（原因: {e}）"
                r = None
            if r:
                return apply_reply_override(raw, r, store)
    # 超管（复用同一批量map）
    matched_admin = _matches_engine(raw, "superadmin", store)
    if engines and superadmin_mod:
        g = _batch_map.get("superadmin") if _batch_map else (_guard(gid, "superadmin", is_admin, raw, store) if store else None)
        if g:
            if matched_admin:
                return g
        else:
            try:
                r = superadmin_mod.handle(gid, qq, raw, is_admin)
                if r:
                    return apply_reply_override(raw, r, store)
            except Exception as e:
                import traceback
                try:
                    from .logger import error as _log_err
                    _log_err(f"[superadmin] handle异常: {e}\n{traceback.format_exc()}")
                except Exception:
                    pass
                if matched_admin:
                    try:
                        _ml = str(e).lower()
                    except Exception:
                        _ml = ""
                    if any(k in _ml for k in ("database", "locked", "rollback", "transaction", "sqlite", "misuse")):
                        return "【超管系统】当前人数较多，系统繁忙，请稍后重试~"
                    return f"【超管系统】处理指令时出现异常，请稍后重试（原因: {e}）"
    elif engines and "superadmin" in engines:
        fn = engines["superadmin"]
        g = _batch_map.get("superadmin") if _batch_map else (_guard(gid, "superadmin", is_admin, raw, store) if store else None)
        if g:
            if matched_admin:
                return g
        else:
            try:
                r = fn.handle(gid, qq, raw, is_admin) if hasattr(fn, "handle") else fn(gid, qq, raw, is_admin)
                if r:
                    return apply_reply_override(raw, r, store)
            except Exception as e:
                import traceback
                try:
                    from .logger import error as _log_err
                    _log_err(f"[superadmin] handle异常: {e}\n{traceback.format_exc()}")
                except Exception:
                    pass
                if matched_admin:
                    try:
                        _ml2 = str(e).lower()
                    except Exception:
                        _ml2 = ""
                    if any(k in _ml2 for k in ("database", "locked", "rollback", "transaction", "sqlite", "misuse")):
                        return "【超管系统】当前人数较多，系统繁忙，请稍后重试~"
                    return f"【超管系统】处理指令时出现异常，请稍后重试（原因: {e}）"
    return None
