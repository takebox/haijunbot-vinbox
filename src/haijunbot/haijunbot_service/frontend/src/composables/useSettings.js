// System settings composable.
//
// Extracted from App.vue's <script setup> (Issue #118 Step 8) while preserving identical behavior:
// - state: notifyOnExit / notifyOnInput / syncConfigSourceNode / syncConfigTargetNodes /
//   syncConfigSections / isSyncingConfig / isUpdatingCode
// - notification toggles: saveNotifySettings
// - config sync: handleSyncConfig / syncConfig
// - code update: handleUpdateCodeToMain / confirmUpdateCodeToMain / updateCodeToMain
// - node restart: confirmRestartAllNodes / restartAllNodes
// - admin panel focus: openAdminSystemAction
//
// Dependency injection (the caller passes these in setup; must be called after their definition):
// - refs like notifyOnExit / notifyOnInput are created and returned by this composable; App.vue
//   shares them after destructuring (notifyOnExit / notifyOnInput are consumed by App.vue's handleMessage).
// - getGatewayAddress / getHttpProtocol / fetchWithAuth / buildNodeHttpUrl / showToast /
//   showConfirm / availableNodeOptions / showAdminPanel / adminPanelRef: defined before this
//   composable's call site, passed by reference/ref directly.
// - pushOverlayState / isRestartingGateway / restartFrontendService: defined after the call site
//   (isRestartingGateway / restartFrontendService come from useGatewayConnection), injected as
//   getters, evaluated internally via () => xxx.
import { nextTick, ref } from 'vue'
export function useSettings({
  showAdminPanel,
  adminPanelRef,
  pushOverlayState,
  getGatewayAddress,
  getHttpProtocol,
  fetchWithAuth,
  buildNodeHttpUrl,
  showToast,
  showConfirm,
  availableNodeOptions,
  isRestartingGateway,
  restartFrontendService,
}) {
  // The notification toggles only control system notification popups, not the beeps (beeps are triggered independently by auto-read and other logic)
  const notifyOnExit = ref(localStorage.getItem('haijunbot_notify_on_exit') === 'true')  // Agent exit notification toggle (off by default)
  const notifyOnInput = ref(localStorage.getItem('haijunbot_notify_on_input') === 'true')  // input-required notification toggle (off by default)
  // Config sync state
  const syncConfigSourceNode = ref('') // source node ID for config sync
  const syncConfigTargetNodes = ref([]) // array of target node IDs for config sync
  const syncConfigSections = ref(['llms', 'llm_groups']) // config types to sync (llms, llm_groups)
  const isSyncingConfig = ref(false) // whether config sync is in progress
  const isUpdatingCode = ref(false) // whether a code update is in progress

  // Save the notification toggle settings (only the popups, not the beeps)
  function saveNotifySettings() {
    localStorage.setItem('haijunbot_notify_on_exit', notifyOnExit.value)
    localStorage.setItem('haijunbot_notify_on_input', notifyOnInput.value)
  }

  // Handle the config sync event from SettingsModal
  function handleSyncConfig({ sourceNodeId }) {
    syncConfigSourceNode.value = sourceNodeId || ''

    // Show a confirmation dialog
    showConfirm(
      'Are you sure you want to sync the config to other nodes? This will overwrite the target nodes\' config.',
      () => {
        syncConfig()
      },
      () => {},
      false
    )
  }

  // Handle the code update event from SettingsModal
  function handleUpdateCodeToMain() {
    updateCodeToMain()
  }

  // Open the admin panel focused on system settings and trigger the given action (for the command palette)
  function openAdminSystemAction(kind) {
    showAdminPanel.value = true
    pushOverlayState()()
    nextTick(() => {
      adminPanelRef.value?.openSystemAction?.(kind)
    })
  }

  // Confirm updating code to the main branch
  function confirmUpdateCodeToMain() {
    showConfirm(
      'Are you sure you want to update all nodes\' code to the main branch?\n\nThis will:\n1. Switch all nodes to the main branch\n2. Pull the latest code\n3. Possibly restart services',
      () => {
        updateCodeToMain()
      },
      () => {},
      false
    )
  }

  // Confirm restarting all nodes (child nodes first, master last)
  async function confirmRestartAllNodes() {
    showConfirm(
      'Are you sure you want to restart all nodes with one click?\n\nOrder:\n1. Restart all child nodes one by one\n2. Restart the master node last\n\nThis will briefly interrupt connections to all nodes, including running Agents.',
      () => {
        restartAllNodes()
      },
      () => {},
      false
    )
  }

  async function restartAllNodes() {
    try {
      isRestartingGateway().value = true
      const { host, port } = getGatewayAddress()

      // Get the list of all nodes (excluding master)
      const childNodes = (availableNodeOptions.value || []).filter(node => node.node_id !== 'master')
      const allNodes = [...childNodes, { node_id: 'master', label: 'Master' }]

      for (const node of allNodes) {
        const nodeId = node.node_id
        const normalizedNodeId = nodeId || 'master'

        try {
          // Send the restart request
          const response = await fetchWithAuth(buildNodeHttpUrl(host, port, normalizedNodeId, 'service/restart'), {
            method: 'POST',
            body: JSON.stringify({
              node_id: normalizedNodeId,
              restart_frontend: restartFrontendService().value
            })
          })

          if (response.ok) {
            const data = await response.json().catch(() => ({}))
            if (data.success === false) {
              showToast(`Node "${normalizedNodeId}" restart failed: ${data.error?.message || 'Unknown error'}`, 'error')
            } else {
              showToast(`Restart request sent to node "${normalizedNodeId}"`, 'success')
            }
          } else {
            showToast(`Node "${normalizedNodeId}" restart failed: HTTP ${response.status}`, 'error')
          }
        } catch (error) {
          console.error(`[SETTINGS] Failed to restart node ${normalizedNodeId}:`, error)
          showToast(`Node "${normalizedNodeId}" restart failed: ${error.message || 'Unknown error'}`, 'error')
        }

        // Wait 1 second between nodes to avoid a burst of requests
        if (node.node_id !== 'master') {
          await new Promise(resolve => setTimeout(resolve, 1000))
        }
      }

      showToast('Restart commands sent to all nodes', 'success')
    } catch (error) {
      console.error('[SETTINGS] Failed to restart all nodes:', error)
      showToast(error.message || 'Failed to restart all nodes', 'error')
    } finally {
      setTimeout(() => {
        isRestartingGateway().value = false
      }, 3000)
    }
  }
  async function syncConfig() {
    if (isSyncingConfig.value) {
      return
    }

    try {
      isSyncingConfig.value = true
      const { host, port } = getGatewayAddress()
      const sourceNodeId = syncConfigSourceNode.value || 'master'

      // Auto-select all nodes except the source as targets
      const targetNodeIds = availableNodeOptions.value
        .map(node => node.node_id)
        .filter(id => id !== sourceNodeId)

      // If the source node is not master, add master to the target list
      if (sourceNodeId !== 'master' && !targetNodeIds.includes('master')) {
        targetNodeIds.unshift('master')
      }

      if (targetNodeIds.length === 0) {
        showToast('No other nodes to sync to', 'warning')
        return
      }

      // 1. Fetch the config from the source node
      const getResponse = await fetchWithAuth(`${getHttpProtocol()}://${host}:${port}/api/nodes/${sourceNodeId}/config`, {
        method: 'GET'
      })
      const getResult = await getResponse.json()

      if (!getResponse.ok || !getResult.success) {
        throw new Error(getResult.error?.message || 'Failed to fetch source node config')
      }

      const sourceConfig = getResult.data?.config || {}

      // Extract the config to sync
      const configData = {}
      for (const section of syncConfigSections.value) {
        if (sourceConfig[section]) {
          configData[section] = sourceConfig[section]
        }
      }

      if (Object.keys(configData).length === 0) {
        showToast('No config data to sync', 'warning')
        return
      }

      // 2. Apply the config to each target node
      let successCount = 0
      const totalCount = targetNodeIds.length
      const results = []

      for (const targetNodeId of targetNodeIds) {
        try {
          const setResponse = await fetchWithAuth(`${getHttpProtocol()}://${host}:${port}/api/nodes/${targetNodeId}/config`, {
            method: 'POST',
            body: JSON.stringify({
              config_sections: syncConfigSections.value,
              config_data: configData
            })
          })
          const setResult = await setResponse.json()

          if (setResponse.ok && setResult.success) {
            successCount++
            results.push({
              node_id: targetNodeId,
              success: true,
              data: setResult.data
            })
          } else {
            results.push({
              node_id: targetNodeId,
              success: false,
              error: setResult.error || { message: 'Failed to apply config' }
            })
          }
        } catch (error) {
          console.error(`[SETTINGS] Failed to set config for node ${targetNodeId}:`, error)
          results.push({
            node_id: targetNodeId,
            success: false,
            error: { message: error.message || 'Failed to apply config' }
          })
        }
      }

      // 3. Show the results
      if (successCount === totalCount) {
        showToast(`Config sync succeeded, applied to ${successCount} nodes`, 'success')
      } else {
        showToast(`Config sync partially succeeded, applied to ${successCount}/${totalCount} nodes`, 'warning')
      }

      // Record the detailed results
    } catch (error) {
      console.error('[SETTINGS] Failed to sync config:', error)
      showToast(error.message || 'Failed to sync config', 'error')
    } finally {
      isSyncingConfig.value = false
    }
  }

  async function updateCodeToMain() {
    if (isUpdatingCode.value) {
      return
    }

    // Debug log

    try {
      isUpdatingCode.value = true
      const { host, port } = getGatewayAddress()

      // Get all online nodes
      const nodeOptions = availableNodeOptions.value || []
      if (nodeOptions.length === 0) {
        showToast('No online nodes to update', 'warning')
        return
      }

      // Run the update on each node
      let successCount = 0
      const totalCount = nodeOptions.length
      const results = []

      for (const node of nodeOptions) {
        const nodeId = node.node_id
        try {
          const response = await fetchWithAuth(`${getHttpProtocol()}://${host}:${port}/api/nodes/${nodeId}/code-update`, {
            method: 'POST'
          })
          const result = await response.json()

          if (response.ok && result.success) {
            successCount++
            results.push({
              node_id: nodeId,
              success: true,
              message: result.data?.message || 'Update succeeded'
            })
            showToast(`Update request sent to node "${nodeId}"`, 'success')
          } else {
            results.push({
              node_id: nodeId,
              success: false,
              message: result.error?.message || 'Update failed'
            })
            showToast(`Node "${nodeId}" update failed: ${result.error?.message || 'Unknown error'}`, 'error')
          }
        } catch (error) {
          console.error(`[SETTINGS] Failed to update code for node ${nodeId}:`, error)
          results.push({
            node_id: nodeId,
            success: false,
            message: error.message || 'Update failed'
          })
          showToast(`Node "${nodeId}" update failed: ${error.message || 'Unknown error'}`, 'error')
        }
      }

      // Show the results

      if (successCount === totalCount) {
        showToast(`Code update succeeded, updated ${successCount}/${totalCount} nodes`, 'success')
      } else if (successCount > 0) {
        showToast(`Code update partially succeeded, ${successCount}/${totalCount} nodes`, 'warning')
      } else {
        showToast('Code update failed, no nodes updated', 'error')
      }
    } catch (error) {
      console.error('[SETTINGS] Failed to update code:', error)
      showToast(error.message || 'Failed to update code', 'error')
    } finally {
      isUpdatingCode.value = false
    }
  }

  return {
    notifyOnExit,
    notifyOnInput,
    syncConfigSourceNode,
    syncConfigTargetNodes,
    syncConfigSections,
    isSyncingConfig,
    isUpdatingCode,
    saveNotifySettings,
    handleSyncConfig,
    handleUpdateCodeToMain,
    openAdminSystemAction,
    confirmUpdateCodeToMain,
    confirmRestartAllNodes,
    restartAllNodes,
    syncConfig,
    updateCodeToMain,
  }
}
