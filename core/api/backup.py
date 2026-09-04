# -*- coding: utf-8 -*-
"""备份 API"""
import base64
import os
import time
from astrbot.api.web import json_response

from .helpers import _err, get_req_query, get_req_json

try:
    from ... import store as ST
except ImportError:
    import store as ST


def _backup_base(plugin_base=""):
    if ST.BACKUP_DIR:
        return ST.BACKUP_DIR
    if hasattr(ST, "get_persistent_data_dir"):
        return os.path.join(ST.get_persistent_data_dir(plugin_base), "backups")
    if plugin_base:
        return os.path.join(plugin_base, "data", "backups")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "backups")


def _safe_backup(rel, base=""):
    b = base or _backup_base()
    p = os.path.abspath(os.path.join(b, str(rel or "").strip()))
    if p != b and not p.startswith(b + os.sep):
        return None
    return p


async def handle_backups_list(request, plugin_base=""):
    try:
        ST.maybe_auto_backup()
    except Exception:
        pass
    rel = get_req_query(request, "dir", "") or get_req_query(request, "path", "")
    root = _safe_backup(rel, _backup_base(plugin_base))
    if not root:
        return _err("bad dir", 400)
    if not os.path.isdir(root):
        return json_response({"dir": str(rel or ""), "dirs": [], "files": []})
    dirs, files = [], []
    base = _backup_base(plugin_base)
    for name in sorted(os.listdir(root)):
        f = os.path.join(root, name)
        r = os.path.relpath(f, base).replace(os.sep, "/")
        if os.path.isdir(f):
            try:
                mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(f)))
            except Exception:
                mtime = ""
            dirs.append({"name": name, "path": r, "mtime": mtime})
        elif os.path.isfile(f) and (name.endswith(".db") or name.endswith(".json")):
            try:
                sz = f"{os.path.getsize(f)//1024}KB"
                mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(f)))
            except Exception:
                sz = ""; mtime = ""
            files.append({"name": name, "path": r, "size": sz, "mtime": mtime})
    dirs.sort(key=lambda x: x["name"], reverse=True)
    files.sort(key=lambda x: x["name"], reverse=True)
    return json_response({"dir": str(rel or ""), "dirs": dirs, "files": files})


async def handle_backups_restore(request, plugin_base=""):
    p = await get_req_json(request, default={})
    rel = str((p.get("path") or p.get("file") or "") if isinstance(p, dict) else "").strip()
    if not rel:
        rel = get_req_query(request, "path", "") or get_req_query(request, "file", "")
    rel = str(rel).strip()
    if rel == "__backup_now__":
        dst = ST.backup_user_data(force=True)
        if dst:
            return json_response({"ok": True, "path": os.path.relpath(dst, _backup_base(plugin_base)).replace(os.sep, "/")})
        return _err("backup failed", 500)
    if not rel:
        return _err("path required", 400)
    src = _safe_backup(rel, _backup_base(plugin_base))
    if not src or not os.path.isfile(src) or not src.endswith(".db"):
        return _err("backup not found (need .db)", 404)
    try:
        import sqlite3
        cur_db = ST._DB
        with ST._LOCK:
            try:
                ST.flush_all()
            except Exception:
                pass
            try:
                cur_db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass
            cur_db.commit()
            src_conn = sqlite3.connect(src)
            src_conn.backup(cur_db)
            src_conn.close()
            cur_db.commit()
            ST._ACC_CACHE.clear()
            ST._GROUP_CACHE.clear()
        return json_response({"ok": True, "path": rel, "msg": "备份恢复成功！数据已实时加载生效。"})
    except Exception as e:
        return _err(f"restore failed: {e}", 500)


async def handle_backups_delete(request, plugin_base=""):
    p = await get_req_json(request, default={})
    rel = str((p.get("path") or p.get("file") or p.get("dir") or "") if isinstance(p, dict) else "").strip()
    if not rel:
        rel = get_req_query(request, "path", "") or get_req_query(request, "file", "") or get_req_query(request, "dir", "")
    rel = str(rel).strip()
    if not rel:
        return _err("path required", 400)
    fp = _safe_backup(rel, _backup_base(plugin_base))
    if not fp or not os.path.exists(fp):
        return _err("path not found", 404)
    base = _backup_base(plugin_base)
    if os.path.abspath(fp) == os.path.abspath(base):
        return _err("cannot delete root", 400)
    try:
        import shutil
        if os.path.isfile(fp):
            os.remove(fp)
            if fp.endswith(".db") and os.path.isfile(fp + ".json"):
                try:
                    os.remove(fp + ".json")
                except Exception:
                    pass
        elif os.path.isdir(fp):
            shutil.rmtree(fp)
        return json_response({"ok": True, "path": rel})
    except Exception as e:
        return _err(f"delete failed: {e}", 500)


async def handle_backups_export(request, plugin_base=""):
    rel = get_req_query(request, "path", "") or get_req_query(request, "file", "")
    if not rel:
        try:
            p = await get_req_json(request, default={})
            if isinstance(p, dict):
                rel = str(p.get("path") or p.get("file") or "").strip()
        except Exception:
            pass
    fp = None
    base = _backup_base(plugin_base)
    if not rel:
        if os.path.isdir(base):
            for root, _, files in os.walk(base):
                for fn in sorted(files, reverse=True):
                    if fn.endswith(".db"):
                        fp = os.path.join(root, fn)
                        rel = os.path.relpath(fp, base).replace(os.sep, "/")
                        break
                if fp:
                    break
    else:
        fp = _safe_backup(rel, base)
    if not fp or not os.path.exists(fp):
        return _err("backup file not found", 404)
    if os.path.isdir(fp):
        cands = [os.path.join(fp, x) for x in sorted(os.listdir(fp), reverse=True) if x.endswith(".db") and os.path.isfile(os.path.join(fp, x))]
        if cands:
            fp = cands[0]
            rel = os.path.relpath(fp, base).replace(os.sep, "/")
        else:
            return _err("file not found in directory", 404)
    try:
        if os.path.getsize(fp) > 50 * 1024 * 1024:
            return _err("file too large", 400)
        is_raw = get_req_query(request, "raw", "") in ("1", "true", "yes") or get_req_query(request, "download", "") in ("1", "true", "yes")
        if not is_raw:
            try:
                p2 = await get_req_json(request, default={})
                if isinstance(p2, dict) and str(p2.get("raw", "")).strip() in ("1", "true", "yes"):
                    is_raw = True
            except Exception:
                pass
        data = open(fp, "rb").read()
        b64 = base64.b64encode(data).decode()
        return json_response({"ok": True, "path": rel, "data": b64, "size": len(data), "filename": os.path.basename(fp)})
    except Exception as e:
        return _err(f"export failed: {e}", 500)


async def handle_clear_all(request, plugin_base=""):
    try:
        p = await get_req_json(request, default={})
        if not isinstance(p, dict) or p.get("confirm") != "确认删除":
            return _err("need confirm=确认删除", 400)
        if p.get("confirm2") != "确认":
            return _err("need confirm2=确认", 400)
        with ST._LOCK:
            if ST._DB:
                ST._DB.execute("DELETE FROM wallet")
                ST._DB.execute("DELETE FROM accounts")
                ST._DB.execute("DELETE FROM groups")
                ST._DB.execute("DELETE FROM redpacks")
                ST._DB.execute("DELETE FROM kv")
                ST._DB.commit()
                ST._ACC_CACHE.clear()
                ST._GROUP_CACHE.clear()
                try:
                    ST._DB.execute("DELETE FROM kv WHERE k='last_backup_ts'")
                    ST._DB.commit()
                except Exception:
                    pass
                ST._last_backup = 0
        try:
            base = _backup_base(plugin_base)
            if os.path.isdir(base):
                for root, _, files in os.walk(base):
                    for fn in files:
                        try:
                            os.remove(os.path.join(root, fn))
                        except Exception:
                            pass
        except Exception:
            pass
        return json_response({"cleared": True})
    except Exception as e:
        return _err(f"clear failed: {e}", 500)

async def handle_db_doctor(request, plugin_base=""):
    """执行数据库健康体检与碎片整理 (VACUUM + PRAGMA integrity_check + wal_checkpoint)"""
    try:
        if ST._DB is None:
            return _err("database not initialized", 500)

        # 1. 强制落盘脏数据
        try:
            ST.flush_all()
        except Exception:
            pass

        db_path = getattr(ST, "_DB_PATH", None) or os.path.join(plugin_base or _backup_base(plugin_base), "..", "xb.db")
        if not os.path.isfile(db_path):
            # 兼容默认 data/xb.db 或 data/nuli_slave.db / xbbot.db
            cands = [
                os.path.join(os.path.dirname(_backup_base(plugin_base)), "xb.db"),
                os.path.join(os.path.dirname(_backup_base(plugin_base)), "nuli_slave.db"),
                os.path.join(os.path.dirname(_backup_base(plugin_base)), "xbbot.db"),
                os.path.join(os.path.dirname(_backup_base(plugin_base)), "data.db")
            ]
            for c in cands:
                if os.path.isfile(c):
                    db_path = c
                    break

        wal_path = (db_path + "-wal") if (db_path and os.path.isfile(db_path + "-wal")) else ""
        
        size_before = 0
        if db_path and os.path.isfile(db_path):
            size_before += os.path.getsize(db_path)
        if wal_path and os.path.isfile(wal_path):
            size_before += os.path.getsize(wal_path)

        with ST._LOCK:
            cur = ST._DB.cursor()
            
            # 3. 运行完整性检查
            cur.execute("PRAGMA integrity_check(10)")
            integrity_rows = cur.fetchall()
            integrity_status = "正常 (OK)" if (integrity_rows and integrity_rows[0][0] == "ok") else str(integrity_rows)

            # 4. 统计各表数据行数
            counts = {}
            for tbl in ("wallet", "accounts", "groups", "redpacks", "kv"):
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                    counts[tbl] = cur.fetchone()[0]
                except Exception:
                    counts[tbl] = 0

            # 5. 执行 WAL 截断与 VACUUM 碎片整理
            try:
                cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass
            try:
                cur.execute("PRAGMA optimize")
            except Exception:
                pass
            try:
                cur.execute("VACUUM")
            except Exception:
                pass

        # 6. 统计整理后大小
        size_after = 0
        if db_path and os.path.isfile(db_path):
            size_after += os.path.getsize(db_path)
        if wal_path and os.path.isfile(wal_path):
            size_after += os.path.getsize(wal_path)

        def fmt_sz(s):
            if s <= 0: return "0 KB"
            if s < 1024 * 1024: return f"{s / 1024:.1f} KB"
            return f"{s / (1024 * 1024):.2f} MB"

        saved = max(0, size_before - size_after)

        return json_response({
            "ok": True,
            "integrity": integrity_status,
            "size_before": fmt_sz(size_before),
            "size_after": fmt_sz(size_after),
            "saved": fmt_sz(saved),
            "tables": counts,
            "msg": f"数据库健康体检完成！完整性状态：{integrity_status}，成功释放碎片空间：{fmt_sz(saved)}。"
        })
    except Exception as e:
        return _err(f"db doctor failed: {e}", 500)
