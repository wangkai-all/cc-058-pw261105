// Coordinate conventions shared by the 3D viewer and tests.
//
// API space (mm): x along box length L, y along box width W, z = height.
// Three.js space: y is up. So API z -> three y, API y -> three z.
// BoxGeometry is centred, so positions use the min corner plus half the size.

export function toThreeSize(placement) {
  return [placement.dx, placement.dz, placement.dy]
}

export function toThreePosition(placement) {
  return [
    placement.x + placement.dx / 2,
    placement.z + placement.dz / 2,
    placement.y + placement.dy / 2,
  ]
}

// Axis-aligned bounding box in Three space, returned as
// { min: [x,y,z], max: [x,y,z] }
export function placementAABB(placement) {
  const [sx, sy, sz] = toThreeSize(placement)
  const [cx, cy, cz] = toThreePosition(placement)
  return {
    min: [cx - sx / 2, cy - sy / 2, cz - sz / 2],
    max: [cx + sx / 2, cy + sy / 2, cz + sz / 2],
  }
}
