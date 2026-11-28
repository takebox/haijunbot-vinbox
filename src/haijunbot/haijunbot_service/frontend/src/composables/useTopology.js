// Network topology composable.
//
// Extracted from App.vue's <script setup> (Issue #118 Step 8) while preserving identical behavior:
// - state: topologyExtensionSessions / topologyDaemonSessions / showTopologyOverlay
// - access session polling: refreshTopologyAccessSessions / startTopologyAccessPolling / stopTopologyAccessPolling
// - overlay control: openTopologyOverlay / closeTopologyOverlay
//
// Dependency injection (the caller passes these in setup; must be called after their definition):
// - fetchBrowserExtensionSessions / fetchDaemonSessions: session query functions (defined in App.vue)
//
// Note: topologyExtensionSessions / topologyDaemonSessions are also written by App.vue's
// refreshManageCapabilities (manage domain), so these two refs are returned by this composable
// and App.vue shares the writes after destructuring.
import { ref } from 'vue'
export function useTopology({
  fetchBrowserExtensionSessions,
  fetchDaemonSessions,
}) {
  // -- "Access end" session list in the network topology map --
  // Browser extension and daemon sessions both come from the gateway session list: multiple devices /
  // browsers may be connected, and each session is rendered as a node showing its name (user-configured terminal name).
  // Non-admins only see their own sessions (gateway-side restriction); admins see all.
  const topologyExtensionSessions = ref([])
  const topologyDaemonSessions = ref([])
  let topologyAccessTimer = null
  async function refreshTopologyAccessSessions() {
    const [extSessions, daemonSessions] = await Promise.all([
      fetchBrowserExtensionSessions(),
      fetchDaemonSessions(),
    ])
    topologyExtensionSessions.value = Array.isArray(extSessions) ? extSessions : []
    topologyDaemonSessions.value = Array.isArray(daemonSessions) ? daemonSessions : []
  }
  function startTopologyAccessPolling() {
    if (topologyAccessTimer) return
    refreshTopologyAccessSessions()
    topologyAccessTimer = setInterval(refreshTopologyAccessSessions, 5000)
  }
  function stopTopologyAccessPolling() {
    if (topologyAccessTimer) {
      clearInterval(topologyAccessTimer)
      topologyAccessTimer = null
    }
  }
  const showTopologyOverlay = ref(false) // network topology map overlay
  // Open the network topology map (triggered by clicking the mini map beside a pet or via context menu)
  function openTopologyOverlay() {
    showTopologyOverlay.value = true
    startTopologyAccessPolling()
  }
  // Close the network topology map: stop access session polling to avoid background idle work
  function closeTopologyOverlay() {
    showTopologyOverlay.value = false
    stopTopologyAccessPolling()
  }

  return {
    topologyExtensionSessions,
    topologyDaemonSessions,
    refreshTopologyAccessSessions,
    startTopologyAccessPolling,
    stopTopologyAccessPolling,
    showTopologyOverlay,
    openTopologyOverlay,
    closeTopologyOverlay,
  }
}
