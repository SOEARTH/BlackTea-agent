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

  /**
   * 发送用户消息，启动 SSE 流。
   */
  async function sendMessage(text) {
    if (!text.trim() || streaming.value) return

    // 清理上一轮状态
    interrupt.value = null
    report.value = null
    agentTimeline.value = []
    streaming.value = true

    // 加入用户消息
    messages.value.push({ role: 'user', content: text })

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
        if (data.message) {
          messages.value.push({ role: 'ai', content: data.message, node: data.node })
        }
        break

      case 'interrupt':
        // clarify 触发 interrupt，弹窗等用户输入
        interrupt.value = {
          message: data.message,
          thread_id: data.thread_id,
        }
        threadId.value = data.thread_id
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
    sendMessage,
    resumeChat,
  }
})
