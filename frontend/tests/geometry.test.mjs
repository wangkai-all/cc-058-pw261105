import test from 'node:test'
import assert from 'node:assert/strict'
import { toThreeSize, toThreePosition, placementAABB } from '../src/geometry.js'

test('API -> Three size swaps y/z so height maps to Three y', () => {
  const p = { dx: 120, dy: 100, dz: 80, x: 0, y: 0, z: 0 }
  assert.deepEqual(toThreeSize(p), [120, 80, 100])
})

test('API -> Three position swaps y/z and centres the geometry', () => {
  const p = { dx: 120, dy: 100, dz: 80, x: 10, y: 20, z: 30 }
  // three: (x+dx/2, z+dz/2, y+dy/2)
  assert.deepEqual(toThreePosition(p), [70, 70, 70])
})

test('AABB stays inside the box inner dimensions for a full-size placement', () => {
  const inner = { inner_l: 300, inner_w: 220, inner_h: 200 }
  const p = { dx: 300, dy: 220, dz: 200, x: 0, y: 0, z: 0 }
  const { min, max } = placementAABB(p)
  assert.deepEqual(min, [0, 0, 0])
  assert.deepEqual(max, [inner.inner_l, inner.inner_h, inner.inner_w])
})

test('two mapped AABBs do not overlap when API boxes are axis-disjoint', () => {
  // two 100 cubes side by side along API x inside a 300 box
  const a = placementAABB({ dx: 100, dy: 100, dz: 100, x: 0, y: 0, z: 0 })
  const b = placementAABB({ dx: 100, dy: 100, dz: 100, x: 100, y: 0, z: 0 })
  const overlap = !(
    a.max[0] <= b.min[0] || b.max[0] <= a.min[0] ||
    a.max[1] <= b.min[1] || b.max[1] <= a.min[1] ||
    a.max[2] <= b.min[2] || b.max[2] <= a.min[2]
  )
  assert.equal(overlap, false)
})

test('mapped AABBs overlap when source boxes genuinely overlap', () => {
  const a = placementAABB({ dx: 100, dy: 100, dz: 100, x: 0, y: 0, z: 0 })
  const b = placementAABB({ dx: 100, dy: 100, dz: 100, x: 50, y: 0, z: 0 })
  const overlap = !(
    a.max[0] <= b.min[0] || b.max[0] <= a.min[0] ||
    a.max[1] <= b.min[1] || b.max[1] <= a.min[1] ||
    a.max[2] <= b.min[2] || b.max[2] <= a.min[2]
  )
  assert.equal(overlap, true)
})
