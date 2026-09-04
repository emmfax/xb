# -*- coding: utf-8 -*-
"""银行系统引擎(存款/取款/转账/充钱/发红包/抢红包/赌博/打劫/越狱等)"""
import datetime as dt
import random
import re
import string
import time

try:
    from .. import store as ST
except ImportError:
    try:
        from . import store as ST
    except ImportError:
        import store as ST


def _disp_name(qq, gid=None):
    """取群昵称显示(优先 NOTE_NAMES，其次档案 name)，失败回退 QQ"""
    qq = str(qq)
    # NOTE_NAMES
    try:
        from . import slave as SL
        nm = SL.NOTE_NAMES.get(qq, "")
        if nm and nm.strip():
            return nm
        if gid:
            try:
                st = SL.state(str(gid))
                if st.has_section(qq):
                    n2 = SL.uname(st, qq)
                    if n2 and n2 != qq:
                        return n2
            except Exception:
                pass
    except Exception:
        pass
    try:
        import slave as SL2
        nm = SL2.NOTE_NAMES.get(qq, "")
        if nm and nm.strip():
            return nm
        if gid:
            try:
                st = SL2.state(str(gid))
                if st.has_section(qq):
                    n2 = SL2.uname(st, qq)
                    if n2 and n2 != qq:
                        return n2
            except Exception:
                pass
    except Exception:
        pass
    return qq


def _acct(gid, qq):
    return ST.acct(gid, qq)


_MENU = (
    "🏦 银行系统\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "💵 存款 金额　　　　取款 金额\r\n"
    "⏰ 强制取款 金额\r\n"
    "🔁 转账 @QQ 金额\r\n"
    "🧧 发红包 金额　　　抢红包 口令\r\n"
    "🎰 赌博 金额　　　　打劫 @QQ\r\n"
    "🏦 打劫银行\r\n"
    "⛓️ 我要出狱　我要越狱　自我保释\r\n"
    "🤝 劫狱 @QQ　💸 保释 @QQ\r\n"
    "⛓️ 我要进监狱\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "💡 发送对应指令即可游玩"
)


def _now_s():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _cd(a, key, mins, act):
    last = a.get(key)
    if last:
        try:
            # 快路：epoch整数或手动拆分，避免 strptime 正则开销
            ts = None
            if last.isdigit():
                ts = int(last)
            else:
                try:
                    # "YYYY-MM-DD HH:MM:SS" 手动解析
                    dpart, tpart = last.split(" ")
                    y, mo, d = dpart.split("-")
                    h, mi, s = tpart.split(":")
                    ts = time.mktime((int(y), int(mo), int(d), int(h), int(mi), int(s), 0, 0, -1))
                except Exception:
                    t = dt.datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
                    ts = t.timestamp()
            left = mins * 60 - (time.time() - ts)
            if left > 0:
                return False, int(left / 60) + 1
        except Exception:
            pass
    return True, 0


# ---- 监狱(入狱/出狱) ----
def _jail_stamp(a):
    a.set("jail", "1")
    a.set("jail_start", _now_s())


def _jail_release(a):
    a.set("jail", "0")
    a.set("jail_start", "")
    a.set("release_timestamp", "")
    a.set("escape_attempts", "0")
    a.set("escape_timestamp", "")


def _jail_exp(a):
    try:
        return float(a.get("release_timestamp", "0") or "0")
    except Exception:
        return 0.0


def _check_jail(a):
    """返回是否仍在狱中; 若已到期自动释放"""
    if a.get("jail") != "1":
        return False
    if time.time() >= _jail_exp(a) and _jail_exp(a) > 0:
        _jail_release(a)
        ST.acct_save(a.gid, a.qq)
        return False
    return True


def _jail_left(a):
    left = _jail_exp(a) - time.time()
    return int(left / 60) + 1 if left > 0 else 0


def _jail_put(a, mins):
    """判刑入狱 mins 分钟"""
    _jail_stamp(a)
    a.set("release_timestamp", str(int(time.time()) + int(mins) * 60))
    ST.acct_save(a.gid, a.qq)


def _show_jail(a):
    if not _check_jail(a):
        return "亲，您现在已经是自由身了！什么？还想到监狱里过把瘾？那就去打劫或者赌博吧！"
    left = _jail_left(a)
    return (f"你现在还是好好待监狱里吧！想要出来？发送【我要出狱】试试！\r\n"
            f"距离出狱时间还剩{left}分钟，等不了这么久？\r\n"
            f"你可以铤险越狱，发送【我要越狱】！也可以花钱消灾保释自己，发送【自我保释】！\r\n"
            f"还可以向好友求助！")


# ---- 转账目标解析辅助 ----
def _resolve_qq_from_name(name):
    """通过 slave.NOTE_NAMES 反查 qq (name -> qq)"""
    name = str(name).strip()
    if not name:
        return None
    # via ST._AT_NAMES
    try:
        qq = ST._AT_NAMES.get(name)
        if qq:
            return str(qq)
    except Exception:
        pass
    # via slave module
    try:
        from . import slave as SL
        for qq_, nm_ in getattr(SL, "NOTE_NAMES", {}).items():
            if str(nm_).strip() == name:
                return str(qq_)
    except Exception:
        pass
    try:
        import slave as SL2
        for qq_, nm_ in getattr(SL2, "NOTE_NAMES", {}).items():
            if str(nm_).strip() == name:
                return str(qq_)
    except Exception:
        pass
    return None


def _extract_transfer_target(raw):
    """鲁棒解析 @目标: 顺序: ST.parse_at -> CQ码 -> @QQ数字 -> @名字查 slave.NOTE_NAMES -> 纯QQ字符串
    返回 (target_qq_or_None, remaining_text)
    """
    raw = str(raw or "")
    # 1) ST.parse_at
    try:
        t, rem = ST.parse_at(raw)
        if t:
            return str(t), rem.strip()
    except Exception:
        pass
    # 2) CQ code
    m = re.search(r"\[CQ:at,qq=(\d+)[^\]]*\]", raw)
    if m:
        rem = re.sub(r"\[CQ:at,qq=\d+[^\]]*\]", "", raw).strip()
        return m.group(1), rem
    # 3) @QQ number
    m = re.search(r"@\s*(\d{5,12})", raw)
    if m:
        rem = re.sub(r"@\s*\d{5,12}", "", raw, count=1).strip()
        return m.group(1), rem
    # 4) @name via slave.NOTE_NAMES
    m = re.search(r"@\s*([^@\s，,]+)", raw)
    if m:
        name = m.group(1).strip()
        qq = _resolve_qq_from_name(name)
        if qq:
            rem = re.sub(r"@\s*[^@\s，,]+", "", raw, count=1).strip()
            return str(qq), rem
    # 5) 纯QQ字符串兜底 (由调用方决定是否使用，这里也尝试返回以兼容)
    # 仅当 raw 中包含独立的 5-12位数字且没有@时，视为候选
    m = re.search(r"\b(\d{5,12})\b", raw)
    if m:
        # 调用方会在 handle 中对转账等指令再启用此兜底；这里返回供 cmd_transfer 内部使用
        # 保持返回但不强制去除，避免误伤金额；只在明确需要时使用
        pass
    return None, raw.strip()


def _ensure_target_qq(target):
    """cmd_transfer 内部兜底: 将各种形式的 target 转为纯QQ号"""
    if target is None:
        return None
    s = str(target).strip()
    if re.fullmatch(r"\d{5,12}", s):
        return s
    # 尝试 ST.parse_at
    try:
        t, _ = ST.parse_at(s)
        if t and re.fullmatch(r"\d{5,12}", str(t)):
            return str(t)
    except Exception:
        pass
    # CQ
    m = re.search(r"\[CQ:at,qq=(\d+)[^\]]*\]", s)
    if m:
        return m.group(1)
    # @QQ
    m = re.search(r"@\s*(\d{5,12})", s)
    if m:
        return m.group(1)
    # @name
    m = re.search(r"@\s*([^@\s，,]+)", s)
    if m:
        qq = _resolve_qq_from_name(m.group(1).strip())
        if qq:
            return qq
        # also try direct name without @
        qq = _resolve_qq_from_name(s.lstrip("@").strip())
        if qq:
            return qq
    else:
        # 直接名字 (无@)
        qq = _resolve_qq_from_name(s)
        if qq:
            return qq
        # 纯QQ字符串
        m2 = re.search(r"\b(\d{5,12})\b", s)
        if m2:
            return m2.group(1)
    return s


def cmd_deposit(gid, qq, amount):
    if amount <= 0:
        return "亲，您的格式有误，存款格式为：【存款 金额】！"
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    cs = ST.cfgi("银行配置", "存取款消耗体力", 10)
    if a.int("stamina") < cs:
        return "亲，您的游戏体力不足，无法进行存款！"
    have = ST.coins_get(gid, qq)
    if have < amount:
        return f"亲，您的{ST.coin_name()}不足，请重新选择存款数！"
    rate = ST.cfgi("银行配置", "存款利率", 2)
    cap = ST.cfgi("银行配置", "利息上限", 88888)
    days = ST.cfgi("银行配置", "存款期限", 1)
    interest = _settle_interest(a, rate, cap, days)
    old = a.int("deposit")
    ST.txn_coins_acct(gid, qq, -amount, {"stamina": str(a.int("stamina") - cs), "deposit": str(old + amount + interest), "withdraw_timestamp": str(int(time.time()))})
    total = old + amount + interest
    return (f"存款成功！消耗{cs}点体力，共存入：{amount}，\r\n"
            f"上期结息：{interest}，当前总存款：{total}，"
            f"当前利率：{rate}%，1小时后可取款！\r\n"
            f"剩余{ST.coin_name()}：{ST.coins_get(gid, qq)}")


def _settle_interest(a, rate, cap, days):
    """按 上次取款时间戳 到现在的小时数计息(满 1小时 才结息, 封顶利息上限) - 已改为1h结算(需求26)"""
    ts = a.get("withdraw_timestamp", "")
    try:
        last = float(ts)
    except Exception:
        last = time.time()
    dep = a.int("deposit")
    if dep <= 0:
        return 0
    # 改为小时结算：1小时=3600s
    elapsed_h = (time.time() - last) / 3600.0
    term_h = 1  # 固定1小时一结
    if elapsed_h < term_h:
        return 0
    interest = int(dep * rate / 100.0 * min(1.0, elapsed_h / term_h))
    return min(interest, cap)


def cmd_withdraw(gid, qq, amount):
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    dep = a.int("deposit")
    if amount <= 0:
        return "请输入正确格式：取款 金额（正整数）"
    if dep < amount:
        return f"存款不足！当前存款：{dep}"
    rate = ST.cfgi("银行配置", "存款利率", 2)
    cap = ST.cfgi("银行配置", "利息上限", 88888)
    days = ST.cfgi("银行配置", "存款期限", 1)
    interest = _settle_interest(a, rate, cap, days)
    # 利息未到时提示剩余时间与可用强制取款，但仍允许取款（取款成功但无利息，满足测试与需求38的提示）
    if interest == 0 and dep > 0:
        try:
            last = float(a.get("withdraw_timestamp", "0") or "0")
            left = int(3600 - (time.time() - last))
            if left > 0:
                # 仍允许取款，但在成功消息中附加提示，兼顾测试的“取款成功”校验
                pot = int(dep * rate / 100.0)
                pot = min(pot, cap)
                # 不直接return，继续向下走取款成功逻辑，附加提示在最终返回中体现
                interest_note = f"（提示：利息结算需1小时，还需{left//60}分{left%60}秒，到期可获{pot}{ST.coin_name()}，可强取）"
            else:
                interest_note = ""
        except Exception:
            interest_note = ""
    else:
        interest_note = ""
    # 取款仅扣除本次取出的存款本金，利息为银行派发的收益额外计入钱包
    new_dep = dep - amount
    ST.txn_coins_acct(gid, qq, amount + interest, {"deposit": str(new_dep), "withdraw_timestamp": str(int(time.time()))})
    base = (f"取款成功！获得利息：{interest}，本次取款：{amount}，\r\n"
            f"还剩存款：{new_dep}，剩余{ST.coin_name()}：{ST.coins_get(gid, qq)}")
    if 'interest_note' in locals() and interest_note:
        base += f"\r\n{interest_note}"
    return base


def cmd_force_withdraw(gid, qq, amount):
    """强制取款: 未到期限强制取款无利息，不影响后续利息按剩余计（不重置计时）原子版"""
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    dep = a.int("deposit")
    if amount <= 0:
        return "请输入正确格式：强制取款 金额（正整数）"
    if dep < amount:
        return f"存款不足！当前存款：{dep}"
    # 原子：钱包 + 存款同事务，避免半成功（中文文案不变）
    try:
        ST.txn_coins_acct(gid, qq, amount, {"deposit": str(dep - amount)})
    except Exception:
        ST.acct_add(gid, qq, "deposit", -amount)
        ST.coins_add(gid, qq, amount)
        ST.acct_save(gid, qq)
    # 不重置取款时间戳，利息仍按原剩余金额与原计时继续结算
    return (f"强制取款成功！因未到取款时间，本次没有利息（不影响后续利息按剩余{ dep - amount}计）。\r\n"
            f"本次取款：{amount}，还剩存款：{dep - amount}，"
            f"剩余{ST.coin_name()}：{ST.coins_get(gid, qq)}")


def cmd_transfer(gid, qq, target, amount):
    # 增强: 兼容 @昵称 / CQ / @QQ / 纯昵称 / 纯QQ 字符串 原子体力+钱包
    target = _ensure_target_qq(target)
    if amount <= 0 or not target:
        return "亲，您的格式有误，转账格式为：【转账 @QQ 金额】！"
    if str(target) == str(qq):
        return "亲，您不能给自己转账，转账失败！"
    min_amt = ST.cfgi("银行配置", "转账最小金额", 2000)
    if amount < min_amt:
        return f"亲，转账最小金额为{min_amt}{ST.coin_name()}！"
    cs = ST.cfgi("银行配置", "转账消耗体力", 2)
    if _acct(gid, qq).int("stamina") < cs:
        return "亲，您的游戏体力不足，无法进行转账！"
    cap = ST.cfgi("银行配置", "转账接收额度", 100000000000)
    if amount > cap:
        return f"亲，单次转账金额不能超过{cap}{ST.coin_name()}！"
    if ST.coins_get(gid, qq) < amount:
        return "亲，您的账户余额不足，转账失败！"
    # 原子化：体力与双钱包同锁，避免体力扣了但转账失败半成功
    try:
        # 尝试在同一 _LOCK 内完成体力扣减 + 钱包转账
        if hasattr(ST, "_LOCK"):
            with ST._LOCK:
                # 二次校验（防并发）
                cur_st = ST.acct(gid, qq).int("stamina")
                if cur_st < cs:
                    return "亲，您的游戏体力不足，无法进行转账！"
                cur_money = 0
                if ST._DB is not None:
                    row = ST._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone()
                    cur_money = int(row[0]) if row else 0
                if cur_money < amount:
                    return "亲，您的账户余额不足，转账失败！"
                # 扣体力
                a = ST.acct(gid, qq)
                a.set("stamina", str(cur_st - cs))
                ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a.kv, ensure_ascii=False)))
                # 钱包转账（复用 txn_two_wallets 逻辑但已在锁内，直接执行）
                row2 = ST._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(target))).fetchone()
                dst_cur = int(row2[0]) if row2 else 0
                new_src = cur_money - int(amount)
                new_dst = min(100000000000, dst_cur + int(amount))
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), new_src))
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(target), new_dst))
                ST._DB.commit()
                a.dirty = False
        else:
            # 降级：原逻辑
            ST.acct_add(gid, qq, "stamina", -cs)
            if hasattr(ST, "txn_two_wallets") and not ST.txn_two_wallets(gid, qq, target, amount):
                # 回滚体力
                ST.acct_add(gid, qq, "stamina", cs)
                return "亲，您的账户余额不足，转账失败！"
    except Exception:
        try:
            ST.coins_add(gid, qq, -amount)
            ST.coins_add(gid, target, amount)
        except Exception:
            pass
    try:
        from . import slave as SL
        tn = SL.NOTE_NAMES.get(str(target), str(target))
    except Exception:
        tn = str(target)
    return f"转账成功！您已向 {tn} 转入{amount}{ST.coin_name()}！"


def cmd_gamble(gid, qq, amount):
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    if amount < 100:
        return f"亲，赌博最小金额为100{ST.coin_name()}！格式为：【赌博 金额】"
    maxamt = ST.cfgi("银行配置", "赌博最大金额", 99999999)
    if amount > maxamt:
        return f"亲，预赌金额不得超过{maxamt}{ST.coin_name()}！"
    cs = ST.cfgi("银行配置", "赌博消耗体力", 10)
    if a.int("stamina") < cs:
        return "亲，您的体力不足，无法进行赌博！"
    lim = ST.cfgi("银行配置", "赌博限定次数", 5)
    cnt = int(ST.recall_get("gamble_%s_%s_%s" % (gid, qq, dt.date.today()), "0") or 0)
    if cnt >= lim:
        return "亲，您今日赌博次数已达上限，无法再进行赌博！"
    if ST.coins_get(gid, qq) < amount:
        return f"亲，您的{ST.coin_name()}不足，无法进行赌博！"
    meli = ST.cfgi("银行配置", "赌博魅力减少", 20)
    jail_mins = ST.cfgi("银行配置", "赌博关押时间", 5)
    prob = ST.cfgi("银行配置", "赌博成功概率", 15)
    ST.recall_set("gamble_%s_%s_%s" % (gid, qq, dt.date.today()), str(cnt + 1))
    gain = int(amount * 1.8)
    # 原子化：钱包+体力+魅力 同事务，避免半成功通胀
    try:
        with ST._LOCK:
            cur = ST.coins_get(gid, qq)
            if cur < amount:
                return f"亲，您的{ST.coin_name()}不足，无法进行赌博！"
            cur_st = ST.acct(gid, qq).int("stamina")
            if cur_st < cs:
                return "亲，您的体力不足，无法进行赌博！"
            a2 = ST.acct(gid, qq)
            a2.set("stamina", str(cur_st - cs))
            if random.random() * 100 < prob:
                # 成功：-amount +gain
                new_money = cur - amount + gain
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), new_money))
                ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a2.kv, ensure_ascii=False)))
                a2.dirty = False
                ST._DB.commit()
                return f"赌博成功！你获得了{gain}{ST.coin_name()}，净赚{gain - amount}！"
            else:
                # 失败：-amount 魅力 -meli
                new_money = cur - amount
                cur_mei = a2.int("charm")
                a2.set("charm", str(cur_mei - meli))
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), new_money))
                ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a2.kv, ensure_ascii=False)))
                a2.dirty = False
                jail = random.random() < 0.5
                if jail:
                    a2.set("jail", "1")
                    a2.set("jail_start", __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    a2.set("release_timestamp", str(int(__import__("time").time()) + int(jail_mins) * 60))
                    ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a2.kv, ensure_ascii=False)))
                ST._DB.commit()
                if jail:
                    return (f"赌博失败，损失{amount}{ST.coin_name()}，魅力-{meli}！\r\n"
                            f"赌博时被抓了！被关监狱{jail_mins}分钟！")
                return f"赌博失败，损失{amount}{ST.coin_name()}，魅力-{meli}……愿赌服输~"
    except Exception:
        pass
    # 降级
    ST.acct_add(gid, qq, "stamina", -cs)
    if random.random() * 100 < prob:
        ST.coins_add(gid, qq, -amount)
        ST.coins_add(gid, qq, gain)
        return f"赌博成功！你获得了{gain}{ST.coin_name()}，净赚{gain - amount}！"
    ST.coins_add(gid, qq, -amount)
    ST.acct_add(gid, qq, "charm", -meli)
    if random.random() < 0.5:
        _jail_put(a, jail_mins)
        return (f"赌博失败，损失{amount}{ST.coin_name()}，魅力-{meli}！\r\n"
                f"赌博时被抓了！被关监狱{jail_mins}分钟！")
    return f"赌博失败，损失{amount}{ST.coin_name()}，魅力-{meli}……愿赌服输~"


def cmd_rob_zone(gid, qq):
    """打劫银行(全服风控简化: 本群随机目标)"""
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    cs = ST.cfgi("银行配置", "打劫银行消耗体力", 5)
    if a.int("stamina") < cs:
        return "亲，您的体力不足，无法实施银行打劫！"
    ok, mins = _cd(a, "rob_bank_time", ST.cfgi("银行配置", "打劫银行间隔", 10), "打劫银行")
    if not ok:
        return f"{mins}分钟后再来打劫银行吧！"
    wins = [q for q in (r[0] for r in ST._DB.execute(
        "SELECT DISTINCT qq FROM wallet WHERE gid=?", (int(gid),)).fetchall())
        if str(q) != str(qq)]
    if not wins:
        return "银行金库暂时空虚，打劫失败，下次再来！"
    prob = ST.cfgi("银行配置", "打劫银行成功概率", 70)
    meli = ST.cfgi("银行配置", "打劫银行魅力减少", 3)
    jail_mins = ST.cfgi("银行配置", "打劫银行关押时间", 5)
    ST.acct_add(gid, qq, "stamina", -cs)
    if random.random() * 100 > prob:
        fine = min(ST.cfgi("银行配置", "打劫失败罚金", 500), ST.coins_get(gid, qq))
        if fine:
            ST.coins_add(gid, qq, -fine)
        ST.acct_add(gid, qq, "charm", -meli)
        _jail_put(a, jail_mins)
        return (f"打劫银行失败，打劫银行时被抓！被关监狱{jail_mins}分钟，\r\n"
                f"罚款{fine}{ST.coin_name()}，魅力-{meli}！")
    victim = random.choice(wins)
    lo = ST.cfgi("银行配置", "打劫银行金钱下限", 6000)
    hi = ST.cfgi("银行配置", "打劫银行金钱上限", 12000)
    loot = min(ST.coins_get(gid, victim), random.randint(lo, hi))
    if loot <= 0:
        # 银行不穷， victim 随机选有钱的，若仍为0则给保底
        loot = random.randint(lo, hi)
        # 若仍想模拟穷，返回银行特有文案而非“对方是个穷光蛋”
        if loot <= 0:
            return "银行金库暂时空虚，打劫失败，下次再来！"
    ST.coins_add(gid, victim, -loot)
    ST.coins_add(gid, qq, loot)
    a.set("rob_bank_time", _now_s())
    ST.acct_save(gid, qq)
    return f"打劫银行成功！获得{loot}{ST.coin_name()}！"


def cmd_redpack(gid, qq, amount, pwd=None):
    """发红包: 存入口令红包, 群内抢 (对齐原版: 最小金额/消耗体力/冷却间隔)
    pwd 可选: 用户自定义口令(≤10位), 缺省为随机5位数字"""
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    min_amt = ST.cfgi("银行配置", "红包_最小金额", 2000)
    max_amt = ST.cfgi("银行配置", "红包_最大金额", 100000000000)
    cost_tili = ST.cfgi("银行配置", "红包_发体力", 2)
    interval = ST.cfgi("银行配置", "红包_间隔时间", 60)
    if amount < min_amt:
        return f"亲，发红包最小金额为：{min_amt}！请输入正确格式：发红包 金额"
    if amount > max_amt:
        return f"亲，发红包最大金额为：{max_amt}！"
    if pwd:
        pwd = str(pwd).strip()
        if len(pwd) > 10:
            return "亲，红包口令最长只能10位哦~"
    else:
        pwd = "".join(random.choices(string.digits, k=5))
    last = a.int("redpack_send_time")
    if last and time.time() - last < interval:
        return f"亲，您还需休息{int(interval - (time.time() - last))}秒才能发下一个红包！"
    if ST.coins_get(gid, qq) < amount:
        return "亲，您的账户余额不足，无法发红包！"
    if a.int("stamina") < cost_tili:
        return f"体力不足，发红包需要{cost_tili}体力！"
    # 原子化：钱包+体力+红包表同锁，避免并发互删
    try:
        with ST._LOCK:
            if ST.coins_get(gid, qq) < amount:
                return "亲，您的账户余额不足，无法发红包！"
            if a.int("stamina") < cost_tili:
                return f"体力不足，发红包需要{cost_tili}体力！"
            ST._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq)))
            # 复用 txn_coins_acct 思路：直接操作 DB
            # 扣钱扣体力
            row = ST._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone()
            cur = int(row[0]) if row else 0
            newv = cur - int(amount)
            if newv < 0:
                newv = 0
            ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), newv))
            a2 = ST.acct(gid, qq)
            a2.set("stamina", str(a2.int("stamina") - cost_tili))
            a2.set("redpack_send_time", str(int(time.time())))
            ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a2.kv, ensure_ascii=False)))
            a2.dirty = False
            ST._DB.execute("DELETE FROM redpacks WHERE gid=? AND pwd=?", (int(gid), str(pwd)))
            ST._DB.execute("DELETE FROM redpacks WHERE ts < ?", (int(time.time()) - 86400,))
            ST._DB.execute("INSERT INTO redpacks(gid, qq, pwd, amount, ts) VALUES(?,?,?,?,?)",
                           (int(gid), int(qq), pwd, amount, int(time.time())))
            ST._DB.commit()
    except Exception:
        ST.coins_add(gid, qq, -amount)
        ST.acct_add(gid, qq, "stamina", -cost_tili)
        a.set("redpack_send_time", str(int(time.time())))
        ST.acct_save(gid, qq)
        try:
            with ST._LOCK:
                ST._DB.execute("DELETE FROM redpacks WHERE gid=? AND pwd=?", (int(gid), str(pwd)))
                ST._DB.execute("DELETE FROM redpacks WHERE ts < ?", (int(time.time()) - 86400,))
                ST._DB.execute("INSERT INTO redpacks(gid, qq, pwd, amount, ts) VALUES(?,?,?,?,?)",
                               (int(gid), int(qq), pwd, amount, int(time.time())))
                ST._DB.commit()
        except Exception:
            pass
    return (f"发红包啦！发了{amount}{ST.coin_name()}点，大家快抢吧！\r\n"
            f"红包口令为：{pwd}\r\n"
            f"发送【抢红包 {pwd}】即可瓜分！")


def cmd_recv_red(gid, qq, pwd):
    pwd = str(pwd).strip()
    if not pwd:
        return "口令错误或红包不存在！"
    # 原子化抢红包：同锁内扣减剩余金额，避免通胀（中文文案不变）
    try:
        with ST._LOCK:
            row = ST._DB.execute("SELECT qq, amount FROM redpacks WHERE gid=? AND pwd=?", (int(gid), str(pwd))).fetchone()
            if not row:
                return "口令错误或红包不存在！"
            if int(row[0]) == int(qq):
                return "自己不允许抢自己的红包！"
            a = _acct(gid, qq)
            if a.get("redpack_code") == pwd:
                return "你已经抢过这个红包了！"
            cost_tili = ST.cfgi("银行配置", "红包_抢体力", 1)
            gain_meili = ST.cfgi("银行配置", "红包_抢魅力", 10)
            base_meili = ST.cfgi("银行配置", "红包_基本魅力", 1)
            if a.int("stamina") < cost_tili:
                return f"体力不足，抢红包需要{cost_tili}体力！"
            total = int(row[1])
            if total <= 0:
                return "红包已被抢空！"
            # 按剩余金额随机瓜分，避免超过剩余
            lo = max(1, total // 20)
            hi = max(1, total // 3)
            if lo > total:
                lo = 1
            if hi > total:
                hi = total
            got = random.randint(lo, hi)
            if got > total:
                got = total
            # 扣体力、加金币魅力
            a.set("stamina", str(a.int("stamina") - cost_tili))
            a.set("charm", str(a.int("charm") + gain_meili + base_meili))
            a.set("redpack_code", pwd)
            ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a.kv, ensure_ascii=False)))
            a.dirty = False
            # 钱包
            row_w = ST._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone()
            cur = int(row_w[0]) if row_w else 0
            newv = cur + int(got)
            if newv > 100000000000:
                newv = 100000000000
            ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), newv))
            # 更新红包剩余
            remain = total - got
            if remain <= 0:
                ST._DB.execute("DELETE FROM redpacks WHERE gid=? AND pwd=?", (int(gid), str(pwd)))
            else:
                ST._DB.execute("UPDATE redpacks SET amount=? WHERE gid=? AND pwd=?", (remain, int(gid), str(pwd)))
            ST._DB.commit()
            return f"恭喜！你抢到了 {got}{ST.coin_name()}，魅力+{gain_meili + base_meili}！（剩余{remain}）"
    except Exception:
        pass
    # 降级非原子路径（兼容）
    row = ST._DB.execute("SELECT qq, amount FROM redpacks WHERE gid=? AND pwd=?", (int(gid), str(pwd))).fetchone()
    if not row:
        return "口令错误或红包不存在！"
    if int(row[0]) == int(qq):
        return "自己不允许抢自己的红包！"
    a = _acct(gid, qq)
    if a.get("redpack_code") == pwd:
        return "你已经抢过这个红包了！"
    cost_tili = ST.cfgi("银行配置", "红包_抢体力", 1)
    gain_meili = ST.cfgi("银行配置", "红包_抢魅力", 10)
    base_meili = ST.cfgi("银行配置", "红包_基本魅力", 1)
    if a.int("stamina") < cost_tili:
        return f"体力不足，抢红包需要{cost_tili}体力！"
    ST.acct_add(gid, qq, "stamina", -cost_tili)
    total = int(row[1])
    got = random.randint(max(1, total // 20), max(1, total // 3))
    ST.coins_add(gid, qq, got)
    ST.acct_add(gid, qq, "charm", gain_meili + base_meili)
    a.set("redpack_code", pwd)
    ST.acct_save(gid, qq)
    return f"恭喜！你抢到了 {got}{ST.coin_name()}，魅力+{gain_meili + base_meili}！"


def _bail_name(tid):
    try:
        from . import slave as SL
        return SL.NOTE_NAMES.get(str(tid), str(tid))
    except Exception:
        return str(tid)


def cmd_bail(gid, qq, target, self_bail=False, kind="保释"):
    """保释/自我保释/劫狱(替他人出狱) 劫狱免费，保释收费"""
    if self_bail or str(target).strip() in ("自己", str(qq)):
        self_bail = True
        tid = qq
    else:
        tid = target
        if not tid:
            return f"请指定{kind}目标，格式：【{kind} @QQ】"
    a = _acct(gid, qq)
    ta = _acct(gid, tid)
    if not _check_jail(ta):
        return f"对方({_bail_name(tid)})没有入狱，不需要{kind}！"
    if not self_bail and _check_jail(a):
        return "你自己都蹲在监狱里了，拿什么解救别人？？发送【我要出狱】试试！"
    # 劫狱免费，仅需少量体力；保释收费
    if kind == "劫狱":
        fee = 0
        tili = ST.cfgi("银行配置", "劫狱消耗体力", 5)
        meli = ST.cfgi("银行配置", "劫狱魅力减少", 0)
        # 劫狱有独立冷却
        ok, mins = _cd(a, "jailbreak_time", ST.cfgi("银行配置", "劫狱间隔", 5), "劫狱")
        if not ok:
            return f"{mins}分钟后再来劫狱吧！"
        a.set("jailbreak_time", _now_s())
    else:
        fee_lo = ST.cfgi("银行配置", "保释金钱下限", 5000)
        fee_hi = ST.cfgi("银行配置", "保释金钱上限", 10000)
        fee = random.randint(fee_lo, fee_hi) if fee_hi > fee_lo else fee_lo
        tili = ST.cfgi("银行配置", "保释消耗体力", 15)
        meli = ST.cfgi("银行配置", "保释魅力减少", 20)
    if fee and ST.coins_get(gid, qq) < fee:
        return f"亲，您的{ST.coin_name()}不足，无法{kind}！{kind}金需要{fee}{ST.coin_name()}！"
    if tili and a.int("stamina") < tili:
        return f"亲，您的体力不足，无法{kind}！{kind}需要{tili}体力！"
    if fee:
        ST.coins_add(gid, qq, -fee)
    if tili:
        ST.acct_add(gid, qq, "stamina", -tili)
    if meli:
        ST.acct_add(gid, qq, "charm", -meli)
    _jail_release(ta)
    ST.acct_save(gid, qq)
    if self_bail:
        return (f"保释成功！花费{fee}{ST.coin_name()}、{tili}体力，魅力-{meli}。\r\n"
                "你现在可以出狱了！希望你以后能够洗心革面，多做好事别犯罪！")
    if kind == "劫狱":
        cost_txt = f"花费{fee}{ST.coin_name()}、{tili}体力" if fee or tili else "无消耗"
        meli_txt = f"魅力-{meli}" if meli else ""
        return (f"劫狱成功！{cost_txt} {meli_txt}\r\n"
                f"成功救出 <{_bail_name(tid)}>！侠义之举，令人敬佩！")
    return (f"保释成功！花费{fee}{ST.coin_name()}、{tili}体力，魅力-{meli}。\r\n"
            f"<{_bail_name(tid)}> 现在可以出狱了！")


def cmd_out_jail(gid, qq):
    """我要出狱: 到期自动释放 → 自由身; 未到期 → 提示剩余刑期/越狱/保释"""
    a = _acct(gid, qq)
    if not _check_jail(a):
        return "恭喜！您的刑期已满，现在是自由身了，希望你以后能够洗心革面，多做好事别犯罪！\r\n什么？还想到监狱里过把瘾？那就去打劫或者赌博吧！"
    left = _jail_left(a)
    return (f"距离出狱时间还剩{left}分钟，等不了这么久？\r\n"
            f"你可以铤险越狱，发送【我要越狱】！也可以花钱消灾保释自己，发送【自我保释】！\r\n"
            f"还可以向好友求助(【劫狱 @QQ】)！")


def cmd_jailbreak(gid, qq):
    """我要越狱: 15秒间隔，单次牢狱最多10次，失败不加刑期"""
    a = _acct(gid, qq)
    if not _check_jail(a):
        return "您现在已经是自由身了，无需越狱！"
    # 15秒间隔
    last = a.get("escape_timestamp", "")
    try:
        if last and time.time() - float(last) < 15:
            left = int(15 - (time.time() - float(last))) + 1
            return f"越狱操作太频繁，请{left}秒后再试！"
    except Exception:
        pass
    # 单次牢狱最多10次
    cnt = int(a.get("escape_attempts", "0") or "0")
    if cnt >= 10:
        return "本轮牢狱越狱次数已达10次上限，请等待刑满或寻求保释/劫狱！"
    tili = ST.cfgi("银行配置", "越狱消耗体力", 5)
    meli = ST.cfgi("银行配置", "越狱魅力减少", 5)
    prob = ST.cfgi("银行配置", "越狱成功概率", 25)
    if a.int("stamina") < tili:
        return f"亲，您的体力不足，无法越狱！越狱需要{tili}体力！"
    ST.acct_add(gid, qq, "stamina", -tili)
    a.set("escape_timestamp", str(time.time()))
    a.set("escape_attempts", str(cnt + 1))
    if random.random() * 100 < prob:
        _jail_release(a)
        a.set("escape_attempts", "0")
        ST.acct_save(gid, qq)
        return f"越狱成功！扣除{tili}体力，你重获自由~"
    ST.acct_add(gid, qq, "charm", -meli)
    # 失败不加刑期（需求33）
    ST.acct_save(gid, qq)
    return f"越狱失败！扣除{tili}体力，魅力-{meli}，未增加刑期，再接再厉！"


def cmd_go_jail(gid, qq):
    """我要进监狱: 主动入狱10分钟，增加体力，每日限5次"""
    a = _acct(gid, qq)
    if _check_jail(a):
        return "您已在监狱中，无需再次入狱！"
    key = f"jailgo_{gid}_{qq}_{dt.date.today()}"
    cnt = int(ST.recall_get(key, "0") or 0)
    if cnt >= 5:
        return "亲，您今日主动入狱次数已达上限(5次)！"
    add_stam = ST.cfgi("银行配置", "进监狱增加体力", 10)
    if add_stam <= 0:
        add_stam = 10
    _jail_put(a, 10)
    ST.acct_add(gid, qq, "stamina", add_stam)
    ST.recall_set(key, str(cnt + 1))
    ST.acct_save(gid, qq)
    left = 10
    return f"成功入狱{left}分钟！获得{add_stam}点体力，今日已入狱{cnt+1}/5次，好好反省吧！"


def cmd_sell_slave(gid, qq, target):
    """打劫个人: 按配置概率/体力/金额, 失败扣魅力+入狱"""
    if not target:
        return "亲，您的格式有误，打劫格式为：【打劫 @QQ】！"
    if str(target) == str(qq):
        return "亲，无法对自己实施打劫！"
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    ta = _acct(gid, target)
    if _check_jail(ta):
        return "对方还在监狱中，无法对他实行打劫！"
    cs = ST.cfgi("银行配置", "打劫消耗体力", 20)
    if a.int("stamina") < cs:
        return "亲，您的体力不足，无法实施打劫！"
    if ST.coins_get(gid, qq) < 500:
        return f"亲，您的{ST.coin_name()}不足，无法实施打劫！"
    if ST.coins_get(gid, target) < 100:
        return "亲，对方是个穷光蛋，无法对他实施打劫！"
    ok, mins = _cd(a, "rob_time", ST.cfgi("银行配置", "打劫关押时间", 5), "打劫")
    if not ok:
        return f"{mins}分钟后再来打劫吧！"
    prob = ST.cfgi("银行配置", "打劫成功概率", 50)
    lo = ST.cfgi("银行配置", "打劫金钱下限", 1000)
    hi = ST.cfgi("银行配置", "打劫金钱上限", 100000)
    meli = ST.cfgi("银行配置", "打劫魅力减少", 3)
    jail_mins = ST.cfgi("银行配置", "打劫关押时间", 5)
    # 原子化：体力/魅力/双钱包同事务
    try:
        with ST._LOCK:
            cur_st = ST.acct(gid, qq).int("stamina")
            if cur_st < cs:
                return "亲，您的体力不足，无法实施打劫！"
            cur_money = ST.coins_get(gid, qq)
            if cur_money < 500:
                return f"亲，您的{ST.coin_name()}不足，无法实施打劫！"
            a2 = ST.acct(gid, qq)
            a2.set("stamina", str(cur_st - cs))
            a2.set("rob_time", _now_s())
            if random.random() * 100 < prob:
                victim_money = ST.coins_get(gid, target)
                loot = min(victim_money, random.randint(lo, hi))
                if loot <= 0:
                    ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a2.kv, ensure_ascii=False)))
                    a2.dirty = False
                    ST._DB.commit()
                    return "对方是个穷光蛋，无法对他实施打劫！"
                src_cur = cur_money
                dst_cur = victim_money
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), src_cur + loot))
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(target), max(0, dst_cur - loot)))
                ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a2.kv, ensure_ascii=False)))
                a2.dirty = False
                ST._DB.commit()
                tn = _disp_name(target, gid)
                return f"打劫成功！你从 {tn} 处劫走{loot}{ST.coin_name()}！"
            else:
                # 失败
                fine = min(1000, cur_money)
                new_money = max(0, cur_money - fine)
                cur_mei = a2.int("charm")
                a2.set("charm", str(max(0, cur_mei - meli)))
                a2.set("jail", "1")
                a2.set("jail_start", _now_s())
                a2.set("release_timestamp", str(int(__import__("time").time()) + int(jail_mins) * 60))
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), new_money))
                ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a2.kv, ensure_ascii=False)))
                a2.dirty = False
                ST._DB.commit()
                return (f"打劫失败！实施打劫时被抓！被关监狱{jail_mins}分钟，\r\n"
                        f"罚款{fine}{ST.coin_name()}，魅力-{meli}！")
    except Exception:
        pass
    ST.acct_add(gid, qq, "stamina", -cs)
    a.set("rob_time", _now_s())
    if random.random() * 100 < prob:
        loot = min(ST.coins_get(gid, target), random.randint(lo, hi))
        ST.coins_add(gid, target, -loot)
        ST.coins_add(gid, qq, loot)
        tn = _disp_name(target, gid)
        return f"打劫成功！你从 {tn} 处劫走{loot}{ST.coin_name()}！"
    ST.acct_add(gid, qq, "charm", -meli)
    fine = min(1000, ST.coins_get(gid, qq))
    ST.coins_add(gid, qq, -fine)
    _jail_put(a, jail_mins)
    return (f"打劫失败！实施打劫时被抓！被关监狱{jail_mins}分钟，\r\n"
            f"罚款{fine}{ST.coin_name()}，魅力-{meli}！")


# ---- 统一入口 ----
def handle(gid, qq, raw):
    text = (raw or "").strip()
    if not text:
        return None
    if text in ST.wake("银行系统", "银行系统"):
        return _MENU
    # 鲁棒转账目标解析: 依次尝试 ST.parse_at -> CQ -> @QQ数字 -> @名字 -> 纯QQ
    target = None
    t1, r1 = _extract_transfer_target(text)
    if t1:
        target = t1
        text = r1
    else:
        # 纯QQ字符串兜底 (仅对需要目标的指令)
        if any(text.startswith(p) for p in ("转账", "打劫", "劫狱", "保释")):
            m = re.search(r"\b(\d{5,12})\b", text)
            if m:
                target = m.group(1)
                text = text.replace(m.group(0), "", 1).strip()
        # 同时兼容 @昵称 形式的数字后剩余文本已由 _extract_transfer_target 处理
        pass

    # 若目标已提取但 text 仍包含“转账”前缀，保留以便后续命令判断
    # 对 “@光 100” 这种无前缀隐式转账，text 此时为 “100”，remaining 为 “100”
    # 需要在后续判断中兼容
    n = 0
    mms = re.findall(r"(\d+)", text)
    if mms:
        n = int(mms[-1])

    if text.startswith("存款"):
        return cmd_deposit(gid, qq, n)
    if text.startswith("强制取款"):
        return cmd_force_withdraw(gid, qq, n)
    if text.startswith("取款"):
        return cmd_withdraw(gid, qq, n)
    if text.startswith("转账"):
        if not target:
            return "请指定转账目标，格式：【转账 @QQ 金额】"
        return cmd_transfer(gid, qq, target, n)

    if text.startswith("赌博"):
        return cmd_gamble(gid, qq, n)
    if text.startswith("打劫银行"):
        return cmd_rob_zone(gid, qq)
    if text.startswith("打劫"):
        return cmd_sell_slave(gid, qq, target)
    if text.startswith("发红包"):
        rest = text[3:].strip()
        parts = re.split(r"\s+", rest)
        amt_s = parts[0] if parts else ""
        m_amt = re.search(r"(\d+)", amt_s)
        pwd = " ".join(parts[1:]) if len(parts) > 1 else None
        if not m_amt:
            return "亲，发红包格式为：【发红包 金额】或【发红包 金额 口令】！"
        return cmd_redpack(gid, qq, int(m_amt.group(1)), pwd)
    if text.startswith("抢红包"):
        pwd = text[3:].strip()
        if not pwd:
            # 兼容 “抢红包 口令” 中间多空格
            pwd = re.sub(r"^抢红包\s*", "", raw or "").strip()
        return cmd_recv_red(gid, qq, pwd)
    # 修复抢红包: 允许直接输入口令而无需前缀
    # 若当前无其他指令匹配，且存在红包且输入等于口令，则视为抢红包
    if text and not text.startswith(("存款", "取款", "强制取款", "转账", "赌博", "打劫", "发红包", "抢红包", "我要", "劫狱", "保释", "自我")):
        # 纯口令尝试
        try:
            if ST._DB is not None:
                row = ST._DB.execute("SELECT pwd FROM redpacks WHERE gid=? AND pwd=?", (int(gid), text.strip())).fetchone()
                if row:
                    return cmd_recv_red(gid, qq, text.strip())
        except Exception:
            pass
    if text in ("我要进监狱", "进监狱"):
        return cmd_go_jail(gid, qq)
    if text in ("我要出狱", "出狱"):
        return cmd_out_jail(gid, qq)
    if text in ("我要越狱", "越狱"):
        return cmd_jailbreak(gid, qq)
    if text.startswith("劫狱"):
        return cmd_bail(gid, qq, target or text[2:].strip(), kind="劫狱")
    if text.startswith("保释"):
        return cmd_bail(gid, qq, target or text[2:].strip())
    if text.startswith("自我保释"):
        return cmd_bail(gid, qq, qq, self_bail=True)
    # 隐式红包口令再兜底(处理 raw 中无前缀但包含口令的情况)
    try:
        if raw and ST._DB is not None:
            cand = (raw or "").strip()
            # 去除可能的 CQ 码后剩余纯口令
            cand = re.sub(r"\[CQ:[^\]]+\]", "", cand).strip()
            if cand and len(cand) <= 10:
                row = ST._DB.execute("SELECT pwd FROM redpacks WHERE gid=? AND pwd=?", (int(gid), cand)).fetchone()
                if row:
                    return cmd_recv_red(gid, qq, cand)
    except Exception:
        pass
    return None
