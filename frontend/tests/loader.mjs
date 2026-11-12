// Node module hooks: JSX transform via esbuild + BoxViewer stub (no WebGL in jsdom)
import esbuild from 'esbuild'
import { pathToFileURL } from 'node:url'

export async function resolve(specifier, context, nextResolve) {
  if (specifier.endsWith('BoxViewer') || specifier.endsWith('BoxViewer.jsx')) {
    return {
      url: new URL('./BoxViewerStub.jsx', import.meta.url).href,
      shortCircuit: true,
    }
  }
  return nextResolve(specifier, context)
}

export async function load(url, context, nextLoad) {
  if (url.endsWith('.jsx') || url.includes('/tests/') && url.endsWith('.test.mjs')) {
    const result = await nextLoad(url, { ...context, format: 'module' })
    const code = result.source.toString()
    const transformed = await esbuild.transform(code, {
      loader: 'jsx',
      jsx: 'automatic',
      format: 'esm',
    })
    return { format: 'module', shortCircuit: true, source: transformed.code }
  }
  return nextLoad(url, context)
}

export const registerURL = pathToFileURL('./tests/loader.mjs').href
