# M2 实现文档：打分矩阵调优 + 组合优化 + 反思升级 + 前端增强

## 1. 打分矩阵调优（scoring.py）

### 1.1 动态权重

M1 使用固定权重（price=0.25, reputation=0.25, sales=0.20, coupon=0.15, brand=0.15）。M2 改为根据 `ShoppingRequirement` 动态调整：

| 条件 | 调整 | 原因 |
|---|---|---|
| `budget_max < 200` | price +0.10 | 低预算用户更敏感于价格 |
| `must_have` 非空 | reputation +0.05 | 硬约束满足依赖品质/口碑 |
| `combo=True` | coupon -0.05 | 组合场景看整体而非单券 |
| `nice_to_have` 非空 | brand +0.05 | 软偏好多与品牌相关 |

调整后归一化，确保权重之和 = 1.0。

**代码位置**：`_compute_dynamic_weights()` in [scoring.py](../backend/app/agents/scoring.py)

### 1.2 软偏好匹配

`nice_to_have` 列表中的关键词与商品标题+品牌+店铺名做子串匹配，命中则 brand 维度 +1.5 分，evidence 记录命中项。

### 1.3 排除项过滤

`excluded` 列表中的关键词在打分前过滤，命中的商品直接从候选列表移除，AIMessage 记录被排除数量。

### 1.4 打分明细增强

- 价格维度：加入预算充裕度因子（`price / budget_max` 比值），远低于预算 +1.0 分，逼近上限 -1.0 分
- 口碑维度：无 RAG 口碑时用店铺 DSR 三项均值兜底（5 分制 → 10 分制）
- 销量维度：新增 5000+ 件 = 9.0 分档位
- evidence 字段始终携带依据文本，前端直接渲染

## 2. 组合优化（optimizer.py）

### 2.1 算法概述

当 `ShoppingRequirement.combo == True` 且 `slots` 非空时，触发背包 DP 优化：

1. **槽位分组**：商品标题与 slot 关键词做子串匹配，每槽位取 top-5 候选
2. **0/1 背包 DP**：状态 = (槽位索引, 累计花费)，价值 = 总得分
3. **多方案生成**：求最优解后，逐个禁用最优解中的选择重新 DP 求次优解，去重取前 3 套

### 2.2 关键参数

| 参数 | 值 | 说明 |
|---|---|---|
| `CANDIDATES_PER_SLOT` | 5 | 每槽位最多参与 DP 的候选数 |
| `MAX_COMBO_SCHEMES` | 3 | 最多产出几套方案 |
| `BUDGET_GRANULARITY` | 1 元 | 预算离散化粒度 |

### 2.3 核心流程

```
knapsack_combo(scored, requirement)
  ├── _partition_by_slots(scored, slots)     # 标题匹配分组
  │     └── _match_slot(title, slot)        # 子串匹配
  └── _solve_topk_schemes(partition, k=3)
        ├── _dp_solve(forbidden=set())      # 标准背包装填
        └── 循环禁用最优解的每个选择
              └── _dp_solve(forbidden={(i,gid)})
```

### 2.4 DP 状态转移

```
dp[capacity] = (max_score, choice_path)

for slot_idx in range(n):
    for cap, (score, path) in dp.items():
        for candidate in partition[slot]:
            if cap + price_q <= capacity:
                new_cap = cap + price_q
                new_score = score + candidate.total
                update new_dp[new_cap]
    dp = new_dp
```

最终取 `max(dp, key=score)` 回溯选择路径，映射回 ScoredProduct。

### 2.5 容错

- 某槽位无候选 → 返回空列表（无法组完整方案）
- 无预算约束 → 容量设为极大值，退化为每槽位取 top-1
- 禁用后无可行解 → 跳过该次优解，不求

**代码位置**：[optimizer.py](../backend/app/agents/optimizer.py)

## 3. 反思升级（reflect.py）

### 3.1 LLM 硬约束校验

M1 的 `must_have` 检查是占位（未实现），M2 改为 async 节点，调用 LLM 校验：

1. 取 top-5 商品，构造 prompt（商品标题 + selling_points + special_texts vs 硬约束列表）
2. LLM 返回 JSON `{"results": [{"index": n, "satisfied": bool, "reason": "..."}]}`
3. 有不满足项 → 记录违规描述，触发打回

LLM 调用失败时降级为跳过（不阻塞流程），记 warning。

### 3.2 组合方案生成

反思通过后，若 `combo=True` 且 state 中已有 combos（scoring 生成），直接写入 DecisionReport；否则现场调用 `knapsack_combo` 补算。

### 3.3 摘要增强

`_generate_summary()` 新增：
- 各维度打分明细（`明分：价格9.0、口碑8.5...`）
- 组合方案数量概览

### 3.4 async 变更

`reflect_node` 从同步改为 `async def`，因为 LLM 调用 (`llm.invoke`) 在异步上下文中执行。LangGraph 原生支持 async 节点。

**代码位置**：[reflect.py](../backend/app/agents/reflect.py)

## 4. 决策报告前端增强（DecisionReport.vue）

### 4.1 雷达图

每个推荐商品卡片内嵌一个 canvas 雷达图，5 个维度（价格/口碑/销量/券/品牌）：

- 5 圈背景网格 + 5 条轴线
- 得分多边形（蓝色半透明填充 + 描边 + 顶点圆点）
- 维度标签渲染在顶点外侧

绘制时机：`watch(chat.report)` 触发 `nextTick(drawAllRadars)`，遍历所有 canvas ref 逐个绘制。

### 4.2 打分明细表

每个商品卡片下方渲染 `<table>`，4 列：维度 / 得分 / 权重 / 依据。维度名通过 `aspectLabels` 映射为中文。

### 4.3 组合方案对比

`chat.report.combos` 非空时，顶部渲染方案对比区：

- 每套方案一个蓝色边框卡片
- 方案编号 + 总价
- 逐件商品展示：标题 + 价格

### 4.4 技术选择

- 雷达图用原生 Canvas 2D API 手绘，不引入 echarts（轻量、无额外依赖）
- watch + nextTick 确保 DOM 渲染后再画 canvas
- `setCanvas(el, index)` 通过 ref 回调收集 canvas 元素

**代码位置**：[DecisionReport.vue](../frontend/src/components/DecisionReport.vue)

## 5. GraphState 变更

新增字段：

```python
combos: list[list]  # list[list[ScoredProduct]]，每套方案一组商品
```

scoring_node 写入 combos，reflect_node 读取 combos 写入 DecisionReport。

## 6. 测试覆盖

### 新增 test_optimizer.py（12 个测试）

| 测试 | 验证点 |
|---|---|
| `test_match_slot_basic` | 槽位关键词匹配逻辑 |
| `test_partition_by_slots` | 商品分组 + 排序 + top-K |
| `test_knapsack_basic_combo` | 三槽位各一候选，预算充足全选中 |
| `test_knapsack_budget_constraint` | 预算不够选最贵组合，退化为次优 |
| `test_knapsack_missing_slot` | 槽位缺候选返回空 |
| `test_knapsack_non_combo_returns_empty` | 非组合场景返回空 |
| `test_knapsack_multiple_schemes` | 多候选产出多套方案 |
| `test_combo_summary` | 摘要文本包含方案编号和价格 |
| `test_dynamic_weights_low_budget` | 低预算 price 权重上调 |
| `test_dynamic_weights_high_budget` | 高预算 price 不上调 |
| `test_dynamic_weights_must_have` | 硬约束 reputation 上调 |
| `test_dynamic_weights_combo` | 组合 coupon 下调 |
| `test_dynamic_weights_normalized` | 归一化后总和=1.0 |

### 更新 test_graph.py（5 个测试）

| 测试 | 变更 |
|---|---|
| `test_clarify_triggers_interrupt` | 无变更 |
| `test_full_pipeline_mock` | reflect_node 改为 await |
| `test_reflect_rejects_over_budget` | reflect_node 改为 await |
| `test_reflect_llm_constraint_check` | 新增：mock LLM 返回不满足约束 |
| `test_combo_pipeline` | 新增：组合场景端到端验证 |
| `test_graph_compiles` | 无变更 |

### 全量结果

```
29 passed in 1.40s
```

## 7. 文件变更清单

| 文件 | 变更 |
|---|---|
| `backend/app/agents/optimizer.py` | 新增：背包 DP 组合优化 |
| `backend/app/agents/scoring.py` | 重写：动态权重 + 软偏好 + 排除过滤 + combo 调用 |
| `backend/app/agents/reflect.py` | 重写：async + LLM 硬约束校验 + combo 摘要 |
| `backend/app/agents/state.py` | 新增 combos 字段 |
| `frontend/src/components/DecisionReport.vue` | 重写：雷达图 + 打分表 + 组合方案对比 |
| `backend/tests/test_optimizer.py` | 新增：12 个 optimizer/dynamic-weight 测试 |
| `backend/tests/test_graph.py` | 更新：async reflect + LLM 约束 + combo 测试 |
