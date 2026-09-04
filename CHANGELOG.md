# 更新日志

## v0.68.1
- 🛡️ **WebAPI 全接口通用安全解析防护**：全面接入 `helpers.get_req_query` 与 `helpers.get_req_json`，彻底杜绝 aiohttp 请求体为空或参数缺失导致的 `NoneType` / `AttributeError` 异常（全面覆盖 backup/config/game/groups/images/legacy/users 全部 7 大路由）；
- 💾 **数据持久化存储架构统一**：全面统合 `store.get_persistent_data_dir()` 持久化路径，修复 `main.py`、`engines/slave.py`、`backup.py` 与 `images.py` 等模块多头打开 SQLite 数据库与插件升级可能丢失数据的风险，实现数据目录自动迁移与双向自愈；
- 🚦 **指令路由器系统开关隔离修复**：修复 `core/router.py` 中子系统开关拦截范围扩大化的严重缺陷（过去关闭某个系统会导致非该系统指令与普通聊天被误拦截），并修复 `'adventure': '冒险'` 映射，确保仅当用户输入命中对应关闭系统的指令集时才进行友好提示拦截；
- ⚡ **SQLite LRU 脏数据防丢失加固**：加固 `store.py` 账户缓存 LRU 溢出淘汰逻辑，在丢弃前对 `dirty` 标志位进行检测并主动触发 `flush()` 同步 WAL，杜绝高并发内存被逐出时的状态回退隐患；
- 🏷️ **版本号 9 处强一致性同步对齐**：所有核心代码、接口与管理控制台全量同步对齐至版本 0.68.1。
