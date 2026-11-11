/**
 * 结算页的幂等键：进页面生成一次，下单成功后换新的。
 * 提交失败时保留原值，让"其实已经落库但响应丢了"的那次重试被服务端识别为重放。
 */
export function newClientToken() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID().replaceAll('-', '')
  }
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`
}
