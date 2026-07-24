<template>
  <div class="app-container">
    <!-- 左侧：对话流 -->
    <div class="chat-panel">
      <div class="chat-header">
        <h2>BlackTea . 智购决策引擎</h2>
      </div>
      <ChatWindow />
    </div>

    <!-- 右侧：agent 轨迹 + 决策报告 -->
    <div class="side-panel">
      <AgentTimeline />
      <DecisionReport />
    </div>

    <!-- interrupt 弹窗 -->
    <InterruptDialog />
  </div>
</template>

<script setup>
import ChatWindow from './components/ChatWindow.vue'
import AgentTimeline from './components/AgentTimeline.vue'
import DecisionReport from './components/DecisionReport.vue'
import InterruptDialog from './components/InterruptDialog.vue'
</script>

<style scoped>
.app-container {
  display: flex;
  height: 100vh;
  gap: 1px;
  background: #e0e0e0;
}
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  min-width: 0;
}
.chat-header {
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}
.chat-header h2 {
  font-size: 16px;
  color: #333;
}
.side-panel {
  width: 380px;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
}
</style>
