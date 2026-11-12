import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { toThreePosition, toThreeSize } from './geometry.js'

// Distinct, readable colors per SKU (cycled)
const PALETTE = [
  0x4f81bd, 0xc0504d, 0x9bbb59, 0x8064a2, 0x4bacc6,
  0xf79646, 0x2c7fb8, 0x7fcdbb, 0xedf8b1, 0xfc8d59,
]

function skuColor(sku, skuIndex) {
  if (skuIndex.has(sku)) return PALETTE[skuIndex.get(sku) % PALETTE.length]
  const idx = skuIndex.size
  skuIndex.set(sku, idx)
  return PALETTE[idx % PALETTE.length]
}

/**
 * Three.js viewer for one packed box.
 * props:
 *   box: { box_code, placements: [{sku,dx,dy,dz,x,y,z,rotation}] }
 *   dims: { inner_l, inner_w, inner_h } from the box type catalog
 */
export default function BoxViewer({ box, dims }) {
  const mountRef = useRef(null)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount || !dims) return undefined

    const width = mount.clientWidth
    const height = mount.clientHeight

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0xf7f8fa)

    const camera = new THREE.PerspectiveCamera(45, width / height, 1, 20000)
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.setSize(width, height)
    mount.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true

    // lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.65))
    const dir = new THREE.DirectionalLight(0xffffff, 0.9)
    dir.position.set(600, 900, 700)
    scene.add(dir)

    const group = new THREE.Group()
    scene.add(group)

    // wireframe box using INNER dimensions; origin at the min corner
    const { inner_l: L, inner_w: W, inner_h: H } = dims
    const boxGeo = new THREE.BoxGeometry(L, H, W)
    const edges = new THREE.EdgesGeometry(boxGeo)
    const frame = new THREE.LineSegments(
      edges,
      new THREE.LineBasicMaterial({ color: 0x333333, linewidth: 2 })
    )
    frame.position.set(L / 2, H / 2, W / 2)
    group.add(frame)

    // ground grid on the box floor (XZ plane at y=0 is already the floor:
    // Three y = API z = vertical height axis)
    const grid = new THREE.GridHelper(Math.max(L, W), 10, 0xcccccc, 0xe2e2e2)
    grid.position.set(L / 2, 0.1, W / 2)
    group.add(grid)

    // placements
    const skuIndex = new Map()
    for (const p of box.placements) {
      const color = skuColor(p.sku, skuIndex)
      const [gx, gy, gz] = toThreeSize(p)
      const geo = new THREE.BoxGeometry(gx, gy, gz)
      const mat = new THREE.MeshStandardMaterial({
        color,
        transparent: true,
        opacity: 0.82,
        roughness: 0.55,
        metalness: 0.05,
      })
      const mesh = new THREE.Mesh(geo, mat)
      mesh.position.set(...toThreePosition(p))
      const edgeLine = new THREE.LineSegments(
        new THREE.EdgesGeometry(geo),
        new THREE.LineBasicMaterial({ color: 0x222222 })
      )
      mesh.add(edgeLine)
      group.add(mesh)
    }

    // frame the whole box
    const center = new THREE.Vector3(L / 2, H / 2, W / 2)
    const span = Math.max(L, W, H)
    camera.position.set(center.x + span * 1.1, center.y + span * 0.9, center.z + span * 1.2)
    controls.target.copy(center)
    controls.update()

    let raf
    const animate = () => {
      raf = requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    const handleResize = () => {
      const w = mount.clientWidth
      const h = mount.clientHeight
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    window.addEventListener('resize', handleResize)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', handleResize)
      controls.dispose()
      renderer.dispose()
      scene.traverse((obj) => {
        if (obj.geometry) obj.geometry.dispose()
        if (obj.material) {
          if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose())
          else obj.material.dispose()
        }
      })
      mount.removeChild(renderer.domElement)
    }
  }, [box, dims])

  return <div ref={mountRef} style={{ width: '100%', height: 340, borderRadius: 8, overflow: 'hidden' }} />
}
