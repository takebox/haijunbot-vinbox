import { ref } from 'vue'

// Input history management composable.
//
// Extracted from App.vue's <script setup> while preserving identical behavior:
// - inputHistory: array of historical inputs (persisted in localStorage under haijunbot_input_history)
// - Up/Down keys browse history (two entry points: Panel and pet lobby, sharing the same array)
// - saveToHistory: records history when an input is sent, de-duplicates, caps the size, resets the browse cursor
//
// Dependency injection:
// - inputText: ref(string) (global input box text)
// - panelInputTexts: ref(Map) (agentId -> Panel input text)
export function useInputHistory({ inputText, panelInputTexts }) {
  const INPUT_HISTORY_STORAGE_KEY = 'haijunbot_input_history'
  const MAX_INPUT_HISTORY_COUNT = 100

  const inputHistory = ref([]) // array of recorded history inputs
  const historyIndex = ref(-1) // index of the history entry currently browsed (-1 = not browsing history)
  const currentTempInput = ref('') // temporary content the user is currently editing
  const panelTempInputs = ref(new Map()) // temporary edit content per Panel (key: agentId, value: content)

  // Pet lobby: independent history browse cursor and staged content per Agent
  const lobbyHistoryIndex = new Map() // agentId -> index (-1 = back to latest)
  const lobbyHistoryTemp = new Map() // agentId -> content staged before browsing

  function loadInputHistory() {
    const savedValue = localStorage.getItem(INPUT_HISTORY_STORAGE_KEY)
    if (!savedValue) {
      return []
    }

    try {
      const parsedValue = JSON.parse(savedValue)
      if (!Array.isArray(parsedValue)) {
        return []
      }

      return parsedValue
        .filter(historyItem => typeof historyItem === 'string' && historyItem.trim())
        .slice(0, MAX_INPUT_HISTORY_COUNT)
    } catch {
      return []
    }
  }

  function saveInputHistory() {
    localStorage.setItem(
      INPUT_HISTORY_STORAGE_KEY,
      JSON.stringify(inputHistory.value.slice(0, MAX_INPUT_HISTORY_COUNT))
    )
  }

  // Save an input to history
  function saveToHistory(text) {
    if (!text || !text.trim()) return

    // Avoid saving duplicate history entries
    const lastHistory = inputHistory.value[0]
    if (lastHistory && lastHistory.trim() === text.trim()) {
      return
    }

    // Prepend the new input to the history
    inputHistory.value.unshift(text)

    // Cap the history size
    if (inputHistory.value.length > MAX_INPUT_HISTORY_COUNT) {
      inputHistory.value.pop()
    }

    saveInputHistory()

    // Reset the history browse state
    historyIndex.value = -1
    currentTempInput.value = ''
  }

  // Browse history
  function navigateHistory(direction, agentId = null) {
    // direction: 'up' or 'down'
    // agentId: the agentId of a specific Panel; when passed, operates on that Panel's isolated input

    const isPanel = agentId !== null
    const getInput = () => isPanel ? (panelInputTexts.value.get(agentId) || '') : inputText.value
    const setInput = (val) => {
      if (isPanel) {
        panelInputTexts.value.set(agentId, val)
      } else {
        inputText.value = val
      }
    }
    const getTemp = () => isPanel ? (panelTempInputs.value.get(agentId) || '') : currentTempInput.value
    const setTemp = (val) => {
      if (isPanel) {
        panelTempInputs.value.set(agentId, val)
      } else {
        currentTempInput.value = val
      }
    }

    if (direction === 'up') {
      // Scroll up: load older history entries
      if (historyIndex.value < inputHistory.value.length - 1) {
        // On the first scroll, save the content currently being edited
        if (historyIndex.value === -1) {
          setTemp(getInput())
        }
        historyIndex.value++
        setInput(inputHistory.value[historyIndex.value])
      }
    } else if (direction === 'down') {
      // Scroll down: load newer history entries
      if (historyIndex.value > -1) {
        historyIndex.value--
        if (historyIndex.value === -1) {
          // Back to the latest state: restore the temporarily staged content
          setInput(getTemp())
        } else {
          setInput(inputHistory.value[historyIndex.value])
        }
      }
    }
  }

  // Pet lobby: input history browsing (same behavior as Panel, returns the text after browsing)
  function onLobbyHistoryNav(agentId, direction, currentText = '') {
    const current = currentText || ''
    let index = lobbyHistoryIndex.has(agentId) ? lobbyHistoryIndex.get(agentId) : -1
    if (direction === 'up') {
      if (index < inputHistory.value.length - 1) {
        if (index === -1) lobbyHistoryTemp.set(agentId, current)
        index++
        lobbyHistoryIndex.set(agentId, index)
        return inputHistory.value[index]
      }
      return current
    } else {
      if (index > -1) {
        index--
        lobbyHistoryIndex.set(agentId, index)
        if (index === -1) return lobbyHistoryTemp.get(agentId) || ''
        return inputHistory.value[index]
      }
      return current
    }
  }

  return {
    inputHistory,
    historyIndex,
    currentTempInput,
    panelTempInputs,
    lobbyHistoryIndex,
    lobbyHistoryTemp,
    MAX_INPUT_HISTORY_COUNT,
    loadInputHistory,
    saveInputHistory,
    saveToHistory,
    navigateHistory,
    onLobbyHistoryNav,
  }
}
