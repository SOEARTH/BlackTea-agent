<template>
  <div class="app-shell">
    <!-- Brand top bar -->
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark"></span>
        <span class="brand-name">BlackTea</span>
        <span class="brand-tag">智购决策引擎</span>
      </div>
      <div class="topbar-meta">
        <span class="state-pill" :class="{ live: chat.streaming }">
          <i class="state-dot"></i>{{ chat.streaming ? "推理中" : "空闲" }}
        </span>
        <span class="meta-chip">{{ NODE_LABELS[chat.activeNode] || "就绪" }}<span
          v-if="chat.iteration > 0" class="meta-iter">· 第 {{ chat.iteration }} 轮</span></span>
        <span class="avatar">SOEARTH</span>
      </div>
    </header>

    <!-- Three-column workbench -->
    <main class="workbench">
      <ChatWindow class="col-chat" />
      <AgentTimeline class="col-rail" />
      <DecisionReport class="col-report" />
    </main>

  </div>
</template>

<script setup>
import ChatWindow from "./components/ChatWindow.vue";
import AgentTimeline from "./components/AgentTimeline.vue";
import DecisionReport from "./components/DecisionReport.vue";
import { useChatStore } from "./stores/chat";

const chat = useChatStore();
const NODE_LABELS = {
  clarify: "需求澄清",
  search: "选品检索",
  price: "比价分析",
  reputation: "口碑分析",
  scoring: "打分排序",
  reflect: "反思校验",
  supervisor: "路由控制",
};
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bt-canvas);
}

/* ---- Top bar ---- */
.topbar {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: var(--bt-surface);
  border-bottom: 1px solid var(--bt-border);
}
.brand { display: flex; align-items: center; gap: 10px; }
.brand-mark {
  width: 22px; height: 22px; border-radius: 50%;
  background: var(--bt-brand);
  box-shadow: inset -4px -4px 0 rgba(0,0,0,0.08);
}
.brand-name { font-size: var(--bt-fs-display); font-weight: 700; color: var(--bt-text); }
.brand-tag  { font-size: var(--bt-fs-caption); color: var(--bt-text-3); }

.topbar-meta { display: flex; align-items: center; gap: 10px; }
.state-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 10px; border-radius: var(--bt-r-full);
  font-size: 12px; color: var(--bt-text-2);
  background: var(--bt-muted);
}
.state-pill.live { background: var(--bt-brand-soft); color: var(--bt-brand); }
.state-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--bt-text-3); }
.state-pill.live .state-dot {
  background: var(--bt-brand);
  box-shadow: 0 0 0 3px var(--bt-brand-soft);
  animation: pulse 1.2s infinite;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 var(--bt-brand-soft); }
  70% { box-shadow: 0 0 0 5px rgba(200,85,61,0); }
  100% { box-shadow: 0 0 0 0 rgba(200,85,61,0); }
}
.meta-chip {
  font-size: 12px; color: var(--bt-text-2);
  padding: 5px 10px; background: var(--bt-subtle);
  border-radius: var(--bt-r-sm);
  border: 1px solid var(--bt-border-soft);
}
.meta-iter { color: var(--bt-text-3); margin-left: 4px; }
.avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: var(--bt-tea); color: #fff;
  font-size: 10px; font-weight: 700; letter-spacing: 0.5px;
  display: flex; align-items: center; justify-content: center;
}

/* ---- Workbench ---- */
.workbench {
  flex: 1;
  display: grid;
  grid-template-columns: 440px 340px 1fr;
  min-height: 0;
  /* 单行轨道钉死为容器高度，列内容再多也不许把整页撑出滚动条 */
  grid-template-rows: minmax(0, 1fr);
  overflow: hidden;
}
/* grid 子项默认可被内容撑大，显式允许收缩，让各列自己滚动 */
.workbench > * { min-height: 0; }
.col-chat { border-right: 1px solid var(--bt-border); }
.col-rail { border-right: 1px solid var(--bt-border); }

@media (max-width: 1200px) {
  .workbench { grid-template-columns: 380px 300px 1fr; }
}
</style>
