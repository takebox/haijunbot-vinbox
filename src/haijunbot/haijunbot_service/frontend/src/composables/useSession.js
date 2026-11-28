// Session restore composable.
//
// Extracted from App.vue's <script setup> (former 4202-4203 state + 12735-12769 function) while preserving identical behavior:
// - showSessionDialog: whether the session restore dialog is visible
// - availableSessions: list of restorable sessions
// - restoreSession(sessionFile): asks the backend to restore the given session file
// - cancelSessionDialog(): cancels session restore (no restore, only loads history messages)
//
// Dependency injection:
// - currentAgentId: ref(string|null) (currently connected Agent ID)
// - getGatewayAddress: function (returns { host, port }, injected by the caller)
// - getCurrentAgentNodeId: function (returns the current Agent's node ID string)
// - fetchWithAuth: function (auth-aware fetch wrapper)
// - buildNodeHttpUrl: function (builds a node HTTP URL)
// - loadHistoryMessages: function (loads history messages, optional prepend/agentId params)
import { ref } from 'vue'

export function useSession({ currentAgentId, getGatewayAddress, getCurrentAgentNodeId, fetchWithAuth, buildNodeHttpUrl, loadHistoryMessages }) {
  const showSessionDialog = ref(false)   // Session selection dialog
  const availableSessions = ref([])      // list of restorable sessions

  // Restore the given session file: call the backend agents/{id}/sessions endpoint
  async function restoreSession(sessionFile) {
    if (!sessionFile || !currentAgentId.value) {
      console.error('[SESSION] Invalid parameters:', { sessionFile, agentId: currentAgentId.value })
      return
    }

    try {
      const { host, port } = getGatewayAddress()
      const targetNodeId = String(getCurrentAgentNodeId() || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `agents/${currentAgentId.value}/sessions`), {
        method: 'POST',
        body: JSON.stringify({ session_file: sessionFile, node_id: targetNodeId })
      })

      const result = await response.json()
      if (result.success) {
        showSessionDialog.value = false
        // Load history messages
        loadHistoryMessages(false)
      } else {
        console.error('[SESSION] Failed to restore session:', result.error)
        alert(`Failed to restore session: ${result.error}`)
      }
    } catch (error) {
      console.error('[SESSION] Error restoring session:', error)
      alert(`Failed to restore session: ${error.message}`)
    }
  }

  // Cancel session restore (the user does not restore the session)
  function cancelSessionDialog() {
    showSessionDialog.value = false
    // Load history messages (the user did not restore the session)
    loadHistoryMessages(false)
  }

  return {
    showSessionDialog,
    availableSessions,
    restoreSession,
    cancelSessionDialog
  }
}
