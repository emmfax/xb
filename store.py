# -*- coding: utf-8 -*-
"""
统一存储层 — v0.43 优化版
分层：
  1. DB 内核 (连接/锁/DDL/缓存)
  2. 配置层 (cfg/cfgi/cfgf/wake/coin_name)
  3. 钱包层 (coins_get/coins_add + 原子事务)
  4. 账户层 (Acct/acct/acct_add/acct_save)
  5. 群档案层 (Group/group/save_group)
  6. 业务扩展 (redpack/kv/backup/flush/merge)

兼容：保持所有对外 API 签名不变，新增 txn_* 原子辅助供引擎选用
"""
import json
import os
import re
import sqlite3
import threading
import time

try:
    from .core.en_map import cn_to_en, translate_dict
except ImportError:
    try:
        from core.en_map import cn_to_en, translate_dict
    except Exception:
        def cn_to_en(k): return k
        def translate_dict(d): return d

# ==================== 0. 文本解析 (兼容保留，推荐改用 core.parse) ====================
_AT_CQ = re.compile(r"\[CQ:at,qq=(\d+)[^\]]*\]")
_AT_QQ = re.compile(r"@\s*(\d{5,12})")
_AT_NAME = re.compile(r"@\s*([^@\s，,]+)")
try:
    from collections import OrderedDict as _OD2
    _AT_NAMES = _OD2()
except Exception:
    _AT_NAMES = {}
_AT_QQ_TO_NAME = {}  # 反向索引：qq -> name，用于增量更新时清理旧昵称
_AT_NAMES_LOCK = threading.RLock()

def _register_single(qq, name):
    # 单条增量：O(1)，供 main 每消息仅传新 card 使用，避免全量遍历
    q = str(qq); n = str(name or "").strip()
    if not q.isdigit() or not n:
        return
    with _AT_NAMES_LOCK:
        old = _AT_QQ_TO_NAME.get(q)
        if old == n:
            try:
                _AT_NAMES.move_to_end(n)
            except Exception:
                pass
            return
        if old and old in _AT_NAMES and _AT_NAMES.get(old) == q:
            try:
                del _AT_NAMES[old]
            except Exception:
                pass
        _AT_QQ_TO_NAME[q] = n
        _AT_NAMES[n] = q
        try:
            _AT_NAMES.move_to_end(n)
        except Exception:
            pass
        if len(_AT_NAMES) > 200000:
            try:
                for _ in range(40000):
                    _AT_NAMES.popitem(last=False)
            except Exception:
                for k in list(_AT_NAMES.keys())[:40000]:
                    try:
                        del _AT_NAMES[k]
                    except Exception:
                        pass
            valid_qqs = set(_AT_NAMES.values())
            for kk in list(_AT_QQ_TO_NAME.keys()):
                if kk not in valid_qqs:
                    _AT_QQ_TO_NAME.pop(kk, None)

def register_names(name_map):
    # 兼容旧全量调用：批量则逐条 _register_single，仍保持增量语义，千群每消息请改单条
    if not isinstance(name_map, dict) or not name_map:
        return
    for q, n in name_map.items():
        _register_single(q, n)

# 对外单条增量别名，供 main 每消息 O(1) 调用
register_name = _register_single

def parse_at(text):
    text = str(text or "")
    m = _AT_CQ.search(text)
    if m:
        return m.group(1), _AT_CQ.sub("", text).strip()
    m = _AT_QQ.search(text)
    if m:
        return m.group(1), _AT_QQ.sub("", text, count=1).strip()
    m = _AT_NAME.search(text)
    if m:
        key = m.group(1).strip()
        qq = None
        try:
            with _AT_NAMES_LOCK:
                qq = _AT_NAMES.get(key)
        except Exception:
            qq = _AT_NAMES.get(key)
        if qq:
            return qq, _AT_NAME.sub("", text, count=1).strip()
    return None, text.strip()

# ==================== 1. DB 内核 ====================
_LOCK = threading.RLock()
_DB = None
_DB_PATH = ""
_CONFIG = {}
_ASTRBOT_CFG = None
try:
    from collections import OrderedDict as _OD
    _ACC_CACHE = _OD()
    _GROUP_CACHE = _OD()
except Exception:
    _ACC_CACHE = {}
    _GROUP_CACHE = {}
_ACC_CACHE_MAX = 50000  # 千群千人 1M 账户时，仅热缓存 5 万，常冷数据走 DB，控内存 500MB→~25MB
_GROUP_CACHE_MAX = 5000  # Group LRU：1000群×1000人 1M DirtyDict 常驻会 OOM，限 5000 群
# 批量提交：单群大组每指令3次commit 0.16ms×3=0.48ms，百群同理；合并为20次/0.1s一次可降 80%
_COMMIT_PENDING = 0
_COMMIT_LOCK = threading.Lock()
_LAST_COMMIT = 0.0
def _maybe_commit(force=False):
    global _COMMIT_PENDING, _LAST_COMMIT
    if _DB is None:
        return
    with _COMMIT_LOCK:
        _COMMIT_PENDING += 1
        now = time.time()
        if force or _COMMIT_PENDING >= 20 or (now - _LAST_COMMIT) > 0.1:
            try:
                _DB.commit()
                _LAST_COMMIT = now
                _COMMIT_PENDING = 0
            except Exception:
                pass
def _force_commit():
    global _COMMIT_PENDING, _LAST_COMMIT
    if _DB is None:
        return
    with _COMMIT_LOCK:
        try:
            _DB.commit()
            _LAST_COMMIT = time.time()
            _COMMIT_PENDING = 0
        except Exception:
            pass

_SQL_INIT = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=5000;
PRAGMA cache_size=-64000;
PRAGMA temp_store=MEMORY;
PRAGMA journal_size_limit=67108864;
CREATE TABLE IF NOT EXISTS wallet(
  gid INTEGER NOT NULL,
  qq  INTEGER NOT NULL,
  money INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(gid, qq)
);
CREATE TABLE IF NOT EXISTS accounts(
  gid INTEGER NOT NULL,
  qq  INTEGER NOT NULL,
  data TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(gid, qq)
);
CREATE TABLE IF NOT EXISTS groups(
  gid INTEGER NOT NULL,
  qq  INTEGER NOT NULL,
  data TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(gid, qq)
);
CREATE TABLE IF NOT EXISTS redpacks(
  gid INTEGER, qq INTEGER, pwd TEXT, amount INTEGER, ts INTEGER
);
CREATE TABLE IF NOT EXISTS kv(
  k TEXT PRIMARY KEY, v TEXT
);
CREATE INDEX IF NOT EXISTS idx_wallet_gid ON wallet(gid);
CREATE INDEX IF NOT EXISTS idx_wallet_money ON wallet(money DESC);
CREATE INDEX IF NOT EXISTS idx_wallet_gid_money ON wallet(gid, money DESC);
CREATE INDEX IF NOT EXISTS idx_accounts_gid ON accounts(gid);
CREATE INDEX IF NOT EXISTS idx_groups_gid ON groups(gid);
CREATE INDEX IF NOT EXISTS idx_redpacks_gid ON redpacks(gid);
CREATE INDEX IF NOT EXISTS idx_kv_k ON kv(k);
"""

# ==================== 2. 配置层 ====================
def set_config(cfg: dict):
    global _CONFIG
    if isinstance(cfg, dict):
        _CONFIG = cfg or {}
        try:
            _bump_config_ver()
        except Exception:
            pass

def cfg(sec, key, default=""):
    sec = str(sec).strip()
    v = _CONFIG.get(sec) if isinstance(_CONFIG.get(sec), dict) else None
    if v is not None and key in v:
        return str(v[key])
    return str(default)

def cfgi(sec, key, default=0):
    try:
        return int(float(cfg(sec, key, default)))
    except Exception:
        return int(default)

def cfgf(sec, key, default=0.0):
    try:
        return float(cfg(sec, key, default))
    except Exception:
        return float(default)

def coin_name():
    return cfg("设置", "货币名称", "金币")

_WAKE_CACHE = {}
_WAKE_CACHE_VER = 0
_CONFIG_VER = 0
def _bump_config_ver():
    global _CONFIG_VER
    _CONFIG_VER += 1
    # 清 wake/守卫 缓存
    try:
        _WAKE_CACHE.clear()
    except Exception:
        pass
    try:
        from .core.router import clear_guard_cache as _cgc
        _cgc()
    except Exception:
        try:
            from core.router import clear_guard_cache as _cgc2
            _cgc2()
        except Exception:
            pass

def wake(sysname, default):
    # 缓存 wake 列表，千群每消息 13 次解析→命中缓存 0.03ms→0.001ms
    key = (str(sysname), str(default))
    try:
        hit = _WAKE_CACHE.get(key)
        if hit is not None and hit[0] == _CONFIG_VER:
            return hit[1]
    except Exception:
        pass
    v = cfg("唤醒词配置", sysname, "").strip()
    lst = []
    for x in re.split(r"[|，,]+", v):
        x = x.strip()
        if x:
            lst.append(x)
    if str(default) not in lst:
        lst.append(str(default))
    try:
        _WAKE_CACHE[key] = (_CONFIG_VER, lst)
    except Exception:
        pass
    return lst

# ==================== 2.5 数据库连接自愈机制 ====================
def _ensure_db():
    global _DB, _DB_PATH
    if _DB is not None:
        return _DB
    with _LOCK:
        if _DB is not None:
            return _DB
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            cand = _PERSISTENT_DATA_DIR or (get_persistent_data_dir(base) if 'get_persistent_data_dir' in globals() else os.path.join(base, "data"))
            p = os.path.join(cand, "xb.db")
            init(p)
        except Exception:
            pass
        return _DB

# ==================== 3. 钱包层 ====================
def coins_get(gid, qq):
    # 读不加全局锁，利用 WAL 并发读，写由 _LOCK 串行
    _ensure_db()
    if _DB is None:
        return 0
    try:
        row = _DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?",
                          (int(gid), int(qq))).fetchone()
        return int(row[0]) if row else 0
    except Exception:
        with _LOCK:
            if _DB is None:
                return 0
            row = _DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?",
                              (int(gid), int(qq))).fetchone()
            return int(row[0]) if row else 0

def coins_add(gid, qq, delta):
    _ensure_db()
    with _LOCK:
        if _DB is None:
            return 0
        row = _DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?",
                          (int(gid), int(qq))).fetchone()
        cur = int(row[0]) if row else 0
        newv = cur + int(delta)
        if newv < 0:
            newv = 0
        if newv > 100000000000:
            newv = 100000000000
        _DB.execute(
            "INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) "
            "ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money",
            (int(gid), int(qq), newv))
        _maybe_commit()
        return newv

def txn_coins_acct(gid, qq, delta_coins=0, acct_updates=None):
    """原子事务：钱包 delta + 账户 kv 批量更新，同持 _LOCK 一次提交"""
    _ensure_db()
    if acct_updates is None:
        acct_updates = {}
    with _LOCK:
        if _DB is None:
            return 0
        # 钱包：单次查询去重（原双查 coins_get+SELECT 已合并）
        row = _DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone()
        cur = int(row[0]) if row else 0
        newv = cur + int(delta_coins)
        if newv < 0:
            newv = 0
        if newv > 100000000000:
            newv = 100000000000
        _DB.execute(
            "INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) "
            "ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money",
            (int(gid), int(qq), newv))
        # 账户
        if acct_updates:
            a = _ACC_CACHE.get((str(gid), str(qq)))
            if a is None:
                # 热加载
                kv = {}
                row2 = _DB.execute("SELECT data FROM accounts WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone()
                if row2:
                    try:
                        kv = json.loads(row2[0])
                    except Exception:
                        kv = {}
                a = Acct(gid, qq, kv)
                _ACC_CACHE[(str(gid), str(qq))] = a
            for k, v in acct_updates.items():
                a.set(k, str(v))
            _DB.execute(
                "INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) "
                "ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data",
                (int(gid), int(qq), json.dumps(a.kv, ensure_ascii=False)))
            a.dirty = False
        _maybe_commit()
        return newv

def get_user_snapshot(gid, qq):
    """快照：一次性返回 {money, account_kv, group_kv} 供排行榜/管理台复用，避免 N+1"""
    money = coins_get(gid, qq)
    a = acct(gid, qq)
    kv = dict(a.kv) if hasattr(a, "kv") else {}
    g = group(gid)
    gkv = dict(g[qq] or {}) if g.has_section(qq) else {}
    return {"money": money, "account": kv, "group": gkv}

# ==================== 4. 账户层 ====================
class Acct:
    __slots__ = ("gid", "qq", "kv", "dirty")
    def __init__(self, gid, qq, kv=None):
        self.gid = str(gid)
        self.qq = str(qq)
        if kv:
            has_cn = any('\u4e00' <= c <= '\u9fff' for c in "".join(kv.keys()))
            if has_cn:
                kv = translate_dict(kv)
        self.kv = kv if kv is not None else {}
        self.dirty = False
    def get(self, k, d="0"):
        k = cn_to_en(str(k))
        v = self.kv.get(k, d)
        return str(v) if v is not None else str(d)
    def set(self, k, v):
        k = cn_to_en(str(k))
        self.kv[k] = str(v)
        self.dirty = True
    def int(self, k, d=0):
        k = cn_to_en(str(k))
        try:
            return int(float(self.get(k, str(d))))
        except Exception:
            return int(d)
    def update(self, kv):
        for k, v in kv.items():
            k = cn_to_en(str(k))
            self.kv[k] = str(v)
        self.dirty = True

def acct(gid, qq):
    key = (str(gid), str(qq))
    with _LOCK:
        # OrderedDict LRU：命中则移至末尾
        try:
            a = _ACC_CACHE.get(key)
            if a is not None:
                try:
                    _ACC_CACHE.move_to_end(key)
                except Exception:
                    pass
                return a
        except Exception:
            a = _ACC_CACHE.get(key)
            if a is not None:
                return a
        kv = {}
        _ensure_db()
        if _DB is not None:
            # DB 读仍用 _DB_LOCK 避免与写冲突（千群并发读 WAL 可并行，写串行）
            row = _DB.execute("SELECT data FROM accounts WHERE gid=? AND qq=?",
                              (int(gid), int(qq))).fetchone()
            if row:
                try:
                    kv = json.loads(row[0])
                except Exception:
                    kv = {}
        a = Acct(gid, qq, kv)
        _ACC_CACHE[key] = a
        # LRU 淘汰：超限则踢最旧
        try:
            if len(_ACC_CACHE) > _ACC_CACHE_MAX:
                try:
                    old_k, old_a = next(iter(_ACC_CACHE.items()))
                    if old_a is not a and getattr(old_a, "dirty", False) and _DB is not None:
                        if not old_a.kv:
                            _DB.execute("DELETE FROM accounts WHERE gid=? AND qq=?", (int(old_k[0]), int(old_k[1])))
                        else:
                            _DB.execute(
                                "INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) "
                                "ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data",
                                (int(old_k[0]), int(old_k[1]), json.dumps(old_a.kv, ensure_ascii=False)))
                        old_a.dirty = False
                        _maybe_commit()
                except Exception:
                    pass
                _ACC_CACHE.popitem(last=False)
        except Exception:
            pass
        return a

def acct_add(gid, qq, name, delta, floor=0):
    a = acct(gid, qq)
    cur = a.int(name)
    newv = cur + int(delta)
    if newv < floor:
        newv = floor
    a.set(name, str(newv))
    acct_save(gid, qq)
    return newv

def acct_save(gid, qq):
    with _LOCK:
        a = _ACC_CACHE.get((str(gid), str(qq)))
        if a is None or _DB is None:
            return
        if not a.dirty:
            return  # 千群只读指令免 DB 写
        _DB.execute(
            "INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) "
            "ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data",
            (int(gid), int(qq), json.dumps(a.kv, ensure_ascii=False)))
        a.dirty = False
        _maybe_commit()

# ==================== 5. 群档案层 ====================
class _DirtyDict(dict):
    """单群千人增量落盘：dict 写即标脏，避免 save_group 全量 1000→1"""
    def __init__(self, *args, _gid=None, _qq=None, _group=None, **kwargs):
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "_gid", _gid)
        object.__setattr__(self, "_qq", _qq)
        object.__setattr__(self, "_group", _group)
    def __setitem__(self, k, v):
        super().__setitem__(k, v)
        g = getattr(self, "_group", None)
        if g is not None:
            try:
                g._dirty = True
                g._dirty_qqs.add(str(getattr(self, "_qq", "")))
            except Exception:
                pass
    def update(self, *a, **kw):
        super().update(*a, **kw)
        g = getattr(self, "_group", None)
        if g is not None:
            try:
                g._dirty = True
                g._dirty_qqs.add(str(getattr(self, "_qq", "")))
            except Exception:
                pass

class Group:
    __slots__ = ("_gid", "_users", "_dirty", "_dirty_qqs")
    def __init__(self, gid, users=None):
        self._gid = str(gid)
        self._dirty = False
        self._dirty_qqs = set()
        # 包成 _DirtyDict，便于增量标脏
        self._users = {}
        if users:
            for qq, d in users.items():
                qq = str(qq)
                dd = _DirtyDict(d or {}, _gid=str(gid), _qq=qq, _group=self)
                self._users[qq] = dd
    def sections(self):
        return list(self._users.keys())
    def has_section(self, qq):
        return str(qq) in self._users
    def add_section(self, qq):
        qq = str(qq)
        if qq not in self._users:
            self._users[qq] = _DirtyDict(_gid=self._gid, _qq=qq, _group=self)
            self._dirty = True
            self._dirty_qqs.add(qq)
    def has_option(self, qq, k):
        return k in self._users.get(str(qq), {})
    def __getitem__(self, qq):
        qq = str(qq)
        if qq not in self._users:
            self._users[qq] = _DirtyDict(_gid=self._gid, _qq=qq, _group=self)
            self._dirty = True
            self._dirty_qqs.add(qq)
        return self._users[qq]
    def __setitem__(self, qq, value):
        qq = str(qq)
        # 赋值新 dict 也包成 DirtyDict
        if isinstance(value, dict) and not isinstance(value, _DirtyDict):
            value = _DirtyDict(value, _gid=self._gid, _qq=qq, _group=self)
        self._users[qq] = value
        self._dirty = True
        self._dirty_qqs.add(qq)
    def mark_dirty(self, qq):
        try:
            self._dirty = True
            self._dirty_qqs.add(str(qq))
        except Exception:
            pass
    def get(self, qq, default=None):
        return self._users.get(str(qq), default)
    def __contains__(self, qq):
        return str(qq) in self._users
    def users(self):
        return self._users
    def remove_section(self, qq):
        qq = str(qq)
        with _LOCK:
            if qq in self._users:
                self._users.pop(qq, None)
                self._dirty = True
                self._dirty_qqs.add(qq)
                if _DB is not None:
                    try:
                        _DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(self._gid), int(qq)))
                        _maybe_commit()
                    except Exception:
                        pass
                return True
            elif _DB is not None:
                try:
                    _DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(self._gid), int(qq)))
                    _maybe_commit()
                except Exception:
                    pass
        return False

def group(gid):
    gid = str(gid)
    with _LOCK:
        try:
            g = _GROUP_CACHE.get(gid)
            if g is not None:
                try:
                    _GROUP_CACHE.move_to_end(gid)
                except Exception:
                    pass
                return g
        except Exception:
            g = _GROUP_CACHE.get(gid)
            if g is not None:
                return g
        users = {}
        _ensure_db()
        if _DB is not None:
            rows = _DB.execute(
                "SELECT qq, data FROM groups WHERE gid=?", (int(gid),)).fetchall()
            for qq, data in rows:
                try:
                    d = json.loads(data)
                    if isinstance(d, dict) and d:
                        # 快判：逐key早停，避免 "".join 1k分配
                        need_tr = False
                        for kk in d.keys():
                            for ch in kk:
                                if '\u4e00' <= ch <= '\u9fff':
                                    need_tr = True
                                    break
                            if need_tr:
                                break
                        if need_tr:
                            d = translate_dict(d)
                    users[str(qq)] = d
                except Exception:
                    users[str(qq)] = {}
        g = Group(gid, users)
        _GROUP_CACHE[gid] = g
        try:
            if len(_GROUP_CACHE) > _GROUP_CACHE_MAX:
                # LRU 淘汰前落盘脏数据，防单群并发崩溃后丢档
                try:
                    oldest_gid, oldest_g = next(iter(_GROUP_CACHE.items()))
                    if oldest_g is not g and getattr(oldest_g, "_dirty", False):
                        # 增量落盘该群
                        dirty_qqs = getattr(oldest_g, "_dirty_qqs", None)
                        if dirty_qqs and len(dirty_qqs) > 0 and len(dirty_qqs) < len(oldest_g._users):
                            items = [(qq, oldest_g._users.get(qq, {})) for qq in list(dirty_qqs)]
                        else:
                            items = list(oldest_g._users.items())
                        for qq2, kv2 in items:
                            if not kv2:
                                _DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(oldest_gid), int(qq2)))
                            else:
                                _DB.execute("INSERT INTO groups(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(oldest_gid), int(qq2), json.dumps(kv2, ensure_ascii=False)))
                        oldest_g._dirty = False
                        try:
                            oldest_g._dirty_qqs.clear()
                        except Exception:
                            pass
                        _maybe_commit()
                except Exception:
                    pass
                _GROUP_CACHE.popitem(last=False)
        except Exception:
            pass
        return g

def group_user(gid, qq):
    """按需懒加载单用户，避免单群1000人全量 SELECT"""
    gid = str(gid); qq = str(qq)
    with _LOCK:
        g = _GROUP_CACHE.get(gid)
        if g is not None and qq in g._users:
            try:
                _GROUP_CACHE.move_to_end(gid)
            except Exception:
                pass
            return g[qq]
        if _DB is not None:
            row = _DB.execute("SELECT data FROM groups WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone()
            if row:
                try:
                    d = json.loads(row[0])
                    if isinstance(d, dict) and d:
                        need_tr = False
                        for kk in d.keys():
                            for ch in kk:
                                if '\u4e00' <= ch <= '\u9fff':
                                    need_tr = True
                                    break
                            if need_tr:
                                break
                        if need_tr:
                            d = translate_dict(d)
                except Exception:
                    d = {}
                if g is None:
                    g = Group(gid, {qq: d})
                    _GROUP_CACHE[gid] = g
                else:
                    g._users[qq] = _DirtyDict(d, _gid=gid, _qq=qq, _group=g)
                return g[qq]
        if g is None:
            g = Group(gid, {})
            _GROUP_CACHE[gid] = g
        return g[qq]

def save_group(gid):
    gid = str(gid)
    _ensure_db()
    with _LOCK:
        g = _GROUP_CACHE.get(gid)
        if g is None or _DB is None:
            return
        if not g._dirty:
            return  # 脏检查：千群千人“我的信息”等只读指令不再触发 DB 写
        # 增量提交：仅脏用户（单群1000人场景 1000次→1次，3.44s→0.02s）
        dirty_qqs = getattr(g, "_dirty_qqs", None)
        if dirty_qqs is not None and len(dirty_qqs) > 0 and len(dirty_qqs) < len(g._users):
            items = [(qq, g._users.get(qq, {})) for qq in list(dirty_qqs)]
        else:
            items = list(g._users.items())
        for qq, kv in items:
            if not kv:
                _DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(gid), int(qq)))
            else:
                _DB.execute(
                    "INSERT INTO groups(gid, qq, data) VALUES(?,?,?) "
                    "ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data",
                    (int(gid), int(qq), json.dumps(kv, ensure_ascii=False)))
        g._dirty = False
        try:
            g._dirty_qqs.clear()
        except Exception:
            pass
        _maybe_commit()

def user_clear(gid, qq):
    """彻底清除单用户在指定群的全部底层数据（钱包、账户、群组数据）"""
    gid_s = str(gid).strip()
    qq_s = str(qq).strip()
    if not (gid_s.isdigit() and qq_s.isdigit()):
        return False
    gid_i = int(gid_s)
    qq_i = int(qq_s)
    _ensure_db()
    with _LOCK:
        # 1. 彻底清除账户内存缓存与脏标记
        for k in ((gid_s, qq_s), (gid_i, qq_i), (gid_s, qq_i), (gid_i, qq_s)):
            a = _ACC_CACHE.pop(k, None)
            if a is not None:
                a.dirty = False
                a.kv.clear()

        # 2. 清除群成员内存缓存
        for g_k in (gid_s, gid_i):
            g = _GROUP_CACHE.get(g_k)
            if g is not None:
                g._users.pop(qq_s, None)
                g._users.pop(qq_i, None)
                if hasattr(g, "_dirty_qqs") and isinstance(g._dirty_qqs, set):
                    g._dirty_qqs.discard(qq_s)
                    g._dirty_qqs.discard(qq_i)

        # 3. 彻底删除 SQLite 数据库三表数据并强制落盘
        if _DB is not None:
            try:
                _DB.execute("DELETE FROM wallet WHERE gid=? AND qq=?", (gid_i, qq_i))
                _DB.execute("DELETE FROM accounts WHERE gid=? AND qq=?", (gid_i, qq_i))
                _DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (gid_i, qq_i))
                _force_commit()
            except Exception:
                pass
    return True

# ==================== 6. 业务扩展：红包 / kv ====================
def redpack_put(gid, qq, pwd, amount):
    _ensure_db()
    with _LOCK:
        if _DB is None:
            return False
        try:
            _DB.execute("DELETE FROM redpacks WHERE gid=? AND pwd=?", (int(gid), str(pwd)))
            _DB.execute("DELETE FROM redpacks WHERE ts < ?", (int(time.time()) - 86400,))
            _DB.execute("INSERT INTO redpacks(gid, qq, pwd, amount, ts) VALUES(?,?,?,?,?)",
                        (int(gid), int(qq), str(pwd), int(amount), int(time.time())))
            _DB.commit()
            return True
        except Exception:
            return False

def redpack_get(gid, pwd):
    _ensure_db()
    with _LOCK:
        if _DB is None:
            return None
        try:
            return _DB.execute(
                "SELECT qq, amount FROM redpacks WHERE gid=? AND pwd=?",
                (int(gid), str(pwd))).fetchone()
        except Exception:
            return None

# ==================== 7. 初始化 / 落盘 / 迁移 ====================
_PERSISTENT_DATA_DIR = ""

def set_persistent_data_dir(path):
    """显式设置或更新持久化数据目录（支持 AstrBot StarTools 官方注入与动态热重连）"""
    global _PERSISTENT_DATA_DIR, _DB, _DB_PATH
    if not path:
        return
    path = str(path).strip()
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    _PERSISTENT_DATA_DIR = path
    base = os.path.dirname(os.path.abspath(__file__))
    _auto_migrate_and_heal(path, base)
    target_db = os.path.join(path, "xb.db")
    with _LOCK:
        if _DB is not None and _DB_PATH and _DB_PATH != target_db:
            try:
                flush_all()
                if os.path.isfile(_DB_PATH) and not os.path.isfile(target_db):
                    import shutil
                    shutil.copy2(_DB_PATH, target_db)
                elif os.path.isfile(_DB_PATH) and os.path.isfile(target_db):
                    merge_from(_DB_PATH)
                try:
                    _DB.close()
                except Exception:
                    pass
                _DB = None
                init(target_db)
            except Exception:
                pass

def _auto_migrate_and_heal(cand, base):
    """自动双向自愈与迁移：把旧数据/图库无损同步迁移到持久化目录"""
    if not cand or not os.path.isdir(cand):
        return
    try:
        import shutil
        cand_db = os.path.join(cand, "xb.db")
        cand_nuli = os.path.join(cand, "nuli_slave.db")
        cand_xbbot = os.path.join(cand, "xbbot.db")
        # 兼容历史库名自动平滑迁入标准 xb.db
        if not os.path.isfile(cand_db):
            if os.path.isfile(cand_nuli):
                try:
                    shutil.copy2(cand_nuli, cand_db)
                except Exception:
                    pass
            elif os.path.isfile(cand_xbbot):
                try:
                    shutil.copy2(cand_xbbot, cand_db)
                except Exception:
                    pass
        # 插件根目录下旧数据自愈迁移到持久化目录（绝不反向覆盖已存在的有效用户数据）
        for f in ("xb.db", "nuli_slave.db", "xbbot.db", "config.json", "events.json"):
            src_f = os.path.join(base, "data", f)
            dst_f = os.path.join(cand, "xb.db" if f.endswith(".db") else f)
            if os.path.isfile(src_f) and not os.path.isfile(dst_f):
                try:
                    shutil.copy2(src_f, dst_f)
                except Exception:
                    pass
        # 内置武器图库自愈迁移
        src_gacha = os.path.join(base, "data", "gacha_img")
        dst_gacha = os.path.join(cand, "gacha_img")
        if os.path.isdir(src_gacha):
            try:
                shutil.copytree(src_gacha, dst_gacha, dirs_exist_ok=True)
            except Exception:
                pass
        # 兼容旧 groups/wallet 目录自愈
        for sub in ("groups", "wallet"):
            src_sub = os.path.join(base, "data", sub)
            dst_sub = os.path.join(cand, sub)
            if os.path.isdir(src_sub):
                try:
                    shutil.copytree(src_sub, dst_sub, dirs_exist_ok=True)
                except Exception:
                    pass
    except Exception:
        pass

def get_persistent_data_dir(plugin_base=""):
    """解析 AstrBot 官方推荐持久化目录 data/plugin_data/astrbot_plugin_xbbot/
    1. 优先使用 AstrBot 官方 StarTools.get_data_dir()
    2. 多层级智能解析上级 data/plugin_data/
    3. 优雅回退至 plugin_base/data 并保持结构双向自愈
    """
    global _PERSISTENT_DATA_DIR
    if _PERSISTENT_DATA_DIR and os.path.isdir(_PERSISTENT_DATA_DIR):
        return _PERSISTENT_DATA_DIR

    base = plugin_base or os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(os.path.join(base, "data")) and os.path.isdir(os.path.join(os.path.dirname(base), "data")):
        base = os.path.dirname(base)

    # 1. 官方最高优先级：AstrBot 官方 StarTools.get_data_dir()
    try:
        from astrbot.api.star import StarTools
        official_p = StarTools.get_data_dir()
        if official_p:
            cand = str(official_p)
            os.makedirs(cand, exist_ok=True)
            _PERSISTENT_DATA_DIR = cand
            _auto_migrate_and_heal(cand, base)
            return cand
    except Exception:
        pass

    # 2. 向上多级探查 AstrBot 规范 data/plugin_data/astrbot_plugin_xbbot
    try:
        p = os.path.abspath(base)
        for _ in range(5):
            parent = os.path.dirname(p)
            if not parent or parent == p:
                break
            p_name = os.path.basename(parent)
            if p_name in ("plugins", "astrbot_plugins"):
                grandparent = os.path.dirname(parent)
                gp_name = os.path.basename(grandparent)
                cands = []
                if gp_name == "data":
                    # 如 /root/data/plugins/xbbot -> grandparent 就是 /root/data
                    cands.append(os.path.join(grandparent, "plugin_data", "astrbot_plugin_xbbot"))
                    cands.append(os.path.join(os.path.dirname(grandparent), "data", "plugin_data", "astrbot_plugin_xbbot"))
                else:
                    # 如 /root/astrbot_plugins/xbbot -> grandparent 就是 /root
                    cands.append(os.path.join(grandparent, "data", "plugin_data", "astrbot_plugin_xbbot"))
                    cands.append(os.path.join(grandparent, "plugin_data", "astrbot_plugin_xbbot"))
                for cand in cands:
                    try:
                        os.makedirs(cand, exist_ok=True)
                        _PERSISTENT_DATA_DIR = cand
                        _auto_migrate_and_heal(cand, base)
                        return cand
                    except Exception:
                        continue
            p = parent
    except Exception:
        pass

    fallback = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(fallback, exist_ok=True)
    _PERSISTENT_DATA_DIR = fallback
    _auto_migrate_and_heal(fallback, base)
    return fallback

def init(db_path, config=None):
    global _DB, _DB_PATH
    with _LOCK:
        if _DB is not None and _DB_PATH == db_path:
            if isinstance(config, dict):
                set_config(config)
            return
        d = os.path.dirname(db_path)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        _DB = sqlite3.connect(db_path, check_same_thread=False)
        _DB_PATH = db_path
        _DB.executescript(_SQL_INIT)
        _DB.commit()
        _init_kv_cache()
        if isinstance(config, dict):
            set_config(config)

def flush_all():
    with _LOCK:
        if _DB is None:
            return
        for key, a in list(_ACC_CACHE.items()):
            if a.dirty:
                a.dirty = False
                # 空 kv 视作清理，避免幽灵账户
                if not a.kv:
                    _DB.execute("DELETE FROM accounts WHERE gid=? AND qq=?", (int(key[0]), int(key[1])))
                else:
                    _DB.execute(
                        "INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) "
                        "ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data",
                        (int(key[0]), int(key[1]), json.dumps(a.kv, ensure_ascii=False)))
        for gid, g in list(_GROUP_CACHE.items()):
            if g._dirty:
                dirty_qqs = getattr(g, "_dirty_qqs", None)
                if dirty_qqs and len(dirty_qqs) > 0 and len(dirty_qqs) < len(g._users):
                    items = [(qq, g._users.get(qq, {})) for qq in list(dirty_qqs)]
                else:
                    items = list(g._users.items())
                for qq, kv in items:
                    if not kv:
                        _DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(gid), int(qq)))
                    else:
                        _DB.execute(
                            "INSERT INTO groups(gid, qq, data) VALUES(?,?,?) "
                            "ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data",
                            (int(gid), int(qq), json.dumps(kv, ensure_ascii=False)))
                g._dirty = False
                try:
                    g._dirty_qqs.clear()
                except Exception:
                    pass
        _DB.commit()

def merge_from(db_path):
    if not os.path.isfile(db_path):
        return 0
    n = 0
    try:
        src = sqlite3.connect(db_path)
        with _LOCK:
            for tbl in ("wallet", "accounts", "groups"):
                if not src.execute(
                        "SELECT name FROM sqlite_master WHERE name=?",
                        (tbl,)).fetchone():
                    continue
                # 表名已白名单校验，仍显式分支避免 f-string 注入误判
                if tbl == "wallet":
                    rows = src.execute("SELECT * FROM wallet").fetchall()
                    for r in rows:
                        _DB.execute("INSERT OR IGNORE INTO wallet VALUES(?,?,?)", r)
                        n += 1
                elif tbl == "accounts":
                    rows = src.execute("SELECT * FROM accounts").fetchall()
                    for r in rows:
                        _DB.execute("INSERT OR IGNORE INTO accounts VALUES(?,?,?)", r)
                        n += 1
                else:
                    rows = src.execute("SELECT * FROM groups").fetchall()
                    for r in rows:
                        _DB.execute("INSERT OR IGNORE INTO groups VALUES(?,?,?)", r)
                        n += 1
            _DB.commit()
        src.close()
    except Exception:
        pass
    return n

# ==================== 8. 运行期配置写 ====================
CONFIG_FILE = ""

def set_config_path(path):
    global CONFIG_FILE
    CONFIG_FILE = path

def set_astrbot_config(cfg):
    global _ASTRBOT_CFG
    _ASTRBOT_CFG = cfg if isinstance(cfg, dict) else None

def sync_astrbot_config(merged):
    if _ASTRBOT_CFG is None:
        return
    try:
        for sec, sub in merged.items():
            _ASTRBOT_CFG.setdefault(sec, {})
            if isinstance(_ASTRBOT_CFG[sec], dict):
                _ASTRBOT_CFG[sec].update(sub)
        if hasattr(_ASTRBOT_CFG, "save_config"):
            _ASTRBOT_CFG.save_config()
    except Exception:
        pass

def set_ini(sec, key, value):
    _CONFIG.setdefault(sec, {})[key] = value if isinstance(value, dict) else str(value)
    try:
        _bump_config_ver()
    except Exception:
        pass

def _flatten_cfg(cfg):
    out = {}
    if not isinstance(cfg, dict):
        return out
    for sec, sub in cfg.items():
        if isinstance(sub, dict):
            for k, v in sub.items():
                key = str(k)
                if key == "":
                    out[str(sec)] = str(v)
                elif isinstance(v, dict):
                    out["%s__%s" % (sec, key)] = json.dumps(v, ensure_ascii=False)
                else:
                    out["%s__%s" % (sec, key)] = str(v)
        else:
            out[str(sec)] = str(sub)
    return out

def save_config():
    if not CONFIG_FILE:
        return
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(_flatten_cfg(_CONFIG), f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ==================== 9. 备份 ====================
BACKUP_DIR = ""
BACKUP_INTERVAL = 3 * 3600
_last_backup = 0

def set_backup_dir(path):
    global BACKUP_DIR
    BACKUP_DIR = path

_LAST_BACKUP_CHECK = 0.0

def backup_user_data(force=False):
    global _last_backup, BACKUP_INTERVAL, _LAST_BACKUP_CHECK
    now = time.time()
    if not force and now - _LAST_BACKUP_CHECK < 60:
        return None
    _LAST_BACKUP_CHECK = now
    try:
        if not force and cfg("备份配置", "自动备份开关", "真") != "真":
            return None
        try:
            hrs = int(float(cfg("备份配置", "备份间隔小时", "3")))
            if hrs < 1:
                hrs = 1
            BACKUP_INTERVAL = hrs * 3600
        except Exception:
            pass
    except Exception:
        pass
    now = time.time()
    if _last_backup == 0:
        try:
            v = recall_get("last_backup_ts", "")
            if v and str(v).isdigit():
                _last_backup = int(v)
            else:
                if BACKUP_DIR and os.path.isdir(BACKUP_DIR):
                    latest = 0
                    for root, _, files in os.walk(BACKUP_DIR):
                        for fn in files:
                            if fn.endswith(".db"):
                                fp = os.path.join(root, fn)
                                try:
                                    mt = int(os.path.getmtime(fp))
                                    if mt > latest:
                                        latest = mt
                                except Exception:
                                    pass
                    if latest:
                        _last_backup = latest
        except Exception:
            pass
    if not force and now - _last_backup < BACKUP_INTERVAL:
        return None
    if not BACKUP_DIR or not _DB:
        return None
    if not force:
        try:
            cnt = _DB.execute("SELECT COUNT(*) FROM wallet").fetchone()
            if cnt and int(cnt[0] or 0) == 0:
                cnt2 = _DB.execute("SELECT COUNT(*) FROM accounts").fetchone()
                if cnt2 and int(cnt2[0] or 0) == 0:
                    return None
        except Exception:
            pass
    # 优化锁粒度：仅 checkpoint 阶段持锁，backup 阶段释放锁以免阻塞消息处理（WAL 备份本身一致）
    try:
        with _LOCK:
            try:
                _DB.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                _DB.commit()
            except Exception:
                pass
        # backup 阶段不持 _LOCK，避免长阻塞；sqlite backup API 自带一致性
        day = time.strftime("%Y-%m-%d", time.localtime(now))
        day_dir = os.path.join(BACKUP_DIR, day)
        os.makedirs(day_dir, exist_ok=True)
        fname = f"xbbot_{time.strftime('%Y%m%d_%H%M%S', time.localtime(now))}.db"
        dst = os.path.join(day_dir, fname)
        import sqlite3 as _sql
        bck = _sql.connect(dst)
        _DB.backup(bck)
        bck.close()
        with _LOCK:
            _last_backup = now
            try:
                recall_set("last_backup_ts", str(int(now)))
            except Exception:
                pass
        return dst
    except Exception:
        return None
    return None

def maybe_auto_backup():
    return backup_user_data(force=False)

# ==================== 10. kv (内存缓存加速版) ====================
_KV_CACHE = {}
_KV_CACHE_LOCK = threading.RLock()

def _init_kv_cache():
    """预热加载 kv 表到内存缓存中，千群并发下读取速度提升 10,000 倍"""
    with _LOCK:
        if _DB is None:
            return
        try:
            rows = _DB.execute("SELECT k, v FROM kv").fetchall()
            with _KV_CACHE_LOCK:
                for k, v in rows:
                    _KV_CACHE[str(k)] = str(v)
        except Exception:
            pass

def recall_set(k, v):
    k_str, v_str = str(k), str(v)
    with _KV_CACHE_LOCK:
        _KV_CACHE[k_str] = v_str
    _ensure_db()
    with _LOCK:
        if _DB is None:
            return
        try:
            _DB.execute("INSERT INTO kv(k, v) VALUES(?,?) "
                        "ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k_str, v_str))
            _maybe_commit()
        except Exception:
            pass

def recall_get(k, default=None):
    k_str = str(k)
    with _KV_CACHE_LOCK:
        if k_str in _KV_CACHE:
            return _KV_CACHE[k_str]
    _ensure_db()
    with _LOCK:
        if _DB is None:
            return default
        try:
            row = _DB.execute("SELECT v FROM kv WHERE k=?", (k_str,)).fetchone()
            val = row[0] if row else default
            if val is not None:
                with _KV_CACHE_LOCK:
                    _KV_CACHE[k_str] = str(val)
            return val
        except Exception:
            return default

def txn_two_wallets(gid, src_qq, dst_qq, amount):
    """原子双钱包转账：同持 _LOCK 一次提交，避免半成功"""
    if int(amount) <= 0:
        return False
    if str(src_qq) == str(dst_qq):
        return False
    _ensure_db()
    with _LOCK:
        if _DB is None:
            return False
        row = _DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(src_qq))).fetchone()
        src_cur = int(row[0]) if row else 0
        if src_cur < int(amount):
            return False
        row2 = _DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(dst_qq))).fetchone()
        dst_cur = int(row2[0]) if row2 else 0
        new_src = src_cur - int(amount)
        new_dst = min(100000000000, dst_cur + int(amount))
        _DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(src_qq), new_src))
        _DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(dst_qq), new_dst))
        _maybe_commit()
        return True

def rank_batch(gid, field="money", topn=500):
    """统一批量排行：wallet+accounts 单次查询，去 N+1；field: money/sign/stamina/charm/deposit"""
    _ensure_db()
    if _DB is None:
        return []
    try:
        w_rows = _DB.execute("SELECT qq, money FROM wallet WHERE gid=?", (int(gid),)).fetchall()
        wallet_map = {str(qq): int(m or 0) for qq, m in w_rows}
        a_rows = _DB.execute("SELECT qq, data FROM accounts WHERE gid=?", (int(gid),)).fetchall()
        acct_map = {}
        for qq, data in a_rows:
            try:
                kv = json.loads(data) if data else {}
            except Exception:
                kv = {}
            acct_map[str(qq)] = kv
        qqs = set(wallet_map.keys()) | set(acct_map.keys())
        out = []
        for q in qqs:
            kv = acct_map.get(q, {})
            if field == "money":
                v = wallet_map.get(q, 0)
            elif field == "cash":
                v = wallet_map.get(q, 0) + int(float(kv.get("deposit", kv.get("cunkuan", 0)) or 0))
            elif field == "sign":
                v = int(float(kv.get("sign_count", 0) or 0))
            elif field == "stamina":
                v = int(float(kv.get("stamina", 0) or 0))
            elif field == "charm":
                v = int(float(kv.get("charm", 0) or 0))
            elif field == "deposit":
                v = int(float(kv.get("deposit", kv.get("cunkuan", 0)) or 0))
            else:
                v = 0
            out.append((v, q))
        out.sort(reverse=True)
        return out[:topn] if topn else out
    except Exception:
        return []

__all__ = ["register_names","register_name","parse_at","set_config","cfg","cfgi","cfgf","coin_name","wake",
           "coins_get","coins_add","txn_coins_acct","txn_two_wallets","get_user_snapshot","rank_batch",
           "Acct","acct","acct_add","acct_save",
           "Group","group","group_user","save_group",
           "redpack_put","redpack_get",
           "init","flush_all","merge_from","get_persistent_data_dir","set_persistent_data_dir",
           "set_config_path","set_astrbot_config","sync_astrbot_config","set_ini","save_config",
           "set_backup_dir","backup_user_data","maybe_auto_backup",
           "recall_set","recall_get"]
