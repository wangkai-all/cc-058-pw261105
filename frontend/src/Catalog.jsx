import { useState } from 'react'

const BOX_EMPTY = {
  code: '', name: '', inner_l: '', inner_w: '', inner_h: '',
  outer_l: '', outer_w: '', outer_h: '',
  box_weight_g: '', box_fee: '', max_gross_g: '',
}
const PLAN_EMPTY = {
  code: '', name: '', vol_divisor: 6000, unit: 'g',
  billing_step_g: 1000, price_per_step: '',
}

export default function Catalog({ boxes, plans, onAddBox, onAddPlan }) {
  const [tab, setTab] = useState('boxes')
  const [boxRow, setBoxRow] = useState(BOX_EMPTY)
  const [planRow, setPlanRow] = useState(PLAN_EMPTY)
  const [error, setError] = useState('')

  const setB = (k) => (e) => setBoxRow({ ...boxRow, [k]: e.target.value })
  const setP = (k) => (e) => setPlanRow({ ...planRow, [k]: e.target.value })

  const submitBox = (e) => {
    e.preventDefault()
    const ints = ['inner_l', 'inner_w', 'inner_h', 'outer_l', 'outer_w', 'outer_h',
      'box_weight_g', 'max_gross_g']
    const payload = { ...boxRow }
    for (const k of ints) {
      const v = Number(payload[k])
      if (!Number.isInteger(v) || v <= 0) {
        setError('尺寸/重量/毛重必须为正整数')
        return
      }
      payload[k] = v
    }
    payload.box_fee = Number(payload.box_fee)
    if (!(payload.box_fee >= 0)) return setError('箱费需为非负数')
    if (payload.outer_l < payload.inner_l || payload.outer_w < payload.inner_w
      || payload.outer_h < payload.inner_h) {
      return setError('外尺寸不能小于内尺寸')
    }
    if (!payload.code.trim()) return setError('请填写箱型编号')
    onAddBox(payload)
    setBoxRow(BOX_EMPTY)
    setError('')
  }

  const submitPlan = (e) => {
    e.preventDefault()
    const payload = { ...planRow }
    for (const k of ['vol_divisor', 'billing_step_g']) {
      const v = Number(payload[k])
      if (!Number.isInteger(v) || v <= 0) return setError('除数与步长必须为正整数')
      payload[k] = v
    }
    payload.price_per_step = Number(payload.price_per_step)
    if (!(payload.price_per_step > 0)) return setError('每步价格必须为正数')
    if (!payload.code.trim()) return setError('请填写方案编号')
    onAddPlan(payload)
    setPlanRow(PLAN_EMPTY)
    setError('')
  }

  return (
    <div className="card">
      <div className="tabs">
        <button className={tab === 'boxes' ? 'active' : ''} onClick={() => setTab('boxes')}>
          候选箱型（{boxes.length}）
        </button>
        <button className={tab === 'plans' ? 'active' : ''} onClick={() => setTab('plans')}>
          运费方案（{plans.length}）
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {tab === 'boxes' && (
        <>
          <table>
            <thead>
              <tr>
                <th>编号</th><th>名称</th><th>内尺寸 L×W×H (mm)</th>
                <th>外尺寸 L×W×H (mm)</th><th>箱重 g</th><th>箱费</th><th>最大毛重 g</th>
              </tr>
            </thead>
            <tbody>
              {boxes.map((b) => (
                <tr key={b.id} className={b.active ? '' : 'inactive'}>
                  <td>{b.code}</td><td>{b.name}</td>
                  <td>{b.inner_l}×{b.inner_w}×{b.inner_h}</td>
                  <td>{b.outer_l}×{b.outer_w}×{b.outer_h}</td>
                  <td>{b.box_weight_g}</td><td>{b.box_fee}</td><td>{b.max_gross_g}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <form className="compact-form" onSubmit={submitBox}>
            <h4>新增箱型（整数毫米）</h4>
            <div className="grid">
              <label>编号<input value={boxRow.code} onChange={setB('code')} /></label>
              <label>名称<input value={boxRow.name} onChange={setB('name')} /></label>
              <label>内 L<input type="number" value={boxRow.inner_l} onChange={setB('inner_l')} /></label>
              <label>内 W<input type="number" value={boxRow.inner_w} onChange={setB('inner_w')} /></label>
              <label>内 H<input type="number" value={boxRow.inner_h} onChange={setB('inner_h')} /></label>
              <label>外 L<input type="number" value={boxRow.outer_l} onChange={setB('outer_l')} /></label>
              <label>外 W<input type="number" value={boxRow.outer_w} onChange={setB('outer_w')} /></label>
              <label>外 H<input type="number" value={boxRow.outer_h} onChange={setB('outer_h')} /></label>
              <label>箱重 g<input type="number" value={boxRow.box_weight_g} onChange={setB('box_weight_g')} /></label>
              <label>箱费<input type="number" step="0.01" value={boxRow.box_fee} onChange={setB('box_fee')} /></label>
              <label>最大毛重 g<input type="number" value={boxRow.max_gross_g} onChange={setB('max_gross_g')} /></label>
            </div>
            <button className="primary" type="submit">添加箱型</button>
          </form>
        </>
      )}

      {tab === 'plans' && (
        <>
          <table>
            <thead>
              <tr>
                <th>编号</th><th>名称</th><th>体积重除数 (mm³/g)</th>
                <th>单位</th><th>计费步长 g</th><th>每步价格</th>
              </tr>
            </thead>
            <tbody>
              {plans.map((p) => (
                <tr key={p.id} className={p.active ? '' : 'inactive'}>
                  <td>{p.code}</td><td>{p.name}</td>
                  <td>{p.vol_divisor}</td><td>{p.unit}</td>
                  <td>{p.billing_step_g}</td><td>{p.price_per_step}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <form className="compact-form" onSubmit={submitPlan}>
            <h4>新增运费方案</h4>
            <div className="grid">
              <label>编号<input value={planRow.code} onChange={setP('code')} /></label>
              <label>名称<input value={planRow.name} onChange={setP('name')} /></label>
              <label>体积重除数<input type="number" value={planRow.vol_divisor} onChange={setP('vol_divisor')} /></label>
              <label>单位
                <select value={planRow.unit} onChange={setP('unit')}>
                  <option value="g">g</option><option value="kg">kg</option>
                </select>
              </label>
              <label>计费步长 g<input type="number" value={planRow.billing_step_g} onChange={setP('billing_step_g')} /></label>
              <label>每步价格<input type="number" step="0.01" value={planRow.price_per_step} onChange={setP('price_per_step')} /></label>
            </div>
            <button className="primary" type="submit">添加方案</button>
          </form>
        </>
      )}
    </div>
  )
}
