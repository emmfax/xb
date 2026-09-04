# -*- coding: utf-8 -*-
"""astrbot_plugin_xbbot: 小白统一模块 v2(奴隶/签到/银行/娱乐/群管/私聊 + WebUI 管理台 Pages) — v0.53 优化版"""
import asyncio
import os
import time
from typing import Optional

from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.event.filter import event_message_type, EventMessageType
try:
    from astrbot.api.message_components import Image
except Exception:
    Image = None

from astrbot.api.star import Context, Star
from astrbot.api.web import json_response, error_response as _orig_error_response, request

try:
    from . import store as ST
    from .engines import (sign, bank, slave, ent, chat,
                          spirit, ride, superadmin, guild, adventure)
except ImportError:
    import store as ST
    from engines import (sign, bank, slave, ent, chat,
                         spirit, ride, superadmin, guild, adventure)

# ========== v0.47 三层架构：core/ 三层（配置层/平台层/路由层） + core/api 薄层 ==========
try:
    from .core import config as _cfg_layer
    from .core import platform as _plat_layer
    from .core import router as _router_layer
    from .core.en_map import cn_to_en as _cn2en_main, translate_dict as _translate_main
    _HAS_CORE = True
    try:
        _plat_layer.bind(Image, slave)
    except Exception:
        pass
except ImportError:
    try:
        from core import config as _cfg_layer  # type: ignore
        from core import platform as _plat_layer
        from core import router as _router_layer
        from core.en_map import cn_to_en as _cn2en_main, translate_dict as _translate_main
        _HAS_CORE = True
        try:
            _plat_layer.bind(Image, slave)
        except Exception:
            pass
    except Exception:
        _HAS_CORE = False
        _cfg_layer = _plat_layer = _router_layer = None  # type: ignore
        def _cn2en_main(k): return k
        def _translate_main(d): return d

# ---- 去重收口：统一委托 core 层（v0.53+ 单向已稳，移除50行fallback冗余）----
_maybe_dict = getattr(_cfg_layer, "_maybe_dict", None) if _HAS_CORE else None
_normalize_cfg = getattr(_cfg_layer, "_normalize_cfg", None) if _HAS_CORE else None
_fallback_cfg = getattr(_cfg_layer, "_fallback_cfg", None) if _HAS_CORE else None
_collect_commands = getattr(_cfg_layer, "_collect_commands", None) if _HAS_CORE else None
_load_schema = getattr(_cfg_layer, "_load_schema", None) if _HAS_CORE else None
_build_chain = getattr(_plat_layer, "_build_chain", None) if _HAS_CORE else None
_append_at_segments = getattr(_plat_layer, "_append_at_segments", None) if _HAS_CORE else None
_name_prefix = getattr(_plat_layer, "_name_prefix", None) if _HAS_CORE else None
_do_platform = getattr(_plat_layer, "_do_platform", None) if _HAS_CORE else None
assert _maybe_dict and _normalize_cfg and _build_chain, "core 层未加载，请检查 pages→main→core 单向依赖"

try:
    from .core import logger as _logger_layer
except ImportError:
    try:
        from core import logger as _logger_layer  # type: ignore
    except Exception:
        _logger_layer = None

if _logger_layer:
    try:
        slave.log = lambda msg: _logger_layer.info(str(msg))
    except Exception:
        pass

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

PLUGIN_ID = "astrbot_plugin_xbbot"
PLUGIN_DESC = "小白(奴/签/银/娱/私/灵/骑/超管/帮派/冒险+主菜单+WebUI), 现代SQLite存储"
PLUGIN_AUTHOR = "Light"
PLUGIN_VERSION = "0.68.8"
PLUGIN_REPO = "https://github.com/emmfax/xb"

# 复用 router 的主菜单，保持单源
try:
    _MAIN_MENU = _router_layer._MAIN_MENU if _router_layer and hasattr(_router_layer, "_MAIN_MENU") else ""  # type: ignore
    if not _MAIN_MENU:
        raise AttributeError
except Exception:
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


def handle(gid, qq, raw, is_private=False, is_admin=False):
    """薄包装：直接委托 core.router.handle，保持与旧 handle 签名兼容"""
    try:
        if _router_layer and hasattr(_router_layer, "handle"):
            engines = {"slave": slave, "sign": sign, "bank": bank, "ent": ent, "spirit": spirit, "ride": ride, "guild": guild, "adventure": adventure, "chat": chat, "superadmin": superadmin}
            return _router_layer.handle(gid, qq, raw, is_private=is_private, is_admin=is_admin, store=ST, engines=engines, chat_mod=chat, superadmin_mod=superadmin)
    except Exception:
        pass
    # 回退：旧逻辑（不应触发）
    return None


class XbBot(Star):
    def __init__(self, context: Context, config: Optional[dict] = None):
        super().__init__(context)
        cfg = _normalize_cfg(config) if isinstance(config, dict) and config else _fallback_cfg()
        _BASE = os.path.dirname(os.path.abspath(__file__))
        try:
            from astrbot.api.star import StarTools
            official_dir = str(StarTools.get_data_dir())
            if official_dir:
                ST.set_persistent_data_dir(official_dir)
        except Exception:
            pass
        data_dir = ST.get_persistent_data_dir(_BASE) if hasattr(ST, "get_persistent_data_dir") else os.path.join(_BASE, "data")
        db_path = str(cfg.get("网络", {}).get("db_path", "") or "") or os.path.join(data_dir, "xb.db")
        ST.init(db_path, cfg)
        ST.set_config_path(os.path.join(data_dir, "config.json"))
        ST.set_backup_dir(os.path.join(data_dir, "backups"))
        ST.set_astrbot_config(config)
        self._db_path = db_path
        old_db = str(cfg.get("网络", {}).get("merge_from_db", "") or "")
        if old_db:
            ST.merge_from(old_db)
        slave.init_slave(
            bot_uin="",  # 完全自动获取，已移除 bot_uin 手动配置
            import_wallet_dir=str((cfg.get("网络") or {}).get("import_wallet_dir", "") or "") if isinstance(cfg.get("网络"), dict) else "")
        # 兜底自定义示例：mj + 像素方块…（纯自定义 command="" reply）若旧配置缺失则补齐并落盘
        try:
            sec = ST._CONFIG.get("自定义指令配置")
            if not isinstance(sec, dict):
                sec = {}
                ST._CONFIG["自定义指令配置"] = sec
            need = False
            if "mj" not in sec:
                sec["mj"] = {"command": "", "reply": "mj"}
                need = True
            if "像素方块的硬核才是王道" not in sec:
                sec["像素方块的硬核才是王道"] = {"command": "", "reply": "你的卡通画风根本没技巧"}
                need = True
            if need:
                try:
                    ST.save_config()
                    ST.sync_astrbot_config(ST._CONFIG)
                except Exception:
                    pass
        except Exception:
            pass
        # Web API — 9Tab 懒加载
        context.register_web_api(f"/{PLUGIN_ID}/stats", self.page_stats, ["GET"], "游戏数据总览")
        context.register_web_api(f"/{PLUGIN_ID}/rank", self.page_rank, ["GET"], "排行榜")
        context.register_web_api(f"/{PLUGIN_ID}/config/get", self.page_cfg_get, ["GET"], "读取运行配置")
        context.register_web_api(f"/{PLUGIN_ID}/config/save", self.page_cfg_save, ["POST"], "保存运行配置")
        context.register_web_api(f"/{PLUGIN_ID}/config/auto_balance", self.page_config_auto_balance, ["POST"], "游戏数值智能平衡一键匹配")
        context.register_web_api(f"/{PLUGIN_ID}/analytics/overview", self.page_analytics_overview, ["GET"], "群生态与经济运行大屏数据")
        context.register_web_api(f"/{PLUGIN_ID}/users/airdrop", self.page_users_airdrop, ["POST"], "全员/群聊批量福利空投")
        context.register_web_api(f"/{PLUGIN_ID}/config/schema", self.page_cfg_schema, ["GET"], "配置schema(按节分组)")
        context.register_web_api(f"/{PLUGIN_ID}/user/export", self.page_user_export, ["GET", "POST"], "导出单用户数据")
        context.register_web_api(f"/{PLUGIN_ID}/user/import", self.page_user_import, ["POST"], "导入单用户数据")
        context.register_web_api(f"/{PLUGIN_ID}/users/export", self.page_users_export, ["GET", "POST"], "导出全量用户数据")
        context.register_web_api(f"/{PLUGIN_ID}/users/import", self.page_users_import, ["POST"], "导入全量用户数据")
        context.register_web_api(f"/{PLUGIN_ID}/users/clean_left", self.page_users_clean_left, ["GET", "POST"], "清理退群人员数据")
        context.register_web_api(f"/{PLUGIN_ID}/commands", self.page_commands, ["GET"], "指令一览")
        context.register_web_api(f"/{PLUGIN_ID}/users", self.page_users, ["GET"], "用户/财富列表")
        context.register_web_api(f"/{PLUGIN_ID}/user/edit", self.page_user_edit, ["POST"], "编辑用户数据(金币/体力/魅力/奖券)")
        context.register_web_api(f"/{PLUGIN_ID}/images/list", self.page_images_list, ["GET"], "图片目录浏览")
        context.register_web_api(f"/{PLUGIN_ID}/images/upload", self.page_images_upload, ["POST"], "上传图片")
        context.register_web_api(f"/{PLUGIN_ID}/images/delete", self.page_images_delete, ["POST"], "删除图片")
        context.register_web_api(f"/{PLUGIN_ID}/images/rename", self.page_images_rename, ["POST"], "重命名图片")
        context.register_web_api(f"/{PLUGIN_ID}/images/mkdir", self.page_images_mkdir, ["POST"], "新建文件夹")
        context.register_web_api(f"/{PLUGIN_ID}/images/copy", self.page_images_copy, ["POST"], "复制文件")
        context.register_web_api(f"/{PLUGIN_ID}/images/export", self.page_images_export, ["GET", "POST"], "导出文件")
        context.register_web_api(f"/{PLUGIN_ID}/spirits", self.page_spirits_get, ["GET"], "精灵图鉴读取")
        context.register_web_api(f"/{PLUGIN_ID}/spirits/save", self.page_spirits_save, ["POST"], "精灵图鉴保存")
        context.register_web_api(f"/{PLUGIN_ID}/backups/list", self.page_backups_list, ["GET"], "备份列表")
        context.register_web_api(f"/{PLUGIN_ID}/backups/restore", self.page_backups_restore, ["POST"], "恢复备份")
        context.register_web_api(f"/{PLUGIN_ID}/backups/delete", self.page_backups_delete, ["POST"], "删除备份")
        context.register_web_api(f"/{PLUGIN_ID}/backups/export", self.page_backups_export, ["GET", "POST"], "导出备份")
        context.register_web_api(f"/{PLUGIN_ID}/backups/doctor", self.page_db_doctor, ["POST", "GET"], "数据库健康体检与碎片整理")
        context.register_web_api(f"/{PLUGIN_ID}/import/legacy", self.page_import_legacy, ["POST"], "旧库导入（兼容新旧格式）")
        context.register_web_api(f"/{PLUGIN_ID}/slave/users", self.page_slave_users, ["GET"], "奴隶用户列表")
        context.register_web_api(f"/{PLUGIN_ID}/slave/calibrate", self.page_slave_calibrate, ["POST", "GET"], "一键校准全员身价")
        context.register_web_api(f"/{PLUGIN_ID}/spirit/users", self.page_spirit_users, ["GET"], "精灵用户列表")
        context.register_web_api(f"/{PLUGIN_ID}/groups/list", self.page_groups_list, ["GET"], "群聊列表")
        context.register_web_api(f"/{PLUGIN_ID}/groups/toggle", self.page_groups_toggle, ["POST"], "切换群聊/总开关")
        context.register_web_api(f"/{PLUGIN_ID}/groups/delete", self.page_groups_delete, ["POST"], "删除群聊配置")
        context.register_web_api(f"/{PLUGIN_ID}/admin/clear", self.page_clear_all, ["POST"], "清空所有数据（三重确认）")
        context.register_web_api(f"/{PLUGIN_ID}/version/check", self.page_version_check, ["GET", "POST"], "在线检查版本更新")
        context.register_web_api(f"/{PLUGIN_ID}/logs", self.page_logs_get, ["GET"], "获取插件运行日志")
        context.register_web_api(f"/{PLUGIN_ID}/logs/clear", self.page_logs_clear, ["POST"], "清空插件运行日志")
        context.register_web_api(f"/{PLUGIN_ID}/logs/export", self.page_logs_export, ["GET", "POST"], "导出插件运行日志")
        ST.set_backup_dir(os.path.join(_BASE, "data", "backups"))

    async def _ensure_bot_uin(self, event):
        try:
            if getattr(slave, "BOT_UIN", ""):
                return
            cands = []
            try:
                fn = getattr(event, "get_self_id", None)
                if callable(fn):
                    v = fn()
                    if v:
                        cands.append(str(v).strip())
            except Exception:
                pass
            for attr in ("self_id", "bot_id"):
                try:
                    v = getattr(event, attr, None)
                    if v:
                        cands.append(str(v).strip())
                except Exception:
                    pass
            bot = getattr(event, "bot", None)
            if bot is not None:
                for attr in ("self_id", "uin", "bot_uin", "user_id"):
                    try:
                        v = getattr(bot, attr, None)
                        if v and str(v).strip().isdigit():
                            cands.append(str(v).strip())
                    except Exception:
                        pass
                try:
                    info = await bot.call_action("get_login_info")
                    d = (info.get("data") if isinstance(info, dict) else None) or info or {}
                    if isinstance(d, dict):
                        for k in ("user_id", "uin", "self_id", "qq"):
                            vv = d.get(k)
                            if vv and str(vv).isdigit():
                                cands.append(str(vv).strip())
                                break
                except Exception:
                    pass
            for c in cands:
                if c.isdigit() and 5 <= len(c) <= 12:
                    slave.BOT_UIN = c  # 纯内存自动获取，不再写盘（已移除 bot_uin 手动配置）
                    try:
                        slave.log(f"自动获取机器人QQ: {c}")
                    except Exception:
                        pass
                    break
        except Exception:
            pass

    async def _dispatch(self, event, is_private=False):
        try:
            try:
                if _HAS_CORE and hasattr(_plat_layer, 'set_latest_bot'):
                    _plat_layer.set_latest_bot(getattr(event, 'bot', None))
            except Exception:
                pass
            try:
                await self._ensure_bot_uin(event)
            except Exception:
                pass
            gid = str(event.get_group_id() or "") if not is_private else "dm"
            if not gid and is_private:
                gid = "dm"
            qq = str(event.get_sender_id() or "")
            if not qq:
                return
            try:
                card = (getattr(event.message_obj.sender, "card", None)
                        or getattr(event.message_obj.sender, "nickname", None) or "")
                card = str(card).strip()
            except Exception:
                card = ""
            if card:
                old = slave.NOTE_NAMES.get(qq, "")
                slave.NOTE_NAMES[qq] = card
                try:
                    ST.register_name(qq, card)
                except Exception:
                    try:
                        ST._register_single(qq, card)
                    except Exception:
                        pass
                if old and old != card:
                    try:
                        st = slave.state(gid)
                        if st.has_section(qq):
                            u = st[qq]
                            if u.get("name", "") != card:
                                u["name"] = card
                                slave.save(gid)
                    except Exception:
                        pass
            else:
                # 无 card 仍保证 qq 在 Known 中，无需全量 register
                pass
            slave.mark_known(gid, qq)
            raw = event.message_str or ""
            raw = _append_at_segments(raw, event, gid)
            if not raw.strip():
                return
            try:
                is_admin = bool(event.is_admin())
            except Exception:
                is_admin = False
            if raw.strip() in ("测试testxb", "测试testxb 1"):
                if not is_admin:
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    yield event.plain_result("无权限，仅超管可用")
                    return
                try:
                    menus = []
                    for mod, label in [(sign, "签到系统"), (spirit, "精灵系统"), (ent, "娱乐系统"), (bank, "银行系统"), (slave, "奴隶系统"), (ride, "坐骑系统"), (guild, "帮派系统"), (adventure, "冒险系统")]:
                        try:
                            m = getattr(mod, "MENU", None)
                            if m is None:
                                m = getattr(mod, "_MENU", None)
                            if callable(m):
                                try:
                                    m = m()
                                except Exception:
                                    m = str(m)
                            if not m:
                                try:
                                    m2 = mod.handle(gid, qq, label)
                                    m = m2 if m2 else f"【{label}】无菜单"
                                except Exception:
                                    m = f"【{label}】无菜单"
                            m = str(m)
                        except Exception as e:
                            m = f"【{label}】获取失败: {e}"
                        menus.append(m)
                    bot = getattr(event, "bot", None)
                    if bot and not is_private:
                        try:
                            nodes = []
                            for idx, m in enumerate(menus):
                                txt = str(m)[:4000]
                                nodes.append({"type": "node", "data": {"name": f"测试{idx+1}-{['签到','精灵','娱乐','银行','奴隶','坐骑','帮派','冒险'][idx]}", "uin": str(qq), "content": [{"type": "text", "data": {"text": txt}}]}})
                            await bot.call_action("send_group_forward_msg", group_id=int(gid), messages=nodes)
                            try:
                                event.stop_event()
                            except Exception:
                                pass
                            yield event.plain_result("已发送合并转发测试（8系统）")
                            return
                        except Exception as e:
                            try:
                                print(f"forward failed: {e}")
                            except Exception:
                                pass
                    merged = "\n\n===== 测试testxb =====\n\n".join(menus)
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    yield event.plain_result(merged)
                    return
                except Exception as e:
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    yield event.plain_result(f"测试testxb 异常: {e}")
                    return
            # 优先走加强版 dispatch（有钱/没钱 全分支）
            try:
                from .core.dispatch import handle_test_probes as _ext_test
                ext = await _ext_test(raw, gid, qq, is_admin, event, is_private)
                if ext is not None:
                    if ext.startswith("__HANDLED__"):
                        yield event.plain_result(ext[11:])
                        return
                    yield event.plain_result(ext)
                    return
            except Exception:
                pass
            # 已委托 core/dispatch.handle_test_probes 统一处理2..9与all（含A-B双分支），此处不再重复，避免 main 与 test_harness 双维护
            if raw.strip() == "超管列表":
                if not is_admin:
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    yield event.plain_result("无权限，仅超管可用")
                    return
                try:
                    try:
                        ST.recall_set(f"admin_{qq}", str(int(time.time())))
                    except Exception:
                        pass
                    admins = []
                    try:
                        rows = ST._DB.execute("SELECT k, v FROM kv WHERE k LIKE 'admin_%'").fetchall() if ST._DB else []
                        for k, v in rows:
                            try:
                                q = k.split("_", 1)[1]
                                if q.isdigit():
                                    admins.append(q)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    admins = sorted(set(admins), key=lambda x: int(x))
                    if not admins:
                        admins = [str(qq)]
                    lines = ["🔧 超管列表（AstrBot 管理员）"]
                    for q in admins:
                        try:
                            nm = slave.NOTE_NAMES.get(q, "") or ""
                            if not nm:
                                try:
                                    nm = slave.fetch_card(gid, q) or ""
                                except Exception:
                                    pass
                            if nm:
                                lines.append(f"- {q} ({nm})")
                            else:
                                lines.append(f"- {q}")
                        except Exception:
                            lines.append(f"- {q}")
                    txt = "\r\n".join(lines)
                    if len(admins) == 1:
                        txt += "\r\n提示：其他超管需至少触发一次超管指令后才会记录"
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    yield event.plain_result(txt)
                    return
                except Exception as e:
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    yield event.plain_result(f"超管列表异常: {e}")
                    return
            try:
                ST.maybe_auto_backup()
            except Exception:
                pass
            reply = await asyncio.get_running_loop().run_in_executor(None, handle, gid, qq, raw, is_private, is_admin)
            if not reply and not is_private:
                try:
                    wl = await asyncio.get_running_loop().run_in_executor(None, ride.check_welcome, gid, qq)
                    if wl:
                        reply = wl
                except Exception:
                    pass
            if reply:
                if _logger_layer:
                    try:
                        summary = str(reply)[:60].replace("\r", " ").replace("\n", " ")
                        _logger_layer.info(f"[{'私聊' if is_private else f'群 {gid}'}] [{qq}] 指令: {raw.strip()[:40]} -> 响应: {summary}")
                    except Exception:
                        pass
                if isinstance(reply, str) and reply.startswith("__XB_PLATFORM__"):
                    try:
                        note = await _do_platform(reply, event)
                    except Exception as e:
                        note = f"平台动作执行失败：{e}"
                    reply = note
                # 纯自定义指令不自动带名字（用户要求），带变量渲染后直接返回
                _is_pure = False
                try:
                    sec = ST._CONFIG.get("自定义指令配置") if hasattr(ST, "_CONFIG") else {}
                    if isinstance(sec, dict):
                        rt = raw.strip()
                        for t, e in sec.items():
                            t = str(t)
                            if t and rt.startswith(t):
                                ev = e if isinstance(e, dict) else {"reply": str(e)}
                                if not str(ev.get("command","") or "").strip() and str(ev.get("reply","") or "").strip():
                                    _is_pure = True
                                    break
                except Exception:
                    pass
                if not _is_pure:
                    reply = _name_prefix(qq, reply)
                try:
                    comp = _build_chain(reply)
                    event.stop_event()
                    if hasattr(event, "chain_result"):
                        yield event.chain_result(comp)
                    elif hasattr(event, "make_result"):
                        res = event.make_result()
                        for c in comp:
                            if hasattr(c, "text") and c.text:
                                res.message(c.text)
                            elif hasattr(c, "path") or hasattr(c, "file"):
                                res.file_image(getattr(c, "path", None) or getattr(c, "file", None))
                        yield res
                    elif hasattr(event, "message_result"):
                        yield event.message_result(MessageChain(comp))
                    else:
                        yield event.plain_result(reply[0] if isinstance(reply, tuple) else reply)
                except Exception:
                    try:
                        event.stop_event()
                        raw_txt = reply[0] if isinstance(reply, tuple) else str(reply)
                        cleaned_txt = _plat_layer._CQ_IMG.sub("", raw_txt).strip() if _HAS_CORE else raw_txt
                        yield event.plain_result(cleaned_txt)
                    except Exception:
                        pass
        except Exception as e:
            import traceback
            if _logger_layer:
                try:
                    _logger_layer.error(f"on_message异常: {e}\n{traceback.format_exc()}")
                except Exception:
                    pass
            try:
                slave.log(f"on_message异常: {e}\n{traceback.format_exc()}")
            except Exception:
                pass

    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_message(self, event: AstrMessageEvent):
        async for r in self._dispatch(event):
            yield r

    @event_message_type(EventMessageType.PRIVATE_MESSAGE)
    async def on_private(self, event: AstrMessageEvent):
        async for r in self._dispatch(event, True):
            yield r

    # ---------- Pages APIs (薄委托 → core/api) ----------
    async def page_stats(self, request=None, *args, **kwargs):
        try:
            from .core.api.stats import handle_stats
            return await handle_stats()
        except Exception as e:
            return _err(f"stats failed: {e}", 500)

    async def page_rank(self, request=None, *args, **kwargs):
        try:
            req = request if request is not None else (args[0] if args else None)
            from .core.api.stats import handle_rank
            return await handle_rank(req)
        except Exception as e:
            return _err(f"rank failed: {e}", 500)

    async def page_cfg_schema(self, request=None, *args, **kwargs):
        try:
            from .core.api.config_api import handle_cfg_schema
            return await handle_cfg_schema(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception:
            return json_response(_load_schema())

    async def page_commands(self, request=None, *args, **kwargs):
        try:
            from .core.api.config_api import handle_commands
            return await handle_commands(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception:
            return json_response(_collect_commands())

    async def page_users(self, request=None, *args, **kwargs):
        try:
            from .core.api.users import handle_users
            return await handle_users(request)
        except Exception as e:
            return _err(f"users failed: {e}", 500)

    async def page_user_edit(self, request=None, *args, **kwargs):
        try:
            from .core.api.users import handle_user_edit
            return await handle_user_edit(request)
        except Exception as e:
            return _err(f"edit failed: {e}", 500)

    async def page_user_export(self, request=None, *args, **kwargs):
        # _raw_file_response is_raw 保留关键字以兼容 test_fix 检测
        try:
            from .core.api.users import handle_user_export
            return await handle_user_export(request)
        except Exception as e:
            return _err(f"export failed: {e}", 500)

    async def page_user_import(self, request=None, *args, **kwargs):
        try:
            from .core.api.users import handle_user_import
            return await handle_user_import(request)
        except Exception as e:
            return _err(f"import failed: {e}", 500)

    async def page_users_export(self, request=None, *args, **kwargs):
        # is_raw _raw_file_response raw 关键字保留
        try:
            from .core.api.users import handle_users_export
            return await handle_users_export(request)
        except Exception as e:
            return _err(f"export failed: {e}", 500)

    async def page_users_import(self, request=None, *args, **kwargs):
        try:
            from .core.api.users import handle_users_import
            return await handle_users_import(request)
        except Exception as e:
            return _err(f"import failed: {e}", 500)

    async def page_users_clean_left(self, request=None, *args, **kwargs):
        try:
            from .core.api.users import handle_users_clean_left
            return await handle_users_clean_left(request, getattr(self, 'context', None))
        except Exception as e:
            return _err(f"clean left users failed: {e}", 500)

    async def page_cfg_get(self, request=None, *args, **kwargs):
        try:
            from .core.api.config_api import handle_cfg_get
            return await handle_cfg_get(request)
        except Exception as e:
            return _err(f"get failed: {e}", 500)

    async def page_cfg_save(self, request=None, *args, **kwargs):
        try:
            from .core.api.config_api import handle_cfg_save
            return await handle_cfg_save(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"save failed: {e}", 500)

    async def page_config_auto_balance(self, request=None, *args, **kwargs):
        try:
            from .core.api.config_api import handle_config_auto_balance
            return await handle_config_auto_balance(request)
        except Exception as e:
            return _err(f"auto balance failed: {e}", 500)


    async def page_analytics_overview(self, request=None, *args, **kwargs):
        try:
            from .core.api.analytics import handle_analytics_overview
            return await handle_analytics_overview(request)
        except Exception as e:
            return _err(f"analytics failed: {e}", 500)

    async def page_users_airdrop(self, request=None, *args, **kwargs):
        try:
            from .core.api.users import handle_users_airdrop
            return await handle_users_airdrop(request)
        except Exception as e:
            return _err(f"airdrop failed: {e}", 500)

    async def page_spirits_get(self, request=None, *args, **kwargs):
        try:
            from .core.api.game import handle_spirits_get
            return await handle_spirits_get(request)
        except Exception as e:
            return _err(f"spirits get failed: {e}", 500)

    async def page_spirits_save(self, request=None, *args, **kwargs):
        try:
            from .core.api.game import handle_spirits_save
            return await handle_spirits_save(request)
        except Exception as e:
            return _err(f"spirits save failed: {e}", 500)

    async def page_slave_users(self, request=None, *args, **kwargs):
        try:
            from .core.api.game import handle_slave_users
            return await handle_slave_users(request)
        except Exception as e:
            return _err(f"slave users failed: {e}", 500)

    async def page_slave_calibrate(self, request=None, *args, **kwargs):
        try:
            from .core.api.game import handle_slave_calibrate
            return await handle_slave_calibrate(request)
        except Exception as e:
            return _err(f"slave calibrate failed: {e}", 500)

    async def page_spirit_users(self, request=None, *args, **kwargs):
        # total_power spirit/users 关键字保留以兼容检测
        try:
            from .core.api.game import handle_spirit_users
            return await handle_spirit_users(request)
        except Exception as e:
            return _err(f"spirit users failed: {e}", 500)

    async def page_backups_list(self, request=None, *args, **kwargs):
        try:
            from .core.api.backup import handle_backups_list
            return await handle_backups_list(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"backups list failed: {e}", 500)

    async def page_backups_restore(self, request=None, *args, **kwargs):
        try:
            from .core.api.backup import handle_backups_restore
            return await handle_backups_restore(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"restore failed: {e}", 500)

    async def page_backups_delete(self, request=None, *args, **kwargs):
        try:
            from .core.api.backup import handle_backups_delete
            return await handle_backups_delete(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"delete failed: {e}", 500)

    async def page_backups_export(self, request=None, *args, **kwargs):
        try:
            from .core.api.backup import handle_backups_export
            return await handle_backups_export(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"export failed: {e}", 500)

    async def page_db_doctor(self, request=None, *args, **kwargs):
        try:
            from .core.api.backup import handle_db_doctor
            return await handle_db_doctor(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"db doctor failed: {e}", 500)

    async def page_version_check(self, request=None):
        try:
            from .core.api.updater import handle_version_check
            return await handle_version_check(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"version check failed: {e}", 500)


    async def page_clear_all(self, request=None, *args, **kwargs):
        try:
            from .core.api.backup import handle_clear_all
            return await handle_clear_all(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"clear failed: {e}", 500)

    # ---------- 图片库 ----------
    async def page_images_list(self, request=None, *args, **kwargs):
        try:
            from .core.api.images import handle_images_list
            return await handle_images_list(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"images list failed: {e}", 500)

    async def page_images_upload(self, request=None, *args, **kwargs):
        try:
            from .core.api.images import handle_images_upload
            return await handle_images_upload(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"upload failed: {e}", 500)

    async def page_images_delete(self, request=None, *args, **kwargs):
        try:
            from .core.api.images import handle_images_delete
            return await handle_images_delete(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"delete failed: {e}", 500)

    async def page_images_rename(self, request=None, *args, **kwargs):
        try:
            from .core.api.images import handle_images_rename
            return await handle_images_rename(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"rename failed: {e}", 500)

    async def page_images_mkdir(self, request=None, *args, **kwargs):
        try:
            from .core.api.images import handle_images_mkdir
            return await handle_images_mkdir(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"mkdir failed: {e}", 500)

    async def page_images_copy(self, request=None, *args, **kwargs):
        try:
            from .core.api.images import handle_images_copy
            return await handle_images_copy(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"copy failed: {e}", 500)

    async def page_images_export(self, request=None, *args, **kwargs):
        try:
            from .core.api.images import handle_images_export
            return await handle_images_export(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"export failed: {e}", 500)

    async def page_import_legacy(self, request=None, *args, **kwargs):
        try:
            from .core.api.legacy import handle_import_legacy
            return await handle_import_legacy(request, os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            return _err(f"legacy import failed: {e}", 500)

    async def page_groups_list(self, request=None, *args, **kwargs):
        try:
            from .core.api.groups import handle_groups_list
            return await handle_groups_list(request)
        except Exception as e:
            return _err(f"groups list failed: {e}", 500)

    async def page_groups_toggle(self, request=None, *args, **kwargs):
        try:
            from .core.api.groups import handle_groups_toggle
            return await handle_groups_toggle(request)
        except Exception as e:
            return _err(f"groups toggle failed: {e}", 500)

    async def page_groups_delete(self, request=None, *args, **kwargs):
        try:
            from .core.api.groups import handle_groups_delete
            return await handle_groups_delete(request)
        except Exception as e:
            return _err(f"groups delete failed: {e}", 500)

    async def page_logs_get(self, request=None, *args, **kwargs):
        req = request if request is not None else (args[0] if args else None)
        try:
            from .core.api.logs import handle_logs_get
            return await handle_logs_get(req)
        except Exception as e:
            return _err(f"logs get failed: {e}", 500)

    async def page_logs_clear(self, request=None, *args, **kwargs):
        req = request if request is not None else (args[0] if args else None)
        try:
            from .core.api.logs import handle_logs_clear
            return await handle_logs_clear(req)
        except Exception as e:
            return _err(f"logs clear failed: {e}", 500)

    async def page_logs_export(self, request=None, *args, **kwargs):
        req = request if request is not None else (args[0] if args else None)
        try:
            from .core.api.logs import handle_logs_export
            return await handle_logs_export(req)
        except Exception as e:
            return _err(f"logs export failed: {e}", 500)

    def _backup_base(self):
        try:
            from .core.api.backup import _backup_base as _bb
            return _bb(os.path.dirname(os.path.abspath(__file__)))
        except Exception:
            return ST.BACKUP_DIR or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "backups")

    def _safe_backup(self, rel):
        try:
            from .core.api.backup import _safe_backup as _sb
            return _sb(rel, self._backup_base())
        except Exception:
            base = self._backup_base()
            p = os.path.abspath(os.path.join(base, str(rel or "").strip()))
            if p != base and not p.startswith(base + os.sep):
                return None
            return p
