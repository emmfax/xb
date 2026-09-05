# 小白机器人 (astrbot_plugin_xbbot) — 核心速查与环境状态卡 (AIINFO)

## 📌 项目基本元数据

| 项目属性 | 当前值 |
| :--- | :--- |
| **插件名称** | `astrbot_plugin_xbbot` (小白统一模块) |
| **当前版本** | `v0.68.24` (已发布并在 GitHub 与本地保持对齐) |
| **项目作者** | Light (`faxlight@faxt.top`) |
| **开源仓库** | `https://github.com/emmfax/xb` |
| **主代码目录** | `c:\Users\Light\Desktop\DRxb\astrbot_plugins\astrbot_plugin_xbbot` |
| **离线发行包** | `C:\Users\Light\Desktop\DRxb\astrbot_plugin_xbbot_v0.68.24.zip` |
| **平台依赖** | AstrBot >= 3.4.0, Python >= 3.10 (支持 3.14t/自由线程) |
| **底层协议端** | OneBot v11 (aiocqhttp), NapCat, Lagrange 原生图文 |

---

## 🚦 系统运行状态诊断指标

- **Python 模块语法解析**：40/40 语法解析通过 (100%)
- **版本号强一致性对齐**：9/9 处对齐为 `0.68.24` (100%)
- **读副本分离 (v0.68.24)**：`coins_get/recall_get` 走 `query_only` 独立连接，16线程×100混合读写零误差
- **死亡代码清理 (v0.68.24)**：`pages/admin/tabs/` 12文件已删（全库零引用确认）
- **配置项定义模式**：28 个系统，296 个配置项解析通过 (100%)
- **WebUI 前端元素检查**：163 个 DOM ID 无重复；43 个 API 端点 100% 对齐后置路由
- **主事件循环延迟 (Lag)**：0ms 纯内存极速分发（已根除旧版 56s 阻塞）
- **数据库死锁与回滚**：已根除 `cannot rollback - no transaction is active` 与 `database is locked`
- **24h等效压测 (`scripts/stress_24h.py`)**：4800 ops群聊风暴 p50 11ms/p95 41ms，DB原文零泄漏零逃逸异常；WebAPI 80/80；接龙30s/冒险30min自愈与资金守恒断言通过 (v0.68.23)
- **全库体检修复台账**：P0×4（精灵无限循环/红包印钱/误删同名/脏数据崩群）+ P1×8（转账截断/清空导入/冒险过期/口令吞数/打劫双花/边界/私聊限频/备份雪崩）已全部落地

---

## 🗂️ 核心文件及职责速查

| 文件路径 | 核心职责与关键维护点 |
| :--- | :--- |
| `main.py` | 插件主入口。`__init__` 中守护线程 `xb-auto-backup` 运行后台冷备与清理；`_dispatch` 纯内存异步分发（0ms）；注册 47 个 Web API |
| `store.py` | 现代 SQLite WAL 模式。全局锁 `_LOCK`；`clean_old_backups` 默认保留 30 份数据；`_safe_commit` 与 `_safe_rollback` 优雅降级 |
| `core/webdav.py` | 纯标准库 WebDAV 备份客户端。支持 Alist/坚果云/NAS；探测超时 8s，上传超时 25s；后台线程异步静默上传 |
| `core/platform.py` | 消息链跨平台构建，原生成分转换，群名片异步后台落盘 |
| `core/router.py` | 统一主路由分发中心，主菜单生成，双分支测试探针 |
| `core/api/backup.py` | WebUI 备份相关 API。包含 WebDAV 连通性测试与立即云备份端点（全面异步化） |
| `core/api/updater.py`| GitHub 云端版本检测。`asyncio.to_thread` 异步执行 |
| `pages/admin/index.html` | Web 管理控制台前端骨架。13 大 Tab 视图 |
| `pages/admin/app.js` | Web 控制台核心 JS 逻辑。包含 WebDAV 测试与云备份事件监听 |
| `engines/sign.py` | 签到与新手礼包。原子加币、首签历史记录 GC 纳入全局互斥 |
| `engines/ent.py` | 接龙等娱乐互动玩法。全系 30 秒超时自愈机制，【重置接龙】支持 |
| `engines/superadmin.py`| 超级管理员指令。支持【测试webdav】、【备份xb】等 |

---

## ⚡ 核心数据接口 (Web API) 速查

- **GET `/astrbot_plugin_xbbot/stats`**：全系统游戏资产宏观统计大屏
- **GET `/astrbot_plugin_xbbot/config/get`** & **POST `/config/save`**：配置中心读取与实时保存
- **GET `/astrbot_plugin_xbbot/backups/list`**：备份目录结构及文件树
- **POST `/astrbot_plugin_xbbot/backup/webdav/test`**：测试 WebDAV 连通性与账号认证
- **POST `/astrbot_plugin_xbbot/backup/webdav/upload`**：立即执行本地冷备并上传至 WebDAV
- **POST `/astrbot_plugin_xbbot/backups/doctor`**：SQLite 碎片整理 (VACUUM) 与健康体检
- **GET `/astrbot_plugin_xbbot/version/check`**：云端 Release 与 main 分支更新探测

---

## 🛡️ 应急指令与排障清单

1. **若用户反馈群聊消息完全不回复**：
   - 查看 AstrBot 控制台是否开启了【总开关配置】（发送【开启总开关】）；
   - 查看是否开启了【维护模式】（超管发送【关闭维护】）；
   - 查看群是否被单独关闭（发送【开启本群】）。
2. **若用户反馈接龙卡死**：
   - 在群内发送【重置接龙】或【结束接龙】，秒级重置全部对局状态。
3. **若 WebDAV 云端备份报 401 或超时**：
   - 在 WebUI 控制台「备份管理」Tab 点击【☁️ 测试 WebDAV】查看清晰报错；
   - 检查 WebDAV 用户名和应用密码是否为生成的专用 Token（如坚果云需生成应用密码）。\n