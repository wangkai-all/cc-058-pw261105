import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import ItemForm from './ItemForm'
import ItemTable from './ItemTable'
import Catalog from './Catalog'
import Results from './Results'

export default function App() {
  const [boxes, setBoxes] = useState([])
  const [plans, setPlans] = useState([])
  const [items, setItems] = useState([])
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [maxBoxes, setMaxBoxes] = useState(12)

  useEffect(() => {
    api.listBoxes().then(setBoxes).catch((e) => setError(e.message))
    api.listPlans().then(setPlans).catch((e) => setError(e.message))
  }, [])

  const boxesById = useMemo(() => new Map(boxes.map((b) => [b.id, b])), [boxes])

  const addItem = (item) => {
    setItems((prev) => {
      const existing = prev.find((x) => x.sku === item.sku)
      if (existing) {
        return prev.map((x) => x.sku === item.sku
          ? { ...x, qty: x.qty + item.qty } : x)
      }
      return [...prev, item]
    })
  }

  const solve = async () => {
    if (!items.length) {
      setError('请先添加订单商品')
      return
    }
    setLoading(true); setError(''); setResult(null)
    try {
      const res = await api.solve({ items, max_boxes: maxBoxes, candidate_limit: 40 })
      setResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const addBox = async (data) => {
    try {
      const created = await api.createBox(data)
      setBoxes((prev) => [...prev, created])
    } catch (e) {
      setError(e.message)
    }
  }

  const addPlan = async (data) => {
    try {
      const created = await api.createPlan(data)
      setPlans((prev) => [...prev, created])
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="page">
      <header>
        <h1>装箱运费规划器</h1>
        <p className="assumptions">
          简化条件：仅处理<strong>轴向摆放</strong>的长方体（边与箱边平行）；商品之间不可重叠、不可超出箱体内尺寸；
          「保持直立」商品只能在水平面转 90°，其他商品允许六种朝向；
          <strong>不考虑支撑力、易碎要求与填充空隙</strong>。求解使用启发式算法，不保证全局最低价；
          输出结果已经独立校验程序复核数量、朝向、坐标、毛重与费用。
        </p>
      </header>

      {error && <div className="error global-error">{error}</div>}

      <div className="layout">
        <section className="left-col">
          <ItemForm onAdd={addItem} />
          <ItemTable
            items={items}
            onRemove={(sku) => setItems(items.filter((x) => x.sku !== sku))}
            onClear={() => setItems([])}
          />
          <div className="card solve-bar">
            <label>最多使用箱数
              <input type="number" min="1" max="60" value={maxBoxes}
                onChange={(e) => setMaxBoxes(Number(e.target.value))} />
            </label>
            <button className="primary big-btn" onClick={solve} disabled={loading}>
              {loading ? '求解中…' : '试装箱并计算运费'}
            </button>
          </div>
        </section>

        <section className="right-col">
          <Catalog boxes={boxes} plans={plans} onAddBox={addBox} onAddPlan={addPlan} />
        </section>
      </div>

      {result && <Results result={result} boxesById={boxesById} />}

      <footer className="muted">
        尺寸单位毫米（整数），重量单位克。体积重量按箱<strong>外尺寸</strong>计算，
        与毛重取较大值后向上取整到计费步长，再加箱费。
      </footer>
    </div>
  )
}
