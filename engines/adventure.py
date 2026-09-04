# -*- coding: utf-8 -*-
"""冒险系统 - 对齐原版: 文字冒险/死亡选择题/萌萌系统, 9 地图, 选择N作答, 消耗体力金钱, 复活币
机制: 发送【冒险 地图】开启一轮(扣体力+金钱) -> 返回长剧情+三选一+「请作出您的选择!【选择 序号】」
-> 发送【选择 N】触发随机事件分支(奖励金钱/复活币/惩罚/神秘遭遇) -> 可【结束冒险】消耗复活币; 【当前冒险】【复活币排行】
文案：每地图 300+字沉浸叙事 + 随机事件池 + 选择分支
"""
import random
import time

try:
    from .. import store as ST
except ImportError:
    try:
        from . import store as ST
    except ImportError:
        import store as ST

from .adventure_text import MAPS, CHOICE_LABELS, RANDOM_EVENTS, MAP_SPECIFIC_EVENTS

def _cfg(key, default=""):
    return ST.cfg("冒险配置", key, default)


def _cfgi(key, default=0):
    try:
        return int(float(_cfg(key, default)))
    except Exception:
        return int(default)


def _acct(gid, qq):
    return ST.acct(gid, qq)


def _coin(gid, qq):
    return ST.coins_get(gid, qq)


def _now():
    return int(time.time())


def _cur(gid, qq):
    a = _acct(gid, qq)
    try:
        import json as _j
        return _j.loads(a.get("adventure", "{}") or "{}")
    except Exception:
        return {}


def _save(gid, qq, adv):
    import json as _j
    _acct(gid, qq).set("adventure", _j.dumps(adv, ensure_ascii=False))
    ST.acct_save(gid, qq)


def _revive(gid, qq):
    return _acct(gid, qq).int("revive_coins")


MENU = (
    "⚔️ 冒险系统\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "🗺️ 迷失海岛 死亡医院 灵异舞会 恶魔岛\r\n"
    "🌫️ 里世界 恐怖旅程 雪夜之旅 幽灵谜境\r\n"
    "🌙 入夜暴走\r\n"
    "📖 冒险 地图　🎲 选择 序号\r\n"
    "📋 当前冒险　🧭 结束冒险(消耗复活币)\r\n"
    "🏆 复活币排行\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "💡 发送【冒险 地图】开始冒险，消耗体力+金币"
)


def _build_start_narrative(mapname):
    intro, scene = MAPS[mapname]
    choices = CHOICE_LABELS.get(mapname, ["【选择 1】", "【选择 2】", "【选择 3】"])
    # 组合成长叙事 + 选项
    choice_block = "\r\n".join(f"{c}" for c in choices)
    return (
        f"【{mapname}·启程】\r\n"
        f"{intro}\r\n"
        f"——\r\n{scene}\r\n"
        f"━━━━━━━━━━━━━━\r\n"
        f"抉择时刻：\r\n{choice_block}\r\n"
        f"━━━━━━━━━━━━━━\r\n"
        f"请作出您的选择！指令为【选择 序号】（如 选择 1）\r\n"
        f"💡 提示：不同选择将触发不同随机事件，影响奖励与命运"
    )


def cmd_start(gid, qq, mapname):
    mapname = (mapname or "").strip()
    if not mapname:
        return "请输入冒险地图：冒险 迷失海岛\r\n发送【冒险系统】查看地图列表！"
    if mapname not in MAPS:
        return "亲，不存在该冒险地图，发送【冒险系统】查看地图吧！"
    a = _acct(gid, qq)
    cs = _cfgi("冒险消耗体力", 5)
    if a.int("stamina") < cs:
        return "亲，您的体力不足，无法进行冒险！"
    cost = _cfgi("冒险需要金钱", 1000)
    if _coin(gid, qq) < cost:
        return f"亲，需要{cost}{ST.coin_name()}才能冒险！"
    last = int(ST.recall_get("advt_%s_%s" % (gid, qq), "0") or 0)
    gap = _cfgi("冒险间隔", 60) * 60
    if last and _now() - last < gap:
        return "休息一下，过会儿再冒险吧！"
    ST.recall_set("advt_%s_%s" % (gid, qq), str(_now()))
    ST.acct_add(gid, qq, "stamina", -cs)
    ST.coins_add(gid, qq, -cost)
    adv = {"map": mapname, "round": 1, "ts": _now(), "last_choice": 0}
    _save(gid, qq, adv)
    return _build_start_narrative(mapname)


def _pick_event(mapname, choice_num):
    # 60% 全局池，40% 地图专属，增加代入感
    pool = []
    if random.random() < 0.4 and mapname in MAP_SPECIFIC_EVENTS:
        pool = MAP_SPECIFIC_EVENTS[mapname]
        # 展开为 (text, kind)
    else:
        # 从 RANDOM_EVENTS 随机
        txt, kind, _ = random.choice(RANDOM_EVENTS)
        return txt, kind
    if pool:
        txt, kind = random.choice(pool)
        return txt, kind
    txt, kind, _ = random.choice(RANDOM_EVENTS)
    return txt, kind


def cmd_choose(gid, qq, n):
    adv = _cur(gid, qq)
    if not adv.get("map"):
        return "对不起，您尚未开始冒险，请发送【冒险 地图】开始！"
    m = adv["map"]
    try:
        choice = int(str(n or "").strip() or random.randint(1, 3))
    except Exception:
        choice = random.randint(1, 3)
    if choice not in (1, 2, 3):
        choice = random.randint(1, 3)
    max_round = max(5, _cfgi("最大轮数", 10))
    adv["round"] = int(adv.get("round", 1)) + 1
    adv["last_choice"] = choice
    lo = _cfgi("事件金钱下限", 500); hi = _cfgi("事件金钱上限", 800)
    money = random.randint(lo, hi)
    event_text, kind = _pick_event(m, choice)

    # 根据 kind 与随机分支决定奖励/惩罚
    # 选择影响概率：选 1 偏向 bonus，选 2 平衡，选 3 偏向 trap 但 high reward
    bias = {1: 0.65, 2: 0.5, 3: 0.4}.get(choice, 0.5)
    r = random.random()
    # 结合 bias 调整 kind 的实际走向
    if kind == "bonus":
        # bonus 事件有小概率反转为 trap（冒进惩罚）
        if r > 0.85:
            kind = "trap"
    elif kind == "trap":
        if r < 0.3:
            kind = "bonus"
    # 最终按 bias 再校正
    if r < bias and kind == "trap":
        # 好运抵消陷阱
        kind = "bonus"
    elif r > bias + 0.3 and kind == "bonus":
        kind = "trap"

    if kind == "bonus":
        # 20% 额外复活币
        if random.random() < 0.35:
            ST.coins_add(gid, qq, money)
            ST.acct_add(gid, qq, "revive_coins", 1)
            outcome = f"{event_text}\r\n✨ 关键抉择生效！奖励{money}{ST.coin_name()}，复活币+1（选择{choice}的勇气得到回应）"
        else:
            ST.coins_add(gid, qq, money)
            outcome = f"{event_text}\r\n🎉 你披荆斩棘，获得{money}{ST.coin_name()}！（选择{choice}）"
    elif kind == "neutral":
        outcome = f"{event_text}\r\n—— 你以少量代价换得通行，未得也未失（选择{choice}）"
    else:
        fine = min(random.randint(_cfgi("结局金钱下限", 1500), _cfgi("结局金钱上限", 2000)), _coin(gid, qq))
        if fine:
            ST.coins_add(gid, qq, -fine)
        outcome = f"{event_text}\r\n💀 遭遇陷阱/诅咒，损失{fine}{ST.coin_name()}，狼狈脱险……（选择{choice}的代价）"

    _save(gid, qq, adv)
    if adv["round"] >= max_round:
        rv = _revive(gid, qq)
        reward = int(max(lo, hi) * 1.8)
        ST.coins_add(gid, qq, reward)
        _save(gid, qq, {})
        return (
            f"【{m}·终章】你历经 {max_round} 轮生死抉择，终于走出{ m }的阴霾！\r\n"
            f"{outcome}\r\n"
            f"━━━━━━━━━━━━━━\r\n"
            f"🏆 通关奖励：{reward}{ST.coin_name()}，当前复活币×{rv}\r\n"
            f"冒险已结束，发送【冒险 地图】开启新征程！"
        )
    # 续程：给出下一轮的抉择提示（保持原序更易理解，避免玩家困惑）
    next_choices = CHOICE_LABELS.get(m, ["【选择 1】", "【选择 2】", "【选择 3】"])
    return (
        f"【{m}·第{adv['round']}轮/共{max_round}轮】\r\n"
        f"{outcome}\r\n"
        "━━━━━━━━━━━━━━\r\n"
        "下一抉择：\r\n" + "\r\n".join(next_choices) + "\r\n"
        "继续发送【选择 序号】推进，或【结束冒险】消耗复活币提前结束！"
    )


def cmd_current(gid, qq):
    adv = _cur(gid, qq)
    if not adv.get("map"):
        return "您当前没有进行中的冒险。"
    return ("当前冒险：【%s】第%d轮\r\n上轮选择：%s\r\n拥有复活币：%d个" % (
        adv["map"], adv.get("round", 1), adv.get("last_choice", 0) or "无", _revive(gid, qq)))


def cmd_end(gid, qq):
    adv = _cur(gid, qq)
    if not adv.get("map"):
        return "您当前没有进行中的冒险。"
    if _revive(gid, qq) <= 0:
        return "没有复活币，无法提前结束冒险！"
    ST.acct_add(gid, qq, "revive_coins", -1)
    m = adv["map"]; _save(gid, qq, {})
    return ("【%s】冒险已提前结束！复活币-1，当前还剩%d个" % (m, _revive(gid, qq)))


def cmd_rank(gid, qq):
    if ST._DB is None:
        return "暂无数据。"
    rows = ST._DB.execute("SELECT qq, data FROM accounts WHERE gid=?",
                          (int(gid),)).fetchall()
    lst = []
    for q, data in rows:
        try:
            import json as _j
            a = _j.loads(data)
            rv = int(a.get("revive_coins", 0) or 0)
        except Exception:
            rv = 0
        if rv:
            lst.append((rv, str(q)))
    lst.sort(reverse=True)
    lines = ["---复活币排行---"]
    for i, (rv, q) in enumerate(lst[:10], 1):
        disp = str(q)
        try:
            from . import slave as SL
            disp = SL.NOTE_NAMES.get(str(q), str(q))
        except Exception:
            pass
        lines.append("%d. %s　%d个" % (i, disp, rv))
    return "\r\n".join(lines) if lines[1:] else "暂无复活币~"


def handle(gid, qq, raw):
    text = (raw or "").strip()
    if not text:
        return None
    if text in ST.wake("冒险系统", "冒险系统"):
        return MENU
    if text == "当前冒险":
        return cmd_current(gid, qq)
    if text == "结束冒险":
        return cmd_end(gid, qq)
    if text == "复活币排行":
        return cmd_rank(gid, qq)
    if text.startswith("冒险") or text.startswith("adventure"):
        return cmd_start(gid, qq, text[2:].strip() if text.startswith("冒险") else text[9:].strip())
    if text.startswith("选择"):
        return cmd_choose(gid, qq, text[2:].strip())
    return None
