<template>
  <div class="chat">
    <div class="chat-head">
      <i class="dot-live"></i>
      <span class="head-title">对话 · 决策会话</span>
      <span class="head-sub">{{ chat.messages.length }} 条</span>
    </div>

    <div class="stream" ref="streamRef">
      <template v-for="(msg, i) in chat.messages" :key="i">
        <div class="msg-row" :class="msg.role">
          <div class="bubble" :class="msg.role">
            <span v-if="msg.node" class="node-tag">{{ nodeLabel(msg.node) }}</span>
            <span class="bubble-text">{{ msg.content }}</span>
          </div>
        </div>
      </template>
      <div v-if="chat.streaming" class="msg-row ai">
        <div class="bubble ai typing">
          <i class="typing-dot"></i><i class="typing-dot"></i><i class="typing-dot"></i>
        </div>
      </div>
    </div>

    <div class="compose">
      <textarea
        v-model="text"
        class="compose-input"
        placeholder="输入你的购物需求，如：我想买个降噪耳机，预算 500 以内"
        rows="2"
        @keydown.enter.ctrl.prevent="send"
        :disabled="chat.streaming"
      />
      <div class="compose-actions">
        <span class="hint">Ctrl + Enter 发送</span>
        <button class="btn-send" :disabled="!text.trim() || chat.streaming" @click="send">
          {{ chat.streaming ? "推理中" : "发送" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from "vue";
import { useChatStore } from "../stores/chat";

const chat = useChatStore();
const text = ref("");
const streamRef = ref(null);

const LABELS = {
  clarify: "需求澄清",
  search: "选品检索",
  price: "比价分析",
  reputation: "口碑分析",
  scoring: "打分排序",
  reflect: "反思校验",
  supervisor: "路由控制",
};
const nodeLabel = (n) => LABELS[n] || n;

function send() {
  const t = text.value.trim();
  if (!t || chat.streaming) return;
  text.value = "";
  chat.sendMessage(t);
}

watch(() => chat.messages.length, async () => {
  await nextTick();
  const el = streamRef.value;
  if (el) el.scrollTop = el.scrollHeight;
});
</script>

<style scoped>
.chat { display: flex; flex-direction: column; height: 100%; background: var(--bt-surface); }

.chat-head {
  display: flex; align-items: center; gap: 8px;
  padding: 14px 18px; border-bottom: 1px solid var(--bt-border-soft);
}
.dot-live { width: 7px; height: 7px; border-radius: 50%; background: var(--bt-pos); }
.head-title { font-size: var(--bt-fs-h2); font-weight: 700; color: var(--bt-text); }
.head-sub { font-size: 11px; color: var(--bt-text-3); margin-left: auto; }

.stream {
  flex: 1; min-height: 0; overflow-y: auto;
  padding: 18px; background: var(--bt-subtle);
  display: flex; flex-direction: column; gap: 14px;
}

.msg-row { display: flex; }
.msg-row.user { justify-content: flex-end; }
.msg-row.ai { justify-content: flex-start; }

.bubble {
  max-width: calc(100% - 32px);
  padding: 10px 13px; border-radius: var(--bt-r-lg);
  font-size: var(--bt-fs-body); line-height: 1.55;
  display: flex; flex-direction: column; gap: 4px;
  box-shadow: var(--bt-shadow-card);
}
.bubble.user { background: var(--bt-brand); color: #fff; border-bottom-right-radius: 4px; }
.bubble.ai { background: var(--bt-surface); color: var(--bt-text); border: 1px solid var(--bt-border-soft); border-bottom-left-radius: 4px; }

.node-tag {
  align-self: flex-start;
  font-size: var(--bt-fs-tag); font-weight: 700;
  padding: 2px 6px; border-radius: var(--bt-r-sm);
  background: var(--bt-amber); color: var(--bt-text);
}
.bubble-text { white-space: pre-wrap; word-break: break-word; }

.typing { padding: 12px 14px; gap: 4px; flex-direction: row; align-items: center; }
.typing-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--bt-text-3);
  animation: blink 1.4s infinite both;
}
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%, 80%, 100% { opacity: 0.2; } 40% { opacity: 1; } }

.compose { border-top: 1px solid var(--bt-border-soft); background: var(--bt-surface); padding: 12px; }
.compose-input {
  width: 100%; resize: none; border: 1px solid var(--bt-border);
  border-radius: var(--bt-r-md); padding: 10px 12px;
  font-size: var(--bt-fs-body); line-height: 1.5; color: var(--bt-text);
  background: var(--bt-subtle); outline: none; font-family: inherit;
  transition: border-color 0.15s;
}
.compose-input:focus { border-color: var(--bt-brand); background: var(--bt-surface); }
.compose-input::placeholder { color: var(--bt-text-3); }
.compose-actions {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 8px;
}
.hint { font-size: 11px; color: var(--bt-text-3); }
.btn-send {
  border: none; cursor: pointer;
  padding: 8px 18px; border-radius: var(--bt-r-md);
  background: var(--bt-brand); color: #fff;
  font-size: var(--bt-fs-body); font-weight: 600;
  transition: background 0.15s;
}
.btn-send:hover:not(:disabled) { background: var(--bt-brand-hover); }
.btn-send:disabled { background: var(--bt-muted); color: var(--bt-text-3); cursor: not-allowed; }
</style>
