# -*- coding: utf-8 -*-
"""插件健康自检: 服务器 python3 verify_plugin.py 运行"""
import ast
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))


def die(kind, msg):
    print("[FAIL] %s: %s" % (kind, msg))
    return False


ok = True
cur_ver = ""

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
            cur_ver = str(m.get("version", "")).strip()
            print("[OK] metadata.yaml 解析成功 (当前版本: %s) 字段: %s" % (cur_ver, sorted(m.keys())))
            if miss:
                ok = die("metadata.yaml", "缺失必填: %s" % ",".join(miss))
    except Exception as e:
        ok = die("metadata.yaml", "yaml 解析异常: %s" % e)

# 2) 全部 Python 源码语法自检
py_count = 0
for root, dirs, files in os.walk(BASE):
    # 忽略临时和版本控制目录
    dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "scratch", ".pytest_cache")]
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, BASE).replace("\\", "/")
            try:
                ast.parse(open(p, encoding="utf-8").read())
                py_count += 1
            except Exception as e:
                ok = die(rel, "语法错误: %s" % e)
print("[OK] 全部 %d 个 Python 模块语法解析通过" % py_count)

# 3) 版本号 9 处强一致性校验
if cur_ver:
    version_locations = [
        ("metadata.yaml", r'version:\s*"([^"]+)"'),
        ("main.py", r'PLUGIN_VERSION\s*=\s*"([^"]+)"'),
        ("core/api/updater.py", r'return\s*"([^"]+)"'),
        ("core/api/users.py", r'PLUGIN_VERSION\s*=\s*"([^"]+)"'),
        ("engines/superadmin.py", r'ver\s*=\s*"([^"]+)"'),
        ("pages/admin/index.html", r'<span class="ver">v([^<]+)</span>'),
        ("pages/admin/app.js", r'version:\s*res\.version\s*\|\|\s*"([^"]+)"'),
        ("CHANGELOG.md", r'##\s*v([^\s]+)'),
        ("README.md", r'v(\d+\.\d+\.\d+)'),
    ]
    for rel, pat in version_locations:
        fp = os.path.join(BASE, rel)
        if not os.path.isfile(fp):
            ok = die(rel, "文件不存在")
            continue
        content = open(fp, "r", encoding="utf-8", errors="ignore").read()
        mat = re.search(pat, content)
        if not mat:
            ok = die(rel, "未能匹配到版本号 (正则: %s)" % pat)
        elif mat.group(1) != cur_ver:
            ok = die(rel, "版本号不一致: 期望 %s, 实际 %s" % (cur_ver, mat.group(1)))
        else:
            print("[OK] %s 版本号对齐 (%s)" % (rel, cur_ver))

# 4) _conf_schema.json
sp = os.path.join(BASE, "_conf_schema.json")
if not os.path.isfile(sp):
    ok = die("_conf_schema.json", "文件不存在")
else:
    try:
        c = json.load(open(sp, encoding="utf-8"))
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

# 5) 图鉴
gdir = os.path.join(BASE, "data", "gacha_img")
if os.path.isdir(gdir):
    n = sum(len(fs) for _, _, fs in os.walk(gdir))
    print("[OK] gacha_img %d 个文件" % n)
else:
    print("[WARN] data/gacha_img 不存在(抽卡不可用,其他功能正常)")

print("==================")
print("RESULT:", "ALL OK" if ok else "有 FAIL, 请按上方红色项处理")
