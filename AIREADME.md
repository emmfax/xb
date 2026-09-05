# 小白机器人 (astrbot_plugin_xbbot) — AI 开发者架构与交接手册 (AIREADME)

> **版本**：`v0.68.21`  
> **适用对象**：接手本项目的 AI 编程助手（Claude, GPT, Gemini 等）与核心维护者  
> **定位**：AstrBot 平台大型统一群互动插件（奴隶/签到/银行/娱乐/私聊/精灵/坐骑/超管/帮派/冒险 等 28 大子系统 + 现代 WebUI 管理控制台）

---

## 1. 核心架构与模块分层设计

整个插件采用三层解耦与单向依赖设计（`pages/` WebUI → `main.py` 调度入口 → `core/` 基础层 / `engines/` 业务层 → `store.py` 数据层）：

```
astrbot_plugin_xbbot/
├── metadata.yaml             # AstrBot 插件元数据（版本号 9 处强校验点之一）
├── _conf_schema.json         # 28 个系统、298 项配置定义模式，WebUI 与 AstrBot 原生配置渲染驱动
├── main.py                   # 插件 Star 主入口，事件监听分发、Web API 注册、后台定时备份守护线程
├── store.py                  # 现代 SQLite (WAL 模式) 存储引擎，原子事务、内存 LRU/全局缓存、自动备份与保留修剪
├── verify_plugin.py          # 语法解析、版本 9 处一致性、配置模式合法性全量自动化校验脚本
├── core/                     # 核心基础设施层
│   ├── config.py             # 配置规范化、双向转换、默认值兜底
│   ├── platform.py           # 跨平台适配、消息链装配、原生成分解析、@提及与名片提取
│   ├── router.py             # 统一指令路由调度机、主菜单生成、子系统分发
│   ├── webdav.py             # 纯标准库零依赖 WebDAV 客户端（支持坚果云/Alist/NAS等）
│   ├── logger.py             # 统一日志收口输出
│   ├── en_map.py             # 中英文字段双向映射表
│   └── api/                  # WebUI 后端 API 端点（9 大 Tab 薄路由）
│       ├── backup.py         # 备份列表、恢复、导出、清理、数据库整理体检、WebDAV 测试与云备份
│       ├── updater.py        # GitHub Releases / main 分支双通道版本检测与在线更新
│       ├── users.py          # 用户资产、封禁、编辑、清空、一键空投
│       ├── groups.py         # 群聊开关管理与状态切换
│       ├── images.py         # 根目录与抽卡图鉴资源文件管理器
│       └── ...
├── engines/                  # 28 大群互动游戏与业务系统
│   ├── slave.py              # 奴隶系统（买卖、打工、折磨、讨好、赎身、身价校准）
│   ├── sign.py               # 签到系统（首签、连签阶梯奖励、新手礼包、点赞）
│   ├── bank.py               # 银行系统（存取款、利息结算、转账、财富榜）
│   ├── ent.py                # 娱乐系统（成语接龙、急转弯、猜字谜、猜数字、24点等，全系30秒超时）
│   ├── spirit.py             # 精灵系统（精灵捕捉、图鉴、培养、战力计算）
│   ├── ride.py               # 坐骑系统（抓捕、合成、属性成长、迎新进群播报）
│   ├── superadmin.py         # 超级管理员系统（备份、WebDAV测试、维护模式、清空、封禁）
│   ├── guild.py              # 帮派系统
│   ├── adventure.py          # 冒险系统
│   └── chat.py               # 词库私聊与唤醒词过滤
└── pages/admin/              # 现代化 WebUI 管理控制台
    ├── index.html            # 单页面控制台骨架（13 大 Tab 视图、深浅色模式）
    ├── app.js                # 前端控制台主逻辑（Bridge 封装、API 通信、图表、搜索联动）
    └── (tabs/ 已于 v0.68.24 整包移除：12 文件全库零引用，Tab 全由 app.js 内联 TAB_LOADERS 承载)
```

---

## 2. 必须严守的“五大黄金法则”（严防退化 Bug）

在后续迭代或修复时，**切勿违反以下原则**，这是多次线上高并发调优与故障复盘得出的血泪教训：

### 规则一：主事件循环（Event Loop）绝对零阻塞
- **绝不在 `main.py` 的 `_dispatch` 或消息分发路径中调用同步 I/O**！
- 定时备份必须在 `__init__` 中启动的独立守护线程（`xb-auto-backup`）中定期执行；
- 群名片/昵称提取时，先在纯内存字典（`slave.NOTE_NAMES`）中同步更新（0ms），涉及 `ST.register_name` 或 `slave.save(gid)` 的数据库落盘必须切入后台线程或线程池执行；
- 所有网络调用（如 `core/webdav.py`、`core/api/updater.py`）必须设置适度超时（探测 <= 8s，上传 <= 25s），且在 Web API 接口中必须使用 `await asyncio.to_thread(...)` 执行，严防事件循环延迟（如 `Event loop lag detected: 56.067s`）。

### 规则二：禁止在 `_ensure_db()` 中跨线程强行 rollback
- `_ensure_db()` 是全局读写连接的健康探测函数，**绝不可在此处根据 `in_transaction` 强行执行 `rollback()`**！
- 跨线程并发执行时，线程 B 若强行 rollback 线程 A 正在进行的写入，会导致 SQLite 抛出 `cannot rollback - no transaction is active` 并使数据库连接陷入假死。
- 所有事务的回滚只能在具体的业务操作捕获异常后的 `except` 块中通过 `_safe_rollback()` 执行。

### 规则三：底层存储写入全面安全降级，禁止裸调 `raise`
- `store.py` 中的核心操作方法（如 `coins_add`、`acct_save`、`save_group`、`txn_coins_acct`、`flush_all` 等），在捕获异常后必须安全执行 `_safe_rollback()` 并返回安全降级值（如原数值或 False），**禁止向外层重新 `raise` 原始数据库异常**；
- 杜绝群聊前台向普通用户暴露“【系统】处理指令时出现异常（原因: ...）”此类崩溃信息。

### 规则四：娱乐游戏与会话全系 30 秒超时自愈
- 接龙、急转弯、猜字谜等全系互动游戏超时统一设为 30 秒；
- 接龙支持 `【重置接龙】` 与 `【结束接龙】` 指令，任何群员均可发送一键释放对局；
- 30 秒无人作答后，下一条互动指令或 `开始接龙` 自动静默清理并秒级重开，杜绝死锁。

### 规则五：9 处版本号强一致性对齐
- 每次版本迭代必须同步更新以下 9 个位置的版本号：
  1. `metadata.yaml`: `version: "x.y.z"`
  2. `main.py`: `PLUGIN_VERSION = "x.y.z"`
  3. `core/api/updater.py`: `return "x.y.z"`
  4. `core/api/users.py`: `PLUGIN_VERSION = "x.y.z"`
  5. `engines/superadmin.py`: `ver = "x.y.z"`
  6. `pages/admin/index.html`: `<span class="ver">vx.y.z</span>`
  7. `pages/admin/app.js`: `version: res.version || "x.y.z"`
  8. `CHANGELOG.md`: `## vx.y.z`
  9. `README.md`: `vX.Y.Z`

---

## 3. 存储与并发控制模型 (`store.py`)

- **模式**：SQLite WAL 模式（`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`），千群并发读完全并行，写串行化；
- **锁机制**：使用全局互斥可重入锁 `_LOCK = threading.RLock()` 保护所有写事务；
- **内存预热与加速**：
  - `kv` 表使用 `_KV_CACHE` 内存字典预热缓存；
  - 群组与用户配置通过 `_GROUP_CACHE` 维护，采用 `_dirty` 脏标记和 `_dirty_qqs` 增量提交；
- **自动备份与清理策略**：
  - 备份目录：`data/backups/YYYY-MM-DD/xbbot_YYYYMMDD_HHMMSS.db`；
  - 自动清理：`clean_old_backups(max_keep=None)`，默认保留最新 30 份（可在配置项 `保留备份数量` 调节），超出自动清除最旧文件并回收空目录；
  - 增量冷备：使用 SQLite 原生 `_DB.backup(bck)` API，支持 `PASSIVE` 检查点。

---

## 4. WebDAV 自动云备份 (`core/webdav.py`)

- **实现特性**：零外部依赖（纯标准库 `urllib.request` + `ssl` + `base64`），兼容任意标准 WebDAV 服务端（坚果云、Alist、群晖、Nextcloud 等）；
- **接口与按钮**：
  - Web 控制台「备份管理」Tab 包含【☁️ 测试 WebDAV】与【☁️ 立即上传云端】按钮；
  - 对应后端路由：`/backup/webdav/test` 和 `/backup/webdav/upload`；
  - 聊天指令：超管在群聊/私聊中发送【测试webdav】或【webdav测试】。

---

## 5. 校验与打包发布标准工作流

在提交任何更改前，请在终端执行以下标准流程：

```powershell
# 1. 语法与强一致性自检（确保 ALL OK）
python -X utf8 verify_plugin.py

# 2. 前端 DOM 与 API 注册完整性检查
python -X utf8 scratch/check_frontend.py

# 3. 构建发布压缩包
python -X utf8 scratch/make_zip.py

# 4. Git 提交并打 Release 标签
git add -A
git commit -m "feat/fix: commit description (vx.y.z)"
git tag vx.y.z
git push origin main
git push origin vx.y.z
```\n