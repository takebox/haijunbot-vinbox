// Diff floating window composable.
//
// Extracted from App.vue's <script setup> (former 2942-2954 state + 14765-14822 function) while preserving identical behavior:
// - showDiffModal: shows the diff floating window
// - diffFiles: structured diff file list (each item contains file_path/additions/deletions/rows)
// - diffActiveIndex: index of the currently selected file
// - diffLoading: loading state
// - diffError: error message when loading fails
// - diffMobileShowDetail: mobile two-level navigation (false=file list, true=diff detail of selected file)
// - diffActiveHtml: rendered result of the selected file (reuses renderSideBySideDiff)
// - selectDiffFile(index): selects a file (desktop switches the right-side content only; mobile enters fullscreen detail)
// - viewDiff(agent): views an Agent's Diff (fetches structured diff data from the backend)
//
// Dependency injection:
// - windowWidth: ref(number) (window width, used for narrow-screen detection on mobile)
// - getGatewayAddress: function (returns { host, port }, injected by the caller)
// - getCurrentAgentNodeId: function (returns the current Agent's node ID string)
// - fetchWithAuth: function (auth-aware fetch wrapper)
// - buildNodeHttpUrl: function (builds a node HTTP URL)
import { computed, ref } from 'vue'
import { renderSideBySideDiff } from '../diffRenderer.js'

export function useDiff({ windowWidth, getGatewayAddress, getCurrentAgentNodeId, fetchWithAuth, buildNodeHttpUrl }) {
  const showDiffModal = ref(false)      // shows the diff floating window
  const diffFiles = ref([])             // structured diff file list (each item contains file_path/additions/deletions/rows)
  const diffActiveIndex = ref(0)        // index of the currently selected file
  const diffLoading = ref(false)        // loading state
  const diffError = ref('')             // error message when loading fails
  // Mobile two-level navigation: false=file list, true=diff detail of the selected file
  const diffMobileShowDetail = ref(false)
  // Rendered result of the currently selected file (reuses renderSideBySideDiff)
  const diffActiveHtml = computed(() => {
    const file = diffFiles.value[diffActiveIndex.value]
    if (!file) return ''
    return renderSideBySideDiff(file)
  })

  // Select a file: desktop only switches the right-side content; mobile enters fullscreen detail
  function selectDiffFile(index) {
    diffActiveIndex.value = index
    // On mobile (narrow screen), clicking a file shows its diff fullscreen; the top back button returns to the list
    if (windowWidth.value <= 768) {
      diffMobileShowDetail.value = true
    }
  }

  // View an Agent's Diff
  async function viewDiff(agent) {
    if (!agent || !agent.agent_id) {
      console.warn('[DIFF] Invalid agent:', agent)
      return
    }
    diffLoading.value = true
    showDiffModal.value = true
    diffFiles.value = []
    diffActiveIndex.value = 0
    diffError.value = ''
    diffMobileShowDetail.value = false
    try {
      const { host, port } = getGatewayAddress()
      const targetNodeId = String(agent?.node_id || '').trim() || String(getCurrentAgentNodeId() || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `agent/${agent.agent_id}/diff`))
      if (!response.ok) {
        console.warn(`[DIFF] Failed to fetch diff for agent ${agent.agent_id}:`, response.status)
        diffError.value = 'Failed to fetch diff'
        return
      }
      const result = await response.json()
      // Use the structured data returned by the backend, with data validation
      if (result.files && Array.isArray(result.files) && result.files.length > 0) {
        // Validate and filter valid file data
        const validFiles = result.files.filter(file => {
          // Verify the file object has the required fields
          if (!file || typeof file !== 'object') return false
          if (!file.rows || !Array.isArray(file.rows)) return false
          // Verify every element in rows
          return file.rows.every(row => {
            return row && typeof row === 'object' &&
                   ['equal', 'insert', 'delete', 'replace'].includes(row.type)
          })
        })
        diffFiles.value = validFiles
      }
    } catch (error) {
      console.error('[DIFF] Error fetching diff:', error)
      diffError.value = 'Failed to fetch diff: ' + (error.message || '')
    } finally {
      diffLoading.value = false
    }
  }

  return {
    showDiffModal,
    diffFiles,
    diffActiveIndex,
    diffLoading,
    diffError,
    diffMobileShowDetail,
    diffActiveHtml,
    selectDiffFile,
    viewDiff
  }
}
