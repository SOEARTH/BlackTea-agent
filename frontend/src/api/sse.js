/**
 * SSE 客户端：用 fetch + ReadableStream 手动解析 Server-Sent Events。
 *
 * 原生 EventSource 只支持 GET，我们的 /api/chat 是 POST，
 * 所以用 fetch streaming 手动解析 SSE 协议帧。
 */

/**
 * 发起 SSE POST 请求，逐事件回调。
 *
 * @param {string} url — 请求地址
 * @param {object} body — JSON body
 * @param {function} onEvent — 回调 (event: string, data: object) => void
 * @returns {Promise<void>}
 */
export async function postSSE(url, body, onEvent) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${resp.statusText}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // SSE 帧以双换行分隔，每帧含 event: 和 data: 行
    const frames = buffer.split('\n\n')
    buffer = frames.pop() // 最后一段可能不完整，留着继续拼

    for (const frame of frames) {
      const event = parseSSEFrame(frame)
      if (event) {
        onEvent(event.event, event.data)
      }
    }
  }

  // 处理最后残留的 buffer
  if (buffer.trim()) {
    const event = parseSSEFrame(buffer)
    if (event) {
      onEvent(event.event, event.data)
    }
  }
}

/**
 * 解析单个 SSE 帧。
 * 格式：event: xxx\ndata: {"key":"val"}\n
 */
function parseSSEFrame(frame) {
  let eventType = 'message'
  let dataStr = ''

  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataStr += line.slice(5).trim()
    }
  }

  if (!dataStr) return null

  try {
    return { event: eventType, data: JSON.parse(dataStr) }
  } catch {
    return { event: eventType, data: { raw: dataStr } }
  }
}
