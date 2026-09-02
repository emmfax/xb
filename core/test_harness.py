# -*- coding: utf-8 -*-
"""Test harness — 测试 1-9 + all 前置与探针，v0.45 抽离自 dispatch"""
import json
import time
try:
    from .. import store as ST
    from ..engines import slave, sign, bank, ent, spirit, ride, guild, adventure
except ImportError:
    import store as ST
    try:
        from engines import slave, sign, bank, ent, spirit, ride, guild, adventure
    except ImportError:
        from ..engines import slave  # type: ignore

_TEST_PROBES = {
    "测试testxb 2": [
        ("签到系统","签到系统"),("签到-有钱","签到"),("签到-重复","签到"),("我的信息-有","我的信息"),("我的信息-重复","我的信息"),("个人排行","个人排行"),
        ("抽奖-有券","抽奖"),("抽奖-没券","抽奖"),("领取新手礼包-首领","领取新手礼包"),("领取新手礼包-重复","领取新手礼包"),
        ("每日点赞-首点","每日点赞"),("每日点赞-重复","每日点赞"),("购买体力-有钱","购买体力 1"),("购买体力-没钱","购买体力 1"),
        ("购买魅力-有钱","购买魅力 1"),("购买魅力-没钱","购买魅力 1"),("财富榜","财富榜"),("签到榜","签到榜"),("体力榜","体力榜"),("魅力榜","魅力榜"),
    ],
    "测试testxb 3": [
        ("精灵系统","精灵系统"),("领养精灵-无","领养精灵"),("领养精灵-已有","领养精灵"),("领取精灵礼包-首领","领取精灵礼包"),("领取精灵礼包-重复","领取精灵礼包"),
        ("我的精灵-无","我的精灵"),("我的精灵-有","我的精灵"),("精灵商城","精灵商城"),("精灵地图","精灵地图"),
        ("精灵冒险-有体力","精灵冒险 原神"),("精灵冒险-没体力","精灵冒险 原神"),("使用精灵球-有球","使用精灵球 大师球"),("使用精灵球-没球","使用精灵球 精灵球"),
        ("查看精灵-存在","查看精灵 火苗"),("查看精灵-不存在","查看精灵 不存在精灵"),("出战精灵-存在","出战精灵 火苗"),("出战精灵-不存在","出战精灵 不存在"),
        ("丢弃精灵-有","丢弃精灵 火苗"),("丢弃精灵-末位保底","丢弃精灵 火苗"),("精灵排行","精灵排行"),
    ],
    "测试testxb 4": [
        ("娱乐系统","娱乐系统"),("抽签-有钱","抽签"),("抽签-没钱","抽签"),("扔炸弹-有钱有目标","扔炸弹 @10001"),("扔炸弹-没钱","扔炸弹 @10001"),("扔炸弹-没目标","扔炸弹"),
        ("接龙-加入","开始接龙"),("接龙-进行中再开","开始接龙"),("接龙-退出","退出接龙"),("接龙-无局退出","退出接龙"),
        ("急转弯-加入","开始急转弯"),("急转弯-退出","退出急转弯"),("猜字谜-加入","开始猜字谜"),("猜字谜-退出","退出字谜"),
        ("猜数-加入","开始猜数"),("猜数-退出","退出猜数"),("答题-加入","开始答题"),("答题-退出","退出答题"),
        ("二四点-生成","二四点"),("二四点-有解校验","二四点"),("猜拳-有钱","猜拳 石头"),("猜拳-没钱","猜拳 石头"),
    ],
    "测试testxb 5": [
        ("银行系统","银行系统"),("存款-有钱","存款 3000"),("存款-没钱","存款 9999999"),("取款-有存款","取款 1000"),("取款-没存款","取款 1000"),
        ("转账-有钱","转账 @10001 3000"),("转账-没钱","转账 @10001 9999999"),("转账-没目标","转账"),("发红包-有钱","发红包 3000 口令加强"),("发红包-没钱","发红包 3000 口令没钱"),
        ("抢红包-有口令","抢红包 口令加强"),("抢红包-错口令","抢红包 错口令"),("抢红包-没口令","抢红包"),("赌博-有钱","赌博 1000"),("赌博-没钱","赌博 9999999"),
        ("打劫-有钱","打劫 @10001"),("打劫-没钱","打劫 @10001"),("打劫银行-有体力","打劫银行"),("打劫银行-没体力","打劫银行"),
        ("保释-有钱","保释 @10001"),("越狱-有体力","我要越狱"),("越狱-没体力","我要越狱"),("进监狱-首进","我要进监狱"),("进监狱-重复","我要进监狱"),
    ],
    "测试testxb 6": [
        ("奴隶系统","奴隶系统"),("我的信息-有","我的信息"),("我的信息-无","我的信息"),("买下-有钱有位","买下 @10002"),("买下-没钱","买下 @10002"),("买下-无位","买下 @10002"),("买下-已是奴隶","买下 @10002"),
        ("释放-是主人","释放 @10002"),("释放-非主人","释放 @10002"),("释放-无奴隶","释放 @10002"),("保护-是主人有钱","保护 @10002"),("保护-没钱","保护 @10002"),("保护-非主人","保护 @10002"),
        ("打架-有奴隶","打架 @10002"),("打架-无奴隶","打架 @10002"),("讨好-有主人","讨好"),("讨好-无主人","讨好"),("学习-有主人","我要学习"),("学习-无主人","我要学习"),("祈福-有","我要祈福"),("造反-有主人","造反"),("造反-无主人","造反"),
        ("打工-有奴隶","奴隶打工"),("打工-无奴隶","奴隶打工"),("买奴隶位-有钱","买奴隶位"),("买奴隶位-没钱","买奴隶位"),
    ],
    "测试testxb 7": [
        ("坐骑系统","坐骑系统"),("我的坐骑-无","我的坐骑"),("我的坐骑-有","我的坐骑"),("坐骑商城","坐骑商城"),
        ("购买坐骑-有钱","购买坐骑 企鹅"),("购买坐骑-没钱","购买坐骑 企鹅"),("购买坐骑-已有","购买坐骑 企鹅"),
        ("查看坐骑-存在","查看坐骑 企鹅"),("查看坐骑-不存在","查看坐骑 不存在坐骑"),("丢弃坐骑-有","丢弃坐骑 企鹅"),("丢弃坐骑-无","丢弃坐骑 企鹅"),("丢弃坐骑-欢迎中","丢弃坐骑 企鹅"),
        ("设置欢迎-有","设置欢迎坐骑 企鹅"),("设置欢迎-无","设置欢迎坐骑 企鹅"),("查看欢迎-有","查看欢迎坐骑"),("查看欢迎-无","查看欢迎坐骑"),
        ("回收欢迎-有","回收欢迎坐骑 企鹅"),("回收欢迎-无","回收欢迎坐骑 企鹅"),("切换坐骑-有","切换坐骑 企鹅"),("切换坐骑-无","切换坐骑 企鹅"),
    ],
    "测试testxb 8": [
        ("帮派系统","帮派系统"),("帮派列表-空","帮派列表"),("我的帮派-无","我的帮派"),("我的帮派-有","我的帮派"),
        ("创建帮派-有钱有魅力","创建帮派 测试帮加强"),("创建帮派-没钱","创建帮派 没钱帮"),("创建帮派-已有","创建帮派 测试帮加强"),
        ("帮派排行","帮派排行"),("成员列表-有","成员列表"),("成员列表-无","成员列表"),("帮派贡献-有钱","帮派贡献 3000"),("帮派贡献-没钱","帮派贡献 9999999"),
        ("帮战-有","发起帮战 测试帮"),("帮战-无帮派","发起帮战 测试帮"),
    ],
    "测试testxb 9": [
        ("冒险系统","冒险系统"),("当前冒险-无","当前冒险"),("结束冒险-无","结束冒险"),("复活币排行","复活币排行"),
        ("冒险-有体力有钱","冒险 迷失海岛"),("冒险-没体力","冒险 迷失海岛"),("冒险-没钱","冒险 迷失海岛"),("冒险-进行中再开","冒险 迷失海岛"),
        ("选择-有效","选择 1"),("当前冒险-有","当前冒险"),("结束冒险-有","结束冒险"),
    ],
    "测试testxb1": [("签到系统","签到系统"),("签到","签到"),("我的信息","我的信息"),("个人排行","个人排行"),("抽奖","抽奖"),("领取新手礼包","领取新手礼包"),("每日点赞","每日点赞"),("购买体力","购买体力 1"),("购买魅力","购买魅力 1"),("财富榜","财富榜"),("签到榜","签到榜"),("体力榜","体力榜"),("魅力榜","魅力榜")],
    "测试testxb2": [("精灵系统","精灵系统"),("领养精灵","领养精灵"),("领取精灵礼包","领取精灵礼包"),("我的精灵","我的精灵"),("精灵商城","精灵商城"),("精灵地图","精灵地图"),("精灵冒险","精灵冒险 原神"),("使用精灵球","使用精灵球 大师球"),("查看精灵","查看精灵 火苗"),("出战精灵","出战精灵 火苗"),("丢弃精灵","丢弃精灵 火苗"),("精灵排行","精灵排行")],
    "测试testxb3": [("娱乐抽签","抽签"),("扔炸弹","扔炸弹 @10001"),("接龙","开始接龙"),("急转弯","开始急转弯"),("猜字谜","开始猜字谜"),("猜数","开始猜数"),("答题","开始答题"),("二四点","二四点"),("猜拳","猜拳 石头")],
    "测试testxb4": [("银行系统","银行系统"),("存款","存款 3000"),("取款","取款 1000"),("转账","转账 @10001 3000"),("发红包","发红包 3000 口令"),("抢红包","抢红包 口令"),("赌博","赌博 1000"),("打劫","打劫 @10001"),("打劫银行","打劫银行"),("保释","保释 @10001"),("越狱","我要越狱"),("进监狱","我要进监狱")],
    "测试testxb5": [("奴隶系统","奴隶系统"),("我的信息","我的信息"),("买下","买下 @10002"),("释放","释放 @10002"),("保护","保护 @10002"),("打架","打架 @10002"),("讨好","讨好"),("学习","我要学习"),("祈福","我要祈福"),("造反","造反"),("打工","奴隶打工"),("起名","起名 @10002 测试名"),("买奴隶位","买奴隶位")],
    "测试testxb6": [("坐骑系统","坐骑系统"),("我的坐骑","我的坐骑"),("坐骑商城","坐骑商城"),("购买坐骑","购买坐骑 企鹅"),("查看坐骑","查看坐骑 企鹅"),("丢弃坐骑","丢弃坐骑 企鹅"),("设置欢迎","设置欢迎坐骑 企鹅"),("查看欢迎","查看欢迎坐骑"),("回收欢迎","回收欢迎坐骑 企鹅"),("切换坐骑","切换坐骑 企鹅")],
    "测试testxb7": [("帮派系统","帮派系统"),("帮派列表","帮派列表"),("我的帮派","我的帮派"),("创建帮派","创建帮派 测试帮"),("帮派排行","帮派排行"),("成员列表","成员列表"),("帮派贡献","帮派贡献 100"),("帮战","发起帮战 测试帮")],
    "测试testxb8": [("冒险系统","冒险系统"),("当前冒险","当前冒险"),("结束冒险","结束冒险"),("复活币排行","复活币排行"),("冒险","冒险 迷失海岛")],
}

def _setup_user(v_gid, v_qq, label, cmd):
    try:
        ST.coins_add(v_gid, v_qq, 1000000)
        ST.acct(v_gid, v_qq).set("stamina", "3000")
        ST.acct(v_gid, v_qq).set("charm", "3000")
        ST.acct(v_gid, v_qq).set("deposit", "50000")
        ST.acct(v_gid, v_qq).set("lottery_tickets", "5")
        ST.acct_save(v_gid, v_qq)
        try:
            slave.mark_known(v_gid, v_qq)
            slave.NOTE_NAMES[v_qq] = f"测试{v_qq[-2:]}"
        except Exception:
            pass
        if "没钱" in label:
            cur = ST.coins_get(v_gid, v_qq)
            ST.coins_add(v_gid, v_qq, -cur)
            ST.acct(v_gid, v_qq).set("deposit", "0")
            ST.acct_save(v_gid, v_qq)
        if "没存款" in label:
            ST.acct(v_gid, v_qq).set("deposit", "0")
            ST.acct_save(v_gid, v_qq)
        if "没体力" in label:
            ST.acct(v_gid, v_qq).set("stamina", "0")
            ST.acct_save(v_gid, v_qq)
        if "有精灵" in label or "已有" in label or "存在" in label.split("-")[-1] or "末位保底" in label:
            try:
                a = ST.acct(v_gid, v_qq)
                if "末位保底" in label:
                    sp = {"list": [{"name": "火苗", "level": 5, "hp": 40, "atk": 51, "def": 40, "spa": 34, "spd": 40}], "active": "火苗", "bag": {}}
                else:
                    sp = {"list": [{"name": "火苗", "level": 5, "hp": 40, "atk": 51, "def": 40, "spa": 34, "spd": 40}, {"name": "水滴", "level": 5, "hp": 40, "atk": 34, "def": 40, "spa": 51, "spd": 40}, {"name": "木叶", "level": 5, "hp": 40, "atk": 40, "def": 45, "spa": 40, "spd": 35}], "active": "火苗", "bag": {"jinglingqiu": 5, "dashiqiu": 2}}
                a.set("spirits", json.dumps(sp, ensure_ascii=False))
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        if "没券" in label:
            try:
                a = ST.acct(v_gid, v_qq)
                a.set("lottery_tickets", "0")
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        if "没精灵" in label or (label.endswith("-无") and "精灵" in label):
            try:
                a = ST.acct(v_gid, v_qq)
                if "我的精灵-无" in label:
                    a.set("spirits", "{}")
                    ST.acct_save(v_gid, v_qq)
                elif "领养精灵-无" in label:
                    a.set("spirits", "{}")
                    ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        if "没球" in label:
            try:
                a = ST.acct(v_gid, v_qq)
                sp = {"list": [{"name": "火苗", "level": 5, "hp": 40, "atk": 51, "def": 40, "spa": 34, "spd": 40}, {"name": "水滴", "level": 5, "hp": 40, "atk": 34, "def": 40, "spa": 51, "spd": 40}, {"name": "木叶", "level": 5, "hp": 40, "atk": 40, "def": 45, "spa": 40, "spd": 35}], "active": "火苗", "bag": {}}
                a.set("spirits", json.dumps(sp, ensure_ascii=False))
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        if any(k in label for k in ["精灵冒险","使用精灵球-有球","查看精灵-存在","出战精灵-存在","丢弃精灵-有","精灵排行"]):
            try:
                a = ST.acct(v_gid, v_qq)
                cur = a.get("spirits","")
                if not cur or cur=="{}" or "火苗" not in cur:
                    sp = {"list": [{"name": "火苗", "level": 5, "hp": 40, "atk": 51, "def": 40, "spa": 34, "spd": 40}, {"name": "水滴", "level": 5, "hp": 40, "atk": 34, "def": 40, "spa": 51, "spd": 40}, {"name": "木叶", "level": 5, "hp": 40, "atk": 40, "def": 45, "spa": 40, "spd": 35}], "active": "火苗", "bag": {"jinglingqiu": 5, "dashiqiu": 2}}
                    a.set("spirits", json.dumps(sp, ensure_ascii=False))
                    ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        if "有坐骑" in label or ("已有" in label and "坐骑" in cmd) or label in ["我的坐骑-有","切换坐骑-有","丢弃坐骑-有","丢弃坐骑-欢迎中","设置欢迎-有","查看欢迎-有","回收欢迎-有","查看坐骑-存在"]:
            try:
                a = ST.acct(v_gid, v_qq)
                r = {"list": ["企鹅", "宝驴"], "welcome": "企鹅", "active": "企鹅"}
                a.set("rides", json.dumps(r, ensure_ascii=False))
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        if label.endswith("-无") and "坐骑" in label or label in ["我的坐骑-无","切换坐骑-无","查看欢迎-无","回收欢迎-无"]:
            try:
                a = ST.acct(v_gid, v_qq)
                a.set("rides", "{}")
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        if "有帮派" in label or ("已有" in label and "帮派" in label) or label in ["我的帮派-有","成员列表-有","帮派贡献-有钱","帮战-有"]:
            try:
                a = ST.acct(v_gid, v_qq)
                pos = "帮主" if label in ["帮战-有","帮派贡献-有钱"] else "成员"
                g = {"name": "测试已有帮", "pos": pos, "gong": 0, "build": 0, "intro": ""}
                a.set("guild", json.dumps(g, ensure_ascii=False))
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        if label == "帮战-有":
            try:
                b = ST.acct(v_gid, "10001")
                g2 = {"name": "测试帮", "pos": "帮主", "gong": 0, "build": 0, "intro": ""}
                b.set("guild", json.dumps(g2, ensure_ascii=False))
                ST.acct_save(v_gid, "10001")
                try:
                    slave.mark_known(v_gid, "10001")
                except Exception:
                    pass
            except Exception:
                pass
        if label.endswith("-无") and "帮派" in label or label in ["帮派列表-空","我的帮派-无","成员列表-无","帮派贡献-没钱","帮战-无帮派"]:
            try:
                a = ST.acct(v_gid, v_qq)
                a.set("guild", "{}")
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        try:
            v_gid_s = v_gid
            for tgt in ("10001", "10002", "10003", "10004", "10005"):
                try:
                    slave.mark_known(v_gid_s, tgt)
                    ST.coins_add(v_gid_s, tgt, 1000000)
                    ST.acct(v_gid_s, tgt).set("stamina", "3000")
                    ST.acct(v_gid_s, tgt).set("charm", "3000")
                    ST.acct_save(v_gid_s, tgt)
                    st = slave.state(v_gid_s)
                    if not st.has_section(tgt):
                        st.add_section(tgt)
                    u = st[tgt]
                    if not u.get("price"):
                        u["price"] = "1000"
                    if not u.get("owner"):
                        u["owner"] = ""
                    slave.save(v_gid_s)
                except Exception:
                    pass
            st = slave.state(v_gid)
            tgt = "10002"
            if "买下-已是奴隶" in label:
                if st.has_section(tgt):
                    st[tgt]["owner"] = v_qq
                    slave.save(v_gid)
            elif "买下-有钱有位" in label or "买下" in label and "有钱" in label:
                if st.has_section(tgt):
                    st[tgt]["owner"] = ""
                    slave.save(v_gid)
            elif "释放-是主人" in label or "保护-是主人" in label:
                if st.has_section(tgt):
                    st[tgt]["owner"] = v_qq
                    slave.save(v_gid)
            elif "释放-非主人" in label or "保护-非主人" in label:
                if st.has_section(tgt):
                    st[tgt]["owner"] = "10001"
                    slave.save(v_gid)
            elif "释放-无奴隶" in label:
                if st.has_section(tgt):
                    st[tgt]["owner"] = ""
                    slave.save(v_gid)
            if "打架-有奴隶" in label:
                for owner, s in [(v_qq, "10003"), ("10002", "10004")]:
                    if not st.has_section(s):
                        st.add_section(s)
                    st[s]["owner"] = owner
                    st[s]["price"] = "1500"
                slave.save(v_gid)
                if st.has_section(v_qq):
                    st[v_qq]["slave_slots"] = "5"
                    slave.save(v_gid)
            if "打架-无奴隶" in label:
                for s in list(st.sections()):
                    if s.isdigit() and st[s].get("owner") == v_qq:
                        st[s]["owner"] = ""
                slave.save(v_gid)
            if "打工-有奴隶" in label:
                if not any(st[s].get("owner")==v_qq for s in st.sections() if s.isdigit()):
                    if not st.has_section("10003"):
                        st.add_section("10003")
                    st["10003"]["owner"] = v_qq
                    st["10003"]["price"] = "1200"
                    slave.save(v_gid)
            if "打工-无奴隶" in label:
                for s in list(st.sections()):
                    if s.isdigit() and st[s].get("owner") == v_qq:
                        st[s]["owner"] = ""
                slave.save(v_gid)
            if "讨好-有主人" in label or "造反-有主人" in label:
                if st.has_section(v_qq):
                    st[v_qq]["owner"] = "10001"
                    slave.save(v_gid)
            if "讨好-无主人" in label or "造反-无主人" in label or "学习-无主人" in label:
                if st.has_section(v_qq):
                    st[v_qq]["owner"] = ""
                    slave.save(v_gid)
            if "学习-有主人" in label:
                if st.has_section(v_qq):
                    st[v_qq]["owner"] = "10001"
                    slave.save(v_gid)
            if "买下-无位" in label:
                if not st.has_section(v_qq):
                    st.add_section(v_qq)
                st[v_qq]["slave_slots"] = "1"
                st[v_qq]["price"] = "1000"
                if not st.has_section("10003"):
                    st.add_section("10003")
                st["10003"]["owner"] = v_qq
                st["10003"]["price"] = "1200"
                if st.has_section("10002"):
                    st["10002"]["owner"] = ""
                    if st["10002"].get("purchase_time",""):
                        st["10002"]["purchase_time"] = ""
                slave.save(v_gid)
            if label.startswith("买下-") and "已是" not in label:
                try:
                    if st.has_section("10002"):
                        if st["10002"].get("owner","") != "":
                            st["10002"]["owner"] = ""
                        if st["10002"].get("purchase_time",""):
                            st["10002"]["purchase_time"] = ""
                        slave.save(v_gid)
                except Exception:
                    pass
            if "越狱" in label or "保释" in label:
                try:
                    import time as _t
                    import datetime as _dt
                    if "越狱" in label:
                        a = ST.acct(v_gid, v_qq)
                        a.set("jail", "1")
                        a.set("jail_start", _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        a.set("release_timestamp", str(int(_t.time()) + 600))
                        if "没体力" in label:
                            a.set("stamina", "0")
                        else:
                            a.set("stamina", "3000")
                        ST.acct_save(v_gid, v_qq)
                    if "保释" in label:
                        tgt = "10001"
                        a2 = ST.acct(v_gid, tgt)
                        a2.set("jail", "1")
                        a2.set("jail_start", _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        a2.set("release_timestamp", str(int(_t.time()) + 600))
                        ST.acct_save(v_gid, tgt)
                        try:
                            slave.mark_known(v_gid, tgt)
                        except Exception:
                            pass
                except Exception:
                    pass
            if any(k in label for k in ["存款","取款","转账","发红包","抢红包","赌博","打劫"]) and not any(k in label for k in ["越狱","保释","进监狱","出狱","劫狱"]):
                try:
                    a = ST.acct(v_gid, v_qq)
                    a.set("jail", "0")
                    a.set("jail_start", "")
                    a.set("release_timestamp", "")
                    ST.acct_save(v_gid, v_qq)
                except Exception:
                    pass
        except Exception:
            pass
    except Exception:
        pass


async def handle_test_probes(raw, gid, qq, is_admin, event, is_private):
    if raw.strip() == "测试testxb all":
        pass
    elif raw.strip() not in _TEST_PROBES:
        return None
    if not is_admin:
        try:
            event.stop_event()
        except Exception:
            pass
        return "无权限，仅超管可用"
    try:
        if raw.strip() == "测试testxb all":
            outs = []
            v_gid = "999999"
            A_RICH = "10006"
            B_POOR = "10007"
            v_qqs = []
            sys_order = [("测试testxb 2", sign), ("测试testxb 3", spirit), ("测试testxb 4", ent), ("测试testxb 5", bank), ("测试testxb 6", slave), ("测试testxb 7", ride), ("测试testxb 8", guild), ("测试testxb 9", adventure)]
            for sys_key, mod in sys_order:
                sys_outs = []
                prev_qq = None
                for label, cmd in _TEST_PROBES.get(sys_key, []):
                    if mod in (slave, ride):
                        v_qq = str(10006 + (len(v_qqs) % 5))
                    elif mod == guild and "创建帮派" in label:
                        if "有钱" in label:
                            v_qq = "10008"
                        elif "没钱" in label:
                            v_qq = "10009"
                        else:
                            v_qq = "10010"
                    elif label == "抢红包-有口令":
                        v_qq = B_POOR
                    elif "重复" in label and prev_qq:
                        v_qq = prev_qq
                    else:
                        is_poor = any(k in label for k in ["没钱","没券","没体力","没球","没口令","错口令"]) or label.endswith("-无") or label.endswith("-空") or label.endswith("-不存在")
                        if "非主人" in label or "无主人" in label or "无奴隶" in label:
                            is_poor = "没钱" in label
                        if "无位" in label:
                            is_poor = False
                        v_qq = B_POOR if is_poor else A_RICH
                    if mod not in (slave, ride):
                        prev_qq = v_qq
                    else:
                        prev_qq = v_qq if "重复" in label else None
                    v_qqs.append(v_qq)
                    _setup_user(v_gid, v_qq, label, cmd)
                    if mod == slave:
                        try:
                            st2 = slave.state(v_gid)
                            if st2.has_section(v_qq):
                                u2 = st2[v_qq]
                                for ck in ["flatter_time","study_time","torture_time","protect_time","打架时间","造反时间","讨好时间","学习时间","保护时间"]:
                                    if ck in u2:
                                        u2[ck] = ""
                                slave.save(v_gid)
                        except Exception:
                            pass
                    if label.endswith("-加入"):
                        try:
                            ST.recall_set(f"ent_game_{v_gid}", "")
                        except Exception:
                            pass
                    try:
                        r = mod.handle(v_gid, v_qq, cmd)
                        if not r:
                            r = f"【{label}】无回复（需前置状态）"
                        sys_outs.append(f"【{label}】\r\n指令：{cmd}\r\n回复：\r\n{str(r)[:800]}")
                    except Exception as e:
                        sys_outs.append(f"【{label}】异常: {e}")
                outs.append((sys_key, sys_outs))
            try:
                uniq = set(v_qqs + ["10001","10002","10003","10004","10005","10006","10007"])
                for vq in uniq:
                    try:
                        ST._DB.execute("DELETE FROM wallet WHERE gid=? AND qq=?", (int(v_gid), int(vq)))
                        ST._DB.execute("DELETE FROM accounts WHERE gid=? AND qq=?", (int(v_gid), int(vq)))
                        ST._DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(v_gid), int(vq)))
                    except Exception:
                        pass
                ST._DB.commit()
                for vq in uniq:
                    ST._ACC_CACHE.pop((v_gid, vq), None)
                ST._GROUP_CACHE.pop(v_gid, None)
            except Exception:
                pass
            bot = getattr(event, "bot", None)
            if bot and not is_private:
                try:
                    for sys_key, sys_outs in outs:
                        nodes = []
                        for idx, txt in enumerate(sys_outs):
                            nodes.append({"type": "node", "data": {"name": f"{sys_key}-{idx+1}", "uin": str(qq), "content": [{"type": "text", "data": {"text": txt[:4000]}}]}})
                        await bot.call_action("send_group_forward_msg", group_id=int(gid), messages=nodes)
                        import asyncio
                        await asyncio.sleep(5)
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    return f"__HANDLED__已发送测试testxb all {len(outs)}系统，分段5秒"
                except Exception as e:
                    print(f"forward all failed: {e}")
            merged = ""
            for sys_key, sys_outs in outs:
                merged += f"\n\n===== {sys_key} =====\n\n" + "\n\n".join(sys_outs)
            try:
                event.stop_event()
            except Exception:
                pass
            return merged
        probes = _TEST_PROBES[raw.strip()]
        sys_map = {"测试testxb 2": sign, "测试testxb 3": spirit, "测试testxb 4": ent, "测试testxb 5": bank, "测试testxb 6": slave, "测试testxb 7": ride, "测试testxb 8": guild, "测试testxb 9": adventure, "测试testxb1": sign, "测试testxb2": spirit, "测试testxb3": ent, "测试testxb4": bank, "测试testxb5": slave, "测试testxb6": ride, "测试testxb7": guild, "测试testxb8": adventure}
        mod = sys_map.get(raw.strip(), sign)
        v_gid = "999999"
        A_RICH = "10006"
        B_POOR = "10007"
        v_qqs = []
        outs = []
        prev_qq = None
        for label, cmd in probes:
            if mod in (slave, ride):
                v_qq = str(10006 + (len(v_qqs) % 5))
            elif mod == guild and "创建帮派" in label:
                if "有钱" in label:
                    v_qq = "10008"
                elif "没钱" in label:
                    v_qq = "10009"
                else:
                    v_qq = "10010"
            elif label == "抢红包-有口令":
                v_qq = B_POOR
            elif "重复" in label and prev_qq:
                v_qq = prev_qq
            else:
                is_poor = any(k in label for k in ["没钱","没券","没体力","没球","没口令","错口令"]) or label.endswith("-无") or label.endswith("-空") or label.endswith("-不存在")
                if "非主人" in label or "无主人" in label or "无奴隶" in label:
                    is_poor = "没钱" in label
                if "无位" in label:
                    is_poor = False
                v_qq = B_POOR if is_poor else A_RICH
            if mod not in (slave, ride):
                prev_qq = v_qq
            else:
                prev_qq = v_qq if "重复" in label else None
            v_qqs.append(v_qq)
            _setup_user(v_gid, v_qq, label, cmd)
            if mod == slave:
                try:
                    st2 = slave.state(v_gid)
                    if st2.has_section(v_qq):
                        u2 = st2[v_qq]
                        for ck in ["flatter_time","study_time","torture_time","protect_time","打架时间","造反时间","讨好时间","学习时间","保护时间"]:
                            if ck in u2:
                                u2[ck] = ""
                        slave.save(v_gid)
                except Exception:
                    pass
            if label.endswith("-加入"):
                try:
                    ST.recall_set(f"ent_game_{v_gid}", "")
                except Exception:
                    pass
            try:
                r = mod.handle(v_gid, v_qq, cmd)
                if not r:
                    try:
                        r2 = mod.handle(gid, qq, cmd)
                        r = r2
                    except Exception:
                        pass
                if not r:
                    r = f"【{label}】无回复（需前置状态）"
                outs.append(f"【{label}】\r\n指令：{cmd}\r\n回复：\r\n{str(r)[:800]}")
            except Exception as e:
                outs.append(f"【{label}】异常: {e}")
        try:
            uniq = set(v_qqs + ["10001","10002","10003","10004","10005","10006","10007"])
            for vq in uniq:
                try:
                    ST._DB.execute("DELETE FROM wallet WHERE gid=? AND qq=?", (int(v_gid), int(vq)))
                    ST._DB.execute("DELETE FROM accounts WHERE gid=? AND qq=?", (int(v_gid), int(vq)))
                    ST._DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(v_gid), int(vq)))
                except Exception:
                    pass
            ST._DB.commit()
            for vq in uniq:
                ST._ACC_CACHE.pop((v_gid, vq), None)
            ST._GROUP_CACHE.pop(v_gid, None)
        except Exception:
            pass
        bot = getattr(event, "bot", None)
        if bot and not is_private:
            try:
                nodes = []
                for idx, txt in enumerate(outs):
                    nodes.append({"type": "node", "data": {"name": f"{raw.strip()}-{idx+1}", "uin": str(qq), "content": [{"type": "text", "data": {"text": txt[:4000]}}]}})
                await bot.call_action("send_group_forward_msg", group_id=int(gid), messages=nodes)
                try:
                    event.stop_event()
                except Exception:
                    pass
                return f"__HANDLED__已发送{raw.strip()}合并转发"
            except Exception as e:
                print(f"forward {raw.strip()} failed: {e}")
        merged = f"\n\n===== {raw.strip()} =====\n\n".join(outs)
        try:
            event.stop_event()
        except Exception:
            pass
        return merged
    except Exception as e:
        try:
            event.stop_event()
        except Exception:
            pass
        return f"{raw.strip()} 异常: {e}"


async def handle_admin_list(raw, gid, qq, is_admin, event):
    if raw.strip() != "超管列表":
        return None
    if not is_admin:
        try:
            event.stop_event()
        except Exception:
            pass
        return "无权限，仅超管可用"
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
        return txt
    except Exception as e:
        try:
            event.stop_event()
        except Exception:
            pass
        return f"超管列表异常: {e}"
