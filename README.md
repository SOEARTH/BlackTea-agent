# BlackTea · 智购多智能体决策引擎

基于真实电商数据的多智能体购物**决策**引擎：把"我想买个好耳机""3000 元帮我配一套露营装备"这类模糊需求，变成带打分依据、方案对比、可解释的购买决策报告。

> 求职作品集项目 · 完整设计文档见 PLAN.md（本地，未提交）

## 亮点

- 多智能体协作：7 节点 LangGraph 图编排——需求澄清 / 选品检索 / 比价 / 口碑分析 / 打分排序 / 反思校验 / Supervisor 路由；关键节点 human-in-the-loop（`interrupt` 反问）
- fork-join 并行：search 后扇出 price 和 reputation 两条并行分支，各自只写独立 state key，汇聚到 scoring——较串行减少总延迟
- 容错体系：clarify interrupt 自环（信息不足自动暂停等用户补充）+ search 异常降级（MCP 失败不崩溃）+ price 单品跳过 + reflect 死循环保护（MAX_ITERATIONS=3）
- 决策引擎：单品动态加权打分矩阵（价格/口碑/销量/券力度/品牌 5 维，按需求调整权重）+ 组合场景预算约束优化（多槽位 0/1 背包 DP），输出 2-3 套方案对比
- 反思升级：LLM 校验 must_have 硬约束（对比商品标题/卖点与约束描述），不满足则打回重检
- 前端可视化：Canvas 雷达图 + 打分明细表 + 组合方案对比卡片，每次决策可解释
- 方面级口碑 RAG：评论/测评按"续航/做工/售后"等维度聚合为结构化口碑分参与打分（M3）
- 记忆驱动个性化：双层记忆（PG 画像 + Milvus 情景记忆），召回动态调整决策权重（M3）
- MCP 工具化：自建 FastMCP server 封装大淘客 API，agent 经 langchain-mcp-adapters 按需挂载，可插拔
- 评估闭环：LangSmith trace + 自建评估集 + LLM-as-judge 打分回归（M4）

## 技术栈

LangChain · LangGraph · LangSmith · FastAPI · Vue3 · PostgreSQL · Milvus · Redis · FastMCP / langchain-mcp-adapters · Pydantic v2

## 智能体架构

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
    __start__([START])
    clarify["需求澄清 Agent<br/>LLM 提取 + interrupt 反问"]
    search["选品检索 Agent<br/>MCP 搜索 + 预算过滤<br/>异常降级→空候选"]
    price["比价 Agent<br/>历史券后价趋势 + 分位<br/>单商品失败跳过"]
    reputation["口碑分析 Agent<br/>M3 RAG / M1 店铺评分代理"]
    scoring["打分与组合规划<br/>动态权重打分矩阵<br/>+ 背包DP组合优化"]
    reflect["反思校验 Agent<br/>预算/好价/LLM硬约束/死循环<br/>MAX_ITERATIONS=3"]
    supervisor["Supervisor<br/>路由控制"]
    __end__([END])

    __start__ --> clarify;
    clarify -->|"信息不足 → interrupt"| clarify;
    clarify -->|"用户回复 → resume"| clarify;
    clarify -->|"信息充足"| search;
    search --> price;
    search --> reputation;
    price --> scoring;
    reputation --> scoring;
    scoring --> reflect;
    reflect -->|"通过"| supervisor;
    reflect -->|"超预算/好价低/硬约束不满足<br/>打回重检"| search;
    supervisor --> __end__;

    classDef agent fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20;
    classDef parallel fill:#fce4ec,stroke:#c62828,stroke-width:2px,color:#b71c1c;
    classDef control fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#bf360c;
    classDef startend fill:#e3f2fd,stroke:#1565c0,stroke-width:2px;

    class clarify,search,scoring,reflect agent;
    class price,reputation parallel;
    class supervisor control;
    class __start__,__end__ startend;
```

## 数据源

- 淘宝：大淘客开放平台（openapi.dataoke.com），appKey 查询类接口 + 转链（默认 PID，项目不变现）
- 自建 FastMCP server 封装搜索/列表/历史券后价/转链/解析五个核心接口
- 项目仅做推荐决策研究，不涉及 CPS 推广变现

## 当前进度

| 里程碑 | 状态 | 完成项 |
|---|---|---|
| **M1 骨架** | ✅ 完成 | 大淘客 FastMCP server（5 工具）+ 归一化商品模型 + 数据模型 + 7 节点 LangGraph 图（fork-join 并行）+ interrupt 自环容错 + AsyncPostgresSaver checkpointer + FastAPI SSE 端点 + Vue3 对话流前端 |
| **M2 决策** | ✅ 完成 | 打分矩阵动态权重调优 + excluded 过滤 + nice_to_have 软偏好匹配 + 组合优化（多槽位 0/1 背包 DP，top-3 方案）+ 反思升级（LLM 校验 must_have 硬约束）+ 决策报告前端卡片增强（Canvas 雷达图 + 打分明细表 + 组合方案对比） |
| **M3 深度** | ✅ 完成 | 方面级口碑 RAG（Milvus review_corpus + aspect 聚合，DSR 兜底）+ 双层记忆（PG profile_facts 画像 + Milvus episodic_memory 情景记忆，scoring 前召回调权）+ Skill 渐进装载（品类 SKILL.md 注入 clarify）+ 12 篇口碑种子语料 |
| M4 质量 | 待做 | LangSmith 评估回归 + LLM-as-judge + 架构图完善 |

## 快速启动

### 前置

- Python 3.12 
- Node.js 22+（前端 dev server）
- Docker（PG / Redis / Milvus）

### 1. 环境变量

```bash
cp .env.example .env
# 填入大淘客 appKey/appSecret、LLM API key、数据库连接等
```

### 2. 后端

```bash
# 安装依赖
pip install -r requirements.txt

# 启动基础设施（PG / Redis / Milvus）
docker-compose up -d

# 跑测试（40 个单元/集成测试）
set PYTHONPATH=backend && python -m pytest backend/tests/ -v

# 启动 FastAPI（自动初始化 PG checkpointer + 编译 graph）
set PYTHONPATH=backend && python backend/run.py
```

后端启动后访问 `http://localhost:8000/health`，返回 `{"status":"ok","graph_ready":true}` 即就绪。

> Windows 注意：必须用 `backend/run.py` 启动，而不是直接 `python -m uvicorn`。`run.py` 在导入 uvicorn 之前把 asyncio 事件循环策略切换为 `WindowsSelectorEventLoopPolicy`，否则 psycopg3 异步驱动无法在默认 ProactorEventLoop 上连接 Postgres（报 "Psycopg cannot use the 'ProactorEventLoop'..."）。Docker PG 映射到宿主机 **5433** 端口，避开本地原生 Postgres 对 5432 的占用。

### 3. 前端

```bash
cd frontend
npm install          # 安装 Vue3 + Pinia + Element Plus + Vite
npm run dev          # 启动 Vite dev server
```

前端启动后访问 `http://localhost:5173`，Vite 自动代理 `/api` 到后端 `localhost:8000`。

### 4. 使用流程

1. 在对话框输入购物需求，如"我想买个降噪耳机，预算 500 以内"
2. 如果信息不足（缺品类或预算），系统弹窗反问，补充后点"提交并继续"
3. 右侧 Agent 轨迹面板实时显示每个 agent 的执行进度
4. 反思通过后，右侧决策报告卡片显示推荐商品排名 + 雷达图 + 打分明细表
5. 组合场景（如"3000 元帮我配露营装备"）会展示 2-3 套预算内组合方案对比

## 项目结构

```
backend/
  app/
    config.py              # pydantic-settings 读 .env
    main.py                # FastAPI 入口（lifespan 初始化 checkpointer + graph）
    models/                # Pydantic 数据模型
      product.py           #   NormalizedProduct 归一化商品
      requirement.py       #   ShoppingRequirement 需求结构
      decision.py          #   AspectScore / ScoredProduct / DecisionReport
    agents/                # LangGraph 多智能体
      state.py             #   GraphState TypedDict（含 user_id）
      clarify.py           #   需求澄清（interrupt 反问 + 自环容错 + Skill 注入）
      search.py            #   选品检索（MCP 搜索 + 异常降级）
      price.py             #   比价（历史券后价趋势，并行，单品跳过）
      reputation.py        #   口碑分析（M3 RAG / M1 店铺评分代理，并行）
      memory_integration.py #  记忆召回调权（画像 + 情景记忆 → 打分权重）
      scoring.py           #   动态权重打分矩阵 + excluded/偏好过滤 + combo 调用（async）
      optimizer.py         #   组合优化（多槽位 0/1 背包 DP，top-3 方案）
      reflect.py           #   反思校验（async + LLM 硬约束 + 预算/好价/死循环）
      supervisor.py        #   路由控制
      graph.py             #   build_graph(checkpointer=None) 图构建
      utils.py             #   LLM 工具函数
    adapters/dtk.py        # 大淘客原始响应 -> NormalizedProduct
    cache/redis.py         # Redis 缓存封装
    db/schema.sql          # PostgreSQL 业务表 DDL（app schema）
    db/checkpointer.py     # AsyncPostgresSaver 生命周期 + AsyncConnectionPool
    db/milvus/             #   向量层
      client.py            #     MilvusClient 单例 + Ollama qwen3-embedding（4096 维）
      collections.py       #     3 个 collection schema + IVF_FLAT/COSINE
      rag.py               #     方面级口碑检索 + 聚合 + get_reputation_for_product
      memory.py            #     情景记忆写入/召回 + PG profile_facts + 抽取流水线
      seed_reviews.py      #     12 篇口碑种子语料入库
    skills/                #   Skill 渐进装载
      loader.py            #     detect_category / load_skill_prompt / enrich_requirement_prompt
      categories/          #     audio/outdoor/digital/default SKILL.md
    routes/chat.py         # SSE 流式对话端点（/api/chat + /api/chat/resume）
  mcp_dtk/                 # 自建 FastMCP server（大淘客封装）
    client.py              #   签名 + API 调用 + fixture 兜底
    tools.py               #   5 个 MCP 工具函数
    server.py              #   FastMCP 注册
    __main__.py            #   python -m mcp_dtk 入口
  tests/                   # 40 个单元/集成测试
    test_adapter_dtk.py    #   大淘客适配器（4）
    test_graph.py          #   LangGraph 端到端（5）
    test_mcp_tools.py      #   MCP 工具（8）
    test_optimizer.py      #   组合优化 + 动态权重（12）
    test_m3.py             #   Skill + 记忆调权 + 口碑 RAG（11）
frontend/                  # Vue3 前端
  src/
    main.js                # Vue 应用入口（Pinia + Element Plus）
    App.vue                # 主布局（左对话 + 右轨迹/报告）
    stores/chat.js         # 聊天状态管理（SSE 事件分发）
    api/sse.js             # fetch-based SSE 客户端（手动解析 SSE 帧）
    components/
      ChatWindow.vue       # 对话消息流 + 输入框
      AgentTimeline.vue    # agent 执行轨迹时间线
      InterruptDialog.vue  # interrupt 反问弹窗
      DecisionReport.vue   # 决策报告（雷达图 + 打分表 + 组合对比）
  package.json
  vite.config.js           # Vite dev server + /api 代理到后端
docker-compose.yml         # PG / Redis / Milvus / etcd / minio
requirements.txt
.env.example               # 环境变量占位符
```
