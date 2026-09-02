# -*- coding: utf-8 -*-
"""Layer 2 — Platform Layer
负责消息链构建、@解析、昵称前缀、平台动作（禁言/踢人）。
隔离 AstrBot / OneBot 适配差异，上层路由无需关心平台细节。
"""
import os
import re
import time


_CQ_IMG = re.compile(r"\[CQ:image,([^\]]*)\]")

# 由外部（main/slave）注入的 Image 组件与 slave 模块，避免循环导入
_Image = None
_slave = None

def bind(image_cls=None, slave_mod=None):
    global _Image, _slave
    if image_cls is not None:
        _Image = image_cls
    if slave_mod is not None:
        _slave = slave_mod


def _build_chain(reply):
    import urllib.parse
    from astrbot.api.message_components import Plain
    try:
        from astrbot.api.message_components import Image as _Img
    except Exception:
        _Img = _Image
    if _Img is None:
        _Img = _Image
    text, imgs = (reply[0], list(reply[1] or [])) if isinstance(reply, tuple) else (reply, [])
    tt = text or ""
    def _repl(m):
        attrs = {}
        for a in m.group(1).split(","):
            if "=" in a:
                k, v = a.split("=", 1)
                attrs[k.strip()] = v.strip()
        f = attrs.get("file", "")
        f_dec = urllib.parse.unquote(f)
        if f_dec.startswith("file:///"):
            p = f_dec[len("file:///")] if len(f_dec) > 8 and f_dec[9:10] == ":" else f_dec[len("file:///")-1:]
            if not os.path.isfile(p) and os.path.isfile(f_dec[len("file:///"):]):
                p = f_dec[len("file:///"):]
            imgs.append(p)
        elif f_dec.startswith("file://"):
            p = f_dec[len("file://"):]
            if not os.path.isfile(p) and os.path.isfile(f_dec[len("file://")+1:]):
                p = f_dec[len("file://")+1:]
            imgs.append(p)
        elif f_dec:
            imgs.append(f_dec)
        return ""
    tt = _CQ_IMG.sub(_repl, tt).strip()
    comp = [Plain(tt)] if tt else []
    for p in imgs:
        try:
            p_clean = str(p).strip()
            # On Windows: /C:/path -> C:/path
            if len(p_clean) > 3 and p_clean[0] == "/" and p_clean[2] == ":":
                p_clean = p_clean[1:]
            if _Img is not None and isinstance(p_clean, str) and os.path.isfile(p_clean):
                comp.append(_Img.fromFileSystem(p_clean))
        except Exception:
            pass
    if not comp and tt:
        comp = [Plain(tt)]
    return comp


def _append_at_segments(raw, event, gid="", slave_mod=None):
    sm = slave_mod or _slave
    try:
        if gid:
            mark_known = getattr(sm, "mark_known", None) if sm else None
        else:
            mark_known = None
        chain = event.message_obj.message or []
        ats = []
        for comp in chain:
            comp_type = getattr(comp, "type", "") or ""
            if "at" not in str(comp_type).lower():
                continue
            q = getattr(comp, "qq", None)
            if q is None:
                q = getattr(comp, "target", None)
            q = str(q or "").strip()
            if q.isdigit() and q not in ats:
                ats.append(q)
                if mark_known:
                    try:
                        mark_known(gid, q)
                    except Exception:
                        pass
                try:
                    nm = (getattr(comp, "name", None) or getattr(comp, "display", None) or getattr(comp, "card", None) or getattr(comp, "nickname", None) or "")
                    nm = str(nm).strip()
                    if nm and q and sm is not None:
                        old = sm.NOTE_NAMES.get(q, "")
                        sm.NOTE_NAMES[q] = nm
                        if old != nm:
                            try:
                                st = sm.state(gid)
                                if st.has_section(q):
                                    u = st[q]
                                    if u.get("name", "") != nm:
                                        u["name"] = nm
                                        sm.save(gid)
                            except Exception:
                                pass
                except Exception:
                    pass
        if ats:
            raw = (raw or "").rstrip()
            if raw and not raw.endswith(" "):
                raw += " "
            raw += " ".join("@" + q for q in ats)
    except Exception:
        pass
    return raw


def _name_prefix(qq, reply, slave_mod=None):
    sm = slave_mod or _slave
    try:
        nm = ""
        if sm is not None:
            nm = sm.NOTE_NAMES.get(str(qq), "") or str(qq)
        else:
            nm = str(qq)
        prefix = f"[{nm}]"
        def _already_has_name(s):
            head = s[:120]
            ts = head.lstrip()
            if ts.startswith(f"[{nm}]") or ts.startswith(f"【{nm}】"):
                return True
            if ts.startswith("[") and "]" in ts[:40]:
                try:
                    inner = ts[1:ts.index("]")]
                    if inner == nm:
                        return True
                    # 非本人前缀不算已有，需补本人前缀
                    return False
                except Exception:
                    return False
            if f"【{nm}】" in head[:60]:
                return True
            return False
        if isinstance(reply, tuple):
            t = (reply[0] or "") if reply else ""
            imgs = list(reply[1] or []) if len(reply) > 1 else []
            if _already_has_name(t):
                return (t, imgs)
            return (f"{prefix}{t}", imgs)
        s = str(reply) if reply is not None else ""
        if _already_has_name(s):
            return s
        return f"{prefix}{s}"
    except Exception:
        return reply


_GROUP_ADMIN_CACHE = {}
_GROUP_ADMIN_TTL = 300.0


async def _is_group_owner_or_admin(event):
    try:
        gid = str(event.get_group_id() or "")
        qq = str(event.get_sender_id() or "")
        key = f"{gid}:{qq}"
        now = time.time()
        hit = _GROUP_ADMIN_CACHE.get(key)
        if hit and now - hit[0] < _GROUP_ADMIN_TTL:
            return hit[1]
        bot = getattr(event, "bot", None)
        if bot is None:
            return False
        info = await bot.call_action("get_group_member_info", group_id=int(gid), user_id=int(qq))
        data = (info.get("data") if isinstance(info, dict) else None) or info or {}
        role = str(data.get("role", "")).lower()
        ok = role in ("owner", "admin", "administrator")
        if len(_GROUP_ADMIN_CACHE) > 500:
            for k in list(_GROUP_ADMIN_CACHE.keys())[:250]:
                _GROUP_ADMIN_CACHE.pop(k, None)
        _GROUP_ADMIN_CACHE[key] = (now, ok)
        return ok
    except Exception:
        return False


async def _do_platform(marker, event, slave_mod=None):
    sm = slave_mod or _slave
    extra_text = ""
    if "__TEXT__" in marker:
        marker, extra_text = marker.split("__TEXT__", 1)
    parts = marker.split("|")
    if len(parts) < 3:
        return "平台动作参数错误。"
    act = parts[1]
    target = parts[2]
    dur_raw = parts[3] if len(parts) > 3 else "0"
    try:
        dur = int(''.join(c for c in str(dur_raw) if c.isdigit()) or "0")
    except Exception:
        dur = 0
    gid = event.get_group_id()
    bot = getattr(event, "bot", None)
    if bot is None:
        return "平台动作需要适配器 Bot 实例支持（当前未连接）。"
    try:
        bot_uin = getattr(sm, "BOT_UIN", "") if sm else ""
        if not bot_uin:
            try:
                info0 = await bot.call_action("get_login_info")
                d0 = (info0.get("data") if isinstance(info0, dict) else None) or info0 or {}
                bot_uin = str(d0.get("user_id") or d0.get("uin") or d0.get("self_id") or "")
            except Exception:
                bot_uin = ""
        if bot_uin:
            try:
                info_bot = await bot.call_action("get_group_member_info", group_id=int(gid), user_id=int(bot_uin))
                d_bot = (info_bot.get("data") if isinstance(info_bot, dict) else None) or info_bot or {}
                role_bot = str(d_bot.get("role", "")).lower()
                if role_bot not in ("owner", "admin", "administrator"):
                    return "机器人不是管理员，无法执行禁言/踢人！"
            except Exception:
                pass
        try:
            info_t = await bot.call_action("get_group_member_info", group_id=int(gid), user_id=int(target))
            d_t = (info_t.get("data") if isinstance(info_t, dict) else None) or info_t or {}
            role_t = str(d_t.get("role", "")).lower()
            if role_t in ("owner", "admin", "administrator"):
                return "对方是管理员，无法禁言/踢人！"
        except Exception:
            pass
    except Exception:
        pass
    try:
        if act == "mute":
            try:
                await bot.call_action("set_group_ban", group_id=int(gid), user_id=int(target), duration=dur)
            except Exception as e1:
                if "不支持" in str(e1) or "not" in str(e1).lower():
                    await bot.call_action("set_group_mute", group_id=int(gid), user_id=int(target), duration=dur)
                else:
                    raise
            base = f"已将成员 <{target}> 禁言 {dur // 60} 分钟。"
            return (extra_text + "\r\n" + base) if extra_text else base
        if act == "kick":
            await bot.call_action("set_group_kick", group_id=int(gid), user_id=int(target))
            base = f"已将成员 <{target}> 移出本群。"
            return (extra_text + "\r\n" + base) if extra_text else base
    except Exception as e:
        if extra_text:
            return extra_text + f"\r\n平台动作执行失败：{e}"
        return f"平台动作执行失败：{e}"
    if extra_text:
        return extra_text
    return "未知平台动作。"


_LATEST_BOT = None

def set_latest_bot(bot):
    global _LATEST_BOT
    if bot is not None:
        _LATEST_BOT = bot

def get_latest_bot():
    return _LATEST_BOT

async def fetch_group_member_qqs(gid, bot=None, context=None):
    """通过 OneBot / AstrBot 适配器拉取指定群聊的实时在线成员 QQ 集合"""
    b = bot or _LATEST_BOT
    if b is None and context is not None:
        for attr in ("platform_adapters", "_platform_adapters", "get_platform_adapters", "get_bots", "bots"):
            try:
                val = getattr(context, attr, None)
                if callable(val):
                    val = val()
                if isinstance(val, (list, tuple, set)) and len(val) > 0:
                    for cand in val:
                        if cand is not None:
                            b = cand
                            break
                elif isinstance(val, dict) and len(val) > 0:
                    b = next(iter(val.values()))
                if b is not None:
                    break
            except Exception:
                pass

    if b is None:
        return None

    actions = ["get_group_member_list", "getGroupMemberList", "get_group_members"]
    cands = [b]
    for sub in ("bot", "client", "api", "_bot", "_client"):
        sub_obj = getattr(b, sub, None)
        if sub_obj is not None and sub_obj not in cands:
            cands.append(sub_obj)

    for cand in cands:
        for act in actions:
            try:
                info = None
                if hasattr(cand, "call_action") and callable(cand.call_action):
                    info = await cand.call_action(act, group_id=int(gid), no_cache=True)
                elif hasattr(cand, "call_api") and callable(cand.call_api):
                    info = await cand.call_api(act, group_id=int(gid), no_cache=True)
                elif hasattr(cand, act) and callable(getattr(cand, act)):
                    fn = getattr(cand, act)
                    info = await fn(group_id=int(gid), no_cache=True)

                if info is not None:
                    data = (info.get("data") if isinstance(info, dict) else None) or info or []
                    if isinstance(data, list) and len(data) > 0:
                        res = set()
                        for m in data:
                            if isinstance(m, dict):
                                q = str(m.get("user_id") or m.get("qq") or "").strip()
                                if q.isdigit():
                                    res.add(q)
                            elif isinstance(m, (int, str)) and str(m).isdigit():
                                res.add(str(m).strip())
                        if len(res) > 0:
                            return res
            except Exception:
                pass
    return None
