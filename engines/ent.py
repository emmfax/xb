# -*- coding: utf-8 -*-
"""娱乐系统(本地词库驱动, 词库可扩展): 抽签/扔炸弹/接龙/急转弯/猜字谜/二四点/答题/猜数/猜拳
已删除(需求): 笑话/鸡汤/冷知识/舔狗日记/神回复/藏头诗/抽签 及各项媒体占位
会话游戏(接龙/答题/猜数/字谜/急转弯/二四点)按 (gid,qq) 分会话, 只有开局者能作答,
其他玩家需在开局后 30 秒内发送【加入接龙/加入答题/加入猜数/加入二四点】加入同一局。胜者可获金币/魅力奖励。
"""
import ast as _ast
import random
import re
import time


def _safe_eval_24(expr):
    """安全计算二四点算式：仅允许数字 + - * / ( ) ，防注入"""
    try:
        # 仅允许数字、运算符、括号、空格
        if not re.fullmatch(r"[\d\s+\-*/().×÷（）]+", expr):
            return None
        # 统一符号
        expr = expr.replace("×", "*").replace("÷", "/").replace("（", "(").replace("）", ")")
        node = _ast.parse(expr, mode="eval")
        # 兼容 Python3.12+：Constant 替代 Num，动态构造 allowed
        allowed_types = [_ast.Expression, _ast.BinOp, _ast.UnaryOp, _ast.Constant, _ast.Add, _ast.Sub, _ast.Mult, _ast.Div, _ast.USub, _ast.UAdd, _ast.Mod, _ast.Pow, _ast.Load]
        try:
            allowed_types.append(_ast.Num)
        except Exception:
            pass
        allowed = tuple(allowed_types)
        for n in _ast.walk(node):
            if not isinstance(n, allowed):
                # 禁止 Call/Name/Attribute 等
                if isinstance(n, (_ast.Call, _ast.Name, _ast.Attribute, _ast.Subscript)):
                    return None
                return None
        # 禁止幂运算大数
        if "**" in expr:
            return None
        return eval(compile(node, "<24>", "eval"), {"__builtins__": {}}, {})
    except Exception:
        return None

try:
    from .. import store as ST
except ImportError:
    try:
        from . import store as ST
    except ImportError:
        import store as ST

_MENU = (
    "🎮 娱乐系统\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "🎋 抽签　　　　　💣 扔炸弹\r\n"
    "🧩 开始接龙　　　🤔 开始急转弯\r\n"
    "🔤 开始猜字谜　　🎲 开始猜数\r\n"
    "❓ 开始答题　　　🃏 二四点\r\n"
    "✊ 猜拳 石头/剪刀/布\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "💡 发送对应指令即可游玩"
)


def _fee(gid, qq, kind):
    """娱乐功能消耗金币(娱乐配置__<kind>造价=0 免费)"""
    try:
        c = int(float(ST.cfg("娱乐配置", kind + "造价", "0") or "0"))
    except Exception:
        c = 0
    if c <= 0:
        return None
    if ST.coins_get(gid, qq) < c:
        return "笑~你没有那么多%s（%s需%d）" % (ST.coin_name(), kind, c)
    ST.coins_add(gid, qq, -c)
    return None


def _ent_cost(gid, qq, prefix):
    """通用娱乐消耗：需要金钱 + 消耗体力（0=免费）"""
    need = ST.cfgi("娱乐配置", prefix + "需要金钱", 0)
    tili = ST.cfgi("娱乐配置", prefix + "消耗体力", 0)
    if need and ST.coins_get(gid, qq) < need:
        return f"笑~你没有那么多{ST.coin_name()}（{prefix}需{need}）"
    if tili and ST.acct(gid, qq).int("stamina") < tili:
        return f"体力不足，{prefix}需要{tili}体力！"
    if need:
        ST.coins_add(gid, qq, -need)
    if tili:
        ST.acct_add(gid, qq, "stamina", -tili)
    return None


# ---- 词库/题库（内置可扩展，支持 WebUI 自定义） ----
CHAIN_WORDS = [
    "一帆风顺", "顺水推舟", "舟车劳顿", "顿开茅塞", "塞翁失马", "马到成功",
    "功成名就", "就事论事", "事半功倍", "倍道而行", "行云流水", "水到渠成",
    "成竹在胸", "胸有成竹", "竹报平安", "安居乐业", "业精于勤", "勤能补拙",
    "拙嘴笨舌", "舌战群儒", "儒雅风流", "流光溢彩", "彩云追月", "月白风清",
    "清风明月", "月明星稀", "稀世珍宝", "宝刀未老", "老当益壮", "壮志凌云",
    "云开见日", "日新月异", "异口同声", "声东击西", "西窗剪烛", "烛光摇曳",
    "曳尾涂中", "中流砥柱", "柱石之坚", "坚定不移", "移花接木", "木已成舟",
    "舟中敌国", "国泰民安", "安步当车", "车水马龙", "龙飞凤舞", "舞文弄墨",
    "墨守成规", "规行矩步", "步步为营", "营私舞弊", "弊绝风清", "清净无为",
    "为所欲为", "为虎作伥", "伥鬼不散", "散兵游勇", "勇往直前", "前程似锦",
    "锦上添花", "花好月圆", "圆满完成", "成群结队", "队友合作", "作壁上观",
]

TRICK = [
    ("什么门永远关不上？", "球门"),
    ("什么东西越洗越脏？", "水"),
    ("什么东西有头无脚？", "图钉"),
    ("什么马不能骑？", "海马"),
    ("什么书在书店买不到？", "遗书"),
    ("什么瓜不能吃？", "傻瓜"),
    ("什么布剪不断？", "瀑布"),
    ("什么英文字母最多人喜欢听？", "CD"),
    ("哪一个月有28天？", "每个月"),
    ("小华在偷偷做作业被发现，为什么老师没骂他？", "他在办公室做"),
    ("什么东西倒立后会增加一半？", "6"),
    ("什么东西有5个头但人不觉的它怪呢？", "手脚"),
    ("一个人在沙滩上行走，回头却看不见脚印，为什么？", "倒着走"),
    ("什么车最长？", "堵车"),
    ("什么东西越用越少？", "常识"),
    ("为什么企鹅的肚子是白的？", "手短擦不到"),
    ("什么东西没吃之前是绿的，吃下去是红的，吐出来是黑的？", "西瓜"),
    ("森林里有一条眼镜蛇，可是它从来不咬人，为什么？", "森林里没人"),
    ("什么房子最多人进去却没人出来？", "厕所"),
    ("什么东西天气越热，它爬得越高？", "温度计"),
]

MIRI = [
    ("一口咬掉牛尾巴（打一字）", "告"),
    ("大雨落在横山上（打一字）", "雪"),
    ("十张口，一颗心（打一字）", "思"),
    ("七十二小时（打一字）", "晶"),
    ("一月七日（打一字）", "脂"),
    ("一口咬定（打一字）", "交"),
    ("武（打一字）", "斐"),
    ("九十九（打一字）", "白"),
    ("上下难分（打一字）", "卡"),
    ("田中（打一字）", "十"),
    ("一口吃掉牛尾巴少一点（打一字）", "告"),
    ("一点一横长，一撇到南洋，南洋有个人，只有一寸长（打一字）", "府"),
    ("四面都是山，山山皆相连（打一字）", "田"),
    ("一字十三点，难在如何点（打一字）", "汁"),
    ("皇帝新衣（打一字）", "袭"),
    ("拱猪入门（打一字）", "阂"),
    ("守门员（打一字）", "闪"),
    ("一口咬掉多半截（打一字）", "名"),
]

QUIZ = [
    ("中国最长的河流是？", "长江"),
    ("太阳系最大的行星是？", "木星"),
    ("一公斤棉花和一公斤铁哪个重？", "一样重"),
    ("一年有多少个星期？", "52"),
    ("中国的首都是哪里？", "北京"),
    ("世界上最高的山峰是？", "珠穆朗玛峰"),
    ("一年有多少天（平年）？", "365"),
    ("水在多少度结冰？", "0度"),
    ("中国四大发明不包括哪一个？火药/指南针/造纸术/印刷术/蒸汽机", "蒸汽机"),
    ("三原色是哪三种？", "红黄蓝"),
    ("人体最大的器官是？", "皮肤"),
    ("光速大约是多少万公里每秒？", "30"),
    ("哪个星球被称为红色星球？", "火星"),
    ("《西游记》中孙悟空的兵器叫什么？", "金箍棒"),
    ("一个正方体有几个面？", "6"),
    ("北京奥运会是哪一年？", "2008"),
    ("我国国歌叫什么？", "义勇军进行曲"),
    ("世界上最大的海洋是？", "太平洋"),
    ("九九乘法表 7*8 等于？", "56"),
    ("人体有多少块骨头？", "206"),
    ("月亮围绕什么转？", "地球"),
    ("中国古代四大美女之一貂蝉对应？", "貂蝉"),
    ("清明上河图是谁的作品？", "张择端"),
    ("元素周期表第一个元素是？", "氢"),
]


def _parse_custom_words(raw):
    """解析自定义接龙词库：支持 | 、换行 、，、, 分隔"""
    if not raw or not str(raw).strip():
        return []
    s = str(raw).strip()
    # 尝试 JSON 数组
    if s.startswith("["):
        try:
            import json as _json
            arr = _json.loads(s)
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass
    # 按分隔符切分
    import re as _re2
    parts = _re2.split(r"[\r\n\|，,、;；]+", s)
    out = []
    for p in parts:
        p = p.strip().strip("【】[]（）()\"' ")
        if p and 2 <= len(p) <= 8:
            out.append(p)
    return out


def _parse_custom_qa(raw):
    """解析自定义题库：每行 问题|答案 或 问题=答案 或 JSON"""
    if not raw or not str(raw).strip():
        return []
    s = str(raw).strip()
    if s.startswith("["):
        try:
            import json as _json
            arr = _json.loads(s)
            res = []
            for it in arr:
                if isinstance(it, (list, tuple)) and len(it) >= 2:
                    res.append((str(it[0]).strip(), str(it[1]).strip()))
                elif isinstance(it, dict):
                    q = it.get("q") or it.get("question") or it.get("题干") or ""
                    a = it.get("a") or it.get("answer") or it.get("答案") or ""
                    if q and a:
                        res.append((str(q).strip(), str(a).strip()))
            if res:
                return res
        except Exception:
            pass
    out = []
    for line in re.split(r"[\r\n]+", s):
        line = line.strip()
        if not line:
            continue
        # 支持 | ｜ -> 分隔、 = 、:、：、->、—
        m = re.split(r"\s*[\|｜]\s*|\s*=\s*|\s*:\s*|：|->|—", line, maxsplit=1)
        if len(m) >= 2 and m[0].strip() and m[1].strip():
            out.append((m[0].strip(), m[1].strip()))
        elif " " in line:
            # 尝试最后空格分隔
            parts = line.rsplit(None, 1)
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                out.append((parts[0].strip(), parts[1].strip()))
    return out


def _get_chain_words():
    base = list(CHAIN_WORDS)
    try:
        raw = ST.cfg("娱乐配置", "接龙词库", "")
        custom = _parse_custom_words(raw)
        if custom:
            # 去重合并
            seen = set(base)
            for w in custom:
                if w not in seen:
                    base.append(w)
                    seen.add(w)
    except Exception:
        pass
    return base


def _get_trick():
    base = list(TRICK)
    try:
        raw = ST.cfg("娱乐配置", "急转弯题库", "")
        custom = _parse_custom_qa(raw)
        if custom:
            base = base + custom
    except Exception:
        pass
    return base


def _get_miri():
    base = list(MIRI)
    try:
        raw = ST.cfg("娱乐配置", "猜字谜题库", "")
        custom = _parse_custom_qa(raw)
        if custom:
            base = base + custom
    except Exception:
        pass
    return base


def _get_quiz():
    base = list(QUIZ)
    try:
        raw = ST.cfg("娱乐配置", "答题题库", "")
        custom = _parse_custom_qa(raw)
        if custom:
            base = base + custom
    except Exception:
        pass
    return base


# ---- 单游戏锁（同一群同时只能一个会话游戏） ----
def _active_game(gid):
    try:
        return ST.recall_get(f"ent_game_{gid}", "") or ""
    except Exception:
        return ""


def _set_active_game(gid, label):
    try:
        ST.recall_set(f"ent_game_{gid}", str(label))
    except Exception:
        pass


def _clear_active_game(gid):
    try:
        ST.recall_set(f"ent_game_{gid}", "")
    except Exception:
        pass


_GAME_KIND_MAP = {
    "接龙": "chain",
    "急转弯": "trick",
    "猜字谜": "miri",
    "字谜": "miri",
    "猜数": "guessnum",
    "答题": "quiz",
    "二四点": "game24",
}


def _clean_expired_game(gid, max_seconds=180):
    """自动清理超时闲置或异常遗留的会话游戏锁，避免单群永久卡死"""
    cur = _active_game(gid)
    if not cur:
        return False
    kind = _GAME_KIND_MAP.get(cur)
    if not kind:
        _clear_active_game(gid)
        return True
    try:
        start_val = ST.recall_get(f"{kind}_start_{gid}", "0")
        try:
            start_ts = int(start_val or "0")
        except Exception:
            start_ts = 0
        now = int(time.time())
        # start_ts <= 0 属于脏数据/孤儿锁，或者距离开局超过 max_seconds，均清理
        if start_ts <= 0 or (now - start_ts) > max_seconds:
            owner = ST.recall_get(f"{kind}_owner_{gid}", "")
            ST.recall_set(f"{kind}_owner_{gid}", "")
            ST.recall_set(f"{kind}_players_{gid}", "")
            ST.recall_set(f"{kind}_start_{gid}", "")
            if owner:
                ST.recall_set(f"{kind}_{gid}_{owner}", "")
            if kind == "chain":
                ST.recall_set(f"chain_{gid}", "")
                ST.recall_set(f"chain_used_{gid}", "")
                ST.recall_set(f"chain_last_qq_{gid}", "")
                ST.recall_set(f"chain_last_time_{gid}", "")
                ST.recall_set(f"chain_owner_{gid}", "")
                ST.recall_set(f"chain_players_{gid}", "")
                ST.recall_set(f"chain_start_{gid}", "")
            elif kind == "game24":
                ST.recall_set(f"game24_{gid}_{owner}", "")
                ST.recall_set(f"game24_players_{gid}", "")
                ST.recall_set(f"game24_start_{gid}", "")
                ST.recall_set(f"game24_owner_{gid}", "")
            _clear_active_game(gid)
            return True
    except Exception:
        pass
    return False


def _check_single_game(gid, new_label):
    _clean_expired_game(gid)
    cur = _active_game(gid)
    if cur and cur != new_label:
        return f"已有进行中的【{cur}】游戏，请先结束当前游戏再开新局！（发送【退出{cur}】结束）"
    # 同类型已在进行中：检查是否已经无互动超过 60 秒，若超过则自动刷新重开
    if cur == new_label:
        kind = _GAME_KIND_MAP.get(cur, "")
        if kind:
            start_val = ST.recall_get(f"{kind}_start_{gid}", "0")
            try:
                start_ts = int(start_val or "0")
            except Exception:
                start_ts = 0
            if start_ts <= 0 or (int(time.time()) - start_ts) > 60:
                _clean_expired_game(gid, max_seconds=0)
                return None
        return f"已有进行中的【{cur}】游戏，请先完成或退出后再开新局！（发送【退出{cur}】可重新开局）"
    return None


# ---- 24点可解性求解器 ----
# 缓存千群并发下重复 4 数判定（最多 13^4=28561 种），避免每局递归 43k 次
try:
    from functools import lru_cache as _lru24
except Exception:
    def _lru24(*a, **k):
        def d(f): return f
        return d

@_lru24(maxsize=8192)
def _can_make_24_cached(key):
    nums_f = [float(x) for x in key]
    def helper(arr):
        if len(arr) == 1:
            return abs(arr[0] - 24) < 1e-6
        # 去重：相同数值对避免重复计算
        seen = set()
        for i in range(len(arr)):
            for j in range(len(arr)):
                if i == j:
                    continue
                a, b = arr[i], arr[j]
                pair = (a,b)
                if pair in seen:
                    continue
                seen.add(pair)
                rest = [arr[k] for k in range(len(arr)) if k != i and k != j]
                for c in (a+b, a-b, a*b, a/b if abs(b) > 1e-9 else None):
                    if c is None:
                        continue
                    if helper(tuple(rest) + (c,)):
                        return True
        return False
    return helper(tuple(nums_f))

def _can_make_24(nums):
    """判断4个数是否能通过 +-*/ 括号算出24（浮点容差）带缓存"""
    try:
        key = tuple(sorted(int(x) for x in nums))
        return _can_make_24_cached(key)
    except Exception:
        return False


_PRE_SOLVABLE = None
def _ensure_pre_solvable():
    global _PRE_SOLVABLE
    if _PRE_SOLVABLE is not None:
        return _PRE_SOLVABLE
    # 轻量预生成：仅用 5 兜底+ 20 随机尝试，避免首次 800 次递归 2s 卡顿
    pool = [[3, 3, 6, 6], [1, 4, 4, 4], [2, 3, 5, 7], [1, 2, 3, 6], [4, 4, 4, 4]]
    seen = {tuple(sorted(x)) for x in pool}
    for _ in range(20):
        cand = [random.randint(1, 13) for _ in range(4)]
        key = tuple(sorted(cand))
        if key in seen:
            continue
        if _can_make_24(cand):
            pool.append(cand)
            seen.add(key)
            if len(pool) >= 20:
                break
    _PRE_SOLVABLE = pool
    return pool

def _generate_solvable_24(max_try=100):
    # 优先预生成池 O(1)，避免每局随机试算 100 次
    try:
        pool = _ensure_pre_solvable()
        if pool:
            return random.choice(pool)
    except Exception:
        pass
    for _ in range(max_try):
        nums = [random.randint(1, 13) for _ in range(4)]
        if _can_make_24(nums):
            return nums
    fallback = [[3, 3, 6, 6], [1, 4, 4, 4], [2, 3, 5, 7], [1, 2, 3, 6], [4, 4, 4, 4]]
    return random.choice(fallback)


def cmd_bomb(gid, qq, arg):
    """扔炸弹: 花费+体力掷炸弹, 按概率命中目标(命中则禁言目标，需平台支持)"""
    import re as _re2
    a = ST.acct(gid, qq)
    cost = ST.cfgi("娱乐配置", "扔炸弹_需要金钱", 30000)
    tili = ST.cfgi("娱乐配置", "扔炸弹_消耗体力", 20)
    meli = ST.cfgi("娱乐配置", "扔炸弹_魅力减少", 5)
    nmin = ST.cfgi("娱乐配置", "扔炸弹_个数下限", 1)
    nmax = ST.cfgi("娱乐配置", "扔炸弹_个数上限", 2)
    prob = ST.cfgi("娱乐配置", "扔炸弹_成功概率", 70)
    mute_lo = ST.cfgi("娱乐配置", "扔炸弹_禁言下限", 5)
    mute_hi = ST.cfgi("娱乐配置", "扔炸弹_禁言上限", 10)
    # 解析目标（必须指定 @QQ / @昵称 / CQ码）
    target = None
    if arg:
        m = _re2.search(r"\[CQ:at,qq=(\d+)[^\]]*\]", arg)
        if m:
            target = m.group(1)
        else:
            t, _ = ST.parse_at(arg)
            if t:
                target = t
            else:
                # 纯数字 QQ
                mm = _re2.search(r"(\d{5,12})", arg)
                if mm:
                    target = mm.group(1)
    if not target:
        return "请指定扔炸弹目标，格式：扔炸弹 @QQ"
    if ST.coins_get(gid, qq) < cost:
        return "笑~你没有那么多%s（扔炸弹需%d）" % (ST.coin_name(), cost)
    if a.int("stamina") < tili:
        return "体力不足，扔炸弹需要%d体力！" % tili
    ST.coins_add(gid, qq, -cost)
    ST.acct_add(gid, qq, "stamina", -tili)
    n = random.randint(nmin, nmax)
    if random.randint(1, 100) <= prob:
        mute = random.randint(mute_lo, mute_hi)
        # 已接入 OneBot 禁言
        return f"__XB_PLATFORM__|mute|{target}|{mute*60}__TEXT__💣 轰！你扔出{n}颗炸弹命中目标！\r\n目标被禁言{mute}分钟！花费{cost}{ST.coin_name()}、{tili}体力"
    ST.acct_add(gid, qq, "charm", -meli)
    return (f"💣 你扔出{n}颗炸弹，可惜被躲开了！\r\n"
            f"魅力-{meli}，花费{cost}{ST.coin_name()}、{tili}体力")





def _start_24(gid, qq):
    # 二四点开局消耗（可配，默认 0/2 兼容旧版）
    err = _ent_cost(gid, qq, "二四点")
    if err:
        return err
    nums = _generate_solvable_24()
    ST.recall_set(f"game24_{gid}_{qq}", "|".join(map(str, nums)))
    ST.recall_set(f"game24_owner_{gid}", str(qq))
    ST.recall_set(f"game24_start_{gid}", str(int(time.time())))
    ST.recall_set(f"game24_players_{gid}", "")
    _set_active_game(gid, "二四点")
    return ("🃏 二四点开始！用 + - * / 和括号把下面 4 个数算出 24：\r\n"
            "【%s】\r\n回复你的算式即可！（其他玩家30秒内发送【加入二四点】加入，发送【退出二四点】结束）"
            % " ".join(map(str, nums)))


def handle(gid, qq, raw):
    text = (raw or "").strip()
    if not text:
        return None
    # 自动检查并清理群内闲置超时或异常遗留的游戏锁
    _clean_expired_game(gid)
    if text in ST.wake("娱乐系统", "娱乐系统"):
        return _MENU
    if text.startswith("抽签"):
        _e = _fee(gid, qq, "抽签")
        if _e:
            return _e
        # 每日一次
        a = ST.acct(gid, qq)
        today = ST.recall_get(f"chouqian_{gid}_{qq}", "")
        cur_day = time.strftime("%Y-%m-%d")
        if today == cur_day:
            return "今日已抽过签，明日再来试试手气吧～"
        ST.recall_set(f"chouqian_{gid}_{qq}", cur_day)
        n = random.randint(1, 100)
        if n <= 15:
            r = "大吉"
            reward = ST.cfgi("娱乐配置", "抽签大吉奖励", 888)
            ST.coins_add(gid, qq, reward)
            ST.acct_add(gid, qq, "charm", 2)
            return f"你抽到了【{r}】🎉 今日运势极佳！奖励{reward}{ST.coin_name()} 魅力+2，好好把握哦～"
        elif n <= 40:
            r = "上签"
            reward = ST.cfgi("娱乐配置", "抽签上签奖励", 388)
            ST.coins_add(gid, qq, reward)
            ST.acct_add(gid, qq, "charm", 1)
            return f"你抽到了【{r}】✨ 运势不错！奖励{reward}{ST.coin_name()} 魅力+1"
        elif n <= 70:
            r = "中签"
            reward = ST.cfgi("娱乐配置", "抽签中签奖励", 88)
            if reward:
                ST.coins_add(gid, qq, reward)
            return f"你抽到了【{r}】 平稳之签，奖励{reward}{ST.coin_name()}，继续加油～"
        else:
            r = "下签"
            return f"你抽到了【{r}】 别灰心，这个只是娱乐，没事的～保持好心情，坏运气很快就会过去的！"
    if text.startswith("扔炸弹"):
        return cmd_bomb(gid, qq, text[3:].strip())
    # ---- 会话类游戏 ----
    if text.startswith("开始接龙"):
        chk = _check_single_game(gid, "接龙")
        if chk:
            return chk
        err = _ent_cost(gid, qq, "接龙")
        if err:
            return err
        first = random.choice(_get_chain_words())
        ST.recall_set(f"chain_owner_{gid}", str(qq))
        ST.recall_set(f"chain_{gid}", first)
        ST.recall_set(f"chain_start_{gid}", str(int(time.time())))
        ST.recall_set(f"chain_players_{gid}", "")
        ST.recall_set(f"chain_used_{gid}", first)
        ST.recall_set(f"chain_last_qq_{gid}", "")
        ST.recall_set(f"chain_last_time_{gid}", "0")
        _set_active_game(gid, "接龙")
        return (f"🧩 接龙开始！机器人先出词：【{first}】\r\n"
                f"请用尾字「{first[-1]}」接龙（词语2-6字）！\r\n"
                "其他玩家请在 30 秒内发送【加入接龙】加入！发送【退出接龙】结束。")
    if text == "加入接龙":
        owner = ST.recall_get(f"chain_owner_{gid}")
        start = ST.recall_get(f"chain_start_{gid}", "0")
        if not owner or str(owner) == str(qq):
            return "您是开局者，无需加入！"
        try:
            if int(time.time()) - int(start) > 30:
                return "开局已超过30秒，无法加入，请等待下一局！"
        except Exception:
            pass
        players = _get_players(gid, "chain_players_")
        if str(qq) not in players:
            players.append(str(qq))
            ST.recall_set(f"chain_players_{gid}", ",".join(players))
        return "你已加入接龙！发送一个词语接续吧~"
    if text in ("结束接龙", "退出接龙"):
        ST.recall_set(f"chain_owner_{gid}", "")
        ST.recall_set(f"chain_{gid}", "")
        ST.recall_set(f"chain_start_{gid}", "")
        ST.recall_set(f"chain_players_{gid}", "")
        ST.recall_set(f"chain_used_{gid}", "")
        ST.recall_set(f"chain_last_qq_{gid}", "")
        ST.recall_set(f"chain_last_time_{gid}", "")
        _clear_active_game(gid)
        return "接龙结束！"
    if text.startswith("开始急转弯"):
        chk = _check_single_game(gid, "急转弯")
        if chk:
            return chk
        err = _ent_cost(gid, qq, "急转弯")
        if err:
            return err
        q, a = random.choice(_get_trick())
        ST.recall_set(f"trick_{gid}_{qq}", a)
        ST.recall_set(f"trick_owner_{gid}", str(qq))
        ST.recall_set(f"trick_start_{gid}", str(int(time.time())))
        ST.recall_set(f"trick_players_{gid}", "")
        _set_active_game(gid, "急转弯")
        return "🤔 急转弯：" + q + "\r\n回复你的答案！（其他玩家30秒内发送【加入急转弯】加入）"
    if text.startswith("开始猜字谜"):
        chk = _check_single_game(gid, "猜字谜")
        if chk:
            return chk
        err = _ent_cost(gid, qq, "猜字谜")
        if err:
            return err
        q, a = random.choice(_get_miri())
        ST.recall_set(f"miri_{gid}_{qq}", a)
        ST.recall_set(f"miri_owner_{gid}", str(qq))
        ST.recall_set(f"miri_start_{gid}", str(int(time.time())))
        ST.recall_set(f"miri_players_{gid}", "")
        _set_active_game(gid, "猜字谜")
        return "🔤 字谜：" + q + "\r\n回复你的答案！（其他玩家30秒内发送【加入字谜】加入）"
    if text.startswith("开始猜数"):
        chk = _check_single_game(gid, "猜数")
        if chk:
            return chk
        err = _ent_cost(gid, qq, "猜数")
        if err:
            return err
        n = random.randint(1, 100)
        ST.recall_set(f"guessnum_{gid}_{qq}", str(n))
        ST.recall_set(f"guessnum_owner_{gid}", str(qq))
        ST.recall_set(f"guessnum_start_{gid}", str(int(time.time())))
        ST.recall_set(f"guessnum_players_{gid}", "")
        _set_active_game(gid, "猜数")
        return ("🎲 猜数开始！我心中想了一个 1-100 之间的数字，\r\n"
                "请你回复一个数字来猜，我会提示大了/小了！\r\n"
                "（其他玩家30秒内发送【加入猜数】加入，发送【退出猜数】结束）")
    if text.startswith("开始答题"):
        chk = _check_single_game(gid, "答题")
        if chk:
            return chk
        err = _ent_cost(gid, qq, "答题")
        if err:
            return err
        q, a = random.choice(_get_quiz())
        ST.recall_set(f"quiz_{gid}_{qq}", a)
        ST.recall_set(f"quiz_owner_{gid}", str(qq))
        ST.recall_set(f"quiz_start_{gid}", str(int(time.time())))
        ST.recall_set(f"quiz_players_{gid}", "")
        _set_active_game(gid, "答题")
        return "❓ 答题开始！" + q + "\r\n回复你的答案！（其他玩家30秒内发送【加入答题】加入）"
    if text == "加入猜数":
        return _join_game(gid, qq, "guessnum", "猜数")
    if text == "加入答题":
        return _join_game(gid, qq, "quiz", "答题")
    if text == "加入字谜":
        return _join_game(gid, qq, "miri", "字谜")
    if text == "加入急转弯":
        return _join_game(gid, qq, "trick", "急转弯")
    if text == "加入二四点":
        return _join_game(gid, qq, "game24", "二四点")
    if text.startswith("退出猜数"):
        res = _quit_game(gid, qq, "guessnum", "猜数")
        # _quit_game 已清 owner 相关，若是开局者退出则清锁
        owner = ST.recall_get(f"guessnum_owner_{gid}")
        if not owner:
            _clear_active_game(gid)
        return res
    if text == "退出答题":
        res = _quit_game(gid, qq, "quiz", "答题")
        if not ST.recall_get(f"quiz_owner_{gid}"):
            _clear_active_game(gid)
        return res
    if text == "退出字谜":
        res = _quit_game(gid, qq, "miri", "字谜")
        if not ST.recall_get(f"miri_owner_{gid}"):
            _clear_active_game(gid)
        return res
    if text == "退出急转弯":
        res = _quit_game(gid, qq, "trick", "急转弯")
        if not ST.recall_get(f"trick_owner_{gid}"):
            _clear_active_game(gid)
        return res
    if text == "退出二四点":
        # 兼容旧单人键与新群组键
        owner = ST.recall_get(f"game24_owner_{gid}")
        if owner and str(owner) == str(qq):
            ST.recall_set(f"game24_owner_{gid}", "")
            ST.recall_set(f"game24_players_{gid}", "")
            ST.recall_set(f"game24_start_{gid}", "")
            ST.recall_set(f"game24_{gid}_{owner}", "")
            _clear_active_game(gid)
        else:
            # 参与者退出
            players = _get_players(gid, "game24_players_")
            if str(qq) in players:
                players.remove(str(qq))
                ST.recall_set(f"game24_players_{gid}", ",".join(players))
            ST.recall_set(f"game24_{gid}_{qq}", "")
            # 若此时无owner或参与者为空但owner仍在，不清锁
            if not ST.recall_get(f"game24_owner_{gid}"):
                _clear_active_game(gid)
        return "已退出二四点！"
    if text.startswith("开始二四点"):
        chk = _check_single_game(gid, "二四点")
        if chk:
            return chk
        return _start_24(gid, qq)
    if text.startswith("二四点"):
        chk = _check_single_game(gid, "二四点")
        if chk:
            return chk
        return _start_24(gid, qq)
    if text.startswith("猜拳"):
        m = re.search(r"猜拳\s*(石头|剪刀|布)", text)
        if not m:
            return "请输入：猜拳 石头/剪刀/布"
        err = _ent_cost(gid, qq, "猜拳")
        if err:
            return err
        choice = {"石头": 0, "剪刀": 1, "布": 2}[m.group(1)]
        names = ["石头", "剪刀", "布"]
        # 胜率走配置 猜拳成功概率%（需求19 默认50）
        win_prob = ST.cfgi("娱乐配置", "猜拳成功概率", 50)
        r = random.random() * 100
        if r < win_prob:
            ai = (choice + 2) % 3  # 必输给玩家
            res = f"我出{names[ai]}！你赢了！"
            coin = ST.cfgi("娱乐配置", "猜拳奖励金币", 58)
            meili = ST.cfgi("娱乐配置", "猜拳奖励魅力", 1)
            if coin:
                ST.coins_add(gid, qq, coin)
            if meili:
                ST.acct_add(gid, qq, "charm", meili)
            if coin or meili:
                res += f" 奖励{coin}{ST.coin_name()}" + (f" 魅力+{meili}" if meili else "")
            return res
        elif r < win_prob + 20:
            ai = choice
            return f"我出{names[ai]}！平局！"
        else:
            ai = (choice + 1) % 3
            return f"我出{names[ai]}！我赢了~"
    # 会话作答
    r = _play(gid, qq, text)
    if r:
        return r
    return None


def _get_players(gid, key_prefix):
    v = ST.recall_get(key_prefix + gid, "")
    return [x for x in str(v).split(",") if x]


def _join_game(gid, qq, kind, label):
    owner = ST.recall_get(f"{kind}_owner_{gid}")
    if not owner:
        return f"当前没有进行中的{label}对局！"
    if str(owner) == str(qq):
        return "您是开局者，无需加入！"
    start = ST.recall_get(f"{kind}_start_{gid}", "0")
    try:
        if int(time.time()) - int(start) > 30:
            return "开局已超过30秒，无法加入，请等待下一局！"
    except Exception:
        pass
    players = _get_players(gid, f"{kind}_players_")
    if str(qq) not in players:
        players.append(str(qq))
        ST.recall_set(f"{kind}_players_{gid}", ",".join(players))
    return f"你已加入{label}！发送你的答案参与吧~"


def _quit_game(gid, qq, kind, label):
    owner = ST.recall_get(f"{kind}_owner_{gid}")
    if not owner:
        return f"当前没有进行中的{label}对局！"
    players = _get_players(gid, f"{kind}_players_")
    if str(owner) == str(qq):
        # 开局者退出=结束整局
        ST.recall_set(f"{kind}_owner_{gid}", "")
        ST.recall_set(f"{kind}_players_{gid}", "")
        for k in (f"{kind}_{gid}_{qq}", f"{kind}_start_{gid}"):
            ST.recall_set(k, "")
        return f"你已退出{label}，对局结束！"
    if str(qq) in players:
        players.remove(str(qq))
        ST.recall_set(f"{kind}_players_{gid}", ",".join(players))
    return f"你已退出{label}！"



def _is_player(gid, qq, kind):
    """判断是否对局参与者(开局者或已加入者)"""
    owner = ST.recall_get(f"{kind}_owner_{gid}")
    if owner and str(owner) == str(qq):
        return True
    players = _get_players(gid, f"{kind}_players_")
    return str(qq) in players


def _play(gid, qq, text):
    try:
        from .. import store as S
    except Exception:
        import store as S
    # 奖励 helper
    def _reward(gid, qq, coin=0, meili=0):
        if coin:
            try: S.coins_add(gid, qq, int(coin))
            except Exception: pass
        if meili:
            try: S.acct_add(gid, qq, "charm", int(meili))
            except Exception: pass
    # 若文本明显是其他系统的指令，则不拦截为答题答案，避免吞掉（需求14/15）
    _CMD_PREFIXES = ("领养","领取","精灵","坐骑","帮派","adventure","签到","转账","deposit","取款","购买","抽奖","抽签","扔炸弹","猜拳","开始","加入","退出","我的","查询","打赏","买下","释放","保护","打架","讨好","学习","祈福","造反","打工","收工","禁言","踢人","扣钱","充钱","群列表","应用统计","财富榜","排行榜","切换","查看","丢弃","设置","回收","携带","进化","对战","排行","你好","在吗","谢谢","晚安",
                    "创建","成员","贡献","weapon","修筑","福利","发起","管理","解散","邀请","同意","接受","当前","选择","复活","背包","商城","地图","出战","丢弃","进化","对战","帮派","精灵","坐骑","银行","奴隶","超管","娱乐","私聊","系统","榜","接龙","急转弯","字谜","猜数","答题","二四点","打劫","赌博","红包","福利","贡献","修筑","成员","管理","解散","邀请","同意","接受","当前","选择","复活","背包","商城","地图","adventure","领养","精灵","坐骑","帮派","adventure","签到","银行","奴隶","超管","娱乐","私聊",
                    "更新","检查更新","小白更新","查询更新","检查版本","小白升级","版本","小白版本","xb版本","插件版本","清空","重置","备份","维护","菜单","帮助")
    def _is_cmd(txt):
        t = txt.strip()
        for p in _CMD_PREFIXES:
            if t.startswith(p):
                return True
        return False
    # quiz/字谜/急转弯 分别按游戏独立会话(题面存开局者 key, 参与者均可作答)
    # 需求14/15：中途不提醒未加入者（非参与者直接静默放行）；参与者发其他指令时放行
    # label -> 配置前缀映射（字谜 实际为 猜字谜）
    _LABEL_CFG = {"答题": "答题", "字谜": "猜字谜", "急转弯": "急转弯"}
    for kind, label in (("quiz", "答题"), ("miri", "字谜"), ("trick", "急转弯")):
        owner = S.recall_get(f"{kind}_owner_{gid}")
        if not owner:
            continue
        try:
            start_val = S.recall_get(f"{kind}_start_{gid}", "0")
            start_ts = int(start_val or "0")
            if start_ts <= 0 or (int(time.time()) - start_ts) > 180:
                S.recall_set(f"{kind}_{gid}_{owner}", "")
                S.recall_set(f"{kind}_owner_{gid}", "")
                S.recall_set(f"{kind}_players_{gid}", "")
                S.recall_set(f"{kind}_start_{gid}", "")
                S.recall_set(f"ent_game_{gid}", "")
                continue
        except Exception:
            pass
        if not _is_player(gid, qq, kind):
            continue
        ans = S.recall_get(f"{kind}_{gid}_{owner}")
        if not ans:
            continue
        if _is_cmd(text):
            continue
        if text.strip() == ans:
            S.recall_set(f"{kind}_{gid}_{owner}", "")
            S.recall_set(f"{kind}_owner_{gid}", "")
            S.recall_set(f"{kind}_players_{gid}", "")
            S.recall_set(f"{kind}_start_{gid}", "")
            S.recall_set(f"ent_game_{gid}", "")
            # 奖励（全量可配，默认值保持旧行为）
            cfg_prefix = _LABEL_CFG.get(label, label)
            coin = S.cfgi("娱乐配置", f"{cfg_prefix}奖励金币", 88 if label!="答题" else 128)
            meili = S.cfgi("娱乐配置", f"{cfg_prefix}奖励魅力", 1)
            _reward(gid, qq, coin, meili)
            return f"恭喜！【{label}】答案正确：{ans} 奖励{coin}{S.coin_name()} 魅力+{meili}"
        return f"答案不对，再想想~（发送【退出{label}】结束）"
    # 猜数(题面存开局者 key, 参与者均可作答; 非参与者/非数字 放行到接龙)
    owner = S.recall_get(f"guessnum_owner_{gid}")
    if owner:
        try:
            start_val = S.recall_get(f"guessnum_start_{gid}", "0")
            start_ts = int(start_val or "0")
            if start_ts <= 0 or (int(time.time()) - start_ts) > 180:
                S.recall_set(f"guessnum_{gid}_{owner}", "")
                S.recall_set(f"guessnum_owner_{gid}", "")
                S.recall_set(f"guessnum_players_{gid}", "")
                S.recall_set(f"guessnum_start_{gid}", "")
                S.recall_set(f"ent_game_{gid}", "")
                owner = None
        except Exception:
            pass
    if owner and _is_player(gid, qq, "guessnum"):
        g = S.recall_get(f"guessnum_{gid}_{owner}")
        if g and text.strip().isdigit():
            v = int(text.strip())
            n = int(g)
            if v == n:
                S.recall_set(f"guessnum_{gid}_{owner}", "")
                S.recall_set(f"guessnum_owner_{gid}", "")
                S.recall_set(f"guessnum_players_{gid}", "")
                S.recall_set(f"guessnum_start_{gid}", "")
                S.recall_set(f"ent_game_{gid}", "")
                coin = S.cfgi("娱乐配置", "猜数奖励金币", 188)
                meili = S.cfgi("娱乐配置", "猜数奖励魅力", 2)
                _reward(gid, qq, coin, meili)
                return f"🎉 猜中啦！答案是 {n}！奖励{coin}{S.coin_name()} 魅力+{meili}"
            return "📉 小了，再猜！" if v < n else "📈 大了，再猜！"
    # 二四点（群组共享，可加入，30秒内）
    owner = S.recall_get(f"game24_owner_{gid}")
    if owner:
        try:
            start_val = S.recall_get(f"game24_start_{gid}", "0")
            start_ts = int(start_val or "0")
            if start_ts <= 0 or (int(time.time()) - start_ts) > 180:
                S.recall_set(f"game24_{gid}_{owner}", "")
                S.recall_set(f"game24_owner_{gid}", "")
                S.recall_set(f"game24_players_{gid}", "")
                S.recall_set(f"game24_start_{gid}", "")
                S.recall_set(f"ent_game_{gid}", "")
                owner = None
        except Exception:
            pass
    if owner:
        # 非参与者：只有发送本次题目数字时才提醒，否则静默（需求18）
        if not _is_player(gid, qq, "game24"):
            gtmp = S.recall_get(f"game24_{gid}_{owner}", "")
            if gtmp and re.search(r"\d", text):
                nums_tmp = [int(x) for x in gtmp.split("|") if x != ""]
                used_tmp = [int(x) for x in re.findall(r"\d+", text) if x.isdigit()]
                if any(u in nums_tmp for u in used_tmp):
                    return "您不是本局参与者，无法参与二四点！发送【加入二四点】加入吧~"
            # 非数字/非相关数字则放行到接龙
            pass
        else:
            g = S.recall_get(f"game24_{gid}_{owner}", "")
            # 兼容旧单人键
            if not g:
                g = S.recall_get(f"game24_{gid}_{qq}", "")
            if g and re.search(r"[\+\-\*/()×÷]", text):
                nums = [int(x) for x in g.split("|") if x != ""]
                t = text.strip().replace("×", "*").replace("÷", "/").replace("（", "(").replace("）", ")")
                try:
                    used = [int(x) for x in re.findall(r"\d+", t)]
                    if sorted(used) == sorted(nums):
                        val = _safe_eval_24(t)
                        if val is None:
                            return "算式有误，请检查（只用 %s 和 +-*/ 括号）：%s" % (" ".join(map(str, nums)), t)
                        if abs(val - 24) < 1e-6:
                            S.recall_set(f"game24_{gid}_{owner}", "")
                            S.recall_set(f"game24_{gid}_{qq}", "")
                            S.recall_set(f"game24_owner_{gid}", "")
                            S.recall_set(f"game24_players_{gid}", "")
                            S.recall_set(f"game24_start_{gid}", "")
                            S.recall_set(f"ent_game_{gid}", "")
                            coin = S.cfgi("娱乐配置", "二四点奖励金币", 128)
                            meili = S.cfgi("娱乐配置", "二四点奖励魅力", 1)
                            _reward(gid, qq, coin, meili)
                            return f"太棒了！『{t}』= 24，二四点通关！奖励{coin}{S.coin_name()} 魅力+{meili}"
                        return "算式得数不是 24，再试试~"
                    return "请只用给出的 4 个数！"
                except Exception:
                    return "算式有误，请检查（只用 %s 和 +-*/ 括号）：%s" % (" ".join(map(str, nums)), t)
            # 二四点非算式，放行到接龙
    else:
        # 兼容旧单人二四点（无owner时）
        g = S.recall_get(f"game24_{gid}_{qq}")
        if g and re.search(r"[\+\-\*/()×÷]", text):
            nums = [int(x) for x in g.split("|") if x != ""]
            t = text.strip().replace("×", "*").replace("÷", "/").replace("（", "(").replace("）", ")")
            try:
                used = [int(x) for x in re.findall(r"\d+", t)]
                if sorted(used) == sorted(nums):
                    val = _safe_eval_24(t)
                    if val is None:
                        return "算式有误，请检查（只用 %s 和 +-*/ 括号）：%s" % (" ".join(map(str, nums)), t)
                    if abs(val - 24) < 1e-6:
                        S.recall_set(f"game24_{gid}_{qq}", "")
                        S.recall_set(f"ent_game_{gid}", "")
                        coin = S.cfgi("娱乐配置", "二四点奖励金币", 128)
                        meili = S.cfgi("娱乐配置", "二四点奖励魅力", 1)
                        _reward(gid, qq, coin, meili)
                        return f"太棒了！『{t}』= 24，二四点通关！奖励{coin}{S.coin_name()} 魅力+{meili}"
                    return "算式得数不是 24，再试试~"
                return "请只用给出的 4 个数！"
            except Exception:
                return "算式有误，请检查（只用 %s 和 +-*/ 括号）：%s" % (" ".join(map(str, nums)), t)
    # 接龙延续: 只允许参与者, 词尾字需接上
    # 需求14：仅当提及结尾字时才提醒未加入；指令不视为接龙词
    owner = S.recall_get(f"chain_owner_{gid}")
    if owner:
        # 若是其他系统指令，直接放行不作接龙处理
        if _is_cmd(text):
            return None
        last = S.recall_get(f"chain_{gid}", "")
        start = S.recall_get(f"chain_start_{gid}", "0")
        try:
            start_ts = int(start or "0")
            if start_ts <= 0 or (int(time.time()) - start_ts) > 180:
                _clean_expired_game(gid, max_seconds=0)
                return "接龙超时结束~"
        except Exception:
            _clean_expired_game(gid, max_seconds=0)
            return "接龙超时结束~"
        if not _is_player(gid, qq, "chain"):
            # 仅当用户尝试接龙（2-6字且首字接尾字）才提醒
            if text and 2 <= len(text) <= 6 and not text.startswith(("开始", "加入", "退出")) and last and text[0] == last[-1]:
                return "您不是本局参与者，无法接龙！发送【加入接龙】加入吧~"
            return None
        if text and 2 <= len(text) <= 6 and not text.startswith(("开始", "加入", "退出")):
            if last:
                if text == last:
                    return f"不能重复接上一个完全相同的词语「{last}」哦，请换一个词~"
                if text[0] != last[-1]:
                    return f"接不上哦！上一个词的尾字是「{last[-1]}」，请用这个字开头~"
            used_str = S.recall_get(f"chain_used_{gid}", "")
            used_list = [w for w in used_str.split(",") if w]
            if text in used_list:
                return f"词语「{text}」在本轮接龙中已经使用过了，请换一个新词吧~"

            now = int(time.time())
            last_qq = S.recall_get(f"chain_last_qq_{gid}", "")
            last_time = int(S.recall_get(f"chain_last_time_{gid}", "0") or 0)
            if last_qq == str(qq) and now - last_time < 2:
                return "接得太快啦，深呼吸一下再接吧~"

            used_list.append(text)
            if len(used_list) > 100:
                used_list = used_list[-100:]
            S.recall_set(f"chain_used_{gid}", ",".join(used_list))
            S.recall_set(f"chain_{gid}", text)
            S.recall_set(f"chain_start_{gid}", str(now))
            S.recall_set(f"chain_last_qq_{gid}", str(qq))
            S.recall_set(f"chain_last_time_{gid}", str(now))

            coin = S.cfgi("娱乐配置", "接龙奖励金币", 50)
            meili = S.cfgi("娱乐配置", "接龙奖励魅力", 0)
            if coin or meili:
                _reward(gid, qq, coin, meili)
                if coin:
                    return f"→ {text} 奖励{coin}{S.coin_name()}" + (f" 魅力+{meili}" if meili else "")
            return f"→ {text}"
    return None
