# -*- coding: utf-8 -*-
"""验证四项修复"""
import pathlib, re, json, sys, os
BASE = pathlib.Path(__file__).parent.parent

def check_adventure():
    p = BASE / "engines" / "adventure.py"
    txt = p.read_text(encoding="utf-8")
    assert "RANDOM_EVENTS" in txt, "adventure missing RANDOM_EVENTS"
    assert "CHOICE_LABELS" in txt, "adventure missing CHOICE_LABELS"
    assert "_pick_event" in txt, "adventure missing _pick_event"
    # check MAPS long narratives
    m = re.search(r'MAPS\s*=\s*\{([^}]+)\}', txt, re.S)
    # simpler: import and check length
    sys.path.insert(0, str(BASE))
    sys.path.insert(0, str(BASE / "engines"))
    from engines import adventure as adv
    for k, v in adv.MAPS.items():
        assert len(v[0]) > 100, f"{k} intro too short"
        assert len(v[1]) > 50, f"{k} scene too short"
    assert len(adv.RANDOM_EVENTS) >= 20, "random events too few"
    assert len(adv.MAP_SPECIFIC_EVENTS) >= 9, "map specific missing"
    # test narrative generation
    import store as ST
    import tempfile
    tmp = tempfile.mktemp(suffix=".db")
    ST.init(tmp, {"冒险配置": {"冒险消耗体力": "0", "冒险需要金钱": "0", "冒险间隔": "0"}})
    ST.coins_add("1000", "123456", 10000)
    ST.acct("1000", "123456").set("stamina", "100")
    ST.acct_save("1000", "123456")
    msg = adv.cmd_start("1000", "123456", "迷失海岛")
    assert len(msg) > 300, f"cmd_start narrative too short {len(msg)}"
    msg2 = adv.cmd_choose("1000", "123456", "1")
    assert len(msg2) > 100, "cmd_choose too short"
    assert "选择" in msg2, "choose missing choice hint"
    print("[PASS] adventure long narratives + random events + choices")

def check_spirit_users():
    txt = (BASE / "main.py").read_text(encoding="utf-8")
    assert "page_spirit_users" in txt, "missing page_spirit_users"
    assert "spirit/users" in txt, "missing spirit/users route"
    assert "total_power" in txt, "spirit users missing power calc"
    # pages
    idx = (BASE / "pages" / "admin" / "index.html").read_text(encoding="utf-8")
    assert "spirit_users" in idx, "missing spirit_users tab"
    assert "精灵系统 · 用户情况" in idx, "missing spirit users section"
    app = (BASE / "pages" / "admin" / "app.js").read_text(encoding="utf-8")
    assert "loadSpiritUsers" in app, "missing loadSpiritUsers"
    assert 'spirit/users' in app, "missing spirit/users api call"
    assert "TAB_LOADERS" in app and "spirit_users" in app, "missing tab loader"
    print("[PASS] spirit users tab + backend")

def check_users_export():
    txt = (BASE / "main.py").read_text(encoding="utf-8")
    # check raw handling in page_users_export
    assert 'page_users_export' in txt
    # find raw block
    assert 'is_raw' in txt and 'users/export' not in txt or 'raw' in txt
    # ensure _raw_file_response used in export
    # locate page_users_export section
    seg = txt[txt.find("async def page_users_export"):txt.find("async def page_users_import")+500]
    assert "_raw_file_response" in seg, "users export missing raw file response"
    assert 'bridge.download' in (BASE / "pages" / "admin" / "app.js").read_text(encoding="utf-8"), "missing bridge.download"
    app = (BASE / "pages" / "admin" / "app.js").read_text(encoding="utf-8")
    # exportAllUsers must try bridge.download
    assert 'exportAllUsers' in app
    exp_seg = app[app.find("async function exportAllUsers"):app.find("async function exportAllUsers")+1500]
    assert 'bridge.download' in exp_seg, "exportAllUsers missing bridge.download"
    assert 'raw' in exp_seg, "exportAllUsers missing raw param"
    assert 'testExportLinks' in app, "missing testExportLinks"
    print("[PASS] users export raw + bridge.download + test")

def check_superadmin():
    sup = (BASE / "engines" / "superadmin.py").read_text(encoding="utf-8")
    # superadmin handle should check is_admin param, not QQ list
    assert "is_admin" in sup, "superadmin missing is_admin"
    # ensure no hardcoded QQ whitelist like superadmin_qq or admin_qq list
    assert "admin_qq" not in sup.lower() and "super_qq" not in sup.lower(), "stale QQ whitelist"
    main = (BASE / "main.py").read_text(encoding="utf-8")
    # ensure old group admin cache removed
    assert "_is_group_owner_or_admin" not in main, "old group admin logic not deleted"
    assert "_GROUP_ADMIN_CACHE" not in main, "old cache not deleted"
    # ensure _dispatch only uses event.is_admin()
    dispatch_seg = main[main.find("async def _dispatch"):main.find("async def _dispatch")+2000]
    assert "event.is_admin()" in dispatch_seg, "missing event.is_admin()"
    assert "群聊管理员" not in dispatch_seg, "old group admin promotion not deleted"
    print("[PASS] superadmin aligned to AstrBot is_admin only")

if __name__ == "__main__":
    check_adventure()
    check_spirit_users()
    check_users_export()
    check_superadmin()
    print("ALL 4 FIXES PASS")
