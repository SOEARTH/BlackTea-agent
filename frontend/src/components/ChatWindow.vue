<template>
  <div class="chat-window">
    <!-- 消息列表 -->
    <div class="messages" ref="messagesRef">
      <div
        v-for="(msg, i) in chat.messages"
        :key="i"
        class="message"
        :class="msg.role"
      >
        <div class="bubble">
          <div v-if="msg.node" class="node-tag">{{ nodeLabel(msg.node) }}</div>
          {{ msg.content }}
        </div>
      </div>
      <div v-if="chat.streaming" class="message ai">
        <div class="bubble typing">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>正在思考...</span>
        </div>
      </div>
    </div>

    <!-- 输入框 -->
    <div class="input-bar">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="2"
        placeholder="输入你的购物需求，如：我想买个降噪耳机，预算 500 以内"
        resize="none"
        @keydown.enter.ctrl="handleSend"
        :disabled="chat.streaming"
      />
      <el-button
        type="primary"
        @click="handleSend"
        :disabled="!inputText.trim() || chat.streaming"
        :loading="chat.streaming"
      >
        发送
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'

const chat = useChatStore()
const inputText = ref('')
const messagesRef = ref(null)

const NODE_LABELS = {
  clarify: '需求澄清',
  search: '选品检索',
  price: '比价分析',
  reputation: '口碑分析',
  scoring: '打分排序',
  reflect: '反思校验',
  supervisor: '路由控制',
}

function nodeLabel(node) {
  return NODE_LABELS[node] || node
}

function handleSend() {
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''
  chat.sendMessage(text)
}

// 自动滚到底
watch(() => chat.messages.length, async () => {
  await nextTick()
  const el = messagesRef.value
  if (el) el.scrollTop = el.scrollHeight
})
</script>

<style scoped>
.chat-window {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}
.message {
  margin-bottom: 12px;
  display: flex;
}
.message.user {
  justify-content: flex-end;
}
.message.ai {
  justify-content: flex-start;
}
.bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
}
.message.user .bubble {
  background: #409eff;
  color: #fff;
}
.message.ai .bubble {
  background: #f4f4f5;
  color: #333;
}
.node-tag {
  font-size: 11px;
  color: #909399;
  margin-bottom: 4px;
}
.typing {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #909399;
}
.input-bar {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid #eee;
  align-items: flex-end;
}
.input-bar .el-input {
  flex: 1;
}
</style>
