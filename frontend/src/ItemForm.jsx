import { useState } from 'react'

const EMPTY = { sku: '', l: '', w: '', h: '', weight_g: '', orientation: 'any', qty: 1 }

export default function ItemForm({ onAdd }) {
  const [row, setRow] = useState(EMPTY)
  const [error, setError] = useState('')

  const set = (k) => (e) => setRow({ ...row, [k]: e.target.value })

  const submit = (e) => {
    e.preventDefault()
    const l = Number(row.l); const w = Number(row.w); const h = Number(row.h)
    const weight_g = Number(row.weight_g); const qty = Number(row.qty)
    if (!row.sku.trim()) return setError('请填写商品 SKU')
    if (!(l > 0 && w > 0 && h > 0)) return setError('长宽高必须为正整数（毫米）')
    if (!Number.isInteger(l) || !Number.isInteger(w) || !Number.isInteger(h)) {
      return setError('尺寸必须为整数毫米')
    }
    if (!(weight_g > 0) || !Number.isInteger(weight_g)) return setError('重量必须为正整数（克）')
    if (!(qty > 0) || !Number.isInteger(qty)) return setError('数量必须为正整数')
    onAdd({ sku: row.sku.trim(), l, w, h, weight_g, orientation: row.orientation, qty })
    setRow({ ...EMPTY, sku: '' })
    setError('')
  }

  return (
    <form className="card item-form" onSubmit={submit}>
      <h3>添加商品</h3>
      <div className="grid">
        <label>SKU
          <input value={row.sku} onChange={set('sku')} placeholder="如 A001" />
        </label>
        <label>长 mm
          <input type="number" min="1" step="1" value={row.l} onChange={set('l')} />
        </label>
        <label>宽 mm
          <input type="number" min="1" step="1" value={row.w} onChange={set('w')} />
        </label>
        <label>高 mm
          <input type="number" min="1" step="1" value={row.h} onChange={set('h')} />
        </label>
        <label>重量 g
          <input type="number" min="1" step="1" value={row.weight_g} onChange={set('weight_g')} />
        </label>
        <label>数量
          <input type="number" min="1" step="1" value={row.qty} onChange={set('qty')} />
        </label>
        <label>朝向限制
          <select value={row.orientation} onChange={set('orientation')}>
            <option value="any">六种朝向（可翻转）</option>
            <option value="upright">保持直立（仅水平转 90°）</option>
          </select>
        </label>
      </div>
      {error && <div className="error">{error}</div>}
      <button type="submit" className="primary">添加到订单</button>
    </form>
  )
}
