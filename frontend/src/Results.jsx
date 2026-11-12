import { useMemo, useState } from 'react'
import BoxViewer from './BoxViewer.jsx'

function fmtKg(g) {
  return `${(g / 1000).toFixed(2)} kg`
}

function QuotePanel({ quote, boxesById }) {
  const [activeBox, setActiveBox] = useState(0)
  const box = quote.boxes[activeBox]
  const dims = boxesById.get(box.box_type_id)

  return (
    <div>
      <div className="summary-row">
        <div><span className="muted">总费用</span><strong className="big"> ¥{quote.total_fee.toFixed(2)}</strong></div>
        <div><span className="muted">运费合计</span> ¥{quote.total_freight.toFixed(2)}</div>
        <div><span className="muted">箱费合计</span> ¥{quote.total_box_fee.toFixed(2)}</div>
        <div><span className="muted">箱数</span> {quote.boxes.length}</div>
      </div>

      <div className="box-tabs">
        {quote.boxes.map((b, i) => (
          <button key={i} className={i === activeBox ? 'active' : ''} onClick={() => setActiveBox(i)}>
            {b.box_code}（{b.placements.length} 件）
          </button>
        ))}
      </div>

      <div className="viewer-layout">
        <BoxViewer box={box} dims={dims} />
        <div className="card fee-detail">
          <h4>{box.box_code} 费用明细</h4>
          <table>
            <tbody>
              <tr><td>外尺寸体积</td><td>{box.outer_volume_mm3.toLocaleString()} mm³</td></tr>
              <tr><td>体积重量（外尺寸÷除数，向上取整）</td><td>{fmtKg(box.volumetric_weight_g)}</td></tr>
              <tr><td>毛重（商品 {box.item_weight_g}g + 箱重）</td><td>{fmtKg(box.gross_weight_g)}</td></tr>
              <tr><td>两者取大 → 向上取整到计费步长</td><td><strong>{fmtKg(box.chargeable_weight_g)}</strong></td></tr>
              <tr><td>运费</td><td>¥{box.freight_fee.toFixed(2)}</td></tr>
              <tr><td>箱费</td><td>¥{box.box_fee.toFixed(2)}</td></tr>
              <tr className="total-row"><td>本箱合计</td><td>¥{box.total_fee.toFixed(2)}</td></tr>
            </tbody>
          </table>
          <h4>摆放清单</h4>
          <table>
            <thead><tr><th>SKU</th><th>朝向尺寸 dx×dy×dz</th><th>坐标 (x,y,z)</th></tr></thead>
            <tbody>
              {box.placements.map((p, i) => (
                <tr key={i}>
                  <td>{p.sku}</td>
                  <td>{p.dx}×{p.dy}×{p.dz}</td>
                  <td>({p.x}, {p.y}, {p.z})</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default function Results({ result, boxesById }) {
  const [planId, setPlanId] = useState(null)
  const activeQuote = useMemo(() => {
    if (!result.quotes.length) return null
    const q = result.quotes.find((x) => x.freight_plan_id === planId) || result.quotes[0]
    return q
  }, [result, planId])

  return (
    <div className="card">
      <h3>求解结果</h3>

      <div className={`validator ${result.validator_passed ? 'ok' : 'bad'}`}>
        {result.validator_passed
          ? '✓ 独立校验通过：数量、朝向、坐标、毛重与费用均已复核'
          : `✗ 独立校验未通过：${result.validator_errors.join('；')}`}
      </div>

      {!!result.warnings.length && (
        <div className="warnings">
          {result.warnings.map((w, i) => <div key={i}>💡 {w}</div>)}
        </div>
      )}

      {!!result.unpacked.length && (
        <div className="unpacked">
          <h4>未能装箱的商品</h4>
          <table>
            <thead><tr><th>SKU</th><th>数量</th><th>判定</th><th>说明</th></tr></thead>
            <tbody>
              {result.unpacked.map((u, i) => (
                <tr key={i}>
                  <td>{u.sku}</td><td>{u.qty}</td>
                  <td>
                    {u.reason === 'exceeds_all_boxes'
                      ? <span className="badge bad">确定超出所有箱型限制</span>
                      : <span className="badge warn">算法暂未找到方案（不代表一定无解）</span>}
                  </td>
                  <td>{u.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!!result.quotes.length && (
        <>
          <h4>运费方案对比（各自独立计费）</h4>
          <div className="plan-tabs">
            {result.quotes.map((q) => (
              <button key={q.freight_plan_id}
                className={activeQuote && q.freight_plan_id === activeQuote.freight_plan_id ? 'active' : ''}
                onClick={() => setPlanId(q.freight_plan_id)}>
                {q.freight_plan_code}
                {result.cheapest_freight_plan_code === q.freight_plan_code && ' ★最低'}
                <div className="tab-fee">¥{q.total_fee.toFixed(2)}</div>
              </button>
            ))}
          </div>
          {activeQuote && <QuotePanel quote={activeQuote} boxesById={boxesById} />}

          <h4>候选装箱组合 × 各方案总价</h4>
          <table>
            <thead>
              <tr>
                <th>组合</th><th>箱数</th><th>总毛重 g</th><th>箱费合计</th>
                {result.quotes.map((q) => <th key={q.freight_plan_id}>{q.freight_plan_code}</th>)}
              </tr>
            </thead>
            <tbody>
              {result.packings.map((p) => (
                <tr key={p.packing_index}>
                  <td>{p.box_codes.join(' + ')}</td>
                  <td>{p.n_boxes}</td>
                  <td>{p.total_gross_weight_g}</td>
                  <td>¥{p.total_box_fee.toFixed(2)}</td>
                  {result.quotes.map((q) => (
                    <td key={q.freight_plan_id}>¥{p.plan_total_fees[q.freight_plan_code].toFixed(2)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
