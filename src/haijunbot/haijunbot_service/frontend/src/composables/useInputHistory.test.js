// useInputHistory unit tests
import { describe, it, expect, beforeEach } from 'vitest'
import { ref } from 'vue'
import { useInputHistory } from './useInputHistory.js'

function makeHarness() {
  const inputText = ref('')
  const panelInputTexts = ref(new Map())
  const api = useInputHistory({ inputText, panelInputTexts })
  return { api, inputText, panelInputTexts }
}

describe('useInputHistory', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('exposes the expected API', () => {
    const { api } = makeHarness()
    expect(typeof api.loadInputHistory).toBe('function')
    expect(typeof api.saveInputHistory).toBe('function')
    expect(typeof api.saveToHistory).toBe('function')
    expect(typeof api.navigateHistory).toBe('function')
    expect(typeof api.onLobbyHistoryNav).toBe('function')
    expect(Array.isArray(api.inputHistory.value)).toBe(true)
    expect(api.MAX_INPUT_HISTORY_COUNT).toBe(100)
  })

  it('saveToHistory saves input and persists it to localStorage', () => {
    const { api } = makeHarness()
    api.saveToHistory('first entry')
    expect(api.inputHistory.value).toEqual(['first entry'])
    expect(JSON.parse(localStorage.getItem('haijunbot_input_history'))).toEqual(['first entry'])
  })

  it('saveToHistory skips empty text', () => {
    const { api } = makeHarness()
    api.saveToHistory('')
    api.saveToHistory('   ')
    expect(api.inputHistory.value).toEqual([])
  })

  it('saveToHistory deduplicates adjacent repeated inputs', () => {
    const { api } = makeHarness()
    api.saveToHistory('duplicate')
    api.saveToHistory('duplicate')
    expect(api.inputHistory.value).toEqual(['duplicate'])
  })

  it('saveToHistory evicts the oldest entries past the limit', () => {
    const { api } = makeHarness()
    for (let i = 0; i < 105; i++) {
      api.saveToHistory(`input-${i}`)
    }
    expect(api.inputHistory.value.length).toBe(100)
    expect(api.inputHistory.value[0]).toBe('input-104')
    expect(api.inputHistory.value[99]).toBe('input-5')
  })

  it('navigateHistory scrolls up through the global input history', () => {
    const { api, inputText } = makeHarness()
    api.saveToHistory('history-A')
    api.saveToHistory('history-B')
    inputText.value = 'current'
    api.navigateHistory('up')
    expect(inputText.value).toBe('history-B')
    api.navigateHistory('up')
    expect(inputText.value).toBe('history-A')
    // Scroll down to the latest, restoring the staged content
    api.navigateHistory('down')
    expect(inputText.value).toBe('history-B')
    api.navigateHistory('down')
    expect(inputText.value).toBe('current')
  })

  it('navigateHistory with an agentId operates on the Panel\'s isolated input', () => {
    const { api, panelInputTexts } = makeHarness()
    api.saveToHistory('panel-history')
    panelInputTexts.value.set('agent-1', 'current')
    api.navigateHistory('up', 'agent-1')
    expect(panelInputTexts.value.get('agent-1')).toBe('panel-history')
    api.navigateHistory('down', 'agent-1')
    expect(panelInputTexts.value.get('agent-1')).toBe('current')
  })

  it('loadInputHistory loads from localStorage and filters invalid items', () => {
    const { api } = makeHarness()
    localStorage.setItem('haijunbot_input_history', JSON.stringify(['valid', '', 123, '  ']))
    api.inputHistory.value = api.loadInputHistory()
    expect(api.inputHistory.value).toEqual(['valid'])
  })

  it('loadInputHistory silently falls back to an empty array for corrupt data', () => {
    const { api } = makeHarness()
    localStorage.setItem('haijunbot_input_history', '{{{bad json')
    expect(api.loadInputHistory()).toEqual([])
  })

  it('onLobbyHistoryNav browses history in the pet lobby', () => {
    const { api } = makeHarness()
    api.saveToHistory('hall-A')
    api.saveToHistory('hall-B')
    expect(api.onLobbyHistoryNav('agent-1', 'up', 'current')).toBe('hall-B')
    expect(api.onLobbyHistoryNav('agent-1', 'up', 'hall-B')).toBe('hall-A')
    expect(api.onLobbyHistoryNav('agent-1', 'down', 'hall-A')).toBe('hall-B')
    expect(api.onLobbyHistoryNav('agent-1', 'down', 'hall-B')).toBe('current')
  })

  it('onLobbyHistoryNav returns the current text when there is no more history', () => {
    const { api } = makeHarness()
    api.saveToHistory('only')
    expect(api.onLobbyHistoryNav('agent-1', 'up', 'current')).toBe('only')
    expect(api.onLobbyHistoryNav('agent-1', 'up', 'only')).toBe('only')
  })
})
