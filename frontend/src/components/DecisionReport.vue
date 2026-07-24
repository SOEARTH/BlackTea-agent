<template>
  <div class="report-panel">
    <div class="panel-title">
      <el-icon><Document /></el-icon>
      决策报告
    </div>
    <div class="report-body">
      <template v-if="chat.report">
        <div class="summary">{{ chat.report.summary }}</div>
        <div v-if="chat.report.reflection_notes?.length" class="notes">
          <div v-for="note in chat.report.reflection_notes" :key="note" class="note">
            <el-icon><InfoFilled /></el-icon>
            {{ note }}
          </div>
        </div>
        <div class="recs">
          <div
            v-for="(item, i) in chat.report.recommendations || []"
            :key="i"
            class="rec-item"
          >
            <div class="rank">#{{ item.rank }}</div>
            <div class="info">
              <div class="title">{{ item.product.title }}</div>
              <div class="meta">
                <span class="price">{{ item.product.price }} 元</span>
                <span class="score">综合 {{ item.total }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="empty">
        决策报告将在反思通过后显示...
      </div>
    </div>
  </div>
</template>

<script setup>
import { Document, InfoFilled } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'

const chat = useChatStore()
</script>

<style scoped>
.report-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
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
.report-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}
.summary {
  font-size: 13px;
  color: #333;
  line-height: 1.5;
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #f0f9eb;
  border-radius: 6px;
}
.notes {
  margin-bottom: 12px;
}
.note {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 4px;
}
.recs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rec-item {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
}
.rank {
  font-size: 16px;
  font-weight: 700;
  color: #409eff;
  width: 32px;
  text-align: center;
}
.info {
  flex: 1;
  min-width: 0;
}
.title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.meta {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}
.price {
  font-size: 13px;
  color: #f56c6c;
  font-weight: 600;
}
.score {
  font-size: 12px;
  color: #909399;
}
.empty {
  color: #c0c4cc;
  font-size: 13px;
  text-align: center;
  padding: 20px;
}
</style>
