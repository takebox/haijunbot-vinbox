<template>
  <div class="app" :class="{ 'not-connected': showConnectModal }">
    <!-- Main pet widget: globally floating pet (tracks / drag / snap-to-edge); long-press to create an Agent from a single sentence -->
    <PetWidget
      ref="petWidgetRef"
      :isConnected="!!socket && !showConnectModal"
      :windowWidth="windowWidth"
      :agentList="agentList"
      :agentStatuses="agentStatuses"
      :isWaitingInput="isWaitingInput"
      :currentAgentId="currentAgentId"
      :nodes="availableNodeOptions"
      :getStatusClass="getStatusClass"
      :extensionSessions="topologyExtensionSessions"
      :daemonSessions="topologyDaemonSessions"
      :localDaemonOnline="localDaemonOnline"
      @petSyncStatus="petSyncAllStatus"
      @petInterruptCurrent="petInterruptCurrent"
      @petGotoWaiting="petGotoWaitingAgent"
      @petToggleSidebar="openWorkspaceAgentList"
      @petOpenTopology="openTopologyOverlay"
      @petOpenCommandPalette="openCommandPalette()"
      @openQuickCreate="openQuickCreateAgent"
    />

    <!-- Main content area -->

    <!-- Main content area -->

    <!-- Main content area -->
    <div class="main-content-wrapper">
    <!-- Panel grid layout -->
    <main class="panel-grid" :style="panelGridStyle">
      <!-- Sole container: the editor panel (all panels open inside the editor, no longer tiled side by side) -->
      <!-- Embedded editor panel -->
      <WorkspacePanel
        v-if="showWorkspacePanel"
        ref="workspacePanelRef"
        :visible="showWorkspacePanel"
        :active="activeWindow === 'workspace'"
        :interaction="workspacePanelInteraction"
        :panelStyle="workspacePanelStyle"
        :agentName="activeWorkspaceSession?.agent_name"
        :activeTab="activeWorkspaceTab"
        :activeTabPath="activeWorkspaceTabPath"
        :tabs="workspaceTabs"
        :isMaximized="isWorkspaceMaximized"
        :showSidebar="showWorkspaceSidebar"
        :sidebarView="workspaceSidebarView"
        :mainView="workspaceMainView"
        :resizeDirections="workspaceResizeDirections"
        :embedded="true"
        :isAdmin="!!auth.userInfo?.is_admin"
        :isEditable="isWorkspaceEditable"
        :hasActiveTab="!!activeWorkspaceTabPath"
        :pluginSidebarViews="pluginSidebarViews"
        :pluginToolPanels="pluginToolPanels"
        @focus="focusWindow('workspace')"
        @startMove="startWorkspacePanelMove"
        @toggleMaximize="toggleWorkspaceMaximize"
        @save="saveActiveWorkspaceTab"
        @close="closeWorkspacePanel"
        @activateTab="activateWorkspaceTab"
        @closeTab="closeWorkspaceTab"
        @tabContextMenu="(path, event) => openTabContextMenu(null, path, event)"
        @toggleEditable="toggleWorkspaceEditable"
        @setSidebarView="toggleWorkspaceSidebarView"
        @setMainView="toggleWorkspaceMainView"
        @startResize="startWorkspacePanelResize"
        @openSettings="showSettingsModal = true; pushOverlayState()"
        @openDocs="openDocs()"
        @openAdmin="showAdminPanel = true; pushOverlayState()"
        @openAbout="openAbout()"
        @openTopology="openTopologyOverlay()"
      >
        <template #sidebar>
          <aside v-if="showWorkspaceSidebar" class="workspace-sidebar" :style="{ width: workspaceSidebarWidth + 'px' }">
            <div class="workspace-sidebar-resize-handle" @mousedown="startWorkspaceSidebarResize($event)"></div>
            <div class="workspace-sidebar-header">
              <span class="workspace-sidebar-title">{{ workspaceSidebarTitle }}</span>
              <button class="icon-btn-small workspace-sidebar-close-mobile" tabindex="-1" @mousedown.prevent @click="closeWorkspaceSidebar" title="Close sidebar">✕</button>
              <button class="icon-btn-small workspace-sidebar-close-desktop" tabindex="-1" @mousedown.prevent @click="closeWorkspaceSidebar" title="Close sidebar">✕</button>
            </div>
            <div v-if="workspaceSidebarView === 'agents'" class="workspace-sidebar-content workspace-sidebar-agents">
              <AgentSidebar
                :visible="true"
                :embedded="true"
                :resizeState="{ active: false }"
                :sidebarStyle="{ width: '100%' }"
                :isBatchMode="isBatchMode"
                :displayGroups="agentDisplayGroups"
                :currentAgentId="currentAgentId"
                :selectedCount="selectedAgents.size"
                :agentList="agentList"
                :windowWidth="windowWidth"
                :isAllSelected="isAllSelected"
                :agentStatuses="agentStatuses"
                :getStatusClass="getStatusClass"
                :getStatusText="getStatusText"
                :getNodeLabel="getAgentNodeLabel"
                :getNodeDisplayLabel="getAgentNodeDisplayLabel"
                :getProxyNodeLabel="getAgentProxyNodeLabel"
                :getWorkingDirDisplay="getWorkingDirDisplay"
                :isSelected="isAgentSelected"
                :isWaitingInput="isWaitingInput"
                :agentGroups="agentGroups"
                :nodes="availableNodeOptions"
                :currentUserId="auth.userInfo?.user_id || ''"
                :currentUserName="auth.userInfo?.display_name || auth.userInfo?.username || ''"
                :isConnected="!!socket && !showConnectModal"
                @close="setWorkspaceSidebarView('files')"
                @toggleBatchMode="toggleBatchMode"
                @createAgent="openCreateAgentModal"
                @orchestrate="openOrchestrateModal"
                @agentClick="onWorkspaceSidebarAgentClick"
                @agentContextMenu="onSidebarAgentContextMenu"
                @toggleSelectAgent="toggleSelectAgent"
                @renameAgent="renameAgent"
                @copyAgent="copyAgent"
                @deleteAgent="deleteAgent"
                @regenerateAgent="regenerateAgent"
                @toggleSelectAll="toggleSelectAll"
                @batchCopy="batchCopyAgents"
                @batchDelete="batchDeleteAgents"
                @addToGroup="addSelectedToGroup"
                @createGroupWithAgents="createGroupWithAgents"
                @renameGroup="renameAgentGroup"
                @deleteGroup="deleteAgentGroup"
                @editAccess="editAgentAccess"
              />
            </div>
            <div v-else-if="workspaceSidebarView === 'files'" class="workspace-sidebar-content">
              <div class="workspace-file-tree-panel">
                <!-- Open any directory on a node (browse/edit files without creating an Agent) -->
                <button class="workspace-open-dir-btn" @click="openOpenDirDialog" title="Choose node and directory to open">
                  <span class="workspace-open-dir-icon" v-html="UI_ICONS.folder"></span>
                  <span>Open Directory</span>
                </button>
                <!-- Active Agent node list -->
                <div
                  v-for="agent in activeAgents"
                  :key="agent.agent_id"
                  class="workspace-agent-node"
                  :class="{
                    'selected': selectedAgentId === agent.agent_id,
                    'waiting-input': isWaitingInput(agent)
                  }"
                >
                  <div
                    class="tree-node-content agent-node-content"
                    @click.stop="toggleAgentExpanded(agent.agent_id)"
                  >
                    <span
                      class="tree-node-icon expand-arrow"
                      :class="{ expanded: expandedAgents.has(agent.agent_id) }"
                    >▶</span>
                    <span class="tree-node-icon agent-icon">
                      <svg v-if="agent.agent_type === 'code_agent'" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <path d="M5.5 4.5 2.5 8l3 3.5M10.5 4.5l3 3.5-3 3.5"/>
                        <path d="M9.5 3.5l-3 9"/>
                      </svg>
                      <svg v-else viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <rect x="3" y="5" width="10" height="7" rx="2"/>
                        <circle cx="5.5" cy="8.5" r="0.7" fill="currentColor" stroke="none"/>
                        <circle cx="10.5" cy="8.5" r="0.7" fill="currentColor" stroke="none"/>
                        <path d="M6 3.5 8 5l2-1.5"/>
                        <path d="M5 12v1.5M11 12v1.5"/>
                        <path d="M3 10H1.5M14.5 10H13"/>
                      </svg>
                    </span>
                    <span class="tree-node-text agent-name">{{ agent.name || agent.agent_id }}</span>
                    <span class="agent-status" :class="getStatusClass(agent)">{{ getStatusClass(agent) === 'stopped' ? '⏹' : getStatusClass(agent) === 'running' ? '▶' : '⏸' }}</span>
                    <span class="agent-node-id">{{ getNodeDisplayName(agent.node_id) }}</span>
                  </div>
                  <!-- Agent file tree -->
                  <div v-if="expandedAgents.has(agent.agent_id)" class="agent-file-tree">
                    <div
                      class="workspace-file-tree-root"
                      :class="{ 'drag-drop-target': fileTreeDropTargetPath === String(agent.working_dir || '').replace(/\/+$/, '') }"
                      @click.stop="ensureWorkspaceSidebarFileTree(agent)"
                      @contextmenu.prevent.stop="openFileTreeContextMenu(agent, null, $event)"
                      @dragover="handleFileTreeDragOver($event, agent.working_dir)"
                      @dragleave="handleFileTreeDragLeave(agent.working_dir)"
                      @drop="handleFileTreeDrop($event, agent.agent_id, agent.working_dir)"
                    >
                      {{ getWorkingDirDisplay(agent.working_dir) }}
                    </div>
                    <div v-if="!(fileTreeState.get(agent.agent_id)?.length > 0)" class="workspace-file-tree-empty">
                      Nothing to display in the current working directory
                    </div>
                    <div v-else class="workspace-file-tree-list" tabindex="0" :data-agent-id="agent.agent_id" @keydown="handleFileTreeKeydown($event, agent.agent_id)">
                      <div
                        v-for="visibleNode in getVisibleFileTreeNodes(agent.agent_id)"
                        :key="visibleNode.node.path"
                        class="tree-node workspace-tree-node"
                        :data-node-path="visibleNode.node.path"
                      >
                        <div
                          class="tree-node-content"
                          :class="{
                            'keyboard-selected': fileTreeSelectedAgentId === agent.agent_id && fileTreeSelectedPath === visibleNode.node.path,
                            'drag-drop-target': visibleNode.node.type === 'directory' && fileTreeDropTargetPath === String(visibleNode.node.path).replace(/\/+$/, '')
                          }"
                          :style="{ paddingLeft: `${8 + visibleNode.depth * 20}px` }"
                          draggable="true"
                          @click.stop="selectFileTreeNode(agent.agent_id, visibleNode.node); handleFileTreeNodeClick(agent.agent_id, visibleNode.node)"
                          @contextmenu.prevent.stop="openFileTreeContextMenu(agent, visibleNode.node, $event)"
                          @dragstart="handleFileTreeDragStart($event, agent.agent_id, visibleNode.node)"
                          @dragend="handleFileTreeDragEnd"
                          @dragover="visibleNode.node.type === 'directory' && handleFileTreeDragOver($event, visibleNode.node.path)"
                          @dragleave="visibleNode.node.type === 'directory' && handleFileTreeDragLeave(visibleNode.node.path)"
                          @drop="visibleNode.node.type === 'directory' && handleFileTreeDrop($event, agent.agent_id, visibleNode.node.path)"
                        >
                          <span
                            v-if="visibleNode.node.type === 'directory'"
                            class="tree-node-icon expand-arrow"
                            :class="{ expanded: visibleNode.node.expanded }"
                          >▶</span>
                          <span v-else class="tree-node-icon"></span>
                          <span
                            class="tree-node-icon"
                            :class="visibleNode.node.type === 'directory' ? 'folder-icon' : 'file-icon'"
                            v-html="getFileTypeIcon(visibleNode.node)"
                          ></span>
                          <span
                            class="tree-node-text"
                            :class="visibleNode.node.type === 'directory' ? 'directory' : 'file'"
                          >{{ visibleNode.node.name }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- Virtual directory sessions (directories opened without creating an Agent) -->
                <div
                  v-for="session in virtualWorkspaceSessions"
                  :key="session.agent_id"
                  class="workspace-agent-node virtual-dir"
                >
                  <div class="tree-node-content agent-node-content" @click.stop="toggleAgentExpanded(session.agent_id)">
                    <span
                      class="tree-node-icon expand-arrow"
                      :class="{ expanded: expandedAgents.has(session.agent_id) }"
                    >▶</span>
                    <span class="tree-node-icon agent-icon" v-html="UI_ICONS.monitor"></span>
                    <span class="tree-node-text agent-name">{{ session.agent.name }}</span>
                    <span class="agent-node-id">{{ getWorkingDirDisplay(session.agent.working_dir) }}</span>
                    <button
                      class="agent-node-remove"
                      title="Remove this directory"
                      @click.stop="removeWorkspaceDir(session.agent_id)"
                    >✕</button>
                  </div>
                  <div v-if="expandedAgents.has(session.agent_id)" class="agent-file-tree">
                    <div class="workspace-file-tree-root"
                      :class="{ 'drag-drop-target': fileTreeDropTargetPath === String(session.agent.working_dir || '').replace(/\/+$/, '') }"
                      @click.stop="ensureWorkspaceSidebarFileTree(session.agent)" @contextmenu.prevent.stop="openFileTreeContextMenu(session.agent, null, $event)"
                      @dragover="handleFileTreeDragOver($event, session.agent.working_dir)"
                      @dragleave="handleFileTreeDragLeave(session.agent.working_dir)"
                      @drop="handleFileTreeDrop($event, session.agent_id, session.agent.working_dir)">
                      {{ getWorkingDirDisplay(session.agent.working_dir) }}
                    </div>
                    <div v-if="!(fileTreeState.get(session.agent_id)?.length > 0)" class="workspace-file-tree-empty">
                      Nothing to display in the current working directory
                    </div>
                    <div v-else class="workspace-file-tree-list" tabindex="0" :data-agent-id="session.agent_id" @keydown="handleFileTreeKeydown($event, session.agent_id)">
                      <div
                        v-for="visibleNode in getVisibleFileTreeNodes(session.agent_id)"
                        :key="visibleNode.node.path"
                        class="tree-node workspace-tree-node"
                        :data-node-path="visibleNode.node.path"
                      >
                        <div
                          class="tree-node-content"
                          :class="{
                            'keyboard-selected': fileTreeSelectedAgentId === session.agent_id && fileTreeSelectedPath === visibleNode.node.path,
                            'drag-drop-target': visibleNode.node.type === 'directory' && fileTreeDropTargetPath === String(visibleNode.node.path).replace(/\/+$/, '')
                          }"
                          :style="{ paddingLeft: `${8 + visibleNode.depth * 20}px` }"
                          draggable="true"
                          @click.stop="selectFileTreeNode(session.agent_id, visibleNode.node); handleFileTreeNodeClick(session.agent_id, visibleNode.node)"
                          @contextmenu.prevent.stop="openFileTreeContextMenu(session.agent, visibleNode.node, $event)"
                          @dragstart="handleFileTreeDragStart($event, session.agent_id, visibleNode.node)"
                          @dragend="handleFileTreeDragEnd"
                          @dragover="visibleNode.node.type === 'directory' && handleFileTreeDragOver($event, visibleNode.node.path)"
                          @dragleave="visibleNode.node.type === 'directory' && handleFileTreeDragLeave(visibleNode.node.path)"
                          @drop="visibleNode.node.type === 'directory' && handleFileTreeDrop($event, session.agent_id, visibleNode.node.path)"
                        >
                          <span
                            v-if="visibleNode.node.type === 'directory'"
                            class="tree-node-icon expand-arrow"
                            :class="{ expanded: visibleNode.node.expanded }"
                          >▶</span>
                          <span v-else class="tree-node-icon"></span>
                          <span
                            class="tree-node-icon"
                            :class="visibleNode.node.type === 'directory' ? 'folder-icon' : 'file-icon'"
                            v-html="getFileTypeIcon(visibleNode.node)"
                          ></span>
                          <span
                            class="tree-node-text"
                            :class="visibleNode.node.type === 'directory' ? 'directory' : 'file'"
                          >{{ visibleNode.node.name }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- Stopped agents grouped by node -->
                <template v-for="(agents, nodeId) in stoppedAgentsByNode" :key="nodeId">
                  <div class="stopped-agents-group">
                    <div
                      class="stopped-agents-header"
                      @click="toggleStoppedNodeCollapse(nodeId)"
                    >
                      <span class="expand-arrow" :class="{ expanded: !isStoppedNodeCollapsed(nodeId) }">▶</span>
                      <span class="stopped-agents-title">{{ getNodeDisplayName(nodeId) }}Stopped Agents ({{ agents.length }})</span>
                    </div>
                    <div v-if="!isStoppedNodeCollapsed(nodeId)" class="stopped-agents-list">
                      <div
                        v-for="agent in agents"
                        :key="agent.agent_id"
                        class="workspace-agent-node stopped"
                        :class="{ 'selected': selectedAgentId === agent.agent_id }"
                      >
                        <div
                          class="tree-node-content agent-node-content"
                          @click.stop="toggleAgentExpanded(agent.agent_id)"
                        >
                          <span
                            class="tree-node-icon expand-arrow"
                            :class="{ expanded: expandedAgents.has(agent.agent_id) }"
                          >▶</span>
                          <span class="tree-node-icon agent-icon">
                            <svg v-if="agent.agent_type === 'code_agent'" viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                              <path d="M5.5 4.5 2.5 8l3 3.5M10.5 4.5l3 3.5-3 3.5"/>
                              <path d="M9.5 3.5l-3 9"/>
                            </svg>
                            <svg v-else viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                              <rect x="3" y="5" width="10" height="7" rx="2"/>
                              <circle cx="5.5" cy="8.5" r="0.7" fill="currentColor" stroke="none"/>
                              <circle cx="10.5" cy="8.5" r="0.7" fill="currentColor" stroke="none"/>
                              <path d="M6 3.5 8 5l2-1.5"/>
                              <path d="M5 12v1.5M11 12v1.5"/>
                              <path d="M3 10H1.5M14.5 10H13"/>
                            </svg>
                          </span>
                          <span class="tree-node-text agent-name">{{ agent.name || agent.agent_id }}</span>
                          <span class="agent-status" :class="getStatusClass(agent)">{{ getStatusClass(agent) === 'stopped' ? '⏹' : getStatusClass(agent) === 'running' ? '▶' : '⏸' }}</span>
                          <span class="agent-node-id">{{ getNodeDisplayName(agent.node_id) }}</span>
                        </div>
                        <!-- Agent file tree -->
                        <div v-if="expandedAgents.has(agent.agent_id)" class="agent-file-tree">
                          <div
                            class="workspace-file-tree-root"
                            :class="{ 'drag-drop-target': fileTreeDropTargetPath === String(agent.working_dir || '').replace(/\/+$/, '') }"
                            @click.stop="ensureWorkspaceSidebarFileTree(agent)"
                            @contextmenu.prevent.stop="openFileTreeContextMenu(agent, null, $event)"
                            @dragover="handleFileTreeDragOver($event, agent.working_dir)"
                            @dragleave="handleFileTreeDragLeave(agent.working_dir)"
                            @drop="handleFileTreeDrop($event, agent.agent_id, agent.working_dir)"
                          >
                            {{ getWorkingDirDisplay(agent.working_dir) }}
                          </div>
                          <div v-if="!(fileTreeState.get(agent.agent_id)?.length > 0)" class="workspace-file-tree-empty">
                            Nothing to display in the current working directory
                          </div>
                          <div v-else class="workspace-file-tree-list" tabindex="0" :data-agent-id="agent.agent_id" @keydown="handleFileTreeKeydown($event, agent.agent_id)">
                            <div
                              v-for="visibleNode in getVisibleFileTreeNodes(agent.agent_id)"
                              :key="visibleNode.node.path"
                              class="tree-node workspace-tree-node"
                              :data-node-path="visibleNode.node.path"
                            >
                              <div
                                class="tree-node-content"
                                :class="{
                                  'keyboard-selected': fileTreeSelectedAgentId === agent.agent_id && fileTreeSelectedPath === visibleNode.node.path,
                                  'drag-drop-target': visibleNode.node.type === 'directory' && fileTreeDropTargetPath === String(visibleNode.node.path).replace(/\/+$/, '')
                                }"
                                :style="{ paddingLeft: `${8 + visibleNode.depth * 20}px` }"
                                draggable="true"
                                @click.stop="selectFileTreeNode(agent.agent_id, visibleNode.node); handleFileTreeNodeClick(agent.agent_id, visibleNode.node)"
                                @contextmenu.prevent.stop="openFileTreeContextMenu(agent, visibleNode.node, $event)"
                                @dragstart="handleFileTreeDragStart($event, agent.agent_id, visibleNode.node)"
                                @dragend="handleFileTreeDragEnd"
                                @dragover="visibleNode.node.type === 'directory' && handleFileTreeDragOver($event, visibleNode.node.path)"
                                @dragleave="visibleNode.node.type === 'directory' && handleFileTreeDragLeave(visibleNode.node.path)"
                                @drop="visibleNode.node.type === 'directory' && handleFileTreeDrop($event, agent.agent_id, visibleNode.node.path)"
                              >
                                <span
                                  v-if="visibleNode.node.type === 'directory'"
                                  class="tree-node-icon expand-arrow"
                                  :class="{ expanded: visibleNode.node.expanded }"
                                >▶</span>
                                <span v-else class="tree-node-icon"></span>
                                <span
                                  class="tree-node-icon"
                                  :class="visibleNode.node.type === 'directory' ? 'folder-icon' : 'file-icon'"
                                  v-html="getFileTypeIcon(visibleNode.node)"
                                ></span>
                                <span
                                  class="tree-node-text"
                                  :class="visibleNode.node.type === 'directory' ? 'directory' : 'file'"
                                >{{ visibleNode.node.name }}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </template>
                <!-- No-agent hint (no longer shown when virtual directories have been opened via "Open Directory") -->
                <div v-if="agentList.length === 0 && virtualWorkspaceSessions.length === 0" class="workspace-file-tree-empty">
                  No Agents yet. Create an Agent first, or click "Open Directory" above.
                </div>
              </div>
            </div>
            <div v-else-if="workspaceSidebarView === 'search'" class="workspace-sidebar-content">
              <div class="workspace-global-search-panel">
                <select
                  v-if="activeAgents.length"
                  class="workspace-sidebar-agent-select"
                  :value="effectiveGlobalSearchAgentId || ''"
                  title="Select the Agent to search"
                  @change="globalSearchAgentId = $event.target.value"
                >
                  <option value="" disabled>Select Agent</option>
                  <option v-for="agent in activeAgents" :key="agent.agent_id" :value="agent.agent_id">
                    {{ agent.name || agent.agent_id }}
                  </option>
                </select>
                <div class="workspace-global-search-mode-tabs">
                  <button
                    class="workspace-global-search-mode-tab"
                    :class="{ active: globalSearchMode === 'content' }"
                    :disabled="globalSearchLoading"
                    @click="setGlobalSearchMode('content')"
                  >Content</button>
                  <button
                    class="workspace-global-search-mode-tab"
                    :class="{ active: globalSearchMode === 'filename' }"
                    :disabled="globalSearchLoading"
                    @click="setGlobalSearchMode('filename')"
                  >File name</button>
                </div>
                <input
                  v-model="globalSearchQuery"
                  class="workspace-global-search-input"
                  type="text"
                  :placeholder="globalSearchMode === 'filename' ? 'Fuzzy search by file name...' : 'Search file contents globally...'"
                  :disabled="globalSearchLoading || !effectiveGlobalSearchAgentId"
                  @keydown.enter.prevent="runGlobalSearch"
                >
                <input
                  v-model="globalSearchFileGlob"
                  class="workspace-global-search-input workspace-global-search-glob-input"
                  type="text"
                  placeholder="File filter, e.g. *.py,!tests/**"
                  :disabled="globalSearchLoading || !effectiveGlobalSearchAgentId"
                  @keydown.enter.prevent="runGlobalSearch"
                >
                <div class="workspace-global-search-toolbar">
                  <label class="workspace-global-search-toggle">
                    <input v-model="globalSearchCaseSensitive" type="checkbox">
                    <span>Case-sensitive</span>
                  </label>
                  <label v-if="globalSearchMode === 'content'" class="workspace-global-search-toggle">
                    <input v-model="globalSearchWholeWord" type="checkbox">
                    <span>Whole word</span>
                  </label>
                  <div class="workspace-global-search-actions">
                    <button class="icon-btn workspace-global-search-btn" @click="runGlobalSearch" :disabled="globalSearchLoading || !effectiveGlobalSearchAgentId || !globalSearchQuery.trim()" :title="globalSearchMode === 'filename' ? 'File name search' : 'Global search'" v-html="UI_ICONS.search"></button>
                    <button class="icon-btn workspace-global-search-btn" @click="clearGlobalSearch" :disabled="globalSearchLoading" title="Clear search">✕</button>
                  </div>
                </div>
              </div>
              <div class="workspace-global-search-results">
                <div class="workspace-global-search-summary">
                  <span v-if="globalSearchLoading">Searching...</span>
                  <span v-else-if="globalSearchError" class="error">{{ globalSearchError }}</span>
                  <span v-else-if="globalSearchExecuted && globalSearchMode === 'filename'">Found {{ fileSearchResults.length }} files (scanned {{ globalSearchTotalFiles }})</span>
                  <span v-else-if="globalSearchExecuted">Found {{ globalSearchTotalMatches }} matches in {{ globalSearchTotalFiles }} files</span>
                  <span v-else>{{ globalSearchMode === 'filename' ? 'Enter a keyword and press Enter to fuzzy search by file name' : 'Enter a keyword and press Enter to search globally in the current Agent working directory' }}</span>
                </div>
                <template v-if="globalSearchMode === 'filename'">
                  <div v-if="!globalSearchLoading && globalSearchExecuted && fileSearchResults.length === 0 && !globalSearchError" class="workspace-global-search-empty">
                    No matching files found
                  </div>
                  <button
                    v-for="result in fileSearchResults"
                    :key="result.file_path"
                    class="workspace-global-search-file-result"
                    @click="openFileSearchResult(result.file_path)"
                  >
                    <span class="workspace-global-search-file-result-name">{{ result.name }}</span>
                    <span class="workspace-global-search-file-result-path">{{ result.file_path }}</span>
                  </button>
                </template>
                <template v-else>
                  <div v-if="!globalSearchLoading && globalSearchExecuted && globalSearchResults.length === 0 && !globalSearchError" class="workspace-global-search-empty">
                    No matching results found
                  </div>
                  <div v-for="result in globalSearchResults" :key="result.file_path" class="workspace-global-search-file-group">
                    <div class="workspace-global-search-file-path" @click="openWorkspaceFile(resolveAgentRelativePath(result.file_path, effectiveGlobalSearchAgentId.value))">
                      {{ result.file_path }}
                      <span class="workspace-global-search-file-count">({{ result.matches.length }})</span>
                    </div>
                    <button
                      v-for="match in result.matches"
                      :key="`${result.file_path}:${match.line_number}:${match.match_start}`"
                      class="workspace-global-search-match"
                      @click="openGlobalSearchResult(result.file_path, match.line_number, match.match_start, match.match_end)"
                    >
                      <span class="workspace-global-search-line">{{ match.line_number }}</span>
                      <span class="workspace-global-search-text">
                        {{ match.line_content.slice(0, match.match_start) }}<mark>{{ match.line_content.slice(match.match_start, match.match_end) }}</mark>{{ match.line_content.slice(match.match_end) }}
                      </span>
                    </button>
                  </div>
                </template>
              </div>
            </div>
            <div v-else-if="workspaceSidebarView === 'manage'" class="workspace-sidebar-content">
              <ManageSidebar
                view="manage"
                :daemonSessions="topologyDaemonSessions"
                :extensionSessions="topologyExtensionSessions"
                :installedScripts="manageInstalledScripts"
                :gatewayScripts="manageGatewayScripts"
                @refresh="refreshManageCapabilities"
              />
            </div>
            <div v-else-if="workspaceSidebarView === 'timers'" class="workspace-sidebar-content">
              <ManageSidebar
                view="timers"
                :timers="manageTimers"
              />
            </div>
            <div v-else-if="workspaceSidebarView === 'plugins'" class="workspace-sidebar-content">
              <PluginSidebar
                :fetchWithAuth="fetchWithAuth"
                :gatewayUrl="gatewayUrl"
                :getHttpProtocol="getHttpProtocol"
                :showToast="showToast"
                :availableNodeOptions="availableNodeOptions"
              />
            </div>
            <div v-else-if="isPluginSidebarView(workspaceSidebarView) && activePluginSidebarComp" class="workspace-sidebar-content">
              <component
                :is="activePluginSidebarComp"
                :workingDir="pluginSidebarWorkingDir"
                :agentInfo="pluginActiveAgentInfo"
                :userInfo="auth.userInfo || null"
                :nodes="availableNodeOptions"
                :gatewayUrl="gatewayUrl"
                :fetchWithAuth="fetchWithAuth"
                :getHttpProtocol="getHttpProtocol"
                :showToast="showToast"
              />
            </div>
            <div v-else-if="isPluginToolView(workspaceSidebarView) && activePluginToolPanelComp" class="workspace-sidebar-content">
              <component
                :is="activePluginToolPanelComp"
                :workingDir="pluginSidebarWorkingDir"
                :agentInfo="pluginActiveAgentInfo"
                :userInfo="auth.userInfo || null"
                :nodes="availableNodeOptions"
                :gatewayUrl="gatewayUrl"
                :fetchWithAuth="fetchWithAuth"
                :getHttpProtocol="getHttpProtocol"
                :showToast="showToast"
              />
            </div>
            <div v-else-if="workspaceSidebarView === 'orchestration'" class="workspace-sidebar-content workspace-sidebar-orchestration">
              <OrchestrationView
                :pipelines="pipelineList"
                :activeId="activePipelineId"
                mode="compact"
                @select="selectPipeline"
                @jump-agent="onOrchestrationJumpAgent"
                @expand="openOrchestrationOverlay"
                @remove="removePipeline"
                @approve="handleApproval('approve', $event)"
                @reject="handleApproval('reject', $event)"
                @retry="handleApproval('retry', $event)"
              />
            </div>
            <div v-else class="workspace-sidebar-content">
              <div class="workspace-git-panel">
                <select
                  v-if="activeAgents.length"
                  class="workspace-sidebar-agent-select"
                  :value="effectiveGitAgentId || ''"
                  title='Select the Agent for Git; choose "Follow current session" to track the editor session'
                  @change="onGitAgentChange($event.target.value)"
                >
                  <option value="">Follow current session</option>
                  <option v-for="agent in activeAgents" :key="agent.agent_id" :value="agent.agent_id">
                    {{ agent.name || agent.agent_id }}
                  </option>
                </select>
                <!-- Git management directory: defaults to the Agent root directory, or any Git directory can be specified (reuses the "Open Directory" picker) -->
                <div class="workspace-git-dir-row">
                  <button class="workspace-open-dir-btn workspace-git-dir-btn" @click="openGitDirDialog" title="Select node and directory as the Git management target">
                    <span class="workspace-open-dir-icon" v-html="UI_ICONS.folder"></span>
                    <span>Select Git Directory</span>
                  </button>
                  <div v-if="gitCustomDir" class="workspace-git-dir-current" :title="gitCustomDir.path">
                    <span class="workspace-git-dir-label">Directory</span>
                    <span class="workspace-git-dir-path">{{ gitCustomDir.path }}</span>
                    <button class="icon-btn-small" @click="clearGitCustomDir" title="Clear custom directory, return to the Agent root directory">✕</button>
                  </div>
                </div>
                <div class="workspace-git-toolbar">
                  <span class="workspace-git-branch" :title="gitCurrentBranch || 'unknown branch'">
                    <svg viewBox="0 0 16 16" width="13" height="13" fill="currentColor" aria-hidden="true"><path d="M9.5 3.25a2.25 2.25 0 1 1 3 2.122V6A2.5 2.5 0 0 1 10 8.5H6a1 1 0 0 0-1 1v1.128a2.251 2.251 0 1 1-1.5 0V5.372a2.25 2.25 0 1 1 1.5 0v1.836A2.492 2.492 0 0 1 6 7h4a1 1 0 0 0 1-1v-.628A2.25 2.25 0 0 1 9.5 3.25Zm-6 0a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Zm8.25-.75a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5ZM4.25 12a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Z"/></svg>
                    <span class="workspace-git-branch-name">{{ gitCurrentBranch || 'no branch' }}</span>
                  </span>
                  <div class="workspace-git-toolbar-actions">
                    <template v-if="gitRangeSelectMode">
                      <span class="workspace-git-range-count" :title="'Selected ' + gitSelectedCommits.size + ' commits'">Selected {{ gitSelectedCommits.size }}</span>
                      <button class="icon-btn-small" @click="downloadGitPatch" :disabled="!gitSelectedCommits.size || gitPatchLoading" title="Download patch (a single commit as .patch, multiple as .tar.gz)">⬇</button>
                      <button class="icon-btn-small" @click="exitGitRangeSelect" title="Exit range selection">✕</button>
                    </template>
                    <template v-else>
                      <button class="icon-btn-small" @click="viewGitTargetDiff" title="View changes (diff of the current Git target Agent)">⇄</button>
                      <button class="icon-btn-small" @click="enterGitRangeSelect" title="Select a range to generate and download a patch">☑</button>
                      <button class="icon-btn-small" @click="refreshGitView" :disabled="gitLogLoading" title="Refresh">⟳</button>
                    </template>
                  </div>
                </div>
                <div class="workspace-git-summary">
                  <span v-if="gitLogLoading && !gitLog.length">Loading...</span>
                  <span v-else-if="gitLogError" class="error">{{ gitLogError }}</span>
                  <span v-else>{{ gitLogTotal !== null ? gitLogTotal : gitLog.length }} commits<span v-if="gitBranches.length"> · {{ gitBranches.length }} branches</span><span v-if="gitTags.length"> · {{ gitTags.length }} tags</span></span>
                </div>
                <div class="workspace-git-commit-list">
                  <template v-for="(commit, index) in gitLog" :key="commit.hash">
                    <div
                      class="workspace-git-commit"
                      :class="{ selected: gitSelectedCommit === commit.hash, 'range-selected': gitRangeSelectMode && gitSelectedCommits.has(commit.hash) }"
                      @click="gitRangeSelectMode ? toggleGitRangeSelect(commit) : toggleGitCommitDetail(commit)"
                      @contextmenu.prevent.stop="openGitCommitContextMenu(commit, $event)"
                    >
                      <div class="workspace-git-graph">
                        <svg viewBox="0 0 20 40" width="20" height="40" aria-hidden="true">
                          <line x1="10" y1="0" x2="10" y2="40" stroke="currentColor" stroke-width="1.5" class="git-graph-line" />
                          <circle cx="10" cy="20" :r="commit.parents && commit.parents.length > 1 ? 5 : 4" class="git-graph-dot" :class="{ 'git-graph-merge': commit.parents && commit.parents.length > 1 }" />
                        </svg>
                      </div>
                      <div class="workspace-git-commit-body">
                        <div class="workspace-git-commit-subject" :title="formatGitCommitTooltip(commit)">{{ commit.subject }}</div>
                        <div class="workspace-git-commit-meta">
                          <span class="workspace-git-refs" v-if="commit.refs && commit.refs.length">
                            <span v-for="ref in commit.refs" :key="ref" class="git-ref" :class="gitRefClass(ref)">{{ ref }}</span>
                          </span>
                          <span class="workspace-git-author">{{ commit.author }}</span>
                          <span class="workspace-git-hash">{{ shortGitHash(commit.hash) }}</span>
                          <span class="workspace-git-time">{{ formatGitRelativeTime(commit.date) }}</span>
                          <button
                            v-if="windowWidth < 768"
                            class="workspace-git-detail-btn"
                            title="View full commit info"
                            @click.stop="showGitCommitInfoModal(commit)"
                          >Details</button>
                        </div>
                        <div v-if="gitSelectedCommit === commit.hash" class="workspace-git-commit-detail" @click.stop>
                          <div v-if="gitCommitDetailLoading" class="workspace-git-detail-empty">Loading file list...</div>
                          <div v-else-if="!gitCommitFiles.length" class="workspace-git-detail-empty">No file changes</div>
                          <template v-else>
                            <div class="workspace-git-detail-summary">{{ gitCommitFiles.length }} files changed</div>
                            <button
                              v-for="file in gitCommitFiles"
                              :key="file.path"
                              class="workspace-git-file"
                              :class="{ active: gitSelectedFile === file.path }"
                              @click="viewGitFileDiff(commit.hash, file.path)"
                            >
                              <span class="workspace-git-file-status" :class="'git-status-' + gitFileStatus(file)">{{ gitFileStatus(file) }}</span>
                              <span class="workspace-git-file-path" :title="file.path">{{ file.path }}</span>
                              <span class="workspace-git-file-stat">
                                <span v-if="file.additions" class="git-add-stat">+{{ file.additions }}</span>
                                <span v-if="file.deletions" class="git-del-stat">-{{ file.deletions }}</span>
                              </span>
                            </button>

                          </template>
                        </div>
                      </div>
                    </div>
                  </template>
                  <div v-if="!gitLogLoading && !gitLogError && !gitLog.length" class="workspace-git-empty">No commits yet</div>
                  <button
                    v-if="gitLogHasMore && !gitLogLoading"
                    class="workspace-git-load-more"
                    @click="fetchGitLog(true)"
                  >Load more</button>
                </div>
              </div>
            </div>
          </aside>
        </template>
<!-- The workspace is always a pane tree (splits >= 1): the only leaf hosts the main-area view,
     WorkspacePanel always renders through the pane tree; the old unsplit single-instance rendering no longer exists. -->
        <template #pane-tree>
          <WorkspacePaneTree
            :node="workspacePaneTree"
            :activePaneId="activePaneId"
            :maximizedPaneId="maximizedPaneId"
            :canSplit="windowWidth > 768"
            :getTitle="getWorkspacePaneTitle"
            :getStatus="getWorkspacePaneStatus"
            @activate="activateWorkspacePane"
            @split="splitWorkspacePane"
            @close="closeWorkspacePane"
            @maximize="toggleMaximizeWorkspacePane"
            @startResize="startWorkspacePaneResize"
          >
            <template #pane-content="{ pane, active }">
              <div class="workspace-pane-content-slot">
                <template v-if="pane.view === 'empty'">
<!-- Empty pane: a newly split area carries no attributes (neither file nor session),
      only shows a neutral placeholder, waiting for the user to explicitly open a file/session. -->
                  <div class="workspace-pane-placeholder" @click="activateWorkspacePane(pane.id)">
                    <div class="workspace-placeholder-icon">▢</div>
                    <div class="workspace-placeholder-title">Empty area</div>
                    <div class="workspace-placeholder-text">Open a file or click an Agent on the left, and its content will appear in this area.</div>
                  </div>
                </template>
                <template v-else-if="pane.view === 'file'">
<!-- File tabs: rendered at the top of this pane itself (no longer spanning the whole workspace).
     When split, each pane uses its own independent tab list (getPaneTabs);
     closing one pane's tabs does not affect other panes. -->
                  <div v-if="getPaneTabs(pane.id).length > 0" class="workspace-tabs workspace-pane-tabs" @mousedown="activateWorkspacePane(pane.id)">
                    <div
                      v-for="tab in getPaneTabs(pane.id)"
                      :key="tab.path"
                      class="workspace-tab"
                      :class="{ active: workspaceViewPanes.get(pane.id) === tab.path }"
                      @click="activateWorkspacePane(pane.id); activateWorkspaceTab(tab.path)"
                      @contextmenu.prevent.stop="openTabContextMenu(pane.id, tab.path, $event)"
                    >
                      <span class="workspace-tab-name">{{ tab.name }}</span>
                      <span v-if="tab.isDirty" class="workspace-tab-dirty">●</span>
                      <button class="workspace-tab-close" tabindex="-1" @mousedown.prevent @click.stop="closeWorkspaceTab(tab.path, pane.id)">✕</button>
                    </div>
                    <!-- Each pane has its own save / read-only toggle: applies to the current file in this pane -->
                    <div class="workspace-pane-actions">
                      <button
                        class="workspace-pane-action"
                        :disabled="!workspaceViewPanes.get(pane.id)"
                        tabindex="-1"
                        @mousedown.prevent
                        @click.stop="savePaneWorkspaceFile(pane.id)"
                        title="Save the file in this pane"
                      ><span v-html="UI_ICONS.save"></span></button>
                      <button
                        class="workspace-pane-action"
                        :class="{ editable: isWorkspaceEditable }"
                        :disabled="!workspaceViewPanes.get(pane.id)"
                        tabindex="-1"
                        @mousedown.prevent
                        @click.stop="toggleWorkspaceEditable()"
                        :title="isWorkspaceEditable ? 'Switch to read-only mode' : 'Switch to edit mode'"
                      ><span v-html="isWorkspaceEditable ? UI_ICONS.unlock : UI_ICONS.lock"></span></button>
                    </div>
                  </div>
<!-- Multiple Monaco instances: each file pane renders a real editor container (editable);
     inactive panes just lack focus, no longer read-only snapshots. -->
                  <div
                    :ref="el => setSplitWorkspaceContainerRef(pane.id, el)"
                    :data-pane-id="pane.id"
                    class="workspace-monaco-container"
                    @mousedown="activateWorkspacePane(pane.id)"
                  ></div>
                </template>
                <template v-else-if="pane.view === 'diff'">
                  <!-- diff leaf: a Git commit file diff as standalone pane content (one independent DiffEditor instance per pane) -->
                  <div class="workspace-pane-diff-wrap" @mousedown="activateWorkspacePane(pane.id)">
                    <div v-if="pane.diff" class="workspace-diff-view">
                      <div class="workspace-diff-header">
                        <span class="workspace-diff-title" :title="(pane.diff.filePath || '') + ' (click to open in the editor)'" @click="onDiffTitleClick($event, pane)">{{ pane.diff.filePath }}</span>
                        <span v-if="pane.diff.commitHash" class="workspace-diff-hash">{{ pane.diff.commitHash.slice(0, 7) }}</span>
                        <span v-if="pane.diff.truncated" class="workspace-diff-truncated">(truncated)</span>
                        <button class="workspace-diff-nav" @click.stop="navigatePaneDiff(pane.id, 'prev')" title="Previous difference">▲</button>
                        <button class="workspace-diff-nav" @click.stop="navigatePaneDiff(pane.id, 'next')" title="Next difference">▼</button>
                        <button class="workspace-diff-toggle" @click.stop="togglePaneDiffShowFull(pane.id)" :title="pane.diff.showFull ? 'Show only the changed context' : 'Show the full file'">
                          {{ pane.diff.showFull ? 'Context only' : 'Full' }}
                        </button>
                        <button class="workspace-diff-toggle" @click.stop="togglePaneDiffSideBySide(pane.id)">
                          {{ pane.diff.sideBySide ? 'Inline' : 'Side by side' }}
                        </button>
                        <button class="workspace-diff-close" @click.stop="closePaneDiff(pane.id)" title="Close diff">✕</button>
                      </div>
                      <div v-if="pane.diff.loading" class="workspace-diff-status">Loading diff...</div>
                      <div v-else-if="pane.diff.error" class="workspace-diff-status error">{{ pane.diff.error }}</div>
                      <div
                        v-else
                        :ref="el => setDiffContainerRef(pane.id, el)"
                        :data-diff-pane-id="pane.id"
                        class="workspace-diff-monaco"
                      ></div>
                    </div>
                    <div v-else class="workspace-pane-placeholder" @click="activateWorkspacePane(pane.id)">
                      <div class="workspace-placeholder-icon" v-html="UI_ICONS.receipt"></div>
                      <div class="workspace-placeholder-title">Empty diff area</div>
                      <div class="workspace-placeholder-text">Click a file inside a commit in the "Git" view on the left to view its diff here.</div>
                    </div>
                  </div>
                </template>
                <template v-else-if="pane.view === 'chat'">
                  <!-- chat leaf: reuses the full wiring of the chat area in the editor main region (host singleton, carried by at most one pane) -->
                  <div class="workspace-pane-embed-wrap" @mousedown="activateWorkspacePane(pane.id)">
                    <ChatPanel
                      :visible="true"
                      :interaction="chatPanelInteraction"
                      :panelStyle="{}"
                      :socket="socket"
                      :rooms="chatRooms"
                      :clients="chatClients"
                      :roomMembers="chatRoomMembers"
                      :myClientId="myClientId"
                      :isAdmin="auth.userInfo?.is_admin"
                      :currentUserId="auth.userInfo?.user_id"
                      :activeRoomId="activeChatRoomId"
                      :activePrivateId="activePrivateClientId"
                      :resizeDirections="[]"
                      :unreadCount="chatUnreadCount" :unreadMap="chatUnreadMap" :joinedRooms="chatJoinedRooms"
                      :myName="chatName"
                      :collapsed="chatPanelCollapsed"
                      :sidebarWidth="chatSidebarWidth"
                      :messages="activePrivateClientId ? (chatMessages['private_' + activePrivateClientId] || []) : (chatMessages[activeChatRoomId] || [])"
                      :embedded="true"
                      @focus="focusWindow"
                      @startMove="startChatPanelMove"
                      @close="setActivePaneView('file')"
                      @createRoom="createChatRoom"
                      @joinRoom="joinChatRoom"
                      @sendMessage="sendChatMessage"
                      @selectPrivate="selectPrivateClient"
                      @startResize="startChatPanelResize"
                      @toggleCollapse="toggleChatPanelCollapse"
                      @leaveRoom="leaveChatRoom"
                      @deleteRoom="deleteChatRoom"
                      @renameRoom="renameChatRoom"
                      @startSidebarResize="startChatSidebarResize"
                      @clearMessages="clearChatMessages"
                    />
                  </div>
                </template>
                <template v-else-if="pane.view === 'terminal'">
                  <!-- terminal leaf: reuses the full wiring of the terminal in the editor main region (host singleton, carried by at most one pane) -->
                  <div class="workspace-pane-embed-wrap" @mousedown="activateWorkspacePane(pane.id)">
                    <TerminalPanel
                      :visible="true"
                      :active="isPaneActive(pane)"
                      :interaction="terminalPanelInteraction"
                      :panelStyle="{}"
                      :nodeOptions="filteredNodeOptionsForCreateAgent"
                      :selectedNodeId="selectedTerminalNodeId"
                      :socket="socket"
                      :sessions="terminalSessions"
                      :activeId="activeTerminalId"
                      :resizeDirections="[]"
                      :formatNodeLabel="formatNodeOptionLabel"
                      :embedded="true"
                      @focus="focusWindow"
                      @startMove="startTerminalPanelMove"
                      @update:selectedNodeId="selectedTerminalNodeId = $event"
                      @createTerminal="createTerminalForSelectedNode"
                      @syncTerminals="restoreTerminalSessions"
                      @close="setActivePaneView('file')"
                      @switch="switchTerminal"
                      @closeTerminal="closeTerminal"
                      @shareTerminal="openTerminalShareDialog"
                      @setHostRef="setTerminalHostRef"
                      @startResize="startTerminalPanelResize"
                    />
                  </div>
                </template>
                <template v-else>
                  <!-- session leaf: renders a real session panel (reuses the same wiring as #main-view) -->
                  <div v-if="getPanePanel(pane)" class="workspace-pane-session-wrap" @mousedown="activateWorkspacePane(pane.id)">
                    <SessionPanel
                      :ref="el => setSessionPanelRef(getPanePanel(pane)?.id, el)"
                      :embedded="true"
                      :agent="getPanelAgent(getPanePanel(pane))"
                      :messages="getPanelMessages(getPanePanel(pane))"
                      :input-text="getPanelInputText(getPanePanel(pane))"
                      :input-mode="getPanelInputMode(getPanePanel(pane))"
                      :input-tip="getPanelInputTip(getPanePanel(pane))"
                      :is-password="getPanelInputPassword(getPanePanel(pane))"
                      :is-input-disabled="getPanelInputDisabled(getPanePanel(pane))"
                      :is-waiting-multi-disabled="getPanelWaitingMultiDisabled(getPanePanel(pane))"
                      :has-buffered-input="getPanelHasBufferedInput(getPanePanel(pane))"
                      :agent-status="getPanelAgentStatus(getPanePanel(pane))"
                      :active="isPaneActive(pane)"
                      :confirm-data="getPanelConfirmData(getPanePanel(pane))"
                      :interaction="{ active: false }"
                      :resizeDirections="[]"
                      :panelStyle="{}"
                      @confirm="handlePanelConfirm(getPanePanel(pane))"
                      @cancel-confirm="handlePanelCancelConfirm(getPanePanel(pane))"
                      @activate="activateWorkspacePane(pane.id)"
                      @close-agent="closeAgentInPanel(getPanePanel(pane).id)"
                      @close-panel="setActivePaneView('file')"
                      @send="sendFromPanel(getPanePanel(pane))"
                      @complete="completeFromPanel(getPanePanel(pane))"
                      @open-completions="openCompletionsFromPanel(getPanePanel(pane))"
                      @input-change="handlePanelInputChange(getPanePanel(pane), $event)"
                      @keydown="handlePanelKeydown(getPanePanel(pane), $event)"
                      @paste="handlePanelPaste(getPanePanel(pane), $event)"
                      @show-buffer="openBufferPanel(getPanePanel(pane))"
                      @clear-buffer="clearBufferFromPanel(getPanePanel(pane))"
                      @set-output-list="setPanelOutputList(getPanePanel(pane), $event)"
                      @set-terminal-ref="(executionId, el, agentId) => setPanelTerminalRef(getPanePanel(pane), executionId, el, agentId)"
                      @show-toast="showToast"
                      @context-menu="onPanelContextMenu(getPanePanel(pane), $event)"
                      @open-diff-file="onOpenDiffFileFromMessage"
                    />
                  </div>
                  <div v-else class="workspace-pane-placeholder" @click="activateWorkspacePane(pane.id)">
                    <div class="workspace-placeholder-icon" v-html="UI_ICONS.folderStack"></div>
                    <div class="workspace-placeholder-title">Empty Session Area</div>
                    <div class="workspace-placeholder-text">Click an Agent in the "Agent List" on the left to open a session in this area.</div>
                  </div>
                </template>
              </div>
            </template>
          </WorkspacePaneTree>
        </template>
      </WorkspacePanel>

      <!-- Empty state: pet hall when there are no visible Panels (mini pets of all Agents swim freely) -->
      <div v-if="hasNoPanel" class="empty-stage">
        <PetLobby
          ref="petLobbyRef"
          :agents="agentList"
          :agentsLoaded="agentListLoaded"
          :nodes="availableNodeOptions"
          :getStatusClass="getStatusClass"
          :getInputState="getLobbyInputState"
          :getLatestOutput="getLobbyLatestOutput"
          :historyNav="onLobbyHistoryNav"
          :getNodeDisplayName="getNodeDisplayName"
          :getWorkingDirDisplay="getWorkingDirDisplay"
          :gatewayAddress="gatewayAddressDisplay"
          :connectionStatus="connectionStatus"
          :connectionLabel="connectionLabel"
          :currentUserName="auth.userInfo?.display_name || auth.userInfo?.username || ''"
          :downloadExtension="downloadBrowserExtension"
          :checkExtensionVersion="fetchBrowserExtensionVersion"
          :checkDaemonSessions="fetchDaemonSessions"
          :checkExtensionSessions="fetchBrowserExtensionSessions"
          :localDaemonOnline="localDaemonOnline"
          :contextActions="lobbyContextActions"
          :agentGroups="agentGroups"
          @selectAgent="onLobbySelectAgent"
          @sendInput="sendLobbyInput"
          @complete="onLobbyComplete"
          @openCompletions="onLobbyOpenCompletions"
          @activePetChange="lobbyActiveAgentId = $event"
          @activeNodeChange="lobbyActiveNodeId = $event"
          @createAgentOnNode="onLobbyCreateAgentOnNode"
          @openOnboarding="(tourId) => startOnboarding(tourId || 'welcome')"
          @contextAgent="onLobbyContextAgent"
          @contextRun="onLobbyContextRun"
          @nodeContextRun="onLobbyNodeContextRun"
          @renameNode="onLobbyRenameNode"
          @addAgentToGroup="onLobbyAddAgentToGroup"
          @removeAgentFromGroup="onLobbyRemoveAgentFromGroup"
        />
      </div>
    </main>

    <!-- Confirmation dialog (popup): Teleport to body to avoid being trapped by .app's isolation stacking context, ensuring it appears above other popups -->
    <Teleport to="body">
      <ConfirmDialog
        :visible="!!confirmDialog"
        :message="confirmDialog?.message || ''"
        :defaultConfirm="confirmDialog?.defaultConfirm ?? true"
        @confirm="handleConfirmDialogConfirm"
        @cancel="handleConfirmDialogCancel"
      />
    </Teleport>

    <!-- Bottom input area -->

    </div> <!-- End main-content-wrapper -->

    <!-- Cache management popup -->
    <BufferPanel
      :visible="showBufferPanel"
      :hasBufferedInput="hasBufferedInput"
      :editText="bufferEditText"
      @update:editText="bufferEditText = $event"
      @close="showBufferPanel = false"
      @load="loadBufferToInput"
      @clear="clearBuffer"
      @save="saveBufferEdit"
    />

    <!-- Completion list popup -->
    <CompletionsModal
      ref="completionsModalRef"
      :visible="showCompletions"
      :searchText="completionSearch"
      :filteredCompletions="filteredCompletions"
      :selectedIndex="selectedIndex"
      @update:searchText="completionSearch = $event"
      @close="closeCompletionsWithoutSelect()"
      @select="(item) => insertCompletion(item, completionAgentId)"
      @keydown="handleCompletionKeydown"
    />

    <!-- Create Agent popup -->
    <CreateAgentModal
      :visible="showCreateAgentModal"
      :nodeOptions="filteredNodeOptionsForCreateAgent"
      :nodeId="newAgentNodeId"
      @update:nodeId="newAgentNodeId = $event"
      :agentType="newAgentType"
      @update:agentType="newAgentType = $event"
      :agentName="newAgentName"
      @update:agentName="newAgentName = $event"
      :modelGroups="modelGroups"
      :modelGroup="newAgentModelGroup"
      @update:modelGroup="newAgentModelGroup = $event"
      :workDir="newAgentDir"
      @update:workDir="newAgentDir = $event"
      :codeAgentWorktree="newCodeAgentWorktree"
      @update:codeAgentWorktree="newCodeAgentWorktree = $event"
      :quickMode="newAgentQuickMode"
      @update:quickMode="newAgentQuickMode = $event"
      :restoreSession="newAgentRestoreSession"
      @update:restoreSession="newAgentRestoreSession = $event"
      :noInteractionMode="newAgentNoInteractionMode"
      @update:noInteractionMode="newAgentNoInteractionMode = $event"
      :taskDescription="newAgentTaskDescription"
      @update:taskDescription="newAgentTaskDescription = $event"
      :proxyNode="newAgentProxyNode"
      @update:proxyNode="newAgentProxyNode = $event"
      :formatNodeLabel="formatNodeOptionLabel"
      :noNodeAccess="userAccessibleNodes !== null && userAccessibleNodes.length === 0"
      :createError="newAgentCreateError"
      :accessAclRead="newAgentAccessAclRead"
      @update:accessAclRead="newAgentAccessAclRead = $event"
      :accessAclInteract="newAgentAccessAclInteract"
      :userOptions="availableUserOptions.filter(u => !u.is_admin && u.user_id !== auth.userInfo?.user_id)"
      :recentWorkDirs="recentWorkDirs"
      :currentNodeId="newAgentNodeId"
      :dirDialogOpen="showDirDialog"
      @cancel="showCreateAgentModal = false"
      @create="createAgent"
      @selectDir="openDirDialog"
    />

    <!-- One-sentence create Agent popup -->
    <QuickCreateAgentModal
      :visible="showQuickCreateAgentModal"
      :loading="quickCreateAgentLoading"
      :error="quickCreateAgentError"
      @close="showQuickCreateAgentModal = false"
      @submit="submitQuickCreateAgent"
      @open-full="openFullCreateAgentFromQuick"
    />

    <!-- Rename Agent popup -->
    <RenameAgentModal
      :visible="showRenameAgentModal"
      :name="renameAgentName"
      @update:name="renameAgentName = $event"
      @cancel="showRenameAgentModal = false"
      @confirm="confirmRename"
    />

    <!-- Generic input popup (e.g. naming new files/folders) -->
    <InputPromptModal
      :visible="inputPrompt.visible"
      :title="inputPrompt.title"
      :label="inputPrompt.label"
      :placeholder="inputPrompt.placeholder"
      :model-value="inputPrompt.value"
      :error="inputPrompt.error"
      @update:model-value="inputPrompt.value = $event"
      @cancel="cancelInputPrompt"
      @confirm="confirmInputPrompt"
    />

    <!-- Agent ACL edit popup -->
    <div v-if="showEditAccessModal" class="modal-overlay" @click.self="showEditAccessModal = false">
      <div class="modal-content" style="max-width: 480px;">
        <h3>Permission Management - {{ editingAccessAgent?.name || editingAccessAgent?.agent_id }}</h3>
        <div class="form-group">
          <label>Users who can view (read)</label>
          <div class="acl-user-list">
            <label v-for="user in filteredUserOptionsForAcl" :key="user.user_id" class="checkbox-label">
              <input type="checkbox" :value="user.user_id" v-model="editAccessRead" />
              {{ user.display_name || user.user_id }}
            </label>
            <div v-if="filteredUserOptionsForAcl.length === 0" class="form-help">No selectable users</div>
          </div>
        </div>
        <div class="form-group">
          <label>Users who can interact (interact)</label>
          <div class="acl-user-list">
            <label v-for="user in filteredUserOptionsForAcl" :key="user.user_id" class="checkbox-label">
              <input type="checkbox" :value="user.user_id" v-model="editAccessInteract" />
              {{ user.display_name || user.user_id }}
            </label>
            <div v-if="filteredUserOptionsForAcl.length === 0" class="form-help">No selectable users</div>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn secondary" @click="showEditAccessModal = false">Cancel</button>
          <button class="btn primary" @click="saveAgentAccess">Save</button>
        </div>
      </div>
    </div>

    <!-- Terminal sharing popup: owner shares the terminal with other users (read-only read / interactable interact) -->
    <div v-if="showTerminalShareModal" class="modal-overlay" @click.self="showTerminalShareModal = false">
      <div class="modal-content" style="max-width: 480px;">
        <h3>Share Terminal</h3>
        <div class="form-group">
          <label>Users who can view (read)</label>
          <div class="acl-user-list">
            <label v-for="user in filteredUserOptionsForTerminalShare" :key="user.user_id" class="checkbox-label">
              <input type="checkbox" :value="user.user_id" v-model="terminalShareRead" />
              {{ user.display_name || user.user_id }}
            </label>
            <div v-if="filteredUserOptionsForTerminalShare.length === 0" class="form-help">No selectable users</div>
          </div>
        </div>
        <div class="form-group">
          <label>Users who can interact (interact)</label>
          <div class="acl-user-list">
            <label v-for="user in filteredUserOptionsForTerminalShare" :key="user.user_id" class="checkbox-label">
              <input type="checkbox" :value="user.user_id" v-model="terminalShareInteract" />
              {{ user.display_name || user.user_id }}
            </label>
            <div v-if="filteredUserOptionsForTerminalShare.length === 0" class="form-help">No selectable users</div>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn secondary" @click="showTerminalShareModal = false">Cancel</button>
          <button class="btn primary" @click="saveTerminalShare">Save</button>
        </div>
      </div>
    </div>

    <!-- Directory selection dialog -->
    <DirectoryDialog
      ref="dirDialogRef"
      :class="{ 'dir-dialog-above-orchestrate': dirDialogContext === 'orchestrate' }"
      :visible="showDirDialog"
      :currentPath="currentDirPath"
      :selectedDir="selectedDir"
      :searchText="dirSearchText"
      :filteredDirs="filteredDirList"
      @update:searchText="dirSearchText = $event"
      @cancel="cancelDirDialog"
      @confirm="confirmDirectory"
      @refresh="fetchDirectories"
      @go-parent="goToParentDir"
      @select="selectDirectory"
      @enter="enterDirectory"
      @search-keydown="handleDirSearchKeydown"
    />
    <!-- Directory tree: open a directory by node (without creating an Agent) -->
    <!-- Single popup layout: node + path selection on top, embedded directory filter below (reuses the DirectoryDialog logic for creating an Agent) -->
    <div v-if="showOpenDirDialog" class="open-dir-overlay" @click.self="closeOpenDirDialog">
      <div class="open-dir-modal">
        <div class="open-dir-header">
          <h2>{{ openDirSource === 'git' ? 'Select Git Directory' : (openDirSource === 'plugin' ? 'Select Directory' : 'Open Directory') }}</h2>
          <button class="open-dir-close" @click="closeOpenDirDialog">×</button>
        </div>
        <div class="open-dir-body">
          <label class="open-dir-label">Node</label>
          <select
            class="open-dir-node-select"
            :value="openDirNodeId"
            @change="onOpenDirNodeChange($event.target.value)"
          >
            <option v-if="!filteredNodeOptionsForCreateAgent.length" value="" disabled>No nodes available</option>
            <option v-for="node in filteredNodeOptionsForCreateAgent" :key="node.node_id" :value="node.node_id">
              {{ getNodeDisplayName(node.node_id) }}
            </option>
          </select>
          <label class="open-dir-label">Directory path</label>
          <input
            ref="openDirInput"
            v-model="openDirPath"
            class="open-dir-path-input"
            type="text"
            placeholder="Absolute path, e.g. /home/user/project; you can also browse and select below"
            @keydown.enter.prevent="confirmOpenDir"
          >
          <!-- Directory filter: embedded DirectoryDialog (identical to the directory selection logic for creating an Agent) -->
          <div class="open-dir-browse-wrap">
            <DirectoryDialog
              ref="openDirDialogRef"
              embedded
              :visible="showOpenDirDialog"
              :currentPath="currentDirPath"
              :selectedDir="selectedDir"
              :searchText="dirSearchText"
              :filteredDirs="filteredDirList"
              @update:searchText="dirSearchText = $event"
              @refresh="fetchDirectories"
              @go-parent="goToParentDir"
              @select="onOpenDirSelect"
              @enter="enterDirectory"
              @search-keydown="handleDirSearchKeydown"
            />
          </div>
        </div>
        <div class="open-dir-actions">
          <button class="btn secondary" @click="closeOpenDirDialog">Cancel</button>
          <button class="btn primary" @click="confirmOpenDir">{{ openDirSource === 'git' ? 'OK' : (openDirSource === 'plugin' ? 'Select' : 'Open') }}</button>
        </div>
      </div>
    </div>
    <!-- Connection popup -->
    <ConnectModal
      :visible="showConnectModal"
      :connecting="connecting"
      :errorMessage="connectErrorMessage"
      :gatewayUrl="gatewayUrl"
      :password="auth.password"
      :username="username"
      @update:gatewayUrl="gatewayUrl = $event"
      @update:password="auth.password = $event"
      @update:username="username = $event"
      @connect="connect"
    />

    <!-- Settings popup -->
    <SettingsModal
      :visible="showSettingsModal"
      :autoLoginEnabled="autoLoginEnabled"
      :notifyOnExit="notifyOnExit"
      :notifyOnInput="notifyOnInput"
      :historyStorage="historyStorage"
      :socket="socket"
      :auth="auth"
      :fetchWithAuth="fetchWithAuth"
      :gatewayUrl="gatewayUrl"
      :getHttpProtocol="getHttpProtocol"
      :showToast="showToast"
      :nodeOptions="availableNodeOptions"
      :nodeDisplayNames="nodeDisplayNames"
      :hideWorkingDir="hideWorkingDir"
      :autoInstallBrowserExt="autoInstallBrowserExt"
      :terminalName="terminalName"
      :daemonPort="daemonPort"
      @update:visible="showSettingsModal = $event"
      @update:autoLoginEnabled="autoLoginEnabled = $event"
      @saveAutoLoginSetting="saveAutoLoginSetting"
      @update:notifyOnExit="notifyOnExit = $event"
      @update:notifyOnInput="notifyOnInput = $event"
      @saveNotifySettings="saveNotifySettings"
      @saveNodeDisplayNames="saveNodeDisplayNames"
      @update:hideWorkingDir="hideWorkingDir = $event"
      @saveHideWorkingDirSetting="saveHideWorkingDirSetting"
      @update:autoInstallBrowserExt="autoInstallBrowserExt = $event"
      @saveAutoInstallBrowserExtSetting="saveAutoInstallBrowserExtSetting"
      @update:terminalName="terminalName = $event"
      @saveTerminalNameSetting="saveTerminalNameSetting"
      @update:daemonPort="daemonPort = $event"
      @saveDaemonPortSetting="saveDaemonPortSetting"
      @confirmClearHistory="confirmClearHistory"
      @disconnectAll="disconnectAll"
    />

    <!-- About popup -->
    <AboutModal
      :visible="showAboutModal"
      :frontendVersion="APP_VERSION"
      :backendVersion="aboutBackendVersion"
      :nodes="aboutNodes"
      :daemonSessions="aboutDaemonSessions"
      :browserExtSessions="aboutBrowserExtSessions"
      @update:visible="showAboutModal = $event"
    />

    <!-- Management panel -->
    <AdminPanel
      :visible="showAdminPanel"
      ref="adminPanelRef"
      :auth="auth"
      :fetchWithAuth="fetchWithAuth"
      :gatewayUrl="gatewayUrl"
      :showToast="showToast"
      :getHttpProtocol="getHttpProtocol"
      :availableNodeOptions="availableNodeOptions"
      :isRestartingGateway="isRestartingGateway"
      :isSyncingConfig="isSyncingConfig"
      :isUpdatingCode="isUpdatingCode"
      :getToken="getAuthToken"
      :pluginAdminTabs="pluginAdminTabs"
      :pluginExtensions="pluginExtensions"
      @update:visible="showAdminPanel = $event"
      @confirmRestartGateway="handleRestartGateway"
      @confirmRestartAllNodes="confirmRestartAllNodes"
      @syncConfig="handleSyncConfig"
      @updateCodeToMain="handleUpdateCodeToMain"
      @confirmUpdateCodeToMain="confirmUpdateCodeToMain"
    />

    <!-- Session selection dialog -->
    <SessionDialog
      :visible="showSessionDialog"
      :sessions="availableSessions"
      :selectedSession="selectedSession"
      @update:selectedSession="selectedSession = $event"
      @restore="restoreSession"
      @cancel="cancelSessionDialog"
    />

    <!-- Diff floating window: file list on the left + diff comparison of the selected file on the right -->
    <div v-if="showDiffModal" class="diff-modal-overlay" @click.self="showDiffModal = false">
      <div class="diff-modal">
        <div class="diff-modal-header">
          <h3>Code Changes<span v-if="diffFiles.length" class="diff-modal-count">({{ diffFiles.length }} files)</span></h3>
          <button class="icon-btn" @click="showDiffModal = false" title="Close">✕</button>
        </div>
        <div v-if="diffLoading" class="diff-loading">Loading...</div>
        <div v-else-if="diffError" class="diff-error">{{ diffError }}</div>
        <div v-else-if="diffFiles.length === 0" class="diff-empty">No changes</div>
        <div v-else class="diff-modal-body" :class="{ 'mobile-detail': diffMobileShowDetail }">
          <div class="diff-file-list">
            <div
              v-for="(file, index) in diffFiles"
              :key="file.file_path || index"
              class="diff-file-item"
              :class="{ active: index === diffActiveIndex }"
              :title="file.file_path"
              @click="selectDiffFile(index)"
            >
              <span class="diff-file-item-path">{{ file.file_path || 'Unknown' }}</span>
              <span class="diff-file-item-stats">
                <span class="diff-additions">+{{ file.additions || 0 }}</span>
                <span class="diff-deletions">-{{ file.deletions || 0 }}</span>
              </span>
            </div>
          </div>
          <div class="diff-file-view">
            <button class="diff-mobile-back" @click="diffMobileShowDetail = false">
              <span class="diff-mobile-back-icon">‹</span>
              <span class="diff-mobile-back-text">{{ diffFiles[diffActiveIndex]?.file_path || 'File List' }}</span>
            </button>
            <div v-html="diffActiveHtml"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Rules floating window -->
    <div v-if="showRulesModal" class="diff-modal-overlay" @click.self="showRulesModal = false">
      <div class="diff-modal rules-modal">
        <div class="diff-modal-header">
          <h3>Rules Info</h3>
          <button class="icon-btn" @click="showRulesModal = false" title="Close">✕</button>
        </div>
        <div class="diff-modal-content">
          <div v-if="rulesLoading" class="diff-loading">Loading...</div>
          <div v-else-if="rulesContent.length === 0" class="diff-empty">No rules</div>
          <table v-else class="rules-table">
            <thead>
              <tr>
                <th>Rule Name</th>
                <th>Status</th>
                <th>File Path</th>
                <th>Preview</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rule in rulesContent" :key="rule.name" :title="rule.preview">
                <td>{{ rule.name }}</td>
                <td>
                  <span :class="rule.is_loaded ? 'rule-loaded' : 'rule-not-loaded'">
                    {{ rule.is_loaded ? 'Loaded' : 'Not Loaded' }}
                  </span>
                </td>
                <td class="rule-file-path">{{ rule.file_path || '--' }}</td>
                <td class="rule-preview">{{ rule.preview }}</td>
              </tr>
            </tbody>
          </table>
          <!-- Loaded rule content -->
          <div v-if="rulesLoadedContent" class="rules-loaded-content-section">
            <h4 class="rules-section-title">Loaded Rule Content</h4>
            <pre class="rules-loaded-content">{{ rulesLoadedContent }}</pre>
          </div>
        </div>
      </div>
    </div>

    <!-- Tools floating window -->
    <div v-if="showToolsModal" class="diff-modal-overlay" @click.self="showToolsModal = false">
      <div class="diff-modal rules-modal">
        <div class="diff-modal-header">
          <h3>Tools Info</h3>
          <button class="icon-btn" @click="showToolsModal = false" title="Close">✕</button>
        </div>
        <div class="diff-modal-content">
          <div v-if="toolsLoading" class="diff-loading">Loading...</div>
          <div v-else>
            <h4 class="tools-section-title">Allowed Tools</h4>
            <div v-if="!toolsContent.allowed_tools" class="diff-empty">All tools allowed</div>
            <table v-else-if="toolsContent.allowed_tools.length > 0" class="rules-table">
              <thead>
                <tr>
                  <th>Tool Name</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="tool in toolsContent.allowed_tools" :key="tool">
                  <td>{{ tool }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="diff-empty">No allowed tools</div>

            <h4 class="tools-section-title">All Tools ({{ toolsContent.all_tools.length }})</h4>
            <div v-if="toolsContent.all_tools.length === 0" class="diff-empty">No tools</div>
            <table v-else class="rules-table">
              <thead>
                <tr>
                  <th>Tool Name</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="tool in toolsContent.all_tools" :key="tool.name" :title="tool.description">
                  <td>{{ tool.name }}</td>
                  <td class="rule-preview">{{ tool.description }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- Network topology overview -->
    <TopologyOverlay
      :visible="showTopologyOverlay"
      :nodes="availableNodeOptions"
      :agents="agentList"
      :getStatusClass="getStatusClass"
      :nodeDisplayNames="nodeDisplayNames"
      :extensionSessions="topologyExtensionSessions"
      :daemonSessions="topologyDaemonSessions"
      @update:visible="showTopologyOverlay = $event"
      @close="closeTopologyOverlay"
    />

    <!-- Pipeline orchestration overview -->
    <OrchestrationOverlay
      :visible="showOrchestrationOverlay"
      :pipelines="pipelineList"
      :activeId="activePipelineId"
      @update:visible="showOrchestrationOverlay = $event"
      @close="closeOrchestrationOverlay"
      @select="selectPipeline"
      @jump-agent="onOrchestrationJumpAgent"
      @approve="handleApproval('approve', $event)"
      @reject="handleApproval('reject', $event)"
      @retry="handleApproval('retry', $event)"
    />

    <!-- Command palette (Ctrl+P) -->
    <CommandPalette
      :visible="showCommandPalette"
      :actions="appActions"
      :ctx="commandPaletteCtx"
      :initial-query="commandPaletteInitialQuery"
      @update:visible="showCommandPalette = $event"
      @run="onCommandRun"
      @close="showCommandPalette = false"
    />

    <!-- Space Leader sequence hint floating window: after pressing space, shows the next-level operations level by level -->
    <div v-if="spaceSeq.active" class="space-seq-popover" @mousedown.prevent>
      <div class="space-seq-title">
        <span class="space-seq-key">Space</span>
        <template v-for="(p, i) in spaceSeq.path" :key="i">
          <span class="space-seq-arrow">›</span>
          <span class="space-seq-key">{{ p }}</span>
        </template>
        <span class="space-seq-hint">Select the next-level operation, ESC to cancel</span>
      </div>
      <div class="space-seq-grid">
        <div
          v-for="group in spaceSeqOptions"
          :key="group.key"
          class="space-seq-group"
          :class="{ active: group.active }"
        >
          <div class="space-seq-group-head">
            <span class="space-seq-item-key">{{ group.key }}</span>
            <span class="space-seq-item-label">{{ group.label }}</span>
          </div>
          <div class="space-seq-children">
            <div
              v-for="cmd in group.children"
              :key="cmd.key"
              class="space-seq-item"
              :class="{ active: cmd.active }"
            >
              <span class="space-seq-item-key">{{ cmd.key }}</span>
              <span class="space-seq-item-label">{{ cmd.label }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Panel context menu: same as the pet context menu, lists "Current Agent" operations -->
    <div
      v-if="panelContextMenu.visible"
      class="panel-context-menu"
      :style="{ left: panelContextMenu.x + 'px', top: panelContextMenu.y + 'px' }"
      @pointerdown.stop
      @click.stop
      @contextmenu.prevent.stop
    >
      <div class="panel-context-title">{{ panelContextMenu.name }}</div>
      <div class="panel-context-items">
        <button
          v-for="act in lobbyContextActions"
          :key="act.id"
          class="panel-context-item"
          :disabled="act.enabled === false"
          @click="onPanelContextAction(act)"
        >
          <span class="panel-context-icon" v-html="act.icon"></span>
          <span class="panel-context-label">{{ act.label }}</span>
        </button>
      </div>
    </div>

    <!-- Editor directory tree context menu -->
    <div
      v-if="fileTreeContextMenu.visible"
      class="file-tree-context-menu"
      :style="{ left: fileTreeContextMenu.x + 'px', top: fileTreeContextMenu.y + 'px' }"
      @pointerdown.stop
      @click.stop
      @contextmenu.prevent.stop
    >
      <button
        v-for="act in fileTreeContextActions"
        :key="act.id"
        class="file-tree-context-item"
        :disabled="act.enabled === false"
        @click="runFileTreeContextAction(act)"
      >
        <span class="file-tree-context-icon" v-html="act.icon"></span>
        <span class="file-tree-context-label">{{ act.label }}</span>
      </button>
    </div>

    <!-- Git commit context menu -->
    <div
      v-if="gitCommitContextMenu.visible"
      class="file-tree-context-menu"
      :style="{ left: gitCommitContextMenu.x + 'px', top: gitCommitContextMenu.y + 'px' }"
      @pointerdown.stop
      @click.stop
      @contextmenu.prevent.stop
    >
      <button
        class="file-tree-context-item"
        @click="copyGitCommit(gitCommitContextMenu.commit)"
      >
        <span class="file-tree-context-icon" v-html="UI_ICONS.copy"></span>
        <span class="file-tree-context-label">Copy commit message</span>
      </button>
      <button
        class="file-tree-context-item"
        @click="copyGitCommitId(gitCommitContextMenu.commit)"
      >
        <span class="file-tree-context-icon" v-html="UI_ICONS.copy"></span>
        <span class="file-tree-context-label">Copy commit ID</span>
      </button>
    </div>

    <!-- Git commit full info popup (no hover on mobile, view via the "Details" button) -->
    <div v-if="gitCommitInfoModal" class="diff-modal-overlay" @click.self="gitCommitInfoModal = null">
      <div class="diff-modal git-commit-info-modal">
        <div class="diff-modal-header">
          <h3>Commit Info</h3>
          <button class="icon-btn" @click="gitCommitInfoModal = null" title="Close">✕</button>
        </div>
        <div class="diff-modal-content">
          <pre class="git-commit-info-pre">{{ formatGitCommitInfo(gitCommitInfoModal) }}</pre>
        </div>
      </div>
    </div>

    <!-- Hidden file selector for directory tree "Upload" -->
    <input
      ref="fileTreeUploadInput"
      type="file"
      multiple
      style="display: none"
      @change="onFileTreeUploadInputChange"
    >

    <!-- Editor tab bar context menu: show in file tree / close all to the right / close all / keep only current -->
    <div
      v-if="tabContextMenu.visible"
      class="file-tree-context-menu"
      :style="{ left: tabContextMenu.x + 'px', top: tabContextMenu.y + 'px' }"
      @pointerdown.stop
      @click.stop
      @contextmenu.prevent.stop
    >
      <button
        v-for="act in tabContextActions"
        :key="act.id"
        class="file-tree-context-item"
        :disabled="act.enabled === false"
        @click="runTabContextAction(act)"
      >
        <span class="file-tree-context-icon">{{ act.icon }}</span>
        <span class="file-tree-context-label">{{ act.label }}</span>
      </button>
    </div>

    <!-- Onboarding (triggered on first occurrence per scenario, can be re-opened anytime from the command palette) -->
    <OnboardingTour
      v-model:visible="showOnboarding"
      :steps="activeTourSteps"
      @close="finishTour"
      @finish="finishTour"
    />
    <!-- Orchestration popup: select node + orchestration file → parse the Agent list (one tab each, editable) → one-click create -->
    <div v-if="showOrchestrateModal" class="orchestrate-overlay" @click.self="closeOrchestrateModal">
      <div class="orchestrate-modal">
        <div class="orchestrate-header">
          <h2>Orchestration: Batch Create Agents</h2>
          <button class="orchestrate-close" @click="closeOrchestrateModal">×</button>
        </div>
        <div class="orchestrate-body">
          <!-- Top: node + orchestration file path + parse -->
          <div class="orchestrate-source">
            <div class="orchestrate-source-row">
              <label class="orchestrate-label">Node</label>
              <select v-model="orchestrateNodeId" class="orchestrate-node-select" @change="onOrchestrateNodeChange">
                <option v-if="!filteredNodeOptionsForCreateAgent.length" value="" disabled>No nodes available</option>
                <option v-for="node in filteredNodeOptionsForCreateAgent" :key="node.node_id" :value="node.node_id">
                  {{ getNodeDisplayName(node.node_id) }}
                </option>
              </select>
            </div>
            <div class="orchestrate-source-row">
              <label class="orchestrate-label">Orchestration File</label>
              <input
                v-model="orchestrateFilePath"
                class="orchestrate-path-input"
                type="text"
                placeholder="Absolute path of the orchestration file on the node (.yaml/.yml=organization orchestration, .flow=flow orchestration), e.g. /home/user/pipeline.flow"
                @keydown.enter.prevent="parseOrchestrationFile"
              >
              <button class="btn secondary" @click="toggleOrchestrateBrowser">
                {{ orchestrateShowBrowser ? 'Collapse' : 'Browse' }}
              </button>
              <button class="btn secondary" @click="onOrchestrateLocalSelect">
                Local Selection
              </button>
              <button class="btn primary" :disabled="orchestrateLoading" @click="parseOrchestrationFile">
                {{ orchestrateLoading ? 'Parsing...' : 'Parse' }}
              </button>
            </div>
            <!-- Hidden file selector for choosing an orchestration file from the local machine (after selecting, it is uploaded to the chosen node and the path is filled back) -->
            <input
              ref="orchestrateLocalFileInput"
              type="file"
              accept=".yaml,.yml,.flow"
              style="display: none"
              @change="onOrchestrateLocalFileChange"
            >
            <!-- Recently used orchestration files: click to reuse quickly, hover to show the delete button -->
            <div v-if="orchestrateRecentFiles.length" class="orchestrate-recent">
              <div class="orchestrate-recent-title">Recently Used</div>
              <div class="orchestrate-recent-list">
                <button
                  v-for="(item, index) in orchestrateRecentFiles"
                  :key="index"
                  class="orchestrate-recent-tag"
                  :class="{ active: orchestrateFilePath === item.path }"
                  :title="item.path"
                  @click="selectOrchestrateRecentFile(item)"
                >
                  <span class="orchestrate-recent-name">{{ item.path }}</span>
                  <span class="orchestrate-recent-node">[{{ getNodeDisplayName(item.nodeId) }}]</span>
                  <span class="orchestrate-recent-remove" title="Remove from recently used" @click.stop="removeOrchestrateRecentFile(item.path, item.nodeId)">✕</span>
                </button>
              </div>
            </div>
            <!-- Plugin orchestration templates: automatically discover orchestration templates declared by installed plugins, click to use directly -->
            <div v-if="orchestratePluginTemplates.length" class="orchestrate-templates">
              <div class="orchestrate-templates-title">Plugin Orchestration Templates</div>
              <div class="orchestrate-templates-list">
                <button
                  v-for="(tpl, index) in orchestratePluginTemplates"
                  :key="index"
                  class="orchestrate-template-tag"
                  :class="{ active: orchestrateFilePath === tpl.file }"
                  :title="tpl.file"
                  @click="selectOrchestratePluginTemplate(tpl)"
                >
                  <span class="orchestrate-template-name">{{ tpl.name }}</span>
                  <span class="orchestrate-template-plugin">[{{ tpl.plugin }}]</span>
                  <span v-if="tpl.description" class="orchestrate-template-desc">{{ tpl.description }}</span>
                </button>
              </div>
            </div>
            <div v-else-if="orchestratePluginTemplatesLoading" class="orchestrate-templates-loading">Loading plugin orchestration templates...</div>
            <!-- File browse panel: embedded DirectoryDialog (directory + .yaml/.yml files, logic identical to "Open Directory") -->
            <div v-if="orchestrateShowBrowser" class="orchestrate-browse-wrap">
              <DirectoryDialog
                ref="orchestrateDialogRef"
                embedded
                :visible="orchestrateShowBrowser"
                :currentPath="orchestrateCurrentDirPath"
                :selectedDir="orchestrateHighlightedDir"
                :searchText="orchestrateDirSearchText"
                :filteredDirs="orchestrateFilteredDirs"
                fileSelectable
                :fileList="orchestrateFilteredFiles"
                :selectedFile="orchestrateHighlightedFile"
                @update:searchText="orchestrateDirSearchText = $event"
                @refresh="fetchOrchestrateEntries"
                @go-parent="goToOrchestrateParentDir"
                @enter="enterOrchestrateDir"
                @select-file="onOrchestrateSelectFile"
                @search-keydown="handleOrchestrateSearchKeydown"
              />
            </div>
          </div>

          <div v-if="orchestrateError" class="orchestrate-error">{{ orchestrateError }}</div>

          <!-- Tabs: one per Agent -->
          <div v-if="orchestrateAgents.length" class="orchestrate-tabs">
            <button
              v-for="(agent, index) in orchestrateAgents"
              :key="index"
              class="orchestrate-tab"
              :class="{ active: index === orchestrateActiveIndex }"
              @click="orchestrateActiveIndex = index"
            >
              <span class="orchestrate-tab-name">{{ agent.name || ('Agent ' + (index + 1)) }}</span>
              <span class="orchestrate-tab-close" @click.stop="removeOrchestrateAgent(index)">×</span>
            </button>
            <button v-if="!orchestrateHasFlow" class="orchestrate-tab-add" title="Add an Agent" @click="addOrchestrateAgent">＋</button>
          </div>

          <!-- Form of the current tab -->
          <div v-if="orchestrateAgents[orchestrateActiveIndex]" class="orchestrate-form">
            <div class="orchestrate-field">
              <label class="orchestrate-label">Name</label>
              <input v-model="orchestrateAgents[orchestrateActiveIndex].name" class="orchestrate-input" type="text" placeholder="Leave blank to auto-generate">
            </div>
            <div class="orchestrate-field orchestrate-field-wide">
              <label class="orchestrate-label">Working Directory</label>
              <div class="orchestrate-dir-row">
                <input v-model="orchestrateAgents[orchestrateActiveIndex].workingDir" class="orchestrate-input" type="text" placeholder="Absolute path">
                <button class="btn secondary" @click="openOrchestrateDirDialog">Select Directory</button>
              </div>
            </div>
            <div class="orchestrate-field">
              <label class="orchestrate-label">Model Group</label>
              <input v-model="orchestrateAgents[orchestrateActiveIndex].llmGroup" class="orchestrate-input" type="text" placeholder="default">
            </div>
            <div class="orchestrate-field">
              <label class="orchestrate-label">Tool Group</label>
              <input v-model="orchestrateAgents[orchestrateActiveIndex].toolGroup" class="orchestrate-input" type="text" placeholder="default">
            </div>
            <div class="orchestrate-field">
              <label class="orchestrate-label">Target Node</label>
              <select v-model="orchestrateAgents[orchestrateActiveIndex].nodeId" class="orchestrate-input">
                <option v-for="node in filteredNodeOptionsForCreateAgent" :key="node.node_id" :value="node.node_id">
                  {{ getNodeDisplayName(node.node_id) }}
                </option>
              </select>
            </div>
            <div class="orchestrate-field">
              <label class="orchestrate-label">Proxy Node</label>
              <select v-model="orchestrateAgents[orchestrateActiveIndex].proxyNode" class="orchestrate-input">
                <option value="">No proxy (direct call)</option>
                <option v-for="node in filteredNodeOptionsForCreateAgent" :key="node.node_id" :value="node.node_id">
                  {{ getNodeDisplayName(node.node_id) }}
                </option>
              </select>
            </div>
            <div class="orchestrate-field orchestrate-field-wide">
              <label class="orchestrate-label">Task Description</label>
              <textarea v-model="orchestrateAgents[orchestrateActiveIndex].task" class="orchestrate-textarea" rows="3" placeholder="Required in no-interaction mode"></textarea>
            </div>
            <div class="orchestrate-field orchestrate-field-wide orchestrate-checks">
              <label class="orchestrate-check"><input v-model="orchestrateAgents[orchestrateActiveIndex].quickMode" type="checkbox"> Turbo Mode</label>
              <label class="orchestrate-check"><input v-model="orchestrateAgents[orchestrateActiveIndex].restoreSession" type="checkbox"> Restore Session</label>
              <label class="orchestrate-check"><input v-model="orchestrateAgents[orchestrateActiveIndex].noInteractionMode" type="checkbox"> No Interaction Mode</label>
            </div>
          </div>
          <div v-else class="orchestrate-empty">Select an orchestration file and parse, or click ＋ to add an Agent</div>

          <!-- Creation result -->
          <div v-if="orchestrateResults.length" class="orchestrate-results">
            <div
              v-for="(r, index) in orchestrateResults"
              :key="index"
              class="orchestrate-result"
              :class="r.ok ? 'ok' : 'fail'"
            >
              <span>{{ r.ok ? '✓' : '✕' }}</span>
              <span class="orchestrate-result-name">{{ r.name }}</span>
              <span v-if="!r.ok" class="orchestrate-result-error">{{ r.error }}</span>
            </div>
          </div>

          <!-- Run pipeline: shown when the orchestration file contains flow. Same path as an Agent calling pipeline_runner; run progress drives the "Orchestration View" DAG visualization -->
          <div v-if="orchestrateHasFlow" class="orchestrate-run">
            <div class="orchestrate-run-title">Run Pipeline</div>
            <div class="orchestrate-run-hint">This orchestration file contains a flow field and will be executed via pipeline scheduling; run progress will be displayed in real time in "Orchestration View".</div>
            <div class="orchestrate-field orchestrate-field-wide">
              <label class="orchestrate-label">Working Directory</label>
              <input
                v-model="orchestrateRunWorkingDir"
                class="orchestrate-input"
                type="text"
                placeholder="Leave blank to default to the current directory; artifacts will be created under .haijunbot/artifacts/ within it"
              >
            </div>
          </div>
        </div>
        <div class="orchestrate-actions">
          <button class="btn secondary" @click="closeOrchestrateModal">Cancel</button>
          <!-- Contains flow: provides two operations, "Preview" static DAG and "Run Pipeline"; otherwise one-click create Agent -->
          <button
            v-if="orchestrateHasFlow"
            class="btn secondary"
            :disabled="!orchestrateFilePath || !orchestrateNodes.length"
            @click="previewOrchestration"
          >
            Preview
          </button>
          <button
            v-if="orchestrateHasFlow"
            class="btn primary orchestrate-run-btn"
            :disabled="orchestrateRunning || !orchestrateFilePath"
            @click="runOrchestration"
          >
            {{ orchestrateRunning ? 'Starting...' : 'Run Pipeline' }}
          </button>
          <button
            v-else
            class="btn primary"
            :disabled="orchestrateCreating || !orchestrateAgents.length"
            @click="createAllOrchestrateAgents"
          >
            {{ orchestrateCreating ? 'Creating...' : `One-click Create（${orchestrateAgents.length}）` }}
          </button>
        </div>
      </div>
    </div>
    <!-- Toast notification -->
    <transition name="toast-fade">
      <div v-if="toast.show" class="toast" :class="`toast-${toast.type}`">
        <span class="toast-icon">{{ toast.type === 'success' ? '✓' : toast.type === 'error' ? '✕' : 'ℹ' }}</span>
        <span class="toast-message">{{ toast.message }}</span>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, onMounted, onUnmounted, reactive, ref, triggerRef, watch } from 'vue'
// Must use the ESM build entry: the package root path gets resolved to min/ (AMD format) when bundled,
// Cannot get monaco.lsp (Monaco's built-in LSP client), nor use it via ESM.
import * as monaco from 'monaco-editor/esm/vs/editor/editor.main.js'
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker.js?worker'
import jsonWorker from 'monaco-editor/esm/vs/language/json/json.worker.js?worker'
import cssWorker from 'monaco-editor/esm/vs/language/css/css.worker.js?worker'
import htmlWorker from 'monaco-editor/esm/vs/language/html/html.worker.js?worker'
import tsWorker from 'monaco-editor/esm/vs/language/typescript/ts.worker.js?worker'
// LSP integration: the language list comes from the backend /api/lsp/servers; the frontend contains no language hardcoding
import { loadLspServers, getServerByLanguage, getServerByPath } from './lsp/registry.js'
import { ensureClient, disposeClient, disposeAll as disposeAllLspClients, getDefinition } from './lsp/manager.js'

// Under vite, Monaco must explicitly provide a worker factory, otherwise the editor cannot start
self.MonacoEnvironment = {
  getWorker(_workerId, label) {
    if (label === 'json') return new jsonWorker()
    if (label === 'css' || label === 'scss' || label === 'less') return new cssWorker()
    if (label === 'html' || label === 'handlebars' || label === 'razor') return new htmlWorker()
    if (label === 'typescript' || label === 'javascript') return new tsWorker()
    return new editorWorker()
  },
}
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'
import 'xterm/css/xterm.css'
import './diff.css'
import historyStorage from './historyStorage.js'
import ConnectModal from './components/ConnectModal.vue'
import BufferPanel from './components/BufferPanel.vue'
import DirectoryDialog from './components/DirectoryDialog.vue'
import SessionDialog from './components/SessionDialog.vue'
import AgentSidebar from './components/AgentSidebar.vue'
import PetWidget from './components/PetWidget.vue'
import CompletionsModal from './components/CompletionsModal.vue'
import TerminalPanel from './components/TerminalPanel.vue'
import ChatPanel from './components/ChatPanel.vue'
import WorkspacePanel from './components/WorkspacePanel.vue'
import WorkspacePaneTree from './components/WorkspacePaneTree.vue'
import WorkspacePaneHeader from './components/WorkspacePaneHeader.vue'
import SettingsModal from './components/SettingsModal.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import CreateAgentModal from './components/CreateAgentModal.vue'
import QuickCreateAgentModal from './components/QuickCreateAgentModal.vue'
import SessionPanel from './components/SessionPanel.vue'
import { renderSideBySideDiff, escapeHtml } from './diffRenderer.js'
import { parseUnifiedDiff, extractDiffContext } from './gitDiffParser.js'
import { useDiff } from './composables/useDiff.js'
import RenameAgentModal from './components/RenameAgentModal.vue'
import InputPromptModal from './components/InputPromptModal.vue'
import AdminPanel from './components/AdminPanel.vue'
import AboutModal from './components/AboutModal.vue'
import CommandPalette from './components/CommandPalette.vue'
import TopologyOverlay from './components/TopologyOverlay.vue'
import OrchestrationView from './components/OrchestrationView.vue'
import OrchestrationOverlay from './components/OrchestrationOverlay.vue'
import { PipelineStore } from './stores/pipelineStore.js'
import PetLobby from './components/PetLobby.vue'
import OnboardingTour from './components/OnboardingTour.vue'
import ManageSidebar from './components/ManageSidebar.vue'
import PluginSidebar from './components/PluginSidebar.vue'
import { fetchPluginExtensions, loadExtensionComponent } from './pluginExtensions.js'
import { ACTIONS as actionDefs, SPACE_COMMANDS } from './actions/registry.js'
import { resolveCurrentAgentId } from './utils/currentAgentResolver.js'
import { useAudioNotifications } from './composables/useAudioNotifications.js'
import { useInputHistory } from './composables/useInputHistory.js'
import { useAuthBridge } from './composables/useAuthBridge.js'
import { useDaemonSync } from './composables/useDaemonSync.js'
import { useTerminal, useTerminalName } from './composables/useTerminal.js'
import { useDiagramRender } from './composables/useDiagramRender.js'
import { useSession } from './composables/useSession.js'
import { useChat } from './composables/useChat.js'
import { useFileTree } from './composables/useFileTree.js'
import { useTour } from './composables/useTour.js'
import { usePlugins } from './composables/usePlugins.js'
import { useTopology } from './composables/useTopology.js'
import { useSettings } from './composables/useSettings.js'
import { useGatewayConnection } from './composables/useGatewayConnection.js'
import { useAgents } from './composables/useAgents.js'
import { useOrchestrate } from './composables/useOrchestrate.js'
import { useGitView } from './composables/useGitView.js'
import { useWorkspacePane } from './composables/useWorkspacePane.js'
import { useWorkspaceEditor } from './composables/useWorkspaceEditor.js'

// Diagram rendering (plantuml/mermaid/dot), extracted from an independent composable
const {
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
} = useDiagramRender()

// Frontend version number: injected at build time by define in vite.config.js (kept consistent with the main version)
const APP_VERSION = __APP_VERSION__

// Format message time - directly display the timestamp passed by the backend
function formatMessageTime(timestamp) {
  if (!timestamp) return ''
  return timestamp
}

const markedRenderer = new marked.Renderer()
const defaultCodeRenderer = markedRenderer.code.bind(markedRenderer)

markedRenderer.code = function(code, language, isEscaped) {
  if (isPlantUmlLanguage(language)) {
    return renderPlantUmlBlock(code)
  }
  if (isDotLanguage(language)) {
    return renderDotBlock(code)
  }
  if (isMermaidLanguage(language)) {
    return renderMermaidBlock(code)
  }
  return defaultCodeRenderer(code, language, isEscaped)
}

// Configure marked to use highlight.js for syntax highlighting
marked.setOptions({
  renderer: markedRenderer,
  breaks: true, // Convert a single newline into a <br> tag
  highlight: function(code, lang) {
    // Fall back to xml highlighting for vue SFC
    const effectiveLang = (lang === 'vue') ? 'xml' : lang
    if (effectiveLang && hljs.getLanguage(effectiveLang)) {
      try {
        return hljs.highlight(code, { language: effectiveLang }).value
      } catch (e) {
        console.error('[highlight.js] Error highlighting code:', e)
      }
    }
    return hljs.highlightAuto(code).value
  }
})

// Compute terminal history display style (adaptive height)
function getTerminalStyle(terminalContent) {
  if (!terminalContent) return {}
  
  const lineCount = terminalContent.split('\n').length
  const fontSize = 12
  const lineHeight = 1.4
  const maxLines = 30
  const headerHeight = 41 // the height of header
  const contentPadding = 32 // the padding of content
  
  const baseStyle = {
    fontFamily: "'Consolas', 'Microsoft YaHei', monospace",
    fontSize: `${fontSize}px`,
    lineHeight: lineHeight
  }
  
  const contentHeight = lineCount * fontSize * lineHeight
  const totalHeight = contentHeight + headerHeight + contentPadding

  if (lineCount <= maxLines) {
    // When the number of lines is small, compute the actual height: content height + header height + padding
    return { ...baseStyle, height: `${totalHeight}px` }
  } else {
    // When there are many lines, use the maximum height
    const maxHeight = maxLines * fontSize * lineHeight + headerHeight + contentPadding
    return { ...baseStyle, height: `${maxHeight}px` }
  }
}




// Drag-related functions
function startDragSidebar(event) {
  isDraggingSidebar.value = true
  dragOffset.value = {
    x: event.clientX - sidebarPosition.value.x,
    y: event.clientY - sidebarPosition.value.y
  }
  document.addEventListener('mousemove', onDragSidebar)
  document.addEventListener('mouseup', stopDragSidebar)
}

function onDragSidebar(event) {
  if (!isDraggingSidebar.value) return
  sidebarPosition.value = {
    x: event.clientX - dragOffset.value.x,
    y: event.clientY - dragOffset.value.y
  }
}

function stopDragSidebar() {
  isDraggingSidebar.value = false
  document.removeEventListener('mousemove', onDragSidebar)
  document.removeEventListener('mouseup', stopDragSidebar)
}

// Infer language from the file extension
function getLanguageFromFilename(filename) {
  if (!filename) return 'plaintext'
  const ext = filename.split('.').pop().toLowerCase()
  const langMap = {
    'py': 'python',
    'js': 'javascript',
    'ts': 'typescript',
    'vue': 'vue',
    'java': 'java',
    'c': 'c',
    'cpp': 'cpp',
    'h': 'cpp',
    'hpp': 'cpp',
    'go': 'go',
    'rs': 'rust',
    'rb': 'ruby',
    'php': 'php',
    'swift': 'swift',
    'kt': 'kotlin',
    'scala': 'scala',
    'sql': 'sql',
    'sh': 'bash',
    'bash': 'bash',
    'zsh': 'bash',
    'yaml': 'yaml',
    'yml': 'yaml',
    'json': 'json',
    'toml': 'toml',
    'ini': 'ini',
    'cfg': 'ini',
    'conf': 'ini',
    'xml': 'xml',
    'html': 'html',
    'css': 'css',
    'scss': 'scss',
    'less': 'less',
    'md': 'markdown',
    'txt': 'plaintext',
    'log': 'plaintext'
  }
  return langMap[ext] || 'plaintext'
}

// Monaco language ID mapping: Monaco's built-in languages mostly share the same name as getLanguageFromFilename,
// Only a few need normalization (e.g., vue has no built-in support, fall back to html).
const MONACO_LANGUAGE_ALIAS = {
  'vue': 'html',
  'toml': 'ini',
  'plaintext': 'plaintext',
}

function getLanguageExtension(language) {
  const normalized = MONACO_LANGUAGE_ALIAS[language] || language
  if (monaco.languages.getLanguages().some(lang => lang.id === normalized)) {
    return normalized
  }
  return 'plaintext'
}

// Authentication and connection configuration
const auth = ref({
  password: '',
  token: '',
  userInfo: null
})
const username = ref(localStorage.getItem('haijunbot_username') || '')
const socket = ref(null) // Gateway connection
const sockets = ref(new Map()) // Multi-Agent connection storage: agent_id -> WebSocket
const autoLoginEnabled = ref(localStorage.getItem('haijunbot_auto_login') === 'true')  // Auto-login switch
const switchGeneration = ref(0) // Switch generation, used to cancel old switchAgent operations

// Login function: use username + password to obtain a JWT Token
async function loginWithPassword(password) {
  try {
    const { host, port } = getGatewayAddress()
    const response = await fetch(`${getHttpProtocol()}://${host}:${port}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value, password })
    })

    const result = await response.json()
    if (!response.ok || !result.success || !result.data?.token) {
      throw new Error(result.error?.message || 'Login failed')
    }

    // Save Token (kept only in memory; it becomes invalid after page refresh, requiring re-login)
    auth.value.token = result.data.token

    // Save user information
    if (result.data.user) {
      auth.value.userInfo = result.data.user
      localStorage.setItem('haijunbot_user_info', JSON.stringify(result.data.user))
    }

    // If auto-login is enabled, save the Token to localStorage
    if (autoLoginEnabled.value) {
      localStorage.setItem('haijunbot_auth_token', result.data.token)
    }

    // Immediately clear the password after successful login (security best practice: use the password only once, then use the Token)
    auth.value.password = ''

    return true
  } catch (error) {
    console.error('[AUTH] Login failed:', error)
    throw error
  }
}

// Generic authenticated fetch function
function hasAuthToken() {
  return Boolean(auth.value.token)
}

// Get the currently valid Token (prefer the one in memory, then fall back to localStorage)
function getAuthToken() {
  // Prefer returning the Token in memory
  if (auth.value.token) {
    return auth.value.token
  }
  // Then try to get it from localStorage
  const savedToken = localStorage.getItem('haijunbot_auth_token')
  if (savedToken) {
    auth.value.token = savedToken
    return savedToken
  }
  return null
}

// Refresh user information (ensure fields like display_name are up to date)
async function refreshUserInfo() {
  if (!hasAuthToken()) return
  try {
    const { host, port } = getGatewayAddress()
    const response = await fetchWithAuth(`${getHttpProtocol()}://${host}:${port}/api/auth/me`)
    if (response.ok) {
      const result = await response.json()
      if (result.success && result.data) {
        const userData = result.data.user || result.data
        auth.value.userInfo = userData
        localStorage.setItem('haijunbot_user_info', JSON.stringify(userData))
      }
    }
  } catch (e) {
    console.warn('[AUTH] Failed to refresh user info:', e)
  }
}

// Try to load the saved token and user information from localStorage
function loadSavedToken() {
  const savedToken = localStorage.getItem('haijunbot_auth_token')
  if (savedToken) {
    auth.value.token = savedToken
    // Load user information
    const savedUserInfo = localStorage.getItem('haijunbot_user_info')
    if (savedUserInfo) {
      try {
        auth.value.userInfo = JSON.parse(savedUserInfo)
        if (auth.value.userInfo?.username) {
          username.value = auth.value.userInfo.username
        }
      } catch (e) {
        console.warn('[AUTH] Failed to parse saved user info')
      }
    }
    return true
  }
  return false
}

async function fetchWithAuth(url, options = {}) {
  if (!hasAuthToken()) {
    // Return a simulated 401 response to trigger the unified 401 handling flow
    return new Response(
      JSON.stringify({success: false, error: {message: 'Not logged in', code: 'UNAUTHORIZED'}}),
      {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      }
    )
  }

  // Copy options to avoid modifying the original object
  const fetchOptions = {
    ...options,
    headers: {
      ...options.headers,
      'Content-Type': 'Content-Type' in (options.headers || {}) ? options.headers['Content-Type'] : 'application/json'
    }
  }
  
  // If there is a Token, add it to the Authorization Header
  if (auth.value.token) {
    fetchOptions.headers['Authorization'] = `Bearer ${auth.value.token}`
  }
  
  const response = await fetch(url, fetchOptions)
  
  // Check for a 401 unauthorized error
  if (response.status === 401) {
    auth.value.token = ''
    auth.value.userInfo = null
    userAccessibleNodes.value = null
    userPermissions.value = null
    localStorage.removeItem('haijunbot_auth_token')
    localStorage.removeItem('haijunbot_user_info')
    showConnectModal.value = true
    connectErrorMessage.value = 'Login has expired, please log in again'
    stopAgentListRefresh()
    stopNodeStatusRefresh()
  }
  
  return response
}

// Expose a unified authenticated request function to plugin frontend extensions (independently dynamically loaded ES modules).
// Plugin sidebar/panel components cannot access this component's auth.value.token, nor should they touch the token directly,
// So window.__haijunbotFetch provides a unified authenticated request entry point: plugins only need to call
//   window.__haijunbotFetch(url, options)
// to automatically carry haijunbot authentication info, without exposing the token to plugins.
try {
  window.__haijunbotFetch = (url, options) => fetchWithAuth(url, options)
} catch (e) {
  /* ignore */
}

// Expose the "send prompt to the currently active Agent" hook to plugin frontend extensions (e.g., the gh plugin's right-click "Process").
// The target Agent stays consistent with the plugin sidebar's working directory: Git target Agent (gitAgentId || currentAgentId),
// Ensuring the prompt is sent to the Agent currently displaying that repository. Sending reuses the existing input_result channel: when the Agent is waiting for input
// Submit immediately, otherwise it enters the input buffer, to be consumed the next time it requests input.
// Return { success, agentId } or { success: false, error }, so plugins can give clear feedback.
try {
  window.__haijunbotSendToActiveAgent = (text, options = {}) => {
    const content = String(text || '').trim()
    if (!content) return { success: false, error: 'Prompt is empty' }
    const agentId = options.agentId || effectiveGitAgentId.value || currentAgentId.value
    if (!agentId) return { success: false, error: 'There is currently no active Agent' }
    const ws = sockets.value.get(agentId)
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      return { success: false, error: 'Target Agent is not connected, please open that Agent in the session panel first' }
    }
    sendInputDirectly(content, 'multi', agentId)
    return { success: true, agentId }
  }
} catch (e) {
  /* ignore */
}

// Expose the "get current active Agent info" hook to plugin frontend extensions (e.g., the gh plugin displays the target Agent at the top).
// The target Agent is exactly the same as __haijunbotSendToActiveAgent: Git target Agent (gitAgentId || currentAgentId),
// Ensuring the Agent displayed by the plugin is exactly the one the prompt is actually sent to.
// Return { agentId, agentName, workingDir }; return null when there is no active Agent.
try {
  window.__haijunbotGetActiveAgentInfo = () => {
    const agentId = effectiveGitAgentId.value
    const agent = agentId ? (agentList.value.find(a => a.agent_id === agentId) || null) : null
    return agent
      ? {
          agentId: agent.agent_id,
          agentName: agent.name || agent.agent_id,
          workingDir: agent.working_dir || '',
        }
      : null
  }
} catch (e) {
  /* ignore */
}

// Expose the "create a new regular Agent to handle a task" hook to plugin frontend extensions (e.g., the gh plugin's right-click "Create New Agent to Handle").
// Use a regular Agent (agent_type='agent') instead of a code Agent, to avoid the mutual exclusion limit of code Agents under the same working directory.
// Create in interactive mode with the prompt as the initial task; the user can intervene at any time. Automatically open that Agent panel after creation.
// options.agentType can specify the agent type (default 'agent', backward compatible; passing 'code_agent' creates a code Agent).
// Return { success, agentId } or { success: false, error }.
try {
  window.__haijunbotCreateAgentForTask = async (options = {}) => {
    const workingDir = String(options.workingDir || '').trim()
    const task = String(options.task || '').trim()
    if (!workingDir) return { success: false, error: 'Working directory is empty' }
    if (!task) return { success: false, error: 'Task prompt is empty' }
    const agentType = String(options.agentType || 'agent').trim() || 'agent'
    const result = await createAgentWithOptions({
      agentType,
      workingDir,
      name: options.name || '',
      task,
      noInteractionMode: false,
    })
    if (!result.ok) return { success: false, error: result.error }
    await afterAgentCreated(result.agent)
    return { success: true, agentId: result.agent.agent_id }
  }
} catch (e) {
  /* ignore */
}

// Expose the "select directory" hook to plugin frontend extensions (e.g., the gh plugin's "Fork and create CodeAgent to handle" needs to select a directory first).
// Reuse the host's existing "open directory" dialog (including node selection + directory browsing); return the selected absolute path after user confirmation,
// or return null if canceled. Returns Promise<string|null>.
try {
  window.__haijunbotPickDirectory = () => {
    return new Promise((resolve) => {
      // When there is an unfinished selection request, first end the previous one with null to avoid a hanging Promise
      if (pluginPickDirResolver) {
        const prev = pluginPickDirResolver
        pluginPickDirResolver = null
        prev(null)
      }
      pluginPickDirResolver = resolve
      openDirSource.value = 'plugin'
      openOpenDirDialog()
    })
  }
} catch (e) {
  /* ignore */
}
// ========== Unified plugin interface family (Issue #97) ==========
// On top of the existing __haijunbot* single-point interfaces, complete a unified interface family of "information query + UI control",
// So that plugin extensions (sidebar_views / admin_tabs / tool_panels) no longer rely on the host adding functions one by one.
// All interfaces follow the try/catch wrapping pattern: silently degrade when the host environment is abnormal, without affecting the main interface.
// For event subscription (__haijunbotOn/__haijunbotOff), see the "Plugin Event Subscription Mechanism" section below.

// Get the current logged-in user info (auth.userInfo); return null when not logged in or not loaded.
try {
  window.__haijunbotGetUserInfo = () => auth.value.userInfo || null
} catch (e) {
  /* ignore */
}

// Get the node list (availableNodeOptions, including fields such as node_id/status; master is always included).
// Return a copy of the array to prevent plugins from directly modifying the host's reactive state.
try {
  window.__haijunbotGetNodes = () => (Array.isArray(availableNodeOptions.value) ? [...availableNodeOptions.value] : [])
} catch (e) {
  /* ignore */
}

// Show a toast notification (reusing the host's showToast).
// message: text; type: 'success' | 'error' | 'info' (default success).
try {
  window.__haijunbotShowToast = (message, type = 'success') => showToast(String(message || ''), type)
} catch (e) {
  /* ignore */
}

// Switch the workspace sidebar view (reusing the host's setWorkspaceSidebarView).
// view: built-in view name (agents/files/search/git/manage/timers/plugins/orchestration)
//       or plugin view ('plugin:<id>' / 'plugin-tool:<id>').
try {
  window.__haijunbotSwitchSidebarView = (view) => {
    const target = String(view || '').trim()
    if (!target) return { success: false, error: 'View name is empty' }
    setWorkspaceSidebarView(target)
    return { success: true }
  }
} catch (e) {
  /* ignore */
}

// Open a host panel/navigation (reusing the host's existing entry points).
// kind supports:
//   'admin'        Open the admin panel
//   'settings'     Open settings
//   'workspace'    Open the workspace (and switch to the Agent list)
//   'git'          Open the workspace and switch to the Git sidebar
//   'plugins'      Open the workspace and switch to the plugin management sidebar
//   'topology'     Open the network topology
//   'docs'         Open the usage documentation
// Return { success } or { success: false, error }.
try {
  window.__haijunbotOpenPanel = (kind) => {
    const target = String(kind || '').trim()
    switch (target) {
      case 'admin':
        showAdminPanel.value = true
        pushOverlayState()
        return { success: true }
      case 'settings':
        showSettingsModal.value = true
        return { success: true }
      case 'workspace':
        openWorkspaceAgentList()
        return { success: true }
      case 'git':
        if (!showWorkspacePanel.value) {
          showWorkspacePanel.value = true
          if (windowWidth.value <= 768) pushOverlayState()
        }
        setWorkspaceSidebarView('git')
        return { success: true }
      case 'plugins':
        if (!showWorkspacePanel.value) {
          showWorkspacePanel.value = true
          if (windowWidth.value <= 768) pushOverlayState()
        }
        setWorkspaceSidebarView('plugins')
        return { success: true }
      case 'topology':
        openTopologyOverlay()
        return { success: true }
      case 'docs':
        openDocs()
        return { success: true }
      default:
        return { success: false, error: `Unknown panel: ${target}` }
    }
  }
} catch (e) {
  /* ignore */
}

// Get the current gateway info (host/port/protocol), for plugins to construct API addresses.
// Return { host, port, protocol }; fall back to default values when parsing fails.
try {
  window.__haijunbotGetGatewayInfo = () => {
    const { host, port } = getGatewayAddress()
    return {
      host,
      port,
      protocol: getHttpProtocol(),
    }
  }
} catch (e) {
  /* ignore */
}

// ========== Plugin Event Subscription Mechanism (Issue #97) ==========
// The host emits events at key state changes; plugins subscribe via window.__haijunbotOn(event, handler),
// and unsubscribe via window.__haijunbotOff(event, handler). The handler receives a (payload) argument.
// Event list:
//   'agent_changed'  Current active Agent changes (payload: { agentId, agentName, workingDir } or null)
//   'token_changed'  token changes (payload: { token }, null on logout)
//   'user_changed'   Current user info changes (payload: { userInfo } or null)
//   'nodes_changed'  Node list changes (payload: { nodes })
const __haijunbotEventListeners = new Map()
try {
  window.__haijunbotOn = (event, handler) => {
    if (typeof handler !== 'function') return () => {}
    const key = String(event || '')
    if (!key) return () => {}
    if (!__haijunbotEventListeners.has(key)) __haijunbotEventListeners.set(key, new Set())
    __haijunbotEventListeners.get(key).add(handler)
    // Return an unsubscribe function, so plugins can clean up when the component unmounts
    return () => window.__haijunbotOff(key, handler)
  }
  window.__haijunbotOff = (event, handler) => {
    const key = String(event || '')
    const set = __haijunbotEventListeners.get(key)
    if (!set) return
    if (handler) {
      set.delete(handler)
    } else {
      set.clear()
    }
  }
} catch (e) {
  /* ignore */
}
// Host-internal emit helper function (not exposed to plugins, called at state changes in this file)
function __haijunbotEmit(event, payload) {
  try {
    const set = __haijunbotEventListeners.get(String(event || ''))
    if (!set) return
    set.forEach((handler) => {
      try {
        handler(payload)
      } catch (e) {
        console.warn(`[PluginEvents] handler for "${event}" failed:`, e)
      }
    })
  } catch (e) {
    /* ignore */
  }
}

// URL parsing helper function: supports HTTPS protocol and domain names

// Get the current page's HTTP protocol (http:// or https://)
function getHttpProtocol() {
  return window.location.protocol === 'https:' ? 'https' : 'http'
}

// Get the current page's WebSocket protocol (ws:// or wss://)
function getWebSocketProtocol() {
  return window.location.protocol === 'https:' ? 'wss' : 'ws'
}

// Parse the gateway address, supporting full URL format (e.g., ws://example.com:8080/ws or example.com:8080)
function parseGatewayAddress(address) {
  // Remove leading/trailing whitespace
  address = address.trim()
  
  // If it is a full URL (containing a protocol)
  if (address.includes('://')) {
    try {
      const url = new URL(address)
      return {
        protocol: url.protocol.replace(':', ''),  // 'ws', 'wss', 'http', 'https'
        host: url.hostname,
        port: url.port || (url.protocol === 'https:' || url.protocol === 'wss:' ? '443' : '80'),
        path: url.pathname
      }
    } catch (e) {
      console.error('[URL] Failed to parse address:', address, e)
      return null
    }
  }
  
  // If it is in host:port format
  if (address.includes(':')) {
    const parts = address.split(':')
    if (parts.length === 2) {
      return {
        protocol: null,  // Use the default protocol
        host: parts[0],
        port: parts[1],
        path: ''
      }
    }
  }
  
  // If there is only a hostname (use the default port)
  return {
    protocol: null,
    host: address,
    port: '8000',
    path: ''
  }
}

// Build the node HTTP base path
function buildNodeHttpUrl(host, port, nodeId = 'master', path = '', protocol = null) {
  const httpProtocol = protocol || getHttpProtocol()
  const normalizedNodeId = String(nodeId || 'master').trim() || 'master'
  const normalizedPath = `/${String(path || '').replace(/^\/+/, '')}`
  return `${httpProtocol}://${host}:${port}/api/node/${encodeURIComponent(normalizedNodeId)}${normalizedPath}`
}

// Build the node WebSocket base path
function buildNodeWebSocketUrl(host, port, nodeId = 'master', path = '', protocol = null) {
  const wsProtocol = protocol || getWebSocketProtocol()
  const normalizedNodeId = String(nodeId || 'master').trim() || 'master'
  const normalizedPath = `/${String(path || '').replace(/^\/+/, '')}`
  return `${wsProtocol}://${host}:${port}/api/node/${encodeURIComponent(normalizedNodeId)}${normalizedPath}`
}

// Build the WebSocket URL (for the gateway connection)
function buildWebSocketUrl(host, port, protocol = null) {
  return buildNodeWebSocketUrl(host, port, 'master', 'ws', protocol)
}

// Build the Agent WebSocket URL (via the unified node proxy)
function buildAgentWebSocketUrl(host, agentId, protocol = null, port = null, nodeId = '') {
  const normalizedNodeId = String(nodeId || 'master').trim() || 'master'
  return buildNodeWebSocketUrl(host, port, normalizedNodeId, `agent/${agentId}/ws`, protocol)
}

// Build the HTTP URL
function buildHttpUrl(host, port, path, protocol = null) {
  const normalizedPath = String(path || '').replace(/^\/+/, '')
  return buildNodeHttpUrl(host, port, 'master', normalizedPath, protocol)
}

function buildWebSocketProtocols() {
  const token = String(auth.value?.token || '').trim()
  if (!token) {
    return ['haijunbot-ws']
  }
  return ['haijunbot-ws', `haijunbot-token.${encodeURIComponent(token)}`]
}

// Get the gateway address (host and port)
function getGatewayAddress() {
  const parsed = parseGatewayAddress(gatewayUrl.value)
  if (!parsed) {
    return {
      host: '127.0.0.1',
      port: '8000'
    }
  }
  return {
    host: parsed.host || '127.0.0.1',
    port: parsed.port || '8000'
  }
}
// Gateway address display string (host:port), for display in the lobby's top-left gauge
const gatewayAddressDisplay = computed(() => {
  const { host, port } = getGatewayAddress()
  return `${host}:${port}`
})

// Download the browser extension zip package: request the gateway's dynamic packaging endpoint to trigger a browser download
async function downloadBrowserExtension() {
  const { host, port } = getGatewayAddress()
  const url = `${getHttpProtocol()}://${host}:${port}/api/browser-ext/download`
  const response = await fetchWithAuth(url)
  if (!response.ok) {
    throw new Error(`Download failed (HTTP ${response.status})`)
  }
  // Prefer the filename from the backend's Content-Disposition
  let filename = 'haijunbot-browser-bridge.zip'
  const disposition = response.headers.get('Content-Disposition') || ''
  const matched = disposition.match(/filename="?([^";]+)"?/i)
  if (matched && matched[1]) filename = matched[1]
  const blob = await response.blob()
  const objectUrl = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(objectUrl)
}

// Query browser extension version info: returns the gateway package version and the online extension version, for the frontend to prompt an upgrade
async function fetchBrowserExtensionVersion() {
  try {
    const { host, port } = getGatewayAddress()
    const url = `${getHttpProtocol()}://${host}:${port}/api/browser-ext/version`
    const response = await fetchWithAuth(url)
    if (!response.ok) return null
    const result = await response.json()
    if (!result || !result.success) return null
    return {
      latestVersion: result.latest_version || '',
      sessions: Array.isArray(result.sessions) ? result.sessions : []
    }
  } catch (e) {
    // A failed version query should not affect the popup display
    return null
  }
}

// Query the local background service (daemon) online sessions: return the session array, for the lobby topology diagram to display connected daemon nodes.
// Non-admins only get their own (the user corresponding to the token) sessions, restricted by the gateway.
async function fetchDaemonSessions() {
  try {
    const { host, port } = getGatewayAddress()
    const url = `${getHttpProtocol()}://${host}:${port}/api/daemon/sessions`
    const response = await fetchWithAuth(url)
    if (!response.ok) return []
    const result = await response.json()
    if (!result || !result.success) return []
    return Array.isArray(result.sessions) ? result.sessions : []
  } catch (e) {
    // A failed query should not affect topology rendering; treat as no online daemon
    return []
  }
}

// Query the scheduled task list (read-only display; tasks are directly controlled by the Agent).
// GET /api/timers returns {success, data:[{task_id, run_at, interval_seconds,
//   is_recurring, cancelled, metadata:{action:{type,params}, schedule}}]}
async function fetchTimers() {
  try {
    const { host, port } = getGatewayAddress()
    const url = `${getHttpProtocol()}://${host}:${port}/api/timers`
    const response = await fetchWithAuth(url)
    if (!response.ok) return []
    const result = await response.json()
    if (!result || !result.success) return []
    return Array.isArray(result.data) ? result.data : []
  } catch (e) {
    return []
  }
}

// Refresh the scheduled task list in the management sidebar
async function refreshManageTimers() {
  manageTimers.value = await fetchTimers()
}
// For the topology diagram to render a node for each connected extension and display its name.
// Note: the sessions of /api/browser-ext/version only contain session_id/extension_version,
// and not name, so /api/browser-ext/sessions is called separately here.
// Non-admins only get their own (the user corresponding to the token) sessions, restricted by the gateway.
async function fetchBrowserExtensionSessions() {
  try {
    const { host, port } = getGatewayAddress()
    const url = `${getHttpProtocol()}://${host}:${port}/api/browser-ext/sessions`
    const response = await fetchWithAuth(url)
    if (!response.ok) return []
    const result = await response.json()
    if (!result || !result.success) return []
    return Array.isArray(result.sessions) ? result.sessions : []
  } catch (e) {
    // A failed query should not affect topology rendering; treat as no online extension
    return []
  }
}

// Open the "About" dialog and refresh version info (backend version / nodes / daemon / browser extension)
async function openAbout() {
  showAboutModal.value = true
  pushOverlayState()
  const { host, port } = getGatewayAddress()
  // Backend version and each node's version
  try {
    const resp = await fetchWithAuth(buildNodeHttpUrl(host, port, 'master', 'node/status'))
    if (resp.ok) {
      const result = await resp.json()
      const data = result?.data
      aboutBackendVersion.value = data?.version || ''
      aboutNodes.value = Array.isArray(data?.nodes) ? data.nodes : []
    }
  } catch (e) {
    // Ignore, keep existing value
  }
  // daemon and browser extension version
  aboutDaemonSessions.value = await fetchDaemonSessions()
  aboutBrowserExtSessions.value = await fetchBrowserExtensionSessions()
}

// Query the custom scripts installed in each online browser extension session (used for the capability list).
// GET /api/browser-ext/scripts/installed returns {success, sessions:[{session_id, name, scripts}]}
async function fetchInstalledScripts() {
  try {
    const { host, port } = getGatewayAddress()
    const url = `${getHttpProtocol()}://${host}:${port}/api/browser-ext/scripts/installed`
    const response = await fetchWithAuth(url)
    if (!response.ok) return []
    const result = await response.json()
    if (!result || !result.success) return []
    return Array.isArray(result.sessions) ? result.sessions : []
  } catch (e) {
    return []
  }
}

// Query the scripts saved under the gateway data directory (used for the capability list).
// GET /api/browser-ext/scripts/list returns {success, scripts:[{name, size, updated_at}]}
async function fetchGatewayScripts() {
  try {
    const { host, port } = getGatewayAddress()
    const url = `${getHttpProtocol()}://${host}:${port}/api/browser-ext/scripts/list`
    const response = await fetchWithAuth(url)
    if (!response.ok) return []
    const result = await response.json()
    if (!result || !result.success) return []
    return Array.isArray(result.scripts) ? result.scripts : []
  } catch (e) {
    return []
  }
}

// Network topology overview (split out from the composable useTopology, see the useTopology call site below)
const {
  topologyExtensionSessions,
  topologyDaemonSessions,
  refreshTopologyAccessSessions,
  startTopologyAccessPolling,
  stopTopologyAccessPolling,
  showTopologyOverlay,
  openTopologyOverlay,
  closeTopologyOverlay,
} = useTopology({
  fetchBrowserExtensionSessions,
  fetchDaemonSessions,
})
// Refresh capability list data (browser extension sessions + daemon sessions + installed scripts + gateway scripts).
// Capability list cache: only called on first open or when manually clicking the refresh button, to avoid frequent requests.
async function refreshManageCapabilities() {
  const [extSessions, daemonSessions, installedScripts, gatewayScripts] = await Promise.all([
    fetchBrowserExtensionSessions(),
    fetchDaemonSessions(),
    fetchInstalledScripts(),
    fetchGatewayScripts(),
  ])
  topologyExtensionSessions.value = Array.isArray(extSessions) ? extSessions : []
  topologyDaemonSessions.value = Array.isArray(daemonSessions) ? daemonSessions : []
  manageInstalledScripts.value = Array.isArray(installedScripts) ? installedScripts : []
  manageGatewayScripts.value = Array.isArray(gatewayScripts) ? gatewayScripts : []
}

// Scheduled task list shown in the admin sidebar (read-only, directly controlled by the Agent)
const manageTimers = ref([])
// Capability list: browser extension installed scripts + gateway script library (cached, to avoid frequent requests, manual refresh only)
const manageInstalledScripts = ref([])
const manageGatewayScripts = ref([])

// Modal control
const showConnectModal = ref(true)  // Show welcome screen on first open
const showSettingsModal = ref(false) // Settings modal
const showAdminPanel = ref(false) // Admin panel
const showAboutModal = ref(false) // About modal
// "About" panel data: backend version / node / daemon / browser extension
const aboutBackendVersion = ref('')
const aboutNodes = ref([])
const aboutDaemonSessions = ref([])
const aboutBrowserExtSessions = ref([])
const adminPanelRef = ref(null) // Admin panel component reference (used by the command palette to navigate to system config)
const petWidgetRef = ref(null)        // Main pet widget component reference (used to call pet show/hide)
const showTerminalPanel = ref(false)  // Terminal panel
const showChatPanel = ref(false)     // Chat room panel
// Editor panel: the sole container, open by default. Initial value depends on whether an Agent already exists:
// Keep closed when there is no Agent, revealing the pet lobby (empty state) as the welcome page; open the editor to host sessions when an Agent exists.
const showWorkspacePanel = ref(false)
// Whether the editor has already been auto-opened because "an Agent was fetched for the first time" (auto-open only once, respecting manual closure afterward)
let workspaceAutoOpened = false
const sessionPanelRefs = new Map()  // panelId -> SessionPanel component instance

// Register/unregister SessionPanel component instances (so the App side can call their exposed capabilities such as focusInput).
// Note: the same panel in the template may be rendered by different hosts (pane leaf / editor main area),
// and the :ref inline function first unregisters with null then registers with the instance on every re-render, so idempotent handling is done here:
// - when el is empty, delete only if the currently registered entry is indeed this panel, to avoid mistakenly deleting valid references from other hosts;
// - when panelId is empty (host unmounted, panel no longer exists), ignore it directly.
function setSessionPanelRef(panelId, el) {
  if (!panelId) return
  if (el) {
    sessionPanelRefs.set(panelId, el)
  } else if (sessionPanelRefs.has(panelId)) {
    sessionPanelRefs.delete(panelId)
  }
}

const showMobileMenu = ref(false)     // Mobile menu
const activeWindow = ref(null)        // Currently focused window: 'terminal' | 'workspace' | 'chat' | 'session' | null



// Rules floating window state
const showRulesModal = ref(false)     // Show rules floating window
const rulesContent = ref([])          // rules content (rule list)
const rulesLoading = ref(false)       // Loading state
const rulesLoadedContent = ref('')    // Specific content of the loaded rules

// Window z-index constants
const BASE_Z_INDEX = 1000
const ACTIVE_Z_INDEX = 1100

const EDITOR_SIDEBAR_DEFAULT_WIDTH = 360
const EDITOR_SIDEBAR_MIN_WIDTH = 200
const EDITOR_SIDEBAR_MAX_WIDTH = 560
const EDITOR_SIDEBAR_STORAGE_KEY = 'haijunbot_workspace_sidebar_width'

function normalizeWorkspaceSidebarWidth(width) {
  // Inlined clamp (not relying on the clamp returned by useWorkspaceEditor, to avoid setup top-level TDZ:
  // This function is defined before the useWorkspaceEditor call site, and loadWorkspaceSidebarWidth executes immediately at the top level)
  const min = EDITOR_SIDEBAR_MIN_WIDTH
  const max = EDITOR_SIDEBAR_MAX_WIDTH
  if (max < min) return min
  return Math.min(Math.max(width, min), max)
}

function loadWorkspaceSidebarWidth() {
  const savedValue = localStorage.getItem(EDITOR_SIDEBAR_STORAGE_KEY)
  if (!savedValue) {
    return EDITOR_SIDEBAR_DEFAULT_WIDTH
  }

  const parsedWidth = Number(savedValue)
  if (!Number.isFinite(parsedWidth)) {
    return EDITOR_SIDEBAR_DEFAULT_WIDTH
  }

  return normalizeWorkspaceSidebarWidth(parsedWidth)
}

function saveWorkspaceSidebarWidth() {
  localStorage.setItem(EDITOR_SIDEBAR_STORAGE_KEY, String(workspaceSidebarWidth.value))
}

const workspaceSidebarWidth = ref(loadWorkspaceSidebarWidth())
const workspaceSidebarResizeState = ref({
  active: false,
  startX: 0,
  startWidth: EDITOR_SIDEBAR_DEFAULT_WIDTH,
})


const windowWidth = ref(window.innerWidth)  // Window width, used for responsive detection
const showCreateAgentModal = ref(false) // Create Agent modal
const showQuickCreateAgentModal = ref(false) // One-sentence create Agent modal
const quickCreateAgentLoading = ref(false) // One-sentence create: request in progress
const quickCreateAgentError = ref('') // One-sentence create: error message
const showRenameAgentModal = ref(false) // Rename Agent modal
const renamingAgent = ref(null)          // Agent being renamed
const renameAgentName = ref('')           // New name for renaming
const selectedSession = ref(null)         // Selected session
const showBufferPanel = ref(false)        // Buffer management panel visibility state
const bufferPanelAgentId = ref(null)      // Target Agent for the buffer management panel (the Agent that owns the clicked Panel)
const bufferEditText = ref('')            // Buffer edit text
const showDirDialog = ref(false)           // Directory selection dialog
let handleResize = null
let handlePopState = null
let visualViewportResizeHandler = null
let diagramObserver = null

function updateViewportHeight() {
  const viewportHeight = window.visualViewport?.height || window.innerHeight
  document.documentElement.style.setProperty('--app-height', `${viewportHeight}px`)
}
const currentDirPath = ref('')             // Directory path currently being browsed
const dirList = ref([])                    // Directory list
const selectedDir = ref(null)              // Selected directory
const dirSearchText = ref('')              // Directory search text
const dirSearchInput = ref(null)           // Directory search input box reference
const selectedDirIndex = ref(-1)           // Currently selected directory index, -1 means not selected

const recentWorkDirs = ref([])             // Recently used working directory list (max 20, deduplicated)
const renameInput = ref(null)               // Rename input box reference
// ===== Directory tree: open any directory by node (browse/edit files without creating an Agent) =====
// Modal state: node + directory path (manual entry or browse selection)
const showOpenDirDialog = ref(false)
const openDirNodeId = ref('master')         // Target node
const openDirPath = ref('')                 // Target directory (absolute path)
const openDirInput = ref(null)              // Manual path input box reference
const openDirDialogRef = ref(null)          // Reference to the DirectoryDialog embedded in the "Open Directory" modal
// Source of the open directory modal: 'workspace'=directory tree opening workspace / 'git'=Git panel selecting Git management directory / 'plugin'=plugin requesting directory selection
const openDirSource = ref('workspace')
// Promise resolver when a plugin requests directory selection: resolve(path) on confirm, resolve(null) on cancel
let pluginPickDirResolver = null
// Git panel custom Git management directory (user-specified, takes priority over Agent root directory): { nodeId, path }
const gitCustomDir = ref(null)
// Persistence key for the custom Git directory: automatically restored after refresh
const GIT_CUSTOM_DIR_STORAGE_KEY = 'haijunbot_git_custom_dir'
function loadGitCustomDir() {
  try {
    const raw = localStorage.getItem(GIT_CUSTOM_DIR_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || !parsed.nodeId || !parsed.path) return null
    return { nodeId: String(parsed.nodeId), path: String(parsed.path) }
  } catch (e) {
    return null
  }
}
function saveGitCustomDir() {
  try {
    if (gitCustomDir.value?.nodeId && gitCustomDir.value?.path) {
      localStorage.setItem(GIT_CUSTOM_DIR_STORAGE_KEY, JSON.stringify(gitCustomDir.value))
    } else {
      localStorage.removeItem(GIT_CUSTOM_DIR_STORAGE_KEY)
    }
  } catch (e) {
    // Silently degrade when localStorage is unavailable (private mode / quota full)
  }
}
// Directory browsing reuses the directory filter state (currentDirPath/dirList/selectedDir/dirSearchText) and logic from create Agent
// Open the "open directory by node" modal (single modal: node selection on top, embedded directory filter below)
// Directory browsing reuses the directory filter logic from create Agent (DirectoryDialog + fetchDirectories, etc.), only the node source differs
async function openOpenDirDialog() {
  showOpenDirDialog.value = true
  // Node options may not be loaded yet (e.g. the create Agent modal has never been opened), so fetch once here
  if (!availableNodeOptions.value.length) {
    try { await fetchNodeStatus() } catch (error) { /* keep an empty list on failure, the modal will show a hint */ }
  }
  const allowed = filteredNodeOptionsForCreateAgent.value
  const preferred = allowed.some(n => n.node_id === openDirNodeId.value)
    ? openDirNodeId.value
    : (allowed[0]?.node_id || 'master')
  openDirNodeId.value = preferred
  openDirPath.value = ''
  // Embedded directory filter: browse from the root directory (no separate modal pops up)
  dirDialogContext.value = 'open-dir'
  selectedDir.value = '~'
  dirSearchText.value = ''
  selectedDirIndex.value = -1
  await fetchDirectories('~')
}
// Open the Git panel's "Select Git Directory" modal (reuses the node + directory selection logic of the open directory modal)
async function openGitDirDialog() {
  openDirSource.value = 'git'
  await openOpenDirDialog()
}
function closeOpenDirDialog() {
  showOpenDirDialog.value = false
  // Plugin requesting directory selection scenario: end the Promise with null on cancel
  if (openDirSource.value === 'plugin' && pluginPickDirResolver) {
    const resolve = pluginPickDirResolver
    pluginPickDirResolver = null
    resolve(null)
  }
  // Reset the scenario to avoid the subsequent create Agent "select directory" being misjudged as the "open directory" scenario
  dirDialogContext.value = 'create-agent'
  openDirSource.value = 'workspace'
  resetDirectorySelectionState()
}
// Clear the Git panel's custom Git management directory, returning to managing by Agent root directory
function clearGitCustomDir() {
  gitCustomDir.value = null
  saveGitCustomDir()
  if (workspaceSidebarView.value === 'git') refreshGitView()
}
// Git panel selects an Agent: clear the custom Git directory (returning to managing by that Agent's root directory) and refresh the Git view.
// When "follow current session" (empty value) is selected, reset to null, restoring linkage with the editor session.
function onGitAgentChange(agentId) {
  gitAgentId.value = agentId ? agentId : null
  if (gitCustomDir.value) {
    gitCustomDir.value = null
    saveGitCustomDir()
  }
  if (workspaceSidebarView.value === 'git') refreshGitView()
}
// Switch target node: re-browse the directory by the new node
async function onOpenDirNodeChange(nodeId) {
  openDirNodeId.value = nodeId
  openDirPath.value = ''
  selectedDir.value = '~'
  dirSearchText.value = ''
  selectedDirIndex.value = -1
  await fetchDirectories('~')
}
// Select an item in the directory filter list: sync to the path input box (reuses create Agent's selectDirectory)
function onOpenDirSelect(path) {
  selectDirectory(path)
  openDirPath.value = path
}
// Confirm open: prioritize the "manual path", then the "browsed selected directory"
async function confirmOpenDir() {
  const nodeId = String(openDirNodeId.value || 'master').trim() || 'master'
  const targetPath = String(openDirPath.value || selectedDir.value || '').trim()
  if (!targetPath) {
    showToast('Please select or enter a directory path', 'error')
    return
  }
  showOpenDirDialog.value = false
  // Reset the scenario to avoid the subsequent create Agent "select directory" being misjudged as the "open directory" scenario
  dirDialogContext.value = 'create-agent'
  resetDirectorySelectionState()
  if (openDirSource.value === 'plugin') {
    // Plugin requesting directory selection: end the Promise with the selected path (do not open the workspace)
    openDirSource.value = 'workspace'
    if (pluginPickDirResolver) {
      const resolve = pluginPickDirResolver
      pluginPickDirResolver = null
      resolve(targetPath)
    }
    return
  }
  if (openDirSource.value === 'git') {
    // Git panel: set the selected directory as the Git management target and refresh the Git view
    openDirSource.value = 'workspace'
    gitCustomDir.value = { nodeId, path: targetPath }
    saveGitCustomDir()
    if (workspaceSidebarView.value === 'git') refreshGitView()
    return
  }
  await openWorkspaceDir(nodeId, targetPath)
}

// Recently used working directory management (localStorage persistent storage)
// Element format: { path: string, nodeId: string }, distinguished by node
function loadRecentWorkDirs() {
  try {
    const stored = localStorage.getItem('haijunbot_recent_work_dirs')
    if (stored) {
      const parsed = JSON.parse(stored)
      // Backward compatibility for old data: the old format is a plain string array; clear it if the type does not match
      const isValid = Array.isArray(parsed) && parsed.every(item =>
        item && typeof item === 'object' && typeof item.path === 'string' && typeof item.nodeId === 'string'
      )
      recentWorkDirs.value = isValid ? parsed : []
    } else {
      recentWorkDirs.value = []
    }
  } catch (error) {
    console.error('[HISTORY DIR] Failed to load history records:', error)
    recentWorkDirs.value = []
  }
}

function saveRecentWorkDir(path, nodeId) {
  try {
    const normalizedNodeId = String(nodeId || '').trim() || 'master'
    // Deduplicate: filter out existing same-node same-path entries
    const filtered = recentWorkDirs.value.filter(item =>
      !(item.path === path && item.nodeId === normalizedNodeId)
    )
    // Add the new path to the front
    const updated = [{ path, nodeId: normalizedNodeId }, ...filtered]
    // Keep only the most recent 20
    recentWorkDirs.value = updated.slice(0, 20)
    // Save to localStorage
    localStorage.setItem('haijunbot_recent_work_dirs', JSON.stringify(recentWorkDirs.value))
  } catch (error) {
    console.error('[HISTORY DIR] Failed to save history records:', error)
  }
}


// Filtered directory list (supports fuzzy search)
const filteredDirList = computed(() => {
  if (!dirSearchText.value.trim()) {
    return dirList.value
  }
  const searchText = dirSearchText.value.toLowerCase().trim()
  return dirList.value.filter(dir => 
    dir.name.toLowerCase().includes(searchText) ||
    dir.path.toLowerCase().includes(searchText)
  )
})

// Floating window position
const sidebarPosition = ref({ x: 20, y: 100 }) // Sidebar floating position
const isDraggingSidebar = ref(false) // Whether the sidebar is being dragged
const dragOffset = ref({ x: 0, y: 0 }) // Drag offset



// ===== Workspace pane tree / free split / sidebar (split out from App.vue into composables/useWorkspacePane.js) =====
const {
  // Constants
  EDITOR_PANEL_MIN_WIDTH, EDITOR_PANEL_MIN_HEIGHT, workspaceResizeDirections, PANEL_DRAG_ACTIVATION_DISTANCE,
  // workspace panel state
  isWorkspaceMaximized, workspacePanelRectBeforeMaximize, saveWorkspacePanelRect,
  workspacePanelRect, workspacePanelInteraction, workspacePanelRef,
  splitWorkspaceContainerRefs, setSplitWorkspaceContainerRef, editorContainerRef,
  // Sessions/tabs
  workspaceSessions, activeWorkspaceSessionId, workspaceTabs, activeWorkspaceTabPath,
  activeWorkspaceSession, virtualWorkspaceSessions, editorModels,
  workspaceFileHeartbeatTimer, isWorkspaceEditable, EDITOR_FILE_HEARTBEAT_INTERVAL,
  // Global search
  globalSearchQuery, globalSearchFileGlob, globalSearchCaseSensitive, globalSearchWholeWord,
  globalSearchLoading, globalSearchError, globalSearchResults, globalSearchTotalFiles,
  globalSearchTotalMatches, globalSearchExecuted, globalSearchMode, fileSearchResults,
  // Sidebar
  showWorkspaceSidebar, workspaceSidebarView, workspaceMainView,
  // pane tree core
  workspacePaneTree, activePaneId, maximizedPaneId, workspacePaneCount, activePane,
  findWorkspacePaneById, activateWorkspacePane, toggleMaximizeWorkspacePane,
  moveActivePaneInDirection, splitWorkspacePane, closeWorkspacePane, collapseWorkspacePanes,
  findWorkspacePaneBySessionPanelId, findWorkspacePaneByView, ensureAgentEditorPane,
  ensureEditorPaneForFileOpen, setMainViewOnLeaf, ensurePaneForView, setActivePaneView,
  setActivePaneViewForPane, getWorkspacePaneTitle, getWorkspacePaneStatus, getPanePanel,
  isPaneActive, startWorkspacePaneResize, persistWorkspacePaneLayout,
  restoreWorkspacePaneLayout, restoreWorkspacePaneContents,
  // Plugin extensions (passed through from usePlugins return)
  pluginExtensions, pluginAdminTabs, pluginSidebarViews, pluginToolPanels,
  pluginSidebarTitle, pluginToolPanelTitle, WORKSPACE_SIDEBAR_TITLES, workspaceSidebarTitle,
  loadPluginExtensionsForUi, resolvePluginExtensionComponent, isPluginSidebarView,
  isPluginToolView, pluginSidebarCompCache, activePluginSidebarComp, activePluginToolPanelComp,
} = useWorkspacePane({
  // Directly passed (defined before this call site)
  fetchWithAuth,
  getGatewayAddress,
  getHttpProtocol,
  hasAuthToken,
  windowWidth,
  // getter injection (after the B-domain useWorkspaceEditor split these symbols will be defined by that composable,
  // this call site is before it, so they are passed as getters and re-evaluated internally via xxx() to avoid TDZ)
  clamp: () => clamp,
  focusWindow: () => focusWindow,
  getWorkspaceTabByPath: () => getWorkspaceTabByPath,
  activeWorkspaceTab: () => activeWorkspaceTab,
  editorViews: () => editorViews,
  workspaceViewPanes: () => workspaceViewPanes,
  diffEditorViews: () => diffEditorViews,
  workspacePaneTabs: () => workspacePaneTabs,
  workspacePaneTabsVersion: () => workspacePaneTabsVersion,
  remountMonacoEditor: () => remountMonacoEditor,
  scheduleWorkspaceLayout: () => scheduleWorkspaceLayout,
  layoutMonacoEditor: () => layoutMonacoEditor,
  activateWorkspaceTab: () => activateWorkspaceTab,
  openWorkspaceFile: () => openWorkspaceFile,
  // getter injection (destructured from useGitView, defined after this call site; re-evaluated internally in useWorkspacePane via xxx()())
  layoutGitDiffEditor: () => layoutGitDiffEditor,
  disposeDiffEditorForPane: () => disposeDiffEditorForPane,
  disposeAllDiffEditors: () => disposeAllDiffEditors,
  loadDiffForPane: () => loadDiffForPane,
  // getter injection (defined after the call site; re-evaluated internally in useWorkspacePane via xxx())
  panels: () => panels,
  activePanelId: () => activePanelId,
  closePanel: () => closePanel,
  getPanelAgent: () => getPanelAgent,
  workspaceSessionPanelId: () => workspaceSessionPanelId,
  agentList: () => agentList,
  gitAgentId: () => gitAgentId,
  switchAgent: () => switchAgent,
  activeTerminalId: () => activeTerminalId,
  terminalSessions: () => terminalSessions,
  restoreTerminalSessions: () => restoreTerminalSessions,
  focusFirstIn: () => focusFirstIn,
})

// ===== Workspace editor / file operations (split out from App.vue into composables/useWorkspaceEditor.js) =====
const {
  EDITOR_FONT_FAMILY,
  UI_ICONS,
  activateWorkspaceTab,
  activeWorkspaceTab,
  bindWorkspaceViewEvents,
  clamp,
  clearGlobalSearch,
  closeWorkspacePanel,
  closeWorkspaceSidebar,
  closeWorkspaceTab,
  createWorkspaceForAgent,
  diffContainerRefs,
  diffEditorViews,
  editorViews,
  ensureMonacoEditor,
  ensureWorkspacePanelInViewport,
  ensureWorkspaceSidebarFileTree,
  fetchFileContent,
  fetchFileSearchResults,
  focusWindow,
  getActiveWorkspaceView,
  getPaneTabs,
  getVirtualWorkspaceAgent,
  getWorkspaceTabByPath,
  hideWorkspaceHostedPanelState,
  layoutMonacoEditor,
  lspBindings,
  openFileSearchResult,
  openGlobalSearchResult,
  openTabContextMenu,
  openWorkspaceDir,
  openWorkspaceFile,
  openWorkspaceGlobalSearch,
  remountMonacoEditor,
  removeWorkspaceDir,
  resolveAgentForPath,
  resolveAgentRelativePath,
  resolveDiffContainer,
  resolveFileTreeAgent,
  restoreVirtualWorkspaceDirs,
  runGlobalSearch,
  runTabContextAction,
  saveActiveWorkspaceTab,
  savePaneWorkspaceFile,
  scheduleWorkspaceLayout,
  setDiffContainerRef,
  setGlobalSearchMode,
  setWorkspaceMainView,
  setWorkspaceSidebarView,
  showWorkspaceHostView,
  startWorkspaceFileHeartbeat,
  startWorkspacePanelMove,
  startWorkspacePanelResize,
  startWorkspaceSidebarResize,
  stopWorkspaceFileHeartbeat,
  stopWorkspacePanelInteraction,
  tabContextActions,
  tabContextMenu,
  toggleWorkspaceEditable,
  toggleWorkspaceMainView,
  toggleWorkspaceMaximize,
  toggleWorkspaceSidebarView,
  workspacePaneTabs,
  workspacePaneTabsVersion,
  workspacePanelStyle,
  workspaceViewPanes,
} = useWorkspaceEditor({
  // Directly passed (defined before this call site)
  fetchWithAuth,
  getGatewayAddress,
  getHttpProtocol,
  buildNodeHttpUrl,
  getWebSocketProtocol,
  buildWebSocketProtocols,
  getLanguageFromFilename,
  getLanguageExtension,
  closePanel: () => closePanel,
  refreshManageCapabilities,
  refreshManageTimers,
  windowWidth,
  activeWindow,
  showWorkspacePanel,
  showTerminalPanel,
  showChatPanel,
  workspaceSidebarWidth,
  workspaceSidebarResizeState,
  agentList: () => agentList,
  socket,
  panels: () => panels,
  workspaceSessionPanelId: () => workspaceSessionPanelId,
  normalizeWorkspaceSidebarWidth,
  saveWorkspaceSidebarWidth,
  ACTIVE_Z_INDEX,
  BASE_Z_INDEX,
  manageInstalledScripts,
  manageGatewayScripts,
  getDefinition,
  loadLspServers,
  getServerByLanguage,
  getServerByPath,
  ensureClient,
  disposeClient,
  // Directly passed (returned by useWorkspacePane, defined before this call site)
  activePaneId,
  workspaceSessions,
  activeWorkspaceSessionId,
  workspaceTabs,
  activeWorkspaceTabPath,
  activeWorkspaceSession,
  virtualWorkspaceSessions,
  editorModels,
  workspaceFileHeartbeatTimer,
  isWorkspaceEditable,
  EDITOR_FILE_HEARTBEAT_INTERVAL,
  globalSearchQuery,
  globalSearchFileGlob,
  globalSearchCaseSensitive,
  globalSearchWholeWord,
  globalSearchLoading,
  globalSearchError,
  globalSearchResults,
  globalSearchTotalFiles,
  globalSearchTotalMatches,
  globalSearchExecuted,
  globalSearchMode,
  fileSearchResults,
  showWorkspaceSidebar,
  workspaceSidebarView,
  workspaceMainView,
  workspacePaneCount,
  workspacePanelInteraction,
  workspacePanelRect,
  workspacePanelRectBeforeMaximize,
  isWorkspaceMaximized,
  saveWorkspacePanelRect,
  splitWorkspaceContainerRefs,
  editorContainerRef,
  EDITOR_PANEL_MIN_WIDTH,
  EDITOR_PANEL_MIN_HEIGHT,
  PANEL_DRAG_ACTIVATION_DISTANCE,
  collapseWorkspacePanes,
  findWorkspacePaneByView,
  ensureEditorPaneForFileOpen,
  ensurePaneForView,
  setMainViewOnLeaf,
  setActivePaneView,
  setActivePaneViewForPane,
  // getter injection (defined after the call site; re-evaluated internally in useWorkspaceEditor via xxx())
  showToast: () => showToast,
  showConfirm: () => showConfirm,
  pushOverlayState: () => pushOverlayState,
  getNodeDisplayName: () => getNodeDisplayName,
  getCurrentAgentOrNull: () => getCurrentAgentOrNull,
  isStoppedAgent: () => isStoppedAgent,
  currentAgent: () => currentAgent,
  workspaceHostsChat: () => workspaceHostsChat,
  workspaceHostsTerminal: () => workspaceHostsTerminal,
  editorShortcutLocked: () => editorShortcutLocked,
  effectiveGlobalSearchAgentId: () => effectiveGlobalSearchAgentId,
  fileTreeState: () => fileTreeState,
  initFileTree: () => initFileTree,
  getVisibleFileTreeNodes: () => getVisibleFileTreeNodes,
  expandedAgents: () => expandedAgents,
  fileTreeExpanded: () => fileTreeExpanded,
  fileTreeLoading: () => fileTreeLoading,
  fileTreeSelectedAgentId: () => fileTreeSelectedAgentId,
  fileTreeSelectedPath: () => fileTreeSelectedPath,
  selectedAgentId: () => selectedAgentId,
  revealTabInFileTree: () => revealTabInFileTree,
  gitLogLoading: () => gitLogLoading,
  refreshGitView: () => refreshGitView,
  layoutGitDiffEditor: () => layoutGitDiffEditor,
  renderDiffForPane: () => renderDiffForPane,
  scheduleDiffLayout: () => scheduleDiffLayout,
  topologyDaemonSessions: () => topologyDaemonSessions,
  topologyExtensionSessions: () => topologyExtensionSessions,
  getWorkspaceTargetNodeId: () => getWorkspaceTargetNodeId,
})
// ===== Editor sidebar Git view (read-only: commit history/details/diff/branches) =====
const {
  // refs
  gitLog, gitLogLoading, gitLogError, gitLogHasMore, gitLogTotal,
  gitBranches, gitTags, gitCurrentBranch, gitSelectedCommit,
  gitRangeSelectMode, gitSelectedCommits, gitPatchLoading,
  gitCommitFiles, gitCommitDetailLoading, gitSelectedFile,
  gitDiffText, gitDiffLoading, gitDiffError, gitDiffTruncated,
  gitDiffSideBySide, gitDiffShowFull,
  pluginSidebarWorkingDir, pluginActiveAgentInfo,
  gitCommitContextMenu, gitCommitInfoModal,
  // Constants
  GIT_LOG_PAGE_SIZE,
  // Functions
  isNarrowGitDiffViewport, getGitTargetAgent, getGitTargetNodeId, getGitWorkingDir,
  callGitApi, fetchGitLog, fetchGitBranches, refreshGitView,
  toggleGitCommitDetail, enterGitRangeSelect, exitGitRangeSelect, toggleGitRangeSelect,
  downloadGitPatch, viewGitTargetDiff, onDiffTitleClick, onOpenDiffFileFromMessage,
  viewGitFileDiff, ensureGitDiffFullText, layoutGitDiffEditor,
  disposeDiffEditorForPane, disposeAllDiffEditors, ensureDiffEditorForPane,
  renderDiffForPane, loadDiffForPane, togglePaneDiffSideBySide, togglePaneDiffShowFull,
  navigatePaneDiff, closePaneDiff, scheduleDiffLayout,
  gitRefClass, gitFileStatus, formatGitRelativeTime, shortGitHash,
  closeGitCommitContextMenu, openGitCommitContextMenu, copyGitCommit, copyGitCommitId,
  formatGitCommitInfo, formatGitCommitTooltip, showGitCommitInfoModal,
} = useGitView({
  EDITOR_FONT_FAMILY,
  buildNodeHttpUrl,
  fetchWithAuth,
  getGatewayAddress,
  getLanguageExtension,
  getLanguageFromFilename,
  windowWidth,
  activeWorkspaceSessionId,
  ensurePaneForView,
  findWorkspacePaneById,
  gitCustomDir,
  persistWorkspacePaneLayout,
  resolveDiffContainer,
  scheduleWorkspaceLayout,
  showWorkspacePanel,
  workspacePaneTree,
  workspaceSidebarView,
  diffContainerRefs,
  diffEditorViews,
  openWorkspaceFile,
  activePane,
  getPanePanel,
  // getter injection (defined after the call site; re-evaluated internally in useGitView via xxx())
  effectiveGitAgentId: () => effectiveGitAgentId,
  agentList: () => agentList,
  showToast: () => showToast,
  viewDiff: () => viewDiff,
  copyTextToClipboard: () => copyTextToClipboard,
  getPanelAgent: () => getPanelAgent,
  getCurrentAgentOrNull: () => getCurrentAgentOrNull,
})

// Directory tree context menu items

// Trigger the hidden file input to select local files to upload to the specified directory

// Call the backend create file/directory API (does not overwrite existing paths)

// ===== Directory tree copy/cut/paste =====

// List the direct children under a directory (reuses the directories API)

// ===== Directory tree drag and drop (HTML5 DnD): normal drag=move, hold Ctrl/⌘=copy =====
// Hard constraint: operations are only allowed within the same directory tree (same node_id); cross-Agent/cross-node is always rejected.
// Drag and drop state: { agentId, nodeId, path, name, kind }, alive only for a single drag operation.

// Find the corresponding loaded directory tree node by absolute path (return null if not found, meaning refresh the working directory root)

// Messages and terminal
const allOutputs = ref(new Map()) // Store messages by agent_id: agent_id -> outputs array
const outputs = computed(() => allOutputs.value.get(currentAgentId.value) || []) // Messages of the current Agent
const outputList = ref(null)
const panelOutputLists = new Map() // panelId -> outputList element
let historyScrollListenerEl = null // Element currently bound to the scroll listener
let historyScrollHandler = null // Scroll listener handler function
let historyScrollDebounceTimer = null // Scroll debounce timer

// Get the seq of the last message of the specified agent from the history
function getAgentLastSeq(agentId) {
  try {
    const messages = historyStorage.getHistoryForAgent(agentId)
    if (messages.length === 0) return -1
    // Messages are already sorted by time, take the last message that has a seq
    for (let i = messages.length - 1; i >= 0; i--) {
      if (typeof messages[i].seq === 'number') {
        return messages[i].seq
      }
    }
    return -1
  } catch (error) {
    console.error('[SYNC] Failed to get last seq for agent:', agentId, error)
    return -1
  }
}
// Input control
const inputText = ref('')
const inputMode = ref('multi') // Input mode of the currently displayed Agent
const inputRequests = ref(new Map()) // Input request for each Agent (key: agentId, value: {tip, mode, preset, request_id})
const inputTip = ref('') // Input tip of the currently displayed Agent
const panelInputTexts = ref(new Map()) // Input text for each Panel (key: agentId, value: string)
const panelInputModes = ref(new Map()) // Input mode for each Panel (key: agentId, value: 'multi'|'single')
const panelInputTips = ref(new Map()) // Input tip for each Panel (key: agentId, value: string)
const panelInputPasswords = ref(new Map()) // Password input flag for each Panel (key: agentId, value: boolean)

const pendingInputAgentId = ref(null) // Agent that owns the current pending input request (used to focus the correct input box)
const pendingConfirmAgentId = ref(null) // Agent that owns the current pending confirm request
const panelConfirmData = ref(new Map()) // Confirm data for each Panel (key: agentId, value: {message, defaultConfirm})
const panelAutoScrolls = ref(new Map()) // Auto-scroll toggle for each Panel (key: agentId, value: boolean, default true)
const panelAutoReads = ref(new Map()) // Auto-read toggle for each Panel (key: agentId, value: boolean, default false)
const inputBuffers = ref(new Map()) // Input buffer for each Agent (key: agentId, value: content)

const COMPLETION_USAGE_STORAGE_KEY = 'haijunbot_completion_usage_stats'

function loadCompletionUsageStats() {
  const savedValue = localStorage.getItem(COMPLETION_USAGE_STORAGE_KEY)
  if (!savedValue) {
    return {}
  }

  try {
    const parsedValue = JSON.parse(savedValue)
    if (!parsedValue || typeof parsedValue !== 'object' || Array.isArray(parsedValue)) {
      return {}
    }

    return Object.fromEntries(
      Object.entries(parsedValue).filter(([, count]) => Number.isInteger(count) && count > 0)
    )
  } catch {
    return {}
  }
}

function saveCompletionUsageStats(completionUsageStats) {
  localStorage.setItem(COMPLETION_USAGE_STORAGE_KEY, JSON.stringify(completionUsageStats))
}

function getCompletionUsageKey(item) {
  if (!item || typeof item.value !== 'string') {
    return ''
  }

  const normalizedValue = item.value.trim()
  if (!normalizedValue) {
    return ''
  }

  const normalizedType = typeof item.type === 'string' && item.type.trim()
    ? item.type.trim()
    : 'unknown'

  return `${normalizedType}:${normalizedValue}`
}

function getCompletionUsageCount(item) {
  const completionUsageKey = getCompletionUsageKey(item)
  if (!completionUsageKey) {
    return 0
  }

  return completionUsageStats.value[completionUsageKey] || 0
}

function getCompletionRecommendationScore(item, originalIndex = 0) {
  if (!item || typeof item !== 'object') {
    return -originalIndex
  }

  const scoreMatch = typeof item.display === 'string'
    ? item.display.match(/\((\d+)%\)$/)
    : null

  if (scoreMatch) {
    return Number(scoreMatch[1])
  }

  return -originalIndex
}

function sortCompletionItems(items = []) {
  return items
    .map((item, index) => ({
      item,
      usageCount: getCompletionUsageCount(item),
      recommendationScore: getCompletionRecommendationScore(item, index),
      originalIndex: index,
    }))
    .sort((leftItem, rightItem) => {
      if (rightItem.usageCount !== leftItem.usageCount) {
        return rightItem.usageCount - leftItem.usageCount
      }

      if (rightItem.recommendationScore !== leftItem.recommendationScore) {
        return rightItem.recommendationScore - leftItem.recommendationScore
      }

      return leftItem.originalIndex - rightItem.originalIndex
    })
    .map(({ item }) => item)
}

function recordCompletionSelection(item) {
  const completionUsageKey = getCompletionUsageKey(item)
  if (!completionUsageKey) {
    return
  }

  const nextCompletionUsageStats = {
    ...completionUsageStats.value,
    [completionUsageKey]: (completionUsageStats.value[completionUsageKey] || 0) + 1,
  }

  completionUsageStats.value = nextCompletionUsageStats
  saveCompletionUsageStats(nextCompletionUsageStats)
}

// Toast notification
const toast = ref({
  show: false,
  message: '',
  type: 'success' // success | error | info
})

let toastTimer = null

function showToast(message, type = 'success') {
  toast.value = {
    show: true,
    message,
    type
  }
  
  if (toastTimer) {
    clearTimeout(toastTimer)
  }
  
  toastTimer = setTimeout(() => {
    toast.value.show = false
  }, 2000)
}

// Open the cache management panel and record the target Agent (the Agent owning the clicked Panel)
function openBufferPanel(panel) {
  bufferPanelAgentId.value = panel?.agentId ?? null
  showBufferPanel.value = true
}

const hasBufferedInput = computed(() => {
  const agentId = bufferPanelAgentId.value
  return agentId ? inputBuffers.value.has(agentId) : false
})

// Watch for the cache panel opening, automatically load the cache content
watch(showBufferPanel, (newVal) => {
  if (newVal && hasBufferedInput.value) {
    const agentId = bufferPanelAgentId.value
    if (agentId && inputBuffers.value.has(agentId)) {
      bufferEditText.value = inputBuffers.value.get(agentId)
    }
  }
})

// Watch for the settings panel opening, automatically fetch the node status
watch(showSettingsModal, (newVal) => {
  if (newVal) {
    fetchNodeStatus()
  }
})

// Panel layout management
const panels = ref([]) // [{ id, agentId: null }]
const activePanelId = ref(null)

// Create a new Panel
function createPanel() {
  const panel = {
    id: `panel-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    agentId: null
  }
  panels.value.push(panel)
  activePanelId.value = panel.id
}

// Close Panel
function closePanel(panelId) {
  const index = panels.value.findIndex(p => p.id === panelId)
  if (index === -1) return
  const panel = panels.value[index]
  // If the Panel has an Agent, close the Agent session
  if (panel.agentId) {
    closeAgentInPanel(panelId)
  }
  panels.value.splice(index, 1)
  panelOutputLists.delete(panelId)
  sessionPanelRefs.delete(panelId)
  // If the closed Panel is currently hosted by the editor, dangling references must be cleaned up, otherwise the editor will point to a no-longer-existing
  // Panel (blank session view). It has been unified into a pane tree: find the pane hosting it and clear it to empty;
  // if not found (fallback when unsplit and the main area is session), fall back to the file view.
  if (workspaceSessionPanelId.value === panelId) {
    workspaceSessionPanelId.value = null
    const hostingPane = findWorkspacePaneBySessionPanelId(panelId)
    if (hostingPane) {
      hostingPane.view = 'empty'
      hostingPane.sessionPanelId = null
      persistWorkspacePaneLayout()
    } else if (workspaceMainView.value === 'session') {
      setMainViewOnLeaf('file')
    }
  }
  // If the closed one is the currently active Panel, activate an adjacent Panel
  if (activePanelId.value === panelId) {
    if (panels.value.length > 0) {
      const newIndex = Math.min(index, panels.value.length - 1)
      const nextPanel = panels.value[newIndex]
      activePanelId.value = nextPanel.id
      // When closing the current Panel, currentAgentId is cleared, so switch back to the newly activated Panel's Agent
      if (nextPanel.agentId && currentAgentId.value !== nextPanel.agentId) {
        const nextAgent = agentList.value.find(a => a.agent_id === nextPanel.agentId)
        if (nextAgent) switchAgent(nextAgent)
      }
    } else {
      activePanelId.value = null
    }
  }
}

// Mobile back button: close all currently visible embedded Panels (including terminal/chat/editor), and return to the pet lobby.
// Mobile allows only one embedded Panel, so simply closing all visible items is enough.
function closeVisiblePanelsOnMobile() {
  if (showTerminalPanel.value) showTerminalPanel.value = false
  if (showChatPanel.value) showChatPanel.value = false
  if (showWorkspacePanel.value) closeWorkspacePanel()
  for (const panel of [...panels.value]) {
    closePanel(panel.id)
  }
}

// Close the Agent in the Panel (keep the Panel)
function closeAgentInPanel(panelId) {
  const panel = panels.value.find(p => p.id === panelId)
  if (!panel || !panel.agentId) return
  const agentId = panel.agentId
  panel.agentId = null
  panelOutputLists.delete(panelId)
  // Clear the embedded confirm data of this Agent's Panel
  panelConfirmData.value.delete(agentId)
  // Clear the auto-scroll toggle of this Agent's Panel
  panelAutoScrolls.value.delete(agentId)
  // Clear the auto-read toggle of this Agent's Panel
  panelAutoReads.value.delete(agentId)
  // Clear the input state of this Agent's Panel
  panelInputTexts.value.delete(agentId)
  panelInputTips.value.delete(agentId)
  panelInputModes.value.delete(agentId)
  // If the current Agent is being closed, clear the current Agent ID
  if (currentAgentId.value === agentId) {
    currentAgentId.value = null
  }
}

// Activate Panel
function activatePanel(panelId) {
  activePanelId.value = panelId
  const panel = panels.value.find(p => p.id === panelId)
  if (panel && panel.agentId) {
    // If the Panel has an Agent, switch the current Agent
    const agent = agentList.value.find(a => a.agent_id === panel.agentId)
    if (agent) {
      switchAgent(agent)
    }
  }
}

// When already split, open the Agent into the "active pane" (requirement: a new Panel lands in the active area;
// if that area already has a Panel, close the old one and let the new one cover it). Returning true means it has been handled.
// Note: only operate on the active pane, never touch Panels hosted by other panes (otherwise the sessions in other areas would be cleared).
// Note: when the active pane already hosts an Agent session, do not cover it, but open a new panel (new pane) to keep the current session,
// avoiding covering the current session when switching Agent from the command palette/sidebar.
function openAgentInActivePane(agent) {
  const activePaneLeaf = activePane.value
  if (!activePaneLeaf) return false
  // Panel already hosted by the active pane
  const hostedPanel = activePaneLeaf.view === 'session' && activePaneLeaf.sessionPanelId
    ? panels.value.find(p => p.id === activePaneLeaf.sessionPanelId)
    : null
  // Active pane already hosts an Agent session: do not cover. If it hosts exactly this Agent, no action is needed (already displayed);
  // otherwise open a new panel (new pane) to host it, keeping the current session.
  if (hostedPanel) {
    if (hostedPanel.agentId === agent.agent_id) {
      activateWorkspacePane(activePaneLeaf.id)
      return true
    }
    openAgentInNewPane(agent)
    return true
  }
  // Active pane is a file/empty area: the new Panel lands in the active pane (covering the file view is reasonable)
  const targetPanel = {
    id: `panel-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    agentId: agent.agent_id
  }
  panels.value.push(targetPanel)
  activePanelId.value = targetPanel.id
  workspaceSessionPanelId.value = targetPanel.id
  // If empty, keep in place; if a pane already hosting this Panel exists, reuse it; otherwise split (without covering the current area)
  ensurePaneForView('session', targetPanel.id)
  switchAgent(agent)
  nextTick(() => maybeStartTour('panel'))
  return true
}

// When already split and the active pane already hosts an Agent session: open a new panel (new pane), keeping the current session.
// Create a new Panel and let ensurePaneForView split a new pane to host it (without covering the active pane's session).
// The caller must ensure the agent is not in any existing Panel (all call sites of openAgentInActivePane already handle this in advance).
function openAgentInNewPane(agent) {
  if (!agent) return
  const targetPanel = {
    id: `panel-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    agentId: agent.agent_id
  }
  panels.value.push(targetPanel)
  activePanelId.value = targetPanel.id
  workspaceSessionPanelId.value = targetPanel.id
  // If empty, keep in place; if a pane already hosting this Panel exists, reuse it; otherwise split (without covering the current area)
  ensurePaneForView('session', targetPanel.id)
  switchAgent(agent)
  nextTick(() => maybeStartTour('panel'))
}

// Open Agent in a Panel (replaces switchAgent)
function openAgentInPanel(agent, panelId = null) {
  // All embedded Panels render only inside the editor: when opening an Agent from entrances such as the pet lobby,
  // the editor must be ensured to be open, otherwise the Panel loses its host and becomes invisible.
  showWorkspacePanel.value = true
  // Mobile does not support multiple Panels, switch directly
  if (windowWidth.value <= 768) {
    // When entering a Panel from the lobby, push a history state so the mobile back button can close the Panel and return to the lobby
    // (do not push repeatedly when a visible Panel already exists, to avoid needing to press back several times)
    if (hasNoPanel.value) {
      pushOverlayState()
    }
    // Ensure at least one Panel exists
    if (panels.value.length === 0) {
      createPanel()
    }
    // Put the Agent into the currently active Panel
    const targetPanel = panels.value.find(p => p.id === activePanelId.value) || panels.value[0]
    if (targetPanel) {
      targetPanel.agentId = agent.agent_id
      // Embedded Panels render only inside the editor: this Panel must be handed to the session view of the editor main area to host,
      // otherwise the Panel loses its host and becomes invisible (on mobile, double-clicking the pet from the lobby follows this path).
      workspaceSessionPanelId.value = targetPanel.id
      setWorkspaceMainView('session')
    }
    switchAgent(agent)
    return
  }
  // It has been unified into a pane tree: route the Agent to open in the "active pane" (when unsplit, activePane is the only leaf).
  // Otherwise the Panel would render as a full grid cell of panel-grid outside the editor, and the user perceives it as "the Agent's panel escaping the editor".
  const existingPanel = panels.value.find(p => p.agentId === agent.agent_id)
  if (existingPanel) {
    const hostingPane = findWorkspacePaneBySessionPanelId(existingPanel.id)
    if (hostingPane) {
      activateWorkspacePane(hostingPane.id)
    } else {
      // If empty, keep in place; otherwise split (without covering the current area)
      ensurePaneForView('session', existingPanel.id)
    }
    activePanelId.value = existingPanel.id
    switchAgent(agent)
    workspaceSessionPanelId.value = existingPanel.id
    return
  }
  // Explicitly specify panelId (e.g. command palette): put it directly into the active pane.
  if (panelId) {
    const targetPanel = panels.value.find(p => p.id === panelId)
    if (targetPanel) {
      targetPanel.agentId = agent.agent_id
      activePanelId.value = targetPanel.id
      workspaceSessionPanelId.value = targetPanel.id
      // If empty, keep in place; if a pane already hosting this Panel exists, reuse it; otherwise split (without covering the current area)
      ensurePaneForView('session', targetPanel.id)
      switchAgent(agent)
      return
    }
  }
  // Requirement: a newly created Panel lands in the "active pane"; if that pane already has a Panel, close the old one and let the new one cover it.
  openAgentInActivePane(agent)
}

// "Open Agent in current Panel": used when pressing Enter in the command palette
// - Agent already in some Panel: activate that Panel
// - Otherwise put it into the currently active Panel (covering the Agent already in it); create one when there is no Panel
function openAgentInCurrentPanel(agent) {
  if (!agent) return
  // Mobile does not support multiple Panels, switch directly
  if (windowWidth.value <= 768) {
    openAgentInPanel(agent)
    return
  }
  // Embedded Panels render only inside the editor: the editor must be ensured to be open and the Panel to be hosted by the editor,
  // otherwise the Panel loses its host and becomes invisible (especially obvious when the editor stays in the file view or is already split).
  showWorkspacePanel.value = true
  const existingPanel = panels.value.find(p => p.agentId === agent.agent_id)
  if (existingPanel) {
    // It has been unified into a pane tree: set the pane hosting this Panel as active; if not hosted, put it into the active pane.
    const hostingPane = findWorkspacePaneBySessionPanelId(existingPanel.id)
    if (hostingPane) {
      activateWorkspacePane(hostingPane.id)
    } else {
      // If empty, keep in place; otherwise split (without covering the current area)
      ensurePaneForView('session', existingPanel.id)
    }
    activePanelId.value = existingPanel.id
    workspaceSessionPanelId.value = existingPanel.id
    switchAgent(agent)
    return
  }
  // It has been unified into a pane tree: put the Agent into the "active pane" (if that pane already has a Panel, cover it in place)
  openAgentInActivePane(agent)
}

// "Open Agent in a new Panel": used when pressing Tab in the command palette
// - Agent already in some Panel: activate it (avoid opening the same Agent twice)
// - Otherwise always create a new Panel
function openAgentInNewPanel(agent) {
  if (!agent) return
  if (windowWidth.value <= 768) {
    openAgentInPanel(agent)
    return
  }
  const existingPanel = panels.value.find(p => p.agentId === agent.agent_id)
  if (existingPanel) {
    activePanelId.value = existingPanel.id
    switchAgent(agent)
    return
  }
  const targetPanel = { id: `panel-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, agentId: null }
  panels.value.push(targetPanel)
  targetPanel.agentId = agent.agent_id
  activePanelId.value = targetPanel.id
  switchAgent(agent)
}

// Get the Agent in the Panel
function getPanelAgent(panel) {
  if (!panel || !panel.agentId) return null
  return agentList.value.find(a => a.agent_id === panel.agentId) || null
}

// Get the Panel's message list
function getPanelMessages(panel) {
  if (!panel || !panel.agentId) return []
  return allOutputs.value.get(panel.agentId) || []
}

// Get the Panel's input text
function getPanelInputText(panel) {
  if (!panel || !panel.agentId) return ''
  return panelInputTexts.value.get(panel.agentId) || ''
}

// Get the Panel's input mode
function getPanelInputMode(panel) {
  if (!panel || !panel.agentId) return 'multi'
  return panelInputModes.value.get(panel.agentId) || 'multi'
}

// Get the Panel's input tip
function getPanelInputTip(panel) {
  if (!panel || !panel.agentId) return ''
  return panelInputTips.value.get(panel.agentId) || ''
}

// Get the Panel's password input flag
function getPanelInputPassword(panel) {
  if (!panel || !panel.agentId) return false
  return panelInputPasswords.value.get(panel.agentId) || false
}

// Get the Panel's input request
function getPanelInputRequest(panel) {
  if (!panel || !panel.agentId) return null
  return inputRequests.value.get(panel.agentId) || null
}

// Get the Panel's Agent status
function getPanelAgentStatus(panel) {
  if (!panel || !panel.agentId) return null
  return agentStatuses.value.get(panel.agentId) || null
}

// Get the Panel's confirm data
function getPanelConfirmData(panel) {
  if (!panel || !panel.agentId) return null
  return panelConfirmData.value.get(panel.agentId) || null
}

// Get the Panel's auto-scroll toggle state
function getPanelAutoScroll(panel) {
  if (!panel || !panel.agentId) return true
  return panelAutoScrolls.value.get(panel.agentId) !== false
}

// Toggle the Panel's auto-scroll
function togglePanelAutoScroll(panel, value) {
  if (!panel || !panel.agentId) return
  panelAutoScrolls.value.set(panel.agentId, value)
}

// Determine whether the specified Agent has auto-scroll enabled (default true)
function isAutoScrollEnabled(agentId) {
  if (!agentId) return true
  return panelAutoScrolls.value.get(agentId) !== false
}

// Get the Panel's auto-read toggle state (default false)
function getPanelAutoRead(panel) {
  if (!panel || !panel.agentId) return false
  return panelAutoReads.value.get(panel.agentId) === true
}

// Toggle the Panel's auto-read
function togglePanelAutoRead(panel, value) {
  if (!panel || !panel.agentId) return
  panelAutoReads.value.set(panel.agentId, value)
  if (!value) {
    stopAutoRead()
  }
}

// Determine whether the specified Agent has auto-read enabled (default false)
function isAutoReadEnabled(agentId) {
  if (!agentId) return false
  return panelAutoReads.value.get(agentId) === true
}
// Audio prompt / auto-read / system notification (extracted from a standalone composable)
const {
  autoReadSupported,
  notifyInputRequest,
  playChatNotificationSound,
  stopAutoRead,
  handleAutoRead,
  sendSystemNotification,
} = useAudioNotifications({
  sessionPanelRefs,
  allOutputs,
  panelInputTips,
  panels,
  isAutoReadEnabled,
})
// History input management (extracted from a standalone composable)
const {
  inputHistory,
  lobbyHistoryIndex,
  lobbyHistoryTemp,
  loadInputHistory,
  saveToHistory,
  navigateHistory,
  onLobbyHistoryNav,
} = useInputHistory({
  inputText,
  panelInputTexts,
})
// Get the Panel's terminal list
function getPanelTerminals(panel) {
  if (!panel || !panel.agentId) return []
  return terminals.value.filter(t => t.agentId === panel.agentId)
}

// Get the Panel's terminal host
function getPanelTerminalHosts(panel) {
  if (!panel || !panel.agentId) return new Map()
  const hosts = new Map()
  for (const [sessionKey, hostEl] of terminalHosts.value.entries()) {
    const [agentId] = sessionKey.split(':')
    if (agentId === panel.agentId) {
      hosts.set(sessionKey, hostEl)
    }
  }
  return hosts
}

// Get the Panel's input disabled state
function getPanelInputDisabled(panel) {
  if (!panel || !panel.agentId) return true
  const agent = getPanelAgent(panel)
  if (!agent || agent.status !== 'running') return true
  return false
}

// Get the Panel's waiting-for-multiline disabled state
function getPanelWaitingMultiDisabled(panel) {
  if (!panel || !panel.agentId) return true
  const statusData = agentStatuses.value.get(panel.agentId)
  const executionStatus = statusData?.execution_status || 'running'
  // Not disabled while waiting for multiline input (input allowed), disabled in other states
  return executionStatus !== 'waiting_multi'
}

// Get the Panel's streaming messages
function getPanelStreamingMessages(panel) {
  if (!panel || !panel.agentId) return new Map()
  const msgs = new Map()
  for (const [agentId, msg] of streamingMessages.value.entries()) {
    if (agentId === panel.agentId) {
      msgs.set(agentId, msg)
    }
  }
  return msgs
}

// Get the Panel's history loading state
function getPanelHistoryState(panel) {
  if (!panel || !panel.agentId) return { isLoading: false, hasMore: false }
  return {
    isLoading: isLoadingHistory.value,
    hasMore: hasMoreHistory.value
  }
}

// Whether the editor main area is currently hosting the chat room / terminal (in that case the standalone panel yields, to avoid the same state being contended by two instances)
// It has been unified into a pane tree: when some pane's view === 'chat'/'terminal' (host singleton, at most one), it is considered hosting.
const workspaceHostsChat = computed(() =>
  showWorkspacePanel.value && !!findWorkspacePaneByView('chat')
)
const workspaceHostsTerminal = computed(() =>
  showWorkspacePanel.value && !!findWorkspacePaneByView('terminal')
)
// Whether the editor main area is currently hosting a session panel (in that case the corresponding panel in the grid yields, to avoid the same xterm host being contended by two instances)
const workspaceHostsSession = computed(() => showWorkspacePanel.value && workspaceMainView.value === 'session')
// The panel currently displayed by the editor main area's session view (determined by clicking the Agent list in the editor sidebar)
const workspaceSessionPanelId = ref(null)
// The panel currently occupied by the editor: as long as the editor panel is open and a panel has been selected, let it yield from the grid.
// Do not return to the grid when the main area view (file/chat/terminal/session) changes, otherwise when clicking chat/terminal
// that panel would appear "out of nowhere" in the grid and mess up the layout (the user expects a replacement, not coexistence).
const workspaceHostedPanel = computed(() => {
  if (!showWorkspacePanel.value || !workspaceSessionPanelId.value) return null
  // It has been unified into a pane tree: only let the panel yield from the grid when it is hosted by some pane;
  // if no pane hosts it (e.g. the pane hosting it was switched to file/chat/terminal),
  // then render it back in the grid, to avoid the panel "vanishing out of nowhere".
  const hostingPane = findWorkspacePaneBySessionPanelId(workspaceSessionPanelId.value)
  if (!hostingPane) return null
  return panels.value.find(p => p.id === workspaceSessionPanelId.value) || null
})
// The panel corresponding to the editor session view: prefer the recorded panel, fall back to the currently active/first panel bound to an Agent
const workspaceSessionPanel = computed(() => {
  if (!workspaceHostsSession.value) return null
  const byId = workspaceHostedPanel.value
  if (byId) return byId
  const active = panels.value.find(p => p.id === activePanelId.value && p.agentId)
  if (active) return active
  return panels.value.find(p => p.agentId) || null
})

// The set of "currently visible" session Agents: i.e. the Agent sessions actually displayed on the interface at this moment.
// Note: it cannot be judged by "whether the panel object holds an agentId"—after the panel is collapsed (view switched back to file)
// panel.agentId is still present, but the session is no longer visible. The command palette uses this to judge "whether selecting it merely switches back to itself":
// when the session is invisible, selecting it is meaningful (reopening), so it must not be grayed out.
const visibleSessionAgentIds = computed(() => {
  const ids = new Set()
  // It has been unified into a pane tree: traverse the pane tree to collect all panes hosting sessions (when unsplit, the only leaf is also traversed).
  const walk = (node) => {
    if (!node) return
    if (node.type === 'leaf') {
      if (node.view === 'session' && node.sessionPanelId) {
        const panel = panels.value.find(p => p.id === node.sessionPanelId)
        if (panel && panel.agentId) ids.add(panel.agentId)
      }
      return
    }
    ;(node.children || []).forEach(walk)
  }
  walk(workspacePaneTree.value)
  return ids
})

// The number of top-level child items actually rendered in the grid (used for panel-grid's column/row layout).
// Note: session/terminal/chat panels always render only inside the editor panel (or as floating panels),
// they are not direct children of panel-grid, so they must never be counted in the grid layout, otherwise the phenomenon
// of "the grid split into two columns but only one child item" → the editor occupying only half the width with blank space on the right would occur.
const embeddedPanelCount = computed(() => {
  // The only child item in the grid is the editor panel (empty state when not open)
  return showWorkspacePanel.value ? 1 : 0
})

// Whether there is currently no visible embedded Panel (used to display the empty-state welcome background)
const hasNoPanel = computed(() => embeddedPanelCount.value === 0)
// Whether the first Agent list fetch has completed (regardless of success or failure).
// The declaration must precede the immediate watch below (otherwise the watch's immediate evaluation would hit the TDZ).
const agentListLoaded = ref(false)

// Display the lobby scene guide when first entering the pet lobby (with no visible Panel)
// It must trigger after the first Agent list fetch completes (agentListLoaded): when not logged in, the list has not been fetched yet,
// and the login dialog is covering the lobby, so showing the guide at that time is both invisible and would be mistakenly marked as already seen.
watch([hasNoPanel, agentListLoaded], ([noPanel, loaded]) => {
  if (noPanel && loaded) maybeStartTour('lobby')
}, { immediate: true })

// Get the Panel's layout style
function getPanelLayout() {
  const count = embeddedPanelCount.value
  if (count === 0) return {}
  if (count === 1) return { gridTemplateColumns: '1fr', gridTemplateRows: '1fr' }
  if (count === 2) return { gridTemplateColumns: '1fr 1fr', gridTemplateRows: '1fr' }
  if (count === 3) return { gridTemplateColumns: '1fr 1fr', gridTemplateRows: '1fr 1fr' }
  if (count === 4) return { gridTemplateColumns: '1fr 1fr', gridTemplateRows: '1fr 1fr' }
  if (count === 5) return { gridTemplateColumns: '1fr 1fr 1fr', gridTemplateRows: '1fr 1fr' }
  return { gridTemplateColumns: '1fr 1fr 1fr', gridTemplateRows: '1fr 1fr' }
}

// Panel grid layout style (computed property)
const panelGridStyle = computed(() => {
  return getPanelLayout()
})

// Get the Panel's buffered input state
function getPanelHasBufferedInput(panel) {
  if (!panel || !panel.agentId) return false
  return inputBuffers.value.has(panel.agentId)
}

// Send a message from the Panel
function sendFromPanel(panel) {
  if (!panel || !panel.agentId) return
  const agentId = panel.agentId
  const agent = getPanelAgent(panel)
  if (!agent || agent.status !== 'running') return

  // Single-line input mode: allow sending an empty string
  // Multiline input mode: do not allow sending an empty string (except when the buffer has content)
  const panelInput = panelInputTexts.value.get(agentId) || ''
  const panelInputMode = getPanelInputMode(panel)
  const hasBuffered = inputBuffers.value.has(agentId) && (inputBuffers.value.get(agentId) || '').trim()
  let userInput
  if (panelInputMode === 'single') {
    userInput = panelInput
  } else {
    userInput = panelInput.trim()
    if (!userInput && !hasBuffered) return
  }

  // Get the current running status
  const statusData = agentStatuses.value.get(agentId)
  const executionStatus = statusData?.execution_status || 'running'

  // Waiting for confirmation state: Enter sends the confirmation result
  if (executionStatus === 'waiting_confirm') {
    const trimmedInput = userInput.trim().toLowerCase()
    // Empty input or y/yes/confirm is treated as confirm, n/no/cancel is treated as cancel
    const confirmed = trimmedInput === '' || trimmedInput === 'y' || trimmedInput === 'yes' || trimmedInput === 'confirm' || trimmedInput === 'yes'
    sendConfirmResult(confirmed, agentId)
    // Clear the input box
    panelInputTexts.value.set(agentId, '')
    inputText.value = ''
    return
  }

  // Determine whether to send to the buffer or send directly
  if (panelInputMode === 'single' || executionStatus === 'waiting_multi') {
    // The backend is waiting for input, send directly
    // If there is buffer content, send the buffer content first
    let sendText = userInput
    if (hasBuffered) {
      const bufferedText = inputBuffers.value.get(agentId)
      inputBuffers.value.delete(agentId)
      sendText = bufferedText
      // If the input box also has content, append it after the buffer content
      if (userInput) {
        sendText = `${bufferedText}\n${userInput}`
      }
      // Buffer has been consumed: if the cache panel is currently showing that Agent, close the panel and reset the editor text
      closeBufferPanelIfForAgent(agentId)
    }
    const message = {
      type: 'input_result',
      payload: {
        text: sendText,
        agent_id: agentId,
        display_name: chatName.value || username.value || '',
        input_mode: panelInputMode,
      },
    }
    sendMessageToAgent(message, agentId)
    // Delete this Agent's input request from the Map
    inputRequests.value.delete(agentId)
  } else if (hasBuffered) {
    // There is buffer content and the backend is not waiting for input, send the buffer content
    sendBufferedInput(agentId)
    // If the input box also has content, append to the buffer
    if (userInput) {
      const existingText = inputBuffers.value.get(agentId) || ''
      const nextValue = existingText ? `${existingText}\n${userInput}` : userInput
      inputBuffers.value.set(agentId, nextValue)
      appendOutput({
        output_type: 'system',
        agent_name: 'system',
        text: '✓ Input appended to buffer, waiting for backend request',
        lang: 'text',
      }, agentId)
    }
  } else {
    // The backend is not waiting for input, save to the buffer
    const existingText = inputBuffers.value.get(agentId) || ''
    const nextValue = existingText ? `${existingText}\n${userInput}` : userInput
    inputBuffers.value.set(agentId, nextValue)
    appendOutput({
      output_type: 'system',
      agent_name: 'system',
      text: '✓ Input appended to buffer, waiting for backend request',
      lang: 'text',
    }, agentId)
  }

  // Save to history
  saveToHistory(userInput)
  panelInputTexts.value.set(agentId, '')
  inputText.value = ''
}

// Complete input from Panel
function completeFromPanel(panel) {
  if (!panel || !panel.agentId) return
  const agentId = panel.agentId
  const statusData = agentStatuses.value.get(agentId)
  const executionStatus = statusData?.execution_status || 'running'
  // Remember the original state to restore after confirm/cancel
  const originalStatus = executionStatus

  // Use Panel inline confirmation instead of a global popup dialog
  panelConfirmData.value.set(agentId, {
    message: 'Are you sure you want to send the completion signal?',
    defaultConfirm: true,
    onConfirm: () => {
      if (executionStatus === 'waiting_multi') {
        // The backend is waiting for multi-line input, send the Ctrl+C signal directly
        const message = {
          type: 'input_result',
          payload: {
            text: '__CTRL_C_PRESSED__',
            agent_id: agentId,
            display_name: chatName.value || username.value || '',
            input_mode: 'single',
          },
        }
        sendMessageToAgent(message, agentId)
      } else {
        // The backend is not waiting for input, save the completion signal to the buffer
        inputBuffers.value.set(agentId, '__CTRL_C_PRESSED__')
        appendOutput({
          output_type: 'system',
          agent_name: 'system',
          text: '✅ Completion signal saved to buffer, automatically triggered next time input is needed',
          lang: 'text',
        }, agentId)
      }
      // Restore input mode to multi-line
      inputMode.value = 'multi'
      panelInputModes.value.set(agentId, 'multi')
      inputTip.value = ''
      panelInputTips.value.set(agentId, '')
      // Restore Agent status to the original state
      agentStatuses.value.set(agentId, {execution_status: originalStatus})
    },
    onCancel: () => {
      // On cancel, restore input mode to multi-line
      inputMode.value = 'multi'
      panelInputModes.value.set(agentId, 'multi')
      inputTip.value = ''
      panelInputTips.value.set(agentId, '')
      // Restore Agent status to the original state
      agentStatuses.value.set(agentId, {execution_status: originalStatus})
    },
  })

  // Synchronously set the waiting_confirm state so that the Enter/y/n keys in handlePanelKeydown can respond
  agentStatuses.value.set(agentId, {execution_status: 'waiting_confirm'})
  // Use single-line input mode for the confirmation request to avoid the multi-line input box stealing focus
  inputMode.value = 'single'
  panelInputModes.value.set(agentId, 'single')
  inputTip.value = 'Are you sure you want to send the completion signal? (Enter/y confirm, n cancel)'
  panelInputTips.value.set(agentId, 'Are you sure you want to send the completion signal? (Enter/y confirm, n cancel)')

  // Focus the input box
  const sessionPanel = sessionPanelRefs.get(panel.id)
  if (sessionPanel?.focusInput) {
    sessionPanel.focusInput()
  }
}

// Open completions from Panel
// Open completions from Panel
async function openCompletionsFromPanel(panel) {
  if (!panel || !panel.agentId) return
  const agent = getPanelAgent(panel)
  if (!agent) {
    alert('Please select an Agent first')
    return
  }

  completionAgentId.value = panel.agentId
  completionSource.value = 'panel'
  // When triggered by the @ button (without going through handlePanelInputChange / handlePanelKeydown),
  // There is no @ symbol in the input box, so record the current cursor position as the insertion point and mark that the @ does not need to be deleted
  if (completionCursorPos.value === -1) {
    const textarea = document.querySelector(`.input-wrapper textarea[data-agent-id="${panel.agentId}"]`) || document.querySelector('.input-wrapper textarea')
    if (textarea) {
      completionCursorPos.value = textarea.selectionStart
    }
    completionHasAtSymbol.value = false
  }
  completionSearch.value = ''
  selectedIndex.value = -1
  showCompletions.value = true
  try {
    const { host, port } = getGatewayAddress()
    const targetNodeId = String(agent?.node_id || '').trim() || 'master'
    const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `completions/${agent.agent_id}`))

    const result = await response.json()

    if (!response.ok) {
      alert(`Failed to get completion list: ${result.error?.message || result.detail || 'Unknown error'}`)
      return
    }

    if (result.success && result.data) {
      completions.value = sortCompletionItems(result.data)
    } else {
      console.error('[COMPLETIONS] Invalid format:', result)
      alert('Failed to get completion list: returned data format error')
    }
  } catch (error) {
    console.error('[COMPLETIONS] Fetch failed:', error)
    alert(`Failed to get completion list: ${error.message}`)
  }

  // Focus the search box on PC, do not focus on mobile
  if (windowWidth.value > 768) {
    nextTick(() => {
      completionSearchInput.value?.focus()
    })
  }
}

// Open completions from the pet lobby input box: agentId is the corresponding pet in the lobby, cursorPos is the @ symbol position
async function onLobbyOpenCompletions(agentId, cursorPos) {
  if (!agentId) return
  const agent = agentList.value.find(a => a.agent_id === agentId)
  if (!agent) return

  completionAgentId.value = agentId
  completionSource.value = 'lobby'
  completionCursorPos.value = typeof cursorPos === 'number' ? cursorPos : -1
  completionHasAtSymbol.value = true
  completionSearch.value = ''
  selectedIndex.value = -1
  showCompletions.value = true
  try {
    const { host, port } = getGatewayAddress()
    const targetNodeId = String(agent?.node_id || '').trim() || 'master'
    const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `completions/${agentId}`))

    const result = await response.json()

    if (!response.ok) {
      alert(`Failed to get completion list: ${result.error?.message || result.detail || 'Unknown error'}`)
      return
    }

    if (result.success && result.data) {
      completions.value = sortCompletionItems(result.data)
    } else {
      console.error('[COMPLETIONS] Invalid format:', result)
      alert('Failed to get completion list: returned data format error')
    }
  } catch (error) {
    console.error('[COMPLETIONS] Fetch failed:', error)
    alert(`Failed to get completion list: ${error.message}`)
  }

  // Focus the search box on PC, do not focus on mobile
  if (windowWidth.value > 768) {
    nextTick(() => {
      completionSearchInput.value?.focus()
    })
  }
}

// Handle Panel input changes
function handlePanelInputChange(panel, event) {
  if (!panel || !panel.agentId) return
  const target = event.target
  // Update the input text of that Panel
  panelInputTexts.value.set(panel.agentId, target.value)
  // Synchronize the global input text (for compatibility)
  inputText.value = target.value
  const cursorPosition = target.selectionStart
  const textBeforeCursor = target.value.substring(0, cursorPosition)

  // Detect whether the @ symbol was just typed (including via Chinese input method)
  // Note: here the @ has actually been written into the input box, so completionHasAtSymbol is set to false,
  // to avoid closeCompletionsWithoutSelect inserting another @ when canceling completions (which would result in two @)
  if (textBeforeCursor.endsWith('@')) {
    completionCursorPos.value = cursorPosition - 1
    completionHasAtSymbol.value = false
    openCompletionsFromPanel(panel)
  }
}

// Handle Panel keyboard events
function handlePanelKeydown(panel, event) {
  if (!panel || !panel.agentId) return
  const agentId = panel.agentId

  // @ key: open the completion list
  if (event.key === '@') {
    event.preventDefault()
    completionCursorPos.value = event.target.selectionStart
    completionHasAtSymbol.value = true
    openCompletionsFromPanel(panel)
    return
  }

  // waiting_confirm state: y/n keys send the confirmation result directly, Enter key triggers the default action
  const statusData = agentStatuses.value.get(agentId)
  const executionStatus = statusData?.execution_status || 'running'
  if (executionStatus === 'waiting_confirm') {
    if (event.key === 'y' || event.key === 'Y') {
      event.preventDefault()
      // Prefer the onConfirm callback of panelConfirmData (e.g. the completeFromPanel scenario)
      const confirmData = panelConfirmData.value.get(agentId)
      if (confirmData?.onConfirm) {
        handlePanelConfirm(panel)
      } else {
        sendConfirmResult(true, agentId)
      }
      return
    }
    if (event.key === 'n' || event.key === 'N') {
      event.preventDefault()
      // Prefer the onCancel callback of panelConfirmData (e.g. the completeFromPanel scenario)
      const confirmData = panelConfirmData.value.get(agentId)
      if (confirmData?.onCancel) {
        handlePanelCancelConfirm(panel)
      } else {
        sendConfirmResult(false, agentId)
      }
      return
    }
    if (event.key === 'Enter') {
      event.preventDefault()
      const confirmData = panelConfirmData.value.get(agentId)
      const defaultConfirm = confirmData?.defaultConfirm !== false
      if (defaultConfirm) {
        handlePanelConfirm(panel)
      } else {
        handlePanelCancelConfirm(panel)
      }
      return
    }
  }

  // Single-line input mode: Enter key submits directly
  if (event.key === 'Enter' && !event.ctrlKey && getPanelInputMode(panel) === 'single') {
    event.preventDefault()
    sendFromPanel(panel)
    return
  }

  // Ctrl+Enter / Ctrl+D submit input
  if (event.ctrlKey && (event.key === 'Enter' || event.key.toLowerCase() === 'd')) {
    event.preventDefault()
    sendFromPanel(panel)
    return
  }

  // Alt+T triggers terminal command execution
  if (event.altKey && (event.code === 'KeyT' || event.key === 't' || event.key === 'T')) {
    event.preventDefault()
    event.stopPropagation()
    panelInputTexts.value.set(agentId, '__ALT_T_PRESSED__')
    sendFromPanel(panel)
    return
  }

  // Ctrl+C triggers the completion function when waiting for multi-line input and the input box is empty
  // Ctrl+C sends a human intervention message when not in input mode and the input box is empty
  if (event.ctrlKey && event.key === 'c') {
    const userInput = (panelInputTexts.value.get(agentId) || '').trim()
    const statusData = agentStatuses.value.get(agentId)
    const executionStatus = statusData?.execution_status || 'running'

    // Scenario 1: trigger the completion function when waiting for multi-line input and the input box is empty
    if (executionStatus === 'waiting_multi' && !userInput) {
      event.preventDefault()
      completeFromPanel(panel)
      return
    }

    // Scenario 2: send a human intervention message when not in input mode (running) and the input box is empty
    if (executionStatus === 'running' && !userInput) {
      event.preventDefault()
      const message = {
        type: 'manual_interrupt',
        payload: {},
      }
      sendMessageToAgent(message, agentId)
      return
    }
  }

  // Up arrow: check if on the first line, and only then trigger history
  // When Ctrl/Alt/Meta modifier keys are held, leave it to the global shortcuts and do not do history navigation
  if (event.key === 'ArrowUp') {
    if (event.ctrlKey || event.altKey || event.metaKey) return
    const textarea = event.target
    if (isCursorAtFirstLine(textarea)) {
      event.preventDefault()
      navigateHistory('up', agentId)
    }
    return
  }

  // Down arrow: check if on the last line, and only then trigger history
  if (event.key === 'ArrowDown') {
    if (event.ctrlKey || event.altKey || event.metaKey) return
    const textarea = event.target
    if (isCursorAtLastLine(textarea)) {
      event.preventDefault()
      navigateHistory('down', agentId)
    }
    return
  }
}

// Handle Panel paste events
function handlePanelPaste(panel, event) {
  if (!panel || !panel.agentId) return
  const items = event.clipboardData?.items
  if (!items) return

  for (const item of items) {
    if (item.type.startsWith('image/')) {
      event.preventDefault()
      const file = item.getAsFile()
      if (file) {
        uploadImageToNode(file, panel.agentId)
      }
      break
    }
  }
}

// Clear the buffer from Panel
function clearBufferFromPanel(panel) {
  if (!panel || !panel.agentId) return
  const agentId = panel.agentId
  inputBuffers.value.delete(agentId)
  // After clearing, if the cache panel is currently showing that Agent, close the panel and reset the editor text
  closeBufferPanelIfForAgent(agentId)
  appendOutput({
    output_type: 'system',
    agent_name: 'system',
    text: '🗑 Buffer cleared',
    lang: 'text',
  }, agentId)
}

// Set up scroll listening to load more history when scrolled to the top
// Supports dynamically switching the scroll container (called when a Panel is created/switched)
function setupHistoryScrollListener(el) {
  const SCROLL_THRESHOLD = 50 // Trigger when within 50px of the top
  const DEBOUNCE_DELAY = 500 // Debounce delay 500ms

  // Remove listeners on the old element
  if (historyScrollListenerEl && historyScrollHandler) {
    historyScrollListenerEl.removeEventListener('scroll', historyScrollHandler)
  }

  // Clear the old debounce timer
  if (historyScrollDebounceTimer) {
    clearTimeout(historyScrollDebounceTimer)
    historyScrollDebounceTimer = null
  }

  if (!el) {
    historyScrollListenerEl = null
    historyScrollHandler = null
    return
  }

  historyScrollListenerEl = el
  historyScrollHandler = () => {
    // Clear the previous timer
    if (historyScrollDebounceTimer) {
      clearTimeout(historyScrollDebounceTimer)
    }

    // Set a new timer
    historyScrollDebounceTimer = setTimeout(() => {
      const scrollTop = el.scrollTop
      if (scrollTop <= SCROLL_THRESHOLD && !isLoadingHistory.value && hasMoreHistory.value) {
        loadHistoryMessages(true) // prepend = true, insert at the beginning
      }
    }, DEBOUNCE_DELAY)
  }

  el.addEventListener('scroll', historyScrollHandler)
}

// Set the Panel's output list reference
function setPanelOutputList(panel, el) {
  if (!panel || !panel.agentId) return
  panelOutputLists.set(panel.id, el)
  if (panel.agentId === currentAgentId.value) {
    outputList.value = el
    // After a Panel is dynamically created, bind the scroll listener to ensure history can be loaded when scrolled to the top
    setupHistoryScrollListener(el)
  }
}

// Set the Panel's terminal reference
function setPanelTerminalRef(panel, executionId, el, agentId) {
  if (!panel || !panel.agentId) return
  const targetAgentId = agentId || panel.agentId
  if (!executionId) return
  // Delegate to setTerminalRef: uniformly handle xterm initialization/rebuild/cleanup
  setTerminalRef(executionId, el, targetAgentId)
}

// Send a message to the specified Agent
function sendMessageToAgent(message, agentId = null) {
  const targetAgentId = agentId || currentAgentId.value
  if (!targetAgentId) {
    console.warn('[SEND] No agent ID, cannot send message')
    return
  }

  const ws = sockets.value.get(targetAgentId)
  if (!ws) {
    console.warn(`[SEND] No WebSocket connection for agent ${targetAgentId}`)
    return
  }

  if (ws.readyState !== WebSocket.OPEN) {
    console.warn(`[SEND] WebSocket for agent ${targetAgentId} is not open, state: ${ws.readyState}`)
    return
  }

  ws.send(JSON.stringify(message))
}

// Load the history messages of the specified Agent
async function loadHistoryMessages(prepend = false, agentId = null) {
  const targetAgentId = agentId || currentAgentId.value
  // When there is no active agent, do not load history
  if (!targetAgentId) {
    return
  }

  if (isLoadingHistory.value) {
    return
  }

  if (!hasMoreHistory.value) {
    return
  }

  isLoadingHistory.value = true

  try {
    const historyMessages = historyStorage.loadHistory(historyStorage.MAX_MESSAGES_PER_PAGE, historyOffset.value, targetAgentId)

    if (historyMessages.length === 0) {
      hasMoreHistory.value = false
      isLoadingHistory.value = false
      return
    }

    // Save the current scroll position (used when prepending)
    let scrollPosition = 0
    if (prepend && outputList.value) {
      scrollPosition = outputList.value.scrollHeight - outputList.value.scrollTop
    }

    // stream message merging: merge STREAM_START/STREAM_CHUNK/STREAM_END into a single message
    const streamAccumulator = new Map() // agent_id -> accumulated message
    const mergedHistoryMessages = []
    for (const msg of historyMessages) {
          // Filter out internal control signals to prevent them from being displayed in the UI
          if (msg.text === '__CTRL_C_PRESSED__') {
            continue;
          }
      const outputType = msg.output_type
      if (outputType === 'STREAM_START') {
        const msgAgentId = msg.agent_id || targetAgentId
        streamAccumulator.set(msgAgentId, {
          ...msg,
          output_type: 'STREAM',
          text: '',
          isStreaming: false,
        })
        continue
      } else if (outputType === 'STREAM_CHUNK') {
        const msgAgentId = msg.agent_id || targetAgentId
        const acc = streamAccumulator.get(msgAgentId)
        if (acc) {
          acc.text += msg.text || ''
          if (typeof msg.seq === 'number') acc.seq = msg.seq
        } else {
          // Orphaned CHUNK (without STREAM_START), keep as a standalone message
          mergedHistoryMessages.push(msg)
        }
        continue
      } else if (outputType === 'STREAM_END') {
        const msgAgentId = msg.agent_id || targetAgentId
        const acc = streamAccumulator.get(msgAgentId)
        if (acc) {
          if (typeof msg.seq === 'number') acc.seq = msg.seq
          mergedHistoryMessages.push(acc)
          streamAccumulator.delete(msgAgentId)
        }
        continue
      }
      mergedHistoryMessages.push(msg)
    }

    // Handle leftover streaming messages that did not receive STREAM_END (abnormal cases)
    for (const acc of streamAccumulator.values()) {
      mergedHistoryMessages.push(acc)
    }
    historyMessages.length = 0
    historyMessages.push(...mergedHistoryMessages)

    // Process each history message
    const executionMessages = historyMessages.filter(msg => msg.output_type === 'execution')
    if (executionMessages.length > 0) {
    }
    // No longer filter the execution type, because it now carries the is_finished flag and can display historical content
    // Fix the is_finished flag of execution messages: terminal execution is serial, and only one execution runs for the same agent at a time
    // Scan from back to front: the last execution trusts the is_finished value in history; all preceding executions are forced to is_finished=true
    const executionIndices = []
    historyMessages.forEach((msg, idx) => {
      if (msg.output_type === 'execution') executionIndices.push(idx)
    })
    const processedMessages = historyMessages.map((msg, idx) => {
        if (msg.output_type === 'execution') {
          const isLast = executionIndices.length > 0 && idx === executionIndices[executionIndices.length - 1]
          if (!isLast && !msg.is_finished) {
            // Not the last execution: force mark as completed
            msg.is_finished = true
            // If there is no terminal_content (and no execution_chunks to fall back on), add placeholder text to avoid showing a blank area
            if (!msg.terminal_content && !(msg.execution_chunks?.length > 0)) {
              msg.terminal_content = '(Terminal output not saved or execution was interrupted)'
            }
          }
          // For the last execution: do not force mark as completed, keep the original state
          // It is only marked as completed when the backend's tool_stream_end event is received
          // This way, when switching back to the Agent, if execution is still in progress, xterm can render normally
          if (isLast && !msg.is_finished) {
          }
        }
        const html = renderMessageHtml(msg)
        // Generate a stable ID to avoid DOM re-creation caused by v-for using index as key
        const stableId = msg.execution_id
          ? `exec_${msg.execution_id}`
          : msg._stableId || `msg_${msg.timestamp || Date.now()}_${Math.random().toString(36).slice(2, 8)}`
        return {
          ...msg,
          html,
          timestamp: msg.timestamp || '',
          agent_name: msg.agent_name || '',
          non_interactive: msg.non_interactive !== undefined ? msg.non_interactive : false,
          agent_list: msg.agent_list || msg.context?.agent_list || '',
          _stableId: stableId,
        }
      })

    // Get the target Agent's message list
    const currentOutputs = allOutputs.value.get(targetAgentId) || []
    if (prepend) {
      // Insert at the beginning of the message list
      allOutputs.value.set(targetAgentId, [...processedMessages, ...currentOutputs])
    } else {
      // Merge history messages with existing messages, deduplicate (avoid duplicates)
      // History is a persisted complete sequence in positive order, so use it as the backbone; the parts of existing messages that history lacks
      // (such as pushes just received and not yet persisted) are appended to the end. This way, messages without seq such as execution (Xterm)
      // can also land in the correct position and will not be placed at the end of the list.
      const existingIds = new Set()
      for (const msg of processedMessages) {
        if (msg.execution_id) existingIds.add('exec_' + msg.execution_id)
        if (typeof msg.seq === 'number') existingIds.add('seq_' + msg.seq)
      }
      let merged = [...processedMessages]
      for (const msg of currentOutputs) {
        const execKey = msg.execution_id ? 'exec_' + msg.execution_id : null
        const seqKey = typeof msg.seq === 'number' ? 'seq_' + msg.seq : null
        if ((execKey && existingIds.has(execKey)) || (seqKey && existingIds.has(seqKey))) continue
        merged.push(msg)
        if (execKey) existingIds.add(execKey)
        if (seqKey) existingIds.add(seqKey)
      }
      // Fallback sorting: if an existing message has a smaller seq than history (abnormal cases such as truncated history storage),
      // only reposition messages with seq by seq; messages without seq keep their relative position in the original sequence.
      if (merged.some(msg => typeof msg.seq === 'number')) {
        let lastSeq = null
        merged = merged
          .map((msg, idx) => {
            if (typeof msg.seq === 'number') {
              lastSeq = msg.seq
              return { msg, idx, key: msg.seq, sub: 0 }
            }
            return { msg, idx, key: lastSeq === null ? -Infinity : lastSeq, sub: 1 }
          })
          .sort((a, b) => {
            if (a.key !== b.key) return a.key - b.key
            if (a.sub !== b.sub) return a.sub - b.sub
            return a.idx - b.idx
          })
          .map(item => item.msg)
      }
      allOutputs.value.set(targetAgentId, merged)
    }

    // Update the offset
    historyOffset.value += historyMessages.length

    // Check whether there is more history
    const totalCount = historyStorage.getTotalCount(targetAgentId)
    hasMoreHistory.value = historyOffset.value < totalCount


    // Restore the scroll position
    if (prepend && outputList.value) {
      nextTick(() => {
        requestAnimationFrame(() => {
          const newScrollHeight = outputList.value.scrollHeight
          outputList.value.scrollTop = newScrollHeight - scrollPosition
        })
      })
    } else {
      // On first history load, scroll to the bottom (only when auto-scroll is enabled)
      nextTick(() => {
        if (outputList.value && isAutoScrollEnabled(targetAgentId)) {
          outputList.value.scrollTop = outputList.value.scrollHeight
        }
      })
    }
  } catch (error) {
    console.error('[HISTORY] Failed to load history:', error)
  } finally {
    isLoadingHistory.value = false
  }
}

// Agent management
const agentList = ref([])        // Agent list
const currentAgentId = ref(null) // Currently connected Agent ID
const agentStatuses = ref(new Map()) // Agent status map (agent_id -> {execution_status, agent_status})
function isStoppedAgent(agent) {
  if (!agent) return false
  return getStatusClass(agent) === 'stopped'
}

const activeAgents = computed(() => {
  return agentList.value.filter(agent => !isStoppedAgent(agent))
})
// The respective Agent selections of global search / Git sidebar (they do not affect each other, nor the editor session or file tree).
// When not explicitly selected (null), follow the global current Agent; after the user selects, keep their own selection and do not let it be overridden by currentAgentId.
const globalSearchAgentId = ref(null)
const gitAgentId = ref(null)
const effectiveGlobalSearchAgentId = computed(() => globalSearchAgentId.value || currentAgentId.value)
const effectiveGitAgentId = computed(() => gitAgentId.value || currentAgentId.value)

// When the target Agent the Git view acts on changes, if currently staying in the Git view, re-fetch according to the new Agent's working directory.
// Watch effectiveGitAgentId (rather than only activeWorkspaceSessionId): clicking the session panel to switch Agent
// will update currentAgentId (and thus change effectiveGitAgentId), but will not change activeWorkspaceSessionId,
// otherwise the Git panel's commit list would not refresh with the new Agent.
watch(effectiveGitAgentId, () => {
  if (!showWorkspacePanel.value || workspaceSidebarView.value !== 'git') return
  nextTick(() => {
    refreshGitView()
  })
})

const stoppedAgents = computed(() => {
  return agentList.value.filter(agent => isStoppedAgent(agent))
})
// Sorted Agent list (active ones first, stopped ones after)
const sortedAgentList = computed(() => {
  return [...activeAgents.value, ...stoppedAgents.value]
})
// Stopped Agents grouped by node (kept for other possible references)
const stoppedAgentsByNode = computed(() => {
  const grouped = {}
  stoppedAgents.value.forEach(agent => {
    const nodeId = getAgentNodeLabel(agent)
    if (!grouped[nodeId]) {
      grouped[nodeId] = []
    }
    grouped[nodeId].push(agent)
  })
  return grouped
})
// Group all Agents by node, with non-stopped Agents pinned to the top within each node group
const agentsByNode = computed(() => {
  const grouped = {}
  // Create a map from agent_id to index, used to maintain reverse chronological order
  const agentIndexMap = new Map()
  agentList.value.forEach((agent, index) => {
    agentIndexMap.set(agent.agent_id, index)
  })
  
  agentList.value.forEach(agent => {
    const nodeId = getAgentNodeLabel(agent)
    if (!grouped[nodeId]) {
      grouped[nodeId] = { active: [], stopped: [] }
    }
    if (isStoppedAgent(agent)) {
      grouped[nodeId].stopped.push(agent)
    } else {
      grouped[nodeId].active.push(agent)
    }
  })
  
  // Sort the agents in each group by their index in agentList (maintaining reverse chronological order, newest at the top)
  Object.keys(grouped).forEach(nodeId => {
    grouped[nodeId].active.sort((a, b) => agentIndexMap.get(a.agent_id) - agentIndexMap.get(b.agent_id))
    grouped[nodeId].stopped.sort((a, b) => agentIndexMap.get(a.agent_id) - agentIndexMap.get(b.agent_id))
  })
  
  return grouped
})
const agentDisplayGroups = computed(() => {
  const groups = []

  // Set of already-grouped agent_ids (deduplicated, preserving definition order)
  const groupedAgentIds = new Set()

  // First collect the agent_ids in custom groups, for exclusion
  agentGroups.value.forEach(group => {
    if (!group.agentIds) group.agentIds = []
    group.agentIds.forEach(id => groupedAgentIds.add(id))
  })

  const sortedNodeIds = Object.keys(agentsByNode.value).sort()

  // First round: active Agents of all nodes (excluding already-grouped ones)
  sortedNodeIds.forEach(nodeId => {
    const nodeAgents = agentsByNode.value[nodeId]
    const active = nodeAgents.active.filter(agent => !groupedAgentIds.has(agent.agent_id))
    if (active.length > 0) {
      groups.push({
        key: `node-${nodeId}`,
        title: nodeId,
        agents: active,
        isCollapsible: false,
      })
    }
  })

  // Second round: custom groups (collapsible)
  agentGroups.value.forEach(group => {
    if (!group.agentIds) group.agentIds = []
    const agents = agentList.value.filter(agent =>
      group.agentIds.includes(agent.agent_id) && !isStoppedAgent(agent)
    )
    if (agents.length > 0) {
      agents.forEach(agent => groupedAgentIds.add(agent.agent_id))
      groups.push({
        key: `group-${group.id}`,
        title: group.name,
        agents,
        isCollapsible: true,
      })
    }
  })

  // Third round: stopped Agents of all nodes (excluding already-grouped ones)
  sortedNodeIds.forEach(nodeId => {
    const nodeAgents = agentsByNode.value[nodeId]
    const stopped = nodeAgents.stopped.filter(agent => !groupedAgentIds.has(agent.agent_id))
    if (stopped.length > 0) {
      groups.push({
        key: `stopped-${nodeId}`,
        title: `${nodeId} stopped Agents`,
        agents: stopped,
        isCollapsible: true,
      })
    }
  })

  return groups
})
const currentAgent = computed(() => {
  return agentList.value.find(agent => agent.agent_id === currentAgentId.value) || null
})

// Note: the collapsed state of stopped Agents is now managed internally by the AgentSidebar component

watch([showWorkspacePanel, currentAgentId, workspaceSidebarView], ([isWorkspacePanelVisible, agentId, sidebarView]) => {
  if (!isWorkspacePanelVisible || !agentId || sidebarView !== 'files') {
    return
  }

  nextTick(() => {
    ensureWorkspaceSidebarFileTree()
  })
})

// Scheduled task sidebar: periodically refresh the scheduled task list when the view is activated (read-only display, tasks may change)
let manageTimersTimer = null
watch([showWorkspaceSidebar, workspaceSidebarView], ([sidebarVisible, sidebarView]) => {
  const active = sidebarVisible && sidebarView === 'timers'
  if (manageTimersTimer) {
    clearInterval(manageTimersTimer)
    manageTimersTimer = null
  }
  if (active) {
    refreshManageTimers()
    manageTimersTimer = setInterval(refreshManageTimers, 5000)
  }
})

// Agent group management
const AGENT_GROUPS_STORAGE_KEY = 'haijunbot_agent_groups'
const agentGroups = ref([]) // Custom groups [{ id, name, agentIds: [] }]

function loadAgentGroups() {
  try {
    const saved = localStorage.getItem(AGENT_GROUPS_STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      if (Array.isArray(parsed)) {
        agentGroups.value = parsed
        return
      }
    }
  } catch (e) {
    console.warn('[AGENT_GROUPS] Failed to load groups:', e)
  }
  agentGroups.value = []
}

function saveAgentGroups() {
  try {
    localStorage.setItem(AGENT_GROUPS_STORAGE_KEY, JSON.stringify(agentGroups.value))
  } catch (e) {
    console.warn('[AGENT_GROUPS] Failed to save groups:', e)
  }
}

function removeStoppedAgentsFromGroups() {
  let changed = false
  agentGroups.value.forEach(group => {
    if (!group.agentIds) group.agentIds = []
    const before = group.agentIds.length
    group.agentIds = group.agentIds.filter(agentId => {
      const agent = agentList.value.find(a => a.agent_id === agentId)
      return !agent || !isStoppedAgent(agent)
    })
    if (group.agentIds.length !== before) changed = true
  })
  if (changed) saveAgentGroups()
}

// Watch agent status/list changes, automatically remove stopped or deleted agents
watch(
  [agentStatuses, agentList],
  () => {
    removeStoppedAgentsFromGroups()
  },
  { deep: true }
)

// Initial load
loadAgentGroups()

// Agent batch selection management
const selectedAgents = ref(new Set()) // Set of selected Agent IDs
const isBatchMode = ref(false)        // Whether in batch selection mode

// Toggle batch selection mode
function toggleBatchMode() {
  isBatchMode.value = !isBatchMode.value
  if (!isBatchMode.value) {
    // Clear selection state when exiting batch mode
    selectedAgents.value.clear()
  }
}


// Editor sidebar Agent list click: show that Agent's session in the editor main area (one at a time)
// The editor session view is single-session: when switching Agents, reuse the same Panel and override agentId,
// instead of creating a new Panel each time (otherwise the old Panel stays in the grid, squeezing the editor to half screen).
function onWorkspaceSidebarAgentClick(agent) {
  if (isBatchMode.value) {
    toggleSelectAgent(agent.agent_id)
    return
  }
  // Mobile does not support multiple Panels; follow existing logic (reuse the currently active Panel)
  if (windowWidth.value <= 768) {
    openAgentInPanel(agent)
    const mobilePanel = panels.value.find(p => p.agentId === agent.agent_id)
    if (mobilePanel) {
      workspaceSessionPanelId.value = mobilePanel.id
      setWorkspaceMainView('session')
    }
    // The mobile sidebar is a bottom drawer overlaying the main area (55% height); it auto-collapses after selection,
    // letting the user immediately see the session content, for a better experience.
    closeWorkspaceSidebar()
    return
  }
  // The Agent is already in a Panel: directly show that Panel (do not create a new one)
  const existingPanel = panels.value.find(p => p.agentId === agent.agent_id)
  if (existingPanel) {
    // Unified into a pane tree: prefer switching the "active pane" to that Panel; if that Panel is already hosted by another pane,
    // then focus that pane (to avoid the same panel appearing in two panes).
    const hostingPane = findWorkspacePaneBySessionPanelId(existingPanel.id)
    if (hostingPane) {
      activateWorkspacePane(hostingPane.id)
    } else {
      // If empty, in place; otherwise split (do not override the current area)
      ensurePaneForView('session', existingPanel.id)
    }
    activePanelId.value = existingPanel.id
    switchAgent(agent)
    workspaceSessionPanelId.value = existingPanel.id
    setWorkspaceMainView('session')
    return
  }
  // Unified into a pane tree: open the Agent into the "active pane" (override if the area already has a Panel),
  // never reuse a Panel hosted by another pane, otherwise the session in that area will be cleared.
  openAgentInActivePane(agent)
}

// ========== Pet gateway operations ==========
// Sync status of all connected Agents
function petSyncAllStatus() {
  let count = 0
  sockets.value.forEach((ws) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'get_status', payload: {} }))
      count++
    }
  })
  if (count > 0) {
    showToast(`Synced status of ${count} Agents`, 'success')
  } else {
    showToast('No connected Agents', 'error')
  }
}

// Interrupt current Agent (manual intervention)
function petInterruptCurrent() {
  const agentId = currentAgentId.value
  if (!agentId) {
    showToast('No Agent selected', 'error')
    return
  }
  sendMessageToAgent({ type: 'manual_interrupt', payload: {} }, agentId)
  showToast('Interrupt signal sent', 'success')
}

// Jump to the Agent waiting for input
function petGotoWaitingAgent() {
  const list = agentList.value || []
  const waiting = list.filter(a => isWaitingInput(a))
  if (waiting.length === 0) {
    showToast('No Agent waiting for input', 'info')
    return
  }
  // Cyclic switch: find the next waiting Agent after the current one, wrap back to the first if none found
  const currentIdx = waiting.findIndex(a => a.agent_id === currentAgentId.value)
  const target = currentIdx >= 0 ? waiting[(currentIdx + 1) % waiting.length] : waiting[0]
  openAgentInPanel(target)
  showToast(`Switched to Agent waiting for input: ${target.name || target.agent_id}`, 'success')
}
// ---- Pipeline orchestration visualization ----
// Select a process (Tab switch)
function selectPipeline(id) {
  activePipelineId.value = id
}
// Delete an orchestration record, and also delete all Agents created when that pipeline ran
async function removePipeline(id) {
  if (!id) return
  const pipeline = pipelineStore.getPipeline(id)
  // Collect all Agents created by that pipeline (pipeline_agents event backfills to stage.agentId)
  const agentIds = []
  if (pipeline && pipeline.stages) {
    for (const [, node] of pipeline.stages) {
      if (node && node.agentId) agentIds.push(node.agentId)
    }
  }
  // When there are Agents to delete, ask the user for confirmation first
  if (agentIds.length) {
    showConfirm(
      `This pipeline created ${agentIds.length} Agents; deleting the pipeline will also delete these Agents. Confirm deletion?`,
      () => removePipelineWithAgents(id, agentIds),
      null,
      false
    )
    return
  }
  // No associated Agents: delete the pipeline record directly
  pipelineStore.removePipeline(id)
  pipelineVersion.value++ // refresh pipelineList
  if (activePipelineId.value === id) activePipelineId.value = ''
}

// After user confirmation: delete the pipeline and the Agents it created
async function removePipelineWithAgents(id, agentIds) {
  // Delete Agents created by the pipeline (pipeline_runner creates them on the master node)
  if (agentIds.length) {
    const { host, port } = getGatewayAddress()
    const targetNodeId = 'master'
    let failed = 0
    for (const agentId of agentIds) {
      try {
        const resp = await fetchWithAuth(
          buildNodeHttpUrl(host, port, targetNodeId, `agents/${agentId}`),
          { method: 'DELETE' }
        )
        const result = await resp.json()
        if (!resp.ok || !result.success) {
          failed++
          console.warn('[PIPELINE] Failed to delete pipeline Agent', agentId, result.error?.message || '')
        }
      } catch (e) {
        failed++
        console.warn('[PIPELINE] Failed to delete pipeline Agent', agentId, e.message)
      }
    }
    if (failed) {
      showToast(`Pipeline record deleted, but ${failed}/${agentIds.length} Agents failed to delete`, 'warning')
    } else {
      showToast(`Deleted pipeline record and its ${agentIds.length} Agents`, 'success')
    }
  } else {
    showToast('Pipeline record deleted', 'success')
  }
  pipelineStore.removePipeline(id)
  pipelineVersion.value++ // refresh pipelineList
  if (activePipelineId.value === id) activePipelineId.value = ''
}
// Click DAG node: if it has agent_id, jump to the corresponding Agent panel, otherwise just select the process
function onOrchestrationJumpAgent(payload) {
  const agentId = payload && payload.agentId
  if (!agentId) return
  const target = agents.value.find(a => a.agent_id === agentId)
  if (target) {
    openAgentInPanel(target)
  } else {
    showToast('The Agent corresponding to this stage no longer exists', 'info')
  }
}
// Open/close the orchestration overview overlay
function openOrchestrationOverlay() {
  showOrchestrationOverlay.value = true
}
function closeOrchestrationOverlay() {
  showOrchestrationOverlay.value = false
}
// On receiving backend pipeline_event: merge into store and trigger view refresh
function onPipelineEvent(payload) {
  if (!payload) return
  pipelineStore.applyEvent(payload)
  pipelineStore.pruneFinished(20)
  pipelineVersion.value++
  if (!activePipelineId.value && payload.pipeline_id) {
    activePipelineId.value = payload.pipeline_id
  }
}

// Public usage docs site (MkDocs published to GitHub Pages)
const DOCS_URL = 'https://takebox.github.io/HaijunBot/'
// Open usage docs (new tab, does not block the current UI)
function openDocs() {
  window.open(DOCS_URL, '_blank', 'noopener')
}

// When opening the command palette, record the panel area that had focus "before opening"
// (the command palette steals focus, making it impossible to infer the target from the active element when performing close/detach)
let commandPaletteFocusKey = null
// Open command palette (triggered by double-clicking the pet); can pass pre-entered content (e.g. 'a>' to go directly to the Agent list)
function openCommandPalette(initialQuery = '') {
  if (showConnectModal.value) return
  commandPaletteFocusKey = getFocusedZoneKey()
  commandPaletteInitialQuery.value = initialQuery
  showCommandPalette.value = true
}

// Open command palette with pre-entered a>, showing the Agent list directly
function openAgentListPalette() {
  openCommandPalette('a>')
}

// Open command palette with pre-entered f>, showing file search directly
function openCommandPaletteFileSearch() {
  openCommandPalette('f>')
}

// Toggle pet show/hide (triggered by command palette, delegates to PetWidget internal logic)
function togglePetVisibility() {
  petWidgetRef.value?.togglePet?.()
}

// ===== Current Agent menu actions (command palette "Current Agent" group) =====
// Get the currently active Panel, fall back to the Panel hosting the current Agent
function getCurrentPanel() {
  const activePanel = panels.value.find(p => p.id === activePanelId.value)
  if (activePanel && activePanel.agentId) return activePanel
  return panels.value.find(p => p.agentId === currentAgentId.value)
    || panels.value.find(p => p.agentId)
    || activePanel
    || null
}
// Agent ID used by the command palette "Current Agent" group:
// Prefer the Agent locked by the context menu; then the Agent in the currently active Panel; then the Agent corresponding to the pet selected in the pet lobby; finally fall back to currentAgentId
// The resolution logic is extracted to utils/currentAgentResolver.js (a pure function, unit-testable); here we only collect snapshots of each state.
const commandPaletteCurrentAgentId = computed(() => resolveCurrentAgentId({
  // While the context menu (sidebar / Panel) is locked, menu actions always apply to the right-clicked Agent (without changing the panel or current Agent).
  // Note: only look at contextMenuAgentId, do not combine it with panelContextMenu.visible——
  // When a menu item is clicked the menu collapses first (visible=false); if we depended on visible it would fall back to the "current active Agent",
  // causing operations like delete/rename to apply to the wrong Agent.
  contextMenuAgentId: contextMenuAgentId.value,
  lobbyActiveAgentId: lobbyActiveAgentId.value,
  hasNoPanel: hasNoPanel.value,
  activePanelAgentId: getCurrentPanel()?.agentId || null,
  currentAgentId: currentAgentId.value,
}))
// Current Agent object (null when nothing is selected)
function getCurrentAgentOrNull() {
  const agentId = commandPaletteCurrentAgentId.value
  if (agentId) {
    const agent = agentList.value.find(a => a.agent_id === agentId)
    if (agent) return agent
  }
  return currentAgent.value || null
}
// Toggle auto-scroll of the current Agent panel
function toggleCurrentAutoScroll() {
  const panel = getCurrentPanel()
  if (!panel || !panel.agentId) {
    showToast('No operable Agent panel', 'error')
    return
  }
  const next = !getPanelAutoScroll(panel)
  togglePanelAutoScroll(panel, next)
  showToast(next ? 'Auto-scroll enabled' : 'Auto-scroll disabled', 'success')
}
// Toggle auto read-aloud of the current Agent panel
function toggleCurrentAutoRead() {
  const panel = getCurrentPanel()
  if (!panel || !panel.agentId) {
    showToast('No operable Agent panel', 'error')
    return
  }
  const next = !getPanelAutoRead(panel)
  if (next && !autoReadSupported) {
    showToast('The current browser does not support auto read-aloud', 'error')
    return
  }
  togglePanelAutoRead(panel, next)
  showToast(next ? 'Auto read-aloud enabled' : 'Auto read-aloud disabled', 'success')
}
// Exit the current Agent's non-interactive mode
function exitCurrentNonInteractive() {
  const agent = getCurrentAgentOrNull()
  if (agent) exitNonInteractiveMode(agent)
}
// Send a manual intervention signal to the current Agent
function interruptCurrentAgent() {
  const panel = getCurrentPanel()
  if (panel && panel.agentId) {
    sendManualInterruptToPanel(panel)
  } else {
    petInterruptCurrent()
  }
}

// Determine whether a focus area key is currently valid (the panel still exists/is visible)
function isFocusKeyAvailable(key) {
  if (!key) return false
  if (key === 'terminal') return !!(showTerminalPanel.value && document.querySelector('.terminal-panel'))
  if (key === 'workspace') return !!(showWorkspacePanel.value && document.querySelector('.workspace-panel'))
  if (key === 'chat') return !!(showChatPanel.value && document.querySelector('.chat-panel'))
  if (key.startsWith('session:')) {
    const panelId = key.slice('session:'.length)
    return panels.value.some(p => p.id === panelId && p.agentId)
  }
  return false
}

// Focus key of named panels (terminal/workspace/chat):
// Prefer based on the real DOM focus; when focus is not on any focusable element (e.g. the user only clicked blank space in a panel,
// and activeElement is body), fall back to the named panel of the most recent interaction (activeWindow, updated by the panel's
// mousedown), and use isFocusKeyAvailable to filter out stale values from closed panels.
function getNamedPanelFocusKey() {
  const focusedKey = getFocusedZoneKey()
  if (focusedKey === 'terminal' || focusedKey === 'workspace' || focusedKey === 'chat') {
    return focusedKey
  }
  if (activeWindow.value && isFocusKeyAvailable(activeWindow.value)) {
    return activeWindow.value
  }
  return null
}

// Key of the panel the current focus is in (session:<id> / terminal / workspace / chat)
// When the command palette is open it steals focus; in that case prefer the snapshot recorded "before opening" (and that panel must still be valid);
// otherwise use the real DOM focus, and finally fall back to the currently active Panel
function getFocusedPanelKey() {
  if (showCommandPalette.value && isFocusKeyAvailable(commandPaletteFocusKey)) {
    return commandPaletteFocusKey
  }
  const focusedKey = getFocusedZoneKey()
  if (focusedKey) return focusedKey
  const namedKey = getNamedPanelFocusKey()
  if (namedKey) return namedKey
  if (isFocusKeyAvailable(commandPaletteFocusKey)) return commandPaletteFocusKey
  const panel = getCurrentPanel()
  if (panel && panel.agentId) return `session:${panel.id}`
  return null
}
// Ctrl+W semantics of the editor panel (same as VS Code): close the file of the "currently active pane";
// when there is no file to close, in the split state close that pane; in the unsplit state return false (the caller closes the entire panel).
// Returns whether it was handled (closed a file or pane).
function handleWorkspaceCloseShortcut() {
  if (!showWorkspacePanel.value) return false
  // Unified into a pane tree: activePane is the currently active area (the only leaf when unsplit).
  const pane = activePane.value
  // file pane has a file → close that file (only affects the active pane, not other panes)
  if (pane && pane.view === 'file') {
    const path = workspaceViewPanes.get(activePaneId.value)
    if (path) {
      closeWorkspaceTab(path, activePaneId.value)
      return true
    }
  }
  // No file to close: close that pane (closing is not allowed when only one pane remains; fall back to closing the entire panel)
  if (workspacePaneCount.value > 1) {
    closeWorkspacePane(activePaneId.value)
    return true
  }
  return false
}

// Close the panel the current focus is in (session/terminal/editor/chat)
function closeFocusedPanel() {
  const key = getFocusedPanelKey()
  if (!key) return
  if (key === 'terminal') {
    showTerminalPanel.value = false
  } else if (key === 'workspace') {
    // Editor panel: Ctrl+W closes the current file first (VS Code semantics); when there is no file, close the entire panel
    if (handleWorkspaceCloseShortcut()) return
    // Consistent with closeWorkspacePanel: closing only hides; state is preserved so it can be restored when reopened
    hideWorkspaceHostedPanelState()
    showWorkspacePanel.value = false
  } else if (key === 'chat') {
    showChatPanel.value = false
  } else if (key.startsWith('session:')) {
    closePanel(key.slice('session:'.length))
  }
}
// ===== Onboarding tour (extracted from the composable useTour) =====
const {
  activeTourId,
  activeTourSteps,
  showOnboarding,
  maybeStartTour,
  finishTour,
  startOnboarding,
  resetOnboardingMarks,
  clearOnboardingTimer,
} = useTour({
  showToast: () => showToast,
  openWorkspaceAgentList: () => openWorkspaceAgentList,
})
// Command palette context: uniformly exposes the action callbacks shared by the pet menu and the command palette
const commandPaletteCtx = computed(() => ({
  currentAgentId: commandPaletteCurrentAgentId.value,
  agentList: agentList.value,
  waitingAgents: (agentList.value || []).filter(a => isWaitingInput(a)),
  currentAgent: getCurrentAgentOrNull(),
  petInterruptCurrent,
  petGotoWaitingAgent,
  syncAllStatus: petSyncAllStatus,
  openCreateAgentModal,
  openQuickCreateAgent,
  refreshAgentList: fetchAgentList,
  restartGateway,
  restartAllNodes,
  confirmRestartAllNodes,
  // Admin-type actions (require admin permission, determined via hasPermission in the registry)
  hasPermission,
  confirmUpdateCodeToMain,
  openAdminPanel: () => { showAdminPanel.value = true; pushOverlayState() },
  openAdminRestartService: () => openAdminSystemAction('restart'),
  openAdminSyncConfig: () => openAdminSystemAction('sync-config'),
  openAdminNodeSecret: () => openAdminSystemAction('node-secret'),
  openAdminConfigFile: () => openAdminSystemAction('config-file'),
  openWorkspaceAgentList,
  // Open the workspace and switch to the Git sidebar view (side activity bar "Git" button / Ctrl+Alt+Shift+V)
  openWorkspaceGit: () => {
    if (!showWorkspacePanel.value) {
      showWorkspacePanel.value = true
      if (windowWidth.value <= 768) pushOverlayState()
    }
    setWorkspaceSidebarView('git')
  },
  // Open the workspace and switch to the "Plugin Management" sidebar view (side activity bar "Plugins" button / Space m p)
  openWorkspacePlugins: () => {
    if (!showWorkspacePanel.value) {
      showWorkspacePanel.value = true
      if (windowWidth.value <= 768) pushOverlayState()
    }
    setWorkspaceSidebarView('plugins')
  },
  toggleTerminalPanel,
  toggleChatPanel,
  // Open the editor sidebar's "Manage Groups" dialog (rename / delete)
  manageGroups: () => { workspacePanelRef.value?.openManageGroups?.() },
  openTopology: openTopologyOverlay,
  openSettings: () => { showSettingsModal.value = true },
  openDocs: openDocs,
  togglePetVisibility,
  openAgentList: openAgentListPalette,
  openCommandPaletteFileSearch: openCommandPaletteFileSearch,
  // Reopen the onboarding tour (shown once automatically after first login, can be reviewed anytime)
  startOnboarding: (tourId) => startOnboarding(tourId || 'welcome'),
  // Reset onboarding tour flags: will be re-triggered the next time the corresponding scenario is entered
  resetOnboarding: () => {
    resetOnboardingMarks()
    activeTourId.value = null
    showToast('Onboarding tour reset; it will prompt again when you enter the corresponding screen', 'success')
  },
  // Open the pet lobby's "Install Browser Extension" overlay
  openInstallExtension: () => { petLobbyRef.value?.openInstallExtensionDialog?.() },
  // Open the pet lobby's "Install Local Background Service (daemon)" overlay
  openDaemonInstall: () => { petLobbyRef.value?.openDaemonDialog?.() },
  // Log out: disconnect all connections and clear authentication info (reuses the settings panel's disconnect logic)
  logout: disconnectAll,
  // Current Agent group
  viewCurrentDiff: () => { const a = getCurrentAgentOrNull(); if (a) viewDiff(a) },
  viewCurrentRules: () => { const a = getCurrentAgentOrNull(); if (a) viewRules(a) },
  viewCurrentTools: () => { const a = getCurrentAgentOrNull(); if (a) viewTools(a) },
  createTerminalForCurrent: () => { const a = getCurrentAgentOrNull(); if (a) createTerminalForAgent(a) },
  openWorkspaceForCurrent: () => { const a = getCurrentAgentOrNull(); if (a) createWorkspaceForAgent(a) },
  // Global: open/hide the editor panel (same behavior as the Ctrl+E branch, does not depend on the current Agent)
  toggleWorkspacePanel,
  // Global: quick access to the editor sidebar's "Content Search" (same behavior as the Ctrl+Shift+F branch; does not respond when the editor is not open)
  openWorkspaceGlobalSearch: () => openWorkspaceGlobalSearch('content'),
  // Global: quick access to the editor sidebar's "File Name Search" (same behavior as the Ctrl+Shift+P branch; does not respond when the editor is not open)
  openWorkspaceFileSearch: () => openWorkspaceGlobalSearch('filename'),
  // Global: quick access to the editor sidebar's directory tree (same behavior as the Ctrl+Shift+E branch; does not respond when the editor is not open)
  openWorkspaceFileTree: () => {
    if (!showWorkspacePanel.value) return
    setWorkspaceSidebarView('files')
    focusFileTreeContainer()
  },
  toggleCurrentAutoScroll,
  toggleCurrentAutoRead,
  exitCurrentNonInteractive,
  interruptCurrentAgent,
  // Current Agent sidebar operations (rename/copy/permission management/lossless reborn/delete)
  renameCurrentAgent: () => { const a = getCurrentAgentOrNull(); if (a) renameAgent(a) },
  copyCurrentAgent: () => { const a = getCurrentAgentOrNull(); if (a) copyAgent(a) },
  editCurrentAgentAccess: () => { const a = getCurrentAgentOrNull(); if (a) editAgentAccess(a) },
  regenerateCurrentAgent: () => { const a = getCurrentAgentOrNull(); if (a) regenerateAgent(a) },
  deleteCurrentAgent: () => { const a = getCurrentAgentOrNull(); if (a) deleteAgent(a.agent_id) },
  // Editor selection → current Agent (command palette action editor-send-selection-to-agent)
  getEditorSelection,
  sendSelectionToAgent,
  // Hide/show the current Agent's output bubble in the lobby (persisted inside PetLobby)
  toggleCurrentAgentOutput: () => {
    const a = getCurrentAgentOrNull()
    const lobby = petLobbyRef.value
    if (a && lobby && typeof lobby.toggleAgentOutput === 'function') {
      lobby.toggleAgentOutput(a.agent_id)
    }
  },
  isCurrentAgentOutputHidden: () => {
    const a = getCurrentAgentOrNull()
    const lobby = petLobbyRef.value
    return !!(a && lobby && typeof lobby.isOutputHidden === 'function' && lobby.isOutputHidden(a.agent_id))
  },
  // Current focus panel: close (the panel header icon remains unchanged)
  closeFocusedPanel,
  // Command palette "f> Search Files": perform a backend fuzzy search by file name in the current Agent workspace; results contain only files
  fileSearchResults: commandPaletteFileResults.value,
  fileSearchLoading: commandPaletteFileSearching.value,
  fileSearchError: commandPaletteFileError.value,
  searchWorkspaceFiles,
  clearWorkspaceFileSearch,
  openFileResult: openCommandPaletteFileResult,
  // Global: open the command palette (same behavior as the Ctrl+P branch)
  openCommandPalette: () => { showCommandPalette.value = true },
  // Global: save the editor's current tab (same behavior as the Ctrl+S branch)
  saveActiveWorkspaceTab: () => saveActiveWorkspaceTab(),
  // Global: split the editor workspace left/right or top/bottom (same behavior as the Ctrl+\ / Ctrl+Shift+\ branches)
  splitWorkspacePane: (paneId, direction) => splitWorkspacePane(paneId, direction),
  activePaneId: activePaneId.value,
  // Global: send buffered input (same behavior as the Ctrl+Alt+Enter branch)
  sendBufferedInput: () => sendBufferedInput(),
  // Lobby: delete the selected Agent (same behavior as the Delete branch)
  lobbyActiveAgentId: lobbyActiveAgentId.value,
  deleteLobbyAgent: (agentId) => {
    const agent = agentList.value.find(a => a.agent_id === agentId)
    if (agent) deleteAgent(agent.agent_id)
  },
  // In the sidebar, "Permission Management" and "Lossless Reborn" are only visible to the Agent owner; keep consistent here
  isCurrentAgentOwner: (() => {
    const a = getCurrentAgentOrNull()
    return !!a && a.owner_id === (auth.value.userInfo?.user_id || '')
  })(),
  // Required for the command palette "Switch Agent" (a> / A> prefix)
  // Enter (without openMode / 'current'): open in the current Panel; Tab ('new'): open in a new Panel
  switchToAgent: (agent, openMode) => {
    if (!agent) return
    if (openMode === 'new') {
      openAgentInNewPanel(agent)
    } else {
      openAgentInCurrentPanel(agent)
    }
  },
  getAgentNodeLabel,
  getStatusClass,
  isWaitingInput,
  // Currently "visible" Agent sessions (used to rank the active Agent at the top of the list and determine whether to gray it out)
  openedAgentIds: visibleSessionAgentIds.value,
  // Node group: applies to the node selected in the lobby (lobbyActiveNodeId)
  currentNodeId: lobbyActiveNodeId.value,
  createAgentOnNode: (nodeId) => onLobbyCreateAgentOnNode(nodeId),
  openTerminalOnNode: (nodeId) => createTerminalForNode(nodeId),
  updateNodeCode: (nodeId) => confirmUpdateNodeCode(nodeId),
  restartNodeService: (nodeId) => confirmRestartNodeService(nodeId),
  renameNode: (nodeId) => { petLobbyRef.value?.renameActiveNode?.(nodeId) },
  // Lobby directional selection (Ctrl+Alt+Arrow keys): only available when the lobby has Agents
  hasLobbyAgents: (agentList.value || []).some(a => a && a.status !== 'stopped'),
  selectLobbyAgentInDirection: (dir) => { petLobbyRef.value?.selectAgentInDirection?.(dir) },
  // Lobby node directional selection (Ctrl+Shift+Arrow keys): only available when the lobby has nodes
  hasLobbyNodes: (availableNodeOptions.value || []).length > 0,
  selectLobbyNodeInDirection: (dir) => { petLobbyRef.value?.selectNodeInDirection?.(dir) },
  // Lobby toggle all output visibility (Ctrl+Alt+A): only available when the lobby has Agents
  hasLobbyAgentsForOutput: (agentList.value || []).some(a => a && a.status !== 'stopped'),
  toggleAllLobbyOutputs: () => { petLobbyRef.value?.toggleAllOutputs?.() },
}))

// Command palette action list (from the unified registry; some actions dynamically adjust text/icons by current state)
const appActions = computed(() => {
  const ctx = commandPaletteCtx.value
  return actionDefs.map(a => {
    const label = resolveActionLabel(a, ctx)
    const icon = resolveActionIcon(a, ctx)
    if (label === a.label && icon === a.icon) return a
    return { ...a, label, icon }
  })
})

// Dynamic menu text/icon: by default take the registry's static values; some actions adjust by current state
function resolveActionLabel(action, ctx) {
  if (action.id === 'current-toggle-output') {
    return ctx.isCurrentAgentOutputHidden && ctx.isCurrentAgentOutputHidden() ? 'Show Output' : 'Hide Output'
  }
  return action.label
}
function resolveActionIcon(action, ctx) {
  if (action.id === 'current-toggle-output') {
    return ctx.isCurrentAgentOutputHidden && ctx.isCurrentAgentOutputHidden() ? UI_ICONS.eye : UI_ICONS.eyeOff
  }
  return action.icon
}
// In the lobby, right-clicking an Agent pet switches the "current Agent" to that pet; the menu actions refresh accordingly
function onLobbyContextAgent(agentId) {
  if (agentId) lobbyActiveAgentId.value = agentId
}
// Lobby pet context-menu actions: reuse the command palette's "Current Agent" group
const lobbyContextActions = computed(() => {
  const ctx = commandPaletteCtx.value
  return actionDefs
    .filter(a => a.group === 'Current Agent')
    .map(a => ({
      id: a.id,
      label: resolveActionLabel(a, ctx),
      icon: resolveActionIcon(a, ctx),
      enabled: typeof a.enabled === 'function' ? a.enabled(ctx) : true,
    }))
})

// Lobby pet context menu click: execute using the same logic as the command palette
function onLobbyContextRun(action) {
  if (!action) return
  const def = actionDefs.find(a => a.id === action.id)
  if (def) onCommandRun(def)
}

// ===== Panel context menu (same actions as pet right-click) =====
// Menu coordinates use viewport coordinates (position: fixed); name is used as the title
const panelContextMenu = ref({ visible: false, x: 0, y: 0, name: '' })
// Agent locked by the context menu: while the menu is open, the "Current Agent" group actions apply to it rather than the currently active panel
const contextMenuAgentId = ref(null)

function closePanelContextMenu() {
  if (panelContextMenu.value.visible) panelContextMenu.value.visible = false
  contextMenuAgentId.value = null
}

// Right-click inside a Panel (with no text selected): first activate that Panel so "Current Agent" points to it, then pop up the menu in place
function onPanelContextMenu(panel, event) {
  if (!panel || !panel.agentId) return
  activatePanel(panel.id)
  contextMenuAgentId.value = panel.agentId
  const agent = agentList.value.find(a => a.agent_id === panel.agentId)
  const MENU_W = 320
  const rows = Math.max(1, Math.ceil(lobbyContextActions.value.length / 2))
  const MENU_H = Math.min(44 + rows * 33, window.innerHeight * 0.6)
  let x = event.clientX
  let y = event.clientY
  if (x + MENU_W > window.innerWidth) x = Math.max(window.innerWidth - MENU_W, 0)
  if (y + MENU_H > window.innerHeight) y = Math.max(window.innerHeight - MENU_H, 0)
  panelContextMenu.value = {
    visible: true,
    x,
    y,
    name: (agent && (agent.name || agent.agent_id)) || panel.agentId,
  }
}

// Click a menu item: first collapse the menu (to avoid the confirmation box being covered by the menu), then reuse the pet right-click execution chain.
// Key point: menu actions locate the "right-clicked Agent" via commandPaletteCurrentAgentId, and that computed
// depends on contextMenuAgentId; closePanelContextMenu() clears it, so here we snapshot first,
// Restore after the menu collapses, then reset once the action completes—ensures delete/rename etc. always apply to the right-clicked Agent.
function onPanelContextAction(action) {
  if (!action || action.enabled === false) return
  const targetAgentId = contextMenuAgentId.value
  closePanelContextMenu()
  contextMenuAgentId.value = targetAgentId
  try {
    onLobbyContextRun(action)
  } finally {
    contextMenuAgentId.value = null
  }
}

// Right-click on a sidebar Agent item: lock that Agent as the menu target and pop up the action menu in place (without changing the current panel layout)
function onSidebarAgentContextMenu(agent, event) {
  if (!agent || !event) return
  contextMenuAgentId.value = agent.agent_id
  const MENU_W = 320
  const rows = Math.max(1, Math.ceil(lobbyContextActions.value.length / 2))
  const MENU_H = Math.min(44 + rows * 33, window.innerHeight * 0.6)
  let x = event.clientX
  let y = event.clientY
  if (x + MENU_W > window.innerWidth) x = Math.max(window.innerWidth - MENU_W, 0)
  if (y + MENU_H > window.innerHeight) y = Math.max(window.innerHeight - MENU_H, 0)
  panelContextMenu.value = {
    visible: true,
    x,
    y,
    name: agent.name || agent.agent_id,
  }
}

// Lobby node right-click menu click: create Agent / open terminal / update code / restart service (more node operations can be extended here later)
function onLobbyNodeContextRun({ action, nodeId }) {
  if (!action) return
  if (action.id === 'node-create-agent') {
    onLobbyCreateAgentOnNode(nodeId)
  } else if (action.id === 'node-open-terminal') {
    createTerminalForNode(nodeId)
  } else if (action.id === 'node-update-code') {
    confirmUpdateNodeCode(nodeId)
  } else if (action.id === 'node-restart-service') {
    confirmRestartNodeService(nodeId)
  }
}

// Lobby node right-click "Update Code": after a second confirmation, call the single-node code update API
function confirmUpdateNodeCode(nodeId) {
  const normalizedNodeId = String(nodeId || '').trim()
  if (!normalizedNodeId) return
  showConfirm(
    `Are you sure you want to update the code for node "${normalizedNodeId}"?\n\nThis operation will:\n1. Switch the node to the main branch\n2. Pull the latest code\n3. Possibly require restarting the node service`,
    () => {
      updateNodeCode(normalizedNodeId)
    },
    () => {},
    false
  )
}

async function updateNodeCode(nodeId) {
  try {
    const { host, port } = getGatewayAddress()
    const response = await fetchWithAuth(
      `${getHttpProtocol()}://${host}:${port}/api/nodes/${encodeURIComponent(nodeId)}/code-update`,
      { method: 'POST' }
    )
    const result = await response.json().catch(() => ({}))
    if (response.ok && result.success) {
      showToast(result.data?.message || `Update request sent to node "${nodeId}"`, 'success')
    } else {
      showToast(`Node "${nodeId}" update failed: ${result.error?.message || `HTTP ${response.status}`}`, 'error')
    }
  } catch (error) {
    console.error(`[LOBBY] Failed to update code for node ${nodeId}:`, error)
    showToast(`Node "${nodeId}" update failed: ${error.message || 'Unknown error'}`, 'error')
  }
}

// Lobby node right-click "Restart Service": after a second confirmation, call the single-node service restart API
function confirmRestartNodeService(nodeId) {
  const normalizedNodeId = String(nodeId || '').trim()
  if (!normalizedNodeId) return
  showConfirm(
    `Confirm restarting the service for node "${normalizedNodeId}"? This will briefly interrupt the node's connection.`,
    () => {
      restartNodeService(normalizedNodeId)
    },
    () => {},
    false
  )
}

async function restartNodeService(nodeId) {
  try {
    const { host, port } = getGatewayAddress()
    const response = await fetchWithAuth(buildNodeHttpUrl(host, port, nodeId, 'service/restart'), {
      method: 'POST',
      body: JSON.stringify({
        node_id: nodeId,
        restart_frontend: restartFrontendService.value
      })
    })
    const data = await response.json().catch(() => ({}))
    if (response.ok) {
      if (data.success === false) {
        showToast(data.error?.message || `Node "${nodeId}" restart failed`, 'error')
      } else {
        showToast(data.data?.message || `Restart request sent to node "${nodeId}"`, 'success')
      }
    } else {
      showToast(`Node "${nodeId}" restart failed: HTTP ${response.status}`, 'error')
    }
  } catch (error) {
    console.error(`[LOBBY] Failed to restart node ${nodeId}:`, error)
    showToast(`Node "${nodeId}" restart failed: ${error.message || 'Unknown error'}`, 'error')
  }
}

// Lobby node rename: write into the node name mapping (same data as the settings UI; leaving it empty restores the node ID)
function onLobbyRenameNode({ nodeId, name }) {
  const normalizedNodeId = String(nodeId || '').trim()
  if (!normalizedNodeId) return
  const next = { ...nodeDisplayNames.value }
  const trimmed = String(name || '').trim()
  if (trimmed) next[normalizedNodeId] = trimmed
  else delete next[normalizedNodeId]
  saveNodeDisplayNames(next)
}

// Execute the action in the command palette
function onCommandRun(action, openMode) {
  // For actions requiring a popup input (such as node rename), close the panel first to release focus, avoiding the popup being obscured by the panel or having its focus stolen
  if (!action?.closePaletteOnRun) showCommandPalette.value = false
  if (!action || typeof action.run !== 'function') return
  try {
    action.run(commandPaletteCtx.value, openMode)
  } catch (err) {
    console.error('Command execution failed', err)
    showToast('Command execution failed', 'error')
  }
}

// Toggle the selected state of a single Agent
function toggleSelectAgent(agentId) {
  if (selectedAgents.value.has(agentId)) {
    selectedAgents.value.delete(agentId)
  } else {
    selectedAgents.value.add(agentId)
  }
  // Trigger reactive update
  selectedAgents.value = new Set(selectedAgents.value)
}

// Determine whether an Agent is selected
function isAgentSelected(agentId) {
  return selectedAgents.value.has(agentId)
}

// Determine whether all are selected
const isAllSelected = computed(() => {
  return agentList.value.length > 0 && agentList.value.every(agent => selectedAgents.value.has(agent.agent_id))
})

// Toggle select all / deselect all
function toggleSelectAll() {
  if (isAllSelected.value) {
    // Deselect all
    selectedAgents.value.clear()
  } else {
    // Select all
    agentList.value.forEach(agent => {
      selectedAgents.value.add(agent.agent_id)
    })
  }
  // Trigger reactive update
  selectedAgents.value = new Set(selectedAgents.value)
}

function isCurrentAgent(agentId) {
  return agentId === currentAgentId.value
}

// Quiet window just after a modal closes: suppress auto-focus during this period.
// After the modal closes, previously pending async state syncs (such as fetchAgentStatus) may only resolve now,
// and if the input box is focused directly at this point, focus will be stolen from the position the user just finished operating.
let modalAutoFocusSuppressUntil = 0
const MODAL_AUTOFOCUS_SUPPRESS_MS = 600
// useAgents writes the quiet window deadline through this setter (App.vue retains ownership of the variable; the composable only assigns it)
function setModalAutoFocusSuppressUntil(timestamp) {
  modalAutoFocusSuppressUntil = timestamp
}

// Whether any modal/popup overlay is currently open.
// Used to prevent Agent-pushed input_request/confirm/ready from stealing the user's focus:
// When the user is operating inside a modal (such as creating an Agent), focus should not be taken away by the auto-focus logic.
function isAutoFocusSuppressed() {
  return isAnyModalOpen() || Date.now() < modalAutoFocusSuppressUntil
}

function isAnyModalOpen() {
  return Boolean(
    showConnectModal.value ||
    showSettingsModal.value ||
    showDiffModal.value ||
    showRulesModal.value ||
    showCreateAgentModal.value ||
    showQuickCreateAgentModal.value ||
    showRenameAgentModal.value ||
    inputPrompt.value.visible ||
    showSessionDialog.value ||
    showDirDialog.value ||
    showCommandPalette.value ||
    showToolsModal.value ||
    showEditAccessModal.value ||
    showTopologyOverlay.value ||
    showOrchestrateModal.value ||
    confirmDialog.value
  )
}

// Determine whether the input box should be disabled (no active agent or the agent status is not running)
const isInputDisabled = computed(() => {
  if (!currentAgentId.value) {
    return true // no active agent
  }
  if (!currentAgent.value || currentAgent.value.status !== 'running') {
    return true // agent status is not running
  }
  return false
})

// Determine whether the Done and completion buttons should be disabled (enabled only while waiting for multiline input)
const isWaitingMultiDisabled = computed(() => {
  // The @ button is always enabled and no longer disabled based on the input mode
  if (!currentAgentId.value) {
    return true // no active agent
  }
  return false // always enabled
})
const newAgentType = ref('agent') // New Agent type (defaults to general Agent to avoid creating a git repo by mistake)
const newAgentDir = ref('~')       // New Agent working directory (defaults to the user home directory)
const newAgentName = ref('General Agent') // New Agent name (optional, defaults to 'General Agent')
const modelGroups = ref([])        // Model group list
const newAgentModelGroup = ref('default') // New Agent model group (defaults to default)
const newCodeAgentWorktree = ref(false) // Whether the new code Agent enables worktree
const newAgentQuickMode = ref(false) // Whether the new Agent enables quick mode
const newAgentRestoreSession = ref(false) // Whether the new Agent enables session restore
const newAgentNoInteractionMode = ref(false) // Whether the new Agent enables no-interaction mode
const newAgentTaskDescription = ref('') // New Agent task description
const newAgentCreateError = ref('') // Error message when creating an Agent
const newAgentProxyNode = ref('') // New Agent proxy node
const newAgentAccessAclRead = ref([]) // New Agent ACL read user ID array
const newAgentAccessAclInteract = ref([]) // New Agent ACL interact user ID array
const availableUserOptions = ref([]) // User list (for ACL selection)
// ACL user list: exclude owner and admin users (they have full control permissions and do not need ACL authorization)
const filteredUserOptionsForAcl = computed(() => {
  const agent = editingAccessAgent.value
  const ownerId = agent?.owner_id || ''
  // Filter out the owner and all administrators from the user list (administrators have full control permissions and do not need ACL authorization)
  return availableUserOptions.value.filter(user => {
    if (user.user_id === ownerId) return false
    if (user.is_admin) return false
    return true
  })
})

const availableNodeOptions = ref([])
const userAccessibleNodes = ref(null) // null=not loaded, []=no permission, ["*"]=all, ["id1","id2"]=limited nodes
const userPermissions = ref(null) // null=not loaded, {allowed:[pattern],denied:[pattern]}=loaded

// Node display name mapping (frontend local only): nodeId -> custom display name; falls back to the original nodeId when unset
const NODE_DISPLAY_NAMES_STORAGE_KEY = 'haijunbot_node_display_names'
function loadNodeDisplayNames() {
  try {
    const savedValue = localStorage.getItem(NODE_DISPLAY_NAMES_STORAGE_KEY)
    if (!savedValue) return {}
    const parsedValue = JSON.parse(savedValue)
    if (!parsedValue || typeof parsedValue !== 'object' || Array.isArray(parsedValue)) return {}
    return Object.fromEntries(
      Object.entries(parsedValue).filter(([, name]) => typeof name === 'string' && name.trim())
    )
  } catch (error) {
    console.warn('[NODE] Failed to load node display names:', error)
    return {}
  }
}
const nodeDisplayNames = ref(loadNodeDisplayNames())
function saveNodeDisplayNames(nextNames = nodeDisplayNames.value) {
  nodeDisplayNames.value = nextNames
  localStorage.setItem(NODE_DISPLAY_NAMES_STORAGE_KEY, JSON.stringify(nextNames))
}
// Get the node's display name: prefer the custom name, otherwise fall back to the original nodeId
function getNodeDisplayName(nodeId) {
  const normalizedNodeId = String(nodeId || '').trim() || 'master'
  const customName = nodeDisplayNames.value[normalizedNodeId]
  return typeof customName === 'string' && customName.trim() ? customName.trim() : normalizedNodeId
}
// Hide working directory (avoid exposing the directory during screen recording/screenshots)
const HIDE_WORKING_DIR_STORAGE_KEY = 'haijunbot_hide_working_dir'
function loadHideWorkingDir() {
  try {
    return localStorage.getItem(HIDE_WORKING_DIR_STORAGE_KEY) === '1'
  } catch (error) {
    console.warn('[WORKDIR] Failed to load hide working dir setting:', error)
    return false
  }
}
const hideWorkingDir = ref(loadHideWorkingDir())
function saveHideWorkingDirSetting(nextValue = hideWorkingDir.value) {
  hideWorkingDir.value = !!nextValue
  try {
    localStorage.setItem(HIDE_WORKING_DIR_STORAGE_KEY, hideWorkingDir.value ? '1' : '0')
  } catch (error) {
    console.warn('[WORKDIR] Failed to save hide working dir setting:', error)
  }
}
// Auto install/update browser extension: off by default. When enabled, the local daemon will, when the gateway extension version changes,
// automatically download and overwrite the local extension directory (without restarting the browser). The state is stored only in browser localStorage,
// and pushed to the daemon along with the login state (the daemon keeps it in memory only, without persisting to disk).
const AUTO_INSTALL_BROWSER_EXT_STORAGE_KEY = 'haijunbot_auto_install_browser_ext'
function loadAutoInstallBrowserExt() {
  try {
    return localStorage.getItem(AUTO_INSTALL_BROWSER_EXT_STORAGE_KEY) === '1'
  } catch (error) {
    console.warn('[BROWSER_EXT] Failed to load auto install setting:', error)
    return false
  }
}
const autoInstallBrowserExt = ref(loadAutoInstallBrowserExt())
function saveAutoInstallBrowserExtSetting(nextValue = autoInstallBrowserExt.value) {
  autoInstallBrowserExt.value = !!nextValue
  try {
    localStorage.setItem(AUTO_INSTALL_BROWSER_EXT_STORAGE_KEY, autoInstallBrowserExt.value ? '1' : '0')
  } catch (error) {
    console.warn('[BROWSER_EXT] Failed to save auto install setting:', error)
  }
  // After the toggle changes, immediately re-push once to the local daemon (the same approach as the terminal name)
  syncTokenToDaemon(auth.value.token, window.__haijunbotAuthBridge.getGateway())
}
// Working directory display: return a placeholder when hiding is enabled, otherwise return the original directory
const WORKING_DIR_HIDDEN_PLACEHOLDER = '••••••'
function getWorkingDirDisplay(workingDir) {
  if (hideWorkingDir.value) return WORKING_DIR_HIDDEN_PLACEHOLDER
  return workingDir || ''
}
// Terminal name / node (extracted from the composable useTerminalName).
// terminalName must be created before useDaemonSync/useAuthBridge (both read terminalName.value);
// getDaemonUrl / syncTokenToDaemon come from useDaemonSync (defined after it), so they are passed in getter form,
// and are only evaluated when called inside useTerminalName, avoiding TDZ.
const { terminalName, saveTerminalNameSetting, initTerminalNameFromDaemon, selectedTerminalNodeId } = useTerminalName({
  auth,
  getDaemonUrl: () => getDaemonUrl,
  syncTokenToDaemon: (token, gw) => syncTokenToDaemon(token, gw),
})
// Local daemon login state sync (extracted into its own composable)
const {
  daemonPort,
  localDaemonOnline,
  getDaemonUrl,
  saveDaemonPortSetting,
  startLocalDaemonProbe,
  stopLocalDaemonProbe,
  syncTokenToDaemon,
} = useDaemonSync({
  auth,
  terminalName,
  autoInstallBrowserExt,
  getGateway: () => window.__haijunbotAuthBridge?.getGateway?.(),
})
// Browser extension login state bridge (extracted into its own composable)
// gatewayUrl is defined by useGatewayConnection (this call site is before it), so it is passed in getter form,
// and is only evaluated when called inside useAuthBridge, avoiding TDZ.
const { installAuthBridge } = useAuthBridge({
  auth,
  terminalName,
  gatewayUrl: () => gatewayUrl,
  parseGatewayAddress,
  syncTokenToDaemon,
})
installAuthBridge()
const newAgentNodeId = ref('master')

// Create Agent modal: filter node options by nodes the user can access
const filteredNodeOptionsForCreateAgent = computed(() => {
  const accessible = userAccessibleNodes.value
  // null=not loaded (permission system not enabled or not yet fetched), show all nodes
  if (accessible === null) return availableNodeOptions.value
  // ["*"]=permission for all nodes
  if (accessible.includes('*')) return availableNodeOptions.value
  // Limited node list: show only nodes with permission
  return availableNodeOptions.value.filter(node => accessible.includes(node.node_id))
})

// Default node for creating an Agent: prefer master, otherwise the first available node
function getDefaultCreateAgentNodeId() {
  const options = filteredNodeOptionsForCreateAgent.value
  if (options.some(node => node.node_id === 'master')) return 'master'
  return options[0]?.node_id || ''
}

// Generate Agent name: Agent type-creation time (e.g. Code Agent-20261213-140013)
function generateAgentName(agentType) {
  const typeName = agentType === 'agent' ? 'General Agent' : 'Code Agent'
  const now = new Date()
  const date = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`
  const time = `${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}${String(now.getSeconds()).padStart(2, '0')}`
  return `${username.value}-${typeName}-${date}-${time}`
}

// Skip the name setting in watch when copying an Agent
const skipNameWatch = ref(false)

// Watch for Agent type changes and auto-fill the default name
watch(newAgentType, (newType) => {
  if (skipNameWatch.value) return
  if (newType === 'agent') {
    newAgentName.value = generateAgentName('agent')
    newCodeAgentWorktree.value = false
  } else if (newType === 'code_agent') {
    newAgentName.value = generateAgentName('code_agent')
  }
}, { immediate: true, flush: 'sync' })

// Confirmation dialog
const confirmDialog = ref(null) // { message, confirmCallback, cancelCallback, defaultConfirm }


// Show the confirmation dialog (auto-scroll to the bottom)
function showConfirm(message, confirmCallback, cancelCallback, defaultConfirm = true) {
  confirmDialog.value = {
    message,
    defaultConfirm,
    confirmCallback,
    cancelCallback
  }

  // Wait for the DOM update, then scroll to the bottom to ensure the user can see the confirmation dialog
  nextTick(() => {
    if (outputList.value) {
      outputList.value.scrollTop = outputList.value.scrollHeight
    }
  })
}

// Handle the confirmation dialog confirm event
function handleConfirmDialogConfirm() {
  if (confirmDialog.value?.confirmCallback) {
    confirmDialog.value.confirmCallback()
  }
  confirmDialog.value = null
}

// Handle the confirmation dialog cancel event
function handleConfirmDialogCancel() {
  if (confirmDialog.value?.cancelCallback) {
    confirmDialog.value.cancelCallback()
  }
  confirmDialog.value = null
}

// Chat room (state + message send/receive/panel interaction), extracted from App.vue into composables/useChat.js
// Depends on socket/auth/username/windowWidth/activeWindow/showChatPanel/focusWindow/showToast/showConfirm/
// playChatNotificationSound/getGatewayAddress/workspaceHostsChat/setWorkspaceMainView/showWorkspaceHostView/
// clamp/PANEL_DRAG_ACTIVATION_DISTANCE/ACTIVE_Z_INDEX/BASE_Z_INDEX, must be called after they are defined
const {
  chatPanelRect,
  chatPanelCollapsed,
  chatPanelInteraction,
  chatPanelStyle,
  chatRooms,
  chatMessages,
  chatClients,
  chatRoomMembers,
  myClientId,
  activeChatRoomId,
  activePrivateClientId,
  chatUnreadCount,
  chatName,
  myUserId,
  chatSidebarWidth,
  chatUnreadMap,
  chatJoinedRooms,
  startChatSidebarResize,
  startChatPanelMove,
  startChatPanelResize,
  toggleChatPanel,
  toggleChatPanelCollapse,
  sendChatMessageToServer,
  createChatRoom,
  joinChatRoom,
  leaveChatRoom,
  deleteChatRoom,
  renameChatRoom,
  clearChatMessages,
  sendChatMessage,
  selectPrivateClient,
  handleChatMessage,
  getOrCreateClientId,
  restoreChatRoomsFromServer,
} = useChat({
  socket,
  auth,
  username,
  windowWidth,
  activeWindow,
  showChatPanel,
  focusWindow,
  showToast,
  showConfirm,
  playChatNotificationSound,
  getGatewayAddress,
  workspaceHostsChat,
  setWorkspaceMainView,
  showWorkspaceHostView,
  clamp,
  PANEL_DRAG_ACTIVATION_DISTANCE,
  ACTIVE_Z_INDEX,
  BASE_Z_INDEX,
})
// File tree (state + node interaction/keyboard navigation/right-click menu/upload download/file CRUD/copy paste/drag and drop/core loading),
// extracted from App.vue into composables/useFileTree.js
// Depends on agentList/getVirtualWorkspaceAgent/resolveFileTreeAgent/resolveAgentForPath/openWorkspaceFile/
// setWorkspaceSidebarView/removeWorkspaceDir/fetchFileContent/fetchWithAuth/buildNodeHttpUrl/
// getGatewayAddress/showToast/showConfirm/globalSearchFileGlob/ensureWorkspaceSidebarFileTree，
// must be called after they are defined
const {
  // State (kept for App.vue script/template access)
  fileTreeState,
  fileTreeExpanded,
  fileTreeLoading,
  expandedAgents,
  selectedAgentId,
  fileTreeSelectedPath,
  fileTreeSelectedAgentId,
  fileTreeContextMenu,
  fileTreeUploadInput,
  inputPrompt,
  fileTreeDropTargetPath,
  // Node interaction
  getFileTypeIcon,
  handleFileTreeNodeClick,
  selectFileTreeNode,
  focusFileTreeContainer,
  revealTabInFileTree,
  toggleAgentExpanded,
  toggleStoppedNodeCollapse,
  isStoppedNodeCollapsed,
  // Keyboard navigation
  handleFileTreeKeydown,
  // Right-click menu
  copyTextToClipboard,
  openFileTreeContextMenu,
  cancelInputPrompt,
  confirmInputPrompt,
  fileTreeContextActions,
  runFileTreeContextAction,
  // Upload download
  readFileAsDataUrl,
  onFileTreeUploadInputChange,
  // Drag and drop
  handleFileTreeDragStart,
  handleFileTreeDragEnd,
  handleFileTreeDragOver,
  handleFileTreeDragLeave,
  handleFileTreeDrop,
  // Core loading
  initFileTree,
  getVisibleFileTreeNodes,
} = useFileTree({
  agentList,
  getVirtualWorkspaceAgent,
  resolveFileTreeAgent,
  resolveAgentForPath,
  openWorkspaceFile,
  setWorkspaceSidebarView,
  removeWorkspaceDir,
  fetchFileContent,
  fetchWithAuth,
  buildNodeHttpUrl,
  getGatewayAddress,
  showToast,
  showConfirm,
  globalSearchFileGlob,
  ensureWorkspaceSidebarFileTree,
})

// Completion list
const showCompletions = ref(false) // Whether to show the completion list
const completionCursorPos = ref(-1) // Records the cursor position when the completion list was opened
const completionHasAtSymbol = ref(false) // Whether an @ symbol to be replaced already exists in the input box when opening completions
const completionAgentId = ref(null) // Records the Panel agentId when the completion list was opened
const completionSource = ref('panel') // Completion source: 'panel' or 'lobby' (pet lobby)
const petLobbyRef = ref(null) // Pet lobby component reference (used to write completion text back to the lobby input box)
const lobbyActiveAgentId = ref(null) // The agentId corresponding to the currently selected pet in the pet lobby
const lobbyActiveNodeId = ref(null) // The id of the currently selected node in the pet lobby (node operation shortcuts act based on this)
const completions = ref([]) // Completion list data
const completionSearch = ref('') // Completion search keyword
const fileCompletions = ref([]) // File completion search results
const completionUsageStats = ref(loadCompletionUsageStats()) // Local usage statistics for completion items

// Watch for search input changes and trigger a file search
watch(completionSearch, async (newSearch) => {
  selectedIndex.value = -1
  
  // If there is search content, load file completions
  if (newSearch.trim()) {
    try {
      const { host, port } = getGatewayAddress()
      // Prefer the agent recorded when completions were opened (possibly an agent in the pet lobby), otherwise fall back to the current agent
      const searchAgentId = completionAgentId.value || currentAgent.value?.agent_id
      if (!searchAgentId) {
        fileCompletions.value = []
        return
      }
      const searchAgent = agentList.value.find(a => a.agent_id === searchAgentId)
      const targetNodeId = String(searchAgent?.node_id || getCurrentAgentNodeId() || 'master').trim() || 'master'
      const response = await fetchWithAuth(
        buildNodeHttpUrl(host, port, targetNodeId, `completions/${searchAgentId}/search?query=${encodeURIComponent(newSearch)}`)
      )
      
      const result = await response.json()
      
      if (response.ok && result.success && result.data) {
        fileCompletions.value = sortCompletionItems(result.data)
      } else {
        fileCompletions.value = []
      }
    } catch (error) {
      console.error('[FILE COMPLETIONS] Fetch failed:', error)
      fileCompletions.value = []
    }
  } else {
    fileCompletions.value = []
  }
})
const completionSearchInput = ref(null) // Completion search input box reference
const completionsModalRef = ref(null) // CompletionsModal component reference
const dirDialogRef = ref(null) // DirectoryDialog component reference
const selectedIndex = ref(-1) // Index of the currently selected completion item; -1 means none selected

// Streaming message tracking
const streamingMessages = ref(new Map()) // Track current streaming messages by agent_id

// Command palette (Ctrl+P)
const showCommandPalette = ref(false)
// Prefilled input content when the command palette opens (e.g. 'a>' directly shows the Agent list)
const commandPaletteInitialQuery = ref('')
// Command palette f> file search: results / loading / error (driven by input changes in CommandPalette)
const commandPaletteFileResults = ref([])
const commandPaletteFileSearching = ref(false)
const commandPaletteFileError = ref('')
// Search request sequence number: discard stale responses (when typing quickly, later requests may arrive first)
let commandPaletteFileSearchToken = 0

// f> file search: perform a backend fuzzy search by filename over "the current Agent's workspace" (results contain files only)
async function searchWorkspaceFiles(rawQuery) {
  const query = String(rawQuery || '').trim()
  const token = ++commandPaletteFileSearchToken
  if (!query) {
    commandPaletteFileResults.value = []
    commandPaletteFileError.value = ''
    commandPaletteFileSearching.value = false
    return
  }
  const agentId = commandPaletteCurrentAgentId.value
  if (!agentId) {
    commandPaletteFileResults.value = []
    commandPaletteFileError.value = 'No current Agent'
    commandPaletteFileSearching.value = false
    return
  }
  commandPaletteFileSearching.value = true
  commandPaletteFileError.value = ''
  try {
    const data = await fetchFileSearchResults(agentId, { query, max_results: 50 })
    if (token !== commandPaletteFileSearchToken) return
    const results = Array.isArray(data.results) ? data.results : []
    commandPaletteFileResults.value = results
      .filter(item => item && item.file_path)
      .map(item => ({ name: item.name || '', file_path: item.file_path }))
  } catch (error) {
    if (token !== commandPaletteFileSearchToken) return
    commandPaletteFileResults.value = []
    commandPaletteFileError.value = error.message || 'Filename search failed'
  } finally {
    if (token === commandPaletteFileSearchToken) commandPaletteFileSearching.value = false
  }
}

// Clean up search results when leaving f> mode / closing the panel
function clearWorkspaceFileSearch() {
  commandPaletteFileSearchToken += 1
  commandPaletteFileResults.value = []
  commandPaletteFileError.value = ''
  commandPaletteFileSearching.value = false
}

// f> select file: close the panel and open in the editor (the backend returns a path relative to the working directory, which must be converted to an absolute path)
function openCommandPaletteFileResult(item) {
  if (!item || !item.file_path) return
  const agentId = commandPaletteCurrentAgentId.value
  showCommandPalette.value = false
  openWorkspaceFile(resolveAgentRelativePath(item.file_path, agentId), agentId)
}
// ---- Pipeline orchestration visualization ----
// Enable localStorage persistence: historical orchestrations can still be restored after refreshing the page (event broadcast is purely in-memory and not persisted)
const pipelineStore = new PipelineStore(20, 'orchestration')
const pipelineVersion = ref(0) // Incremented after an event arrives to trigger recomputation of computed
const pipelineList = computed(() => {
  void pipelineVersion.value
  return pipelineStore.listPipelines()
})
const activePipelineId = ref('')
const showOrchestrationOverlay = ref(false)

// After the command palette closes, if no other popup takes over focus, return focus to the current Agent's input box
function focusCurrentPanelInput(force = false) {
  const panel = getCurrentPanel()
  if (!panel || !panel.agentId) return
  const sessionPanel = sessionPanelRefs.get(panel.id)
  if (sessionPanel?.focusInput) {
    sessionPanel.focusInput(force)
  }
}

watch(showCommandPalette, (visible, wasVisible) => {
  if (visible || !wasVisible) return
  // Panel closed: clean up f> file search results to avoid leftovers the next time it is opened
  clearWorkspaceFileSearch()
  // Panel close action may have opened other popups at the same time (e.g., command execution opening settings/topology), so do not steal focus here
  if (isAnyModalOpen()) return
  nextTick(() => {
    if (isAnyModalOpen()) return
    focusCurrentPanelInput()
  })
})

// Execution status
const isExecuting = ref(false)


const inputModeLabel = computed(() => (inputMode.value === 'multi' ? 'Multi-line' : 'Single-line'))

// History message loading status
const isLoadingHistory = ref(false)
const historyOffset = ref(0)
const hasMoreHistory = ref(true)

// Save auto-login setting
function saveAutoLoginSetting() {
  localStorage.setItem('haijunbot_auto_login', autoLoginEnabled.value)
  // If auto-login is disabled, clear the saved token
  if (!autoLoginEnabled.value) {
    localStorage.removeItem('haijunbot_auth_token')
  }
}

// System settings (notification toggle/config sync/code update/node restart/admin panel positioning), extracted from a standalone composable
// Depends on showAdminPanel/adminPanelRef/availableNodeOptions/getGatewayAddress/getHttpProtocol/
// fetchWithAuth/buildNodeHttpUrl/showToast/showConfirm；pushOverlayState/isRestartingGateway/
// restartFrontendService is defined after the call site, injected via getter
const {
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
} = useSettings({
  showAdminPanel,
  adminPanelRef,
  pushOverlayState: () => pushOverlayState,
  getGatewayAddress,
  getHttpProtocol,
  fetchWithAuth,
  buildNodeHttpUrl,
  showToast,
  showConfirm,
  availableNodeOptions,
  isRestartingGateway: () => isRestartingGateway,
  restartFrontendService: () => restartFrontendService,
})



// ========== Agent management methods (extracted from App.vue into composables/useAgents.js) ==========
const {
  // In-scope ref (destructured and shared by App.vue)
  dirDialogContext,
  showToolsModal,
  toolsContent,
  toolsLoading,
  showEditAccessModal,
  editingAccessAgent,
  editAccessRead,
  editAccessInteract,
  // Functions
  getStatusText,
  getStatusClass,
  isWaitingInput,
  fetchAgentStatus,
  syncOnlineAgentStatuses,
  getCreateAgentDirectoryNodeId,
  resetDirectorySelectionState,
  openDirDialog,
  fetchDirectories,
  selectDirectory,
  handleDirSearchKeydown,
  enterDirectory,
  goToParentDir,
  confirmDirectory,
  cancelDirDialog,
  openCreateAgentModal,
  onLobbyCreateAgentOnNode,
  fetchModelGroups,
  fetchUserAccessibleNodes,
  fetchUserPermissions,
  matchPermissionPattern,
  hasPermission,
  fetchNodeStatus,
  startNodeStatusRefresh,
  stopNodeStatusRefresh,
  fetchUserList,
  formatNodeOptionLabel,
  getDefaultTerminalNodeId,
  getAgentNodeLabel,
  getAgentNodeDisplayLabel,
  getAgentProxyNodeLabel,
  getCurrentAgentNodeId,
  getWorkspaceTargetNodeId,
  checkCodeAgentDirConflict,
  createAgentWithOptions,
  afterAgentCreated,
  createAgent,
  openQuickCreateAgent,
  openFullCreateAgentFromQuick,
  submitQuickCreateAgent,
  openCompletions,
  closeCompletionsWithoutSelect,
  handleCompletionKeydown,
  scrollToSelected,
  scrollToDirSelected,
  findVisiblePanelTextarea,
  insertAtPosition,
  insertCompletion,
  fetchAgentList,
  buildCopiedAgentPayload,
  copyAgent,
  batchCopyAgents,
  onLobbyAddAgentToGroup,
  onLobbyRemoveAgentFromGroup,
  addSelectedToGroup,
  createGroupWithAgents,
  renameAgentGroup,
  deleteAgentGroup,
  viewRules,
  exitNonInteractiveMode,
  viewTools,
  renameAgent,
  confirmRename,
  editAgentAccess,
  saveAgentAccess,
  deleteAgent,
  regenerateAgent,
  batchDeleteAgents,
  onLobbySelectAgent,
  getLobbyInputState,
  sendLobbyInput,
  getLobbyLatestOutput,
  onLobbyComplete,
  switchAgent,
  startAgentListRefresh,
  stopAgentListRefresh,
} = useAgents({
  agentList,
  currentAgentId,
  agentStatuses,
  isStoppedAgent,
  currentAgent,
  agentGroups,
  selectedAgents,
  isBatchMode,
  inputText,
  inputMode,
  inputRequests,
  inputTip,
  panelInputTexts,
  panelInputModes,
  panelInputTips,
  panelConfirmData,
  pendingInputAgentId,
  pendingConfirmAgentId,
  inputBuffers,
  allOutputs,
  outputs,
  outputList,
  panelOutputLists,
  panels,
  sessionPanelRefs,
  showToast,
  showConfirm,
  showSettingsModal,
  showWorkspacePanel,
  activeWorkspaceSession,
  hasNoPanel,
  isAutoFocusSuppressed,
  isAnyModalOpen,
  socket,
  sockets,
  auth,
  username,
  getHttpProtocol,
  buildNodeHttpUrl,
  getGatewayAddress,
  fetchWithAuth,
  escapeHtml,
  historyStorage,
  loadHistoryMessages,
  sendMessageToAgent,
  setupHistoryScrollListener,
  openAgentInPanel,
  closePanel,
  closeAgentInPanel,
  closeOpenDirDialog,
  confirmOpenDir,
  restoreWorkspacePaneContents,
  saveRecentWorkDir,
  loadRecentWorkDirs,
  filteredDirList,
  sortCompletionItems,
  recordCompletionSelection,
  switchGeneration,
  windowWidth,
  agentListLoaded,
  setModalAutoFocusSuppressUntil,
  MODAL_AUTOFOCUS_SUPPRESS_MS,
  hasMoreHistory,
  historyOffset,
  showCompletions,
  completionCursorPos,
  completionHasAtSymbol,
  completionAgentId,
  completionSource,
  petLobbyRef,
  completions,
  completionSearch,
  fileCompletions,
  completionSearchInput,
  completionsModalRef,
  selectedIndex,
  showCreateAgentModal,
  showQuickCreateAgentModal,
  quickCreateAgentLoading,
  quickCreateAgentError,
  showRenameAgentModal,
  renamingAgent,
  renameAgentName,
  showDirDialog,
  currentDirPath,
  dirList,
  selectedDir,
  dirSearchText,
  dirSearchInput,
  selectedDirIndex,
  dirDialogRef,
  saveAgentGroups,
  renameInput,
  openDirNodeId,
  openDirPath,
  openDirDialogRef,
  newAgentType,
  newAgentDir,
  newAgentName,
  modelGroups,
  newAgentModelGroup,
  newCodeAgentWorktree,
  newAgentQuickMode,
  newAgentRestoreSession,
  newAgentNoInteractionMode,
  newAgentTaskDescription,
  newAgentCreateError,
  newAgentProxyNode,
  newAgentAccessAclRead,
  newAgentAccessAclInteract,
  availableUserOptions,
  availableNodeOptions,
  userAccessibleNodes,
  userPermissions,
  getNodeDisplayName,
  newAgentNodeId,
  filteredNodeOptionsForCreateAgent,
  getDefaultCreateAgentNodeId,
  generateAgentName,
  skipNameWatch,
  rulesLoading,
  showRulesModal,
  rulesContent,
  rulesLoadedContent,
  selectedTerminalNodeId,
  chatName,
  saveToHistory,
  lobbyHistoryIndex,
  lobbyHistoryTemp,
  maybeStartTour,
  fileTreeState,
  fileTreeExpanded,
  fileTreeLoading,
  orchestrateAgents: () => orchestrateAgents,
  orchestrateActiveIndex: () => orchestrateActiveIndex,
  orchestrateNodeId: () => orchestrateNodeId,
  terminals: () => terminals,
  terminalHosts: () => terminalHosts,
  disposeExecutionTerminal: () => disposeExecutionTerminal,
  connectToAgent: () => connectToAgent,
  autoConnectToOnlineAgents: () => autoConnectToOnlineAgents,
  renderMessageHtml: () => renderMessageHtml,
  appendOutput: () => appendOutput,
  sendInputDirectly: () => sendInputDirectly,
  sendBufferedInput: () => sendBufferedInput,
  sendConfirmResult: () => sendConfirmResult,
  restoreWaitingConfirmUI: () => restoreWaitingConfirmUI,
  pushOverlayState: () => pushOverlayState,
})
// Diff floating window (state + fetch/render/file navigation), extracted from App.vue into composables/useDiff.js
// Depends on getGatewayAddress/getCurrentAgentNodeId/fetchWithAuth/buildNodeHttpUrl/windowWidth, must be called after they are defined
const {
  showDiffModal,
  diffFiles,
  diffActiveIndex,
  diffLoading,
  diffError,
  diffMobileShowDetail,
  diffActiveHtml,
  selectDiffFile,
  viewDiff
} = useDiff({
  windowWidth,
  getGatewayAddress,
  getCurrentAgentNodeId,
  fetchWithAuth,
  buildNodeHttpUrl
})
// Session recovery (state + recover/cancel), extracted from App.vue into composables/useSession.js
// Depends on currentAgentId/getGatewayAddress/getCurrentAgentNodeId/fetchWithAuth/buildNodeHttpUrl/loadHistoryMessages, must be called after they are defined
const {
  showSessionDialog,
  availableSessions,
  restoreSession,
  cancelSessionDialog
} = useSession({
  currentAgentId,
  getGatewayAddress,
  getCurrentAgentNodeId,
  fetchWithAuth,
  buildNodeHttpUrl,
  loadHistoryMessages
})
// Orchestration (state + parse/create/file browsing), extracted from App.vue into composables/useOrchestrate.js
const {
  showOrchestrateModal,
  orchestrateNodeId,
  orchestrateFilePath,
  orchestratePluginTemplates,
  orchestratePluginTemplatesLoading,
  orchestrateRecentFiles,
  ORCHESTRATE_RECENT_KEY,
  ORCHESTRATE_RECENT_MAX,
  orchestrateAgents,
  orchestrateHasFlow,
  orchestrateNodes,
  orchestrateActiveIndex,
  orchestrateLoading,
  orchestrateError,
  orchestrateCreating,
  orchestrateResults,
  orchestrateRunWorkingDir,
  orchestrateRunning,
  orchestrateFileEntries,
  orchestrateSelectedFile,
  orchestrateDialogRef,
  orchestrateShowBrowser,
  orchestrateCurrentDirPath,
  orchestrateLocalFileInput,
  orchestrateDirSearchText,
  orchestrateSelectedIndex,
  orchestrateFilteredDirs,
  orchestrateFilteredFiles,
  orchestrateNavItems,
  orchestrateHighlightedDir,
  orchestrateHighlightedFile,
  ORCHESTRATE_FILE_EXTENSIONS,
  buildOrchestrateAgentForm,
  openOrchestrateModal,
  closeOrchestrateModal,
  loadOrchestrateRecentFiles,
  saveOrchestrateRecentFile,
  removeOrchestrateRecentFile,
  selectOrchestrateRecentFile,
  loadOrchestratePluginTemplates,
  selectOrchestratePluginTemplate,
  parseOrchestrationFile,
  addOrchestrateAgent,
  removeOrchestrateAgent,
  createAllOrchestrateAgents,
  openOrchestrateDirDialog,
  runOrchestration,
  previewOrchestration,
  handleApproval,
  isOrchestrateFile,
  filterOrchestrateEntries,
  fetchOrchestrateEntries,
  toggleOrchestrateBrowser,
  orchestrateInitialBrowsePath,
  enterOrchestrateDir,
  goToOrchestrateParentDir,
  onOrchestrateSelectFile,
  onOrchestrateLocalSelect,
  onOrchestrateLocalFileChange,
  handleOrchestrateSearchKeydown,
  syncOrchestrateKeyboardSelection,
  scrollToOrchestrateSelected,
  onOrchestrateNodeChange,
} = useOrchestrate({
  agentList,
  availableNodeOptions,
  buildNodeHttpUrl,
  fetchWithAuth,
  filteredNodeOptionsForCreateAgent,
  getDefaultCreateAgentNodeId,
  getGatewayAddress,
  hasNoPanel,
  openAgentInPanel,
  pipelineStore,
  pipelineVersion,
  setWorkspaceSidebarView,
  showToast,
  showWorkspaceSidebar,
  readFileAsDataUrl,
  createAgentWithOptions,
  fetchAgentList,
  fetchNodeStatus,
  dirDialogContext,
  openDirDialog,
  startAgentListRefresh,
})
// Switch the currently working Agent

// Sync the specified Agent's input mode and tip to the global/panel state
// Used to update the UI when input_request arrives (basis for switching between multi-line textarea and single-line input)
function syncAgentInputMode(targetAgentId, payload) {
  if (!targetAgentId) return
  inputTip.value = payload.tip || ''
  inputMode.value = payload.mode || 'multi'
  if (payload.preset) {
    inputText.value = payload.preset
  }
  // Sync to the Panel isolated state
  panelInputTips.value.set(targetAgentId, payload.tip || '')
  panelInputModes.value.set(targetAgentId, payload.mode || 'multi')
  panelInputPasswords.value.set(targetAgentId, payload.is_password || false)
  if (payload.preset) {
    panelInputTexts.value.set(targetAgentId, payload.preset)
  }
  pendingInputAgentId.value = targetAgentId
}

function handleMessage(message, agentId = null) {
  const { type, payload, seq } = message
  // Debug: log all received message types


  // Determine target Agent ID: use the passed-in agentId first, otherwise use currentAgentId
  const targetAgentId = agentId || currentAgentId.value
  
  // seq is already saved to history along with the message, no separate maintenance needed
  
  if (type === 'ready') {
    // Agent connection established and ready
    // Message sync relies entirely on the sync_request mechanism; no longer manually load history or clear messages

    // Restore the current Agent's input request state (retrieved from the Map)
    const currentAgentIdLocal = targetAgentId
    const inputRequest = inputRequests.value.get(currentAgentIdLocal)
    if (inputRequest) {
      inputTip.value = inputRequest.tip || ''
      inputMode.value = inputRequest.mode || 'multi'
      inputText.value = inputText.value || inputRequest.preset || ''
      // Sync to the Panel isolated state
      panelInputTips.value.set(currentAgentIdLocal, inputRequest.tip || '')
      panelInputModes.value.set(currentAgentIdLocal, inputRequest.mode || 'multi')
      panelInputPasswords.value.set(currentAgentIdLocal, inputRequest.is_password || false)
      if (inputRequest.preset) {
        panelInputTexts.value.set(currentAgentIdLocal, inputRequest.preset)
      }
      pendingInputAgentId.value = currentAgentIdLocal
      // Do not steal focus when a popup is open (avoid taking focus away from what the user is operating on while restoring input state)
      if (!isAnyModalOpen()) {
        nextTick(() => {
          if (isAnyModalOpen()) return
          const inputEl = document.querySelector(inputMode.value === 'multi' ? 'textarea' : 'input[type="text"]')
          inputEl?.focus()
        })
      }
    }
  } else if (type === 'sync_response') {
    // Handle sync response, receiving multiple history messages at once (incremental mode)
    const messages = payload?.messages || []
    // Deduplicate and merge with local history by seq, then save
    if (messages.length > 0) {
      // Get existing local messages and index them by seq
      const localMessages = historyStorage.getHistoryForAgent(targetAgentId)
      const seqMap = new Map()
      for (const msg of localMessages) {
        if (typeof msg.seq === 'number') {
          seqMap.set(msg.seq, msg)
        }
      }
      // Merge remote messages (remote messages override local messages with the same seq)
      // stream message merging: merge STREAM_START/STREAM_CHUNK/STREAM_END into a single message
      const streamAccumulator = new Map() // agent_id -> { streamingMessage, lastSeq }
      for (const rawMsg of messages) {
        // Convert {type, payload, seq} format to flat format {output_type, text, ..., seq}
        let msg = rawMsg.payload
          ? { ...rawMsg.payload, seq: rawMsg.seq, type: rawMsg.type }
          : rawMsg
        // Supplement the display fields of input_result messages to stay consistent with real-time message handling
        if (rawMsg.type === 'input_result' && !msg.output_type) {
          // Filter out Ctrl+C sentinel values, do not echo them to the chat window
          if (msg.text === '__CTRL_C_PRESSED__') {
            continue
          }
          msg.output_type = 'user_input'
          msg.agent_name = 'user'
        }

        // Handle stream messages: merge into one final message
        const outputType = msg.output_type
        if (outputType === 'STREAM_START') {
          const agentId = msg.context?.agent_id || msg.agent_id || targetAgentId
          streamAccumulator.set(agentId, {
            output_type: 'STREAM',
            text: '',
            lang: 'markdown',
            agent_name: msg.context?.agent_name || msg.agent_name || '',
            model_name: msg.context?.model_name || '',
            timestamp: msg.timestamp || null,
            context: msg.context || {},
            seq: msg.seq,
          })
          continue
        } else if (outputType === 'STREAM_CHUNK') {
          const agentId = msg.context?.agent_id || msg.agent_id || targetAgentId
          const acc = streamAccumulator.get(agentId)
          if (acc) {
            acc.text += msg.text || ''
            if (typeof msg.seq === 'number') {
              acc.seq = msg.seq // Use the seq of the last chunk
            }
          }
          continue
        } else if (outputType === 'STREAM_END') {
          const agentId = msg.context?.agent_id || msg.agent_id || targetAgentId
          const acc = streamAccumulator.get(agentId)
          if (acc) {
            if (typeof msg.seq === 'number') {
              acc.seq = msg.seq
            }
            if (typeof acc.seq === 'number') {
              seqMap.set(acc.seq, acc)
            } else {
              seqMap.set(`_no_seq_${Date.now()}_${Math.random()}`, acc)
            }
            streamAccumulator.delete(agentId)
          }
          continue
        }

        if (typeof msg.seq === 'number') {
          seqMap.set(msg.seq, msg)
        } else {
          // Messages without seq are appended directly
          seqMap.set(`_no_seq_${Date.now()}_${Math.random()}`, msg)
        }
      }
      // Handle leftover streaming messages that never received STREAM_END (abnormal case)
      for (const acc of streamAccumulator.values()) {
        if (typeof acc.seq === 'number') {
          seqMap.set(acc.seq, acc)
        } else {
          seqMap.set(`_no_seq_${Date.now()}_${Math.random()}`, acc)
        }
      }
      // Sort by seq, then save
      const mergedMessages = Array.from(seqMap.values()).sort((a, b) => {
        const seqA = typeof a.seq === 'number' ? a.seq : 0
        const seqB = typeof b.seq === 'number' ? b.seq : 0
        return seqA - seqB
      })
      historyStorage.setHistoryForAgent(targetAgentId, mergedMessages)
      // Clear the current message list and force a full reload of history from local storage
      // This ensures the synced history displays correctly and avoids problems caused by merging with existing messages
      if (targetAgentId === currentAgentId.value) {
        allOutputs.value.set(targetAgentId, [])
        historyOffset.value = 0
        hasMoreHistory.value = true
      }
      loadHistoryMessages(false)
    }
  } else if (type === 'input_result') {
    // Input buffer sent by the backend on reconnect; echo the user input to the chat window
    const inputText = payload?.text
    if (inputText && inputText !== '__CTRL_C_PRESSED__') {
      appendOutput({
        output_type: 'user_input',
        agent_name: 'user',
        text: inputText,
        lang: 'text',
        seq: seq, // Pass seq
      }, targetAgentId)
    }
  } else if (type === 'output') {
    const outputType = payload?.output_type
    
    // Handle streaming output
    if (outputType === 'STREAM_START') {
      // Create the current Agent's streaming message
      const currentOutputs = allOutputs.value.get(targetAgentId) || []
      const streamingMessage = {
        output_type: 'STREAM',
        text: '',
        lang: 'markdown',
        agent_name: payload?.context?.agent_name || payload?.agent_name || '',
        model_name: payload?.context?.model_name || '',
        timestamp: payload?.timestamp || null,
        context: payload?.context || {},
        isStreaming: true
      }
      streamingMessages.value.set(targetAgentId, streamingMessage)
      currentOutputs.push(streamingMessage)
    } else if (outputType === 'STREAM_CHUNK') {
      // Append to the current Agent's streaming message
      const streamingMessage = streamingMessages.value.get(targetAgentId)
      if (streamingMessage) {
        streamingMessage.text += payload.text || ''
        // Use renderMessageHtml to ensure streaming and history messages use the same rendering logic
        streamingMessage.html = renderMessageHtml(streamingMessage)
        // Streaming messages trigger scrolling (when auto-scroll is on), scrolling only that Agent's own container;
        // Only when that Agent is the one currently being viewed and has no separate Panel container does it fall back to outputList,
        // to avoid a background Agent's streaming output scrolling the view of another Agent the user is viewing all the way to the bottom.
        nextTick(() => {
          if (!isAutoScrollEnabled(targetAgentId)) return
          const targetPanel = panels.value.find(p => p.agentId === targetAgentId)
          const targetOutputList = targetPanel ? panelOutputLists.get(targetPanel.id) : null
          const scrollEl = targetOutputList || (isCurrentAgent(targetAgentId) ? outputList.value : null)
          if (scrollEl) {
            scrollEl.scrollTop = scrollEl.scrollHeight
          }
        })
      } else {
        console.warn('[STREAM] Received chunk but no streaming message found for agent:', targetAgentId)
      }
    } else if (outputType === 'STREAM_END') {
      const streamingMessage = streamingMessages.value.get(targetAgentId)
      if (streamingMessage) {
        // Remove the streaming message from the current Agent's outputs array
        const currentOutputs = allOutputs.value.get(targetAgentId) || []
        const index = currentOutputs.indexOf(streamingMessage)
        if (index !== -1) {
          currentOutputs.splice(index, 1)
        }
        // Clear the current Agent's streaming message reference
        streamingMessages.value.delete(targetAgentId)
      } else {
        console.warn('[STREAM] Received end but no streaming message found for agent:', targetAgentId)
      }
    } else {
      // Normal output, pass seq
      appendOutput({ ...payload, seq: seq }, targetAgentId)
    }
  } else if (type === 'input_request') {

    const requestAgentId = targetAgentId
    pendingInputAgentId.value = requestAgentId

    // Check whether currently in waiting_confirm state; if so, skip the status update (do not override the confirm state)
    const currentStatus = requestAgentId ? agentStatuses.value.get(requestAgentId)?.execution_status : null
    if (currentStatus === 'waiting_confirm') {
      return
    }

    // Set agentStatuses according to mode
    if (requestAgentId && payload.mode) {
      const statusKey = payload.mode === 'multi' ? 'waiting_multi' : 'waiting_single'
      agentStatuses.value.set(requestAgentId, {execution_status: statusKey})
    }
    
    // Check whether the buffer has content
    if (requestAgentId && inputBuffers.value.has(requestAgentId)) {
      // The completion signal (__CTRL_C_PRESSED__) is sent only to multi-line input
      const bufferedText = inputBuffers.value.get(requestAgentId)
      const isCompletionSignal = bufferedText === '__CTRL_C_PRESSED__'
      const isMultiLineRequest = payload.mode === 'multi'
      
      if (isCompletionSignal && !isMultiLineRequest) {
        // The completion signal cannot be sent to single-line input (such as a confirmation dialog); clear the buffer
        inputBuffers.value.delete(requestAgentId)
      } else {
        // For normal input or matching multi-line input, send the buffer content
        inputBuffers.value.delete(requestAgentId)
        sendInputResult(bufferedText, payload.request_id, requestAgentId, payload.mode)
      }
      // The buffer content has been consumed, but the input mode still needs to be synced (otherwise the multi-line input box will not switch to single-line immediately)
      if (isCurrentAgent(targetAgentId)) {
        syncAgentInputMode(targetAgentId, payload)
      }
      return
    }
    
    // Save the input request to the Map for recovery after reconnect and Agent switching
    const hadPendingRequest = inputRequests.value.has(targetAgentId)
    inputRequests.value.set(targetAgentId, {
      tip: payload.tip || '',
      mode: payload.mode || 'multi',
      preset: payload.preset || '',
      is_password: payload.is_password || false,
      request_id: payload.request_id
    })

    // Prompt sound: use input_request as the accurate trigger signal (it arrives every time input is actually requested)
    // If that Agent already has a pending request (e.g., pushed again during reconnect recovery), skip to avoid playing repeatedly
    if (!hadPendingRequest) {
      notifyInputRequest()
      // Auto read-aloud: use input_request as the accurate trigger signal (it arrives every time input is actually requested)
      handleAutoRead(targetAgentId, payload.mode === 'multi' ? 'waiting_multi' : 'waiting_single')
    }
    
    // If it is the current Agent, update the global UI state and show the input box
    if (isCurrentAgent(targetAgentId)) {
      syncAgentInputMode(targetAgentId, payload)
      // Focus the input box (do not steal focus when a popup or the pet radial menu is open)
      const targetPanel = panels.value.find(p => p.agentId === targetAgentId)
      const sp = targetPanel ? sessionPanelRefs.get(targetPanel.id) : null
      if (sp?.focusInput && !isAnyModalOpen()) sp.focusInput()

    }
    
    // Check whether at the bottom (used to decide whether to scroll after showing the input box)
    const SCROLL_THRESHOLD = 50 // 50px tolerance
    let shouldScrollAfterInputShow = false
    if (outputList.value) {
      const scrollTop = outputList.value.scrollTop
      const scrollHeight = outputList.value.scrollHeight
      const clientHeight = outputList.value.clientHeight
      // If already near the bottom, record that scrolling is needed after the input box is shown
      shouldScrollAfterInputShow = (scrollTop + clientHeight >= scrollHeight - SCROLL_THRESHOLD)
    }
    
    nextTick(() => {
      
      // After the input box is shown, if it was previously at the bottom and the request belongs to the current Agent, scroll to the bottom (and when auto-scroll is on)
      if (isCurrentAgent(requestAgentId) && shouldScrollAfterInputShow && outputList.value && isAutoScrollEnabled(requestAgentId)) {
        requestAnimationFrame(() => {
          const scrollHeight = outputList.value.scrollHeight
          const scrollTop = outputList.value.scrollTop
          const clientHeight = outputList.value.clientHeight
          outputList.value.scrollTop = scrollHeight
        })
      }
    })
  } else if (type === 'confirm') {
    // Confirmation requests are also treated as requiring input; play the prompt sound unconditionally
    notifyInputRequest()

    pendingConfirmAgentId.value = targetAgentId
    // Update the Agent status to waiting_confirm
    agentStatuses.value.set(targetAgentId, {execution_status: 'waiting_confirm'})

    // Update the Panel embedded confirmation data (isolated by agentId)
    panelConfirmData.value.set(targetAgentId, {
      message: payload.message || 'Please confirm',
      defaultConfirm: payload.default !== undefined ? payload.default : true
    })

    // Confirmation requests use single-line input mode to avoid the multi-line input box stealing focus
    inputMode.value = 'single'
    panelInputModes.value.set(targetAgentId, 'single')
    inputTip.value = payload.message || 'Please confirm (y/n/Enter)'
    panelInputTips.value.set(targetAgentId, payload.message || 'Please confirm (y/n/Enter)')
    // Focus the input box (only for the current Agent and when no popup is open, to avoid other Agents' confirmation requests stealing focus)
    const targetPanel = panels.value.find(p => p.agentId === targetAgentId)
    const sp = targetPanel ? sessionPanelRefs.get(targetPanel.id) : null
    if (sp?.focusInput && isCurrentAgent(targetAgentId) && !isAnyModalOpen()) sp.focusInput()
    // When there is no Panel, do not show a global dialog; the confirmation request waits silently, and the confirm control becomes visible after the user opens the Panel
  } else if (type === 'execution') {
    appendExecution(payload, targetAgentId)
    // Only create the output item when the terminal is created for the first time
    const executionId = payload?.execution_id || 'default'
    const executionSessionKey = getExecutionSessionKey(targetAgentId, executionId)
    const currentOutputs = allOutputs.value.get(targetAgentId) || []
    const existingItem = currentOutputs.find(
      item => item.output_type === 'execution' && item.execution_id === executionId
    )
    // Standalone terminals (execution_id starting with 'terminal_') do not need chat messages created
    // Because their output is written directly to the terminal panel, handled by appendExecution
    if (!existingItem && !executionId.startsWith('terminal_')) {
      appendOutput({
        output_type: 'execution',
        text: '',
        lang: 'text',
        payload: payload, // Save payload for later use
        execution_id: executionId,
      }, targetAgentId)
      // Terminal initialization automatically triggers setTerminalRef via the template :ref callback; no manual call needed
    }
  } else if (type === 'terminal_created') {
    // Standalone terminal created successfully
    isCreatingTerminalSession.value = false
    const terminalId = payload?.terminal_id
    const nodeId = payload?.node_id
    if (!nodeId) {
      console.error('[ws] terminal_created missing node_id:', payload)
      ElMessage.error('Failed to create terminal: backend did not return node_id')
      return
    }
    if (terminalId) {
      // Deduplicate: for existing sessions (e.g., real-time sharing/recovery scenarios) only update the access level to avoid duplicate pushes
      const existing = terminalSessions.value.find(t => t.terminal_id === terminalId)
      if (existing) {
        if (payload?.access) existing.access = payload.access
        return
      }
      terminalSessions.value.push({
        terminal_id: terminalId,
        node_id: nodeId,
        interpreter: payload?.interpreter || 'bash',
        working_dir: payload?.working_dir || '.',
        access: payload?.access || 'owner',
        terminal: null,
        hostEl: null,
        fitAddon: null,
        resizeObserver: null,  // ResizeObserver instance
        history: [],  // Save history output for restoring when the panel is shown again after being hidden
      })
      // Only auto-switch when this device initiated the terminal creation, to avoid terminals shared by other devices interrupting this device's workflow
      if (terminalCreationTracker.shouldSwitch()) {
        activeTerminalId.value = terminalId
      }
      // Initialize terminal
      nextTick(() => {
        const hostEl = independentTerminalHosts.value.get(terminalId)
        if (hostEl) {
          initIndependentTerminal(terminalId, hostEl)
        }
      })
      // Real-time sharing: take over the session so the backend records this user to receive real-time output
      attachTerminalSession(terminalId)
    }
  } else if (type === 'terminal_closed') {
    // Standalone terminal closed
    const terminalId = payload?.terminal_id
    if (terminalId) {
      // Check whether the terminal still exists, to avoid repeated closing causing an infinite loop
      const session = terminalSessions.value.find(t => t.terminal_id === terminalId)
      if (session) {
        closeTerminal(terminalId)
      }
    }
  } else if (type === 'error') {
    console.warn('[ws] error payload', payload)
    const errorMessage = payload?.message || 'Unknown error'
    const errorCode = payload?.code || ''
    
    // If authentication failed, show the connection dialog again
    if (errorCode === 'AUTH_FAILED') {
      // Show error message
      connectErrorMessage.value = errorMessage
      // Clear the password input box
      auth.value.password = ''
      // Show the connection dialog again
      showConnectModal.value = true
    } else if (errorCode === 'FORBIDDEN') {
      // Permission denied: show a toast notification
      showToast(errorMessage, 'error')
    }
    // Other errors no longer show system error messages via appendOutput, to avoid polluting the session window
    // Error info is still output via console.warn for easier debugging
  } else if (type === 'pipeline_event') {
    // Pipeline orchestration progress event: merge into pipelineStore to drive real-time refresh of the DAG view
    onPipelineEvent(payload)
  } else if (type === 'status_update') {
    // Update Agent execution status
    if (payload?.execution_status) {
      const prevStatus = agentStatuses.value.get(targetAgentId)?.execution_status
      agentStatuses.value.set(targetAgentId, {execution_status: payload.execution_status})

      // Multi-device sync: when the status switches from waiting for input/confirmation to running, clear that Agent's input request and confirmation dialog
      // Prevent other devices from still showing a UI that can be submitted repeatedly after one device has already responded
      if (payload.execution_status === 'running' && ['waiting_single', 'waiting_multi', 'waiting_confirm'].includes(prevStatus)) {
        if (inputRequests.value.has(targetAgentId)) {
          inputRequests.value.delete(targetAgentId)
        }
        if (confirmDialog.value && pendingConfirmAgentId.value === targetAgentId) {
          confirmDialog.value = null
          pendingConfirmAgentId.value = null
        }
        // Clear the Panel embedded confirmation data
        if (panelConfirmData.value.has(targetAgentId)) {
          panelConfirmData.value.delete(targetAgentId)
        }
      }

      // Sync-update the status of the corresponding agent in agentList so the UI responds promptly
      const agentInList = agentList.value.find(a => a.agent_id === targetAgentId)
      if (agentInList) {
        // If execution_status indicates stopped (e.g., 'stopped' or 'finished'), update agent.status
        if (['stopped', 'finished'].includes(payload.execution_status)) {
          agentInList.status = 'stopped'
        } else if (payload.execution_status === 'running') {
          agentInList.status = 'running'
        }
      }

      // When the current Agent starts thinking, auto-scroll to the bottom (and when auto-scroll is on)
      if (payload.execution_status === 'running' && isCurrentAgent(targetAgentId) && isAutoScrollEnabled(targetAgentId)) {
        nextTick(() => {
          if (outputList.value) {
            outputList.value.scrollTop = outputList.value.scrollHeight
          }
        })
      }

      // Send a system notification when the Agent ends
      if (['stopped', 'finished'].includes(payload.execution_status)) {
        const agentInList = agentList.value.find(a => a.agent_id === targetAgentId)
        const agentName = agentInList?.name || agentInList?.agent_type || 'Agent'
        if (notifyOnExit.value) {
          sendSystemNotification(`${agentName} has exited`)
        }
      }

      // Send a system notification when switching from running state to input state
      if (['waiting_single', 'waiting_confirm', 'waiting_multi'].includes(payload.execution_status)) {
        const agentInList = agentList.value.find(a => a.agent_id === targetAgentId)
        const agentName = agentInList?.name || agentInList?.agent_type || 'Agent'
        if (notifyOnInput.value) {
          sendSystemNotification(`${agentName} waiting for input`)
        }
      }
    }
  } else if (type === 'file_upload_response') {
    handleFileUploadResponse(payload)
  } else if (type === 'editor_open_file') {
    // Agent requests to open a file in the editor and locate to the specified line/column (a structured editor command, not an eval_js escape hatch)
    handleEditorOpenFile(payload)
  } else if (type === 'eval_js_request') {
    // The response must use the agentId of the connection that received the request (the main gateway message is null); targetAgentId cannot be used
    handleEvalJsRequest(payload, agentId)
  } else if (type && type.startsWith('chat_')) {
    handleChatMessage(type, payload)
  }
}

// Handle the JS execution request sent down by the backend; send the result back after execution
// agentId: the agent_id corresponding to the Agent connection that received this request (the main gateway message is null)
async function handleEvalJsRequest(payload, agentId = null) {
  const callId = payload?.call_id
  const code = payload?.code
  if (!callId) return
  let response
  try {
    const fn = new Function(`return (async () => { ${code} })()`)
    const value = await fn()
    response = { call_id: callId, success: true, result: safeSerialize(value) }
  } catch (e) {
    response = { call_id: callId, success: false, error: String(e?.stack || e) }
  }
  // The result must be sent back to the connection that received the request: Agent requests go through the Agent connection in sockets,
  // rather than the main gateway connection socket.value (otherwise the main gateway has no corresponding waiter and the result will be discarded)
  const replyWs = agentId ? sockets.value.get(agentId) : socket.value
  if (replyWs && replyWs.readyState === WebSocket.OPEN) {
    replyWs.send(JSON.stringify({ type: 'eval_js_result', payload: response }))
  }
}

// Agent -> editor command: open a file and locate to the specified line/column
// payload: { agent_id, path, line?, column?, select_start?, select_end?, reveal? }
async function handleEditorOpenFile(payload) {
  const agentId = payload?.agent_id || currentAgentId.value
  const path = resolveAgentRelativePath(payload?.path, agentId)
  if (!path) return
  // First locate/create that Agent's editor panel: reuse its existing file panel, or split the current panel
  // Open in a new file panel---to avoid overwriting the current session/chat/terminal area.
  ensureAgentEditorPane(agentId)
  await openWorkspaceFile(path, agentId)   // Reuse the existing entry (create session/load content/activate tab)
  await nextTick()
  const modelData = editorModels.get(path)
  const view = getActiveWorkspaceView()
  if (!view || !modelData) return
  const line = Number(payload?.line || 1)
  const col = Number(payload?.column || 1)
  if (payload?.reveal !== false) view.revealLineInCenter(line)
  if (payload?.select_start != null && payload?.select_end != null) {
    const startCol = Number(payload.select_start) + 1
    const endCol = Math.max(startCol, Number(payload.select_end) + 1)
    view.setSelection(new monaco.Selection(line, startCol, line, endCol))
  }
  view.setPosition({ lineNumber: line, column: col })
  view.focus()
}

// Get the selected content in the currently active editor (used for the command palette action's enabled check and sendSelectionToAgent)
// Returning null means no selection/no editor; otherwise returns { path, text, startLine, endLine }
function getEditorSelection() {
  const view = getActiveWorkspaceView()
  if (!view) return null
  const model = view.getModel()
  if (!model) return null
  const selection = view.getSelection()
  if (!selection || selection.isEmpty()) return null
  const path = model.__haijunbotPath || ''
  const text = model.getValueInRange(selection)
  if (!text || !text.trim()) return null
  return { path, text, startLine: selection.startLineNumber, endLine: selection.endLineNumber }
}

// Send the editor's selected content to the current Agent so the Agent can analyze/explain/modify it
function sendSelectionToAgent() {
  const sel = getEditorSelection()
  if (!sel) {
    showToast('Please select code in the editor first', 'info')
    return
  }
  const agentId = currentAgentId.value
  if (!agentId) {
    showToast('Please select the current Agent first', 'error')
    return
  }
  const location = sel.path
    ? `(File: ${sel.path} lines ${sel.startLine}-${sel.endLine})`
    : `(lines ${sel.startLine}-${sel.endLine})`
  const message = {
    type: 'input_result',
    payload: {
      text: `Please analyze the following selected code${location}:\n${sel.text}`,
      agent_id: agentId,
      display_name: chatName.value || username.value || '',
      input_mode: 'single',
    },
  }
  sendMessageToAgent(message, agentId)
}

// Convert the JS execution result into a JSON structure that can be safely transmitted
function safeSerialize(value) {
  if (value === undefined) return null
  try {
    const json = JSON.stringify(value)
    if (json !== undefined) return JSON.parse(json)
  } catch (e) {
    // Circular reference or non-serializable; use the fallback logic
  }
  let text
  if (typeof Element !== 'undefined' && value instanceof Element) {
    text = `[Element ${value.tagName}] ${value.outerHTML.slice(0, 2000)}`
  } else if (typeof value === 'function') {
    text = `[Function ${value.name || 'anonymous'}]`
  } else {
    text = String(value)
  }
  if (text.length > 10 * 1024 * 1024) text = text.slice(0, 10 * 1024 * 1024) + '...[truncated]'
  return text
}


// Unified message HTML rendering function (used for new messages and history messages)
function renderMessageHtml(payload) {
  if (payload?.output_type === 'DIFF') {
    // Dedicated DIFF type: parse side by side diff data
    try {
      const diffData = JSON.parse(payload.text || '{}')
      if (diffData.diff_type === 'side_by_side') {
        return renderSideBySideDiff(diffData)
      }
    } catch (e) {
      return escapeHtml(payload.text || '')
    }
  }
  if (payload?.lang === 'markdown') {
    return marked.parse(payload.text || '', { breaks: true })
  } else if (payload?.lang === 'diff') {
    // Wrap the diff in a markdown code block for syntax highlighting
    return marked.parse(`\`\`\`diff\n${payload.text || ''}\n\`\`\``)
  } else {
    return escapeHtml(payload.text || '')
  }
}

function appendOutput(payload, agentId = null) {
  // Filter internal control signals to prevent them from displaying in the UI
  if (payload?.text === '__CTRL_C_PRESSED__') {
    return;
  }
  const html = renderMessageHtml(payload)
  
  // Use the timestamp passed from the backend, do not generate locally
  const now = payload?.timestamp || ''
  
  // Extract agent info from context, but prefer the agent_name at the top level of payload
  const context = payload?.context || {}
  const agentName = payload?.agent_name || context.agent_name || context.agent || ''
  const nonInteractive = payload?.non_interactive !== undefined ? payload?.non_interactive : (context.non_interactive || false)
  const agentList = payload?.agent_list || context.agent_list || ''
  const resolvedAgentId = agentId || payload?.agent_id || context.agent_id || currentAgentId.value
  
  // Generate a stable ID to avoid DOM rebuilds caused by v-for using index as key
  const stableId = payload?.execution_id
    ? `exec_${payload.execution_id}`
    : payload?._stableId || `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

  const outputItem = {
    ...payload,
    html,
    timestamp: now,
    agent_name: agentName,
    non_interactive: nonInteractive,
    agent_list: agentList,
    agent_id: resolvedAgentId,
    _stableId: stableId,
  }

  // Determine target Agent ID: prefer the passed-in parameter, then the message's own agent_id, finally fall back to the current Agent
  const targetAgentId = resolvedAgentId
  // Whether this Agent is in some Panel (auto-scroll if inside a Panel)
  const targetPanel = panels.value.find(p => p.agentId === targetAgentId)
  const shouldAutoScroll = !!targetPanel || isCurrentAgent(targetAgentId)

  // Add to the target Agent's message list
  const currentOutputs = allOutputs.value.get(targetAgentId) || []

  // execution message dedup: if an identical execution_id already exists, skip it (avoid duplication between history loading and WebSocket pushes)
  if (outputItem.output_type === 'execution' && outputItem.execution_id) {
    const duplicate = currentOutputs.find(
      item => item.output_type === 'execution' && item.execution_id === outputItem.execution_id
    )
    if (duplicate) {
      return
    }
  }

  // seq dedup: if a message with the same seq already exists, skip it (avoid duplication between history loading and WebSocket pushes)
  if (typeof outputItem.seq === 'number') {
    const duplicate = currentOutputs.find(item => item.seq === outputItem.seq)
    if (duplicate) {
      return
    }
  }

  currentOutputs.push(outputItem)

  // Message count limit: when exceeding 100, truncate the first 50 and keep only the last 50, to avoid excessive DOM causing page lag
  if (currentOutputs.length > 100) {
    currentOutputs.splice(0, currentOutputs.length - 50)
    allOutputs.value.set(targetAgentId, currentOutputs)
  }

  // Save messages to local storage
  try {
    // execution messages are also saved to history (including execution_chunks), used to rebuild xterm after switching Agent
    if (outputItem.output_type === 'execution') {
      const messageToSave = {
        id: outputItem.execution_id ? `execution_${outputItem.execution_id}` : undefined,
        agent_id: targetAgentId,
        output_type: outputItem.output_type,
        text: outputItem.text || '',
        lang: outputItem.lang || 'text',
        agent_name: outputItem.agent_name,
        non_interactive: outputItem.non_interactive,
        agent_list: outputItem.agent_list,
        timestamp: outputItem.timestamp,
        execution_id: outputItem.execution_id,
        context: outputItem.context,
        is_finished: outputItem.is_finished || false,
        terminal_content: outputItem.terminal_content || '',
        execution_chunks: outputItem.execution_chunks || [],
        seq: outputItem.seq, // save seq
      }
      historyStorage.saveMessage(messageToSave)
    } else {
      // Non-execution messages are saved normally
      const messageToSave = {
        id: undefined,
        agent_id: targetAgentId,
        output_type: outputItem.output_type,
        text: outputItem.text,
        lang: outputItem.lang,
        agent_name: outputItem.agent_name,
        non_interactive: outputItem.non_interactive,
        agent_list: outputItem.agent_list,
        timestamp: outputItem.timestamp,
        context: outputItem.context,
        seq: outputItem.seq, // save seq
      }
      historyStorage.saveMessage(messageToSave)
    }
  } catch (error) {
    console.warn('[HISTORY] Failed to save message:', error)
  }
  
  // Auto-scroll to bottom after DOM update (Mermaid/dot rendering is auto-triggered by MutationObserver, and when auto-scroll is enabled)
  nextTick(() => {
    requestAnimationFrame(() => {
      if (!shouldAutoScroll || !isAutoScrollEnabled(targetAgentId)) return
      // Prefer the outputList corresponding to the Panel, then use the global outputList
      const targetOutputList = targetPanel ? panelOutputLists.get(targetPanel.id) : null
      const scrollEl = targetOutputList || outputList.value
      if (scrollEl) {
        const scrollHeight = scrollEl.scrollHeight
        scrollEl.scrollTop = scrollHeight
      }
    })
  })
}

// Scroll the specified Agent's session conversation container to the bottom (when auto-scroll is enabled)
// Used after execution output such as execute_script is written to xterm, so the outer conversation container scrolls along
function scrollSessionToBottom(targetAgentId) {
  if (!targetAgentId || !isAutoScrollEnabled(targetAgentId)) return
  const targetPanel = panels.value.find(p => p.agentId === targetAgentId)
  const targetOutputList = targetPanel ? panelOutputLists.get(targetPanel.id) : null
  // Only scroll that Agent's own container; only when it is the Agent currently being viewed and there is no independent Panel container,
  // fall back to outputList, to avoid a background Agent's terminal output scrolling the view of another Agent the user is viewing all the way to the bottom.
  const scrollEl = targetOutputList || (isCurrentAgent(targetAgentId) ? outputList.value : null)
  if (!scrollEl) return
  nextTick(() => {
    requestAnimationFrame(() => {
      scrollEl.scrollTop = scrollEl.scrollHeight
    })
  })
}

// Copy message content to clipboard
async function copyToClipboard(text, index) {
  if (!text) {
    console.warn('[COPY] No text to copy')
    return
  }
  
  try {
    await navigator.clipboard.writeText(text)
    showToast('Copied to clipboard', 'success')
  } catch (err) {
    console.error('[COPY] Failed to copy text:', err)
    // Optional: fallback plan
    try {
      const textArea = document.createElement('textarea')
      textArea.value = text
      textArea.style.position = 'fixed'
      textArea.style.opacity = '0'
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
    } catch (fallbackErr) {
      console.error('[COPY] Fallback also failed:', fallbackErr)
      alert('Copy failed, please copy manually')
    }
  }
}



// Check whether the cursor is on the first line
function isCursorAtFirstLine(textarea) {
  const cursorPosition = textarea.selectionStart
  const textBeforeCursor = textarea.value.substring(0, cursorPosition)
  return !textBeforeCursor.includes('\n')
}



// Check whether the cursor is on the last line
function isCursorAtLastLine(textarea) {
  const cursorPosition = textarea.selectionEnd
  const textAfterCursor = textarea.value.substring(cursorPosition)
  return !textAfterCursor.includes('\n')
}

// Store the Promise resolve functions waiting for file upload responses
const pendingFileUploads = new Map()

// Handle file upload responses
function handleFileUploadResponse(payload) {
  const { message_id, success, file_path, error } = payload
  const resolve = pendingFileUploads.get(message_id)
  if (resolve) {
    pendingFileUploads.delete(message_id)
    if (success) {
      resolve(file_path)
    } else {
      console.error('File upload failed:', error)
      alert(`Image upload failed: ${error}`)
      resolve(null)
    }
  }
}



// Upload image to node
async function uploadImageToNode(file, agentId = null) {
  // Limit file size to 20MB
  if (file.size > 20 * 1024 * 1024) {
    alert('Image size cannot exceed 20MB')
    return
  }

  const targetAgentId = agentId || currentAgentId.value
  const targetAgent = agentList.value.find(a => a.agent_id === targetAgentId)
  const targetNodeId = String(targetAgent?.node_id || '').trim() || 'master'

  const reader = new FileReader()
  reader.onload = async (e) => {
    const base64Data = e.target.result
    const { host, port } = getGatewayAddress()
    const url = buildNodeHttpUrl(host, port, targetNodeId, 'upload')

    try {
      const response = await fetchWithAuth(url, {
        method: 'POST',
        body: JSON.stringify({
          agent_id: targetAgentId,
          file_name: file.name,
          file_data: base64Data
        })
      })

      const result = await response.json()
      if (result.success && result.data?.file_path) {
        insertTextAtCursor(`${result.data.file_path} `, targetAgentId)
      } else {
        alert('Upload failed: ' + (result.error || 'Unknown error'))
      }
    } catch (error) {
      console.error('Image upload failed:', error)
      alert('Image upload failed: ' + error.message)
    }
  }
  reader.readAsDataURL(file)
}

// Insert text at cursor position
// Insert text at cursor position
function insertTextAtCursor(text, agentId = null) {
  const textarea = document.querySelector('textarea')
  if (!textarea) return

  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const targetAgentId = agentId || currentAgentId.value
  const currentText = targetAgentId
    ? (panelInputTexts.value.get(targetAgentId) || '')
    : inputText.value
  const before = currentText.substring(0, start)
  const after = currentText.substring(end)
  const newText = before + text + after

  if (targetAgentId) {
    panelInputTexts.value.set(targetAgentId, newText)
  }
  inputText.value = newText

  // Update cursor position
  textarea.selectionStart = textarea.selectionEnd = start + text.length
  textarea.focus()
}





// When the buffer is consumed/cleared, if the cache management panel is displaying that Agent's buffer, close the panel and reset the edit text.
// Avoid: â‘  the panel retains stale content (showing stale content when reopened after consumption); â‘¡ the panel automatically pops up again when content is added again after consumption
// (showBufferPanel is still true, and hasBufferedInput changes from false to true triggering v-if to display again).
function closeBufferPanelIfForAgent(agentId) {
  if (bufferPanelAgentId.value === agentId) {
    showBufferPanel.value = false
    bufferEditText.value = ''
  }
}

function updateInputBuffer(agentId, nextValue) {
  inputBuffers.value.set(agentId, nextValue)
  if (currentAgentId.value === agentId) {
    bufferEditText.value = nextValue
  }
}

function appendToInputBuffer(agentId, text) {
  const existingText = inputBuffers.value.get(agentId) || ''
  const nextValue = existingText
    ? `${existingText}\n${text}`
    : text

  updateInputBuffer(agentId, nextValue)
}



function submitCompletion() {
  const agentId = currentAgentId.value
  if (!agentId) {
    console.warn('[SUBMIT] No current agent ID, cannot submit completion')
    return
  }
  
  // Get the current running status
  const statusData = agentStatuses.value.get(agentId)
  const executionStatus = statusData?.execution_status || 'running'
  
  // Add a confirmation dialog to prevent accidental triggering
  showConfirm(
    'Are you sure you want to send the completion signal?',
    () => {
      // User confirmed, send a Ctrl+C signal as the completion signal (consistent with the Ctrl+C behavior in CLI mode)
      // Note: the completion signal only applies to multi-line input; single-line input (such as confirmation dialogs) does not use the completion button
      if (executionStatus === 'waiting_multi') {
        // The backend is waiting for multi-line input, send the Ctrl+C signal directly
        sendInputDirectly('__CTRL_C_PRESSED__', 'single')
      } else {
        // The backend is not waiting for input or is waiting for single-line input, save the completion signal to the buffer (unified mechanism with normal input)
        updateInputBuffer(agentId, '__CTRL_C_PRESSED__')
        appendOutput({
          output_type: 'system',
          agent_name: 'system',
          text: 'âœ… Completion signal saved to buffer, it will trigger automatically the next time input is needed',
          lang: 'text',
        })
      }
    },
    null, // cancel callback, no special handling needed
    true  // defaultConfirm=true, default select "yes"
  )
}

function sendInputDirectly(text, inputMode = 'multi', agentId = null) {
  const targetAgentId = agentId || currentAgentId.value

  const message = {
    type: 'input_result',
    payload: {
      text: text,
      agent_id: targetAgentId,
      display_name: chatName.value || username.value || '',
      input_mode: inputMode,
    },
  }

  sendMessageToAgent(message, targetAgentId)

  // Delete this Agent's input request from the Map
  if (targetAgentId) {
    inputRequests.value.delete(targetAgentId)
  }
}

function sendInputResult(text, requestId, agentId = null, inputMode = 'multi') {
  const targetAgentId = agentId || pendingInputAgentId.value || currentAgentId.value



  const message = {
    type: 'input_result',
    payload: {
      text: text,
      request_id: requestId,
      agent_id: targetAgentId,
      display_name: chatName.value || username.value || '',
      input_mode: inputMode,
    },
  }
  if (targetAgentId) {
    const ws = sockets.value.get(targetAgentId)
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message))
    } else {
      console.warn(`[SEND] No open WebSocket for agent ${targetAgentId}`)
    }
  }
  
  // Delete this Agent's input request from the Map (indicating it has been responded to)
  if (targetAgentId) {
    inputRequests.value.delete(targetAgentId)
  }
  pendingInputAgentId.value = null
}

function sendBufferedInput(agentId = null) {
  const targetAgentId = agentId || currentAgentId.value
  if (!targetAgentId || !inputBuffers.value.has(targetAgentId)) {
    return
  }
  const bufferedText = inputBuffers.value.get(targetAgentId)
  // Clear the buffer
  inputBuffers.value.delete(targetAgentId)
  // Send the buffer contents
  sendInputDirectly(bufferedText, 'multi', targetAgentId)
  // The buffer has been consumed: if the cache panel is displaying that Agent, close the panel and reset the edit text
  closeBufferPanelIfForAgent(targetAgentId)
}

function clearBuffer() {
  const agentId = bufferPanelAgentId.value
  if (!agentId) {
    return
  }
  inputBuffers.value.delete(agentId)
  // After clearing, if the cache panel is displaying that Agent, close the panel and reset the edit text
  closeBufferPanelIfForAgent(agentId)
  appendOutput({
    output_type: 'system',
    agent_name: 'system',
    text: 'ðŸ—‘ï¸ Buffer cleared',
    lang: 'text',
  })
}

function loadBufferToInput() {
  const agentId = bufferPanelAgentId.value
  if (!agentId || !inputBuffers.value.has(agentId)) {
    return
  }
  const bufferedText = inputBuffers.value.get(agentId)
  inputText.value = bufferedText
  showBufferPanel.value = false
  // Focus the input box
  setTimeout(() => {
    const textarea = document.querySelector('.input-wrapper textarea')
    textarea?.focus()
  }, 100)
}

function saveBufferEdit() {
  const agentId = bufferPanelAgentId.value
  if (!agentId || !bufferEditText.value.trim()) {
    return
  }
  updateInputBuffer(agentId, bufferEditText.value.trim())
  appendOutput({
    output_type: 'system',
    agent_name: 'system',
    text: 'âœ… Cache updated',
    lang: 'text',
  })
}

function sendConfirmResult(confirmed, agentId = null) {
  const targetAgentId = agentId || pendingConfirmAgentId.value || currentAgentId.value
  const message = {
    type: 'confirm_result',
    payload: {
      confirmed,
    },
  }
  if (targetAgentId) {
    const ws = sockets.value.get(targetAgentId)
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message))
    } else {
      console.warn(`[SEND] No open WebSocket for agent ${targetAgentId}`)
    }
    // Clear the Panel inline confirmation data
    panelConfirmData.value.delete(targetAgentId)
    // Optimistic downgrade of execution status: avoid, before the backend status_update arrives,
    // the lobby/panel still rendering a default "please confirm" with no messages according to waiting_confirm
    const confirmStatus = agentStatuses.value.get(targetAgentId)?.execution_status
    if (confirmStatus === 'waiting_confirm') {
      agentStatuses.value.set(targetAgentId, {execution_status: 'running'})
    }
    // Restore input mode to multi-line
    inputMode.value = 'multi'
    panelInputModes.value.set(targetAgentId, 'multi')
    inputTip.value = ''
    panelInputTips.value.set(targetAgentId, '')
    // Clear the input box
    panelInputTexts.value.set(targetAgentId, '')
    inputText.value = ''
  }
  pendingConfirmAgentId.value = null
}

// Handle Panel inline confirmation
function handlePanelConfirm(panel) {
  if (!panel || !panel.agentId) return
  const confirmData = panelConfirmData.value.get(panel.agentId)
  if (confirmData?.onConfirm) {
    confirmData.onConfirm()
    panelConfirmData.value.delete(panel.agentId)
    // Clear the input box
    panelInputTexts.value.set(panel.agentId, '')
    inputText.value = ''
    return
  }
  sendConfirmResult(true, panel.agentId)
}

// Handle Panel inline cancel confirmation
function handlePanelCancelConfirm(panel) {
  if (!panel || !panel.agentId) return
  const confirmData = panelConfirmData.value.get(panel.agentId)
  if (confirmData?.onCancel) {
    confirmData.onCancel()
    panelConfirmData.value.delete(panel.agentId)
    // Clear the input box
    panelInputTexts.value.set(panel.agentId, '')
    inputText.value = ''
    return
  }
  sendConfirmResult(false, panel.agentId)
}

// Restore waiting_confirm UI (restore from panelConfirmData)
function restoreWaitingConfirmUI(agentId) {
  if (!agentId) return
  const confirmData = panelConfirmData.value.get(agentId)
  if (confirmData) {
    pendingConfirmAgentId.value = agentId
    // When there is no Panel, do not pop up the global dialog; the confirmation request waits silently, and the user can see the confirm control after opening the Panel
  } else {
    console.warn('[AGENT] No panel confirm data found for agent', agentId)
  }
}

function sendMessageToAgentById(agentId, message) {
  if (!agentId) {
    console.warn('[SEND] No agent ID provided for message:', message?.type)
    return
  }

  const ws = sockets.value.get(agentId)
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message))
  } else {
    console.warn(`[SEND] No open WebSocket for agent ${agentId}`)
  }
}

// Terminal domain (split from the composable useTerminal): xterm instance management, independent terminal sessions,
// terminal floating panel, terminal sharing, execution chunks rebuilding. Dependency injection stays consistent with App.vue.
const {
  terminalHosts,
  terminals,
  getExecutionSessionKey,
  terminalSessions,
  activeTerminalId,
  independentTerminalHosts,
  isCreatingTerminalSession,
  terminalCreationTracker,
  _debouncedSaveExecHistory,
  appendExecution,
  disposeExecutionTerminal,
  setTerminalRef,
  setTerminalHostRef,
  initIndependentTerminal,
  attachTerminalSession,
  restoreTerminalSessions,
  createTerminalForSelectedNode,
  createTerminalForNode,
  createTerminalForAgent,
  closeTerminal,
  saveTerminalPanelRect,
  terminalPanelInteraction,
  ensureTerminalPanelInViewport,
  startTerminalPanelMove,
  startTerminalPanelResize,
  switchTerminal,
  sendTerminalResize,
  showTerminalShareModal,
  terminalShareRead,
  terminalShareInteract,
  openTerminalShareDialog,
  saveTerminalShare,
  filteredUserOptionsForTerminalShare,
} = useTerminal({
  socket,
  sockets,
  currentAgentId,
  currentAgent,
  allOutputs,
  isExecuting,
  windowWidth,
  activeWindow,
  auth,
  showTerminalPanel,
  selectedTerminalNodeId,
  getGatewayAddress,
  fetchWithAuth,
  getHttpProtocol,
  sendMessageToAgentById,
  scrollSessionToBottom,
  getCurrentAgentNodeId,
  showWorkspaceHostView,
  clamp,
  PANEL_DRAG_ACTIVATION_DISTANCE,
  BASE_Z_INDEX,
  ACTIVE_Z_INDEX,
  focusWindow,
  fetchUserList,
  showToast,
  availableUserOptions,
  historyStorage,
})
let heartbeatTimer = null // heartbeat timer (lifecycle managed by App.vue: started in onMounted / cleaned up in onUnmounted)
// Gateway connection (Gateway WebSocket connection + multi-Agent connections + heartbeat detection), split into an independent composable
// Depends on socket/sockets (created at the top level of App.vue)/auth/username/myClientId/terminalSessions/allOutputs/
// currentAgentId/agentList/agentStatuses/showConnectModal/showSettingsModal/userAccessibleNodes/
// gitCustomDir/parseGatewayAddress/buildWebSocketUrl/buildWebSocketProtocols/buildAgentWebSocketUrl/
// getGatewayAddress/buildNodeHttpUrl/fetchWithAuth/loginWithPassword/hasAuthToken/
// startAgentListRefresh/startNodeStatusRefresh/restoreVirtualWorkspaceDirs/loadGitCustomDir/
// refreshUserInfo/fetchUserPermissions/fetchModelGroups/fetchNodeStatus/fetchUserAccessibleNodes/
// restoreTerminalSessions/getOrCreateClientId/sendChatMessageToServer/loadHistoryMessages/
// closeTerminal/handleMessage/getAgentLastSeq/showToast/showConfirm，
// Must be called after useChat/useTerminal (depends on the myClientId/terminalSessions etc. they return)
const {
  gatewayUrl,
  lastPongTime,
  HEARTBEAT_INTERVAL,
  HEARTBEAT_TIMEOUT,
  connecting,
  agentConnecting,
  connectingAgents,
  connectErrorMessage,
  isRestartingGateway,
  restartNodeId,
  restartFrontendService,
  reconnecting,
  reconnectAttempts,
  reconnectTimer,
  reconnectInterval,
  userDisconnected,
  isAutoConnecting,
  connectionStatus,
  connectionLabel,
  connect,
  disconnect,
  reconnect,
  disconnectAll,
  handleRestartGateway,
  confirmRestartGateway,
  restartGateway,
  connectToAgent,
  autoConnectToOnlineAgents,
  checkHeartbeatTimeout,
  sendHeartbeat,
} = useGatewayConnection({
  socket,
  sockets,
  auth,
  username,
  myClientId,
  terminalSessions,
  allOutputs,
  currentAgentId,
  agentList,
  agentStatuses,
  showConnectModal,
  showSettingsModal,
  autoLoginEnabled,
  userAccessibleNodes,
  gitCustomDir,
  parseGatewayAddress,
  buildWebSocketUrl,
  buildWebSocketProtocols,
  buildAgentWebSocketUrl,
  getGatewayAddress,
  buildNodeHttpUrl,
  fetchWithAuth,
  loginWithPassword,
  hasAuthToken,
  startAgentListRefresh,
  startNodeStatusRefresh,
  restoreVirtualWorkspaceDirs,
  loadGitCustomDir,
  refreshUserInfo,
  fetchUserPermissions,
  fetchModelGroups,
  fetchNodeStatus,
  fetchUserAccessibleNodes,
  restoreTerminalSessions,
  getOrCreateClientId,
  sendChatMessageToServer,
  loadHistoryMessages,
  closeTerminal,
  handleMessage,
  getAgentLastSeq,
  showToast,
  showConfirm,
})
function sendInterrupt() {
  const message = {
    type: 'interrupt',
    payload: {},
  }
  sendMessageToAgent(message)
}

function sendManualInterruptToPanel(panel) {
  if (!panel || !panel.agentId) {
    console.warn('[SEND] Invalid panel for manual interrupt')
    return
  }
  const message = {
    type: 'manual_interrupt',
    payload: {},
  }
  sendMessageToAgentById(panel.agentId, message)
}

function confirmClearHistory() {
  // First close the settings dialog
  showSettingsModal.value = false
  
  showConfirm(
    'Are you sure you want to clear all history? This action cannot be undone.',
    () => {
      if (historyStorage.clearHistory()) {
        // Clear the current Agent's messages
        allOutputs.value.set(currentAgentId.value, [])
        // Reset the history load state
        historyOffset.value = 0
        hasMoreHistory.value = true
        // seq is obtained from the history records via getAgentLastSeq(), and automatically returns -1 after clearing history
      } else {
        console.error('[HISTORY] Failed to clear history')
      }
      // Whether clearing succeeds or not, close the settings dialog
      showSettingsModal.value = false
    }
  )
}






// SessionPanel floating panel
const SESSION_PANEL_MIN_WIDTH = 400
const SESSION_PANEL_MIN_HEIGHT = 300
const SESSION_PANEL_STORAGE_KEY_PREFIX = 'haijunbot_session_panel_rect_'
const sessionResizeDirections = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']

function getDefaultSessionPanelRect(panelId) {
  return {
    top: 80,
    left: Math.max(window.innerWidth - 824, 16),
    width: 600,
    height: 500,
  }
}

function loadSessionPanelRect(panelId) {
  const defaultRect = getDefaultSessionPanelRect(panelId)
  const savedValue = localStorage.getItem(SESSION_PANEL_STORAGE_KEY_PREFIX + panelId)
  if (!savedValue) {
    return defaultRect
  }

  try {
    const parsedValue = JSON.parse(savedValue)
    if (
      typeof parsedValue.top !== 'number' ||
      typeof parsedValue.left !== 'number' ||
      typeof parsedValue.width !== 'number' ||
      typeof parsedValue.height !== 'number'
    ) {
      return defaultRect
    }

    return parsedValue
  } catch {
    return defaultRect
  }
}

function saveSessionPanelRect(panelId) {
  const rect = sessionPanelRects.value[panelId]
  if (rect) {
    localStorage.setItem(SESSION_PANEL_STORAGE_KEY_PREFIX + panelId, JSON.stringify(rect))
  }
}

const sessionPanelRects = ref({})  // panelId -> rect
const sessionPanelInteraction = ref({
  active: false,
  mode: null,
  direction: null,
  panelId: null,
  startX: 0,
  startY: 0,
  startTop: 0,
  startLeft: 0,
  startWidth: 0,
  startHeight: 0,
})

function getSessionPanelStyle(panelId) {
  const rect = sessionPanelRects.value[panelId]
  if (!rect) return {}
  return {
    top: `${rect.top}px`,
    left: `${rect.left}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
    zIndex: activeWindow.value === 'session' ? ACTIVE_Z_INDEX : BASE_Z_INDEX,
  }
}

function getSessionPanelBounds() {
  const HEADER_HEIGHT = 32
  const MIN_VISIBLE_WIDTH = 100
  return {
    minTop: 0,
    minLeft: 0,
    maxLeft: window.innerWidth - MIN_VISIBLE_WIDTH,
    maxTop: window.innerHeight - HEADER_HEIGHT,
  }
}

function ensureSessionPanelInViewport(panelId) {
  const rect = sessionPanelRects.value[panelId]
  if (!rect) return
  const HEADER_HEIGHT = 32
  const MIN_VISIBLE_WIDTH = 100
  const maxWidth = Math.max(window.innerWidth, SESSION_PANEL_MIN_WIDTH)
  const maxHeight = Math.max(window.innerHeight, SESSION_PANEL_MIN_HEIGHT)

  rect.width = clamp(rect.width, SESSION_PANEL_MIN_WIDTH, maxWidth)
  rect.height = clamp(rect.height, SESSION_PANEL_MIN_HEIGHT, maxHeight)

  rect.left = clamp(
    rect.left,
    0,
    window.innerWidth - MIN_VISIBLE_WIDTH
  )
  rect.top = clamp(
    rect.top,
    0,
    window.innerHeight - HEADER_HEIGHT
  )
}

function startSessionPanelMove(event, panelId) {
  if (windowWidth.value <= 768) return
  if (event.target.closest('.session-header-actions')) return

  focusWindow('session')

  const rect = sessionPanelRects.value[panelId]
  if (!rect) return

  sessionPanelInteraction.value = {
    active: false,
    mode: 'move',
    direction: null,
    panelId,
    startX: event.clientX,
    startY: event.clientY,
    startTop: rect.top,
    startLeft: rect.left,
    startWidth: rect.width,
    startHeight: rect.height,
  }

  document.addEventListener('mousemove', onSessionPanelPointerMove)
  document.addEventListener('mouseup', stopSessionPanelInteraction)
}

function startSessionPanelResize(event, direction, panelId) {
  if (windowWidth.value <= 768) return

  const rect = sessionPanelRects.value[panelId]
  if (!rect) return

  sessionPanelInteraction.value = {
    active: true,
    mode: 'resize',
    direction,
    panelId,
    startX: event.clientX,
    startY: event.clientY,
    startTop: rect.top,
    startLeft: rect.left,
    startWidth: rect.width,
    startHeight: rect.height,
  }

  document.addEventListener('mousemove', onSessionPanelPointerMove)
  document.addEventListener('mouseup', stopSessionPanelInteraction)
  event.preventDefault()
  event.stopPropagation()
}

function onSessionPanelPointerMove(event) {
  const interaction = sessionPanelInteraction.value
  const panelId = interaction.panelId
  const rect = sessionPanelRects.value[panelId]
  if (!rect) return

  const deltaX = event.clientX - interaction.startX
  const deltaY = event.clientY - interaction.startY

  if (interaction.mode === 'move' && !interaction.active) {
    const dragDistance = Math.hypot(deltaX, deltaY)
    if (dragDistance < PANEL_DRAG_ACTIVATION_DISTANCE) {
      return
    }

    sessionPanelInteraction.value = {
      ...interaction,
      active: true,
    }
    event.preventDefault()
  }

  if (!sessionPanelInteraction.value.active) return

  if (sessionPanelInteraction.value.mode === 'move') {
    const bounds = getSessionPanelBounds()
    rect.left = clamp(interaction.startLeft + deltaX, bounds.minLeft, bounds.maxLeft)
    rect.top = clamp(interaction.startTop + deltaY, bounds.minTop, bounds.maxTop)
    return
  }

  const direction = sessionPanelInteraction.value.direction || ''
  const startLeft = sessionPanelInteraction.value.startLeft
  const startTop = sessionPanelInteraction.value.startTop
  const startWidth = sessionPanelInteraction.value.startWidth
  const startHeight = sessionPanelInteraction.value.startHeight

  let nextLeft = startLeft
  let nextTop = startTop
  let nextWidth = startWidth
  let nextHeight = startHeight

  if (direction.includes('e')) {
    nextWidth = clamp(startWidth + deltaX, SESSION_PANEL_MIN_WIDTH, Math.max(window.innerWidth - startLeft, SESSION_PANEL_MIN_WIDTH))
  }

  if (direction.includes('s')) {
    nextHeight = clamp(startHeight + deltaY, SESSION_PANEL_MIN_HEIGHT, Math.max(window.innerHeight - startTop, SESSION_PANEL_MIN_HEIGHT))
  }

  if (direction.includes('w')) {
    const desiredLeft = clamp(startLeft + deltaX, 0, startLeft + startWidth - SESSION_PANEL_MIN_WIDTH)
    nextLeft = desiredLeft
    nextWidth = startWidth - (desiredLeft - startLeft)
  }

  if (direction.includes('n')) {
    const desiredTop = clamp(startTop + deltaY, 0, startTop + startHeight - SESSION_PANEL_MIN_HEIGHT)
    nextTop = desiredTop
    nextHeight = startHeight - (desiredTop - startTop)
  }

  if (nextLeft + nextWidth > window.innerWidth) {
    nextWidth = Math.max(SESSION_PANEL_MIN_WIDTH, window.innerWidth - nextLeft)
  }

  if (nextTop + nextHeight > window.innerHeight) {
    nextHeight = Math.max(SESSION_PANEL_MIN_HEIGHT, window.innerHeight - nextTop)
  }

  rect.left = clamp(nextLeft, 0, Math.max(window.innerWidth - nextWidth, 0))
  rect.top = clamp(nextTop, 0, Math.max(window.innerHeight - nextHeight, 0))
  rect.width = clamp(nextWidth, SESSION_PANEL_MIN_WIDTH, Math.max(window.innerWidth - rect.left, SESSION_PANEL_MIN_WIDTH))
  rect.height = clamp(nextHeight, SESSION_PANEL_MIN_HEIGHT, Math.max(window.innerHeight - rect.top, SESSION_PANEL_MIN_HEIGHT))
}

function stopSessionPanelInteraction() {
  const panelId = sessionPanelInteraction.value.panelId
  sessionPanelInteraction.value = {
    active: false,
    mode: null,
    direction: null,
    panelId: null,
    startX: 0,
    startY: 0,
    startTop: 0,
    startLeft: 0,
    startWidth: 0,
    startHeight: 0,
  }

  document.removeEventListener('mousemove', onSessionPanelPointerMove)
  document.removeEventListener('mouseup', stopSessionPanelInteraction)
  if (panelId) {
    saveSessionPanelRect(panelId)
  }
}




// Watch the panel display state
watch(showWorkspacePanel, (visible) => {
  if (visible) {
    startWorkspaceFileHeartbeat()
    return
  }

  stopWorkspaceFileHeartbeat()
})

watch(activeWorkspaceTabPath, () => {
  startWorkspaceFileHeartbeat()
})

// Parse the shortcut key string from the registry (such as "Ctrl+Alt+Shift+D" / "F2") into matching conditions

// Parse the shortcut key string from the registry (such as "Ctrl+Alt+Shift+D" / "F2") into matching conditions

// Parse the shortcut key string from the registry (such as "Ctrl+Alt+Shift+D" / "F2") into matching conditions
function parseShortcut(shortcut) {
  if (!shortcut || typeof shortcut !== 'string') return null
  const parts = shortcut.split('+').map(p => p.trim()).filter(Boolean)
  if (!parts.length) return null
  const cond = { ctrl: false, alt: false, shift: false, key: '' }
  for (const part of parts) {
    const lower = part.toLowerCase()
    if (lower === 'ctrl' || lower === 'cmd' || lower === 'meta') cond.ctrl = true
    else if (lower === 'alt' || lower === 'option') cond.alt = true
    else if (lower === 'shift') cond.shift = true
    else cond.key = part
  }
  return cond.key ? cond : null
}

// Determine whether a keyboard event hits a shortcut (based on event.code, to avoid being affected by input method/keyboard layout)
function matchShortcut(shortcut, event) {
  const cond = parseShortcut(shortcut)
  if (!cond) return false
  const ctrlPressed = event.ctrlKey || event.metaKey
  if (ctrlPressed !== cond.ctrl) return false
  if (event.altKey !== cond.alt) return false
  if (event.shiftKey !== cond.shift) return false
  const key = cond.key
  if (/^[a-z]$/i.test(key)) return event.code === 'Key' + key.toUpperCase()
  if (/^[0-9]$/.test(key)) return event.code === 'Digit' + key
  if (key === '`') return event.code === 'Backquote'
  if (key === ',') return event.code === 'Comma'
  if (key === '/') return event.code === 'Slash'
  if (key === '\\') return event.code === 'Backslash'
  if (key === 'Backspace') return event.code === 'Backspace'
  if (/^F[0-9]{1,2}$/i.test(key)) return event.code === key.toUpperCase()
  return event.key === key
}

// Determine whether the event target is an editable element (input box / textarea / contentEditable)
// Used for global shortcut avoidance: pressing keys in editable elements should preserve native behavior
function isEditableElement(target) {
  if (!target || typeof target !== 'object') return false
  const tagName = String(target.tagName || '').toLowerCase()
  if (tagName === 'input' || tagName === 'textarea' || tagName === 'select') return true
  if (target.isContentEditable) return true
  return false
}

// Determine whether focus is inside the Monaco editor (including its hidden input textarea.ime-text-area)
// Used for global shortcut avoidance: when the editor is focused, Monaco's built-in keybindings (multi-cursor / jump to bracket / rename symbol)
// should take effect before global shortcuts, to avoid the global branch grabbing preventDefault first and swallowing the editor's native behavior
function isMonacoEditorFocused() {
  const el = document.activeElement
  if (!el || typeof el.closest !== 'function') return false
  return !!el.closest('.monaco-editor')
}

// Determine whether focus is inside the terminal (xterm). xterm receives keyboard input through a hidden <textarea class="xterm-helper-textarea">
// whose tagName is already textarea (isEditableElement can cover it); here we use the .xterm container
// as an explicit fallback, to avoid depending on changes to xterm's internal DOM structure, ensuring space sequences do not take effect when the terminal is focused.
function isTerminalFocused() {
  const el = document.activeElement
  if (!el || typeof el.closest !== 'function') return false
  return !!el.closest('.xterm')
}

// Whether the editor has "broken away" from global shortcut control: after pressing ESC in the Monaco editor it becomes true,
// so that Ctrl+A is no longer swallowed by the editor's select-all, but instead triggers the command palette (list Agents).
// Clicking/focusing the editor again automatically restores it to false (see onDidFocusEditorText in bindWorkspaceViewEvents).
const editorShortcutLocked = ref(false)

// ===== Space Leader key sequence =====
// Overall redesign: replace a large number of Ctrl+Alt(+Shift)+letter combinations with a two-level key sequence of "space + domain key + action key".
// Semantic keys always use a single letter with no modifiers, absolutely not intercepted by the system/browser (in the user's environment Ctrl+Alt+Shift is intercepted by system software).
// Flow: press space to enter the sequence â†’ popup shows domains â†’ press a domain key (such as a) â†’ popup shows that domain's actions â†’ press an action key to execute.
// ESC interrupts; the popup stays displayed until the user presses a key or ESC interrupts it (no timeout auto-exit);
// when focus is in an input box/editor/terminal, space is preserved as normal input.
// Sequence state: active indicates whether it is activated; path is the entered key sequence ([]=domain pending selection, ['a']=domain selected waiting for action)
const spaceSeq = ref({ active: false, path: [] })

// Lock focus while the space sequence is active: prevent focus from transferring to editable elements (including multi-line input boxes/editors/terminals),
// otherwise subsequent sequence keys would be captured by the input box instead of advancing the sequence.
function handleSpaceSeqFocusIn(e) {
  if (!spaceSeq.value.active) return
  const target = e.target
  if (isEditableElement(target) || isMonacoEditorFocused() || isTerminalFocused()) {
    // Prevent focus from falling into editable elements: blur back to body, letting keystrokes continue through the global keydown to advance the sequence
    if (target && typeof target.blur === 'function') target.blur()
  }
}

function enterSpaceSeq() {
  spaceSeq.value = { active: true, path: [] }
  // When entering the sequence, if focus is in an editable element, move it away immediately, to avoid subsequent keystrokes being captured by the input box
  const el = document.activeElement
  if (el && (isEditableElement(el) || isMonacoEditorFocused() || isTerminalFocused())) {
    el.blur()
  }
}
function exitSpaceSeq() {
  spaceSeq.value = { active: false, path: [] }
}
// The command grouping corresponding to the current space sequence (for floating window rendering): each level is grouped and displayed by "domain prefix". At the first level (no domain selected)
// display the complete sequence (such as ad=show diff); after a domain is selected (such as Space a), commands within the group only show the action keys (such as d for show diff),
// no longer repeating the domain prefix. Keep only the group corresponding to the current prefix, so the user sees all available options under the "current prefix".
const spaceSeqOptions = computed(() => {
  const path = spaceSeq.value.path || []
  const prefix = path.join('')
  const showPrefix = path.length === 0
  return Object.entries(SPACE_COMMANDS)
    .filter(([gKey]) => path.length === 0 || gKey === prefix)
    .map(([gKey, g]) => ({
      key: gKey,
      label: g.label,
      active: path[0] === gKey,
      children: Object.entries(g.children || {}).map(([ck, leaf]) => ({
        key: showPrefix ? gKey + ck : ck,
        label: leaf.label,
        active: path.length === 2 && prefix === gKey + ck,
      })),
    }))
})

// Dialog focus trap: return the currently visible dialog container (take the topmost when multiple dialogs are open simultaneously)
function getActiveOverlay() {
  const overlays = document.querySelectorAll('.modal-overlay, .palette-overlay')
  for (let i = overlays.length - 1; i >= 0; i--) {
    const el = overlays[i]
    // Only take those actually rendered and visible (dialogs controlled by v-if are not in the DOM after closing; then exclude display:none)
    if (el.offsetParent !== null || el.getClientRects().length > 0) return el
  }
  return null
}

// Dialog focus restoration: record the focused element before the dialog opened, restore it after the dialog closes
let overlayReturnFocusEl = null
let overlayObserver = null

// Collect focusable elements inside the dialog (Tab cycle targets)
function getFocusableElements(container) {
  const selector = [
    'button:not([disabled])',
    'input:not([disabled]):not([type="hidden"])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    'a[href]',
    '[tabindex]:not([tabindex="-1"])'
  ].join(', ')
  return Array.from(container.querySelectorAll(selector)).filter(
    (el) => el.offsetParent !== null || el.getClientRects().length > 0
  )
}

// Global keyboard event handling
function handleGlobalKeydown(event) {
  const isModifierPressed = event.ctrlKey || event.metaKey

  // ===== Dialog focus trap: Tab/Shift+Tab cycle within the dialog, do not jump out to the page behind =====
  if (event.key === 'Tab') {
    const overlay = getActiveOverlay()
    if (overlay) {
      // Record the focus before the dialog opened (for restoration after closing); if focus is already inside the dialog, do not record again
      if (!overlayReturnFocusEl && !overlay.contains(document.activeElement)) {
        overlayReturnFocusEl = document.activeElement
      }
      const focusables = getFocusableElements(overlay)
      if (focusables.length) {
        const first = focusables[0]
        const last = focusables[focusables.length - 1]
        const active = document.activeElement
        if (event.shiftKey) {
          // Shift+Tab: wrap from the first (or focus outside the dialog) to the last
          if (active === first || !overlay.contains(active)) {
            event.preventDefault()
            last.focus()
          }
        } else {
          // Tab: wrap from the last (or focus outside the dialog) to the first
          if (active === last || !overlay.contains(active)) {
            event.preventDefault()
            first.focus()
          }
        }
      }
      return
    }
  }

  // ===== Space Leader key sequence (prioritized over all other branches) =====
  if (spaceSeq.value.active) {
    // ESC interrupts the sequence
    if (event.key === 'Escape') {
      event.preventDefault()
      exitSpaceSeq()
      return
    }
    // Space pressed again: reset to the first level (reselect domain)
    if (event.code === 'Space') {
      event.preventDefault()
      spaceSeq.value = { active: true, path: [] }
      return
    }
    // Letter with no modifiers: advance the sequence
    if (!event.ctrlKey && !event.altKey && !event.metaKey && /^[a-z]$/i.test(event.key)) {
      const key = event.key.toLowerCase()
      const path = spaceSeq.value.path
      if (path.length === 0) {
        // First level: select domain
        if (SPACE_COMMANDS[key]) {
          event.preventDefault()
          spaceSeq.value = { active: true, path: [key] }
        } else {
          exitSpaceSeq()
        }
      } else {
        // Second level: select action
        const group = SPACE_COMMANDS[path[0]]
        const leaf = group?.children?.[key]
        if (leaf) {
          const action = actionDefs.find(a => a.id === leaf.actionId)
          exitSpaceSeq()
          event.preventDefault()
          if (action && typeof action.run === 'function') {
            onCommandRun(action)
          }
        } else {
          exitSpaceSeq()
        }
      }
      return
    }
    // Other keys (including modifier combinations): exit the sequence and continue the normal flow
    exitSpaceSeq()
  }

  // Enter the space sequence: space key (no modifiers, focus not in input box/editor/terminal)
  if (event.code === 'Space' && !event.ctrlKey && !event.altKey && !event.metaKey && !event.shiftKey) {
    if (isEditableElement(event.target) || isMonacoEditorFocused() || isTerminalFocused()) return
    event.preventDefault()
    enterSpaceSeq()
    return
  }

  // Ctrl/Cmd + P: when the editor is focused, yield to Monaco (its built-in command palette editor.action.quickCommand is
  // triggered by our additionally bound Ctrl+P addAction); otherwise open the HaijunBot command palette (the login screen does not respond)
  // Exclude Shift: Ctrl+Shift+P goes through the "filename search" branch below (open-editor-file-search)
  if (isModifierPressed && !event.altKey && !event.shiftKey && event.code === 'KeyP') {
    if (showConnectModal.value) return
    // When the editor is focused, yield, letting the event continue propagating to Monaco to trigger its command palette addAction
    if (isMonacoEditorFocused()) return
    event.preventDefault()
    if (!showCommandPalette.value) {
      // Before opening, record the region where focus is located, for "close/detach current focus panel"
      commandPaletteFocusKey = getFocusedZoneKey()
      // When opened via shortcut, clear the pre-input, to avoid carrying over the query brought in by the last pet menu
      commandPaletteInitialQuery.value = ''
    }
    showCommandPalette.value = !showCommandPalette.value
    return
  }

  // Ctrl/Cmd + A opens the command palette and directly shows the Agent list (pre-input a>)
  // Note: Ctrl+A is the universal shortcut for "select all"; it must yield when focus is in the Monaco editor or an input box,
  // Otherwise it would swallow the select-all behavior of the editor/input box.
  // Exception: when the editor has already "escaped" shortcut control via ESC (editorShortcutLocked), it no longer yields,
  // letting Ctrl+A trigger the command palette instead of selecting all in the editor.
  // Ordinary input boxes (textarea/input/contentEditable) yield unconditionally: even if editorShortcutLocked
  // is true (ESC was pressed to escape the editor), Ctrl+A should still revert to native select-all upon entering the input box.
  // Exclude Shift: Ctrl+Shift+A does not trigger this branch (to avoid accidental interception)
  if (isModifierPressed && !event.altKey && !event.shiftKey && event.code === 'KeyA') {
    if (showConnectModal.value) return
    if (isEditableElement(event.target) || (!editorShortcutLocked.value && isMonacoEditorFocused())) return
    event.preventDefault()
    commandPaletteFocusKey = getFocusedZoneKey()
    commandPaletteInitialQuery.value = 'a>'
    showCommandPalette.value = true
    return
  }

  // Ctrl/Cmd + F opens the command palette and directly enters file search (pre-filled with f>)
  // Note: Ctrl+F is the common shortcut for "Find"; when focus is in the Monaco editor or an input box it must yield,
  // otherwise it would swallow the native find behavior of the editor/input box.
  // Exception: when the editor has already "escaped" shortcut control via ESC (editorShortcutLocked), it no longer yields.
  // Ordinary input boxes (textarea/input/contentEditable) yield unconditionally: even if editorShortcutLocked
  // is true (ESC was pressed to escape the editor), Ctrl+F should still revert to native find upon entering the input box.
  // Exclude Shift: Ctrl+Shift+F goes to the "content search" branch below (open-editor-global-search)
  if (isModifierPressed && !event.altKey && !event.shiftKey && event.code === 'KeyF') {
    if (showConnectModal.value) return
    if (isEditableElement(event.target) || (!editorShortcutLocked.value && isMonacoEditorFocused())) return
    event.preventDefault()
    commandPaletteFocusKey = getFocusedZoneKey()
    commandPaletteInitialQuery.value = 'f>'
    showCommandPalette.value = true
    return
  }

  // Ctrl/Cmd + Alt + Shift + arrow keys: select a node by direction in the lobby (relative to the current selected node's position,
  // when nothing is selected, start from the opposite edge of that direction, e.g. → takes the first node on the far left).
  // Consistent with the node operation shortcuts (Ctrl+Alt+Shift+letter): "adding Shift means it acts on nodes".
  if (event.ctrlKey && event.altKey && event.shiftKey &&
      (event.key === 'ArrowLeft' || event.key === 'ArrowRight' || event.key === 'ArrowUp' || event.key === 'ArrowDown')) {
    // When the editor is focused, yield to Monaco's native keybindings (Ctrl+Alt+↑/↓ inserts a cursor, Shift variants are selection variants)
    if (isMonacoEditorFocused()) return
    event.preventDefault()
    showCommandPalette.value = false
    const dirMap = { ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down' }
    const lobby = petLobbyRef.value
    if (lobby && typeof lobby.selectNodeInDirection === 'function' && lobby.selectNodeInDirection(dirMap[event.key])) {
      return
    }
    return
  }

  // Ctrl/Cmd + Alt + arrow keys: prioritize selecting an Agent by direction in the lobby (relative to the current selected pet's position,
  // when nothing is selected, start from the one closest to the edge in that direction); when the lobby has no pets, fall back to region-level focus jumping
  // (Session Panel / integrated terminal / editor). Uses the Ctrl+Alt combination to avoid conflicting with the arrow key behavior of input boxes/other controls
  if (event.ctrlKey && event.altKey && !event.shiftKey &&
      (event.key === 'ArrowLeft' || event.key === 'ArrowRight' || event.key === 'ArrowUp' || event.key === 'ArrowDown')) {
    const dirMap = { ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down' }
    const dir = dirMap[event.key]
    // When the editor is focused, yield to Monaco's addAction (Ctrl+Alt+←/→ jumps to "previous/next edit location",
    // Ctrl+Alt+↑/↓ is "insert cursor above/below" multi-cursor editing). Left/right arrow keys also yield in read-only mode,
    // ensuring edit-location jumping is always available; up/down arrow keys only yield in editable mode (in read-only mode multi-cursor doesn't take effect anyway, so continue switching panes).
    if (isMonacoEditorFocused()) {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') return
      if (isWorkspaceEditable.value) return
    }
    event.preventDefault()
    showCommandPalette.value = false
    const inWorkspace = getFocusedZoneKey() === 'workspace' || getNamedPanelFocusKey() === 'workspace'
    // Workspace: switch the active split region (pane)
    if (inWorkspace && showWorkspacePanel.value) {
      if (moveActivePaneInDirection(dir)) return
      return
    }
    // Lobby: switch Agent
    const lobby = petLobbyRef.value
    if (lobby && typeof lobby.selectAgentInDirection === 'function' && lobby.selectAgentInDirection(dir)) {
      return
    }
    moveFocusInDirection(dir)
    return
  }

  // Ctrl/Cmd + S saves the current editor tab
  // Only save when focus is actually in the editor workspace (including the Monaco editor / tab bar / sidebar);
  // otherwise do not intercept, to avoid accidentally triggering the "file saved" prompt on the frontend main interface.
  if (isModifierPressed && !event.altKey && event.key === 's') {
    if (getFocusedZoneKey() === 'workspace' &&
        showWorkspacePanel.value && activeWorkspaceTab.value && !activeWorkspaceTab.value.loading) {
      event.preventDefault()
      saveActiveWorkspaceTab()
    }
    return
  }

  // Ctrl/Cmd + Shift + F quickly reaches the editor sidebar's "content search" (does not respond when the editor is not open)
  if (isModifierPressed && !event.altKey && event.shiftKey && event.code === 'KeyF') {
    if (!showWorkspacePanel.value) return
    // Preserve default behavior inside input boxes (to avoid interrupting input); exception inside the editor—allows searching directly after selecting text in the editor
    if (isEditableElement(event.target) && !isMonacoEditorFocused()) return
    event.preventDefault()
    openWorkspaceGlobalSearch('content')
    return
  }

  // Ctrl/Cmd + Shift + P quickly reaches the editor sidebar's "filename search" (does not respond when the editor is not open)
  if (isModifierPressed && !event.altKey && event.shiftKey && event.code === 'KeyP') {
    if (!showWorkspacePanel.value) return
    // Preserve default behavior inside input boxes (to avoid interrupting input); exception inside the editor—allows searching directly after selecting text in the editor
    if (isEditableElement(event.target) && !isMonacoEditorFocused()) return
    event.preventDefault()
    openWorkspaceGlobalSearch('filename')
    return
  }

  // Ctrl/Cmd + Shift + E quickly reaches the editor sidebar's directory tree (does not respond when the editor is not open)
  if (isModifierPressed && !event.altKey && event.shiftKey && event.code === 'KeyE') {
    if (!showWorkspacePanel.value) return
    // Preserve default behavior inside input boxes (to avoid interrupting input)
    if (isEditableElement(event.target)) return
    event.preventDefault()
    setWorkspaceSidebarView('files')
    focusFileTreeContainer()
    return
  }

  // Ctrl/Cmd + E opens/hides the editor panel
  if (isModifierPressed && !event.altKey && !event.shiftKey && event.code === 'KeyE') {
    event.preventDefault()
    if (showWorkspacePanel.value) {
      closeWorkspacePanel()
    } else {
      showWorkspacePanel.value = true
    }
    return
  }

  // Ctrl/Cmd + L opens the command palette and directly shows the Agent list (pre-filled with a>)
  // Consistent with the registry's open-agent-list (Ctrl+L); must intercept the browser's default address bar focus
  if (isModifierPressed && !event.altKey && !event.shiftKey && event.code === 'KeyL') {
    if (showConnectModal.value) return
    // Preserve default behavior inside input boxes (to avoid interrupting input)
    if (isEditableElement(event.target)) return
    event.preventDefault()
    commandPaletteFocusKey = getFocusedZoneKey()
    commandPaletteInitialQuery.value = 'a>'
    showCommandPalette.value = true
    return
  }
  // Ctrl/Cmd + N opens the create Agent dialog (intercepts the browser's new window)
  if (isModifierPressed && !event.altKey && !event.shiftKey && event.code === 'KeyN') {
    // Does not respond on the login screen
    if (showConnectModal.value) return
    // Preserve default behavior inside input boxes (to avoid interrupting input)
    if (isEditableElement(event.target)) return
    event.preventDefault()
    openCreateAgentModal()
    return
  }

  // Ctrl + ` opens/hides the terminal panel
  if (event.ctrlKey && !event.altKey && event.key === '`') {
    event.preventDefault()
    if (socket.value) {
      toggleTerminalPanel()
    }
  }



  // Ctrl + Alt + Enter sends the buffer contents (effective when the buffer has content)
  if (event.ctrlKey && event.altKey && event.key === 'Enter') {
    if (hasBufferedInput.value) {
      event.preventDefault()
      sendBufferedInput()
    }
  }

  // F2 rename: the same physical key is reused in different scenarios, dispatched by the registry's shortcutScope
  // - global scenario: rename the current Agent (higher priority than nodes)
  // - node scenario: when there is no current Agent, rename the selected node in the lobby
  // Do not trigger repeatedly when the Agent rename dialog is already open
  if (event.key === 'F2') {
    if (showRenameAgentModal.value) return
    // When the editor is focused, yield to Monaco's "rename symbol" (F2)
    if (isMonacoEditorFocused()) return
    const agent = getCurrentAgentOrNull()
    if (agent) {
      event.preventDefault()
      renameAgent(agent)
      return
    }
    const lobby = petLobbyRef.value
    if (lobby && typeof lobby.renameActiveNode === 'function' && lobby.renameActiveNode()) {
      event.preventDefault()
    }
    return
  }

  // Delete removes the selected Agent in the pet lobby (requires confirmation)
  // Only effective when the pet lobby has a selected pet and focus is not on an editable element, to avoid affecting normal character deletion
  if (event.key === 'Delete' && !isModifierPressed && !event.altKey && !event.shiftKey) {
    if (!isEditableElement(event.target) && lobbyActiveAgentId.value) {
      const agent = agentList.value.find(a => a.agent_id === lobbyActiveAgentId.value)
      if (agent) {
        event.preventDefault()
        deleteAgent(agent.agent_id)
        return
      }
    }
  }

  // Ctrl/Cmd + \ splits the currently active pane left/right; Ctrl/Cmd + - splits up/down
  // Effective whenever the workspace is open (no longer limited to the editor file view) and not on mobile; when not split, first split the active pane.
  // Split up/down changed to Ctrl+- (replacing the original Ctrl+Shift+\, to avoid conflicting with Monaco's "jump to matching bracket";
  // it also overrides Monaco's Ctrl+- zoom out; users don't need zooming).
  if (isModifierPressed && !event.altKey && !event.shiftKey && event.code === 'Backslash') {
    if (showWorkspacePanel.value && windowWidth.value > 768) {
      event.preventDefault()
      splitWorkspacePane(activePaneId.value, 'row')
      return
    }
  }
  // Ctrl/Cmd + - splits up/down (main keyboard minus Minus / numpad minus NumpadSubtract)
  if (isModifierPressed && !event.altKey && !event.shiftKey &&
      (event.code === 'Minus' || event.code === 'NumpadSubtract')) {
    if (showWorkspacePanel.value && windowWidth.value > 768) {
      event.preventDefault()
      splitWorkspacePane(activePaneId.value, 'column')
      return
    }
  }

// Ctrl/Cmd + W closes the panel where the current focus is (must intercept the browser's native close-tab behavior)
// When focus is inside a panel (terminal/editor/chat/session panel), prioritize closing that panel;
// When focus is not in any panel (i.e. in the pet lobby) and there is an active pet, instead "hide that Agent's output and deselect it"
// Exclude Shift: Ctrl+Shift+W does not trigger this branch (to avoid accidentally intercepting browser/other behavior)
  if (isModifierPressed && !event.altKey && !event.shiftKey && event.code === 'KeyW') {
    event.preventDefault()
// When the editor is split and focus is in the editor workspace: Ctrl+W prioritizes closing "the file of the active pane"
// (VS Code semantics); if there is no file, close that pane. The unsplit state is handled uniformly by closeFocusedPanel.
    if (workspacePaneCount.value > 1 && workspaceMainView.value === 'file' && windowWidth.value > 768) {
      const editorZone = getFocusedZoneKey()
      const namedKey = getNamedPanelFocusKey()
      if (editorZone === 'workspace' || namedKey === 'workspace') {
        if (handleWorkspaceCloseShortcut()) return
        closeFocusedPanel()
        return
      }
    }
// Inside a named panel (terminal/workspace/chat): even if focus is not on a focusable element (the panel was only mouse-clicked),
// it should still close that panel, rather than being intercepted by the lobby logic
    if (!getFocusedZoneKey() && !getNamedPanelFocusKey()) {
      const lobby = petLobbyRef.value
      if (lobby && typeof lobby.hideActiveOutputAndClose === 'function' && lobby.hideActiveOutputAndClose()) {
        return
      }
    }
    closeFocusedPanel()
    return
  }

  // ESC key closes all dialogs
  if (event.key === 'Escape') {
    // When the Panel context menu is open, prioritize closing it
    if (panelContextMenu.value.visible) {
      closePanelContextMenu()
      return
    }
    // When the completion panel is open, prioritize closing it (focus may still be in the input box, so handle it uniformly here)
    if (showCompletions.value) {
      closeCompletionsWithoutSelect()
      return
    }
    // When the command palette is open, prioritize closing it
    if (showCommandPalette.value) {
      showCommandPalette.value = false
      return
    }
    // When the network topology full view is open, prioritize closing it
    if (showTopologyOverlay.value) {
      showTopologyOverlay.value = false
      return
    }
    // When the admin panel is open, prioritize closing it
    if (showAdminPanel.value) {
      showAdminPanel.value = false
      return
    }
    // When the about dialog is open, prioritize closing it
    if (showAboutModal.value) {
      showAboutModal.value = false
      return
    }
    // Popup panels (diff/rules/tools/cache/rename/permission management): Esc closes them
    if (showDiffModal.value) {
      // Mobile detail state: Esc first returns to the file list, pressing again closes the dialog
      if (diffMobileShowDetail.value) {
        diffMobileShowDetail.value = false
        return
      }
      showDiffModal.value = false
      return
    }
    if (showRulesModal.value) {
      showRulesModal.value = false
      return
    }
    if (showToolsModal.value) {
      showToolsModal.value = false
      return
    }
    if (showRenameAgentModal.value) {
      showRenameAgentModal.value = false
      return
    }
    if (showEditAccessModal.value) {
      showEditAccessModal.value = false
      return
    }
    if (showBufferPanel.value) {
      showBufferPanel.value = false
      return
    }
    // If a dialog is open, close the dialog
    if (showSettingsModal.value) {
      showSettingsModal.value = false
    } else if (showCreateAgentModal.value) {
      showCreateAgentModal.value = false
    } else if (showQuickCreateAgentModal.value) {
      showQuickCreateAgentModal.value = false
    } else if (showSessionDialog.value) {
      cancelSessionDialog()
    } else if (showDirDialog.value) {
      cancelDirDialog()
    } else if (showOpenDirDialog.value) {
      closeOpenDirDialog()
    }
    
    // ESC key also closes the mobile menu
    if (showMobileMenu.value) {
      showMobileMenu.value = false
    }
    
    // ESC key also closes the terminal panel (mobile)
    if (showTerminalPanel.value && windowWidth.value <= 768) {
      showTerminalPanel.value = false
    }

    // Lowest priority: deselect the selected pet in the pet lobby (does nothing when nothing is selected)
    if (petLobbyRef.value && typeof petLobbyRef.value.closeActivePanel === 'function') {
      petLobbyRef.value.closeActivePanel()
    }

    // When a pane is temporarily maximized, Esc restores the original layout
    if (maximizedPaneId.value) {
      maximizedPaneId.value = null
      nextTick(() => {
        remountMonacoEditor()
        layoutGitDiffEditor()
      })
      return
    }

    // When focus is in the Monaco editor or an editable input box (no dialog/menu needs closing), pressing ESC removes focus,
    // letting the editor/input box "escape" shortcut control: afterward Ctrl+A is no longer swallowed by select-all/the input box,
    // but instead triggers the command palette (listing Agents).
    // - Monaco editor: set editorShortcutLocked as a fallback (its hidden textarea's isMonacoEditorFocused after blur
    //   may still be true), automatically restored when the editor is refocused (see onDidFocusEditorText in bindWorkspaceViewEvents).
    // - Ordinary input boxes (textarea/input/contentEditable): blur directly; after focus moves out, event.target is no longer an input box.
    const ae = document.activeElement
    if (isMonacoEditorFocused()) {
      editorShortcutLocked.value = true
      if (ae && typeof ae.blur === 'function') ae.blur()
    } else if (ae && isEditableElement(ae)) {
      if (typeof ae.blur === 'function') ae.blur()
    }
  }

  // Unified dispatch of registry shortcuts: if an action with a shortcut in the registry is hit, execute it
  // Does not respond on the login screen; the Ctrl+Alt combination also takes effect inside input boxes (without conflicting with native input box editing),
  // only the login screen and disabled actions are skipped
  if ((event.ctrlKey || event.metaKey) && event.altKey) {
    if (showConnectModal.value) return
    const matched = actionDefs.find(a => a.shortcut && matchShortcut(a.shortcut, event))
    if (matched) {
      const ctx = commandPaletteCtx.value
      const isEnabled = typeof matched.enabled === 'function' ? matched.enabled(ctx) : true
      if (isEnabled) {
        event.preventDefault()
        onCommandRun(matched)
      }
      return
    }
  }
}


// Focus the active terminal inside the integrated terminal
function focusActiveTerminal() {
  const session = terminalSessions.value.find(s => s.terminal_id === activeTerminalId.value)
    || terminalSessions.value[0]
  if (session?.terminal) {
    session.terminal.focus()
    return true
  }
  return false
}

// Region container fallback focus: when there is no focusable element inside the region (e.g. empty terminal/empty editor),
// let focus land on the region container, ensuring arrow key navigation has landing feedback and the subsequent navigation start point is correct
function focusZoneContainer(el) {
  if (!el) return
  if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1')
  if (typeof el.focus === 'function') el.focus({ preventScroll: true })
}

// Whether it is a truly focusable element (excluding disabled / invisible)
function isFocusableTarget(el) {
  if (!el || typeof el.focus !== 'function') return false
  if (el.disabled) return false
  if (el.hasAttribute && el.hasAttribute('disabled')) return false
  // Controls with tabindex="-1" (such as region split/close, title bar buttons) deliberately do not participate in focus navigation,
  // so they should also be skipped in fallback focusing, to avoid focus landing on these "non-focus-stealing" buttons
  if (el.getAttribute && el.getAttribute('tabindex') === '-1') return false
  return true
}

// Find the first focusable element in the region and focus it; if not found, fall back to focusing the container
function focusFirstIn(el, selector) {
  if (!el) return
  const defaultSel = 'textarea, input, [contenteditable="true"], button:not([disabled]):not([tabindex="-1"]), [tabindex]:not([tabindex="-1"])'
  const list = selector ? el.querySelectorAll(`${selector}:not([disabled])`) : el.querySelectorAll(defaultSel)
  for (const target of list) {
    if (isFocusableTarget(target)) {
      target.focus({ preventScroll: true })
      return
    }
  }
  focusZoneContainer(el)
}

// Build the list of focusable regions (only currently visible items), attaching their screen rectangles for geometric navigation
// Order: each Session Panel → integrated terminal → editor → chat room
function getFocusZones() {
  const zones = []
  for (const panel of panels.value) {
    if (!panel.agentId) continue
    zones.push({
      key: `session:${panel.id}`,
      kind: 'session',
      focus: () => {
        activatePanel(panel.id)
        nextTick(() => {
          if (isAnyModalOpen()) return
          focusCurrentPanelInput(true)
        })
      },
    })
  }
  if (showTerminalPanel.value) {
    zones.push({
      key: 'terminal',
      kind: 'terminal',
      focus: () => {
        focusWindow('terminal')
        nextTick(() => {
          if (focusActiveTerminal()) return
          // When there is no active terminal, fall back to focusing the first focusable control inside the terminal (e.g. the "new terminal" button),
          // to avoid focus being reset by the framework after focusing a non-interactive container
          focusFirstIn(document.querySelector('.terminal-panel'))
        })
      },
    })
  }
  if (showWorkspacePanel.value) {
    zones.push({
      key: 'workspace',
      kind: 'workspace',
      focus: () => {
        focusWindow('workspace')
        nextTick(() => {
          const view = getActiveWorkspaceView()
          if (view) {
            view.focus()
            return
          }
          // When there is no editor content, fall back to focusing the first focusable control inside the editor (e.g. activity bar buttons),
          // to avoid focus being reset by the framework after focusing a non-interactive container
          focusFirstIn(document.querySelector('.workspace-panel'))
        })
      },
    })
  }
  if (showChatPanel.value) {
    zones.push({
      key: 'chat',
      kind: 'chat',
      focus: () => {
        focusWindow('chat')
        nextTick(() => {
          focusFirstIn(document.querySelector('.chat-panel'), '.chat-input')
        })
      },
    })
  }
  return zones
}

// Infer the current region key based on the real DOM focus (more reliable than activeWindow:
// activeWindow is only updated when focusWindow is explicitly called; it is not synchronized when the user clicks a panel input box)
function getFocusedZoneKey() {
  const el = document.activeElement
  if (!el) return null
  const termEl = document.querySelector('.terminal-panel')
  if (termEl && termEl.contains(el)) return 'terminal'
  const workspaceEl = document.querySelector('.workspace-panel')
  if (workspaceEl && workspaceEl.contains(el)) return 'workspace'
  const chatEl = document.querySelector('.chat-panel')
  if (chatEl && chatEl.contains(el)) return 'chat'
  for (const panel of panels.value) {
    if (!panel.agentId) continue
    const root = sessionPanelRefs.get(panel.id)?.$el
    if (root && root.contains(el)) return `session:${panel.id}`
  }
  return null
}

// The current focus region key (used to locate the starting point for geometric navigation)
function getActiveFocusZoneKey() {
  // Prioritize based on the real focus position
  const focusedKey = getFocusedZoneKey()
  if (focusedKey) return focusedKey
  // Fallback: based on the explicitly recorded current window
  if (activeWindow.value === 'terminal' && showTerminalPanel.value) {
    return 'terminal'
  }
  if (activeWindow.value === 'workspace' && showWorkspacePanel.value) {
    return 'workspace'
  }
  if (activeWindow.value === 'chat' && showChatPanel.value) {
    return 'chat'
  }
  const panel = getCurrentPanel()
  if (panel && panel.agentId) return `session:${panel.id}`
  return null
}

// Get the screen rectangle of the focus region; returns null when invisible/no DOM
function getFocusZoneRect(zone) {
  if (!zone) return null
  let el = null
  if (zone.kind === 'session') {
    const panelId = zone.key.slice('session:'.length)
    el = sessionPanelRefs.get(panelId)?.$el || null
  } else if (zone.kind === 'terminal') {
    el = document.querySelector('.terminal-panel')
  } else if (zone.kind === 'workspace') {
    el = document.querySelector('.workspace-panel')
  } else if (zone.kind === 'chat') {
    el = document.querySelector('.chat-panel')
  }
  if (!el || typeof el.getBoundingClientRect !== 'function') return null
  const rect = el.getBoundingClientRect()
  if (rect.width <= 0 && rect.height <= 0) return null
  return rect
}

// Determine whether the candidate region is located in the given direction relative to the current region, and return a ranking score (smaller is higher priority)
// dir: 'left' | 'right' | 'up' | 'down'
function scoreFocusZoneByDirection(curRect, candRect, dir) {
  const curCenterX = curRect.left + curRect.width / 2
  const curCenterY = curRect.top + curRect.height / 2
  const candCenterX = candRect.left + candRect.width / 2
  const candCenterY = candRect.top + candRect.height / 2

  if (dir === 'left') {
    if (candCenterX >= curCenterX) return null
    const primary = curRect.left - candRect.right
    // The smaller the vertical centerline displacement, the higher the priority
    const secondary = Math.abs(candCenterY - curCenterY)
    return primary * 1000 + secondary
  }
  if (dir === 'right') {
    if (candCenterX <= curCenterX) return null
    const primary = candRect.left - curRect.right
    const secondary = Math.abs(candCenterY - curCenterY)
    return primary * 1000 + secondary
  }
  if (dir === 'up') {
    if (candCenterY >= curCenterY) return null
    const primary = curRect.top - candRect.bottom
    const secondary = Math.abs(candCenterX - curCenterX)
    return primary * 1000 + secondary
  }
  if (dir === 'down') {
    if (candCenterY <= curCenterY) return null
    const primary = candRect.top - curRect.bottom
    const secondary = Math.abs(candCenterX - curCenterX)
    return primary * 1000 + secondary
  }
  return null
}

// Move between focusable regions by geometric layout: based on the current region rectangle, choose the region closest in that direction
function moveFocusInDirection(dir) {
  const zones = getFocusZones()
  if (zones.length === 0) return
  const activeKey = getActiveFocusZoneKey()
  const currentZone = zones.find(z => z.key === activeKey)
  const curRect = getFocusZoneRect(currentZone)
  if (!curRect) return

  let bestZone = null
  let bestScore = Infinity
  for (const zone of zones) {
    if (zone.key === activeKey) continue
    const candRect = getFocusZoneRect(zone)
    if (!candRect) continue
    const score = scoreFocusZoneByDirection(curRect, candRect, dir)
    if (score === null) continue
    if (score < bestScore) {
      bestScore = score
      bestZone = zone
    }
  }
  if (bestZone) bestZone.focus()
}
// Mobile history management variables
let historyStateCount = 0

// Mobile: push history state when opening the overlay
const pushOverlayState = () => {
  if (windowWidth.value <= 768) {
    window.history.pushState({ overlay: true }, '', '')
    historyStateCount++
  }
}

// Open the editor panel and switch to the "Agent list" view (the only entry point of the original global Agent sidebar)
const openWorkspaceAgentList = () => {
  if (!showWorkspacePanel.value) {
    showWorkspacePanel.value = true
    if (windowWidth.value <= 768) {
      pushOverlayState()
    }
  }
  setWorkspaceSidebarView('agents')
}

// Open/close the terminal panel (mobile handles history)
const toggleTerminalPanel = () => {
  // When the workspace is showing the terminal, the semantics are "collapse": switch back to the file view
  if (workspaceHostsTerminal.value) {
    setWorkspaceMainView('file')
    return
  }
  showWorkspaceHostView('terminal')
}
// Open/close the editor panel (mobile handles history; does not depend on the current Agent, consistent with Ctrl+E behavior)
const toggleWorkspacePanel = () => {
  if (showWorkspacePanel.value) {
    closeWorkspacePanel()
    return
  }
  showWorkspacePanel.value = true
  if (windowWidth.value <= 768) {
    pushOverlayState()
  }
}

watch(showWorkspacePanel, async (visible) => {
  if (visible) {
    ensureWorkspacePanelInViewport()
    await nextTick()
    ensureMonacoEditor()
    if (activeWorkspaceTabPath.value) {
      activateWorkspaceTab(activeWorkspaceTabPath.value)
    }
    nextTick(() => layoutMonacoEditor())
  } else {
    stopWorkspacePanelInteraction()
  }
})

watch(activeWorkspaceTabPath, async (path) => {
  if (!path) return
  await nextTick()
  ensureMonacoEditor()
  activateWorkspaceTab(path)
})


watch(
  () => auth.value.token,
  (newToken) => {
    try {
      window.postMessage({ type: 'haijunbot_token_changed', token: newToken || null }, '*')
    } catch (e) {
      console.warn('[AUTH] broadcast token change failed:', e)
    }
    // Notify plugin subscribers of token changes
    __haijunbotEmit('token_changed', { token: newToken || null })
    // Sync to the local daemon when the token changes (including logout to empty)
    syncTokenToDaemon(newToken, window.__haijunbotAuthBridge.getGateway())
  }
)

// Notify plugin subscribers when user info changes (login/refresh/logout all go through here)
watch(
  () => auth.value.userInfo,
  (newUserInfo) => {
    __haijunbotEmit('user_changed', { userInfo: newUserInfo || null })
  }
)

// Notify plugin subscribers when the current Agent switches (payload structure is consistent with __haijunbotGetActiveAgentInfo)
watch(
  () => currentAgentId.value,
  (newAgentId) => {
    const agent = agentList.value.find(a => a.agent_id === newAgentId) || null
    __haijunbotEmit('agent_changed', agent
      ? { agentId: agent.agent_id, agentName: agent.name || agent.agent_id, workingDir: agent.working_dir || '' }
      : null)
  }
)

// Notify plugin subscribers when the node list changes
watch(
  () => availableNodeOptions.value,
  (nodes) => {
    __haijunbotEmit('nodes_changed', { nodes: Array.isArray(nodes) ? [...nodes] : [] })
  }
)

onMounted(() => {
  // Phase 4: restore the previous editor split layout (invalid data automatically falls back to the default single leaf)
  restoreWorkspacePaneLayout()
  // Terminal name: when the user has never configured it, use the computer name reported by the local daemon as the default value
  initTerminalNameFromDaemon()
  // No longer create the terminal on page load; instead create it dynamically

  // Start the heartbeat mechanism
  heartbeatTimer = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL)

  // seq is obtained dynamically from history by getAgentLastSeq(); no need to load during initialization

  // Try to load the saved token from localStorage (auto-login feature)
  loadSavedToken()

  // If the token loads successfully, hide the login box and connect automatically
  if (hasAuthToken()) {
    showConnectModal.value = false
    isAutoConnecting.value = true
    connect()
    // When a token already exists on page load (the loadSavedToken backfill path does not trigger watch), push once more to the local daemon,
    // ensuring the daemon and the page's login state are consistent; failure is silent and does not affect the main connection flow.
    syncTokenToDaemon(auth.value.token, window.__haijunbotAuthBridge.getGateway())
    // Load the frontend extension points declared by plugins (admin_tabs / sidebar_views / tool_panels)
    loadPluginExtensionsForUi()
  }

  updateViewportHeight()
  visualViewportResizeHandler = () => {
    updateViewportHeight()
  }
  window.visualViewport?.addEventListener('resize', visualViewportResizeHandler)

  inputHistory.value = loadInputHistory()
  
  // Only start the Agent list refresh when logged in, to avoid sending requests to the backend before obtaining the token
  if (hasAuthToken()) {
    startAgentListRefresh()
  }

  // Client session polling (browser extension / background service): the mini topology is always displayed, so polling must start right after mounting,
  // otherwise the client nodes would only appear after the user opens the topology full view once.
  if (hasAuthToken()) {
    startTopologyAccessPolling()
  }

  // Local daemon online detection: independent of login state (the daemon can answer /api/status without authentication),
  // used to hide the lobby's "install local background service" guide entry.
  startLocalDaemonProbe()
  
  // Add a scroll event listener to load more history when scrolled to the top
  setupHistoryScrollListener(outputList.value)
  
  // Add a global keyboard event listener (handles Ctrl+T and other shortcuts in the capture phase)
  document.addEventListener('keydown', handleGlobalKeydown, { capture: true })

  // Lock focus during space-sequence activation to prevent focus from falling into the input box/editor/terminal
  document.addEventListener('focusin', handleSpaceSeqFocusIn)

  // Click anywhere outside the menu to close the Panel context menu (the menu itself already stops propagation)
  document.addEventListener('pointerdown', closePanelContextMenu)
  
  // Listen to the window resize event
  handleResize = () => {
    windowWidth.value = window.innerWidth
    updateViewportHeight()
    ensureWorkspacePanelInViewport()
    ensureTerminalPanelInViewport()
    saveWorkspacePanelRect()
    saveTerminalPanelRect()
    // When split, each Monaco instance has its own automaticLayout (ResizeObserver) and follows the container size on its own,
    // No longer calling layout() individually here (otherwise resize → layout → size change → layout again would cause oscillation).
    if (workspacePaneCount.value <= 1) {
      layoutMonacoEditor()
    }

    const activeSession = terminalSessions.value.find(session => session.terminal_id === activeTerminalId.value)
    if (activeSession && activeSession.fitAddon && activeSession.terminal) {
      activeSession.fitAddon.fit()
      sendTerminalResize(activeSession.terminal_id, activeSession.terminal.rows, activeSession.terminal.cols)
    }
  }
  window.addEventListener('resize', handleResize)

  // Mobile: listen for the back button (popstate event)
  handlePopState = () => {
    
    if (historyStateCount > 0) {
      // There is pushed history state; just close the overlay, do not actually go back
      historyStateCount--
      
      // Close all open overlays
      if (showSettingsModal.value) {
        showSettingsModal.value = false
      } else if (showCreateAgentModal.value) {
        showCreateAgentModal.value = false
      } else if (showSessionDialog.value) {
        cancelSessionDialog()
      } else if (showDirDialog.value) {
        cancelDirDialog()
      } else if (showTerminalPanel.value && windowWidth.value <= 768) {
        showTerminalPanel.value = false
      } else if (showMobileMenu.value) {
        showMobileMenu.value = false
      } else if (windowWidth.value <= 768 && !hasNoPanel.value) {
        // Mobile: close the currently visible Panel, return to the pet hall
        closeVisiblePanelsOnMobile()
      } else {
      }
    } else {
      // No pushed history state; allow default back behavior
    }
  }
  window.addEventListener('popstate', handlePopState)

  // MutationObserver: watch outputList DOM changes, auto-render mermaid/dot diagrams
  if (outputList.value) {
    let diagramRenderTimer = null
    diagramObserver = new MutationObserver(() => {
      // Debounce: avoid frequent triggering during streaming updates
      if (diagramRenderTimer) clearTimeout(diagramRenderTimer)
      diagramRenderTimer = setTimeout(async () => {
        const hasMermaid = outputList.value?.querySelector('.mermaid-container[data-mermaid-source]')
        const hasDot = outputList.value?.querySelector('.dot-container[data-dot-source]')
        if (hasMermaid) await renderMermaidDiagrams(outputList.value)
        if (hasDot) await renderDotDiagrams(outputList.value)
      }, 50)
    })
    diagramObserver.observe(outputList.value, { childList: true, subtree: true })
  }

  // Dialog focus restoration: record the focus before opening when the dialog appears, restore focus when the dialog is removed from the DOM (by any close method)
  overlayObserver = new MutationObserver(() => {
    const overlay = document.querySelector('.modal-overlay, .palette-overlay')
    if (overlay) {
      // Dialog appears: record the focus before opening (if focus is not inside the dialog)
      const active = document.activeElement
      if (!overlayReturnFocusEl && active && !overlay.contains(active)) {
        overlayReturnFocusEl = active
      }
    } else if (overlayReturnFocusEl) {
      // Dialog disappears: restore focus to the element focused before opening
      const target = overlayReturnFocusEl
      overlayReturnFocusEl = null
      // Only restore when the target element still exists and is focusable, to avoid focus landing on a destroyed element
      if (target && document.body.contains(target) && typeof target.focus === 'function') {
        target.focus()
      }
    }
  })
  overlayObserver.observe(document.body, { childList: true, subtree: true })
})

onUnmounted(() => {

  // Clean up the onboarding delayed-display timer
  clearOnboardingTimer()

  // Clean up scroll listener
  if (historyScrollListenerEl && historyScrollHandler) {
    historyScrollListenerEl.removeEventListener('scroll', historyScrollHandler)
    historyScrollListenerEl = null
    historyScrollHandler = null
  }
  if (historyScrollDebounceTimer) {
    clearTimeout(historyScrollDebounceTimer)
    historyScrollDebounceTimer = null
  }
  
  // Clean up heartbeat timer
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
  
  stopWorkspacePanelInteraction()
  stopWorkspaceFileHeartbeat()
  // Stop access-point session polling
  stopTopologyAccessPolling()
  // Stop local daemon online probing
  stopLocalDaemonProbe()
  window.visualViewport?.removeEventListener('resize', visualViewportResizeHandler)

  for (const [, view] of editorViews) {
    view.dispose()
  }
  editorViews.clear()
  workspaceViewPanes.clear()
  for (const modelData of editorModels.values()) {
    if (modelData.model && !modelData.model.isDisposed()) {
      modelData.model.dispose()
    }
  }
  editorModels.clear()
  // Release all LSP connections to avoid WS leaks
  disposeAllLspClients()
  lspBindings.clear()

  // Remove global keyboard event listener
  document.removeEventListener('keydown', handleGlobalKeydown, { capture: true })

  // Remove space-sequence focus lock listener
  document.removeEventListener('focusin', handleSpaceSeqFocusIn)

  // Remove the global close listener for the Panel context menu
  document.removeEventListener('pointerdown', closePanelContextMenu)
  
  // Remove window resize listener
  window.removeEventListener('resize', handleResize)

  // Remove back button listener
  window.removeEventListener('popstate', handlePopState)

  // Disconnect the diagram rendering MutationObserver
  if (diagramObserver) {
    diagramObserver.disconnect()
    diagramObserver = null
  }

  // Disconnect the dialog focus restoration MutationObserver
  if (overlayObserver) {
    overlayObserver.disconnect()
    overlayObserver = null
  }
  overlayReturnFocusEl = null
})


</script>

<style>
/* Global styles */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

/* Background highlight for the Agent waiting-for-input state */
.workspace-agent-node.waiting-input {
  background: rgba(210, 153, 34, 0.15);
}

html,
body {
  width: 100vw;
  height: var(--app-height, 100vh);
  min-height: 100vh;
  min-height: 100dvh;
  margin: 0;
  padding: 0;
  overflow: hidden;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

#app {
  width: 100vw;
  height: var(--app-height, 100vh);
  min-height: 100vh;
  min-height: 100dvh;
  margin: 0;
  padding: 0;
}

/* Global scrollbar styles - apply to all scrollable elements */
*::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

*::-webkit-scrollbar-track {
  background: var(--color-bg-primary);
  border-radius: 3px;
}

*::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
}

*::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.25);
}

*::-webkit-scrollbar-thumb:active {
  background: rgba(255, 255, 255, 0.3);
}

*::-webkit-scrollbar-corner {
  background: transparent;
}

/* html and body do not show scrollbars (use in-app scrolling) */
html::-webkit-scrollbar,
body::-webkit-scrollbar {
  display: none;
}

/* When the directory selection dialog is opened from within the "Orchestration" dialog, it must overlay the orchestration dialog (z-index:3000) */
.palette-overlay.dir-dialog-above-orchestrate {
  z-index: 3100;
}

/* PWA fullscreen/standalone mode: content extends to the very top of the screen, removing the status bar/cutout safe margins (achieving true fullscreen).
   Note: only effective in PWA installed mode; browser tab mode still retains safe margins to avoid being covered by the browser top bar.
   This block must be placed in global <style> (non-scoped), otherwise html/body/#app will have data-v attributes added and cannot be matched. */
@media (display-mode: fullscreen), (display-mode: standalone) {
  /* In mobile PWA fullscreen, --app-height uses visualViewport.height (excluding the system status bar),
     causing the .app height to be insufficient, and the top status bar/cutout area exposes the dark body background forming a black edge.
     Here, add safe-area-inset-top to the html/body/#app/.app heights so the page covers to the very top of the screen. */
  html, body, #app, .app {
    height: calc(var(--app-height, 100vh) + env(safe-area-inset-top, 0px));
  }
  .app {
    padding-top: 0;
    padding-left: 0;
    padding-right: 0;
  }
}

</style>

<style scoped src="./styles/app-layout.css"></style>
<style scoped src="./styles/app-split-pane.css"></style>
<style scoped src="./styles/app-editor-sidebar.css"></style>
<style scoped src="./styles/app-git-view.css"></style>
<style scoped src="./styles/app-agent-window.css"></style>
<style scoped src="./styles/app-session-panel.css"></style>
<style scoped src="./styles/app-panel-grid.css"></style>
<style scoped src="./styles/app-chat.css"></style>
<style scoped src="./styles/app-terminal-input.css"></style>
<style scoped src="./styles/app-buffer-buttons.css"></style>
<style scoped src="./styles/app-modals.css"></style>
<style scoped src="./styles/app-context-menus.css"></style>
<style scoped src="./styles/app-toast.css"></style>
<style scoped src="./styles/app-responsive.css"></style>
<style scoped src="./styles/app-toggle-switch.css"></style>
<style scoped src="./styles/app-diff-rules.css"></style>
<style scoped src="./styles/app-orchestrate.css"></style>
