import test from 'node:test'
import assert from 'node:assert/strict'
import { createRoot } from 'react-dom/client'
import { act } from 'react'
import React from 'react'
import Results from '../src/Results.jsx'

const boxesById = new Map([
  [2, { id: 2, code: 'B2', inner_l: 300, inner_w: 220, inner_h: 200 }],
])

const result = {
  feasible: true,
  validator_passed: true,
  validator_errors: [],
  cheapest_freight_plan_code: 'STD',
  warnings: ['STD: 拆成 2 箱 S+S 总价 35.00，比最少 1 箱的 50.00 还便宜 —— 示例说明'],
  unpacked: [
    { sku: 'HUGE', qty: 2, reason: 'exceeds_all_boxes', detail: '放不进任何箱型' },
    { sku: 'TIGHT', qty: 50, reason: 'no_solution_found', detail: '算法暂未找到' },
  ],
  quotes: [
    {
      freight_plan_id: 1, freight_plan_code: 'STD',
      total_freight: 24, total_box_fee: 2, total_fee: 26,
      packing_index: 0,
      boxes: [{
        box_type_id: 2, box_code: 'B2',
        item_weight_g: 1200, gross_weight_g: 1520,
        outer_volume_mm3: 15316224, volumetric_weight_g: 2553,
        chargeable_weight_g: 2000, freight_fee: 24, box_fee: 2, total_fee: 26,
        freight_detail: {},
        placements: [
          { sku: 'A', box_index: 0, dx: 120, dy: 100, dz: 80, x: 0, y: 0, z: 0, rotation: [0, 1, 2] },
          { sku: 'U', box_index: 0, dx: 60, dy: 60, dz: 180, x: 120, y: 0, z: 0, rotation: [0, 1, 2] },
        ],
      }],
    },
    {
      freight_plan_id: 2, freight_plan_code: 'AIR',
      total_freight: 30, total_box_fee: 2, total_fee: 32,
      packing_index: 0,
      boxes: [{
        box_type_id: 2, box_code: 'B2',
        item_weight_g: 1200, gross_weight_g: 1520,
        outer_volume_mm3: 15316224, volumetric_weight_g: 3064,
        chargeable_weight_g: 2000, freight_fee: 30, box_fee: 2, total_fee: 32,
        freight_detail: {}, placements: [],
      }],
    },
  ],
  packings: [
    { packing_index: 0, n_boxes: 1, box_codes: ['B2'], total_gross_weight_g: 1520,
      total_box_fee: 2, plan_total_fees: { STD: 26, AIR: 32 } },
    { packing_index: 1, n_boxes: 2, box_codes: ['S', 'S'], total_gross_weight_g: 1500,
      total_box_fee: 3, plan_total_fees: { STD: 35, AIR: 40 } },
  ],
}

function render(node) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  act(() => root.render(node))
  return container
}

test('Results renders validation state, fees and both unpacked reason labels', () => {
  const container = render(<Results result={result} boxesById={boxesById} />)
  const text = container.textContent

  assert.ok(text.includes('独立校验通过'))
  assert.ok(text.includes('确定超出所有箱型限制'))
  assert.ok(text.includes('算法暂未找到方案'))
  assert.ok(text.includes('不代表一定无解'))
  assert.ok(text.includes('拆成 2 箱'))
  assert.ok(text.includes('¥26.00'))
  assert.ok(text.includes('¥32.00'))
  assert.ok(text.includes('STD'))
  assert.ok(text.includes('AIR'))
  assert.ok(text.includes('★最低'))
  // placement table content
  assert.ok(text.includes('120×100×80'))
  assert.ok(container.querySelector('[data-testid="box-viewer-stub"]'))
})

test('Results shows failed validator distinctly', () => {
  const bad = { ...result, validator_passed: false, validator_errors: ['overlap detected'] }
  const container = render(<Results result={bad} boxesById={boxesById} />)
  assert.ok(container.textContent.includes('独立校验未通过'))
  assert.ok(container.textContent.includes('overlap detected'))
})
