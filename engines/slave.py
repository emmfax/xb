# -*- coding: utf-8 -*-
"""
[游戏模块 nuli_slave] 奴隶买卖 文本库
原文逐字提取自 nuli4.2.dll (小栗子版)
表情适配: 原版小栗子 [bqN] 已转换为 NapCat/OneBot11 的 [CQ:face,id=N]
(drea 主插件原生格式为 [DR:emoji,id=N], 如经 drea 转发需再映射)
"""

try:
    from .slave_text import *  # noqa: F401,F403
except ImportError:
    try:
        from slave_text import *  # type: ignore  # noqa: F401,F403
    except Exception:
        pass


# ============================================================
# 逻辑层 · 第1块: 路径/配置/钱包/存档/基础工具
# ============================================================
BOT_UIN = ""   # engine overwrites at runtime

import os as _os
import re as _re
import time as _time
import random as _random
import datetime as _dt
import threading as _threading

# Fix: extract constants
STAR_ATK = [100, 200, 400, 600, 800, 1600]  # 0-5星
MAX_PRICE = 1000000
_state_lock = _threading.RLock()
_CMD_LOCKS = {}
_CMD_LOCKS_GUARD = _threading.Lock()

def _cmd_lock(gid):
    with _CMD_LOCKS_GUARD:
        lk = _CMD_LOCKS.get(gid)
        if lk is None:
            lk = _threading.RLock()
            _CMD_LOCKS[gid] = lk
        return lk
_econ_lock = _threading.RLock()
import json as _json
try:
    from .. import store as ST
    store = ST
except ImportError:
    try:
        from . import store as ST
        store = ST
    except ImportError:
        import store as ST
        store = ST

_BASE    = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # 插件根
_ENG_DIR = _os.path.join(_BASE, "engines")

def _resolve_persistent_data_dir():
    if hasattr(store, "get_persistent_data_dir"):
        return store.get_persistent_data_dir(_BASE)
    return _os.path.join(_BASE, "data")

DATA_DIR = _resolve_persistent_data_dir()
GROUPS_DIR = _os.path.join(DATA_DIR, "groups")                     # 兼容旧目录(迁移用)
WALLET_DIR = _os.path.join(DATA_DIR, "wallet")                     # 兼容旧目录(迁移用)
DB_PATH = _os.path.join(DATA_DIR, "nuli_slave.db")                 # 现代存储(SQLite)
CONFIG_JSON = _os.path.join(DATA_DIR, "config.json")               # 现代配置(JSON)
GACHA_DIR = _os.path.join(DATA_DIR, "gacha_img")
EVENTS_JSON = _os.path.join(DATA_DIR, "events.json")

def cfg(sec, key, default=""):
    return store.cfg(sec, key, default)


def cfgi(sec, key, default=0):
    try:
        return int(float(cfg(sec, key, default)))
    except Exception:
        return default


def cfgf(sec, key, default=0.0):
    try:
        return float(cfg(sec, key, default))
    except Exception:
        return float(default)


def log(msg):
    ts = _time.strftime("%H:%M:%S")
    line = f"[{ts}] [奴隶买卖] {msg}"
    print(line, flush=True)


# ---- 钱包(现代: SQLite, UTF-8, 事务安全; 旧drea数据可经 store.import_drea_wallet 导入) ----
def coins_get(gid, qq):
    return store.coins_get(gid, qq)


def coins_add(gid, qq, delta):
    return store.coins_add(gid, qq, delta)


# ---- 存档(现代: store/SQLite) ----
def state(gid):
    return store.group(gid)


def save(gid):
    store.save_group(gid)


def save_all():
    try:
        store.flush_all()
    except Exception:
        pass


def U(st, qq):
    qq = str(qq)
    init_price = cfgi("费用配置", "初始身价", 500)
    if init_price <= 0:
        init_price = 500
    if not st.has_section(qq):
        st.add_section(qq)
        u = st[qq]
        u["price"] = str(init_price)
        u["owner"] = ""
        u["weapon"] = ""
        u["treasure"] = ""
        u["weapon_exp"] = "0"
        u["slave_slots"] = str(cfgi("设置", "奴隶个数", 2))
        u["protect_until"] = ""
        u["sign_date"] = ""
        u["consecutive_days"] = "0"
    else:
        u = st[qq]
        try:
            cur_p = int(u.get("price", "0") or 0)
            if cur_p <= 0:
                u["price"] = str(init_price)
                if hasattr(st, "mark_dirty"):
                    st.mark_dirty(qq)
        except Exception:
            u["price"] = str(init_price)
    return st[qq]


try:
    from ..core.en_map import cn_to_en as _cn2en
except ImportError:
    try:
        from core.en_map import cn_to_en as _cn2en  # type: ignore
    except Exception:
        def _cn2en(k): return k

def uget(u, k, d=""):
    return u.get(_cn2en(str(k)), d)


def uset(u, k, v):
    u[_cn2en(str(k))] = str(v)


# _napcat_port 已移除（napcat_http_port 配置已删）

_name_fail_until = [0.0]
_card_cache = {}
_CARD_TTL = 300.0
NOTE_NAMES = {}   # qq -> card/nickname (由适配层注入)
_KNOWN = {}       # gid -> set(qq) 记录本群出现过的成员(@目标/发送者/已开户), 用于判断"是否存在人"


def mark_known(gid, qq):
    """记录 qq 是本群已知成员(出现过/被@/开过户)"""
    try:
        gid = str(gid); qq = str(qq)
        if qq.isdigit():
            _KNOWN.setdefault(gid, set()).add(qq)
    except Exception:
        pass


def exists_user(gid, qq):
    """判断 qq 是否为该群真实存在的成员。
    判定依据(任一命中即存在): 已在本群出现过 / 在 NOTE_NAMES(事件名片) /
    真正开户(有主人/名字/签到/货币等实质数据)。
    只读, 不创建任何档案; 忽略 U() 自动补的空壳(仅默认 身价/主人=""/武器"" 等)。"""
    gid = str(gid); qq = str(qq)
    if not qq.isdigit():
        return False
    if qq == str(BOT_UIN):
        return True
    if _KNOWN.get(gid) and qq in _KNOWN[gid]:
        return True
    if qq in NOTE_NAMES:
        return True
    try:
        st = state(gid)
        if st is not None and st.has_section(qq):
            raw = dict(st[qq] or {})
            # 兼顾中英文键：落库已英文化，显示保持中文，故同时检查英文键
            for k in ("name", "owner", "sign_date", "total_sign_days", "cash_total", "stamina", "charm", "message_count", "protect_until", "purchase_time"):
                v = str(raw.get(k, "")).strip()
                # 跳过默认空主人与默认身价等空壳
                if v and not (k == "owner" and v == ""):
                    # 对 price 单独不算存在，避免 U() 默认 1000 误判
                    if k in ("cash_total", "stamina", "charm", "message_count"):
                        try:
                            if float(v) > 0:
                                return True
                        except Exception:
                            return True
                    else:
                        return True
            # 再查 DB 钱包/账户是否存在实质数据
            try:
                if store._DB is not None:
                    row = store._DB.execute("SELECT 1 FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone()
                    if row:
                        return True
                    row2 = store._DB.execute("SELECT 1 FROM accounts WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone()
                    if row2:
                        return True
            except Exception:
                pass
    except Exception:
        pass
    return bool(fetch_card(gid, qq))


def fetch_card(gid, qq):
    """仅使用 NOTE_NAMES 缓存（AstrBot 事件注入），已移除 NapCat 直连"""
    qq = str(qq)
    n = NOTE_NAMES.get(qq)
    if n:
        return n
    now = _time.time()
    ck = f"{gid}:{qq}"
    hit = _card_cache.get(ck)
    if hit and now - hit[0] < _CARD_TTL:
        return hit[1]
    if now < _name_fail_until[0]:
        return ""
    # 已移除 NapCat 直连（napcat_http_port 已删），仅走 NOTE_NAMES 缓存
    return ""


def uname(st, qq):
    u = U(st, qq)
    # 优先 NOTE_NAMES(由 _dispatch 实时同步的最新群昵称)，并回写到档案以持久化
    try:
        nm = NOTE_NAMES.get(str(qq), "")
        if nm and _re.sub(r"[\u3000\u3164\u200b\ufeff\u2800-\u28ff\s]", "", nm):
            if u.get("name", "") != nm:
                uset(u, "name", nm)
                try:
                    save(getattr(st, "_gid", "") or "")
                except Exception:
                    pass
            return nm
    except Exception:
        pass
    n = uget(u, "name")
    # 不可见字符昵称(空白/零宽)视为无名字
    if n and _re.sub(r"[\u3000\u3164\u200b\ufeff\u2800-\u28ff\s]", "", n):
        return n
    gid = getattr(st, "_gid", None) or ""
    if gid:
        card = fetch_card(gid, qq)
        if card and _re.sub(r"[\u3000\u3164\u200b\ufeff\u2800-\u28ff\s]", "", card):
            uset(u, "name", card)
            try:
                save(getattr(st, "_gid", gid))
            except Exception:
                pass
            return card
    return str(qq)


def slaves_of(st, qq):
    return [s for s in st.sections()
            if s.isdigit() and uget(st[s], "owner") == str(qq)]


def weapons_of(u):
    return [w for w in uget(u, "weapon").split("|") if w]


def treasures_of(u):
    return [t for t in uget(u, "treasure").split("|") if t]


def star_of(u, w):
    try:
        return int(uget(u, w + "升星", "0"))
    except Exception:
        return 0


def atk_of(st, qq):
    """武器攻击力: 鬼泪村正系成长表 100/200/400/600/800/1600"""
    u = U(st, qq)
    table = STAR_ATK
    total = 0
    for w in weapons_of(u):
        s = min(star_of(u, w), 5)
        total += table[s]
    return total


def battle_power(st, qq):
    """战斗力 = 主人奴隶身价之和 + 武器攻击力"""
    u = U(st, qq)
    p = int(uget(u, "price") or 0)
    for s in slaves_of(st, qq):
        p += int(uget(U(st, s), "price") or 0)
    return p + atk_of(st, qq)


def protected_until(u):
    v = cn_parse(uget(u, "protect_until"))
    return v if v is not None else 0


# ---- 原版中文时间格式 ----
def cn_parse(s):
    if not s:
        return None
    m = _re.match(r"(\d+)年(\d+)月(\d+)日(\d+)时(\d+)分(\d+)秒", str(s))
    if m:
        y, mo, d, h, mi, se = map(int, m.groups())
        try:
            # Validate date
            if not (1970 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31 and 0 <= h < 24 and 0 <= mi < 60 and 0 <= se < 60):
                return None
            return _dt.datetime(y, mo, d, h, mi, se).timestamp()
        except Exception:
            return None
    try:
        v = float(s)
        if v < 0 or v > 4102444800:
            return None
        return v
    except Exception:
        return None


def cn_fmt(ts):
    if not ts:
        return ""
    dt = _dt.datetime.fromtimestamp(ts)
    return dt.strftime("%Y年%m月%d日%H时%M分%S秒")


def cd_check(u, key, minutes_key):
    # Fix B7: check only, no write; caller commits on success
    minutes = cfgi("间隔配置", minutes_key, 30)
    last = cn_parse(uget(u, key))
    if last is None:
        return True, 0
    left = minutes * 60 - (_time.time() - last)
    if left > 0:
        return False, int(left / 60) + 1
    return True, 0

def cd_commit(u, key):
    uset(u, key, _dt.datetime.now().strftime("%Y年%m月%d日%H时%M分%S秒"))


def _event_delta():
    """奇遇变化量: 在[下限,上限]取有符号随机值后取绝对值, 保证为正且保留随机性"""
    lo = cfgi("费用配置", "变化下限", -1000)
    hi = cfgi("费用配置", "变化上限", 1000)
    if lo > hi:
        lo, hi = hi, lo
    return max(1, abs(_random.randint(lo, hi)))


# ============================================================
# 逻辑层 · 第2块: 经济与社交指令
# ============================================================
_AT = _re.compile(r"\[CQ:at,qq=(\d+)[^\]]*\]")
_NUM = _re.compile(r"(\d+)\s*$")


def _fmt(mins, act):
    return T.COOLDOWN_MIN.format(min=mins, act=act)


def cmd_menu():
    return T.MENU


def cmd_myinfo(gid, qq, st):
    if BOT_UIN and str(qq) == str(BOT_UIN):
        return T.BOT_NO_JOIN
    u = U(st, qq)
    coins = coins_get(gid, qq)
    price = int(uget(u, "price") or 0)
    owner = uget(u, "owner")
    prot = protected_until(u)
    if prot and prot > _time.time():
        ptxt = f"🛡️{int((prot-_time.time())/60)}分"
    else:
        ptxt = T.NO_PROTECT
    sign_total, sign_streak = _sign_info(gid, qq, st)
    wexp = int(uget(u, "weapon_exp", "0") or 0)
    slaves = slaves_of(st, qq)
    cap = int(uget(u, "slave_slots", str(cfgi("设置", "奴隶个数", 2))) or 2)
    sl_txt = ", ".join(uname(st, s) for s in slaves) or T.NO_SLAVE
    w_list = weapons_of(u)
    t_list = treasures_of(u)
    acct = store.acct(gid, qq)
    dep = acct.int("deposit")
    tili = acct.int("stamina")
    meili = acct.int("charm")
    jq = acct.int("lottery_tickets")
    lines = [
        f"📋【{uname(st,qq)}】的档案",
        f"💰资产：{coins}{coin_name()}｜🏦存款：{dep}｜💎身价：{price}",
        f"🔋体力：{tili}｜💄魅力：{meili}｜🎫奖券：{jq}｜📖经验：{wexp}",
        f"👑主人：{uname(st, owner) if owner else T.NO_OWNER}｜{ptxt}｜📅总签{sign_total}·连签{sign_streak}天",
        f"⚔️武器：{', '.join(f'{w}★{star_of(u,w)}' for w in w_list) if w_list else T.NO_WEAPON}",
        f"🎁宝物：{', '.join(t_list) if t_list else T.NO_TREASURE}",
        f"👥奴隶({len(slaves)}/{cap})：{sl_txt}",
    ]
    return "\r\n".join(lines)


def coin_name():
    return cfg("设置", "货币名称", "金币")


def _ymd(dtobj):
    return f"{dtobj.year}年{dtobj.month}月{dtobj.day}日"


def _sign_info(gid, qq, st):
    """总签/连签: 完全本地(不依赖drea) —— 总签与连签双向打通 sign 与 slave 存储"""
    u = U(st, qq)
    acct = ST.acct(gid, qq)
    today = _dt.date.today()
    today_s = _ymd(today)
    
    # 优先从 Acct(sign 引擎) 和 Group(slave 引擎) 取最大值，兼容新旧库
    total = max(
        int(uget(u, "total_sign_days", "0") or 0),
        acct.int("sign_count"),
        acct.int("total_sign_days")
    )
    streak = max(
        int(uget(u, "shadow_streak", "0") or 0),
        acct.int("consecutive_days"),
        int(uget(u, "consecutive_days", "0") or 0)
    )
    seen = uget(u, "shadow_date") or acct.get("last_sign_date")
    
    # 检查是否今日已签到
    is_signed_today = (
        uget(u, "last_sign") == today.isoformat() or
        acct.get("sign_date") == today.isoformat() or
        acct.get("last_sign_date") == today.isoformat()
    )
    
    if is_signed_today:
        if seen != today_s and seen != today.isoformat():
            yest_s = _ymd(today - _dt.timedelta(days=1))
            yest_iso = (today - _dt.timedelta(days=1)).isoformat()
            streak = (streak + 1) if (seen == yest_s or seen == yest_iso) else max(streak, 1)
            uset(u, "shadow_streak", str(streak))
            uset(u, "shadow_date", today_s)
            acct.set("consecutive_days", str(streak))
            acct.set("last_sign_date", today.isoformat())
            ST.acct_save(gid, qq)
        return total, max(streak, 1)
    
    # 非今日签到
    return total, streak


def cmd_query(gid, qq, target, st):
    if not target:
        return T.QUERY_WHO
    if BOT_UIN and str(target) == str(BOT_UIN):
        return T.BOT_NO_JOIN
    if not st.has_section(str(target)):
        return "Ta还没加入本群的游戏哦~"
    return cmd_myinfo(gid, target, st)


def cmd_compensate(gid, qq, target, amount, st):
    if not target:
        return T.COMP_WHO
    if str(target) == qq:
        return "自己给自己补偿好玩吗！？"
    if amount <= 0:
        return T.COMP_WHO
    limit = cfgi("费用配置", "打赏上限", 10000)
    if amount > limit:
        return f"单次补偿最多 {limit}{coin_name()} 哦~"
    if coins_get(gid, qq) < amount:
        return T.POOR.format(coin=coin_name())
    coins_add(gid, qq, -amount)
    coins_add(gid, target, amount)
    return f"[{uname(st,qq)}] 补偿了 [{uname(st,target)}] {amount}{coin_name()}"


def cmd_buy_slave(gid, qq, target, st):
    if not target:
        return T.BUY_WHO
    tid = str(target)
    if tid == qq:
        return T.SELF_OP_WEIRD
    if BOT_UIN and tid == str(BOT_UIN):
        return T.BOT_NO_TRADE
    if not exists_user(gid, tid):
        return T.NOT_IN_GROUP
    buyer, tgt = U(st, qq), U(st, tid)
    if uget(tgt, "owner") == qq:
        return T.BUY_IS_MINE
    if uget(buyer, "owner") == tid:
        return T.SELF_BUY_SELF
    prev_owner = uget(tgt, "owner")
    if BOT_UIN and prev_owner == str(BOT_UIN):
        return T.BOT_NO_TRADE
    if _time.time() < protected_until(tgt):
        left = int((protected_until(tgt) - _time.time()) / 60) + 1
        prot_qq = uget(tgt, "protector")
        if prot_qq and st.has_section(prot_qq):
            return T.BUY_PROTECTED.format(who=uname(st, prot_qq), min=left)
        return T.PROTECTED_CANNOT_BUY.format(min=left)
    slots = int(uget(buyer, "slave_slots", str(cfgi("设置", "奴隶个数", 2))))
    mine = slaves_of(st, qq)
    if len(mine) >= slots:
        return T.BUY_SLOT_FULL.format(cap=slots)
    price = int(uget(tgt, "price") or 0)
    if coins_get(gid, qq) < price:
        return T.BUY_COST.format(cost=price) + "\r\n" + T.POOR.format(coin=coin_name())
    # 原版有"刚刚被交易过恢复情绪"判定, 用购买时间近似
    last_trade = cn_parse(uget(tgt, "purchase_time"))
    iv = cfgi("间隔配置", "购买间隔", 1)
    if last_trade and _time.time() - last_trade < iv * 60:
        left = int(iv - (_time.time() - last_trade) / 60) + 1
        return T.BUY_JUST_TRADED.format(min=left)
    tax = cfgf("设置", "税率", 0.1)
    coins_add(gid, qq, -price)
    tax_amount = int(price * tax)
    profit = price - tax_amount
    if prev_owner:
        coins_add(gid, prev_owner, profit)
        orig = int(uget(tgt, "purchase_price") or price)
    else:
        profit = 0
        orig = price
    uset(tgt, "owner", qq)
    uset(tgt, "purchase_price", str(price))
    uset(tgt, "purchase_time", _dt.datetime.now().strftime("%Y年%m月%d日%H时%M分%S秒"))
    uset(tgt, "_work_wage", "")
    newp = min(1000000, int(price * 1.25))
    uset(tgt, "price", str(newp))
    tn = uname(st, tid)
    head = T.BUY_OK_HEAD.format(who=tn)
    lines = [
        T.BUY_COST.format(cost=price),
        T.BUY_PRICE_UP.format(up=newp - price),
        T.BUY_PRICE_NOW.format(now=newp),
    ]
    if prev_owner:
        pon = uname(st, prev_owner)
        lines += [
            T.BUY_PREV_OWNER.format(prev=pon),
            T.BUY_PREV_COST.format(orig=orig),
            T.BUY_TAX.format(tax=tax_amount),
            T.BUY_PREV_PROFIT.format(profit=profit),
        ]
    return head + "\r\n" + "\r\n".join(lines)


def cmd_torture(gid, qq, target, st):
    if not target:
        return T.TORTURE_WHO
    tid = str(target)
    if tid == qq:
        return T.TORTURE_SELF
    s = U(st, tid)
    if uget(s, "owner") != qq:
        return T.TORTURE_NOT_MINE
    last_tor = cn_parse(uget(s, "tortured_time"))
    if last_tor and _time.time() - last_tor < 300:
        return T.TORTURE_JUST
    my_slaves = slaves_of(st, qq)
    ok, mins = cd_check(U(st, qq), "torture_time", "折磨间隔")
    if not ok:
        return _fmt(mins, "折磨")
    if not my_slaves:
        return T.TORTURE_ALL_DONE
    sc = coins_get(gid, tid)
    cd_commit(U(st, qq), "torture_time")
    if _random.randint(1, 100) <= 20:
        return T.TORTURE_MERCY
    evs = [e for e in EVENTS if e.get("type", "").startswith("折磨")]
    if not evs:
        take = min(sc, _random.randint(20, 100))
        coins_add(gid, tid, -take)
        coins_add(gid, qq, take // 2)
        uset(s, "tortured_time", cn_fmt(_time.time()))
        return f"折磨了 [{uname(st,tid)}], 掠夺 {take}"
    up_pool = [e for e in evs if e.get("effect") == "主人货币上涨"]
    down_pool = [e for e in evs if e.get("effect") == "主人货币下跌"]
    sup_pool = [e for e in evs if e.get("effect") == "奴隶货币上涨"]
    sdown_pool = [e for e in evs if e.get("effect") == "奴隶货币下跌"]
    parts = []
    if up_pool and _random.random() < 0.6:
        ev = _random.choice(up_pool)
        amt = _event_delta()
        coins_add(gid, qq, amt)
        parts.append(T.EVENT_MASTER_UP.format(text=ev.get("text", ""), amt=amt))
    elif down_pool and _random.random() < 0.3:
        ev = _random.choice(down_pool)
        amt = min(coins_get(gid, qq), _random.randint(50, 500))
        if amt > 0:
            coins_add(gid, qq, -amt)
            parts.append(T.EVENT_MASTER_DOWN.format(text=ev.get("text", ""), amt=amt))
    if sup_pool and _random.random() < 0.35:
        ev = _random.choice(sup_pool)
        amt = _random.randint(30, 300)
        coins_add(gid, tid, amt)
        parts.append(T.EVENT_SLAVE_UP.format(text=ev.get("text", ""), amt=amt))
    elif sdown_pool and _random.random() < 0.5:
        ev = _random.choice(sdown_pool)
        amt = min(sc, _random.randint(30, 400))
        if amt > 0:
            coins_add(gid, tid, -amt)
            parts.append(T.EVENT_SLAVE_DOWN.format(text=ev.get("text", ""), amt=amt))
    if not parts:
        return T.TORTURE_MERCY
    uset(s, "tortured_time", cn_fmt(_time.time()))
    sn = uname(st, tid)
    parts.insert(0, f"你对 [{sn}] 实施了折磨...")
    return "\r\n".join(parts)


def cmd_protect(gid, qq, target, st):
    if not target:
        return T.PROTECT_WHO
    tid = str(target)
    if tid == str(qq):
        return T.SELF_OP_WEIRD
    if BOT_UIN and tid == str(BOT_UIN):
        return T.BOT_NO_TRADE
    u = U(st, tid)
    if uget(u, "owner") != qq:
        return T.PROTECT_NOT_YOURS
    if _time.time() < protected_until(u):
        left = int((protected_until(u) - _time.time())/60)+1
        return T.ALREADY_PROTECTED_BY_YOU.format(min=left)
    ok, mins = cd_check(U(st, qq), "protect_time", "保护间隔")
    if not ok:
        return _fmt(mins, "保护")
    hours = cfgf("设置", "保护时长小时", 12)
    fee = cfgi("设置", "保护费用", 1000)
    if coins_get(gid, qq) < fee:
        return T.PROTECT_POOR.format(coin=coin_name())
    coins_add(gid, qq, -fee)
    until = _time.time() + hours * 3600
    uset(u, "protect_until", _dt.datetime.fromtimestamp(until).strftime("%Y年%m月%d日%H时%M分%S秒"))
    uset(u, "protector", qq)
    cd_commit(U(st, qq), "protect_time")
    mins = int(hours * 60)
    who = uname(st, tid)
    return T.PROTECT_OK.format(cost=fee, coin=coin_name(), who=who, min=mins)


def cmd_release(gid, qq, target, st):
    if not target:
        return T.RELEASE_WHO
    tid = str(target)
    if tid == qq:
        return T.SELF_RELEASE
    s = U(st, tid)
    if uget(s, "owner") != qq:
        return "不是你的奴隶，你无法释放Ta！"
    uset(s, "owner", "")
    uset(s, "protect_until", "")
    uset(s, "protector", "")
    return T.RELEASE_OK.format(who=uname(st, tid))


def cmd_ransom(gid, qq, target, st):
    """赎身@QQ: 帮别人的奴隶向其主人支付身价, 让TA自由"""
    if not target:
        return T.RANSOM_WHO
    tid = str(target)
    s = U(st, tid)
    owner = uget(s, "owner")
    if not owner:
        return T.RANSOM_TA_FREE
    if owner == qq:
        return T.RANSOM_OWN_SLAVE
    last_r = cn_parse(uget(s, "赎身时间"))
    iv_r = cfgi("间隔配置", "赎身间隔", 30)
    if last_r and _time.time() - last_r < iv_r * 60:
        left = int((iv_r * 60 - (_time.time() - last_r)) / 60) + 1
        return T.RANSOM_CD.format(min=left)
    price = int(int(uget(s, "price") or 0) * 1.5)
    if coins_get(gid, qq) < price:
        return T.POOR.format(coin=coin_name()) + f"(需{price})"
    coins_add(gid, qq, -price)
    coins_add(gid, owner, price)
    uset(s, "owner", "")
    uset(s, "赎身时间", cn_fmt(_time.time()))
    return f"[{uname(st,qq)}] 大发善心，花费{price}为 [{uname(st,tid)}] 赎身，Ta已恢复自由！"


def cmd_freedom(gid, qq, st):
    u = U(st, qq)
    owner = uget(u, "owner")
    if not owner:
        return T.RANSOM_NO_OWNER
    last_f = cn_parse(uget(u, "自由时间"))
    iv_f = cfgi("间隔配置", "自由间隔", 30)
    if last_f and _time.time() - last_f < iv_f * 60:
        left = int((iv_f * 60 - (_time.time() - last_f)) / 60) + 1
        return T.FREE_CD.format(min=left)
    price = int(int(uget(u, "price") or 0) * 1.5)
    have = coins_get(gid, qq)
    if have < price:
        return (T.FREE_BY_TORTURE.format(cost=price) + "\r\n" + T.FREE_FAIL_PAY
                + f"\r\n(还差 {price - have} 金币)")
    coins_add(gid, qq, -price)
    coins_add(gid, owner, price)
    uset(u, "owner", "")
    uset(u, "自由时间", cn_fmt(_time.time()))
    return T.FREE_KIND.format(cost=price) + "\r\n换取自由！"


def cmd_rename(gid, qq, target, newname, st):
    return "起名功能已下线，请使用系统默认昵称。"


def cmd_buyslot(gid, qq, st):
    u = U(st, qq)
    cur = int(uget(u, "slave_slots", str(cfgi("设置", "奴隶个数", 2))))
    cap = cfgi("设置", "奴隶个数上限", 8)
    if cur >= cap:
        return T.SLOT_SYS_MAX
    base_price = cfgi("设置", "奴隶位价格", 59999)
    base_cap = cfgi("设置", "奴隶个数", 2)
    price = int(base_price * (2 ** max(0, cur - base_cap)))
    if coins_get(gid, qq) < price:
        return (T.SLOT_NEED.format(price=price) + "\r\n" +
                T.SLOT_POOR.format(coin=coin_name()))
    coins_add(gid, qq, -price)
    uset(u, "slave_slots", str(cur + 1))
    return ("\r\n".join([
        f"恭喜您花费{price}{coin_name()}",
        T.SLOT_BUY_ONE,
        T.SLOT_NOW_CAP.format(cap=cur + 1),
        T.SLOT_NEXT_PRICE.format(price=int(price * 2)),
    ]))


EVENTS = []


def load_events():
    global EVENTS
    try:
        EVENTS = _json.load(open(EVENTS_JSON, encoding="utf-8"))
    except Exception:
        EVENTS = []

load_events()

# ============================================================
# 文本命名空间绑定(T.引用 -> 本模块大写常量)
# ============================================================
import types as _types
_tmap = {k: v for k, v in dict(globals()).items() if k.isupper() and not k.startswith("_")}
for _k2, _v2 in list(_tmap.items()):
    if _k2.startswith("T_"):
        _tmap.setdefault(_k2[2:], _v2)
T = _types.SimpleNamespace(**_tmap)


# ============================================================
# 逻辑层 · 第4块: 讨好/学习奇遇/祈福
# ============================================================
def cmd_flatter(gid, qq, st):
    u = U(st, qq)
    owner = uget(u, "owner")
    if not owner:
        return T.FLATTER_NO_OWNER
    ok, mins = cd_check(u, "flatter_time", "讨好间隔")
    if not ok:
        return _fmt(mins, "讨好主人")
    if int(uget(u, "price") or 0) > int(U(st, owner).get("price") or 0):
        return T.FLATTER_RICHER
    mc = coins_get(gid, owner)
    if mc <= 0:
        return T.FLATTER_POOR_M
    if _random.randint(1, 100) <= cfgi("概率配置", "讨好概率", 60):
        got = _random.randint(50, max(50, min(mc, 500)))
        got = min(got, mc)
        coins_add(gid, owner, -got)
        cd_commit(u, "flatter_time")
        coins_add(gid, qq, got)
        return T.FLATTER_OK.format(got=got)
    return "你各种撒娇打泼，主人仍不为所动，你什么都没有讨到~"


def _grant_treasure(gid, qq, st):
    treas = [t for t in (cfg("设置", "treasure", "") or "").split("|") if t]
    if not treas:
        return None
    t = _random.choice(treas)
    u = U(st, qq)
    uset(u, t, str(int(uget(u, t, "0")) + 1))
    # Fix N-C03: maintain 宝物 list
    lst = treasures_of(u)
    if t not in lst:
        lst.append(t)
        uset(u, "treasure", "|".join(lst))
    return t


def cmd_study(gid, qq, st):
    u = U(st, qq)
    owner = uget(u, "owner")
    ok, mins = cd_check(u, "study_time", "学习间隔")
    if not ok:
        return _fmt(mins, "学习")
    fee = _random.randint(100, 800)
    if owner:
        oc = coins_get(gid, owner)
        if oc < fee:
            return T.STUDY_POOR_MASTER.format(fee=fee)
    # 学费由主人支付(原版机制); 无主者自付
    payer = owner if owner else qq
    coins_add(gid, payer, -fee)
    exp_gain = _random.randint(20, 150)
    uset(u, "weapon_exp", str(int(uget(u, "weapon_exp", "0") or 0) + exp_gain))
    cd_commit(u, "study_time")
    head = f"缴纳学费 {fee} 后开始学习! 武器经验 +{exp_gain}"
    # 奇遇事件: 学习类剧情 + 概率获得宝物
    evs = [e for e in EVENTS if e.get("type") == "学习"]
    tail = ""
    if evs:
        ev = _random.choice(evs)
        content = ev.get("text", "")
        effect = ev.get("effect", "")
        delta = _event_delta()
        if "上涨" in effect:
            newp = min(MAX_PRICE, int(uget(u, "price") or 0) + delta)
            uset(u, "price", str(newp))
            tail = f"\r\n🍀奇遇: {content}\r\n奴隶身价上涨 {delta}"
        elif "下跌" in effect:
            cur_p = int(uget(u, "price") or 0)
            if cur_p <= cfgi("费用配置", "初始身价", 1000):
                newp = min(MAX_PRICE, cur_p + delta)
                uset(u, "price", str(newp))
                tail = (f"\r\n🍀奇遇: {content}\r\n"
                        f"因为你的身价过低触发系统双倍保护，奴隶身价上涨 {newp - cur_p}")
            else:
                newp = max(100, cur_p - delta)
                uset(u, "price", str(newp))
                tail = f"\r\n🍀奇遇: {content}\r\n奴隶身价下跌 {delta}"
        else:
            tail = f"\r\n🍀奇遇: {content}"
    # 奇遇触发概率 -> 额外获得宝物
    if _random.randint(1, 100) <= cfgi("设置", "奇遇触发概率", 6):
        t = _grant_treasure(gid, qq, st)
        if t:
            tail += f"\r\n🎁 奇遇事件中获得宝物【{t}】!"
    return head + tail


def cmd_pray(gid, qq, st):
    """祭拜忍神: 每天12点后可祈福一次"""
    u = U(st, qq)
    now = _dt.datetime.now()
    today = now.strftime("%Y-%m-%d")
    if now.hour < 12:
        return T.PRAY_TIME_NOTYET
    if uget(u, "pray_date") == today:
        return "今天已经祭拜过忍神了, 明天中午12点再来~"
    uset(u, "pray_date", today)
    name = uname(st, qq)
    cn = coin_name()
    if _random.randint(1, 100) <= cfgi("祈福配置", "人品爆发概率", 5):
        amt = cfgi("祈福配置", "人品爆发奖励", 99999)
        coins_add(gid, qq, amt)
        return T.PRAY_BIG.format(amt=f"{amt}{cn}") + f"\r\n[{name}] 获得 {amt} {cn}!!"
    if _random.randint(1, 100) <= 25:
        lose = min(coins_get(gid, qq), _random.randint(50, 300))
        coins_add(gid, qq, -lose)
        return (T.PRAY_PITY_HEAD.format(who=f"[{name}]")
                + f"\r\n被顺走了 {lose} {cn}...")
    lo = cfgi("祈福配置", "祈福奖励下限", 666)
    hi = cfgi("祈福配置", "祈福奖励上限", 19999)
    if _random.randint(1, 100) <= 30:
        amt = _random.randint(lo, hi)
        coins_add(gid, qq, amt)
        return T.PRAY_NINJA.format(who=f"[{name}]", amt=f"{amt}{cn}")
    amt = _random.randint(max(lo // 2, 10), max(hi // 4, 100))
    coins_add(gid, qq, amt)
    return T.PRAY_NORMAL.format(who=f"[{name}]", amt=f"{amt}{cn}")


# ============================================================
# 逻辑层 · 第5块: 打工两段式 / 造反剧情线
# ============================================================
def cmd_work_dispatch(gid, qq, st):
    u = U(st, qq)
    my = slaves_of(st, qq)
    if not my:
        return T.WORK_NO_SLAVE
    if uget(u, "work_status") == "真":
        started = cn_parse(uget(u, "work_time")) or 0
        duration = cfgi("间隔配置", "打工间隔", 30) * 60
        left = started + duration - _time.time()
        if left > 0:
            return T.WORK_WORKING.format(min=int(left / 60) + 1)
        uset(u, "work_status", "")   # 超时自动收工
    duration = cfgi("间隔配置", "打工间隔", 30)
    target = 0
    for s in my:
        su = U(st, s)
        w = _random.randint(100, 500) + int(uget(su, "price") or 0) // 50
        uset(su, "_work_wage", str(w))
        target += w
    uset(u, "work_status", "真")
    uset(u, "work_time", cn_fmt(_time.time()))
    uset(u, "work_wage", str(target))
    return T.WORK_DISPATCH.format(target=target, min=duration)


def cmd_work_collect(gid, qq, st):
    u = U(st, qq)
    my = slaves_of(st, qq)
    if not my:
        return T.WORK_NO_SLAVE
    if uget(u, "work_status") != "真":
        return T.WORK_NOT_STARTED
    started = cn_parse(uget(u, "work_time")) or 0
    duration = cfgi("间隔配置", "打工间隔", 30) * 60
    left = started + duration - _time.time()
    if left > 0:
        return T.WORK_WAIT.format(min=int(left / 60) + 1)

    ratio = cfgi("费用配置", "工资比例", 50)
    tax = cfgf("设置", "税率", 0.1)
    total = int(uget(u, "work_wage") or 0)
    lines = [T.WORK_COLLECT.format(total=total)]
    wage_paid = 0
    for s in my:
        su = U(st, s)
        wage = int(uget(su, "_work_wage") or 0)
        if int(uget(su, "price") or 0) < 100:
            lines.append(f"[{uname(st,s)}]{T.WORK_NO_WAGE}")
            continue
        got = wage * ratio // 100
        coins_add(gid, s, got)
        wage_paid += got
        lines.append(f"[{uname(st,s)}]{T.WORK_GOT_WAGE.format(wage=got)}")
        uset(su, "_work_wage", "")
    master_net = int(total * (1 - tax)) - wage_paid
    if master_net > 0:
        coins_add(gid, qq, master_net)
    uset(u, "work_status", "")
    uset(u, "work_time", "")
    lines.append(T.WORK_WAGE_TOTAL.format(wage=wage_paid))
    lines.append(T.WORK_TAX_TOTAL.format(tax=int(total * tax)))
    lines.append(T.WORK_MASTER_GET.format(got=max(0, master_net)))
    return "\r\n".join(lines)


def cmd_revolt(gid, qq, st):
    u = U(st, qq)
    owner = uget(u, "owner")
    if not owner:
        return T.REVOLT_NO_OWNER
    ok, mins = cd_check(u, "造反时间", "造反间隔")
    if not ok:
        return _fmt(mins, "造反")
    need = max(500, int(uget(u, "price") or 0) // 10)
    if coins_get(gid, qq) < need:
        return T.REVOLT_TOO_POOR.format(need=need)
    cd_commit(u, "造反时间")
    # 主人奴隶数量是我方两倍 -> 镇压
    m_slaves = len(slaves_of(st, owner))
    my_power = battle_power(st, qq)
    om_power = battle_power(st, owner)
    if m_slaves >= 2 * max(1, len(slaves_of(st, qq))) and om_power > my_power:
        fine = min(coins_get(gid, qq), 500)
        coins_add(gid, qq, -fine)
        coins_add(gid, owner, fine)
        return T.REVOLT_CRUSHED + f"(被罚{fine})"
    sn = uget(u, "name") or (str(qq))
    loot = min(coins_get(gid, owner), _random.randint(500, 5000))

    i_have_gourd = "酒神葫芦" in treasures_of(u)
    master_has_gourd = "酒神葫芦" in treasures_of(U(st, owner))

    if i_have_gourd:
        uset(u, "owner", "")
        uset(u, "protect_until", "")
        uset(u, "protector", "")
        coins_add(gid, owner, -loot)
        coins_add(gid, qq, loot)
        return (T.RV_GOURD_WIN + "\r\n" + T.RV_LOOT.format(loot=loot, coin=coin_name())
                + "\r\n" + T.REVOLT_FREE.replace("，", ""))
    if master_has_gourd:
        pay = min(coins_get(gid, qq), loot)
        coins_add(gid, qq, -pay)
        coins_add(gid, owner, pay)
        return T.RV_GOURD_LOSE + f"({pay}{coin_name()})\r\n" + T.REVOLT_FAIL_STAY
    if _random.randint(1, 100) <= cfgi("概率配置", "造反概率", 40):
        uset(u, "owner", "")
        uset(u, "protect_until", "")
        uset(u, "protector", "")
        coins_add(gid, owner, -loot)
        coins_add(gid, qq, loot)
        return (T.RV_NORMAL_WIN + f"\r\n[{sn}] " + T.RV_LOOT.format(loot=loot, coin=coin_name())
                + "\r\n" + T.REVOLT_FREE.replace("，", ""))
    pay = min(coins_get(gid, qq), 500)
    coins_add(gid, qq, -pay)
    coins_add(gid, owner, pay)
    return (T.RV_NORMAL_LOSE + f"(罚{pay}{coin_name()})\r\n"
            + f"[{sn}]" + T.REVOLT_FAIL_STAY)


# ============================================================
# 逻辑层 · 第6块: 奴隶群战 / 抽卡 / 升星 / 升阶
# ============================================================
_GACHA_CACHE = {}
_GACHA_CACHE_TS = {}  # 分 rar 独立 TTL，避免 SSR 刷新污染 R
_GACHA_TTL = 60.0  # 60s 刷新，千群每消息 listdir 1507次→0次

def _gacha_pool(rar):
    now = _time.time()
    hit = _GACHA_CACHE.get(rar)
    ts = _GACHA_CACHE_TS.get(rar, 0)
    if hit is not None and now - ts < _GACHA_TTL and len(hit) > 0:
        return hit
    # 优先使用持久化数据目录，若无则回退至插件内置图库
    dd = _os.path.join(DATA_DIR, "gacha_img", rar)
    if not _os.path.isdir(dd) or not _os.listdir(dd):
        dd = _os.path.join(_BASE, "data", "gacha_img", rar)
    try:
        lst = [_os.path.join(dd, f) for f in sorted(_os.listdir(dd)) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))]
    except Exception:
        lst = []
    _GACHA_CACHE[rar] = lst
    _GACHA_CACHE_TS[rar] = now
    return lst


def cmd_fight(gid, qq, target, st):
    if not target:
        return T.FIGHT_WHO
    tid = str(target)
    if tid == str(qq):
        return T.SELF_FIGHT if hasattr(T, "SELF_FIGHT") else "\u4e0d\u80fd\u548c\u81ea\u5df1\u6253\u67b6\u54e6\uff5e"
    a_slaves = slaves_of(st, qq)
    d_slaves = slaves_of(st, tid)

    if tid == uget(U(st, qq), "owner"):
        return T.FIGHT_MASTER
    if tid in a_slaves:
        return T.FIGHT_OWN_SLAVE
    if not a_slaves:
        return T.FIGHT_NO_SLAVE
    if not d_slaves:
        return T.FIGHT_ENEMY_NO_S
    rest = cn_parse(uget(U(st, tid), "战斗恢复时间"))
    iv_rest = cfgi("间隔配置", "打架间隔", 20)
    if rest and _time.time() - rest < iv_rest * 60:
        left = int((iv_rest * 60 - (_time.time() - rest)) / 60) + 1
        return T.FIGHT_RESTING.format(min=left)

    my_p = battle_power(st, qq)
    ta_p = battle_power(st, tid)
    if my_p >= ta_p * 3:
        return T.FIGHT_TOO_STRONG

    ca, cdd = coins_get(gid, qq), coins_get(gid, tid)
    stake = min(int(ca * 0.1), int(cdd * 0.1), 50000)
    if stake <= 0:
        if ca < 100:
            return T.FIGHT_I_AM_POOR.replace("@", "")
        return T.FIGHT_TA_IS_POOR

    ok, mins = cd_check(U(st, qq), "打架时间", "打架间隔")
    if not ok:
        return _fmt(mins, "打架")
    cd_commit(U(st, qq), "打架时间")
    now_fmt = cn_fmt(_time.time())
    uset(U(st, qq), "战斗恢复时间", now_fmt)
    uset(U(st, tid), "战斗恢复时间", now_fmt)

    # 5星武器狂热: 每把5星+10%概率战力翻倍
    crit = False
    five = sum(1 for w in weapons_of(U(st, qq)) if star_of(U(st, qq), w) >= 5)
    if five and _random.randint(1, 100) <= five * 10:
        crit = True
        my_p *= 2

    lines = [T.FIGHT_HEAD,
             T.FIGHT_CALL_UP.format(who="[" + (U(st, tid).get("name") or str(tid)) + "]"),
             T.FIGHT_MY_TEAM.format(team=", ".join(uname(st, s) for s in a_slaves))]
    if crit:
        lines.append(T.FIGHT_CRIT)
    lines.append(T.FIGHT_ENEMY_TEAM.format(team=", ".join(uname(st, s) for s in d_slaves)))
    lines.append(T.FIGHT_POWER_CMP.format(a=my_p, b=ta_p))

    pwin = my_p / (my_p + ta_p)
    lines.append(T.FIGHT_WINRATE.format(pct=int(pwin * 100)))
    win = _random.random() < pwin

    def _shield(owner_q):
        return "四象护符" in treasures_of(U(st, owner_q))

    if win:
        lines.append(T.FIGHT_WIN)
        free_slot = len(slaves_of(st, qq)) < int(uget(U(st, qq), "slave_slots",
                                                  str(cfgi("设置", "奴隶个数", 2))))
        stealable = [s for s in d_slaves]
        if stealable and free_slot:
            if _shield(tid):
                victim = _random.choice(stealable)
                lines.append(T.FIGHT_TA_TREASURE)
                lines.append("[" + uname(st, victim) + "]" + T.FIGHT_TA_SHIELD)
            else:
                victim = _random.choice(stealable)
                uset(U(st, victim), "owner", qq)
                uset(U(st, victim), "purchase_price", str(int(uget(U(st, victim), "price") or 0)))
                uset(U(st, victim), "purchase_time", cn_fmt(_time.time()))
                uset(U(st, victim), "_work_wage", "")
                newp = min(1000000, int(int(uget(U(st, victim), "price") or 0) * 1.25))
                uset(U(st, victim), "price", str(newp))
                lines.append(T.FIGHT_GET_SLAVE.format(slave="[" + uname(st, victim) + "]"))
        elif stealable:
            ransom = min(cdd, stake)
            coins_add(gid, tid, -ransom)
            coins_add(gid, qq, ransom)
            lines.append(T.FIGHT_SLOT_FULL.format(money=ransom))
        else:
            # Fix B4: no slave stealable -> single money payout
            pay = min(cdd, stake)
            if pay > 0:
                coins_add(gid, tid, -pay)
                coins_add(gid, qq, pay)
                lines.append(T.FIGHT_GET_MONEY.format(money=pay))
    else:
        lines.append(T.FIGHT_LOSE)
        shield = _shield(qq)
        stealable = [s for s in a_slaves]
        if stealable and not shield:
            free_t = len(slaves_of(st, tid)) < int(uget(U(st, tid), "slave_slots",
                                                   str(cfgi("设置", "奴隶个数", 2))))
            if free_t:
                victim = _random.choice(stealable)
                uset(U(st, victim), "owner", tid)
                uset(U(st, victim), "purchase_price", str(int(uget(U(st, victim), "price") or 0)))
                uset(U(st, victim), "purchase_time", cn_fmt(_time.time()))
                uset(U(st, victim), "_work_wage", "")
                newp = min(1000000, int(int(uget(U(st, victim), "price") or 0) * 1.25))
                uset(U(st, victim), "price", str(newp))
                lines.append(T.FIGHT_LOSE_SLAVE.format(slave="[" + uname(st, victim) + "]"))
            else:
                ransom = min(ca, stake)
                coins_add(gid, qq, -ransom)
                coins_add(gid, tid, ransom)
                lines.append(T.FIGHT_PAY_MONEY.format(money=ransom))
        elif shield:
            victim = _random.choice(stealable)
            lines.append(T.FIGHT_MY_TREASURE)
            lines.append("[" + uname(st, victim) + "]" + T.FIGHT_MY_SHIELD)
        else:
            ransom = min(ca, stake)
            coins_add(gid, qq, -ransom)
            coins_add(gid, tid, ransom)
            lines.append(T.FIGHT_PAY_MONEY.format(money=ransom))
    return "\r\n".join(lines)


_GACHA_LABEL = {1: "单抽", 10: "十连抽", 30: "三十连抽", 50: "五十连抽"}
_GACHA_COST_KEY = {1: "抽武器花费", 10: "十连抽花费", 30: "三十连抽花费", 50: "五十连抽花费"}
_GACHA_COST_DEF = {1: 1988, 10: 18800, 30: 56000, 50: 92000}

def cmd_gacha(gid, qq, st, count=1):
    count = count if count in _GACHA_LABEL else 1
    n = count
    label = _GACHA_LABEL[count]
    cost = cfgi("设置", _GACHA_COST_KEY[count], _GACHA_COST_DEF[count])
    if not any(_gacha_pool(r) for r in ("SSR", "SR", "R")):
        return "武器图库为空, 请管理员先放入 SSR/SR/R 图鉴后再来抽~"
    u = U(st, qq)
    if coins_get(gid, qq) < cost:
        return f"武器{label}需要消耗{cost}{coin_name()}, " + T.POOR.format(coin=coin_name())
    coins_add(gid, qq, -cost)

    pr = {"R": cfgi("设置", "抽武器R概率", 50),
          "SR": cfgi("设置", "抽武器SR概率", 38),
          "SSR": cfgi("设置", "抽武器SSR概率", 2)}
    exp_map = {"R": cfgi("设置", "R经验", 9),
               "SR": cfgi("设置", "SR经验", 99),
               "SSR": cfgi("设置", "SSR经验", 299)}

    results, imgs, exp_total = [], [], 0
    owned = set(weapons_of(u))
    got_ssr = False
    agg = {}
    for i in range(n):
        roll = _random.uniform(0, 100)
        acc, rar = 0, "R"
        for r in ("SSR", "SR", "R"):
            acc += pr[r]
            if roll <= acc:
                rar = r
                break
        pool = _gacha_pool(rar)
        if not pool:
            for alt in ("R", "SR", "SSR"):
                alt_pool = _gacha_pool(alt)
                if alt_pool:
                    rar = alt
                    pool = alt_pool
                    break
        if not pool:
            continue
        imgpath = _random.choice(pool)
        name = _os.path.splitext(_os.path.basename(imgpath))[0]
        e_gain = exp_map.get(rar, 9)

        if rar == "SSR":
            # 同步至商城图鉴
            _sync_weapon_shop(name)
            if name in owned:
                exp_total += e_gain
                cur = int(uget(u, name, "0") or 0) + 1
                uset(u, name, str(cur))
                uset(u, "weapon_exp", str(int(uget(u, "weapon_exp") or 0) + e_gain))
                results.append(f"{name} 重复获得，转化为武器经验：{e_gain}")
            else:
                owned.add(name)
                wl = weapons_of(u)
                wl.append(name)
                uset(u, "weapon", "|".join(wl))
                uset(u, name, "1")
                if not st.has_option(str(qq), name + "升星"):
                    uset(u, name + "升星", "0")
                cq = _img_cq(_os.path.abspath(imgpath))
                if cq:
                    imgs.append(cq)
                got_ssr = True
                results.append(f"🌟NEW! {name}")
        else:
            exp_total += e_gain
            uset(u, "weapon_exp", str(int(uget(u, "weapon_exp") or 0) + e_gain))
            if count == 1:
                results.append(f"{rar}·{name} 经验+{e_gain}")
            else:
                a = agg.setdefault(rar, [0, 0])
                a[0] += 1
                a[1] += e_gain
    if count > 1:
        for rar in ("SR", "R"):
            if rar in agg:
                c, e = agg[rar]
                results.append(f"{rar}×{c}，自动转化为经验+{e}")
    head = f"[{uname(st,qq)}] " + (f"武器{label}需要消耗{cost}{coin_name()}" if count > 1 else (f"本次抽武器消耗{cost}{coin_name()}"))

    out = head + "\r\n" + "\r\n".join(results)
    if count >= 10 and not got_ssr:
        out += "\r\n" + T.GACHA_NO_SSR
    out += "\r\n" + (T.GACHA_TOTAL_EXP.format(exp=exp_total))
    out += "\r\n💡 R/SR已自动转为经验; SSR可装备出战"
    if imgs:
        # 十连及以上展示最多10张，单抽展示1张
        lim = 10 if count >= 10 else 4
        out += "\r\n" + "".join(imgs[:lim])
    return out


def cmd_starup(gid, qq, wname, st):
    wname = wname.strip("+ ").strip()
    u = U(st, qq)
    wl = weapons_of(u)
    if wname not in wl:
        return T.WUP_NOT_EXIST
    lv = star_of(u, wname)
    if lv >= 5:
        return T.WUP_MAX
    cn = ["一", "二", "三", "四", "五"][lv]
    need_cnt = cfgi("设置", f"{cn}星武器消耗同武器数量", lv + 1)
    cost = cfgi("设置", f"{cn}星武器花费", 5555)
    prob = cfgi("设置", f"{cn}星武器概率", 50)
    need_exp = cfgi("设置", f"{cn}星武器经验", 999)

    mat = int(uget(u, wname, "0"))
    curexp = int(uget(u, "weapon_exp") or 0)
    if mat < need_cnt:
        return (T.WUP_USE_WEAPON.format(items=f"{wname}x{need_cnt}")) + "\r\n" + \
               T.NOT_ENOUGH + f"(现有同名{mat})"
    if curexp < need_exp:
        return T.WUP_NO_EXP + f"(需{need_exp}, 现有{curexp})"
    if coins_get(gid, qq) < cost:
        return T.WUP_USE_COIN.format(coin=cost) + "\r\n" + T.POOR.format(coin=coin_name())

    coins_add(gid, qq, -cost)
    if _random.randint(1, 100) > prob:
        uset(u, wname, str(mat - need_cnt))
        uset(u, "weapon_exp", str(curexp - need_exp))
        return (T.WUP_FAIL + "\r\n" + T.WUP_USE_WEAPON.format(items=f"{wname}x{need_cnt}")
                + "\r\n" + T.WUP_USE_EXP.format(exp=need_exp)
                + "\r\n" + T.WUP_PROB.format(prob=prob))
    uset(u, wname, str(mat - need_cnt))
    uset(u, "weapon_exp", str(curexp - need_exp))
    uset(u, wname + "升星", str(lv + 1))
    return T.WUP_OK.format(name=wname) + f" 当前{lv+1}星!"


def cmd_treasure_up(gid, qq, tname, st):
    tname = tname.strip("+＋ ").strip()
    treas = [t for t in (cfg("设置", "treasure", "") or "").split("|") if t]
    if tname not in treas:
        return T.TUP_NOT_EXIST
    u = U(st, qq)
    if not treasures_of(u):
        return T.TUP_HAVE_NONE
    stage = int(uget(u, tname + "升阶", "0"))
    if stage >= 3:
        return T.TUP_MAX
    idx = ["一", "二", "三"][stage]
    need = cfgi("设置", f"{idx}阶宝物消耗宝物数量", stage + 1)
    cost = cfgi("设置", f"{idx}阶宝物花费", 77777)
    prob = cfgi("设置", f"{idx}阶宝物概率", 50)
    have = int(uget(u, tname, "0"))
    if have < need:
        return T.TUP_NO_ITEM + f"(需{tname}x{need}, 现有{have})"
    if coins_get(gid, qq) < cost:
        return f"升阶需要{cost}{coin_name()}，哦，攒够了再来吧~"

    coins_add(gid, qq, -cost)
    if _random.randint(1, 100) > prob:
        uset(u, tname, str(have - need))
        return (T.TUP_FAIL + "\r\n" + T.TUP_USED.format(items=f"{tname}x{need}")
                + "\r\n" + T.TUP_COST.format(cost=cost)
                + "\r\n" + T.TUP_PROB.format(prob=prob)
                + "\r\n升阶失败只扣除材料，宝物不会消失哦~")
    uset(u, tname, str(have - need))
    uset(u, tname + "升阶", str(stage + 1))
    eff = T.GOURD_EFFECT if "酒神" in tname else T.CHARM_EFFECT
    return (f"✨ [{tname}] 升至{stage+1}阶!\r\n{T.T_STAGE.format(n=stage+1)} "
            + eff)


def cmd_sign(gid, qq, st):
    """签到开关=假时静默(交给 drea 主插件处理)"""
    if cfg("签到配置", "签到开关", "假") != "真":
        return None
    u = U(st, qq)
    today = _dt.date.today().isoformat()
    if uget(u, "last_sign") == today:
        return T.SIGN_REPEAT
    base = cfgi("签到配置", "签到奖励", 10)
    chain_bonus = cfgi("签到配置", "连签奖励", 5)
    chain = int(uget(u, "consecutive_days", "0")) + 1
    total = int(uget(u, "total_sign_days", "0")) + 1
    gain = base + chain_bonus * chain
    uset(u, "last_sign", today)
    uset(u, "consecutive_days", str(chain))
    uset(u, "total_sign_days", str(total))
    coins_add(gid, qq, gain)
    return (
        f"&@恭喜你签到成功！\r\n"
        f"奖励详情：\r\n"
        f"基础奖励 +{base}\r\n"
        f"连签{chain}天奖励 +{chain_bonus * chain}\r\n"
        f"奖励合计：{gain}\r\n"
        f"当前{coin_name()}：{coins_get(gid, qq)}\r\n"
        f"签到者 [{uname(st, qq)}] 总签{total}天 连签{chain}天"
    )


def _weapon_shop():
    v = store.cfg("商城图鉴", "weapon_shop", "")
    if isinstance(v, dict):
        return v
    if v:
        try:
            d = _json.loads(v)
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return {}

def _sync_weapon_shop(name):
    try:
        ws = _weapon_shop()
        if name not in ws:
            # 自动同步抽奖武器至商城，默认价 50000 可在 WebUI 改
            ws[name] = {"price": 50000, "atk": 0, "desc": ""}
            store.set_ini("商城图鉴", "weapon_shop", _json.dumps(ws, ensure_ascii=False))
            try:
                store.save_config()
            except Exception:
                pass
    except Exception:
        pass

def cmd_weapon_menu(gid, qq, st):
    # 复用 gacha 缓存，避免每消息 listdir
    try:
        names = [_os.path.splitext(_os.path.basename(p))[0] for p in _gacha_pool("SSR")]
    except Exception:
        names = []
    # 合并商城武器与抽奖武器，去重
    try:
        ws = _weapon_shop()
        for k in ws.keys():
            if k not in names:
                names.append(k)
    except Exception:
        pass
    u = U(st, qq)
    owned = set(weapons_of(u))
    ws = _weapon_shop()
    lines = ["⚔️ 武器图鉴", "━━━━━━━━━━━━━━"]
    for n in names:
        star = star_of(u, n)
        own = f"✔已持有 ★{star}" if n in owned else "未持有"
        price = ws.get(n, {}).get("price", "") if isinstance(ws.get(n), dict) else ws.get(n, "")
        price_txt = f" 价格:{price}{coin_name()}" if price else ""
        # 检查图片是否存在，缺失则不显示黑图
        img_missing = ""
        try:
            # 尝试在 SSD/R 池中找对应文件
            found = False
            for rar in ("SSR","SR","R"):
                for p in _gacha_pool(rar):
                    if _os.path.splitext(_os.path.basename(p))[0] == n and _os.path.isfile(p):
                        found = True
                        break
                if found:
                    break
            if not found:
                img_missing = " (图缺)"
        except Exception:
            pass
        lines.append(f"◆ {n}　攻击+{STAR_ATK[min(5, star)]}　{own}{price_txt}{img_missing}")
    lines.append("━━━━━━━━━━━━━━")
    lines.append("成长: ★0+100 → ★3+600 → ★5+1600")
    lines.append("🎁 获取: 【抽武器】【十连抽】【三十连抽】【五十连抽】/商城购买")
    lines.append("💡 R/SR抽到即转经验, SSR才能装备出战")
    lines.append("⭐ 升星: 【升星+武器名】如【升星雷鸣剑】")
    lines.append("🔍 详情: 直接发【武器名】如【鬼泪村正】")
    return "\r\n".join(lines)


def cmd_treasure_menu(gid, qq, st):
    treas = [t for t in (cfg("设置", "treasure", "") or "").split("|") if t]
    u = U(st, qq)

    def eff(t):
        if "酒神" in t:
            return T.GOURD_EFFECT
        if "四象" in t or "护符" in t:
            return T.CHARM_EFFECT
        return ""

    lines = ["🎁 宝物图鉴", "━━━━━━━━━━━━━━"]
    for t in treas:
        cnt = int(uget(u, t, "0") or 0)
        stage = int(uget(u, t + "升阶", "0") or 0)
        own = f"✔已持有{cnt}个" if cnt > 0 else "未持有"
        lines.append(f"◆ {t}　{own}")
        e = eff(t)
        if e:
            lines.append(f"　└ {e}")
            if stage:
                lines[-1] += f"(当前{stage}阶)"
    lines.append("━━━━━━━━━━━━━━")
    lines.append("🍀 获取: 【我要学习】概率奇遇(获取即生效)")
    lines.append("🔺 升阶: 【升阶+宝物名】如【升阶酒神葫芦】")
    lines.append("🔍 详情: 直接发【宝物名】如【酒神葫芦】")
    return "\r\n".join(lines)


def cmd_rank_price(gid, st):
    lst = sorted(((int(uget(st[s], "price") or 0), s)
                  for s in st.sections()
                  if s.isdigit() and not (BOT_UIN and s == str(BOT_UIN))),
                 reverse=True)[:10]
    out = ["🏆 身价排行榜"]
    for i, (p, q) in enumerate(lst, 1):
        out.append(f"{i}. [{uname(st, q)}] {p}")
    return "\r\n".join(out)


def cmd_rank_sign(gid, st):
    """签到次数来自本地档案(总签天数), 不再依赖 drea"""
    lst = []
    for q in st.sections():
        if not q.isdigit():
            continue
        if BOT_UIN and q == str(BOT_UIN):
            continue
        try:
            dcount = int(uget(st[q], "total_sign_days", "0") or 0)
        except Exception:
            dcount = 0
        lst.append((dcount, q))
    lst.sort(reverse=True)
    out = ["📅 签到排行榜"]
    for i, (dcount, q) in enumerate(lst[:10], 1):
        nm = uget(st[q], "name") if st.has_section(q) else ""
        out.append(f"{i}. [{nm or q}] {dcount}天")
    return "\r\n".join(out)


def cmd_rank(gid, st):
    return cmd_rank_price(gid, st) + "\r\n\r\n" + cmd_rank_sign(gid, st)


# 指令路由入口
def handle(gid, qq, raw):
    reply = _route(gid, qq, raw)
    if isinstance(reply, str) and reply:
        save(str(gid))
        return reply
    return None

# Fix: table-driven exact (re-added)
_ROUTE_EXACT = {
    "我的信息": lambda gid, qq, target, st, text: cmd_myinfo(gid, qq, st),
    "我要自由": lambda gid, qq, target, st, text: cmd_freedom(gid, qq, st),
    "武器菜单": lambda gid, qq, target, st, text: cmd_weapon_menu(gid, qq, st),
    "宝物菜单": lambda gid, qq, target, st, text: cmd_treasure_menu(gid, qq, st),
    "身价排行榜": lambda gid, qq, target, st, text: cmd_rank_price(gid, st),
    "身价排行": lambda gid, qq, target, st, text: cmd_rank_price(gid, st),
    "签到排行榜": lambda gid, qq, target, st, text: cmd_rank_sign(gid, st),
    "签到排行": lambda gid, qq, target, st, text: cmd_rank_sign(gid, st),
    "排行榜": lambda gid, qq, target, st, text: cmd_rank(gid, st),
    "奴隶打工": lambda gid, qq, target, st, text: cmd_work_dispatch(gid, qq, st),
    "我要打工": lambda gid, qq, target, st, text: cmd_work_dispatch(gid, qq, st),
    "奴隶收工": lambda gid, qq, target, st, text: cmd_work_collect(gid, qq, st),
}

def _route(gid, qq, raw):
    gid = str(gid); qq = str(qq)

    # Fix B5: serialize commands per group
    with _cmd_lock(gid):
        return _route_locked(gid, qq, raw)

def _route_locked(gid, qq, raw):

    # 分群开关
    if cfg("分群开关", gid, "") == "假":
        return None

    st = state(gid)
    target, text = store.parse_at(raw)
    mark_known(gid, qq)

    # @名字 兜底: 从本群已有档案(名片/昵称)反查 qq
    if not target:
        m = _re.search(r"@\s*([^@\s，,]+)", text)
        if m:
            nm = m.group(1).strip()
            for _uid in st.users():
                if uget(U(st, _uid), "name") == nm:
                    target = str(_uid)
                    text = text.replace(m.group(0), "", 1).strip()
                    break
            if not target and store._AT_NAMES:
                store.register_names(NOTE_NAMES)  # 确保索引最新
        # 兼容纯 QQ 号（无 @）的写法：文案仅 @QQ，但解析支持 QQ 号
        if not target:
            # 仅对需要目标的指令尝试提取，避免金额被误判
            _need = ("查询","补偿","买下","折磨","保护","释放","赎身","起名","打架","购买奴隶位")
            for _pref in _need:
                if text.startswith(_pref):
                    m = _re.search(r"\b(\d{5,12})\b", text)
                    if m:
                        target = m.group(1)
                        text = text.replace(m.group(0), "", 1).strip()
                    break
            # 通用兜底：若仍无 target 且文本含 @QQ 之外的独立 QQ 号（如 买下 123），也尝试首个数字
            if not target:
                # 对于买下/查询等，即使前缀不完全匹配也尝试
                if any(kw in text for kw in ("买下","查询","补偿","保护","释放","赎身","起名","打架")):
                    m = _re.search(r"\b(\d{5,12})\b", text)
                    if m:
                        target = m.group(1)
                        text = text.replace(m.group(0), "", 1).strip()

    # 去掉开头的表情码干扰
    text = _re.sub(r"\[(?:CQ|DR):[^\]]+\]", "", text).strip()

    # Fast path: exact commands
    if text in _ROUTE_EXACT:
        return _ROUTE_EXACT[text](gid, qq, target, st, text)

    if text in store.wake("奴隶系统", "奴隶系统"):
        return cmd_menu()
    if text == "我的信息" or text.startswith("我的信息"):
        # 支持 我的信息 @QQ / QQ 查询他人（兼容已提取的 target）
        t = target
        if not t and text.startswith("我的信息 "):
            # 兜底：从剩余文本再解析（纯数字或@）
            t2, _ = store.parse_at(text[len("我的信息 "):])
            if t2:
                t = t2
            else:
                import re as _re2
                m = _re2.search(r"(\d{5,12})", text)
                if m:
                    t = m.group(1)
        if t:
            return cmd_query(gid, qq, t, st)
        return cmd_myinfo(gid, qq, st)
    if text.startswith("查询"):
        # 查询@QQ  -> 查他人我的信息，兼容已提取的 target
        t = target
        if not t:
            t2, _ = store.parse_at(text)
            if t2:
                t = t2
            else:
                import re as _re3
                m = _re3.search(r"(\d{5,12})", text)
                if m:
                    t = m.group(1)
        if t:
            return cmd_query(gid, qq, t, st)
        return "格式：查询 @QQ"
    if text.startswith("补偿"):
        mnum = _NUM.search(text)
        amt = int(mnum.group(1)) if mnum else 0
        return cmd_compensate(gid, qq, target, amt, st)
    if text.startswith("买下"):
        return cmd_buy_slave(gid, qq, target, st)
    if text.startswith("折磨"):
        return cmd_torture(gid, qq, target, st)
    if text.startswith("保护"):
        return cmd_protect(gid, qq, target, st)
    if text.startswith("释放"):
        return cmd_release(gid, qq, target, st)
    if text.startswith("赎身"):
        return cmd_ransom(gid, qq, target, st)
    if text == "我要自由":
        return cmd_freedom(gid, qq, st)
    if text.startswith("起名"):
        return "起名功能已下线，请使用系统默认昵称。"
    if text.startswith("买奴隶位") or text.startswith("购买奴隶位"):
        return cmd_buyslot(gid, qq, st)
    if text.startswith("打架"):
        return cmd_fight(gid, qq, target, st)
    if text.startswith("五十连抽") or text.startswith("50连抽"):
        return cmd_gacha(gid, qq, st, count=50)
    if text.startswith("三十连抽") or text.startswith("30连抽"):
        return cmd_gacha(gid, qq, st, count=30)
    if text.startswith("十连抽"):
        return cmd_gacha(gid, qq, st, count=10)
    if text.startswith("抽武器"):
        return cmd_gacha(gid, qq, st, count=1)
    if text.startswith("升星"):
        return cmd_starup(gid, qq, text[2:], st)
    if text.startswith("升阶"):
        return cmd_treasure_up(gid, qq, text[2:], st)
    if text == "奴隶打工" or text == "我要打工":
        return cmd_work_dispatch(gid, qq, st)
    if text == "奴隶收工":
        return cmd_work_collect(gid, qq, st)
    if text == "我要造反" or text.startswith("造反"):
        return cmd_revolt(gid, qq, st)
    if text.startswith("讨好主人") or text == "讨好":
        return cmd_flatter(gid, qq, st)
    if text == "我要学习" or text.startswith("学习"):
        return cmd_study(gid, qq, st)
    if text == "我要祈福" or text.startswith("祈福"):
        return cmd_pray(gid, qq, st)
    # Fix: removed 我要签到 to avoid conflict with normal sign-in
    # if text == "我要签到":
    #     return cmd_sign(gid, qq, st)
    if text == "武器菜单":
        return cmd_weapon_menu(gid, qq, st)
    if text == "宝物菜单":
        return cmd_treasure_menu(gid, qq, st)
    if text == "身价排行榜" or text == "身价排行":
        return cmd_rank_price(gid, st)
    if text == "签到排行榜" or text == "签到排行":
        return cmd_rank_sign(gid, st)
    if text == "排行榜":
        return cmd_rank(gid, st)

    # 查询武器/宝物信息: 支持带【】或不带
    q = text
    if q.startswith("【") and q.endswith("】"):
        q = q[1:-1].strip()
    treas = [t for t in (cfg("设置", "treasure", "") or "").split("|") if t]
    try:
        all_w = [_os.path.splitext(_os.path.basename(p))[0] for p in _gacha_pool("SSR")]
    except Exception:
        all_w = []
    if q in treas:
        stage = int(uget(U(st, qq), q + "升阶", "0"))
        have = int(uget(U(st, qq), q, "0"))
        eff = T.GOURD_EFFECT if "酒神" in q else T.CHARM_EFFECT
        return (T.T_NAME.format(name=q) + "\r\n" + T.T_STAGE.format(n=stage)
                + "\r\n" + T.T_EFFECT.format(effect=eff)
                + f"\r\n持有数量: {have}")
    if q in all_w:
        u = U(st, qq)
        lv = star_of(u, q)
        table = STAR_ATK
        owned = q in weapons_of(u)
        imgp = _os.path.join(DATA_DIR, "gacha_img", "SSR", q + ".png")
        img = _img_cq(imgp)
        return (T.W_NAME.format(name=q) + f"★{lv}\r\n"
                + T.W_EFFECT.format(atk=f"+{table[min(5, lv)]}") + "\r\n"
                + T.W_5STAR_EFFECT + "\r\n"
                + ("✔你已拥有" if owned else "✖未拥有")
                + "\r\n" + img)

    return None



_IMG_BASE = _os.path.join(DATA_DIR, "gacha_img")

def _img_cq(path):
    """CQ 图片段: 本地文件绝对路径(OneBot 原生支持 file:/// 本机读图)"""
    try:
        p = _os.path.abspath(path)
        if not _os.path.isfile(p):
            return ""
        pp = p.replace("\\", "/")
        if not pp.startswith("/"):
            pp = "/" + pp
        return f"[CQ:image,file=file://{pp}]"
    except Exception:
        return ""

def init_slave(bot_uin="", note_names=None, import_wallet_dir=""):
    """适配层启动时调用: store 初始化 + 机器人QQ + 名片缓存 + (可选)旧drea钱包导入"""
    global BOT_UIN
    BOT_UIN = str(bot_uin or "")
    if note_names:
        NOTE_NAMES.update(note_names)
    load_events()
    if getattr(store, "_DB", None) is None:
        store.init(DB_PATH, CONFIG_JSON)
    _os.makedirs(GROUPS_DIR, exist_ok=True)
    _os.makedirs(WALLET_DIR, exist_ok=True)
    if import_wallet_dir and _os.path.isdir(import_wallet_dir):
        try:
            log("旧drea钱包导入(请用WebUI配置: 已切换为现代存储方案)")
        except Exception as e:
            log(f"钱包导入失败: {e}")
    # 预加载 gacha 池（千群并发下避免每消息 listdir 0.285s）
    try:
        for rar in ("SSR", "SR", "R"):
            _gacha_pool(rar)
    except Exception:
        pass
    # 兼容旧群档案: 若存在 ini 且 sqlite 仍为空, 尝试搬入
    try:
        _migrate_legacy_group_ini()
    except Exception:
        pass


def _migrate_legacy_group_ini():
    """一次性: 把旧 light 群档案 ini 迁入 SQLite(源文件仅改名备份)"""
    import configparser as _cp2
    for fn in _os.listdir(GROUPS_DIR):
        if not fn.lower().endswith(".ini"):
            continue
        gid = fn[:-4]
        if not gid.isdigit():
            continue
        g = store.group(gid)
        if g.users():
            continue
        path = _os.path.join(GROUPS_DIR, fn)
        for enc in ("utf-8", "gbk"):
            try:
                cp = _cp2.ConfigParser(interpolation=None)
                cp.optionxform = str
                cp.read(path, encoding=enc)
                for sec in cp.sections():
                    g[sec].update({k: cp.get(sec, k, fallback="") for k in cp.options(sec)})
                store.save_group(gid)
                _os.rename(path, path + ".migrated")
                log(f"群档案迁移: {fn}")
                break
            except Exception:
                continue
