# -*- coding: utf-8 -*-
"""stats / rank API — 总览与排行榜"""
import json
from astrbot.api.web import json_response

try:
    from ... import store as ST
    from ...engines import slave
except ImportError:
    import store as ST
    try:
        from engines import slave
    except ImportError:
        import slave  # type: ignore


async def handle_stats(request=None):
    n_wallet = ST._DB.execute("SELECT COUNT(*) FROM wallet").fetchone()[0]
    n_acct = ST._DB.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    n_group = ST._DB.execute("SELECT COUNT(DISTINCT gid) FROM wallet").fetchone()[0]
    total = ST._DB.execute("SELECT COALESCE(SUM(money),0) FROM wallet").fetchone()[0]
    total_dep = 0
    try:
        total_dep = ST._DB.execute(
            "SELECT COALESCE(SUM(CAST(COALESCE(json_extract(data,'$.deposit'), json_extract(data,'$.cunkuan'), json_extract(data,'$.\"存款总数\"'), '0') AS INTEGER)),0) FROM accounts").fetchone()[0] if ST._DB else 0
    except Exception:
        total_dep = 0
    if not total_dep:
        try:
            s = 0
            for (d,) in ST._DB.execute("SELECT data FROM accounts").fetchall():
                try:
                    j = json.loads(d or "{}")
                    v = j.get("deposit") or j.get("cunkuan") or j.get("存款总数") or "0"
                    s += int(float(v or 0))
                except Exception:
                    pass
            if s:
                total_dep = s
        except Exception:
            pass
    n_sign = ST._DB.execute(
        "SELECT COALESCE(SUM(CAST(COALESCE(json_extract(data,'$.sign_count'), json_extract(data,'$.签到次数'), '0') AS INTEGER)),0) "
        "FROM accounts").fetchone()[0]
    return json_response({
        "players": {"wallet": n_wallet, "accounts": n_acct, "groups": n_group},
        "total_money": total,
        "total_deposit": int(total_dep or 0),
        "total_sign": n_sign,
    })


async def handle_rank(request):
    rtype = request.query.get("type", "money")
    if rtype == "tili":
        rtype = "stamina"
    if rtype == "meili":
        rtype = "charm"
    if rtype == "cunkuan":
        rtype = "deposit"
    sql = {
        "money": ("SELECT qq, money FROM wallet ORDER BY money DESC LIMIT 20", lambda r: (r[0], r[1])),
        "sign": ("SELECT qq, CAST(COALESCE(json_extract(data,'$.sign_count'), json_extract(data,'$.签到次数'), '0') AS INTEGER) "
                 "FROM accounts ORDER BY 2 DESC LIMIT 20", None),
        "stamina": ("SELECT qq, CAST(COALESCE(json_extract(data,'$.stamina'), json_extract(data,'$.tili'), '0') AS INTEGER) "
                 "FROM accounts ORDER BY 2 DESC LIMIT 20", None),
        "charm": ("SELECT qq, CAST(COALESCE(json_extract(data,'$.charm'), json_extract(data,'$.meili'), '0') AS INTEGER) "
                  "FROM accounts ORDER BY 2 DESC LIMIT 20", None),
        "deposit": ("SELECT qq, CAST(COALESCE(json_extract(data,'$.deposit'), json_extract(data,'$.cunkuan'), json_extract(data,'$.存款总数'), '0') AS INTEGER) "
                 "FROM accounts ORDER BY 2 DESC LIMIT 20", None),
    }.get(rtype)
    if not sql:
        rows = ST._DB.execute("SELECT qq, data FROM accounts ORDER BY qq LIMIT 20").fetchall()
    else:
        rows = ST._DB.execute(sql[0]).fetchall()
    nm = getattr(slave, "NOTE_NAMES", {}) or {}
    # 批量预取昵称，避免 N+1
    qq_list = [str(r[0]) for r in rows]
    g_names, a_names = {}, {}
    if qq_list:
        try:
            placeholders = ",".join("?" for _ in qq_list)
            for qq_, d in ST._DB.execute(f"SELECT qq, data FROM groups WHERE qq IN ({placeholders})", tuple(int(q) for q in qq_list)).fetchall():
                try:
                    j = json.loads(d or "{}")
                    if j.get("name"):
                        g_names[str(qq_)] = j["name"]
                except Exception:
                    pass
        except Exception:
            pass
        try:
            placeholders = ",".join("?" for _ in qq_list)
            for qq_, d in ST._DB.execute(f"SELECT qq, data FROM accounts WHERE qq IN ({placeholders})", tuple(int(q) for q in qq_list)).fetchall():
                try:
                    j = json.loads(d or "{}")
                    if j.get("name"):
                        a_names[str(qq_)] = j["name"]
                except Exception:
                    pass
        except Exception:
            pass
    out = []
    for r in rows:
        qq = str(r[0])
        name = nm.get(qq, "") or g_names.get(qq, "") or a_names.get(qq, "")
        if not name:
            try:
                name = slave.fetch_card("", qq) or ""
            except Exception:
                pass
        out.append({"qq": qq, "name": name, "value": r[1]})
    return json_response(out)
