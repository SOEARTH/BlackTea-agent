<template>
  <el-dialog
    v-model="visible"
    title="需要补充信息"
    width="420px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
  >
    <div class="interrupt-msg">{{ chat.interrupt?.message }}</div>
    <el-input
      v-model="answerText"
      type="textarea"
      :rows="3"
      placeholder="请输入补充信息..."
      resize="none"
      @keydown.enter.ctrl="handleResume"
    />
    <template #footer>
      <el-button
        type="primary"
        @click="handleResume"
        :loading="chat.streaming"
      >
        提交并继续
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useChatStore } from '../stores/chat'

const chat = useChatStore()
const answerText = ref('')

const visible = computed({
  get: () => !!chat.interrupt,
  set: () => {},
})

function handleResume() {
  const text = answerText.value.trim()
  if (!text) return
  answerText.value = ''
  chat.resumeChat(text)
}
</script>

<style scoped>
.interrupt-msg {
  margin-bottom: 12px;
  padding: 12px 16px;
  background: #ecf5ff;
  border-radius: 8px;
  font-size: 14px;
  color: #409eff;
  line-height: 1.5;
}
</style>
