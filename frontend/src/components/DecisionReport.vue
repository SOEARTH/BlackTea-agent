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
          <div v-for="(note, i) in chat.report.reflection_notes" :key="i" class="note">
            <el-icon><InfoFilled /></el-icon>
            {{ note }}
          </div>
        </div>
        <div v-if="chat.report.combos?.length" class="combos-section">
          <div class="section-title">组合方案对比</div>
          <div v-for="(scheme, si) in chat.report.combos" :key="si" class="combo-card">
            <div class="combo-header">
              <span class="combo-badge">方案{{ si + 1 }}</span>
              <span class="combo-total">{{ comboTotal(scheme) }} 元</span>
            </div>
            <div class="combo-items">
              <div v-for="(sp, ci) in scheme" :key="ci" class="combo-item">
                <span class="combo-slot">{{ sp.product.dtitle || sp.product.title }}</span>
                <span class="combo-price">{{ sp.product.price }} 元</span>
              </div>
            </div>
          </div>
        </div>
        <div class="recs">
          <div v-for="(item, i) in chat.report.recommendations || []" :key="i" class="rec-item">
            <div class="rank">#{{ item.rank }}</div>
            <div class="rec-main">
              <div class="title">{{ item.product.title }}</div>
              <div class="meta">
                <span class="price">{{ item.product.price }} 元</span>
                <span class="score">综合 {{ item.total }}</span>
              </div>
              <canvas :ref="el => setCanvas(el, i)" width="120" height="120" class="radar"></canvas>
              <table class="score-table">
                <thead>
                  <tr><th>维度</th><th>得分</th><th>权重</th><th>依据</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(a, ai) in item.aspects" :key="ai">
                    <td>{{ aspectLabel(a.aspect) }}</td>
                    <td>{{ a.score.toFixed(1) }}</td>
                    <td>{{ (a.weight * 100).toFixed(0) }}%</td>
                    <td>{{ a.evidence }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="empty">决策报告将在反思通过后显示...</div>
    </div>
  </div>
</template>

<script setup>
import { Document, InfoFilled } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'
import { onMounted, nextTick, watch } from 'vue'

const chat = useChatStore()
const aspectLabels = { price: '价格', reputation: '口碑', sales: '销量', coupon: '券力度', brand: '品牌' }

function aspectLabel(key) { return aspectLabels[key] || key }
function comboTotal(scheme) { return scheme.reduce((s, sp) => s + parseFloat(sp.product.price), 0).toFixed(0) }

const canvases = {}
function setCanvas(el, index) { if (el) canvases[index] = el }

function drawRadar(canvas, aspects) {
  if (!canvas || !aspects || aspects.length === 0) return
  const ctx = canvas.getContext('2d')
  const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2
  const r = Math.min(cx, cy) - 12, n = aspects.length
  ctx.clearRect(0, 0, w, h)
  ctx.strokeStyle = '#e8e8e8'; ctx.lineWidth = 1
  for (let ring = 1; ring <= 5; ring++) {
    ctx.beginPath()
    const rr = (r * ring) / 5
    for (let i = 0; i <= n; i++) {
      const a = (Math.PI * 2 * i) / n - Math.PI / 2
      const x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
    }
    ctx.stroke()
  }
  ctx.strokeStyle = '#dcdcdc'
  for (let i = 0; i < n; i++) {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2
    ctx.beginPath(); ctx.moveTo(cx, cy)
    ctx.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r); ctx.stroke()
  }
  ctx.fillStyle = 'rgba(64, 158, 255, 0.15)'; ctx.strokeStyle = '#409eff'; ctx.lineWidth = 2
  ctx.beginPath()
  for (let i = 0; i < n; i++) {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2
    const sc = Math.max(0, Math.min(10, aspects[i].score))
    const rr = (r * sc) / 10
    const x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
  }
  ctx.closePath(); ctx.fill(); ctx.stroke()
  ctx.fillStyle = '#409eff'
  for (let i = 0; i < n; i++) {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2
    const sc = Math.max(0, Math.min(10, aspects[i].score))
    const rr = (r * sc) / 10
    ctx.beginPath(); ctx.arc(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, 2.5, 0, Math.PI * 2); ctx.fill()
  }
  ctx.fillStyle = '#666'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
  for (let i = 0; i < n; i++) {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2
    ctx.fillText(aspectLabel(aspects[i].aspect), cx + Math.cos(a) * (r + 8), cy + Math.sin(a) * (r + 8))
  }
}

function drawAllRadars() {
  const recs = chat.report?.recommendations || []
  for (let i = 0; i < recs.length; i++) {
    if (canvases[i]) drawRadar(canvases[i], recs[i].aspects)
  }
}

watch(() => chat.report, () => { nextTick(drawAllRadars) }, { deep: true })
onMounted(() => { nextTick(drawAllRadars) })
</script>

<style scoped>
.report-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.panel-title { padding: 12px 16px; font-size: 14px; font-weight: 600; color: #333; display: flex; align-items: center; gap: 6px; border-bottom: 1px solid #f0f0f0; }
.report-body { flex: 1; overflow-y: auto; padding: 12px 16px; }
.summary { font-size: 13px; color: #333; line-height: 1.5; margin-bottom: 12px; padding: 10px 12px; background: #f0f9eb; border-radius: 6px; }
.notes { margin-bottom: 12px; }
.note { font-size: 12px; color: #909399; display: flex; align-items: center; gap: 4px; margin-bottom: 4px; }
.combos-section { margin-bottom: 16px; }
.section-title { font-size: 13px; font-weight: 600; color: #333; margin-bottom: 8px; }
.combo-card { border: 1px solid #409eff; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; background: #f4f9ff; }
.combo-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.combo-badge { font-size: 12px; font-weight: 600; color: #409eff; }
.combo-total { font-size: 13px; font-weight: 700; color: #f56c6c; }
.combo-items { display: flex; flex-direction: column; gap: 2px; }
.combo-item { display: flex; justify-content: space-between; font-size: 12px; color: #555; }
.combo-slot { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: 8px; }
.combo-price { flex-shrink: 0; color: #f56c6c; }
.recs { display: flex; flex-direction: column; gap: 10px; }
.rec-item { display: flex; gap: 10px; padding: 10px 12px; border: 1px solid #f0f0f0; border-radius: 8px; }
.rank { font-size: 16px; font-weight: 700; color: #409eff; width: 32px; text-align: center; }
.rec-main { flex: 1; min-width: 0; }
.title { font-size: 13px; font-weight: 600; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.meta { display: flex; gap: 12px; margin-top: 4px; flex-wrap: wrap; align-items: center; }
.price { font-size: 13px; color: #f56c6c; font-weight: 600; }
.score { font-size: 12px; color: #909399; }
.radar { display: block; margin: 8px auto; }
.score-table { width: 100%; font-size: 11px; border-collapse: collapse; margin-top: 6px; }
.score-table th { text-align: left; color: #909399; font-weight: 400; padding: 2px 4px; border-bottom: 1px solid #f0f0f0; }
.score-table td { padding: 2px 4px; color: #555; border-bottom: 1px solid #f8f8f8; }
.score-table td:nth-child(2) { font-weight: 600; color: #409eff; }
.empty { color: #c0c4cc; font-size: 13px; text-align: center; padding: 20px; }
</style>
