/** 整数金额去掉 .00，非整数保留两位；接口给的是字符串。 */
export function moneyText(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) {
    return '—'
  }
  return Number.isInteger(num) ? String(num) : num.toFixed(2)
}
