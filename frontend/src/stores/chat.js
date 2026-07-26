import { defineStore } from 'pinia'
import { ref } from 'vue'
import { postSSE } from '../api/sse'

/**
 * 聊天状态管理。
 *
 * 数据流：
 *   用户输入 → POST /api/chat → SSE 流 → onEvent 分发
 *   interrupt 暂停 → 用户补充 → POST /api/chat/resume → SSE 流
 *   reflect 通过 → report 事件 → 决策报告
 */
export const useChatStore = defineStore('chat', () => {
  // 对话消息列表（用户 + AI）
  const messages = ref([])
  // agent 执行轨迹（时间线）
  const agentTimeline = ref([])
  // 当前 interrupt 信息
  const interrupt = ref(null) // { message, thread_id }
  // 决策报告
  const report = ref(null)
  // 当前 thread_id
  const threadId = ref(null)
  // 是否正在流式加载
  const streaming = ref(false)
  // 当前活跃 agent 节点（顶栏 meta 用）
  const activeNode = ref('')
  // 反思轮次（reflect 打回计数）
  const iteration = ref(0)

  // ===== MOCK 模式（不连后端，本地模拟 SSE，验证 UI）=====
  // USE_MOCK = true  → 本地模拟事件流，不需要后端/网络
  // USE_MOCK = false → 走真实后端 POST /api/chat SSE
  const USE_MOCK = false
  const mockTimers = []
  function mockEmit(event, data, delay) {
    const t = setTimeout(() => handleEvent(event, data), delay)
    mockTimers.push(t)
  }
  function clearMock() {
    mockTimers.forEach((t) => clearTimeout(t))
    mockTimers.length = 0
  }
  function mockReport(tid) {
    const ap = (aspect, score, weight, evidence) => ({ aspect, score, weight, evidence })
    const mk = (title, dtitle, price) => ({ title, dtitle, price })
    const rec = (product, aspects, total, rank) => ({ product, aspects, total, rank })
    return {
      requirement: { category: '零食', budget: 30, scene: '肉类' },
      summary:
        '综合口碑、价格与销量，XX 猪肉脯综合分最高、预算内可入手；YY 牛肉粒次之，重口味可作替换方案',
      recommendations: [
        rec(
          mk('XX精选原味猪肉脯 200g', '猪肉脯', 19.9),
          [
            ap('price', 8.5, 0.30, '¥19.9，低于品类中位价约 13%'),
            ap('reputation', 8.8, 0.30, 'RAG 方面级聚合：口感8.6/复购8.4/售后9.1'),
            ap('sales', 7.5, 0.15, '近30天月销 2100+'),
            ap('coupon', 7.0, 0.15, '满20减3，券后 ¥17.9'),
            ap('brand', 6.5, 0.10, '新锐国货，认知度一般'),
          ],
          8.0, 1,
        ),
        rec(
          mk('YY沙嗲味牛肉粒 150g', '牛肉粒', 24.5),
          [
            ap('price', 7.0, 0.30, '¥24.5，近预算上限'),
            ap('reputation', 8.5, 0.30, '口感稳8.5，重口味好评多'),
            ap('sales', 8.0, 0.15, '月销 3200+'),
            ap('coupon', 7.5, 0.15, '满25减2'),
            ap('brand', 7.5, 0.10, '老牌肉企旗下'),
          ],
          7.6, 2,
        ),
        rec(
          mk('ZZ低脂鸡胸肉条 100g', '鸡胸肉条', 9.9),
          [
            ap('price', 9.2, 0.30, '¥9.9，远低于预算'),
            ap('reputation', 7.2, 0.30, '低脂健康但偏柴'),
            ap('sales', 6.8, 0.15, '月销 800+，偏小众'),
            ap('coupon', 6.0, 0.15, '无券'),
            ap('brand', 6.0, 0.10, '新品牌'),
          ],
          7.2, 3,
        ),
      ],
      combos: [
        [
          rec(mk('XX精选原味猪肉脯 200g', '猪肉脯', 19.9),
            [ap('price',8.5,0.3,''),ap('reputation',8.8,0.3,''),ap('sales',7.5,0.15,''),ap('coupon',7.0,0.15,''),ap('brand',6.5,0.1,'')], 8.0, 1),
          rec(mk('ZZ低脂鸡胸肉条 100g', '鸡胸肉条', 9.9),
            [ap('price',9.2,0.3,''),ap('reputation',7.2,0.3,''),ap('sales',6.8,0.15,''),ap('coupon',6.0,0.15,''),ap('brand',6.0,0.1,'')], 7.2, 3),
        ],
      ],
      reflection_notes: [
        '预算 30 元内：方案1合计 ¥29.8 合规',
        '当前价处近30天 20% 分位以下，判定为好价',
        '品类=肉类零食，硬需求已命中',
      ],
      created_at: new Date().toISOString(),
    }
  }
  async function runMockSend() {
    clearMock()
    const tid = 'mock-' + Date.now()
    threadId.value = tid
    mockEmit('agent', { node: 'clarify', message: '正在分析你的购物需求…' }, 600)
    mockEmit('interrupt', { message: '你的预算大概是多少？例如：50 元以内', thread_id: tid }, 1400)
    mockEmit('done', { thread_id: tid }, 1600)
    await new Promise((r) => setTimeout(r, 1700))
  }
  async function runMockResume(tid) {
    clearMock()
    mockEmit('agent', { node: 'clarify', message: '需求已明确，开始检索…' }, 400)
    mockEmit('agent', { node: 'search', message: '检索到 8 件候选商品', products_count: 8 }, 1500)
    mockEmit('agent', { node: 'price', message: '比价完成：当前价处于近30天低位' }, 2600)
    mockEmit('agent', { node: 'reputation', message: '方面级口碑聚合完成' }, 3300)
    mockEmit('agent', { node: 'scoring', message: '5 维加权打分排序完成', scored_count: 8 }, 4200)
    mockEmit('agent', { node: 'reflect', message: '反思通过：预算合规 · 好价 · 无硬需求遗漏' }, 5100)
    mockEmit('report', mockReport(tid), 5800)
    mockEmit('done', { thread_id: tid }, 6000)
    await new Promise((r) => setTimeout(r, 6100))
  }

  /**
   * 发送用户消息，启动 SSE 流。
   */
  async function sendMessage(text) {
    if (!text.trim() || streaming.value) return

    // 清理上一轮状态
    interrupt.value = null
    report.value = null
    agentTimeline.value = []
    activeNode.value = ''
    iteration.value = 0
    streaming.value = true

    // 加入用户消息
    messages.value.push({ role: 'user', content: text })

    if (USE_MOCK) {
      try { await runMockSend() } finally { streaming.value = false }
      return
    }

    try {
      await postSSE('/api/chat', {
        message: text,
        thread_id: threadId.value,
      }, handleEvent)
    } catch (e) {
      messages.value.push({ role: 'ai', content: `错误：${e.message}` })
    } finally {
      streaming.value = false
    }
  }

  /**
   * interrupt 恢复：用户补充信息后继续执行。
   */
  async function resumeChat(answer) {
    if (!answer.trim() || streaming.value || !interrupt.value) return

    const tid = interrupt.value.thread_id
    interrupt.value = null
    streaming.value = true

    // 加入用户回复
    messages.value.push({ role: 'user', content: answer })

    if (USE_MOCK) {
      const tid = threadId.value || 'mock-resume'
      try { await runMockResume(tid) } finally { streaming.value = false }
      return
    }

    try {
      await postSSE('/api/chat/resume', {
        answer: answer,
        thread_id: tid,
      }, handleEvent)
    } catch (e) {
      messages.value.push({ role: 'ai', content: `错误：${e.message}` })
    } finally {
      streaming.value = false
    }
  }

  /**
   * SSE 事件分发。
   */
  function handleEvent(event, data) {
    switch (event) {
      case 'agent':
        // agent 节点执行完成
      agentTimeline.value.push({
        node: data.node,
        message: data.message || '',
        timestamp: Date.now(),
      })
      activeNode.value = data.node
      if (typeof data.iteration === 'number') iteration.value = data.iteration
      if (data.message) {
        messages.value.push({ role: 'ai', content: data.message, node: data.node })
      }
        break

      case 'interrupt':
        // clarify 触发 interrupt：反问同步进对话流，内联 banner 提示用户补充
        interrupt.value = {
          message: data.message,
          thread_id: data.thread_id,
        }
        threadId.value = data.thread_id
        messages.value.push({ role: 'ai', content: data.message, node: 'clarify' })
        break

      case 'report':
        // 反思通过，决策报告
        report.value = data
        break

      case 'done':
        // 流结束
        threadId.value = data.thread_id
        break

      case 'error':
        messages.value.push({ role: 'ai', content: `错误：${data.message}` })
        break
    }
  }

  return {
    messages,
    agentTimeline,
    interrupt,
    report,
    threadId,
    streaming,
    activeNode,
    iteration,
    sendMessage,
    resumeChat,
  }
})
