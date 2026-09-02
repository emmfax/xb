# -*- coding: utf-8 -*-
"""插件健康自检: 服务器 python3 verify_plugin.py 运行"""
import ast
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))


def die(kind, msg):
    print("[FAIL] %s: %s" % (kind, msg))
    return False


ok = True
# 1) metadata.yaml
mp = os.path.join(BASE, "metadata.yaml")
if not os.path.isfile(mp):
    ok = die("metadata.yaml", "文件不存在")
else:
    try:
        import yaml
        m = yaml.safe_load(open(mp, encoding="utf-8"))
        if not isinstance(m, dict):
            ok = die("metadata.yaml", "yaml 解析结果非字典")
        else:
            req = ("name", "desc", "version", "author")
            miss = [k for k in req if not (k in m and isinstance(m[k], str) and m[k].strip())]
            print("[OK] metadata.yaml 解析成功 字段:", sorted(m.keys()))
            if miss:
                ok = die("metadata.yaml", "缺失必填: %s" % ",".join(miss))
    except Exception as e:
        ok = die("metadata.yaml", "yaml 解析异常: %s" % e)

# 2) main.py / store.py / engines
for f in ("main.py", "store.py", "engines/sign.py", "engines/bank.py",
          "engines/slave.py", "engines/ent.py", "engines/chat.py",
          "engines/spirit.py", "engines/spirit_data.py", "engines/ride.py",
          "engines/superadmin.py", "engines/guild.py", "engines/adventure.py"):
    p = os.path.join(BASE, f)
    if not os.path.isfile(p):
        ok = die(f, "文件不存在")
        continue
    try:
        ast.parse(open(p, encoding="utf-8").read())
        print("[OK] %s 语法" % f)
    except Exception as e:
        ok = die(f, "语法错误: %s" % e)

# 3) _conf_schema.json
sp = os.path.join(BASE, "_conf_schema.json")
if not os.path.isfile(sp):
    ok = die("_conf_schema.json", "文件不存在")
else:
    try:
        c = json.load(open(sp, encoding="utf-8"))
        # 官方嵌套: 顶层={系统:{type:"object", items:{键:{type:...}}}}
        def _check(schema, path=""):
            bads = []
            for k, v in schema.items():
                if not isinstance(v, dict) or "type" not in v:
                    bads.append("%s.%s" % (path, k))
                elif v["type"] == "object" and isinstance(v.get("items"), dict):
                    bads += _check(v["items"], "%s.%s" % (path, k))
            return bads
        bads = _check(c)
        if bads:
            ok = die("_conf_schema.json", "缺/非法 type 的项: %s" % bads[:8])
        else:
            nkey = sum(len(v.get("items") or {}) for v in c.values())
            print("[OK] _conf_schema.json 解析成功 系统数:%d 配置项:%d" % (len(c), nkey))
    except Exception as e:
        ok = die("_conf_schema.json", "JSON 异常: %s" % e)

# 4) 图鉴
gdir = os.path.join(BASE, "data", "gacha_img")
if os.path.isdir(gdir):
    n = sum(len(fs) for _, _, fs in os.walk(gdir))
    print("[OK] gacha_img %d 个文件" % n)
else:
    print("[WARN] data/gacha_img 不存在(抽卡不可用,其他功能正常)")

print("==================")
print("RESULT:", "ALL OK" if ok else "有 FAIL, 请按上方红色项处理")
