# -*- coding: utf-8 -*-
"""Layer 1 — Config Layer
负责配置归一、Schema 加载、指令索引收集。
被 main.XbBot 与 router 层复用，保持单一来源 store._CONFIG。
"""
import json
import os
import re


def _maybe_dict(v):
    if isinstance(v, str) and v[:1] == "{" and v[-1:] == "}":
        try:
            j = json.loads(v)
            if isinstance(j, dict):
                return j
        except Exception:
            pass
        try:
            import ast
            p = ast.literal_eval(v)
            if isinstance(p, dict):
                return p
        except Exception:
            pass
    return v


def _normalize_cfg(cfg):
    out = {}
    if not isinstance(cfg, dict):
        return out
    for k, v in cfg.items():
        k = str(k)
        if "__" in k:
            sec, key = k.split("__", 1)
            out.setdefault(sec, {})[key] = _maybe_dict(v)
        elif isinstance(v, dict):
            sec = k
            for kk, vv in v.items():
                out.setdefault(sec, {})[str(kk)] = _maybe_dict(vv)
        else:
            out.setdefault(k, {})[""] = str(v)
    return out


def _fallback_cfg(base_dir=""):
    cfg = {}
    try:
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # try file in plugin data/
        p = os.path.join(base_dir, "data", "config.json")
        # fallback: if base_dir is core/, go up one more
        if not os.path.isfile(p):
            p = os.path.join(os.path.dirname(base_dir), "data", "config.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                cfg = _normalize_cfg(json.load(f))
    except Exception:
        cfg = {}
    return cfg


def _load_schema(base_dir=""):
    p = ""
    try:
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p = os.path.join(base_dir, "_conf_schema.json")
        if not os.path.isfile(p):
            p = os.path.join(os.path.dirname(base_dir), "_conf_schema.json")
    except Exception:
        p = ""
    groups = {}
    defaults = {}
    try:
        with open(p, encoding="utf-8") as f:
            c = json.load(f)
        for sec, obj in c.items():
            if not isinstance(obj, dict):
                continue
            items = obj.get("items") if isinstance(obj.get("items"), dict) else {}
            for key, it in items.items():
                it = it if isinstance(it, dict) else {}
                d = it.get("default", "")
                t = it.get("type", "string")
                desc = it.get("description", "")
                groups.setdefault(sec, []).append({"key": key, "desc": desc, "default": d, "type": t})
                defaults["%s__%s" % (sec, key)] = d
    except Exception:
        pass
    return {"groups": groups, "defaults": defaults}


# 指令索引正则（与 main._collect_commands 保持一致）
_CMD_RE1 = re.compile(r'\b(?:text|m)\s*\.startswith\(\s*["\']([^"\']+)["\']')
_CMD_RE2 = re.compile(r'\b(?:text|m)\s*==\s*["\']([^"\']+)["\']')
_CMD_RE3 = re.compile(r'\b(?:text|m)\s*in\s*\(([^)]*)\)')


def _collect_commands(base_dir="", store=None):
    out = {}
    try:
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        eng_dir = os.path.join(base_dir, "engines")
        if not os.path.isdir(eng_dir):
            eng_dir = os.path.join(os.path.dirname(base_dir), "engines")
        # also try plugin root
        if not os.path.isdir(eng_dir):
            eng_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engines")
            eng_dir = os.path.abspath(eng_dir)
        for name in ("slave", "sign", "bank", "ent", "chat", "spirit", "ride", "superadmin", "guild", "adventure"):
            p = os.path.join(eng_dir, name + ".py")
            try:
                src = open(p, encoding="utf-8").read()
            except Exception:
                continue
            cmds = []
            for c in _CMD_RE1.findall(src) + _CMD_RE2.findall(src):
                c = c.strip()
                if c and re.search(r"[\u4e00-\u9fff]", c) and c not in cmds:
                    cmds.append(c)
            for body in _CMD_RE3.findall(src):
                for c in re.findall(r'["\']([^"\']+)["\']', body):
                    c = c.strip()
                    if c and re.search(r"[\u4e00-\u9fff]", c) and c not in cmds:
                        cmds.append(c)
            out[name] = cmds
        # 唤醒词显式展示
        try:
            if not base_dir:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sch_path = os.path.join(base_dir, "_conf_schema.json")
            if not os.path.isfile(sch_path):
                sch_path = os.path.join(os.path.dirname(base_dir), "_conf_schema.json")
            with open(sch_path, encoding="utf-8") as f:
                sch = json.load(f)
            wc = sch.get("唤醒词配置", {}).get("items", {}) if isinstance(sch.get("唤醒词配置"), dict) else {}
            for sysname, it in wc.items():
                eng_name = None
                for _e, _s in (("sign", "签到系统"), ("spirit", "精灵系统"), ("ent", "娱乐系统"), ("bank", "银行系统"), ("slave", "奴隶系统"), ("ride", "坐骑系统"), ("guild", "帮派系统"), ("adventure", "冒险系统"), ("superadmin", "超管系统")):
                    if _s == sysname:
                        eng_name = _e
                        break
                if eng_name is None:
                    continue
                default = str((it.get("default") if isinstance(it, dict) else "") or sysname)
                cur = None
                if store is not None and hasattr(store, "cfg"):
                    try:
                        cur = store.cfg("唤醒词配置", sysname, default)
                    except Exception:
                        cur = default
                else:
                    cur = default
                words = [w for w in re.split(r"[|，,]+", cur.strip()) if w.strip()] or [default]
                if default not in words:
                    words.insert(0, default)
                for w in words:
                    if w not in out.setdefault(eng_name, []):
                        out[eng_name].insert(0, w)
        except Exception:
            pass
    except Exception:
        pass
    return out
