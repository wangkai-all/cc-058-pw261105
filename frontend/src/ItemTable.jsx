export default function ItemTable({ items, onRemove, onClear }) {
  if (!items.length) return <p className="muted">订单还没有商品。</p>
  return (
    <div className="card">
      <h3>订单商品（{items.reduce((s, i) => s + i.qty, 0)} 件）</h3>
      <table>
        <thead>
          <tr>
            <th>SKU</th><th>长</th><th>宽</th><th>高</th><th>重量 g</th>
            <th>朝向</th><th>数量</th><th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={it.sku}>
              <td>{it.sku}</td>
              <td>{it.l}</td><td>{it.w}</td><td>{it.h}</td><td>{it.weight_g}</td>
              <td>{it.orientation === 'upright' ? '保持直立' : '六种朝向'}</td>
              <td>{it.qty}</td>
              <td><button className="link" onClick={() => onRemove(it.sku)}>移除</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className="link" onClick={onClear}>清空订单</button>
    </div>
  )
}
