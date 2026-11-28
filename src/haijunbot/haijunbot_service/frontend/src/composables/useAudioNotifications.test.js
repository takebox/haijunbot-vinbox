// Temporary verification of useAudioNotifications behavior (delete after validation)
import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'
import { useAudioNotifications } from './useAudioNotifications.js'

function makeHarness() {
  const sessionPanelRefs = new Map()
  const allOutputs = ref(new Map())
  const panelInputTips = ref(new Map())
  const panels = ref([])
  const panelAutoReads = ref(new Map())
  const isAutoReadEnabled = (agentId) => panelAutoReads.value.get(agentId) === true
  const api = useAudioNotifications({ sessionPanelRefs, allOutputs, panelInputTips, panels, isAutoReadEnabled })
  return { api, sessionPanelRefs, allOutputs, panelInputTips, panels, panelAutoReads }
}

describe('useAudioNotifications', () => {
  it('exposes the expected API', () => {
    const { api } = makeHarness()
    expect(typeof api.notifyInputRequest).toBe('function')
    expect(typeof api.playChatNotificationSound).toBe('function')
    expect(typeof api.stopAutoRead).toBe('function')
    expect(typeof api.handleAutoRead).toBe('function')
    expect(typeof api.sendSystemNotification).toBe('function')
    expect(typeof api.autoReadSupported).toBe('boolean')
  })

  it('handleAutoRead returns early when auto-read is disabled', async () => {
    const { api } = makeHarness()
    const result = await api.handleAutoRead('agent-1', 'waiting_single')
    expect(result).toBeUndefined()
  })

  it('handleAutoRead calls SessionPanel\'s speakText when enabled', async () => {
    const { api, panelAutoReads, panelInputTips, panels, sessionPanelRefs } = makeHarness()
    panelAutoReads.value.set('agent-1', true)
    panelInputTips.value.set('agent-1', 'hello')
    panels.value = [{ id: 'panel-1', agentId: 'agent-1' }]
    const speakText = vi.fn()
    const sp = { speakText, speakMessage: vi.fn() }
    sessionPanelRefs.set('panel-1', sp)
    await api.handleAutoRead('agent-1', 'waiting_single')
    expect(speakText).toHaveBeenCalledWith('hello')
  })

  it('handleAutoRead takes the last message with text from multi-line input', async () => {
    const { api, panelAutoReads, allOutputs, panels, sessionPanelRefs } = makeHarness()
    panelAutoReads.value.set('agent-1', true)
    allOutputs.value.set('agent-1', [
      { html: '<p>first</p>' },
      { html: '<p>second</p>' },
    ])
    panels.value = [{ id: 'panel-1', agentId: 'agent-1' }]
    const speakMessage = vi.fn()
    sessionPanelRefs.set('panel-1', { speakMessage, speakText: vi.fn() })
    await api.handleAutoRead('agent-1', 'waiting_multi')
    expect(speakMessage).toHaveBeenCalled()
    // Should pick the last message with text
    expect(speakMessage.mock.calls[0][0]).toEqual({ html: '<p>second</p>' })
  })

  it('stopAutoRead calls stopSpeak on every SessionPanel', () => {
    // jsdom has no speechSynthesis, so mock it to make autoReadSupported true
    globalThis.speechSynthesis = {}
    const { api, sessionPanelRefs } = makeHarness()
    const sp1 = { stopSpeak: vi.fn() }
    const sp2 = { stopSpeak: vi.fn() }
    sessionPanelRefs.set('p1', sp1)
    sessionPanelRefs.set('p2', sp2)
    api.stopAutoRead()
    expect(sp1.stopSpeak).toHaveBeenCalled()
    expect(sp2.stopSpeak).toHaveBeenCalled()
  })

  it('sendSystemNotification returns silently without a Notification API', () => {
    const { api } = makeHarness()
    expect(() => api.sendSystemNotification('test')).not.toThrow()
  })
})
