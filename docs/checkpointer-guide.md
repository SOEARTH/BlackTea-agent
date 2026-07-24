# PG Checkpointer 接入指南

> 2026-07-24 · 怎么把 LangGraph 的短期记忆持久化到 PostgreSQL

## 1. 为什么需要 Checkpointer

LangGraph 的 `StateGraph` 默认编译为纯内存图——每调用一次，状态从零开始，跑完即丢。这在单测里没问题，但真实场景有两个硬需求：

1. **interrupt 恢复**：`clarify` agent 用 `interrupt()` 暂停图等用户补充信息，用户回复后需要恢复到暂停点继续执行，这就要求 graph 记住暂停时的完整 state。如果进程重启了（比如 FastAPI 服务重启），没有持久化就丢了。
2. **线程记忆**：用户可以用同一个 `thread_id` 跨请求继续对话，graph 需要恢复上次跑完的 state。

Checkpointer 就是 LangGraph 的解决方案：每个节点执行后把 state 快照写入 checkpoint 存储，恢复时从最近的 checkpoint 读取。

## 2. 选型：AsyncPostgresSaver

LangGraph 提供多个 checkpointer 实现：

| 实现 | 场景 | 我们的选择 |
|---|---|---|
| `MemorySaver` | 单测、临时调试 | 默认 `build_graph()` 不传 checkpointer 时的行为 |
| `PostgresSaver` | 同步、Flask 等 | — |
| `AsyncPostgresSaver` | 异步、FastAPI | **本项目用这个** |

选 `AsyncPostgresSaver` 的原因：FastAPI 全链路异步，agent 节点都是 `async def`，如果 checkpointer 是同步的会阻塞事件循环。`AsyncPostgresSaver` 基于 psycopg3 的 `AsyncConnection`，与 FastAPI 的 async 天然契合。

## 3. 架构分层

```
FastAPI lifespan
  │
  ├─ get_checkpointer()          # 连接 PG，yield AsyncPostgresSaver
  │    └─ AsyncPostgresSaver.from_conn_string(db_url)
  │         └─ psycopg3 AsyncConnection (autocommit=True, prepare_threshold=0)
  │
  ├─ init_checkpointer(saver)    # 调 setup() 建表 + 迁移
  │    └─ saver.setup()
  │         └─ 在 public schema 建 4 张表：
  │            checkpoints, checkpoint_writes, checkpoint_blobs, checkpoint_migrations
  │
  └─ build_graph(checkpointer)   # 编译带持久化的图
       └─ graph.compile(checkpointer=saver)
            └─ 挂到 app.state.graph
```

关键文件：

- [backend/app/db/checkpointer.py](../backend/app/db/checkpointer.py) — 两个工厂函数
- [backend/app/agents/graph.py](../backend/app/agents/graph.py) — `build_graph(checkpointer=None)` 接受可选参数
- [backend/app/main.py](../backend/app/main.py) — FastAPI lifespan 启动时初始化

## 4. 连接参数说明

`AsyncPostgresSaver.from_conn_string` 内部调用 `psycopg.AsyncConnection.connect` 时固定了两个参数：

```python
async with await AsyncConnection.connect(
    conn_string,
    autocommit=True,       # 自动提交，每条 SQL 立即生效
    prepare_threshold=0,   # 禁用 prepared statement 缓存
    row_factory=dict_row,   # 返回 dict 行
) as conn:
```

- **`autocommit=True`**：LangGraph 的 checkpoint 写入是单条 SQL 级别的，不需要事务包裹，开启自动提交避免悬挂事务。
- **`prepare_threshold=0`**：psycopg3 默认会在第 6 次执行同一 SQL 时缓存 prepared statement，但在高频并发写入 checkpoint 时容易触发 `prepared statement "..." does not exist` 错误（连接池下语句被清理）。设为 0 关闭这个优化，换稳定性。

## 5. PG 中的表结构

调用 `await saver.setup()` 后会在 `public` schema 自动创建 4 张表：

```
public.checkpoint_migrations   — 迁移版本记录
public.checkpoints             — 每个 checkpoint 的元数据（thread_id, checkpoint_id, parent_id...）
public.checkpoint_blobs        — state 序列化后的二进制 blob
public.checkpoint_writes       — 每个 node 的写入记录（用于中断恢复）
```

这些表由 LangGraph 管理，与业务表 `app.*` 互不干扰（业务表在 `app` schema，checkpoint 表在 `public` schema）。

## 6. 启动流程

### 前置：Docker 起 PG

```bash
docker-compose up -d postgres
```

### 首次启动：自动建表

FastAPI 的 `lifespan` 在应用启动时执行：

1. 连接 PG → 创建 `AsyncPostgresSaver`
2. 调 `setup()` → 检查 `checkpoint_migrations` 表，不存在则建，然后按版本号跑迁移
3. 编译 `build_graph(checkpointer)` → `app.state.graph`

首次启动会多花 1-2 秒建表，后续启动检测到表存在则跳过。

### 验证

```bash
# 启动服务
$env:PYTHONPATH='backend'; & "F:\anaconda\envs\BlackTea\python.exe" -m uvicorn app.main:app --reload

# 健康检查
curl http://localhost:8000/health
# {"status":"ok","graph_ready":true}
```

`graph_ready: true` 说明 checkpointer 已连接、graph 已编译。

## 7. 如何使用 thread_id

checkpointer 的核心概念是 `thread_id`——一个图执行的唯一标识，用于隔离不同用户/不同会话的 state。

### 调用图时传入 thread_id

```python
config = {"configurable": {"thread_id": "user-123-thread-456"}}

# 首次调用
result = await graph.ainvoke(initial_state, config)

# interrupt 后恢复（用户补充了信息）
from langgraph.types import Command
result = await graph.ainvoke(Command(resume="用户回答内容"), config)
```

同一个 `thread_id` 多次调用时，graph 会自动从 checkpoint 恢复上次 state，而不是从零开始。

### interrupt 恢复流程

```
首次调用 thread_id=T
  └─ clarify 节点执行
       └─ LLM 发现缺预算 → interrupt("请输入预算")
            └─ state 写入 checkpoint（thread_id=T, checkpoint_id=C1）
            └─ 图暂停，返回 interrupt 信息给前端

用户回复后，同一 thread_id=T 调用
  └─ graph 从 C1 恢复 state
       └─ Command(resume="200元") 注入 resume 值
            └─ clarify 继续执行，写入 ShoppingRequirement
            └─ 流向 search → [price || reputation] → scoring → reflect
```

## 8. 测试策略

`build_graph(checkpointer=None)` 不传 checkpointer 时编译为纯内存图，14 个测试全部通过——不需要 PG 连接即可跑单测。

如果写 checkpointer 集成测试，用 pytest 的 `skip` 机制：

```python
import pytest

@pytest.mark.asyncio
async def test_graph_with_pg_checkpointer():
    try:
        import asyncpg  # 或尝试连接
        conn = await asyncpg.connect("postgresql://blacktea:blacktea@localhost:5432/blacktea")
        await conn.close()
    except Exception:
        pytest.skip("PG not available")
    # ...checkpointer 集成测试...
```

## 9. 配置

`.env` 中通过 `DATABASE_URL` 配置 PG 连接串：

```env
DATABASE_URL=postgresql://blacktea:blacktea@localhost:5432/blacktea
```

如果 `DATABASE_URL` 为空，`main.py` 的 lifespan 会退化到无 checkpointer 模式（`build_graph()` 不传参），服务仍可启动但无持久化能力。

## 10. 面试可讲的点

- **为什么选 Async 而不是 Sync**：FastAPI 全链路异步，同步 checkpointer 会阻塞事件循环。
- **prepare_threshold=0 的原因**：psycopg3 的 prepared statement 缓存在连接池 / 高频写入场景下容易与 checkpoint 操作冲突，关闭换稳定性。
- **checkpoint 表与业务表的隔离**：public schema 放 LangGraph 自管表，app schema 放业务表，两套表互不干扰。
- **interrupt 恢复机制**：checkpoint 保存暂停点的完整 state，`Command(resume=...)` 注入用户回复后从 checkpoint 恢复继续。
- **build_graph() 的可测试性设计**：checkpointer 作为可选参数注入，单测传 None 走内存、集成测试和线上注入 PG saver，同一套代码两种模式。