import test from 'node:test'
import assert from 'node:assert/strict'
import { createRoot } from 'react-dom/client'
import { act } from 'react'
import React from 'react'
import ItemForm from '../src/ItemForm.jsx'
import ItemTable from '../src/ItemTable.jsx'

function render(node) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  act(() => root.render(node))
  return container
}

function setValue(input, value) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  setter.call(input, String(value))
  input.dispatchEvent(new window.Event('input', { bubbles: true }))
}

test('ItemForm rejects non-integer millimetre dimensions', () => {
  let added = null
  const container = render(<ItemForm onAdd={(it) => { added = it }} />)
  const inputs = container.querySelectorAll('input')
  // [sku, l, w, h, weight, qty] + select
  setValue(inputs[0], 'A1')
  setValue(inputs[1], 120.5)
  setValue(inputs[2], 100)
  setValue(inputs[3], 80)
  setValue(inputs[4], 700)
  setValue(inputs[5], 2)
  act(() => container.querySelector('form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true })))
  assert.ok(container.textContent.includes('整数毫米'))
  assert.equal(added, null)
})

test('ItemForm emits a valid item and table shows total quantity', () => {
  const added = []
  const formContainer = render(<ItemForm onAdd={(it) => added.push(it)} />)
  const inputs = formContainer.querySelectorAll('input')
  setValue(inputs[0], 'A1')
  setValue(inputs[1], 120); setValue(inputs[2], 100); setValue(inputs[3], 80)
  setValue(inputs[4], 700); setValue(inputs[5], 3)
  act(() => formContainer.querySelector('form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true })))
  assert.deepEqual(added[0], { sku: 'A1', l: 120, w: 100, h: 80, weight_g: 700, orientation: 'any', qty: 3 })

  const tableContainer = render(<ItemTable items={added} onRemove={() => {}} onClear={() => {}} />)
  assert.ok(tableContainer.textContent.includes('3 件'))
  assert.ok(tableContainer.textContent.includes('六种朝向'))
})

test('ItemTable labels upright orientation in Chinese', () => {
  const container = render(
    <ItemTable
      items={[{ sku: 'U', l: 60, w: 60, h: 180, weight_g: 250, orientation: 'upright', qty: 1 }]}
      onRemove={() => {}} onClear={() => {}}
    />
  )
  assert.ok(container.textContent.includes('保持直立'))
})
