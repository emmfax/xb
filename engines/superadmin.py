# -*- coding: utf-8 -*-
"""超管系统 - 对齐原版超管/账户管理指令(已并入原群管的禁言/踢人/账户管理)
权限: is_admin = AstrBot 机器人管理员(event.is_admin())
数据级可测: 群列表/应用统计/账户管理(扣钱/充值/清空)
平台操作: 禁言/踢人 通过 AstrBot 适配器 call_action 执行(见 main._do_platform)
"""
import json
import re

try:
    from .. import store as ST
except ImportError:
    try:
        from . import store as ST
    except ImportError:
        import store as ST

MENU = (
    "🔧 超管系统\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "📇 群列表　📊 应用统计　🔖 小白版本\r\n"
    "💸 扣钱 @QQ 金额　💳 充钱 @QQ 金额\r\n"
    "🧹 清空财富/体力/魅力/账户/精灵/用户 @QQ\r\n"
    "🔨 禁言 @QQ 分钟　🚪 踢人 @QQ\r\n"
    "💾 备份xb　（立即备份全量数据）\r\n"
    "🛠️ 开启维护　关闭维护　维护信息 内容\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "⚠️ 全部指令仅限 AstrBot 机器人管理员\r\n"
    "💡 发送对应指令即可操作"
)


def _cfg(key, default=""):
    return ST.cfg("超管配置", key, default)



def _target_name(gid, t):
    t_str = str(t)
    try:
        from . import slave as S
        if hasattr(S, "uname"):
            try:
                n = S.uname(S.U(S.ST, t_str), t_str)
                if n and n != t_str:
                    return n
            except Exception:
                pass
        if hasattr(S, "NOTE_NAMES"):
            n = S.NOTE_NAMES.get(t_str)
            if n:
                return n
    except Exception:
        pass
    try:
        g = ST.group(gid)
        if g and t_str in g.users():
            n = g[t_str].get("name")
            if n:
                return n
    except Exception:
        pass
    try:
        a = ST.acct(gid, t_str)
        n = a.get("name")
        if n:
            return n
    except Exception:
        pass
    return t_str

def _name(qq):
    try:
        from . import slave as S
        return S.NOTE_NAMES.get(str(qq), str(qq)) if hasattr(S, "NOTE_NAMES") else str(qq)
    except Exception:
        return str(qq)


def _sum_money(gid, qq):
    return ST.coins_get(gid, qq)


def _acct(gid, qq):
    return ST.acct(gid, qq)


def _j(data):
    try:
        return json.loads(data or "{}")
    except Exception:
        return {}


# ---- 群列表 / 应用统计 ----
def cmd_groups():
    if ST._DB is None:
        return "无数据。"
    rows = ST._DB.execute(
        "SELECT gid, COUNT(*) c FROM groups GROUP BY gid UNION ALL "
        "SELECT gid, COUNT(*) FROM accounts GROUP BY gid").fetchall()
    seen = {}
    for gid, c in rows:
        seen[str(gid)] = seen.get(str(gid), 0) + int(c)
    lst = sorted(seen.items(), key=lambda x: -x[1])
    out = ["📇 群列表（群号：玩家数）"]
    for gid, c in lst[:30]:
        out.append(f"{gid}：{c}")
    return "\r\n".join(out) if len(out) > 1 else "暂无群数据。"


def cmd_stats():
    if ST._DB is None:
        return "无数据。"
    nw = ST._DB.execute("SELECT COUNT(*) FROM wallet").fetchone()[0]
    na = ST._DB.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    ng = ST._DB.execute("SELECT COUNT(DISTINCT gid) FROM accounts").fetchone()[0]
    tm = ST._DB.execute("SELECT COALESCE(SUM(money),0) FROM wallet").fetchone()[0]
    # 兼容新旧键：deposit(英文化) 与 cunkuan(旧)，中文统计文案不变
    try:
        td = ST._DB.execute("SELECT COALESCE(SUM(CAST(COALESCE(json_extract(data,'$.deposit'), json_extract(data,'$.cunkuan')) AS INTEGER)),0) FROM accounts").fetchone()[0] if ST._DB else 0
        td = int(td or 0)
    except Exception:
        td = 0
    return (f"📊 应用统计\r\n"
            f"钱包用户：{nw}　档案用户：{na}\r\n"
            f"群数：{ng}　总金币：{tm}　总存款：{td}")


# ---- 账户管理 ----
def _parse_target_amount(arg):
    """解析 扣钱/充钱 目标与金额: 支持 [CQ:at,qq=]/@QQ/@昵称/纯数字，金额取末数（修复 @昵称 后金额被误判为 QQ 的 bug）"""
    arg = (arg or "").strip()
    t, rest = None, arg
    # 1) 统一 @ 解析（含CQ/昵称/@QQ），优先
    try:
        t_tmp, rest_tmp = ST.parse_at(arg)
        if t_tmp:
            t, rest = t_tmp, rest_tmp
    except Exception:
        pass
    # 2) 直接 CQ 兜底
    if not t:
        m = re.search(r"\[CQ:at,qq=(\d+)[^\]]*\]", arg)
        if m:
            t = m.group(1)
            # rest 为去除 CQ 后的剩余
            rest = re.sub(r"\[CQ:at,qq=\d+[^\]]*\]", "", arg, count=1).strip()
    # 3) @QQ 兜底
    if not t:
        m = re.search(r"@\s*(\d{5,12})", arg)
        if m:
            t = m.group(1)
            rest = arg.replace(m.group(0), "", 1).strip()
    # 4) 纯数字开头
    if not t:
        m = re.match(r"(\d{5,12})\b", arg)
        if m:
            t = m.group(1)
            rest = arg[len(t):].strip().lstrip("* ").strip()
    if not t:
        nums = re.findall(r"\d+", arg)
        if len(nums) >= 2:
            return nums[-2], int(nums[-1])
        return None, None
    # 金额：优先取 rest 末尾的数字，其次取 arg 中最后一个非 t 的数字
    # rest 可能为 "100000" 或 "*100000" 等
    m = re.search(r"(\d+)\s*$", rest)
    if m:
        try:
            return t, int(m.group(1))
        except Exception:
            pass
    # 兼容金额紧贴 QQ 如 "QQ*100000" 或 "QQ 100000"
    # 从 rest 中找首个数字
    m = re.search(r"(\d+)", rest)
    if m:
        try:
            return t, int(m.group(1))
        except Exception:
            pass
    # 兜底：从原 arg 中找最后一个非 t 的数字
    nums = re.findall(r"\d+", arg)
    for n in reversed(nums):
        if n != t:
            try:
                return t, int(n)
            except Exception:
                continue
    # 仅剩 t 本身，无金额
    return None, None


def cmd_deduct(gid, qq, arg):
    """扣钱: 超管扣除指定用户指定金额，显示群昵称"""
    t, amt = _parse_target_amount(arg)
    if not t or amt is None:
        return "格式：扣钱 @QQ 金额（正整数）"
    cur = _sum_money(gid, t)
    nv = ST.coins_add(gid, t, -amt)
    t_name = _target_name(gid, t)
    return f"已扣除【{t_name}】{amt}{ST.coin_name()}（{cur}→{nv}）"


def cmd_recharge(gid, qq, arg):
    """充钱: 超管给指定用户充值指定金额，显示群昵称"""
    t, amt = _parse_target_amount(arg)
    if not t or amt is None:
        return "格式：充钱 @QQ 金额（正整数）"
    nv = ST.coins_add(gid, t, amt)
    t_name = _target_name(gid, t)
    return f"已为【{t_name}】充值 {amt}{ST.coin_name()}（当前 {nv}）"


def cmd_force_take(gid, qq, arg):
    t, amt = _parse_target_amount(arg)
    if not t or amt is None:
        return "格式：强制取款 @QQ 金额"
    a = _acct(gid, t)
    cur = a.int("deposit")
    take = min(cur, amt)
    a.set("deposit", str(cur - take))
    ST.acct_save(gid, t)
    ST.coins_add(gid, qq, take)
    t_name = _target_name(gid, t)
    return f"已强制取款【{t_name}】{take}{ST.coin_name()}（存入自己账户）"


def _clear_money(gid, t):
    cur = _sum_money(gid, t)
    ST.coins_add(gid, t, -cur)
    return f"已清空 <{_name(t)}> 财富。"


def _clear_field(gid, t, field, label):
    a = _acct(gid, t)
    a.set(field, "0")
    ST.acct_save(gid, t)
    return f"已清空 <{_name(t)}> 的{label}。"


def cmd_clear(gid, qq, arg):
    arg = (arg or "").strip()
    m = re.match(r"^(?:清空|重置)(财富|体力|魅力|账户|精灵|用户)\s*(.*)$", arg)
    if not m:
        return "格式：清空{财富/体力/魅力/账户/精灵/用户} @QQ"
    kind = m.group(1)
    rest = m.group(2).strip()
    t = None
    try:
        t_parsed, _ = ST.parse_at(rest)
        if t_parsed:
            t = str(t_parsed).strip()
    except Exception:
        pass
    if not t:
        m_cq = re.search(r"\[CQ:at,qq=(\d+)[^\]]*\]", rest)
        if m_cq:
            t = m_cq.group(1)
    if not t:
        m_qq = re.search(r"@?\s*(\d{5,12})", rest)
        if m_qq:
            t = m_qq.group(1)
    if not t:
        return "格式：清空{财富/体力/魅力/账户/精灵/用户} @QQ"
    if kind == "财富":
        return _clear_money(gid, t)
    if kind in ("体力", "stamina"):
        return _clear_field(gid, t, "stamina", "体力")
    if kind in ("魅力", "charm"):
        return _clear_field(gid, t, "charm", "魅力")
    if kind == "账户":
        a = _acct(gid, t)
        a.kv.clear()
        ST.acct_save(gid, t)
        _clear_money(gid, t)
        return f"已清空 <{_name(t)}> 的账户及财富数据。"
    if kind == "精灵":
        a = _acct(gid, t)
        a.set("spirits", "{}")
        ST.acct_save(gid, t)
        return f"已清空 <{_name(t)}> 的精灵。"
    if kind == "用户":
        # 1. 清空底层存储与三表数据 (wallet, accounts, groups)
        if hasattr(ST, "user_clear"):
            ST.user_clear(gid, t)
        else:
            a = _acct(gid, t)
            a.kv.clear()
            ST.acct_save(gid, t)
            _clear_money(gid, t)
        # 2. 清空奴隶与释放名下奴隶
        try:
            from engines import slave as _sl
            if hasattr(_sl, "clear_user_slave"):
                _sl.clear_user_slave(gid, t)
        except Exception:
            pass
        ST.flush_all()
        return f"已彻底清空 <{_name(t)}> 的所有数据（包含奴隶、精灵与礼包状态，可重新领取新手礼包）。"
    return "未知操作。"


# ---- 禁言/踢人(平台动作, 由 main._do_platform 执行) ----
def cmd_mute(gid, qq, arg):
    """禁言 @QQ 分钟  支持 @ 昵称"""
    arg = (arg or "").strip()
    # 先尝试统一 parse_at 解析 @ 昵称/数字
    target = None
    rest = arg
    try:
        import store as _ST
        t, r = _ST.parse_at(arg)
        if t:
            target = t
            rest = r
    except Exception:
        pass
    if target:
        # rest 含分钟
        import re as _re2
        m2 = _re2.search(r"(\d+)", rest)
        mins = int(m2.group(1)) if m2 else 0
        if not mins:
            return "格式：禁言 @QQ 分钟"
        if str(target) == str(qq):
            return "不能对自己执行禁言！"
        return "__XB_PLATFORM__|mute|%s|%d" % (target, mins * 60)
    m = re.match(r"@?\s*(\d{5,12})\s*(\d+)", arg)
    if not m:
        return "格式：禁言 @QQ 分钟"
    t, mins = m.group(1), int(m.group(2))
    if str(t) == str(qq):
        return "不能对自己执行禁言！"
    return "__XB_PLATFORM__|mute|%s|%d" % (t, mins * 60)


def cmd_kick(gid, qq, arg):
    """踢人 @QQ"""
    arg = (arg or "").strip()
    m = re.match(r"@?\s*(\d{5,12})", arg)
    if not m:
        return "格式：踢人 @QQ"
    t = m.group(1)
    if str(t) == str(qq):
        return "不能对自己执行踢人！"
    return "__XB_PLATFORM__|kick|%s|0" % t


def cmd_backup_xb():
    try:
        dst = ST.backup_user_data(force=True)
        if dst:
            # 脱敏：仅展示相对路径
            try:
                base = ST.BACKUP_DIR or ""
                rel = dst.replace(base, "").lstrip("/\\") if base else dst
            except Exception:
                rel = dst
            return f"备份成功：{rel}（已写入 backups）"
        return "备份失败（无数据或目录不可写）"
    except Exception as e:
        return f"备份异常：{e}"


def _maint_on():
    cur = dict(ST._CONFIG)
    cur.setdefault("维护配置", {})["维护开关"] = "真"
    ST.set_config(cur); ST.save_config(); ST.sync_astrbot_config(cur)
    return "已开启维护模式，仅超管可用。"

def _maint_off():
    cur = dict(ST._CONFIG)
    cur.setdefault("维护配置", {})["维护开关"] = "假"
    ST.set_config(cur); ST.save_config(); ST.sync_astrbot_config(cur)
    return "已关闭维护模式，恢复正常。"

def _maint_msg(msg):
    msg = (msg or "").strip()
    if not msg:
        return "格式：维护信息 内容"
    cur = dict(ST._CONFIG)
    cur.setdefault("维护配置", {})["维护信息"] = msg
    ST.set_config(cur); ST.save_config(); ST.sync_astrbot_config(cur)
    return f"已设置维护信息：{msg}"

def _version():
    try:
        import os, re
        base = os.path.dirname(os.path.abspath(__file__))
        ver = ""
        meta = os.path.join(base, "..", "metadata.yaml")
        if os.path.isfile(meta):
            try:
                with open(meta, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("version:"):
                            ver = line.split(":", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass
        if not ver:
            main_py = os.path.join(base, "..", "main.py")
            if os.path.isfile(main_py):
                try:
                    with open(main_py, "r", encoding="utf-8") as f:
                        m2 = re.search(r'PLUGIN_VERSION\s*=\s*["\']([^"\']+)["\']', f.read())
                        if m2:
                            ver = m2.group(1).strip()
                except Exception:
                    pass
        if not ver:
            ver = "0.68.17"
        return f"小白版本：{ver}"
    except Exception:
        return "小白版本：0.68.17"

# ---- 统一入口（测试指令仅超管，WebUI可配但不显示于MENU，已删 个人信息） ----
_ADMIN_CMDS = ("群列表", "应用统计", "扣钱", "充钱", "清空", "重置", "禁言", "踢人", "备份xb", "备份", "开启维护", "关闭维护", "维护信息", "测试testxb", "测试testxb1", "测试testxb2", "测试testxb3", "测试testxb4", "测试testxb5", "测试testxb6", "测试testxb7", "测试testxb8", "超管列表")


def handle(gid, qq, raw, is_admin=False):
    text = (raw or "").strip()
    if not text:
        return None
    # 允许所有人查询版本
    if text in ("小白版本", "版本", "xb版本", "插件版本"):
        return _version()
    # 允许所有人查询云端更新情况（只读无害，支持 更新/查询更新/检查更新/小白更新）
    if text in ("检查更新", "小白更新", "检查版本", "查询更新", "更新", "查看更新", "小白升级"):
        try:
            info = None
            try:
                from ..core.api import updater
                info = updater.check_latest_version()
            except Exception:
                try:
                    from core.api import updater
                    info = updater.check_latest_version()
                except Exception:
                    pass

            if info and info.get("has_update"):
                lat_v = info.get("latest_version")
                cur_v = info.get("current_version")
                name = info.get("release_name", "")
                return f"🚀 发现小白新版本【{lat_v}】(当前: {cur_v})\n🏷️ 发布信息: {name}\n💡 可前往 AstrBot 后台「插件管理」页面点击更新升级！"
            elif info:
                cur_v = info.get("current_version")
                lat_v = info.get("latest_version")
                return f"✅ 当前小白已是最新版本【{cur_v}】(云端最新: {lat_v})。"
            else:
                return _version()
        except Exception as e:
            return f"检查更新异常: {e}"

    if text in ST.wake("超管系统", "超管系统"):
        if not is_admin:
            return "亲亲,你没有相关权限哦~"
        return MENU
    if not is_admin:
        # 命中超管指令 -> 提醒无权限(而非静默)
        for c in _ADMIN_CMDS:
            if text.startswith(c):
                return "亲亲，你没有相关权限哦~该指令仅限机器人管理员使用！"
        return None
    if _cfg("开关", "真") != "真":
        return "【超管系统】已经被关闭了，无法使用该功能！"
    if text == "群列表":
        return cmd_groups()
    if text == "应用统计":
        return cmd_stats()
    if text.startswith("扣钱"):
        return cmd_deduct(gid, qq, text[2:].strip())
    if text.startswith("充钱"):
        return cmd_recharge(gid, qq, text[2:].strip())
    if text.startswith("清空") or text.startswith("重置"):
        return cmd_clear(gid, qq, text)
    if text.startswith("禁言"):
        return cmd_mute(gid, qq, text[2:].strip())
    if text.startswith("踢人"):
        return cmd_kick(gid, qq, text[2:].strip())
    if text in ("备份xb", "备份", "备份数据", "xb备份"):
        return cmd_backup_xb()
    if text.startswith("备份xb"):
        return cmd_backup_xb()
    if text in ("开启维护", "打开维护"):
        return _maint_on()
    if text in ("关闭维护", "关闭维护模式"):
        return _maint_off()
    if text.startswith("维护信息"):
        return _maint_msg(text[4:].strip())
    if text == "查看维护":
        sw = ST.cfg("维护配置", "维护开关", "假")
        msg = ST.cfg("维护配置", "维护信息", "🚧 维护中，仅超管可用，请稍后再试。")
        return f"维护开关：{sw}\r\n维护信息：{msg}"
    # 测试指令（WebUI 指令-超管系统可见，聊天不显示，仅 main._dispatch 处理）
    if text.startswith("测试testxb"):
        return None
    if text == "超管列表":
        return None
    return None
