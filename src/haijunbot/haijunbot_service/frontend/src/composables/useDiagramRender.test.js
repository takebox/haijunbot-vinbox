// useDiagramRender unit tests
import { describe, it, expect, vi } from 'vitest'
import { useDiagramRender } from './useDiagramRender.js'

function makeHarness() {
  return useDiagramRender()
}

describe('useDiagramRender', () => {
  it('exposes the expected API', () => {
    const api = makeHarness()
    expect(typeof api.encodePlantUmlText).toBe('function')
    expect(typeof api.isPlantUmlLanguage).toBe('function')
    expect(typeof api.isPlantUmlComplete).toBe('function')
    expect(typeof api.renderPlantUmlBlock).toBe('function')
    expect(typeof api.isDotLanguage).toBe('function')
    expect(typeof api.isMermaidLanguage).toBe('function')
    expect(typeof api.renderDotBlock).toBe('function')
    expect(typeof api.renderMermaidBlock).toBe('function')
    expect(typeof api.renderMermaidDiagrams).toBe('function')
    expect(typeof api.renderDotDiagrams).toBe('function')
  })

  describe('language detection', () => {
    it('isPlantUmlLanguage detects plantuml (case/whitespace insensitive)', () => {
      const { isPlantUmlLanguage } = makeHarness()
      expect(isPlantUmlLanguage('plantuml')).toBe(true)
      expect(isPlantUmlLanguage('PlantUML')).toBe(true)
      expect(isPlantUmlLanguage(' plantuml ')).toBe(true)
      expect(isPlantUmlLanguage('mermaid')).toBe(false)
      expect(isPlantUmlLanguage('')).toBe(false)
      expect(isPlantUmlLanguage(null)).toBe(false)
    })

    it('isDotLanguage detects dot and graphviz', () => {
      const { isDotLanguage } = makeHarness()
      expect(isDotLanguage('dot')).toBe(true)
      expect(isDotLanguage('graphviz')).toBe(true)
      expect(isDotLanguage('GraphViz')).toBe(true)
      expect(isDotLanguage('mermaid')).toBe(false)
      expect(isDotLanguage('')).toBe(false)
    })

    it('isMermaidLanguage detects mermaid', () => {
      const { isMermaidLanguage } = makeHarness()
      expect(isMermaidLanguage('mermaid')).toBe(true)
      expect(isMermaidLanguage('Mermaid')).toBe(true)
      expect(isMermaidLanguage('dot')).toBe(false)
      expect(isMermaidLanguage('')).toBe(false)
    })
  })

  describe('PlantUML completeness check', () => {
    it('isPlantUmlComplete requires both @startuml and @enduml', () => {
      const { isPlantUmlComplete } = makeHarness()
      expect(isPlantUmlComplete('@startuml\nA -> B\n@enduml')).toBe(true)
      expect(isPlantUmlComplete('@startuml\nA -> B')).toBe(false)
      expect(isPlantUmlComplete('A -> B\n@enduml')).toBe(false)
      expect(isPlantUmlComplete('')).toBe(false)
      expect(isPlantUmlComplete(null)).toBe(false)
    })
  })

  describe('renderPlantUmlBlock', () => {
    it('empty source returns an empty placeholder', () => {
      const { renderPlantUmlBlock } = makeHarness()
      expect(renderPlantUmlBlock('')).toBe('<pre><code class="language-plantuml"></code></pre>')
      expect(renderPlantUmlBlock(null)).toBe('<pre><code class="language-plantuml"></code></pre>')
    })

    it('incomplete source does not request remote rendering and is escaped directly', () => {
      const { renderPlantUmlBlock } = makeHarness()
      const html = renderPlantUmlBlock('A -> B')
      expect(html).toContain('<pre><code class="language-plantuml">')
      expect(html).not.toContain('plantuml.com')
    })

    it('complete source generates an img with the online service URL', () => {
      const { renderPlantUmlBlock } = makeHarness()
      const html = renderPlantUmlBlock('@startuml\nA -> B\n@enduml')
      expect(html).toContain('plantuml-block')
      expect(html).toContain('https://www.plantuml.com/plantuml/svg/')
      expect(html).toContain('class="plantuml-image"')
      expect(html).toContain('class="plantuml-link"')
    })
  })

  describe('renderDotBlock / renderMermaidBlock', () => {
    it('empty source returns an empty placeholder', () => {
      const { renderDotBlock, renderMermaidBlock } = makeHarness()
      expect(renderDotBlock('')).toBe('<pre><code class="language-dot"></code></pre>')
      expect(renderMermaidBlock('')).toBe('<pre><code class="language-mermaid"></code></pre>')
    })

    it('dot source generates placeholder HTML with data-dot-id/data-dot-source', () => {
      const { renderDotBlock } = makeHarness()
      const html = renderDotBlock('digraph G { A -> B }')
      expect(html).toContain('diagram-block')
      expect(html).toMatch(/data-dot-id="dot-diagram-\d+"/)
      expect(html).toContain('data-dot-source=')
      expect(html).toContain('dot-loading')
    })

    it('mermaid source generates placeholder HTML with data-mermaid-id/data-mermaid-source', () => {
      const { renderMermaidBlock } = makeHarness()
      const html = renderMermaidBlock('graph TD\nA-->B')
      expect(html).toContain('diagram-block')
      expect(html).toMatch(/data-mermaid-id="mermaid-diagram-\d+"/)
      expect(html).toContain('data-mermaid-source=')
      expect(html).toContain('mermaid-loading')
    })
  })

  describe('renderMermaidDiagrams / renderDotDiagrams', () => {
    it('returns safely for an empty container', async () => {
      const { renderMermaidDiagrams, renderDotDiagrams } = makeHarness()
      await expect(renderMermaidDiagrams(null)).resolves.toBeUndefined()
      await expect(renderDotDiagrams(null)).resolves.toBeUndefined()
    })

    it('returns safely when no elements match', async () => {
      const { renderMermaidDiagrams, renderDotDiagrams } = makeHarness()
      const container = document.createElement('div')
      await expect(renderMermaidDiagrams(container)).resolves.toBeUndefined()
      await expect(renderDotDiagrams(container)).resolves.toBeUndefined()
    })
  })
})
