// Diagram rendering composable.
//
// Extracted from App.vue's <script setup> (former lines 1961-2159) while preserving identical behavior:
// - PlantUML: encode the source with plantuml-encoder and render SVG via an online service
// - Mermaid: rendered in the browser via the mermaid library (returns placeholder HTML, then renders asynchronously after DOM insertion)
// - dot/Graphviz: rendered in the browser via d3-graphviz (returns placeholder HTML, then renders asynchronously after DOM insertion)
//
// No Vue reactivity dependencies (pure functions + module-level counters); the caller destructures directly:
//   const { renderPlantUmlBlock, renderDotBlock, renderMermaidBlock, ... } = useDiagramRender()

import plantumlEncoder from 'plantuml-encoder'
import mermaid from 'mermaid'
import { graphviz } from 'd3-graphviz'
import { escapeHtml } from '../diffRenderer.js'

const PLANTUML_SERVER_URL = 'https://www.plantuml.com/plantuml/svg/'
const PLANTUML_BLOCK_LANGUAGE = 'plantuml'
const MERMAID_BLOCK_LANGUAGE = 'mermaid'
const DOT_BLOCK_LANGUAGES = ['dot', 'graphviz']

// Mermaid render counter for generating unique IDs
let mermaidRenderCounter = 0
// Dot render counter for generating unique IDs
let dotRenderCounter = 0

// Initialize Mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
  fontFamily: 'inherit'
})

export function useDiagramRender() {
  function encodePlantUmlText(plantUmlSource) {
    return plantumlEncoder.encode(String(plantUmlSource || '').trim())
  }

  function isPlantUmlLanguage(language) {
    return String(language || '').trim().toLowerCase() === PLANTUML_BLOCK_LANGUAGE
  }

  /**
   * Check whether the PlantUML code is complete (contains the @startuml and @enduml markers)
   * @param {string} source - PlantUML source code
   * @returns {boolean} - true if complete
   */
  function isPlantUmlComplete(source) {
    const trimmedSource = String(source || '').trim()
    const lowerSource = trimmedSource.toLowerCase()
    return lowerSource.includes('@startuml') && lowerSource.includes('@enduml')
  }

  function renderPlantUmlBlock(plantUmlSource) {
    const trimmedSource = String(plantUmlSource || '').trim()
    if (!trimmedSource) {
      return '<pre><code class="language-plantuml"></code></pre>'
    }

    // Check the PlantUML code for completeness; skip remote rendering when incomplete
    if (!isPlantUmlComplete(trimmedSource)) {
      return `<pre><code class="language-plantuml">${escapeHtml(trimmedSource)}</code></pre>`
    }

    try {
      const escapedSource = escapeHtml(trimmedSource)
      const encodedSource = encodePlantUmlText(trimmedSource)
      const plantUmlUrl = `${PLANTUML_SERVER_URL}${encodedSource}`

      return [
        '<div class="plantuml-block">',
        '  <div class="plantuml-notice">',
        '    The frontend renders PlantUML via an online service; if the image fails to load, expand to view the source.',
        '  </div>',
        `  <a class="plantuml-link" href="${plantUmlUrl}" target="_blank" rel="noopener noreferrer">`,
        `    <img class="plantuml-image" src="${plantUmlUrl}" alt="PlantUML diagram" loading="lazy" />`,
        '  </a>',
        '  <details class="plantuml-source">',
        '    <summary>View PlantUML source</summary>',
        `    <pre><code class="language-plantuml">${escapedSource}</code></pre>`,
        '  </details>',
        '</div>'
      ].join('\n')
    } catch (error) {
      console.error('[PlantUML] Failed to render PlantUML block:', error)
      return `<pre><code class="language-plantuml">${escapeHtml(trimmedSource)}</code></pre>`
    }
  }

  function isDotLanguage(language) {
    return DOT_BLOCK_LANGUAGES.includes(String(language || '').trim().toLowerCase())
  }

  function isMermaidLanguage(language) {
    return String(language || '').trim().toLowerCase() === MERMAID_BLOCK_LANGUAGE
  }

  /**
   * Render a dot/Graphviz code block
   * Rendered in the browser via d3-graphviz
   */
  function renderDotBlock(dotSource) {
    const trimmedSource = String(dotSource || '').trim()
    if (!trimmedSource) {
      return '<pre><code class="language-dot"></code></pre>'
    }

    const id = `dot-diagram-${++dotRenderCounter}`
    const escapedSource = escapeHtml(trimmedSource)

    // Return placeholder HTML; renderDotDiagrams renders it asynchronously after DOM insertion
    return [
      '<div class="diagram-block">',
      '  <div class="diagram-notice">',
      '    Graphviz diagram (rendered in the browser).',
      '  </div>',
      `  <div class="dot-container" data-dot-id="${id}" data-dot-source="${encodeURIComponent(trimmedSource)}">`,
      '    <div class="dot-loading">Rendering...</div>',
      '  </div>',
      '  <details class="diagram-source">',
      '    <summary>View dot source</summary>',
      `    <pre><code class="language-dot">${escapedSource}</code></pre>`,
      '  </details>',
      '</div>'
    ].join('\n')
  }

  /**
   * Render a Mermaid code block
   * Rendered in the browser via the mermaid library
   */
  function renderMermaidBlock(mermaidSource) {
    const trimmedSource = String(mermaidSource || '').trim()
    if (!trimmedSource) {
      return '<pre><code class="language-mermaid"></code></pre>'
    }

    const id = `mermaid-diagram-${++mermaidRenderCounter}`
    const escapedSource = escapeHtml(trimmedSource)

    // Return placeholder HTML; renderMermaidDiagrams renders it asynchronously after DOM insertion
    return [
      '<div class="diagram-block">',
      '  <div class="diagram-notice">',
      '    Mermaid diagram (rendered in the browser).',
      '  </div>',
      `  <div class="mermaid-container" data-mermaid-id="${id}" data-mermaid-source="${encodeURIComponent(trimmedSource)}">`,
      '    <div class="mermaid-loading">Rendering...</div>',
      '  </div>',
      '  <details class="diagram-source">',
      '    <summary>View Mermaid source</summary>',
      `    <pre><code class="language-mermaid">${escapedSource}</code></pre>`,
      '  </details>',
      '</div>'
    ].join('\n')
  }

  /**
   * Asynchronously render all unrendered Mermaid diagrams on the page
   * Called after message content updates
   */
  async function renderMermaidDiagrams(containerEl) {
    if (!containerEl) return
    const elements = containerEl.querySelectorAll('.mermaid-container[data-mermaid-source]')
    for (const el of elements) {
      const source = decodeURIComponent(el.getAttribute('data-mermaid-source') || '')
      const id = el.getAttribute('data-mermaid-id') || 'mermaid-diagram'
      if (!source) continue

      try {
        const { svg } = await mermaid.render(id, source)
        el.innerHTML = svg
        el.removeAttribute('data-mermaid-source')
      } catch (error) {
        console.error('[Mermaid] Failed to render diagram:', error)
        el.innerHTML = `<pre><code class="language-mermaid">${escapeHtml(source)}</code></pre>`
        el.removeAttribute('data-mermaid-source')
      }
    }
  }

  /**
   * Asynchronously render all unrendered dot/Graphviz diagrams on the page
   * Called after message content updates
   */
  async function renderDotDiagrams(containerEl) {
    if (!containerEl) return
    const elements = containerEl.querySelectorAll('.dot-container[data-dot-source]')
    for (const el of elements) {
      const source = decodeURIComponent(el.getAttribute('data-dot-source') || '')
      if (!source) continue

      try {
        await new Promise((resolve, reject) => {
          graphviz(el, { useWorker: false })
            .renderDot(source)
            .on('end', resolve)
            .on('error', reject)
        })
        el.removeAttribute('data-dot-source')
      } catch (error) {
        console.error('[Dot] Failed to render diagram:', error)
        el.innerHTML = `<pre><code class="language-dot">${escapeHtml(source)}</code></pre>`
        el.removeAttribute('data-dot-source')
      }
    }
  }

  return {
    encodePlantUmlText,
    isPlantUmlLanguage,
    isPlantUmlComplete,
    renderPlantUmlBlock,
    isDotLanguage,
    isMermaidLanguage,
    renderDotBlock,
    renderMermaidBlock,
    renderMermaidDiagrams,
    renderDotDiagrams,
  }
}
