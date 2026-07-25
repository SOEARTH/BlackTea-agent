<template>
  <div class="rail">
    <div class="rail-head">
      <span class="rh-title">Agent 轨迹</span>
      <span class="rh-meta">{{ doneCount }}/{{ STAGES.length }}</span>
    </div>

    <div class="rail-body" ref="bodyRef">
      <!-- 阶段轴：7 节点为主轴(每节点一个 stage 卡)，观影并行分支用「‖」层标记 -->
      <div
        v-for="(stage, idx) in STAGES"
        :key="stage.node"
        class="stage"
        :class="stageState(stage.node)"
      >
        <div class="spine">
          <span class="spine-dot"></span>
          <span v-if="idx < STAGES.length - 1" class="spine-line" :class="{ branch: stage.fork }"></span>
        </div>
        <div class="stage-card">
          <div class="stage-top">
            <span class="stage-name">{{ stage.name }}</span>
            <i v-if="stage.fork" class="fork-mark" title="并行扇出/汇聚">‖</i>
          </div>
          <p class="stage-desc">{{ stage.desc }}</p>
          <p v-if="msgFor(stage.node)" class="stage-msg">{{ msgFor(stage.node) }}</p>
        </div>
      </div>

      <div v-if="!chat.agentTimeline.length" class="empty">
        等待对话开始…
      </div>
    </div>
  </div>
</template>

<script setup>
import { useChatStore } from "../stores/chat";
import { computed } from "vue";

const chat = useChatStore();

// 7 节点 + fork 标记(用来画 LangGraph fork-join 视觉线索)
const STAGES = [
  { node: "clarify",    name: "需求澄清", desc: "LLM 提取品类/预算/场景 · interrupt 反问" },
  { node: "search",     name: "选品检索", desc: "MCP 搜索 · 预算硬过滤 · 异常降级" },
  { node: "price",      name: "比价分析", desc: "历史券后价趋势 · 低价分位", fork: true },
  { node: "reputation", name: "口碑分析", desc: "方面级 RAG 聚合 · DSR 兜底", fork: true },
  { node: "scoring",    name: "打分排序", desc: "5 维加权矩阵 · 记忆召回调权" },
  { node: "reflect",    name: "反思校验", desc: "LLM 硬约束 · 预算/好价/死循环" },
  { node: "supervisor", name: "Supervisor", desc: "路由控制 → END" },
];

const doneSet = computed(() => new Set(chat.agentTimeline.map(t => t.node)));
const activeNode = computed(() => chat.activeNode);

const doneCount = computed(() => {
  let n = 0;
  for (const s of STAGES) if (doneSet.value.has(s.node)) n++;
  return n;
});

function stageState(node) {
  if (doneSet.value.has(node)) return "done";
  if (node === activeNode.value) return "active";
  return "todo";
}
function msgFor(node) {
  const item = chat.agentTimeline.find(t => t.node === node);
  return item?.message || "";
}
</script>

<style scoped>
.rail { display: flex; flex-direction: column; height: 100%; background: var(--bt-surface); }
.rail-head {
  display: flex; align-items: baseline; justify-content: space-between;
  padding: 14px 18px; border-bottom: 1px solid var(--bt-border-soft);
}
.rh-title { font-size: var(--bt-fs-h2); font-weight: 700; color: var(--bt-text); }
.rh-meta { font-size: 12px; color: var(--bt-text-3); }

.rail-body { flex: 1; min-height: 0; overflow-y: auto; padding: 16px 18px 20px; }

.stage { display: grid; grid-template-columns: 16px 1fr; gap: 12px; }
.spine { position: relative; display: flex; flex-direction: column; align-items: center; }
.spine-dot {
  width: 10px; height: 10px; margin-top: 4px; border-radius: 50%;
  border: 2px solid var(--bt-border); background: var(--bt-surface);
}
.stage.done .spine-dot { background: var(--bt-pos); border-color: var(--bt-pos); }
.stage.active .spine-dot {
  background: var(--bt-brand); border-color: var(--bt-brand);
  box-shadow: 0 0 0 4px var(--bt-brand-soft);
}
.spine-line {
  flex: 1; width: 2px; background: var(--bt-border);
  margin: 6px 0 0 0; min-height: 18px;
}
.stage.active .spine-line { background: var(--bt-brand-soft); }
.stage.done .spine-line { background: var(--bt-tea-soft); }
.spine-line.branch { background: var(--bt-amber-soft); }

.stage-card { padding-bottom: 16px; min-width: 0; }
.stage-top { display: flex; align-items: center; gap: 6px; }
.stage-name { font-size: 13px; font-weight: 700; color: var(--bt-text); }
.stage.todo .stage-name { color: var(--bt-text-3); font-weight: 600; }
.fork-mark {
  font-size: 11px; font-weight: 900; color: var(--bt-amber);
  font-style: normal;
  border: 1px solid var(--bt-amber); border-radius: 3px;
  padding: 0 4px; line-height: 14px;
}
.stage-desc { margin: 4px 0 0 0; font-size: 11px; color: var(--bt-text-3); line-height: 1.4; }
.stage-msg {
  margin: 6px 0 0 0; font-size: 11px; color: var(--bt-tea);
  background: var(--bt-tea-soft); padding: 5px 8px; border-radius: var(--bt-r-sm);
  line-height: 1.4; word-break: break-word;
}
.empty { color: var(--bt-text-3); font-size: 13px; text-align: center; padding: 24px 0; }
</style>
