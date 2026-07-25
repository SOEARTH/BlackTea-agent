<template>
  <Transition name="fade">
    <div v-if="chat.interrupt" class="overlay">
      <div class="dialog">
        <div class="dialog-head">
          <i class="ask-dot"></i>
          <span class="dialog-title">需要补充信息</span>
          <span class="dialog-sub">决策已暂停 · interrupt</span>
        </div>
        <div class="dialog-body">
          <p class="ask">{{ chat.interrupt.message }}</p>
          <textarea
            v-model="answer"
            class="answer"
            placeholder="请输入补充信息…"
            rows="3"
            @keydown.enter.ctrl.prevent="resume"
          />
          <div class="actions">
            <span class="hint">Ctrl + Enter 提交</span>
            <button class="btn-resume" :disabled="!answer.trim() || chat.streaming" @click="resume">
              {{ chat.streaming ? "提交中" : "提交并继续" }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref } from "vue";
import { useChatStore } from "../stores/chat";

const chat = useChatStore();
const answer = ref("");

function resume() {
  const t = answer.value.trim();
  if (!t || chat.streaming) return;
  answer.value = "";
  chat.resumeChat(t);
}
</script>

<style scoped>
.overlay {
  position: fixed; inset: 0;
  background: rgba(40, 30, 20, 0.35);
  backdrop-filter: blur(2px);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
}
.dialog {
  width: 440px; max-width: 92vw;
  background: var(--bt-surface);
  border-radius: var(--bt-r-lg);
  box-shadow: var(--bt-shadow-pop);
  border: 1px solid var(--bt-border-soft);
  overflow: hidden;
}
.dialog-head {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--bt-border-soft);
  background: var(--bt-subtle);
}
.ask-dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: var(--bt-info);
  box-shadow: 0 0 0 3px rgba(45, 115, 184, 0.18);
}
.dialog-title { font-size: 14px; font-weight: 700; color: var(--bt-text); }
.dialog-sub { margin-left: auto; font-size: 11px; color: var(--bt-text-3); }

.dialog-body { padding: 18px; display: flex; flex-direction: column; gap: 12px; }
.ask {
  margin: 0; padding: 10px 12px;
  background: rgba(45, 115, 184, 0.08);
  border-left: 3px solid var(--bt-info);
  border-radius: var(--bt-r-sm);
  font-size: 13px; color: var(--bt-text); line-height: 1.5;
}
.answer {
  width: 100%; resize: none; font-family: inherit;
  border: 1px solid var(--bt-border); border-radius: var(--bt-r-md);
  padding: 10px 12px; font-size: 13px; line-height: 1.5;
  background: var(--bt-subtle); color: var(--bt-text); outline: none;
  transition: border-color 0.15s;
}
.answer:focus { border-color: var(--bt-info); background: var(--bt-surface); }
.actions { display: flex; align-items: center; justify-content: space-between; }
.hint { font-size: 11px; color: var(--bt-text-3); }
.btn-resume {
  border: none; cursor: pointer;
  padding: 8px 18px; border-radius: var(--bt-r-md);
  background: var(--bt-tea); color: #fff;
  font-size: 13px; font-weight: 600;
  transition: background 0.15s;
}
.btn-resume:hover:not(:disabled) { background: #1A5641; }
.btn-resume:disabled { background: var(--bt-muted); color: var(--bt-text-3); cursor: not-allowed; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.18s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
