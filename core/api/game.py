# -*- coding: utf-8 -*-
"""游戏画像 API — 奴隶 / 精灵 用户画像 + 精灵图鉴 + 身价校准"""
import json
from astrbot.api.web import json_response

from .helpers import _err

try:
    from ... import store as ST
    from ...engines import slave
except ImportError:
    import store as ST
    try:
        from engines import slave
    except ImportError:
        import slave  # type: ignore


async def handle_slave_users(request):
    try:
        gid = ""
        try: gid = str(request.query.get("gid") or "").strip()
        except Exception: gid = ""
        if not gid:
            try:
                j = await request.json()
                if isinstance(j, dict) and j.get("gid"): gid = str(j.get("gid")).strip()
            except Exception: pass

        default_init_price = ST.cfgi("费用配置", "初始身价", 500) if hasattr(ST, "cfgi") else 500
        if default_init_price <= 0: default_init_price = 500

        # 从 groups, wallet, accounts 聚合所有玩家
        out = []
        seen = set()

        if gid and gid.isdigit():
            st = slave.state(gid)
            for qq in st.sections():
                if not qq.isdigit(): continue
                u = slave.U(st, qq)
                p = int(u.get("price", "0") or 0)
                if p <= 0:
                    p = default_init_price
                    u["price"] = str(p)
                    st.mark_dirty(qq)
                seen.add((gid, str(qq)))
                out.append({
                    "gid": gid,
                    "qq": str(qq),
                    "name": slave.NOTE_NAMES.get(str(qq), u.get("name", "") or str(qq)),
                    "price": p,
                    "owner": u.get("owner", "") or "",
                    "owner_name": slave.NOTE_NAMES.get(u.get("owner", ""), u.get("owner", "")) if u.get("owner") else "",
                    "protect": u.get("protect_until", ""),
                    "slaves": len([s for s in st.sections() if s.isdigit() and st[s].get("owner") == str(qq)]),
                    "weapons": u.get("weapon", ""),
                    "treasures": u.get("treasure", ""),
                })
            # 补该群 wallet 中有资产但尚未初始化的用户
            if ST._DB:
                w_rows = ST._DB.execute("SELECT qq FROM wallet WHERE gid=?", (int(gid),)).fetchall()
                for (w_qq,) in w_rows:
                    w_qq = str(w_qq)
                    if (gid, w_qq) in seen: continue
                    u = slave.U(st, w_qq)
                    p = int(u.get("price", "0") or 0) or default_init_price
                    seen.add((gid, w_qq))
                    out.append({
                        "gid": gid, "qq": w_qq,
                        "name": slave.NOTE_NAMES.get(w_qq, w_qq),
                        "price": p, "owner": "", "owner_name": "",
                        "protect": "", "slaves": 0, "weapons": "", "treasures": ""
                    })
            slave.save(gid)
        else:
            gids = set()
            if ST._DB:
                for (g_id,) in ST._DB.execute("SELECT DISTINCT gid FROM groups").fetchall():
                    if str(g_id).isdigit(): gids.add(str(g_id))
                for (g_id,) in ST._DB.execute("SELECT DISTINCT gid FROM wallet").fetchall():
                    if str(g_id).isdigit(): gids.add(str(g_id))
                for (g_id,) in ST._DB.execute("SELECT DISTINCT gid FROM accounts").fetchall():
                    if str(g_id).isdigit(): gids.add(str(g_id))

            for g in gids:
                try:
                    st = slave.state(g)
                    for qq in st.sections():
                        if not qq.isdigit(): continue
                        u = slave.U(st, qq)
                        p = int(u.get("price", "0") or 0)
                        if p <= 0:
                            p = default_init_price
                            u["price"] = str(p)
                            st.mark_dirty(qq)
                        seen.add((g, str(qq)))
                        out.append({
                            "gid": g,
                            "qq": str(qq),
                            "name": slave.NOTE_NAMES.get(str(qq), u.get("name", "") or str(qq)),
                            "price": p,
                            "owner": u.get("owner", "") or "",
                            "owner_name": slave.NOTE_NAMES.get(u.get("owner", ""), u.get("owner", "")) if u.get("owner") else "",
                            "protect": u.get("protect_until", ""),
                            "slaves": len([s for s in st.sections() if s.isdigit() and st[s].get("owner") == str(qq)]),
                            "weapons": u.get("weapon", ""),
                            "treasures": u.get("treasure", ""),
                        })
                    slave.save(g)
                except Exception:
                    continue

        out.sort(key=lambda x: -x["price"])
        return json_response(out[:500])
    except Exception as e:
        return _err(f"slave users failed: {e}", 500)


async def handle_slave_calibrate(request):
    """一键校准全员奴隶身价：将全库所有 <=0 的身价批量修复为最新初始身价"""
    try:
        data = {}
        try: data = await request.json()
        except Exception: pass

        init_price = int(data.get("price", 0) or 0)
        if init_price <= 0:
            init_price = ST.cfgi("费用配置", "初始身价", 500) if hasattr(ST, "cfgi") else 500
        if init_price <= 0:
            init_price = 500

        fixed_count = 0
        gids = set()
        if ST._DB:
            for (g_id,) in ST._DB.execute("SELECT DISTINCT gid FROM groups").fetchall():
                if str(g_id).isdigit(): gids.add(str(g_id))
            for (g_id,) in ST._DB.execute("SELECT DISTINCT gid FROM wallet").fetchall():
                if str(g_id).isdigit(): gids.add(str(g_id))
            for (g_id,) in ST._DB.execute("SELECT DISTINCT gid FROM accounts").fetchall():
                if str(g_id).isdigit(): gids.add(str(g_id))

        for g in gids:
            try:
                st = slave.state(g)
                # 检查已开户用户
                for qq in list(st.sections()):
                    if not qq.isdigit(): continue
                    u = st[qq]
                    p = int(u.get("price", "0") or 0)
                    if p <= 0:
                        u["price"] = str(init_price)
                        st.mark_dirty(qq)
                        fixed_count += 1
                # 检查该群 wallet 玩家
                if ST._DB:
                    w_rows = ST._DB.execute("SELECT qq FROM wallet WHERE gid=?", (int(g),)).fetchall()
                    for (w_qq,) in w_rows:
                        w_qq = str(w_qq)
                        if not st.has_section(w_qq):
                            u = slave.U(st, w_qq)
                            u["price"] = str(init_price)
                            st.mark_dirty(w_qq)
                            fixed_count += 1
                slave.save(g)
            except Exception:
                continue

        ST.flush_all()
        return json_response({
            "ok": True,
            "fixed_count": fixed_count,
            "initial_price": init_price,
            "msg": f"已成功校准 {fixed_count} 名用户的奴隶身价为 {init_price} 金币！"
        })
    except Exception as e:
        return _err(f"slave calibrate failed: {e}", 500)


async def handle_spirit_users(request):
    try:
        gid = ""
        try:
            gid = str(request.query.get("gid") or "").strip()
        except Exception:
            gid = ""
        if not gid:
            try:
                j = await request.json()
                if isinstance(j, dict) and j.get("gid"):
                    gid = str(j.get("gid")).strip()
            except Exception:
                pass
        out = []
        q = "SELECT gid, qq, data FROM accounts"
        args = ()
        if gid and gid.isdigit():
            q += " WHERE gid=?"
            args = (int(gid),)
        elif gid and not gid.isdigit():
            rows = []
            return json_response([])
        rows = ST._DB.execute(q, args).fetchall() if ST._DB else []
        for g, qq, data in rows:
            g = str(g); qq = str(qq)
            try:
                kv = json.loads(data or "{}")
            except Exception:
                kv = {}
            sp_raw = kv.get("spirits", "")
            sp = {}
            if isinstance(sp_raw, dict):
                sp = sp_raw
            elif isinstance(sp_raw, str) and sp_raw.strip():
                try:
                    sp = json.loads(sp_raw)
                except Exception:
                    sp = {}
            if not isinstance(sp, dict) or not sp.get("list"):
                continue
            lst = sp.get("list") if isinstance(sp.get("list"), list) else []
            if not lst:
                continue

            def _power(it):
                try:
                    return int(it.get("level", 1)) * (int(it.get("hp", 0)) + int(it.get("atk", 0)) + int(it.get("def", 0)) + int(it.get("spa", 0)) + int(it.get("spd", 0))) // 5
                except Exception:
                    return 0

            active = str(sp.get("active", "") or "")
            bag = sp.get("bag", {}) if isinstance(sp.get("bag"), dict) else {}
            total_power = sum(_power(it) for it in lst)
            best = max(lst, key=_power) if lst else {}
            best_name = best.get("name", "") if isinstance(best, dict) else ""
            max_lv = max((int(it.get("level", 1)) for it in lst), default=1)
            out.append({
                "gid": g,
                "qq": qq,
                "name": getattr(slave, "NOTE_NAMES", {}).get(qq, kv.get("name", "") or qq),
                "count": len(lst),
                "active": active,
                "best": best_name,
                "max_level": max_lv,
                "total_power": total_power,
                "bag_count": len(bag),
                "bag": bag,
            })
        out.sort(key=lambda x: -x["total_power"])
        return json_response(out[:300])
    except Exception as e:
        return _err(f"spirit users failed: {e}", 500)


def _load_spirit_data():
    try:
        try:
            from ...engines import spirit
        except ImportError:
            import spirit  # type: ignore
        sp = dict(spirit._SPIRITS() or {})  # type: ignore
        mp = dict(spirit._MAPS() or {})
        sh = dict(spirit._SHOP() or {})
        return {"spirits": sp, "maps": mp, "shop": sh}
    except Exception:
        try:
            try:
                from ...engines import spirit_data as SD  # type: ignore
            except ImportError:
                import spirit_data as SD  # type: ignore
            return {"spirits": dict(getattr(SD, "SPIRITS", {})), "maps": dict(getattr(SD, "MAPS", {})), "shop": dict(getattr(SD, "SHOP", {}))}
        except Exception:
            return {"spirits": {}, "maps": {}, "shop": {}}


async def handle_spirits_get(request):
    return json_response(_load_spirit_data())


async def handle_spirits_save(request):
    payload = await request.json(default={})  # type: ignore
    if not isinstance(payload, dict):
        return _err("payload must be dict", 400)
    saved = []
    for key in ("spirits", "maps", "shop"):
        if key not in payload:
            continue
        val = payload[key]
        if not isinstance(val, dict):
            return _err(f"{key} must be dict", 400)
        ST.set_ini("精灵图鉴", key, json.dumps(val, ensure_ascii=False))
        saved.append(key)
    if not saved:
        return _err("no data (want spirits/maps/shop)", 400)
    try:
        ST.save_config()
        st_cfg = dict(ST._CONFIG or {})
        ST.sync_astrbot_config(st_cfg)
    except Exception:
        pass
    return json_response({"saved": True, "keys": saved})
