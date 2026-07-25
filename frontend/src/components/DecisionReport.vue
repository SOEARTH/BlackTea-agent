<template>
  <div class="report">
    <header class="rep-head">
      <span class="rep-title">决策报告</span>
      <span v-if="chat.report" class="rep-meta">综合 {{ topRec?.total ?? "—" }} · {{ recs.length }} 件入选</span>
    </header>

    <div class="rep-body" ref="bodyRef">
      <div v-if="!chat.report" class="empty">
        <i class="ph" v-for="n in 3" :key="n"></i>
        <p>决策报告将在反思通过后显示</p>
      </div>

      <template v-else>
        <!-- 决策摘要 —— 直接结论先行 -->
        <section class="summary">
          <span class="summary-label">摘要</span>
          <p class="summary-text">{{ chat.report.summary || "—" }}</p>
        </section>

        <!-- Top1 推荐卡：雷达打分可视化 + 综合分 + 价位 -->
        <section v-if="topRec" class="hero-card">
          <div class="hero-rank">#{{ topRec.rank }}</div>
          <div class="hero-main">
            <div class="hero-top">
              <div class="hero-title">{{ topRec.product.title }}</div>
              <div class="hero-meta">
                <span class="hero-price">¥{{ topRec.product.price }}</span>
                <span class="hero-sep">·</span>
                <span class="hero-total">综合 {{ topRec.total }}</span>
              </div>
            </div>
            <div class="hero-grid">
              <canvas :ref="el => setCanvas(el, 0)" width="160" height="160" class="radar"></canvas>
              <table class="aspect-table">
                <thead><tr><th>维度</th><th>得分</th><th>权重</th></tr></thead>
                <tbody>
                  <tr v-for="(a, ai) in topRec.aspects" :key="ai">
                    <td>{{ aspectLabel(a.aspect) }}</td>
                    <td class="num">{{ a.score.toFixed(1) }}</td>
                    <td class="num">{{ (a.weight * 100).toFixed(0) }}%</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <!-- Top 列表：#2 / #3 横向卡 + 打分条 -->
        <section v-if="recs.length > 1" class="runners">
          <div v-for="(item, i) in recs.slice(1)" :key="item.rank" class="runner-card">
            <div class="runner-rank">#{{ item.rank }}</div>
            <div class="runner-body">
              <div class="runner-title">{{ item.product.title }}</div>
              <div class="runner-meta">
                <span class="runner-price">¥{{ item.product.price }}</span>
                <span class="runner-total">综合 {{ item.total }}</span>
              </div>
              <div class="bar-row">
                <div v-for="(a, ai) in item.aspects" :key="ai"
                     class="bar" :title="aspectLabel(a.aspect) + ' ' + a.score.toFixed(1)">
                  <span class="bar-fill" :style="{ width: pctWidth(a.score), background: aspectColor(a.aspect) }"></span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- 依据详情：折叠展开 -->
        <details class="evidence" v-if="topRec">
          <summary>打分依据 · Top1</summary>
          <div class="ev-rows">
            <div v-for="(a, ai) in topRec.aspects" :key="ai" class="ev-row">
              <span class="ev-k">{{ aspectLabel(a.aspect) }} · {{ (a.weight*100).toFixed(0) }}%</span>
              <span class="ev-v">{{ a.evidence }}</span>
            </div>
          </div>
        </details>

        <!-- 组合方案对比 -->
        <section v-if="combos.length" class="combos">
          <div class="sect-title">组合方案对比</div>
          <div class="combo-grid">
            <div v-for="(scheme, si) in combos" :key="si" class="combo-card"
                 :class="{ best: si === 0 }">
              <div class="combo-head">
                <span class="combo-badge">方案 {{ si + 1 }}<span v-if="si === 0" class="best-tag">最低</span></span>
                <span class="combo-total">¥{{ comboTotal(scheme) }}</span>
              </div>
              <ul class="combo-list">
                <li v-for="(sp, ci) in scheme" :key="ci">
                  <span class="cb-slot">{{ sp.product.dtitle || sp.product.title }}</span>
                  <span class="cb-price">¥{{ sp.product.price }}</span>
                </li>
              </ul>
            </div>
          </div>
        </section>

        <!-- 反思备注 -->
        <section v-if="notes.length" class="notes">
          <div class="sect-title">反思备注</div>
          <div v-for="(n, i) in notes" :key="i" class="note">
            <i class="note-dot"></i>{{ n }}
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { useChatStore } from "../stores/chat";
import { onMounted, nextTick, watch, ref } from "vue";

const chat = useChatStore();

const ASPECT_LABELS = { price: "价格", reputation: "口碑", sales: "销量", coupon: "券力度", brand: "品牌" };
const aspectLabel = (k) => ASPECT_LABELS[k] || k;
const aspectColor = (k) => ({
  price:       "#C8553D",
  reputation:  "#216B4F",
  sales:       "#E8A33C",
  coupon:      "#2D73B8",
  brand:       "#7B5E3C",
}[k] || "#998F84");
const pctWidth = (score) => `${Math.max(0, Math.min(10, score)) * 10}%`;

const recs = ref([]);
const topRec = ref(null);
const combos = ref([]);
const notes = ref([]);
const bodyRef = ref(null);

function syncReport() {
  if (!chat.report) return;
  recs.value = chat.report.recommendations || [];
  topRec.value = recs.value[0] || null;
  combos.value = chat.report.combos || [];
  notes.value = chat.report.reflection_notes || [];
}
function comboTotal(scheme) {
  const sum = scheme.reduce((s, sp) => s + parseFloat(sp.product.price || 0), 0);
  return Number.isFinite(sum) ? sum.toFixed(0) : "—";
}

// ---- Radar drawing ----
const canvases = {};
function setCanvas(el, index) { if (el) canvases[index] = el; }

function drawRadar(canvas, aspects) {
  if (!canvas || !aspects || aspects.length === 0) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
  const r = Math.min(cx, cy) - 16, n = aspects.length;
  const palette = aspects.map(a => aspectColor(a.aspect));

  ctx.clearRect(0, 0, w, h);
  // rings
  ctx.strokeStyle = "#E2DBCB"; ctx.lineWidth = 1;
  for (let ring = 1; ring <= 5; ring++) {
    ctx.beginPath();
    const rr = (r * ring) / 5;
    for (let i = 0; i <= n; i++) {
      const a = (Math.PI * 2 * i) / n - Math.PI / 2;
      const x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
  // spokes
  ctx.strokeStyle = "#EEE8DE";
  for (let i = 0; i < n; i++) {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    ctx.beginPath(); ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r); ctx.stroke();
  }
  // shape
  ctx.fillStyle = "rgba(200, 85, 61, 0.18)"; ctx.strokeStyle = "#C8553D"; ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    const sc = Math.max(0, Math.min(10, aspects[i].score));
    const rr = (r * sc) / 10;
    const x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.closePath(); ctx.fill(); ctx.stroke();
  // vertices
  for (let i = 0; i < n; i++) {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    const sc = Math.max(0, Math.min(10, aspects[i].score));
    const rr = (r * sc) / 10;
    ctx.beginPath();
    ctx.arc(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, 3, 0, Math.PI * 2);
    ctx.fillStyle = palette[i]; ctx.fill();
  }
  // labels
  ctx.fillStyle = "#5C564F"; ctx.font = "11px Inter, sans-serif";
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  for (let i = 0; i < n; i++) {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    ctx.fillText(aspectLabel(aspects[i].aspect),
      cx + Math.cos(a) * (r + 10), cy + Math.sin(a) * (r + 10));
  }
}

function drawAll() {
  if (topRec.value && canvases[0]) drawRadar(canvases[0], topRec.value.aspects);
}

watch(() => chat.report, async () => {
  syncReport();
  await nextTick();
  drawAll();
}, { deep: true });
onMounted(async () => { syncReport(); await nextTick(); drawAll(); });
</script>

<style scoped>
.report { display: flex; flex-direction: column; height: 100%; background: var(--bt-surface); }
.rep-head {
  display: flex; align-items: baseline; justify-content: space-between;
  padding: 14px 18px; border-bottom: 1px solid var(--bt-border-soft);
}
.rep-title { font-size: var(--bt-fs-h2); font-weight: 700; color: var(--bt-text); }
.rep-meta { font-size: 12px; color: var(--bt-text-3); }

.rep-body { flex: 1; min-height: 0; overflow-y: auto; padding: 16px 18px 24px; display: flex; flex-direction: column; gap: 14px; }

.empty { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 32px 0; color: var(--bt-text-3); font-size: 13px; }
.ph { display: block; width: 100%; height: 10px; background: var(--bt-muted); border-radius: 4px; opacity: 0.5; }
.empty p { margin-top: 8px; }

/* summary */
.summary { display: flex; gap: 8px; align-items: flex-start; background: var(--bt-tea-soft); border-left: 3px solid var(--bt-tea); padding: 10px 12px; border-radius: var(--bt-r-sm); }
.summary-label { font-size: 11px; font-weight: 700; color: var(--bt-tea); }
.summary-text { margin: 0; font-size: var(--bt-fs-body); color: var(--bt-text); line-height: 1.55; }

/* hero */
.hero-card { display: flex; gap: 10px; border: 1px solid var(--bt-border); border-radius: var(--bt-r-lg); background: var(--bt-subtle); padding: 14px; box-shadow: var(--bt-shadow-card); }
.hero-rank { font-size: 22px; font-weight: 800; color: var(--bt-brand); width: 28px; }
.hero-main { flex: 1; min-width: 0; }
.hero-top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 10px; }
.hero-title { font-size: 14px; font-weight: 700; color: var(--bt-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hero-meta { font-size: 12px; color: var(--bt-text-2); white-space: nowrap; }
.hero-price { color: var(--bt-brand); font-weight: 700; }
.hero-sep { color: var(--bt-text-3); margin: 0 4px; }
.hero-total { color: var(--bt-tea); font-weight: 700; }
.hero-grid { display: grid; grid-template-columns: 160px 1fr; gap: 12px; align-items: center; }
.radar { display: block; }
.aspect-table { width: 100%; font-size: 11px; border-collapse: collapse; }
.aspect-table th { text-align: left; font-weight: 600; color: var(--bt-text-3); padding: 2px 4px; border-bottom: 1px solid var(--bt-border); }
.aspect-table td { padding: 4px; color: var(--bt-text-2); border-bottom: 1px solid var(--bt-border-soft); }
.aspect-table td.num { text-align: right; font-weight: 700; color: var(--bt-text); }

/* runners */
.runners { display: flex; flex-direction: column; gap: 8px; }
.runner-card { display: flex; gap: 8px; padding: 10px 12px; border: 1px solid var(--bt-border-soft); border-radius: var(--bt-r-md); background: var(--bt-surface); }
.runner-rank { font-size: 14px; font-weight: 800; color: var(--bt-amber); width: 24px; }
.runner-body { flex: 1; min-width: 0; }
.runner-title { font-size: 13px; font-weight: 600; color: var(--bt-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.runner-meta { display: flex; gap: 8px; margin: 4px 0 6px; font-size: 12px; }
.runner-price { color: var(--bt-brand); font-weight: 700; }
.runner-total { color: var(--bt-text-2); }
.bar-row { display: flex; gap: 4px; }
.bar { flex: 1; height: 6px; background: var(--bt-muted); border-radius: 3px; overflow: hidden; }
.bar-fill { display: block; height: 100%; border-radius: 3px; transition: width 0.4s; }

/* evidence */
.evidence { border: 1px solid var(--bt-border-soft); border-radius: var(--bt-r-md); padding: 8px 10px; background: var(--bt-subtle); }
.evidence summary { cursor: pointer; font-size: 12px; font-weight: 600; color: var(--bt-text-2); }
.ev-rows { margin-top: 8px; display: flex; flex-direction: column; gap: 6px; }
.ev-row { font-size: 11px; line-height: 1.4; }
.ev-k { font-weight: 700; color: var(--bt-tea); display: block; }
.ev-v { color: var(--bt-text-2); display: block; }

/* combos */
.sect-title { font-size: 12px; font-weight: 700; color: var(--bt-text-2); margin-bottom: 6px; }
.combo-grid { display: flex; flex-direction: column; gap: 8px; }
.combo-card { border: 1px solid var(--bt-border); border-radius: var(--bt-r-md); padding: 10px 12px; background: var(--bt-subtle); }
.combo-card.best { border-color: var(--bt-brand); background: var(--bt-brand-soft); }
.combo-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.combo-badge { font-size: 12px; font-weight: 700; color: var(--bt-brand); display: flex; align-items: center; gap: 6px; }
.best-tag { font-size: 9px; padding: 1px 4px; background: var(--bt-brand); color: #fff; border-radius: 3px; }
.combo-total { font-size: 13px; font-weight: 800; color: var(--bt-brand); }
.combo-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
.combo-list li { display: flex; justify-content: space-between; gap: 8px; font-size: 11px; color: var(--bt-text-2); }
.cb-slot { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cb-price { color: var(--bt-text-2); flex-shrink: 0; }

/* notes */
.notes { display: flex; flex-direction: column; gap: 4px; }
.note { display: flex; align-items: flex-start; gap: 6px; font-size: 11px; color: var(--bt-text-2); line-height: 1.5; }
.note-dot { width: 5px; height: 5px; margin-top: 6px; border-radius: 50%; background: var(--bt-warn); flex-shrink: 0; }
</style>
