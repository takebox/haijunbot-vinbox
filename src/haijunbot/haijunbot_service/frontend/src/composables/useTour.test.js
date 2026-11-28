// useTour unit tests
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useTour } from './useTour.js'

// Build a DI harness for useTour (getter injection, matching App.vue)
function makeHarness() {
  const showToast = vi.fn()
  const openWorkspaceAgentList = vi.fn()
  const api = useTour({
    showToast: () => showToast,
    openWorkspaceAgentList: () => openWorkspaceAgentList,
  })
  return { api, showToast, openWorkspaceAgentList }
}

// In-memory localStorage mock
function makeLocalStorageMock() {
  const store = new Map()
  return {
    getItem: vi.fn((key) => (store.has(key) ? store.get(key) : null)),
    setItem: vi.fn((key, value) => store.set(key, String(value))),
    removeItem: vi.fn((key) => store.delete(key)),
    key: vi.fn((i) => Array.from(store.keys())[i] ?? null),
    get length() {
      return store.size
    },
    _store: store,
  }
}

describe('useTour', () => {
  let ls
  beforeEach(() => {
    ls = makeLocalStorageMock()
    vi.stubGlobal('localStorage', ls)
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('initial state: no active tour and empty steps', () => {
    const { api } = makeHarness()
    expect(api.activeTourId.value).toBe(null)
    expect(api.showOnboarding.value).toBe(false)
    expect(api.activeTourSteps.value).toEqual([])
  })

  it('startOnboarding opens the tour for a given scene (without writing marks)', () => {
    const { api } = makeHarness()
    api.startOnboarding('lobby')
    expect(api.activeTourId.value).toBe('lobby')
    expect(api.showOnboarding.value).toBe(true)
    expect(api.activeTourSteps.value.length).toBeGreaterThan(0)
    // markTourSeen was not called, so no mark should be written
    expect(ls.getItem('haijunbot_onboarding_lobby_v1')).toBe(null)
  })

  it('startOnboarding defaults to the welcome scene', () => {
    const { api } = makeHarness()
    api.startOnboarding()
    expect(api.activeTourId.value).toBe('welcome')
    expect(api.activeTourSteps.value).toHaveLength(6)
  })

  it('startOnboarding calls openWorkspaceAgentList for the sidebar scene', () => {
    const { api, openWorkspaceAgentList } = makeHarness()
    api.startOnboarding('sidebar')
    expect(openWorkspaceAgentList).toHaveBeenCalledTimes(1)
  })

  it('startOnboarding does not call openWorkspaceAgentList for non-sidebar scenes', () => {
    const { api, openWorkspaceAgentList } = makeHarness()
    api.startOnboarding('welcome')
    expect(openWorkspaceAgentList).not.toHaveBeenCalled()
  })

  it('finishTour marks as seen, closes, and shows a toast for the welcome scene', () => {
    const { api, showToast } = makeHarness()
    api.startOnboarding('welcome')
    api.finishTour()
    expect(api.activeTourId.value).toBe(null)
    expect(api.showOnboarding.value).toBe(false)
    expect(ls.getItem('haijunbot_onboarding_welcome_v1')).toBe('1')
    expect(showToast).toHaveBeenCalledWith('Guide complete, start using HaijunBot', 'success')
  })

  it('finishTour shows no toast for non-welcome scenes', () => {
    const { api, showToast } = makeHarness()
    api.startOnboarding('agent')
    api.finishTour()
    expect(showToast).not.toHaveBeenCalled()
  })

  it('setting showOnboarding to false triggers finishTour (v-model close)', () => {
    const { api } = makeHarness()
    api.startOnboarding('panel')
    api.showOnboarding.value = false
    expect(api.activeTourId.value).toBe(null)
    expect(ls.getItem('haijunbot_onboarding_panel_v1')).toBe('1')
  })

  it('maybeStartTour triggers unseen scenes after a delay', () => {
    const { api } = makeHarness()
    api.maybeStartTour('lobby')
    expect(api.activeTourId.value).toBe(null) // delay has not elapsed yet
    vi.advanceTimersByTime(800)
    expect(api.activeTourId.value).toBe('lobby')
  })

  it('maybeStartTour skips scenes already seen', () => {
    const { api } = makeHarness()
    ls.setItem('haijunbot_onboarding_lobby_v1', '1')
    api.maybeStartTour('lobby')
    vi.advanceTimersByTime(800)
    expect(api.activeTourId.value).toBe(null)
  })

  it('maybeStartTour skips an in-progress tour', () => {
    const { api } = makeHarness()
    api.startOnboarding('welcome')
    api.maybeStartTour('lobby')
    vi.advanceTimersByTime(800)
    expect(api.activeTourId.value).toBe('welcome')
  })

  it('hasSeenTour recognizes the legacy single tour mark (welcome)', () => {
    const { api } = makeHarness()
    ls.setItem('haijunbot_onboarding_done_v1', '1')
    api.maybeStartTour('welcome')
    vi.advanceTimersByTime(800)
    expect(api.activeTourId.value).toBe(null)
  })

  it('resetOnboardingMarks clears all onboarding marks', () => {
    const { api } = makeHarness()
    ls.setItem('haijunbot_onboarding_welcome_v1', '1')
    ls.setItem('haijunbot_onboarding_lobby_v1', '1')
    ls.setItem('haijunbot_onboarding_done_v1', '1')
    ls.setItem('unrelated_key', '1')
    api.resetOnboardingMarks()
    expect(ls.getItem('haijunbot_onboarding_welcome_v1')).toBe(null)
    expect(ls.getItem('haijunbot_onboarding_lobby_v1')).toBe(null)
    expect(ls.getItem('haijunbot_onboarding_done_v1')).toBe(null)
    // Unrelated keys are untouched
    expect(ls.getItem('unrelated_key')).toBe('1')
  })

  it('clearOnboardingTimer cancels the pending tour', () => {
    const { api } = makeHarness()
    api.maybeStartTour('panel')
    api.clearOnboardingTimer()
    vi.advanceTimersByTime(800)
    expect(api.activeTourId.value).toBe(null)
  })

  it('per-scene step constants are available via getTourSteps', () => {
    const { api } = makeHarness()
    expect(api.activeTourSteps.value).toEqual([])
    // Trigger each scene via startOnboarding and verify steps are not empty
    api.startOnboarding('welcome')
    expect(api.activeTourSteps.value.length).toBeGreaterThan(0)
    api.startOnboarding('lobby')
    expect(api.activeTourSteps.value.length).toBeGreaterThan(0)
    api.startOnboarding('agent')
    expect(api.activeTourSteps.value.length).toBeGreaterThan(0)
    api.startOnboarding('panel')
    expect(api.activeTourSteps.value.length).toBeGreaterThan(0)
    api.startOnboarding('sidebar')
    expect(api.activeTourSteps.value.length).toBeGreaterThan(0)
  })
})
