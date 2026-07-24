<template>
  <div class="timeline-panel">
    <div class="panel-title">
      <el-icon><Histogram /></el-icon>
      Agent 轨迹
    </div>
    <div class="timeline">
      <div
        v-for="(item, i) in chat.agentTimeline"
        :key="i"
        class="timeline-item"
      >
        <div class="dot" :class="{ active: i === chat.agentTimeline.length - 1 }"></div>
        <div class="content">
          <div class="node-name">{{ nodeLabel(item.node) }}</div>
          <div class="node-msg" v-if="item.message">{{ item.message }}</div>
        </div>
      </div>
      <div v-if="chat.agentTimeline.length === 0" class="empty">
        等待对话开始...
      </div>
    </div>
  </div>
</template>

<script setup>
import { Histogram } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'

const chat = useChatStore()

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
</script>

<style scoped>
.timeline-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-bottom: 1px solid #eee;
  overflow: hidden;
}
.panel-title {
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  display: flex;
  align-items: center;
  gap: 6px;
  border-bottom: 1px solid #f0f0f0;
}
.timeline {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}
.timeline-item {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  align-items: flex-start;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #c0c4cc;
  margin-top: 4px;
  flex-shrink: 0;
}
.dot.active {
  background: #409eff;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.2);
}
.content {
  flex: 1;
  min-width: 0;
}
.node-name {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}
.node-msg {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
  line-height: 1.4;
}
.empty {
  color: #c0c4cc;
  font-size: 13px;
  text-align: center;
  padding: 20px;
}
</style>
