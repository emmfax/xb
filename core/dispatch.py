# -*- coding: utf-8 -*-
"""Dispatch — 薄层，委托 test_harness"""
from .test_harness import _TEST_PROBES, _setup_user, handle_test_probes as _th_probes, handle_admin_list as _th_admin  # noqa: F401
import time
try:
    from .. import store as ST  # noqa: F401
    from ..engines import slave  # noqa: F401
except ImportError:
    import store as ST  # noqa: F401
    try:
        from engines import slave  # noqa: F401
    except ImportError:
        from ..engines import slave  # type: ignore  # noqa: F401

# 兼容旧导入：保留 _TEST_PROBES / _setup_user
__all__ = ["_TEST_PROBES", "_setup_user", "handle_test_probes", "handle_admin_list"]

async def handle_test_probes(raw, gid, qq, is_admin, event, is_private):
    return await _th_probes(raw, gid, qq, is_admin, event, is_private)

async def handle_admin_list(raw, gid, qq, is_admin, event):
    try:
        return await _th_admin(raw, gid, qq, is_admin, event)
    except AttributeError:
        # fallback 本地（与 th 相同）
        if raw.strip() != "超管列表":
            return None
        if not is_admin:
            try:
                event.stop_event()
            except Exception:
                pass
            return "无权限，仅超管可用"
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
