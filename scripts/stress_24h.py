# -*- coding: utf-8 -*-
"""24h高并发等效压测（加速模拟）：群聊游戏 + WebUI API
模拟 24h 生产流量：多群×多用户×混合指令（签到/新手/排行/接龙/银行/冒险/精灵/奴隶/私聊）
+ Web API 并发调用。断言：零DB原文泄漏、零未捕获异常、总量守恒、超时自愈生效。
用法：python -X utf8 scripts/stress_24h.py
"""
import asyncio
import os
import random
import statistics
import sys
import tempfile
import threading
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import store as ST  # noqa: E402
from core import router as R  # noqa: E402
from engines import sign, bank, slave, ent, chat, spirit, ride, superadmin, guild, adventure  # noqa: E402

ENGINES = {"slave": slave, "sign": sign, "bank": bank, "ent": ent, "spirit": spirit,
           "ride": ride, "guild": guild, "adventure": adventure, "chat": chat,
           "superadmin": superadmin}

TMP = tempfile.mkdtemp(prefix="xb_stress_")
ST.init(os.path.join(TMP, "xb.db"), {})
ST.set_backup_dir(os.path.join(TMP, "backups"))

GIDS = ["10001", "10002", "10003"]
QQS = [str(200000 + i) for i in range(30)]
BAD_PATTERNS = ("database is locked", "cannot rollback", "no transaction",
                "sqlite", "misuse", "not defined", "traceback")

TRAFFIC = (["签到", "领取新手礼包", "财富榜", "签到榜", "我的信息", "个人排行",
            "开始接龙", "加入接龙", "当前接龙", "结束接龙",
            "抽奖", "购买体力 1", "冒险 迷失海岛", "选择 1", "当前冒险",
            "领养精灵", "我的精灵", "银行", "存款 100", "取款 50", "转账",
            "发红包 2000", "抢红包", "猜拳 石头", "扔炸弹", "打卡", "点赞"]
           + ["hello", "你好", "菜单", "签到系统", "娱乐系统"])

lat = []
lat_lock = threading.Lock()
leaks = []
leak_lock = threading.Lock()
errs = []
err_lock = threading.Lock()
OPS = 0
OPS_LOCK = threading.Lock()


def one_op(seed):
    global OPS
    rng = random.Random(seed)
    gid = rng.choice(GIDS)
    qq = rng.choice(QQS)
    raw = rng.choice(TRAFFIC)
    if raw == "转账":
        raw = "转账 %s %d" % (rng.choice(QQS), rng.choice([2000, 5000]))
    if raw == "扔炸弹":
        raw = "扔炸弹 @%s" % rng.choice(QQS)
    t0 = time.perf_counter()
    try:
        r = R.handle(gid, qq, raw, is_private=False, is_admin=False,
                     store=ST, engines=ENGINES, chat_mod=chat, superadmin_mod=superadmin)
        dt = (time.perf_counter() - t0) * 1000
        with lat_lock:
            lat.append(dt)
        if isinstance(r, str):
            low = r.lower()
            for p in BAD_PATTERNS:
                if p in low:
                    with leak_lock:
                        leaks.append((raw, r[:120]))
                    break
    except Exception as e:  # noqa: BLE001 - 任何逃逸异常即失败
        with err_lock:
            errs.append((raw, repr(e)[:150]))
    with OPS_LOCK:
        OPS += 1


def test_timeout_selfheal():
    # 接龙30s超时自愈 + 冒险30min过期
    gid, owner, other = "91001", "80001", "80002"
    r1 = ent.handle(gid, owner, "开始接龙")
    assert r1 and "接龙开始" in r1, r1
    ST.recall_set(f"chain_start_{gid}", str(int(time.time()) - 31))
    ST.recall_set(f"chain_last_time_{gid}", str(int(time.time()) - 31))
    r2 = ent.handle(gid, other, "加入接龙")
    assert "30" in str(r2) or "没有进行中" in str(r2) or "新的一局" in str(r2), r2
    r3 = ent.handle(gid, other, "开始接龙")
    assert "接龙开始" in str(r3), r3
    ent.handle(gid, owner, "结束接龙")
    # 冒险过期（先注资体力与金币，否则开局前置校验失败）
    ST.coins_add(gid, owner, 100000)
    ST.acct_add(gid, owner, "stamina", 1000)
    adventure.cmd_start(gid, owner, "迷失海岛")
    a = adventure._cur(gid, owner)
    assert a.get("map"), "adventure start failed"
    a["ts"] = int(time.time()) - 31 * 60
    adventure._save(gid, owner, a)
    assert adventure._cur(gid, owner) == {}, "adventure TTL failed"
    r4 = adventure.cmd_choose(gid, owner, "abc")
    assert "尚未开始冒险" in str(r4), r4  # 已过期 → 视为未开始
    # 活跃冒险中非法输入必须提示格式、不得随机推进（清冷却后重开）
    ST.recall_set("advt_%s_%s" % (gid, owner), "0")
    adventure.cmd_start(gid, owner, "迷失海岛")
    r5 = adventure.cmd_choose(gid, owner, "abc")
    assert "1 / 2 / 3" in str(r5), r5
    return True


def test_money_conservation():
    gid, a, b = "92001", "81001", "81002"
    ST.coins_add(gid, a, 100000)
    ST.coins_add(gid, b, 100000)
    before = ST.coins_get(gid, a) + ST.coins_get(gid, b)
    for _ in range(50):
        ST.txn_two_wallets(gid, a, b, 1000)
        ST.txn_two_wallets(gid, b, a, 1000)
    after = ST.coins_get(gid, a) + ST.coins_get(gid, b)
    assert before == after, (before, after)
    return True


async def webui_storm():
    import types
    # 无AstrBot运行时：桩掉 astrbot.api.web，仅验API逻辑与并发安全
    if "astrbot" not in sys.modules:
        _ab = types.ModuleType("astrbot")
        _api = types.ModuleType("astrbot.api")
        _web = types.ModuleType("astrbot.api.web")
        _web.json_response = lambda data, status=200: {"_stub_json": data, "status": status}
        _web.error_response = lambda msg, code=500: {"_stub_err": msg, "code": code}
        _web.request = object
        _ab.api = _api
        _api.web = _web
        sys.modules["astrbot"] = _ab
        sys.modules["astrbot.api"] = _api
        sys.modules["astrbot.api.web"] = _web
    from core.api.stats import handle_stats
    from core.api.backup import handle_backups_list
    from core.api.groups import handle_groups_list
    from core.api.users import handle_users
    oks, fails = 0, 0
    async def call(fn, *a):
        nonlocal oks, fails
        try:
            await fn(*a)
            oks += 1
        except Exception:  # noqa: BLE001
            fails += 1
    tasks = []
    for _ in range(20):
        tasks.append(call(handle_stats))
        tasks.append(call(handle_backups_list, None, BASE))
        tasks.append(call(handle_groups_list, None))
        tasks.append(call(handle_users, None))
    await asyncio.gather(*tasks)
    return oks, fails


def main():
    t0 = time.time()
    # 阶段1：功能自愈与守恒
    test_timeout_selfheal()
    test_money_conservation()
    print("[1/3] selfheal+conservation PASS")
    # 阶段2：群聊高并发（16线程×300 = 4800 ops，约等效24h消息量级）
    from concurrent.futures import ThreadPoolExecutor
    N_THREAD, N_OP = 16, 300
    with ThreadPoolExecutor(max_workers=N_THREAD) as pool:
        futs = [pool.submit(one_op, 100000 + i) for i in range(N_THREAD * N_OP)]
        for f in futs:
            f.result()
    lat_sorted = sorted(lat)
    p50 = statistics.median(lat_sorted)
    p95 = lat_sorted[int(len(lat_sorted) * 0.95)]
    print(f"[2/3] chat storm: ops={OPS} p50={p50:.2f}ms p95={p95:.2f}ms leaks={len(leaks)} errors={len(errs)}")
    for raw, s in leaks[:5]:
        print("  LEAK:", raw, "->", s)
    for raw, s in errs[:5]:
        print("  ERR:", raw, "->", s)
    # 阶段3：WebUI风暴
    oks, fails = asyncio.run(webui_storm())
    print(f"[3/3] webui storm: ok={oks} fail={fails}")
    total = time.time() - t0
    ok = (not leaks) and (not errs) and fails == 0 and p95 < 500
    print(f"TOTAL {total:.1f}s RESULT: {'ALL OK' if ok else 'FAILED'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
