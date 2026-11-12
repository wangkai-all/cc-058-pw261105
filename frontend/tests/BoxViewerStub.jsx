export default function BoxViewerStub({ box }) {
  return (
    <div data-testid="box-viewer-stub" data-box-code={box?.box_code ?? ''} />
  )
}
