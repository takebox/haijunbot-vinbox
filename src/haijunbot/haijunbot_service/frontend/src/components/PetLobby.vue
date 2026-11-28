<template>
  <div class="pet-lobby" ref="stageRef" @click="onStageClick">
    <!-- Floor style Background -->
    <div class="pet-lobby-floor"></div>
    <!-- Floor up 's Slogan：make Old、mottled weathered texture -->
    <div class="pet-lobby-slogan" aria-hidden="true">
      <span class="pet-lobby-slogan-text">Stand alone, work together</span>
    </div>
    <div class="pet-lobby-glow pet-lobby-glow-a"></div>
    <div class="pet-lobby-glow pet-lobby-glow-b"></div>

    <!--  left  up  corner：GatewayInfo instrument Table（Time + ConnectStatus + GatewayAddress + Node + User），style andNode topology consistent，Not intercept interactions -->
    <div class="pet-lobby-dash" aria-hidden="true">
      <div class="lobby-dash-time">{{ dashTime }}</div>
      <div class="lobby-dash-date">{{ dashDate }}</div>
      <div class="lobby-dash-divider"></div>
      <div class="lobby-dash-row">
        <span class="lobby-dash-dot" :class="'is-' + connectionStatus"></span>
        <span class="lobby-dash-label">{{ connectionLabel || 'Unknown' }}</span>
      </div>
      <div class="lobby-dash-row">
        <span class="lobby-dash-label">Gateway</span>
        <span class="lobby-dash-value">{{ gatewayAddress || '—' }}</span>
      </div>
      <div class="lobby-dash-row">
        <span class="lobby-dash-label">Node</span>
        <span class="lobby-dash-value">{{ nodeOnlineStat.online }}/{{ nodeOnlineStat.total }}</span>
      </div>
      <div v-if="agentStatusStat.length" class="lobby-dash-row">
        <span class="lobby-dash-label">Agent</span>
        <span class="lobby-dash-agents">
          <span v-for="s in agentStatusStat" :key="s.state" class="lobby-dash-agent-item" :title="s.label">
            <span class="lobby-dash-agent-dot" :style="{ background: s.color }"></span>
            <span class="lobby-dash-agent-num">{{ s.count }}</span>
          </span>
        </span>
      </div>
      <div v-if="currentUserName" class="lobby-dash-row">
        <span class="lobby-dash-label">User</span>
        <span class="lobby-dash-value">{{ currentUserName }}</span>
      </div>
    </div>

    <!-- Nodeand connecting-lines layer：reference big screen「Net topology」style（chassis shape + lines），position at/on floor of up 、Pet of down  -->
    <div class="pet-lobby-topology" aria-hidden="true">
      <svg class="pet-lobby-links" :width="stageSize.w" :height="stageSize.h" :viewBox="`0 0 ${stageSize.w} ${stageSize.h}`">
        <defs>
          <linearGradient id="lobby-center-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#e8d089" />
            <stop offset="100%" stop-color="#c99a34" />
          </linearGradient>
          <filter id="lobby-glow" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="2.4" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        <!-- connecting lines：master → each Node -->
        <g class="lobby-links-master">
          <line
            v-for="link in nodeLinks"
            :key="link.key"
            :x1="link.x1"
            :y1="link.y1"
            :x2="link.x2"
            :y2="link.y2"
            :stroke="link.offline ? 'rgba(255,93,108,0.35)' : '#20c8ff'"
            :stroke-opacity="link.offline ? 1 : 0.55"
            :stroke-width="1.6"
            :stroke-dasharray="link.offline ? '6 5' : ''"
            class="lobby-link"
            :class="{ 'is-flow': !link.offline }"
          />
        </g>

        <!-- connecting lines：Agent Pet → its own Node（follows PetMoveReal-timeUpdate） -->
        <g class="lobby-links-agent">
          <line
            v-for="link in agentLinks"
            :key="link.key"
            :x1="link.x1"
            :y1="link.y1"
            :x2="link.x2"
            :y2="link.y2"
            :stroke="link.color"
            stroke-width="1"
            stroke-dasharray="3 3"
            opacity="0.7"
          />
        </g>

        <!-- curve connecting lines：master → each itemsOnlineconnect/join in end（Browser extension / Local daemon service） -->
        <!-- end point QuantityNot fixed（mayHas more devices / more itemsBrowser），therefore use curves minCol both sides，avoidandNode between straight-line confusion -->
        <!--  must  must  arrange in/atNode of front render：SVG No z-index， back rendered ones in/at up layer，Nothen connecting lines will cover GatewayNode -->
        <g class="lobby-links-local">
          <path
            v-for="link in accessLinks"
            :key="link.key"
            :d="link.d"
            fill="none"
            :stroke="link.offline ? 'rgba(255,93,108,0.35)' : '#20c8ff'"
            :stroke-opacity="link.offline ? 1 : 0.55"
            :stroke-width="1.6"
            :stroke-dasharray="link.offline ? '6 5' : ''"
            class="lobby-link"
            :class="{ 'is-flow': !link.offline }"
          />
        </g>

        <!-- Node：Service device chassis shape（master golden Center，the rest colored by Status） -->
        <g
          v-for="n in nodeItems"
          :key="n.node_id"
          class="lobby-node"
          :class="['st-' + n.state, { 'is-center': n.isMaster, active: n.active }]"
          @click.stop="onNodeClick(n)"
          @contextmenu.prevent.stop="onNodeContextMenu(n, $event)"
        >
          <!-- chassis body -->
          <rect
            :x="n.x - n.rw"
            :y="n.y - n.rh"
            :width="n.rw * 2"
            :height="n.rh * 2"
            rx="6"
            :fill="n.fill"
            :stroke="n.color"
            :stroke-width="n.isMaster ? 1.6 : 1.3"
            class="lobby-node-body"
          />
          <!-- Top slot -->
          <line
            :x1="n.x - n.rw + 6" :y1="n.y - n.rh + 7"
            :x2="n.x + n.rw - 6" :y2="n.y - n.rh + 7"
            :stroke="n.color" stroke-width="1.4" opacity="0.6"
          />
          <!-- heat-dissipation grille -->
          <line
            v-for="k in 3" :key="'g' + k"
            :x1="n.x - n.rw + 8" :y1="n.y - n.rh + 6 + k * 4.6"
            :x2="n.x + n.rw - 16" :y2="n.y - n.rh + 6 + k * 4.6"
            :stroke="n.color" stroke-width="1" opacity="0.35"
          />
          <!-- indicator light -->
          <circle :cx="n.x + n.rw - 10" :cy="n.y - 2" r="2.4" :fill="n.color" class="lobby-node-led" />
          <circle :cx="n.x + n.rw - 10" :cy="n.y + 5" r="2.4" :fill="n.color" opacity="0.4" />
          <!-- BottomStatusitems -->
          <rect
            :x="n.x - n.rw + 6" :y="n.y + n.rh - 8"
            :width="n.rw * 2 - 12" :height="3" rx="1.5"
            :fill="n.color" opacity="0.5"
          />
          <text :x="n.x" :y="n.y + n.rh + 16" text-anchor="middle" class="lobby-node-label">{{ n.short }}</text>
          <text :x="n.x" :y="n.y + n.rh + 29" text-anchor="middle" class="lobby-node-count">{{ n.agentCount }} agent</text>
          <text
            v-if="n.version"
            :x="n.x"
            :y="n.y + n.rh + 41"
            text-anchor="middle"
            class="lobby-node-version"
            :class="{ mismatch: n.versionMismatch }"
          >{{ n.version }}</text>
        </g>

        <!-- connect/join in endNode： up Row=Browser extension， down Row=Local daemon service（circular shape，andGateway chassis Node clearly distinct min） -->
        <!-- Name/Version/Platform all come from GatewaySession（Extension hello  up reports name、daemon hello  up reports name/hostname） -->
        <g
          v-for="n in accessNodes"
          :key="n.id"
          class="lobby-node is-local"
          :class="'st-' + n.state"
        >
          <title>{{ n.title }}</title>
          <!-- circular body -->
          <circle :cx="n.x" :cy="n.y" :r="LOCAL_NODE_RH"
                  :fill="n.fill" :stroke="n.color" stroke-width="1.3" class="lobby-node-body" />
          <!-- TypeIcon -->
          <g :transform="`translate(${n.x - 8}, ${n.y - 8})`">
            <svg v-if="n.icon === 'extension'" viewBox="0 0 16 16" width="16" height="16" fill="none" :stroke="n.color" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
              <path d="M6 3.5A1.5 1.5 0 0 1 9 3.5V4h1.5A1.5 1.5 0 0 1 12 5.5V7h.5a1.5 1.5 0 0 1 0 3H12v1.5A1.5 1.5 0 0 1 10.5 13H9v.5a1.5 1.5 0 0 1-3 0V13H4.5A1.5 1.5 0 0 1 3 11.5V10h-.5a1.5 1.5 0 0 1 0-3H3V5.5A1.5 1.5 0 0 1 4.5 4H6z"/>
            </svg>
            <svg v-else-if="n.icon === 'daemon'" viewBox="0 0 16 16" width="16" height="16" fill="none" :stroke="n.color" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="3" width="12" height="8" rx="1.5"/>
              <path d="M5.5 13.5h5M8 11v2.5"/>
            </svg>
          </g>
          <!-- Tags text：vertical tohour up  down Drop（TopRowin/at down 、BottomRowin/at up ）、horizontal tohour left  right Drop（ left Colin/at right 、 right Colin/at left ），all toward Middle -->
          <text :x="n.labelAbove === null ? (n.anchor === 'start' ? n.x + LOCAL_NODE_RH + 16 : n.x - LOCAL_NODE_RH - 16) : n.x"
                :y="n.labelAbove === null ? n.y : (n.labelAbove ? n.y - LOCAL_NODE_RH - 16 : n.y + LOCAL_NODE_RH + 16)"
                :text-anchor="n.anchor" class="lobby-node-label">{{ n.short }}</text>
          <text :x="n.labelAbove === null ? (n.anchor === 'start' ? n.x + LOCAL_NODE_RH + 16 : n.x - LOCAL_NODE_RH - 16) : n.x"
                :y="n.labelAbove === null ? n.y + 13 : (n.labelAbove ? n.y - LOCAL_NODE_RH - 29 : n.y + LOCAL_NODE_RH + 29)"
                :text-anchor="n.anchor" class="lobby-node-count">{{ n.sub }}</text>
        </g>
      </svg>
    </div>

    <!--  right  up  corner：RoamSwitch + SpriteShowModeSwitch -->
    <div class="pet-lobby-toggles">
      <button
        class="pet-lobby-roam-toggle"
        :class="{ off: !roaming }"
        :title="roaming ? 'ClickStoppedPetRoam' : 'Click to start pet roaming'"
        @click.stop="roaming = !roaming"
      >
        <span class="pet-lobby-roam-icon" v-html="roaming ? PET_ICONS.roam : PET_ICONS.stand"></span>
        <span class="pet-lobby-roam-label">{{ roaming ? 'Roaming' : 'Standing still' }}</span>
      </button>

      <!-- Show/Hide Agent Sprite：Control all Has Agent Sprite's ShowandHide（Button label for Will want execute Row's Action） -->
      <button
        class="pet-lobby-display-toggle"
        :class="{ off: petsHidden }"
        :title="petsHidden ? 'Click to show Agent sprites' : 'Click to hide Agent sprites'"
        @click.stop="toggleAllPets()"
      >
        <span class="pet-lobby-display-icon" v-html="petsHidden ? PET_ICONS.eye : PET_ICONS.eyeOff"></span>
        <span class="pet-lobby-display-label">{{ petsHidden ? 'Show Agent sprites' : 'Hide Agent sprites' }}</span>
      </button>

      <!-- AllOutput show/hide：one KeySwitch（AllHide ↔ AllShow），Button label for Will want execute Row's Action -->
      <button
        class="pet-lobby-display-toggle"
        :title="allOutputsHidden ? 'Show all Agent outputs' : 'Hide all Agent outputs'"
        @click.stop="toggleAllOutputs()"
      >
        <span class="pet-lobby-display-icon" v-html="allOutputsHidden ? PET_ICONS.chat : PET_ICONS.ban"></span>
        <span class="pet-lobby-display-label">{{ allOutputsHidden ? 'Show all outputs' : 'Hide all outputs' }}</span>
      </button>

      <!-- Install browser extension：OpenInstall guide popup（ inner containing DownloadButton）；HasNewVersion hourShow red dot -->
      <!-- AlreadyDetected local InstallExtension（content script written in the DOM Mark）hourHidethe/thisButton：since installed then Not  must again guide Install -->
      <button
        v-if="!extensionInstalled"
        class="pet-lobby-display-toggle pet-lobby-install-toggle"
        :class="{ 'has-update': extensionVersion.outdated }"
        title="Install browser extension"
        @click.stop="openInstallExtensionDialog()"
      >
        <span class="pet-lobby-display-icon" v-html="PET_ICONS.puzzle"></span>
        <span class="pet-lobby-display-label">Install browser extension</span>
        <span v-if="extensionVersion.outdated" class="pet-lobby-update-dot" title="Extension has new version"></span>
      </button>

      <!-- Install local daemon service（daemon）：OpenInstall guide popup（ inner containing DownloadLinkandInstallCommand） -->
      <!-- AlreadyDetected local Install and Running daemon（local loopback /api/status probe Success）hourHidethe/thisButton：since installed then Not  must again guide Install -->
      <button
        v-if="!daemonInstalled"
        class="pet-lobby-display-toggle"
        title="Install local daemon service"
        @click.stop="openDaemonDialog()"
      >
        <span class="pet-lobby-display-icon" v-html="PET_ICONS.monitor"></span>
        <span class="pet-lobby-display-label">Local daemon service</span>
      </button>
    </div>
    <!-- No Agent hour's EmptyStatus guidance：temporarily hour removed（both end are all Not  shown）， back later will reNew design -->
    <!-- Pet group -->
    <div
      v-for="pet in petAgents"
      v-show="showPets"
      :key="pet.agentId"
      class="lobby-pet"
      :class="[pet.classes, { active: pet.active, dragging: pet.dragging, dimmed: activePetId && activePetId !== pet.agentId, 'is-code-agent': pet.agentType === 'code_agent' }]"
      :style="{ left: pet.x + 'px', top: pet.y + 'px' }"
      @pointerdown="onPetPointerDown(pet, $event)"
      @dblclick="onPetDblClick(pet)"
      @contextmenu.prevent.stop="onPetContextMenu(pet, $event)"
    >
      <div class="lobby-pet-inner">
        <div class="lobby-pet-body">
          <div class="lobby-pet-head">
            <div class="lobby-pet-ear l"></div>
            <div class="lobby-pet-ear r"></div>
            <div class="lobby-pet-eye l"><div class="lobby-pet-pupil"></div></div>
            <div class="lobby-pet-eye r"><div class="lobby-pet-pupil"></div></div>
            <div class="lobby-pet-mouth"></div>
          </div>
          <div class="lobby-pet-tail"></div>
        </div>
        <div class="lobby-pet-shadow"></div>
      </div>
      <div class="lobby-pet-name"><span class="lobby-pet-type">
        <svg v-if="pet.agentType === 'code_agent'" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M5.5 4.5 2.5 8l3 3.5M10.5 4.5l3 3.5-3 3.5"/>
          <path d="M9.5 3.5l-3 9"/>
        </svg>
        <svg v-else viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <rect x="3" y="5" width="10" height="7" rx="2"/>
          <circle cx="5.5" cy="8.5" r="0.7" fill="currentColor" stroke="none"/>
          <circle cx="10.5" cy="8.5" r="0.7" fill="currentColor" stroke="none"/>
          <path d="M6 3.5 8 5l2-1.5"/>
          <path d="M5 12v1.5M11 12v1.5"/>
          <path d="M3 10H1.5M14.5 10H13"/>
        </svg>
      </span>{{ pet.name }}</div>
      <div v-if="petWorkingDir(pet)" class="lobby-pet-dir" :title="petWorkingDir(pet)">{{ petWorkingDir(pet) }}</div>
      <div class="lobby-pet-status" :class="pet.statusClass"></div>

      <!-- OutputBubble + Input/ConfirmControl：stacked in/atPet down side -->
      <div
        v-show="!isOutputHidden(pet.agentId) || pet.active || pet.inputMode === 'confirm'"
        class="lobby-pet-stack"
        :class="{ 'stack-above': pet.panelAbove }"
        :style="{ left: pet.stackLeft + 'px', width: pet.stackWidth + 'px', maxHeight: pet.stackMaxH + 'px' }"
        @pointerdown.stop
        @click.stop
        @dblclick.stop
      >
        <!-- OutputBubble：persistent Show（markdown rendering）；ClickBubble same way Activethe/this Agent -->
        <div v-if="pet.output && !isOutputHidden(pet.agentId)" class="lobby-pet-output-wrap">
          <div
            class="lobby-pet-output message-body markdown-content"
            :data-pet-output="pet.agentId"
            v-html="pet.output"
            @click.stop="onPetClick(pet)"
            @scroll="onOutputScroll(pet, $event)"
          ></div>
          <button
            class="lobby-pet-copy"
            :class="{ copied: pet.copied }"
            :title="pet.copied ? 'Copied' : 'Copy output'"
            @click.stop="copyPetOutput(pet)"
          >{{ pet.copied ? '✓' : '⧉' }}</button>
          <button
            class="lobby-pet-export"
            :class="{ exported: pet.exported }"
            :title="pet.exported ? 'Exported' : 'Export as image'"
            @click.stop="exportPetOutput(pet)"
          ><span v-html="pet.exported ? '✓' : PET_ICONS.image"></span></button>
        </div>

        <!-- ConfirmControl：needConfirmhour directly connect/joinShow（NoNeed Click） -->
        <div v-if="pet.inputMode === 'confirm'" class="lobby-pet-panel">
          <div class="lobby-pet-confirm">
            <div class="lobby-pet-confirm-msg">{{ pet.confirmMessage || 'Please confirm' }}</div>
            <div class="lobby-pet-confirm-actions" :class="{ 'default-yes': pet.confirmDefault !== false }">
              <button class="lobby-pet-confirm-btn yes" @click="submitConfirm(pet, true)">Confirm</button>
              <button class="lobby-pet-confirm-btn no" @click="submitConfirm(pet, false)">Cancel</button>
            </div>
          </div>
        </div>

        <!-- InputPanel：click Expand（ more Row/single Row，based on StatusAutoSelect） -->
        <div v-else-if="pet.active" class="lobby-pet-panel">
          <!--  more RowInput -->
          <div v-if="pet.inputMode === 'multi'" class="lobby-pet-input-row lobby-pet-input-row-multi">
            <textarea
              class="lobby-pet-textarea"
              rows="3"
              :data-pet-input="pet.agentId"
              :placeholder="pet.inputTip || 'Enter content (Ctrl+Enter / Ctrl+D to send)'"
              v-model="pet.inputText"
              @keydown="handlePetKeydown(pet, $event)"
              @keyup="handlePetCtrlKeyup($event)"
              @input="handlePetInput(pet, $event)"
              @pointerdown.stop="onInputPointerDown(pet)"
            ></textarea>
            <button v-if="isMobile" class="lobby-pet-at" @click="insertAtSymbol(pet)" title="Insert @ trigger autocomplete">@</button>
            <button class="lobby-pet-complete" @click="completePet(pet)" title="Done (send empty message)">Done</button>
            <button class="lobby-pet-send" @click="submitPet(pet)" title="Send (Ctrl+Enter)">➤</button>
          </div>

          <!-- single RowInput -->
          <div v-else class="lobby-pet-input-row">
            <input
              class="lobby-pet-input"
              :type="pet.isPassword ? 'password' : 'text'"
              :data-pet-input="pet.agentId"
              :placeholder="pet.inputTip || 'Enter content (Enter to send)'"
              v-model="pet.inputText"
              @keydown="handlePetSingleKeydown(pet, $event)"
              @keyup="handlePetCtrlKeyup($event)"
              @input="handlePetInput(pet, $event)"
              @pointerdown.stop="onInputPointerDown(pet)"
            />
            <button class="lobby-pet-complete" @click="completePet(pet)" title="Done (send empty message)">Done</button>
            <button class="lobby-pet-send" @click="submitPet(pet)" title="Send (Enter)">➤</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Right clickMenu：Pet（ right Current Agent's Action）/ Node（NodeAction） -->
    <div
      v-if="contextMenu.visible"
      class="lobby-context-menu"
      :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
      @pointerdown.stop
      @click.stop
      @contextmenu.prevent.stop
    >
      <div class="lobby-context-title">{{ contextMenu.name }}</div>
      <div class="lobby-context-items">
        <button
          v-for="act in contextMenuActions"
          :key="act.id"
          class="lobby-context-item"
          :disabled="act.enabled === false"
          @click="onContextAction(act)"
        >
          <span class="lobby-context-icon" v-html="act.icon"></span>
          <span class="lobby-context-label">{{ act.label }}</span>
        </button>
      </div>
    </div>

    <!-- NodeRename popup：OK back Sync to Settings middle's NodeNameMap -->
    <div
      v-if="renameDialog.visible"
      class="lobby-rename-mask"
      @pointerdown.stop
      @click.stop="closeRenameDialog"
    >
      <div class="lobby-rename-dialog" @click.stop>
        <div class="lobby-rename-title">RenameNode</div>
        <div class="lobby-rename-sub">{{ renameDialog.nodeId }}</div>
        <input
          ref="renameInputRef"
          class="lobby-rename-input"
          type="text"
          placeholder="InputShowName（leave EmptyRestore for Node ID）"
          v-model="renameDialog.value"
          @keydown.enter.prevent="confirmRename"
          @keydown.esc.prevent="closeRenameDialog"
        />
        <div class="lobby-rename-actions">
          <button class="lobby-rename-btn cancel" @click="closeRenameDialog">Cancel</button>
          <button class="lobby-rename-btn ok" @click="confirmRename">OK</button>
        </div>
      </div>
    </div>

    <!-- Pet「Add to group」popup：SelectAlreadyHasGrouporNewGroup -->
    <div
      v-if="groupDialog.visible"
      class="lobby-rename-mask"
      @pointerdown.stop
      @click.stop="closeGroupDialog"
    >
      <div class="lobby-rename-dialog" @click.stop>
        <div class="lobby-rename-title">Add to group</div>
        <div class="lobby-rename-sub">{{ groupDialog.agentName }}</div>
        <div class="lobby-group-list">
          <button
            v-for="g in agentGroups"
            :key="g.id"
            class="lobby-group-item"
            @click="pickGroup(g.id)"
          >
            <span class="lobby-group-name">{{ g.name }}</span>
            <span class="lobby-group-count">{{ (g.agentIds || []).length }}</span>
          </button>
          <div v-if="agentGroups.length === 0" class="lobby-group-empty">No groups yet, create one below</div>
        </div>
        <div class="lobby-group-create">
          <input
            class="lobby-rename-input"
            type="text"
            placeholder="New group name"
            v-model="groupDialog.newGroupName"
            @keydown.enter.prevent="createGroupAndAdd"
            @keydown.esc.prevent="closeGroupDialog"
          />
          <button
            class="lobby-rename-btn ok"
            :disabled="!String(groupDialog.newGroupName || '').trim()"
            @click="createGroupAndAdd"
          >Create and add</button>
        </div>
      </div>
    </div>

    <!-- Pet「Remove from group」popup：Col out the/this Agent that is in/atGroup，Click to Remove -->
    <div
      v-if="removeGroupDialog.visible"
      class="lobby-rename-mask"
      @pointerdown.stop
      @click.stop="closeRemoveGroupDialog"
    >
      <div class="lobby-rename-dialog" @click.stop>
        <div class="lobby-rename-title">Remove from group</div>
        <div class="lobby-rename-sub">{{ removeGroupDialog.agentName }}</div>
        <div class="lobby-group-list">
          <button
            v-for="g in removeGroupOptions"
            :key="g.id"
            class="lobby-group-item"
            @click="pickRemoveGroup(g.id)"
          >
            <span class="lobby-group-name">{{ g.name }}</span>
            <span class="lobby-group-count">Remove</span>
          </button>
          <div v-if="removeGroupOptions.length === 0" class="lobby-group-empty">This Agent is not in any group</div>
        </div>
      </div>
    </div>

    <!-- Install browser extension popup：InstallDescription + Download extension packageButton -->
    <div
      v-if="installDialog.visible"
      class="lobby-rename-mask"
      @pointerdown.stop
      @click.stop="closeInstallDialog"
    >
      <div class="lobby-install-dialog" @click.stop>
        <div class="lobby-rename-title">Install browser extension</div>
        <div class="lobby-rename-sub">HaijunBot Browser Bridge ·  let  Agent Action with your True real Browser middle the web page</div>
        <div class="lobby-install-steps">
          <div class="lobby-install-step">
            <span class="lobby-install-step-no">1</span>
            <span class="lobby-install-step-text">Click down below「Download extension package」，must  to  zip CompressPkg and Extract to LocalDirectory。</span>
          </div>
          <div class="lobby-install-step">
            <span class="lobby-install-step-no">2</span>
            <span class="lobby-install-step-text">Open Chrome/Edge，visit <code>chrome://extensions</code>，Enable right  up corner「Dev eloper Mode」。</span>
          </div>
          <div class="lobby-install-step">
            <span class="lobby-install-step-no">3</span>
            <span class="lobby-install-step-text">Click「LoadAlreadyExtract the ExtensionProg」，Select just now Extract out  come the Directory。</span>
          </div>
          <div class="lobby-install-step">
            <span class="lobby-install-step-no">4</span>
            <span class="lobby-install-step-text">in/atBrowser middle Login HaijunBot web page（Extension willAuto reuse Login state，NoNeed manually fill in Token）。</span>
          </div>
          <div class="lobby-install-step">
            <span class="lobby-install-step-no">5</span>
            <span class="lobby-install-step-text">ClickToolbarExtensionIcon，in/at「AddGatewayAddress」 middle fill in GatewayAddress（e.g. this pageAddress）and Connect。</span>
          </div>
        </div>
        <div v-if="installDialog.error" class="lobby-install-error">{{ installDialog.error }}</div>

        <div v-if="extensionVersion.outdated" class="lobby-install-update">
          <span class="lobby-install-update-icon">⬆</span>
          <span>DetectedExtension has new version（Current {{ localExtensionVersion }} → latest {{ extensionVersion.latest }}), please download again and reload extension.</span>
        </div>
        <div v-else-if="extensionVersion.latest" class="lobby-install-version">
          <span v-if="localExtensionVersion">Current extension version {{ localExtensionVersion }} · Latest version {{ extensionVersion.latest }}</span>
          <span v-else>Latest extension version {{ extensionVersion.latest }}(no locally installed extension detected yet)</span>
        </div>

        <!-- risk TipandDisclaimer：This extension requestsHeight sensitive Permissions，Download front  must  must  let User clearly informed -->
        <div class="lobby-install-risk">
          <div class="lobby-install-risk-head">
            <span class="lobby-install-risk-icon">⚠</span>
            <span>High risk warning · Please read carefully before downloading</span>
          </div>
          <div class="lobby-install-risk-body">
            <p>
              This extension requests <strong>28 itemsBrowserPermissions</strong>，of which middle  <strong>8 highly sensitive permissions</strong>：
              <code>cookies</code>、<code>webRequest</code>、<code>management</code>、<code>nativeMessaging</code>、
              <code>proxy</code>、<code>privacy</code>、<code>browsingData</code>、<code>contentSettings</code>。
            </p>
            <p>
              Install back ，Agent Will gain must <strong> right your Browser's complete Actioncan capability</strong>：Can just like yourself ActionAnyAlreadyLogin web page
              （Click、Input、Upload、capture Graph、execute RowScript），read and rewrite NetStream traffic，ManageExtensionand site Permissions，
              and access Bookmark、History、Download、Cookie、Password etc.<strong>Allbrowser data</strong>。
            </p>
            <p>Specifically，Connect to this Gateway's Agent Will <strong>possess the following down can capabilities</strong>：</p>
            <ul>
              <li>Read、Modify、Delete your <strong>Cookie（including Login credentials）</strong> in/at various websites，equivalent to<strong>connect/join managing your AllLogin state</strong>；</li>
              <li>Read and rewrite your<strong>AllNetReq</strong>（Can block or redirect to），Can inject in 、tamper with Any web pageContent；</li>
              <li>View、Enable、Disable even <strong>Uninstall the OtherExtension that you Install</strong>；</li>
              <li>and<strong>local applications</strong> communicate，and<strong>modify system proxy settings</strong>（affect AllNetStream traffic）；</li>
              <li>Modify privacy Switch，as well as <strong>clear browsing History、Cache、Cookie、saved Password</strong>；</li>
              <li>Modify site-level Permissions（camera、microphone、geographic Position、Modal etc.），Can <strong>silently Enable camera/microphone Authorization</strong>；</li>
              <li>in/atPage main world execute RowAny JS，<strong>bypass Page CSP and same origin Strategy</strong> read Page inner Data。</li>
            </ul>
            <p class="lobby-install-risk-warn">
               up mentioned can capabilities combined back ，equivalent same at/on<strong>「your Browser（including AllAccountandData）completely hand over to Agent」</strong>。
              of which middle  <strong>clear browsing data、uninstall extensions、delete cookies</strong> such Action<strong>Not Can be undone</strong>，once executed Rowcannot be recovered。
            </p>
            <p>
              <strong>Disclaimer：</strong>This Extension is provided on an「as-is」basis，only for use at/on your own AuthorizationRange inner BrowserAuto automation。
              Please only in/at your <strong>fully trust</strong> connected Gatewayand Agent，as provided down use。
               because Authorization、erroneous Actionor third-party abuse caused Account leak、funds loss、Data loss、Config corruption bad etc. back consequences，
               by user bear the consequences，this Project and authorassume no liability。
              If Not connect/join accept up mentioned risks，Please<strong>NowClose this Modal，do not download or install</strong>。
            </p>
          </div>
        </div>

        <div class="lobby-rename-actions">
          <button class="lobby-rename-btn cancel" @click="closeInstallDialog">Close</button>
          <button
            class="lobby-rename-btn ok"
            :disabled="installDialog.downloading"
            @click="downloadExtension()"
          >{{ installDialog.downloading ? 'Downloading...' : 'Download extension package' }}</button>
        </div>
      </div>
    </div>

    <!-- Install local daemon service（daemon）popup：InstallDescription + DownloadLink + risk Tip -->
    <div
      v-if="daemonDialog.visible"
      class="lobby-rename-mask"
      @pointerdown.stop
      @click.stop="closeDaemonDialog"
    >
      <div class="lobby-install-dialog" @click.stop>
        <div class="lobby-rename-title">Install local daemon service</div>
        <div class="lobby-rename-sub">HaijunBot Daemon ·  let  Agent directly connect/joinAction your this computer（Script / File / SystemService / desktop GUI）</div>
        <div class="lobby-install-steps">
          <div class="lobby-install-step">
            <span class="lobby-install-step-no">1</span>
            <span class="lobby-install-step-text">
              OpenDownloadpage
              <code>https://github.com/takebox/HaijunBot/releases</code>
              （or Click down below Button），in/at latest New Release's Assets  middle according to your System Select right  should File：
            </span>
          </div>
          <div class="lobby-install-step">
            <span class="lobby-install-step-no">2</span>
            <span class="lobby-install-step-text">
              Download and Extract right  should Platform's CompressPkg：Windows 64-bit <code>haijunbot-daemon_windows_amd64.zip</code>、
              Windows ARM64 <code>haijunbot-daemon_windows_arm64.zip</code>；
              Linux x86_64 <code>haijunbot-daemon_linux_amd64.tar.gz</code>、
              Linux ARM64 <code>haijunbot-daemon_linux_arm64.tar.gz</code>。
            </span>
          </div>
          <div class="lobby-install-step">
            <span class="lobby-install-step-no">3</span>
            <span class="lobby-install-step-text">
              <strong>Windows</strong>：in/atExtractDirectoryOpen PowerShell，run Row <code>.\haijunbot-daemon.exe install</code>，
              Then run Row <code>.\haijunbot-daemon.exe start</code>（willRegister for Login auto start the ScheduleTasks）。
            </span>
          </div>
          <div class="lobby-install-step">
            <span class="lobby-install-step-no">4</span>
            <span class="lobby-install-step-text">
              <strong>Linux</strong>：Extract back run Row <code>chmod +x haijunbot-daemon</code>，then back run Row
              <code>./haijunbot-daemon install</code>，then run Row <code>./haijunbot-daemon start</code>
              （willRegister for  <code>systemctl --user</code> UserService and Launch at startup）。
            </span>
          </div>
          <div class="lobby-install-step">
            <span class="lobby-install-step-no">5</span>
            <span class="lobby-install-step-text">
              Install back  daemon willin/at local <code>127.0.0.1:17800</code> listen，and Auto connect back this Gateway；
              Can in/at「Settings → local Daemon servicePort」 middle Modify front endConnectPort。
              its It Command：<code>status</code> ViewStatus、<code>stop</code> Stopped、<code>uninstall</code> Uninstall。
            </span>
          </div>
        </div>

        <!-- risk TipandDisclaimer：daemon Yes local resident Proc，Permissions far Heightat/onBrowser extension -->
        <div class="lobby-install-risk">
          <div class="lobby-install-risk-head">
            <span class="lobby-install-risk-icon">⚠</span>
            <span>High risk warning · Please read carefully before installing</span>
          </div>
          <div class="lobby-install-risk-body">
            <p>
              Local daemon service（daemon）Yes a items<strong>resident in/at your computer up the BackendProc</strong>，It will expose local can capabilities to Connect to this Gateway's Agent。
              Install and Start back ，Agent Will <strong>directly connect/join as your User identity Actionthis computer</strong>。
            </p>
            <p>Specifically，Connect to this Gateway's Agent Will <strong>possess the following down can capabilities</strong>：</p>
            <ul>
              <li>run Row<strong>AnyLocalScriptandCommand</strong>（including SystemCommand、PkgManage manager、BuildScript etc.）；</li>
              <li><strong>Read、write in 、Delete your local AnyFile</strong>（CurrentVersionNoPath sandbox Limit）；</li>
              <li>View、Start、Stopped、restart your<strong>SystemService</strong>（Linux  for User-level systemd Service）；</li>
              <li>Enumerate and End local<strong>AnyProc</strong>；</li>
              <li>Control your<strong>desktop GUI</strong>：Col out /Focus/CloseWindow，simulate mouse ClickandKey board Input，RWSystem clipboard，capture screen image；</li>
              <li>Read local<strong>SystemInfo</strong>（Hostname、User、hardware andRunningEnvironment etc.）。</li>
            </ul>
            <p class="lobby-install-risk-warn">
               up mentioned can capabilities combined back ，equivalent same at/on<strong>「your this computer's Control rights completely hand over to Agent」</strong>。
              of which middle <strong>DeleteFile、EndProc、StoppedService</strong> such Action<strong>Not Can be undone</strong>，once executed Rowcannot be recovered；
              Clipboard and screen Content also mayPkg contain<strong>Password、Verify code、private Info</strong>。
            </p>
            <p>
              <strong>Disclaimer：</strong>This Prog is provided on an「as-is」basis，only for use at/on your own AuthorizationRange inner local Auto automation。
              Please only in/at your <strong>fully trust</strong> connected Gatewayand Agent，as provided down Installuse。
               because Authorization、erroneous Actionor third-party abuse caused Account leak、funds loss、Data loss、System corruption bad etc. back consequences，
               by user bear the consequences，this Project and authorassume no liability。
              If Not connect/join accept up mentioned risks，Please<strong>NowClose this Modal，do not download or install</strong>。
            </p>
          </div>
        </div>

        <div class="lobby-rename-actions">
          <button class="lobby-rename-btn cancel" @click="closeDaemonDialog">Close</button>
          <a
            class="lobby-rename-btn ok"
            href="https://github.com/takebox/HaijunBot/releases"
            target="_blank"
            rel="noopener noreferrer"
          >Go to download page</a>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { normalizeNodeStatus, normalizeAgentStatus, formatBrowserLabel } from './topology.js'
import { exportElementAsImage } from '../utils/exportImage.js'

const props = defineProps({
  agents: { type: Array, default: () => [] },
  agentsLoaded: { type: Boolean, default: false },
  nodes: { type: Array, default: () => [] },
  getStatusClass: { type: Function, default: null },
  getInputState: { type: Function, default: null },
  getLatestOutput: { type: Function, default: null },
  historyNav: { type: Function, default: null },
  getNodeDisplayName: { type: Function, default: null },
  // Working Directory display：by parent Component injected in to reuse「Hide working Directory」Pref（EnablehourBackPlaceholder）
  getWorkingDirDisplay: { type: Function, default: null },
  // Right clickMenu actions（reuse CommandPanel「Current Agent」group），by parent Component based on Current Agent Calculate back passed in 
  contextActions: { type: Array, default: () => [] },
  // NodeRight clickMenu actions，by parent Component passed in（for at/on back future ExtensionMoreNodeFeature）
  nodeActions: { type: Array, default: () => [] },
  // Current Has Agent GroupList（used at/onPetRight click「Add to group」）
  agentGroups: { type: Array, default: () => [] },
  // GatewayAddress（host:port），used at/on left  up corner instrument Table display
  gatewayAddress: { type: String, default: '' },
  // ConnectStatusand labels（online/connecting/reconnecting/offline +  middle Chinese Tags）
  connectionStatus: { type: String, default: '' },
  connectionLabel: { type: String, default: '' },
  // CurrentLoginUser name（prefer Show name）
  currentUserName: { type: String, default: '' },
  // DownloadBrowser extensionPkg（AsyncFunction，Back { filename, blob }），by parent Component injected in to reuse authentication andGatewayAddress
  downloadExtension: { type: Function, default: null },
  // QueryExtensionVersion（AsyncFunction，Back { latestVersion, sessions }），used at/on detect ExtensionUpdate
  checkExtensionVersion: { type: Function, default: null },
  // QueryDaemon service（daemon）Session（AsyncFunction，BackSessionArray），used at/on topology Graph display connect/join in the daemon Node
  checkDaemonSessions: { type: Function, default: null },
  // QueryBrowser extensionSession（AsyncFunction，BackSessionArray），used at/on topology Graph display connect/join in the ExtensionNode
  checkExtensionSessions: { type: Function, default: null },
  // local YesNoAlreadyInstall and RunningDaemon service（daemon）：by parent Component probe local loopback /api/status  back passed in，
  //  for  true hourHide「Install local daemon service」Button（popup still Can via CommandPanelOpen）
  localDaemonOnline: { type: Boolean, default: false },
})

const emit = defineEmits(['selectAgent', 'sendInput', 'complete', 'openCompletions', 'activePetChange', 'activeNodeChange', 'createAgentOnNode', 'contextAgent', 'contextRun', 'nodeContextRun', 'renameNode', 'addAgentToGroup', 'removeAgentFromGroup', 'openOnboarding'])

// Pet size Constant（and CSS  middle .lobby-pet WidthHeight stay consistent）
const PET_W = 72
const PET_H = 82
const PET_SPEED = 0.55 // pixels/frame，about 33px/Sec
const MIN_DIST = 96 // Pet's between MinSpacing，used at/on repulsion to avoid let 
const EDGE_PAD = 12
const PANEL_H = 150 // Interactive PanelHeight（approximate Value，used at/onJudgePanel facing up /facing down ）
const STACK_GAP = 4 // stack ContainerandPet body's Spacing（and CSS the calc(100% + 4px) consistent）
// Node chassis half Height：master slightly big（and nodeItems  middle of rw/rh stay consistent）
const MASTER_RH = 33
const NODE_RH = 26

// custom-drawn 16x16 stroke linear SVG Icon（currentColor inherits Theme color），used at/onReplace A ClassFeature styled emoji
const PET_ICONS = {
  roam: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="2.8" r="1.5"/><path d="M8 4.3 6.6 9.2"/><path d="M8 5.2 9.8 6.8"/><path d="M6.6 9.2 4.6 12.8"/><path d="M6.6 9.2 9 10.2"/></svg>',
  stand: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="2.8" r="1.5"/><path d="M8 4.3V9"/><path d="M8 5.5 6 7"/><path d="M8 5.5 10 7"/><path d="M8 9 6 12.5"/><path d="M8 9 10 12.5"/></svg>',
  pause: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="3" width="2.6" height="10" rx="1"/><rect x="9.4" y="3" width="2.6" height="10" rx="1"/></svg>',
  eye: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1.5 8s2.5-4 6.5-4 6.5 4 6.5 4-2.5 4-6.5 4S1.5 8 1.5 8Z"/><circle cx="8" cy="8" r="1.8"/></svg>',
  eyeOff: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 3l10 10"/><path d="M6.2 5.3A6.5 6.5 0 0 1 8 5c4 0 6.5 3 6.5 3a8.7 8.7 0 0 1-1.5 1.8M9.9 10.8A5.4 5.4 0 0 1 8 11c-4 0-6.5-3-6.5-3a8.7 8.7 0 0 1 2.6-2.5"/></svg>',
  chat: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.5 3h11v7h-7L3.5 13v-3h-1z"/></svg>',
  ban: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6"/><path d="M4 4l8 8"/></svg>',
  puzzle: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3.5A1.5 1.5 0 0 1 9 3.5V4h1.5A1.5 1.5 0 0 1 12 5.5V7h.5a1.5 1.5 0 0 1 0 3H12v1.5A1.5 1.5 0 0 1 10.5 13H9v.5a1.5 1.5 0 0 1-3 0V13H4.5A1.5 1.5 0 0 1 3 11.5V10h-.5a1.5 1.5 0 0 1 0-3H3V5.5A1.5 1.5 0 0 1 4.5 4H6z"/></svg>',
  monitor: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="3" width="12" height="8" rx="1.5"/><path d="M5.5 13.5h5M8 11v2.5"/></svg>',
  image: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2.5" y="3" width="11" height="10" rx="1.5"/><circle cx="5.5" cy="6" r="1"/><path d="M3.5 12.5l3.5-3.5 2.5 2.5 2-2 1 1"/></svg>',
  terminal: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="3" width="12" height="10" rx="1.5"/><path d="M5 6.5 7 8l-2 1.5M9 10h2.5"/></svg>',
  refresh: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9"/><path d="M13.5 2.5v3h-3"/></svg>',
  restart: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 2.5A5.5 5.5 0 1 0 13.5 8"/><path d="M13.5 2.5v3h-3"/><path d="M8 8.5l2-2"/></svg>',
  edit: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11.5 2.5a1.8 1.8 0 0 1 2.5 2.5L6 13l-3.5 1L3.5 10.5z"/></svg>',
  folder: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 4.5A1.5 1.5 0 0 1 3.5 3h3l1.5 2H12.5A1.5 1.5 0 0 1 14 6.5v5A1.5 1.5 0 0 1 12.5 13h-9A1.5 1.5 0 0 1 2 11.5z"/></svg>',
  folderOpen: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 4.5A1.5 1.5 0 0 1 3.5 3h3l1.5 2H12.5A1.5 1.5 0 0 1 14 6.5v.5H3.5L2 12z"/><path d="M2.5 12.5 4 8.5h9.5l-1 4z"/></svg>',
}

const stageRef = ref(null)
const stageSize = ref({ w: 0, h: 0 })
const petAgents = ref([])
const activePetId = ref(null)
// Selected the Node id：NodeAction（Create Agent / Open terminal / Update code / Restart service）based on This acts at/on the/thisNode
const activeNodeId = ref(null)
// YesNoallowPet self by Roam：persist to  localStorage（DefaultEnable）
const ROAMING_KEY = 'haijunbot.petLobby.roaming'
function loadRoaming() {
  try {
    return localStorage.getItem(ROAMING_KEY) !== '0'
  } catch (e) {
    /* localStorage Not Available hour falls back to DefaultValue */
  }
  return true
}
const roaming = ref(loadRoaming())
watch(roaming, (on) => {
  try {
    localStorage.setItem(ROAMING_KEY, on ? '1' : '0')
  } catch (e) {
    /* Ignore write in Failed（privacy Mode etc.） */
  }
})

// PetPosition persistence：by agentId Record { x, y }
//  big hall Component in/atOpen/Close Panel hourwill be recreated by v-if Uninstall（App.vue's hasNoPanel），
// If No persistence，after rebuild back every Pet will all re-NewRand pick position，causing Position jumps。
const POSITIONS_KEY = 'haijunbot.petLobby.positions'
function loadPositions() {
  try {
    const raw = localStorage.getItem(POSITIONS_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    const result = {}
    for (const [agentId, pos] of Object.entries(parsed)) {
      if (!pos || typeof pos !== 'object') continue
      const x = Number(pos.x)
      const y = Number(pos.y)
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue
      result[agentId] = { x, y }
    }
    return result
  } catch (e) {
    /* localStorage Not AvailableorData corruption bad hour falls back  for Empty */
  }
  return {}
}
const petPositions = loadPositions()
// Position only in/atComponentUninstallhour（i.e. leaving open  big hall、by App.vue's v-if Uninstall）uniformly persisted to disk once：
// Roam process middle every frame all in/atMove，per-frame orCron write localStorage all YesNot  must want the Disk open overhead。
function savePositions() {
  try {
    localStorage.setItem(POSITIONS_KEY, JSON.stringify(petPositions))
  } catch (e) {
    /* Ignore write in Failed（privacy Mode etc.） */
  }
}
function rememberPosition(pet) {
  if (!pet || !pet.agentId) return
  petPositions[pet.agentId] = { x: pet.x, y: pet.y }
}
// clean up AlreadyDoes not exist Agent's PositionRecord，avoid localStorage No-limit growth long 
function prunePositions(validIds) {
  for (const agentId of Object.keys(petPositions)) {
    if (!validIds.has(agentId)) delete petPositions[agentId]
  }
}

// MoveendJudge：and CSS breakpoints（max-width: 768px）stay consistent，used at/on based on Need ShowMoveend dedicated Control
const MOBILE_BREAKPOINT = 768
const isMobile = ref(typeof window !== 'undefined' && window.innerWidth <= MOBILE_BREAKPOINT)
function updateIsMobile() {
  isMobile.value = window.innerWidth <= MOBILE_BREAKPOINT
  // connect/join in endLayout adapts to screen orientation toResp style：Width>Height（PC）hour left  right two Col、Height>Width（Move）hour up  down two Row
  isPortrait.value = window.innerHeight > window.innerWidth
}
// screen YesNo for portrait to（Height>Width）：true hour connect/join in end up  down two Row，false（PC Width>Height）hour left  right two Col
const isPortrait = ref(typeof window !== 'undefined' && window.innerHeight > window.innerWidth)

// SpriteShow：petsHidden=YesNoHideAllSprite，persist to  localStorage
// Output show/hide completely by single items Agent's hiddenOutputIds Control（Not longer HasGlobalOutputSwitch）
const DISPLAY_MODE_KEY = 'haijunbot.petLobby.displayMode'
function loadPetsHidden() {
  try {
    // compatible withOld version three states：all / no-output / hidden
    return localStorage.getItem(DISPLAY_MODE_KEY) === 'hidden'
  } catch (e) {
    /* localStorage Not Available hour falls back to DefaultValue */
  }
  return false
}
const petsHidden = ref(loadPetsHidden())
const showPets = computed(() => !petsHidden.value)
watch(petsHidden, (hidden) => {
  try {
    localStorage.setItem(DISPLAY_MODE_KEY, hidden ? 'hidden' : 'all')
  } catch (e) {
    /* Ignore write in Failed（privacy Mode etc.） */
  }
})
// Show / Hide Agent Sprite：Switch all Has Agent Sprite's ShowandHide
function toggleAllPets() {
  petsHidden.value = !petsHidden.value
}
// Whether all Has Agent's Output all AlreadyHide：used at/on「AllOutput show/hide」Button's label and Icon
// NoPethour treated for NotHide，ButtonShow「Hide all outputs」
const allOutputsHidden = computed(() => {
  const pets = petAgents.value
  if (!pets.length) return false
  return pets.every(p => hiddenOutputIds.value.has(p.agentId))
})
// AllOutput show/hide：AlreadyAllHidethenAllShow，NothenAllHide
function toggleAllOutputs() {
  if (allOutputsHidden.value) {
    if (hiddenOutputIds.value.size) {
      hiddenOutputIds.value = new Set()
      saveHiddenOutputs()
    }
  } else {
    hiddenOutputIds.value = new Set(petAgents.value.map(p => p.agentId))
    saveHiddenOutputs()
  }
}

// single items Agent's Output show/hide：IndependentControl and persisted
const HIDDEN_OUTPUTS_KEY = 'haijunbot.petLobby.hiddenOutputs'
function loadHiddenOutputs() {
  try {
    const raw = localStorage.getItem(HIDDEN_OUTPUTS_KEY)
    const arr = raw ? JSON.parse(raw) : []
    if (Array.isArray(arr)) return new Set(arr.filter(id => typeof id === 'string'))
  } catch (e) {
    /* localStorage Not AvailableorData corruption bad hour falls back Empty set */
  }
  return new Set()
}
const hiddenOutputIds = ref(loadHiddenOutputs())
// previously out appeared the agentId：used at/onJudge which persisted items right  should the Agent Already been Delete
const seenAgentIds = new Set()
function saveHiddenOutputs() {
  try {
    localStorage.setItem(HIDDEN_OUTPUTS_KEY, JSON.stringify([...hiddenOutputIds.value]))
  } catch (e) {
    /* Ignore write in Failed（privacy Mode etc.） */
  }
}
// a certain Agent's OutputYesNo is IndividualHide
function isOutputHidden(agentId) {
  return hiddenOutputIds.value.has(agentId)
}
// Switch a certain Agent's Output show/hide（for CommandPanel/Right clickMenu calls）
function toggleAgentOutput(agentId) {
  if (!agentId) return
  const next = new Set(hiddenOutputIds.value)
  if (next.has(agentId)) next.delete(agentId)
  else next.add(agentId)
  hiddenOutputIds.value = next
  saveHiddenOutputs()
}

let rafId = null
let resizeObserver = null

// ===== Nodeand connecting lines（reference big screen「Net topology」style）=====
// NodeStatus color scheme（and big screen TopologyOverlay stay consistent）
const NODE_COLORS = { online: '#34d99b', offline: '#ff5d6c', unknown: '#8a9bb0' }
const AGENT_COLORS = { running: '#20c8ff', waiting: '#ffb347', idle: '#8a9bb0', stopped: '#ff5d6c' }

function nodeColor(state) {
  if (state === 'online') return NODE_COLORS.online
  if (state === 'offline') return NODE_COLORS.offline
  return NODE_COLORS.unknown
}
function agentColor(state) {
  return AGENT_COLORS[state] || AGENT_COLORS.idle
}

// Nodein/at big hall middle's coordinates：master Center，the rest Node evenly min distributed in/at circle Week up 
// circle Week radius down limit：ensure circle Week up the Node chassis Not and master chassis same touching/overlapping——Nothen「 pos  up direction」
// thatitems master→Node connecting lines will entire segment be covered by two items chassis，looks start come like not drawn（the rest directions toHas diagonal toEmpty blank segment still Visible）。
const nodeLayout = computed(() => {
  const list = Array.isArray(props.nodes) ? props.nodes : []
  const w = stageSize.value.w
  const h = stageSize.value.h
  const cx = w / 2
  const cy = h / 2
  // circle Week radius: adapts should to stage size, leaving out Margin; same hour Not Lt "master half Height + Node half Height + between gap"
  const minRadius = MASTER_RH + NODE_RH + 14
  const radius = Math.max(Math.min(w, h) * 0.32, 120, minRadius)
  const result = new Map()
  const master = list.find(n => n && n.node_id === 'master')
  if (master) {
    result.set('master', { node_id: 'master', x: cx, y: cy })
  }
  const others = list.filter(n => n && n.node_id && n.node_id !== 'master')
  const count = others.length
  others.forEach((n, i) => {
    //  from  pos  up side Start, clockwise evenly distribute
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / Math.max(count, 1)
    result.set(n.node_id, {
      node_id: n.node_id,
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
    })
  })
  return result
})

// NodeList (with coordinates, Status, color scheme, chassis size), for Template rendering
const nodeItems = computed(() => {
  const list = Array.isArray(props.nodes) ? props.nodes : []
  const agentList = Array.isArray(props.agents) ? props.agents : []
  // master Version as for baseline: Nodes not consistent with it are regarded as Not Update, Need Height bright Tip
  const masterVersion = (() => {
    const master = list.find(n => n && n.node_id === 'master')
    return master && master.version ? String(master.version) : ''
  })()
  return list
    .filter(n => n && n.node_id && nodeLayout.value.has(n.node_id))
    .map(n => {
      const pos = nodeLayout.value.get(n.node_id)
      const state = normalizeNodeStatus(n.status)
      const isMaster = n.node_id === 'master'
      const color = isMaster && state !== 'offline' && state !== 'unknown'
        ? '#ffd75e'
        : nodeColor(state)
      const name = props.getNodeDisplayName
        ? props.getNodeDisplayName(n.node_id)
        : (isMaster ? 'master' : n.node_id)
      const short = (() => {
        const s = String(name || '')
        if (s === 'master') return 'master'
        return s.length > 10 ? s.slice(0, 9) + '…' : s
      })()
      // the/thisNode up 's agent count (Not including AlreadyStopped)
      const agentCount = agentList.filter(a => {
        const nid = String(a?.node_id || '').trim() || 'master'
        return nid === n.node_id && a.status !== 'stopped'
      }).length
      // chassis size: master slightly big 
      const rw = isMaster ? 38 : 30
      const rh = isMaster ? MASTER_RH : NODE_RH
      // NodeVersion: child by heartbeat reports up, master by Gateway supplements; when missing leave Empty Not Show
      const version = n.version ? String(n.version) : ''
      // and master Version Not consistent (and both parties have Version) when Height bright, Tip the/thisNode Not Update
      const versionMismatch = !!version && !!masterVersion && version !== masterVersion
      return {
        node_id: n.node_id,
        x: pos.x,
        y: pos.y,
        state,
        color,
        isMaster,
        short,
        agentCount,
        version,
        versionMismatch,
        rw,
        rh,
        active: activeNodeId.value === n.node_id,
        fill: state === 'offline'
          ? 'rgba(255,93,108,0.10)'
          : (isMaster ? 'url(#lobby-center-fill)' : 'rgba(8,18,30,0.7)'),
      }
    })
})

// NodeOnlineStats: state by normalizeNodeStatus normalized to online/offline/unknown
const nodeOnlineStat = computed(() => {
  const list = nodeItems.value
  const online = list.filter(n => n.state === 'online').length
  return { online, total: list.length }
})
// Agent StatusStats: according to normalizeAgentStatus normalized to running/waiting/idle/stopped Count
// Note: Stats must base at/on props.agents full set (petAgents Already Filtered out stopped Agent)
const AGENT_STAT_ORDER = ['running', 'waiting', 'idle', 'stopped']
const AGENT_STAT_LABEL = { running: 'Running', waiting: 'Waiting', idle: 'Idle', stopped: 'Stopped' }
const agentStatusStat = computed(() => {
  const counts = { running: 0, waiting: 0, idle: 0, stopped: 0 }
  for (const agent of (props.agents || [])) {
    const state = normalizeAgentStatus(props.getStatusClass ? props.getStatusClass(agent) : '')
    if (counts[state] !== undefined) counts[state] += 1
  }
  return AGENT_STAT_ORDER
    .filter(state => counts[state] > 0)
    .map(state => ({ state, label: AGENT_STAT_LABEL[state], count: counts[state], color: agentColor(state) }))
})
// Node between connection line: master → the rest Nodes
const nodeLinks = computed(() => {
  const links = []
  const master = nodeLayout.value.get('master')
  if (!master) return links
  const stateById = new Map(nodeItems.value.map(n => [n.node_id, n.state]))
  for (const [id, pos] of nodeLayout.value) {
    if (id === 'master') continue
    links.push({
      key: `node-${id}`,
      x1: master.x,
      y1: master.y,
      x2: pos.x,
      y2: pos.y,
      offline: stateById.get(id) === 'offline',
    })
  }
  return links
})

// ===== connect/join in endNode：Browser extension（ up Row） / Local daemon service（ down Row） =====
// the two Not belong at/on GatewayNode (availableNodeOptions), but Yes "connect/join in this Gateway's client end":
// - Browser extension: Gateway /api/browser-ext/sessions returned OnlineExtensionSession (may more devices / more Browser instances);
// - Local daemon service (daemon): Gateway /api/daemon/sessions returned Online daemon Session (may more machines).
// Name takes the name inside Session (UserConfig's Terminal name, daemon defaults back to hostname), All come from Gateway,
//  because This shows the "whole items Net connect/join in's" client end, but Not Yes only this local machine.
// Position: distributed on stage up down edges (Extension in/at up, daemon in/at down), each evenly distributed in/at Horizontal direction, connect with straight lines to master chassis.
const LOCAL_NODE_RW = 30
// connect/join end Node radius (circular, slightly Lt sub-Node chassis half Height to leave out Tags Empty between, also convenient at/on closer to canvas edge)
const LOCAL_NODE_RH = NODE_RH * 0.77
// Distance from stage up down edges' Vertical margin (leave enough Empty between, avoid NodeTags text being clipped by stage edge)
const LOCAL_NODE_MARGIN = 56
//  same one Row Horizontal Spacing between more items Nodes (including chassis Width)
const ACCESS_NODE_GAP = LOCAL_NODE_RH * 2 + 26

// single Row Node's horizontal to coordinate: use master's x for middle center evenly distributed, and Limit in/at stage inner 
function accessRowXs(count, centerX, stageW) {
  if (count <= 0) return []
  const total = (count - 1) * ACCESS_NODE_GAP
  const start = centerX - total / 2
  const minX = LOCAL_NODE_RW + 18
  const maxX = Math.max(minX, stageW - LOCAL_NODE_RW - 18)
  const xs = []
  for (let i = 0; i < count; i++) {
    xs.push(Math.min(Math.max(start + i * ACCESS_NODE_GAP, minX), maxX))
  }
  return xs
}

// single Col Node's vertical to coordinate: use master's y for middle center evenly distributed, and Limit in/at stage inner 
function accessColumnYs(count, centerY, stageH) {
  if (count <= 0) return []
  const total = (count - 1) * ACCESS_NODE_GAP
  const start = centerY - total / 2
  const minY = LOCAL_NODE_RH + 18
  const maxY = Math.max(minY, stageH - LOCAL_NODE_RH - 18)
  const ys = []
  for (let i = 0; i < count; i++) {
    ys.push(Math.min(Math.max(start + i * ACCESS_NODE_GAP, minY), maxY))
  }
  return ys
}

// Session display name: prefer GatewaySession inside's name, when missing fall back by Type 
function accessSessionName(session, fallback) {
  const name = String((session && session.name) || '').trim()
  return name || fallback
}

// Name too long when truncated (chassis bottom Tags Width has limit)
function accessShortName(name) {
  const s = String(name || '')
  if (s.length > 10) return s.slice(0, 9) + '…'
  return s
}

const accessNodes = computed(() => {
  const w = stageSize.value.w
  const h = stageSize.value.h
  if (!w || !h) return []
  const masterPos = nodeLayout.value.get('master')
  if (!masterPos) return []
  // connect/join end placed in/at ring sub-Node's outside (closer to stage edge), avoid and sub-Nodes overlapping:
  // sub-Node Yes Service server chassis, take its chassis half Height (n.rh) as for ring sub-Node's Edge boundary
  const childTop = nodeItems.value.length
    ? Math.min(...nodeItems.value.map(n => n.y - n.rh))
    : masterPos.y
  const childBottom = nodeItems.value.length
    ? Math.max(...nodeItems.value.map(n => n.y + n.rh))
    : masterPos.y
  const childLeft = nodeItems.value.length
    ? Math.min(...nodeItems.value.map(n => n.x - n.rw))
    : masterPos.x
  const childRight = nodeItems.value.length
    ? Math.max(...nodeItems.value.map(n => n.x + n.rw))
    : masterPos.x
  // Layout by screen direction responsive: Width>Height (PC) when left right two Col, Height>Width (Move) when up down two Row
  const portrait = isPortrait.value
  let extPos = []
  let daemonPos = []
  if (portrait) {
    // vertical to (Move): Extension top Row, daemon bottom Row, each evenly distributed Horizontal
    const topY = Math.max(LOCAL_NODE_RH, Math.min(LOCAL_NODE_MARGIN + LOCAL_NODE_RH, childTop - 55))
    const bottomY = Math.min(h - LOCAL_NODE_RH, Math.max(h - LOCAL_NODE_MARGIN - LOCAL_NODE_RH, childBottom + 55))
    const extXs = accessRowXs(extensionSessions.value.length, masterPos.x, w)
    const daemonXs = accessRowXs(daemonSessions.value.length, masterPos.x, w)
    extPos = extXs.map(x => ({ x, y: topY, labelAbove: false, anchor: 'middle' }))
    daemonPos = daemonXs.map(x => ({ x, y: bottomY, labelAbove: true, anchor: 'middle' }))
  } else {
    // horizontal to (PC): Extension left Col, daemon right Col, each evenly distributed Vertical
    const leftX = LOCAL_NODE_MARGIN + LOCAL_NODE_RH
    const rightX = w - LOCAL_NODE_MARGIN - LOCAL_NODE_RH
    const extYs = accessColumnYs(extensionSessions.value.length, masterPos.y, h)
    const daemonYs = accessColumnYs(daemonSessions.value.length, masterPos.y, h)
    extPos = extYs.map(y => ({ x: leftX, y, labelAbove: null, anchor: 'start' }))
    daemonPos = daemonYs.map(y => ({ x: rightX, y, labelAbove: null, anchor: 'end' }))
  }
  const nodes = []
  extensionSessions.value.forEach((s, i) => {
    const name = accessSessionName(s, 'Browser extension')
    // sub Title displays "Browser name main Version · ExtensionVersion", let User distinguish different Browser/device
    const browserLabel = formatBrowserLabel(s && s.browser_info, s && s.extension_version)
    const p = extPos[i] || { x: masterPos.x, y: masterPos.y, labelAbove: false, anchor: 'middle' }
    nodes.push({
      id: `ext-${s.session_id || i}`,
      x: p.x,
      y: p.y,
      state: 'online',
      color: nodeColor('online'),
      fill: 'rgba(8,18,30,0.7)',
      short: accessShortName(name),
      sub: browserLabel || 'Browser extension',
      icon: 'extension',
      labelAbove: p.labelAbove,
      anchor: p.anchor,
      title: `Browser extension · ${name}${browserLabel ? ` · ${browserLabel}` : ''}`,
      masterX: masterPos.x,
      masterY: masterPos.y,
    })
  })
  daemonSessions.value.forEach((s, i) => {
    const name = accessSessionName(s, 'Daemon service')
    const platform = String((s && s.platform) || '').trim()
    const version = String((s && s.daemon_version) || '').trim()
    // daemon reported up Version may come with v front prefix (such as v5.0.5), avoid concatenating into vv5.0.5
    const versionLabel = version ? (/^v/i.test(version) ? version : `v${version}`) : ''
    const detail = [platform, versionLabel].filter(Boolean).join(' · ')
    const p = daemonPos[i] || { x: masterPos.x, y: masterPos.y, labelAbove: true, anchor: 'middle' }
    nodes.push({
      id: `daemon-${s.session_id || i}`,
      x: p.x,
      y: p.y,
      state: 'online',
      color: nodeColor('online'),
      fill: 'rgba(8,18,30,0.7)',
      short: accessShortName(name),
      sub: detail || 'Daemon service',
      icon: 'daemon',
      labelAbove: p.labelAbove,
      anchor: p.anchor,
      title: `Daemon service · ${name}${detail ? ` · ${detail}` : ''}`,
      masterX: masterPos.x,
      masterY: masterPos.y,
    })
  })
  return nodes
})

// straight line connection: master chassis → each connect/join end Node, directly connect two points.
const accessLinks = computed(() =>
  accessNodes.value.map(n => ({
    key: `access-${n.id}`,
    d: `M ${n.masterX} ${n.masterY} L ${n.x} ${n.y}`,
    color: n.color,
    offline: n.state === 'offline',
  })),
)

// connection between Agent and its belonging Node: Pet middle center → Node coordinate (Color takes agent Status color)
const agentLinks = computed(() => {
  const links = []
  // when Sprite Hide Not drawing agent→Node connection
  if (!showPets.value) return links
  for (const pet of petAgents.value) {
    const agent = (props.agents || []).find(a => a.agent_id === pet.agentId)
    const nodeId = String(agent?.node_id || '').trim() || 'master'
    const pos = nodeLayout.value.get(nodeId)
    if (!pos) continue
    const state = normalizeAgentStatus(props.getStatusClass ? props.getStatusClass(agent) : '')
    links.push({
      key: `agent-${pet.agentId}`,
      x1: pet.x + PET_W / 2,
      y1: pet.y + PET_H / 2,
      x2: pos.x,
      y2: pos.y,
      color: agentColor(state),
    })
  }
  return links
})

function randBetween(min, max) {
  return min + Math.random() * (max - min)
}

function clampPos(x, y) {
  const maxX = Math.max(stageSize.value.w - PET_W - EDGE_PAD, EDGE_PAD)
  const maxY = Math.max(stageSize.value.h - PET_H - EDGE_PAD, EDGE_PAD)
  return {
    x: Math.min(Math.max(x, EDGE_PAD), maxX),
    y: Math.min(Math.max(y, EDGE_PAD), maxY),
  }
}

function pickTarget() {
  const maxX = Math.max(stageSize.value.w - PET_W - EDGE_PAD, EDGE_PAD)
  const maxY = Math.max(stageSize.value.h - PET_H - EDGE_PAD, EDGE_PAD)
  return {
    x: randBetween(EDGE_PAD, maxX),
    y: randBetween(EDGE_PAD, maxY),
  }
}

// Copy some Pet's OutputContent (take rendered back plain Text)
async function copyPetOutput(pet) {
  if (!pet || !pet.output) return
  const holder = document.createElement('div')
  holder.innerHTML = pet.output
  const text = (holder.textContent || '').trim()
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
  } catch (err) {
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
      console.error('[PET-COPY] CopyFailed:', fallbackErr)
      return
    }
  }
  pet.copied = true
  if (pet.copyTimer) clearTimeout(pet.copyTimer)
  pet.copyTimer = setTimeout(() => { pet.copied = false }, 1200)
}

// Export some Pet's OutputContent for Image (with Agent name and Time Info items)
async function exportPetOutput(pet) {
  if (!pet || !pet.output || pet.exporting) return
  // use data-pet-output to accurately locate this Pet's Output element, avoid Export to other Pet
  const el = stageRef.value?.querySelector(`[data-pet-output="${CSS.escape(pet.agentId)}"]`)
  if (!el) return
  pet.exporting = true
  try {
    const result = await exportElementAsImage(el, {
      title: pet.name || pet.agentId,
      subtitle: pet.agentType === 'code_agent' ? 'Code Agent' : 'Agent',
      time: new Date().toLocaleString(),
      filename: `haijunbot-${pet.name || pet.agentId}-${Date.now()}`,
    })
    if (!result.ok) {
      console.error('[PET-EXPORT] ExportFailed:', result.error)
      return
    }
    pet.exported = true
    if (pet.exportTimer) clearTimeout(pet.exportTimer)
    pet.exportTimer = setTimeout(() => { pet.exported = false }, 1200)
  } finally {
    pet.exporting = false
  }
}

// Judge whether current focus is allowed to be taken over by Pet Input box:
// If modal Modal is Open, or User is editing other InputControl (input/textarea/contenteditable) when don't grab focus.
function canStealPetFocus() {
  const overlays = document.querySelectorAll('.el-overlay, .modal-overlay, .dialog-overlay, .diff-modal-overlay')
  for (const el of overlays) {
    const style = window.getComputedStyle(el)
    if (style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') return false
  }
  const active = document.activeElement
  if (!active || active === document.body) return true
  const tagName = String(active.tagName || '').toLowerCase()
  if (tagName === 'input' || tagName === 'textarea' || active.isContentEditable) return false
  return true
}

// Focus some Pet's Input box (more Row/single Row auto matched by Current inputMode)
// force=true use at/on explicit Switch focus (such as just Active Pet), Skip "User editing other Input box" Protected
// Input box only renders when in/at pet.active and inputMode !== 'confirm'; Panel Expand/inputMode Switch will replace element,
// single nextTick may appear earlier at/on element, so Retry within several frames until Focus Success.
function focusPetInput(agentId, force = false) {
  if (!agentId) return
  if (!force && !canStealPetFocus()) return
  let attempts = 0
  const tryFocus = () => {
    const el = stageRef.value && stageRef.value.querySelector(`[data-pet-input="${agentId}"]`)
    if (el) {
      if (document.activeElement !== el) el.focus()
      // Already Success Focus (or element Already exists but preempted by other Control) then End Retry
      if (document.activeElement === el) return
    }
    // element still Not rendered (Panel just Expand / inputMode Switch in the middle) when Continue Retry, at most about 10 frames
    if (attempts++ < 10) requestAnimationFrame(tryFocus)
  }
  nextTick(tryFocus)
}

// Pet name displays the working Directory below: reuse parent Component's "Hide working Directory" Pref (when Not noting, restore back original starting Directory)
function petWorkingDir(pet) {
  if (!pet) return ''
  const dir = pet.workingDir || ''
  if (!dir) return ''
  return props.getWorkingDirDisplay ? props.getWorkingDirDisplay(dir) : dir
}

// Refresh some Pet's Input state and latest Output
function refreshPetData(pet) {
  if (!pet) return
  const state = props.getInputState ? props.getInputState(pet.agentId) : null
  if (state) {
    // InputMode changes will Replace Input Control (textarea ↔ input), original focus element is destroyed,
    // Need to return focus back to Input box after render in/at, otherwise when Waiting single Row Input focus is lost
    const modeChanged = pet.inputMode !== state.mode
    pet.inputMode = state.mode
    if (modeChanged && pet.active) focusPetInput(pet.agentId)
    // Whether there is Pending Input Req: when Expand Pet decide according to This whether Auto Focus Input box
    pet.hasInputRequest = !!state.hasRequest
    pet.inputTip = state.tip
    pet.isPassword = state.isPassword
    pet.confirmMessage = state.confirmMessage
    pet.confirmDefault = state.confirmDefault
    // first enter or preset changes when fill Input box
    if (state.preset && !pet.inputText) {
      pet.inputText = state.preset
    }
  }
  const latest = props.getLatestOutput ? props.getLatestOutput(pet.agentId) : null
  const nextOutput = latest ? latest.html : ''
  const outputChanged = nextOutput !== pet.output
  pet.output = nextOutput
  layoutPetStack(pet)
  // Stream type Output: after Content Update if User Not scrolling up, Auto scroll to Bottom
  if (outputChanged && pet.outputAutoScroll) {
    scrollOutputToBottom(pet.agentId)
  }
}

// Output Scroll to Bottom (execute after Waiting DOM Update)
function scrollOutputToBottom(agentId) {
  nextTick(() => {
    const el = stageRef.value && stageRef.value.querySelector(`[data-pet-output="${agentId}"]`)
    if (el) el.scrollTop = el.scrollHeight
  })
}

// User Manual Scroll Output box: when near Bottom Restore Auto Scroll, otherwise Pause (avoid interrupting User View History)
function onOutputScroll(pet, event) {
  const el = event.target
  if (!el) return
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24
  pet.outputAutoScroll = atBottom
}

// Calculate stacked Container (Output/Input/Confirm) Position and size, ensure finally falls in/at stage visible Range inner 
// Horizontal: Align with Pet middle center, and clamp to stage left right Edge boundary inner 
// Vertical: prefer place below, if below Empty between Not enough then place above, and Limit Max Height avoid overflow out 
function layoutPetStack(pet) {
  if (!pet) return
  const w = stageSize.value.w
  const h = stageSize.value.h
  if (!w || !h) return
  // Width and CSS's min(560px, 62vw) Align, and Not exceed out stage Available Width
  const width = Math.max(160, Math.min(560, w * 0.62, w - EDGE_PAD * 2))
  pet.stackWidth = width
  // Horizontal: would like to Center at/on Pet, clamp to [EDGE_PAD, w - width - EDGE_PAD]
  const cx = pet.x + PET_W / 2
  const idealLeft = cx - width / 2
  const clampedLeft = Math.min(Math.max(idealLeft, EDGE_PAD), Math.max(w - width - EDGE_PAD, EDGE_PAD))
  // left Relative Pet left top corner (stack is for absolute, parent Yes Pet)
  pet.stackLeft = clampedLeft - pet.x
  // Vertical: below / above Available Empty between 
  const belowSpace = h - (pet.y + PET_H + STACK_GAP)
  const aboveSpace = pet.y - STACK_GAP
  const useAbove = belowSpace < PANEL_H && aboveSpace > belowSpace
  pet.panelAbove = useAbove
  const avail = Math.max(useAbove ? aboveSpace : belowSpace, 120)
  pet.stackMaxH = Math.min(avail, h - EDGE_PAD * 2)
}

// Based on agents Sync Pet Inst: added are filled in, disappeared are removed, Already Has keep Position
function syncPets() {
  const list = Array.isArray(props.agents) ? props.agents : []
  const existing = new Map(petAgents.value.map(p => [p.agentId, p]))
  const next = []
  for (const agent of list) {
    const agentId = agent.agent_id
    if (!agentId) continue
    // Already Stopped Agent Not Show Pet
    if (agent.status === 'stopped') continue
    let pet = existing.get(agentId)
    if (!pet) {
      // prefer reuse Last Record's Position (when Component is rebuilt by Uninstall because Open/Close Panel keep Position Not changed),
      // when No Record or Record out of bounds only then Rand take position
      const saved = petPositions[agentId]
      const start = saved ? clampPos(saved.x, saved.y) : pickTarget()
      pet = {
        agentId,
        name: agent.name || agent.agent_id,
        agentType: agent.agent_type || 'agent',
        workingDir: agent.working_dir || '',
        x: start.x,
        y: start.y,
        target: pickTarget(),
        faceLeft: false,
        statusClass: '',
        classes: '',
        active: false,
        typing: false,
        dragging: false,
        inputMode: 'multi',
        hasInputRequest: false,
        inputText: '',
        inputTip: '',
        isPassword: false,
        confirmMessage: '',
        confirmDefault: true,
        output: '',
        panelAbove: false,
        stackLeft: 0,
        stackWidth: 0,
        stackMaxH: 0,
        outputAutoScroll: true,
        copied: false,
        copyTimer: null,
      }
    } else {
      pet.name = agent.name || agent.agent_id
      pet.agentType = agent.agent_type || 'agent'
      pet.workingDir = agent.working_dir || ''
    }
    const statusClass = props.getStatusClass ? props.getStatusClass(agent) : ''
    pet.statusClass = statusClass
    pet.classes = `status-${statusClass}${pet.faceLeft ? ' face-left' : ''}`
    refreshPetData(pet)
    next.push(pet)
  }
  petAgents.value = next
  // if Current Expand's Pet Already disappeared, Reset activePetId
  if (activePetId.value && !next.some(p => p.agentId === activePetId.value)) {
    activePetId.value = null
  }
  // clean up Already being Deleted Agent's Position Record (stopped still Exists, Not cleaned up)
  // only clean up after in/at taken a non Empty agent List back, avoid wrongly deleting when initial Load (List is temporarily Empty)
  if (list.length > 0) {
    prunePositions(new Set(next.map(p => p.agentId)))
  }
  // clean up Already being Deleted Agent's Output Hide persisted Data (stopped still Exists, Not cleaned up)
  // only clean up after in/at taken a non Empty agent List back, avoid wrongly deleting when initial Load (List is temporarily Empty)
  if (list.length > 0) {
    for (const a of list) {
      if (a && a.agent_id) seenAgentIds.add(a.agent_id)
    }
    let hiddenChanged = false
    const pruned = new Set()
    for (const id of hiddenOutputIds.value) {
      if (seenAgentIds.has(id)) pruned.add(id)
      else hiddenChanged = true
    }
    if (hiddenChanged) {
      hiddenOutputIds.value = pruned
      saveHiddenOutputs()
    }
  }
}

// single frame: all Has Pets Move to their respective target points, and do repulsion avoid 
function step() {
  const pets = petAgents.value
  // when Sprite Hide Not rendering also Not Move, directly Skip All Calculate, reduce resource consumption
  if (!showPets.value) {
    rafId = requestAnimationFrame(step)
    return
  }
  const n = pets.length
  // Calculate pairwise repulsion Offset
  const pushX = new Array(n).fill(0)
  const pushY = new Array(n).fill(0)
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const dx = pets[j].x - pets[i].x
      const dy = pets[j].y - pets[i].y
      const dist = Math.hypot(dx, dy) || 0.001
      if (dist < MIN_DIST) {
        const force = (MIN_DIST - dist) / MIN_DIST
        const ux = dx / dist
        const uy = dy / dist
        pushX[i] -= ux * force * 2.2
        pushY[i] -= uy * force * 2.2
        pushX[j] += ux * force * 2.2
        pushY[j] += uy * force * 2.2
      }
    }
  }

  for (let i = 0; i < n; i++) {
    const pet = pets[i]
    // In progress Input, Expand interactive Panel or Pet in the middle of dragging Not Move
    if (pet.active || pet.typing || pet.dragging) continue
    if (!roaming.value) continue
    const dx = pet.target.x - pet.x
    const dy = pet.target.y - pet.y
    const dist = Math.hypot(dx, dy)
    if (dist < 6) {
      pet.target = pickTarget()
    } else {
      pet.x += (dx / dist) * PET_SPEED + pushX[i]
      pet.y += (dy / dist) * PET_SPEED + pushY[i]
    }
    const clamped = clampPos(pet.x, pet.y)
    pet.x = clamped.x
    pet.y = clamped.y
    // after Position changes write back to persisted Record by throttled stream
    rememberPosition(pet)
    const faceLeft = dx < -1
    if (faceLeft !== pet.faceLeft) {
      pet.faceLeft = faceLeft
      pet.classes = `status-${pet.statusClass}${faceLeft ? ' face-left' : ''}`
    }
  }

  rafId = requestAnimationFrame(step)
}

function measureStage() {
  const el = stageRef.value
  if (!el) return
  stageSize.value = { w: el.clientWidth, h: el.clientHeight }
  // after stage size changes recalculate stacked Container Position, avoid Input/Output box overflow out visible Range
  for (const pet of petAgents.value) layoutPetStack(pet)
}

// Click big hall blank area: Cancel all Pets' Selected/Expand Status, let It Restore floating
function onStageClick(event) {
  // Click anywhere all first Close Right click Menu
  closeContextMenu()
  // only when Click target Yes stage itself (Empty blank Area) when only then handle; Pet and its Panel Already stop bubbling
  if (event.target !== stageRef.value) return
  // Click blank area Cancel Node Selected
  activeNodeId.value = null
  for (const pet of petAgents.value) {
    if (pet.active) closePanel(pet)
  }
}

// ===== Right click Menu (for Pet / Node Total) =====
// Menu Status: coordinate Relative stage left top corner; kind distinguish come origin; name use at/on Title
const contextMenu = ref({ visible: false, x: 0, y: 0, kind: 'pet', agentId: null, nodeId: null, name: '' })

// Node Menu built-in action: in/at Node up Create Agent / Update code / Restart service (later Can append More Node Feature in/at This)
const NODE_MENU_ACTIONS = [
  { id: 'node-create-agent', icon: '➕', label: 'Create Agent' },
  { id: 'node-open-terminal', icon: PET_ICONS.terminal, label: 'Open terminal' },
  { id: 'node-update-code', icon: PET_ICONS.refresh, label: 'Update code' },
  { id: 'node-restart-service', icon: PET_ICONS.restart, label: 'Restart service' },
  { id: 'node-rename', icon: PET_ICONS.edit, label: 'Rename' },
]
const nodeMenuActions = computed(() => {
  const extra = props.nodeActions || []
  return [...NODE_MENU_ACTIONS, ...extra]
})

// Pet Menu built-in action: Add to group / Remove from group (later Can append More Pet Feature in/at This)
const PET_MENU_ACTIONS = [
  { id: 'pet-add-to-group', icon: PET_ICONS.folder, label: 'Add to group' },
  { id: 'pet-remove-from-group', icon: PET_ICONS.folderOpen, label: 'Remove from group' },
]
const petMenuActions = computed(() => [...(props.contextActions || []), ...PET_MENU_ACTIONS])

// Current Menu items: take right should come origin by kind
const contextMenuActions = computed(() =>
  contextMenu.value.kind === 'node' ? nodeMenuActions.value : petMenuActions.value
)

function closeContextMenu() {
  if (contextMenu.value.visible) contextMenu.value.visible = false
}

// Estimate Menu size and do Edge boundary clamp, avoid exceed out stage (two Col Layout, Width and CSS min-width Align)
function placeContextMenu(event, itemCount) {
  const stage = stageRef.value
  if (!stage) return null
  const rect = stage.getBoundingClientRect()
  const MENU_W = 320
  const rows = Math.max(1, Math.ceil(itemCount / 2))
  const MENU_H = Math.min(44 + rows * 33, rect.height * 0.6)
  let x = event.clientX - rect.left
  let y = event.clientY - rect.top
  if (x + MENU_W > rect.width) x = Math.max(rect.width - MENU_W, 0)
  if (y + MENU_H > rect.height) y = Math.max(rect.height - MENU_H, 0)
  return { x, y }
}

// in/at Pet up Right click: Notification parent Component Switch Current Agent and prepare action, then popup Menu in place
function onPetContextMenu(pet, event) {
  if (!pet) return
  // Cancel pending execution single click detection: avoid 250ms after Right click wrongly trigger onPetClick and change Selected Status
  if (clickTimer) {
    clearTimeout(clickTimer)
    clickTimer = null
  }
  // Mark this gesture Already triggered Right click Menu: Move end Long Press's pointerup later at/on contextmenu,
  // then according to This suppress onPetClick, avoid Long Press at the same time Switch Agent Active Status
  contextMenuTriggered = true
  // first Req parent Component to switch "Current Agent" to this Pet (decide Menu action and availability)
  emit('contextAgent', pet.agentId)
  const pos = placeContextMenu(event, petMenuActions.value.length)
  if (!pos) return
  contextMenu.value = {
    visible: true,
    x: pos.x,
    y: pos.y,
    kind: 'pet',
    agentId: pet.agentId,
    nodeId: null,
    name: pet.name || pet.agentId,
  }
}

// in/at Node up single click: Selected this Node (Node Action Shortcuts according to This act at/on this Node); again Click same one Node then Cancel Selected
function onNodeClick(node) {
  if (!node) return
  activeNodeId.value = activeNodeId.value === node.node_id ? null : node.node_id
}

// in/atNode up Right click：popupNodeActionMenu
function onNodeContextMenu(node, event) {
  if (!node) return
  // Right click at the same time Selected this Node, make Node Action Shortcuts and Menu act at/on same one Node
  activeNodeId.value = node.node_id
  const pos = placeContextMenu(event, nodeMenuActions.value.length)
  if (!pos) return
  contextMenu.value = {
    visible: true,
    x: pos.x,
    y: pos.y,
    kind: 'node',
    agentId: null,
    nodeId: node.node_id,
    name: node.short || node.node_id,
  }
}

// ===== Node Rename popup layer =====
// after OK emit('renameNode', { nodeId, name }), written by parent Component into Settings inside's Node Name Map
const renameDialog = ref({ visible: false, nodeId: '', value: '' })
const renameInputRef = ref(null)

function openRenameDialog(nodeId, currentName) {
  if (!nodeId) return
  // when Already Open Not triggered repeatedly (avoid Reset Input Content when F2 repeatedly pressed, Shortcuts and Right click Menu Concurrent)
  if (renameDialog.value.visible) return
  renameDialog.value = {
    visible: true,
    nodeId,
    value: currentName && currentName !== nodeId ? currentName : '',
  }
  nextTick(() => {
    const el = renameInputRef.value
    if (el) {
      el.focus()
      el.select()
    }
  })
}

function closeRenameDialog() {
  if (renameDialog.value.visible) renameDialog.value.visible = false
}

function confirmRename() {
  const nodeId = renameDialog.value.nodeId
  const name = String(renameDialog.value.value || '').trim()
  if (nodeId) emit('renameNode', { nodeId, name })
  closeRenameDialog()
}

// ===== Pet "Add to group" popup layer =====
// SelectAlreadyHasGroup，orNewGroup；OK back  emit('addAgentToGroup', { agentId, groupId } | { agentId, newGroupName })
const groupDialog = ref({ visible: false, agentId: '', agentName: '', newGroupName: '' })

function openGroupDialog(agentId, agentName) {
  if (!agentId) return
  groupDialog.value = { visible: true, agentId, agentName: agentName || agentId, newGroupName: '' }
}

function closeGroupDialog() {
  if (groupDialog.value.visible) groupDialog.value.visible = false
}

// add to Already Has Group
function pickGroup(groupId) {
  const agentId = groupDialog.value.agentId
  if (agentId && groupId) emit('addAgentToGroup', { agentId, groupId })
  closeGroupDialog()
}

// New Group and add to 
function createGroupAndAdd() {
  const agentId = groupDialog.value.agentId
  const name = String(groupDialog.value.newGroupName || '').trim()
  if (!agentId || !name) return
  emit('addAgentToGroup', { agentId, newGroupName: name })
  closeGroupDialog()
}

// ===== Pet "Remove from group" popup layer =====
// only list out Group this Agent currently belongs to, Click then Remove
const removeGroupDialog = ref({ visible: false, agentId: '', agentName: '' })

// Group List this Agent currently belongs to
const removeGroupOptions = computed(() => {
  const agentId = removeGroupDialog.value.agentId
  if (!agentId) return []
  return (props.agentGroups || []).filter(g => (g.agentIds || []).includes(agentId))
})

function openRemoveGroupDialog(agentId, agentName) {
  if (!agentId) return
  removeGroupDialog.value = { visible: true, agentId, agentName: agentName || agentId }
}

function closeRemoveGroupDialog() {
  if (removeGroupDialog.value.visible) removeGroupDialog.value.visible = false
}

// Remove from specified Group
function pickRemoveGroup(groupId) {
  const agentId = removeGroupDialog.value.agentId
  if (agentId && groupId) emit('removeAgentFromGroup', { agentId, groupId })
  closeRemoveGroupDialog()
}

// ===== Install Browser extension popup layer =====
// display Install Step Description, and provide "Download extension package" Button (actually Download by parent Component injected download Extension Done)
const installDialog = ref({ visible: false, downloading: false, error: '' })

function openInstallExtensionDialog() {
  installDialog.value = { visible: true, downloading: false, error: '' }
  refreshExtensionVersion()
}

function closeInstallDialog() {
  if (installDialog.value.visible) installDialog.value.visible = false
}

async function downloadExtension() {
  if (installDialog.value.downloading) return
  if (typeof props.downloadExtension !== 'function') {
    installDialog.value.error = 'Current Environment Not supported Download, Please Manual Load from source Directory browser_extension/'
    return
  }
  installDialog.value.downloading = true
  installDialog.value.error = ''
  try {
    await props.downloadExtension()
  } catch (e) {
    installDialog.value.error = (e && e.message) ? e.message : 'DownloadFailed，PleaseLaterRetry'
  } finally {
    installDialog.value.downloading = false
  }
}

// ===== Install local daemon service (daemon) popup layer =====
// display Install Step, Download Link and risk Tip; pure Static Content, No Net Req
const daemonDialog = ref({ visible: false })

// Whether Already Install local daemon service (daemon): by parent Component detecting local loopback /api/status passed in via props back.
// daemon Yes local process, cannot inject in DOM Mark to Page like Browser extension that way, so can only rely on local detection to judge;
// detection Success (local daemon In progress Running) then Hide big hall's Install guide Button, and keep Hide logic consistent with Extension's.
const daemonInstalled = computed(() => props.localDaemonOnline === true)

function openDaemonDialog() {
  daemonDialog.value = { visible: true }
}

function closeDaemonDialog() {
  if (daemonDialog.value.visible) daemonDialog.value.visible = false
}

// ===== Extension Version detection =====
// latest come from Gateway Package Version; "Current Version" takes local Extension reported localExtensionVersion.
// when any missing Not judged as Need Upgrade.
const extensionVersion = ref({ latest: '', outdated: false, checked: false })

function isVersionOutdated(current, latest) {
  if (!current || !latest) return false
  return String(current).trim() !== String(latest).trim()
}

async function refreshExtensionVersion() {
  if (typeof props.checkExtensionVersion !== 'function') return
  let info = null
  try {
    info = await props.checkExtensionVersion()
  } catch (e) {
    // in polling scenario down Abnormal must not interrupt Timer, also Not should affect popup layer display
    return
  }
  if (!info) {
    extensionVersion.value = { latest: '', outdated: false, checked: true }
    return
  }
  const latest = info.latestVersion || ''
  // only keep Gateway Package's latest Version; "Current Version" always takes local Extension reported Version
  // (localExtensionVersion), Not again use Gateway's Global Online Session Version,
  // avoid when more devices / more Users Online showing others' Version as local Version.
  extensionVersion.value = {
    latest,
    outdated: isVersionOutdated(localExtensionVersion.value, latest),
    checked: true
  }
}

// Whether Already Install Browser extension: by Extension's content script written in DOM Mark in/at Page up
// (document.documentElement.dataset.haijunbotExtInstalled) judged.
// this Mark indicates "local installed Extension", and is No close to "Extension whether Online/Already Connect Gateway":
// - desktop installed Extension → content script injected → Mark Exists → Hide Install Button;
// - mobile Not installed Extension → No content script → Mark missing → as usual Show Button;
//  because This will Not wrongly Hide mobile's guide Button because desktop Extension Online.
const extensionInstalled = ref(false)
// local Already Install Extension's Version number: also written into DOM by content script (dataset.haijunbotExtVersion),
// taken from Extension itself's chrome.runtime.getManifest().version.
// use It but not Gateway's Online Session Version: Gateway sessions Yes Global's (Not distinguishing devices/Users),
// when more devices Online will be shown as others' Version, and does not match local actually installed Version.
const localExtensionVersion = ref('')

function readExtensionInstalled() {
  try {
    return document.documentElement.dataset.haijunbotExtInstalled === '1'
  } catch (e) {
    /* when DOM Not Available regarded as Not Install */
  }
  return false
}

function readLocalExtensionVersion() {
  try {
    return String(document.documentElement.dataset.haijunbotExtVersion || '')
  } catch (e) {
    /* when DOM Not Available regarded as Unknown */
  }
  return ''
}

// content script injected in at document_idle, may be later at/on this Component mounting;
// so after mounting short when poll until reading Mark, once read then Stopped.
let extensionInstalledTimer = null
function startExtensionInstalledWatch() {
  extensionInstalled.value = readExtensionInstalled()
  localExtensionVersion.value = readLocalExtensionVersion()
  if (extensionInstalled.value) return
  let attempts = 0
  extensionInstalledTimer = setInterval(() => {
    if (readExtensionInstalled()) {
      extensionInstalled.value = true
      localExtensionVersion.value = readLocalExtensionVersion()
      stopExtensionInstalledWatch()
      // local Version only then Available at This time: recalculate once "Whether Has New Version", make Upgrade Tip Now take effect
      refreshExtensionVersion()
      return
    }
    // at most poll about 10 Sec (20 × 500ms), avoid long term Empty spinning when No Extension
    if (++attempts >= 20) stopExtensionInstalledWatch()
  }, 500)
}

function stopExtensionInstalledWatch() {
  if (extensionInstalledTimer) {
    clearInterval(extensionInstalledTimer)
    extensionInstalledTimer = null
  }
}

// Extension Version polling: after mounting detect once immediately, then recheck every 5 Min,
//  make "Install browser extension" Button's Update red dot Can take effect without Open popup layer
const EXTENSION_VERSION_POLL_MS = 5 * 60 * 1000
let extensionVersionTimer = null

function startExtensionVersionPolling() {
  refreshExtensionVersion()
  extensionVersionTimer = setInterval(
    refreshExtensionVersion,
    EXTENSION_VERSION_POLL_MS,
  )
}

function stopExtensionVersionPolling() {
  if (extensionVersionTimer) {
    clearInterval(extensionVersionTimer)
    extensionVersionTimer = null
  }
}

// ===== connect/join end Session polling (Browser extension / Local daemon service) =====
// Data source all for Gateway Session List (injected by parent Component):
// - checkExtensionSessions → GET /api/browser-ext/sessions (including name / extension_version)
// - checkDaemonSessions    → GET /api/daemon/sessions (including name / platform / daemon_version)
// topology Graph according to This render one Node for each Online Session and Show its Name.
// Note: Gateway right non Manage staff only return their own user_id Session, so what ordinary User sees Yes their own connect/join end.
const extensionSessions = ref([])
const daemonSessions = ref([])
const ACCESS_POLL_MS = 10000
let accessTimer = null

async function refreshAccessSessions() {
  if (typeof props.checkExtensionSessions === 'function') {
    try {
      const sessions = await props.checkExtensionSessions()
      extensionSessions.value = Array.isArray(sessions) ? sessions : []
    } catch (e) {
      // in polling scenario down Abnormal must not interrupt Timer
      extensionSessions.value = []
    }
  }
  if (typeof props.checkDaemonSessions === 'function') {
    try {
      const sessions = await props.checkDaemonSessions()
      daemonSessions.value = Array.isArray(sessions) ? sessions : []
    } catch (e) {
      daemonSessions.value = []
    }
  }
}

function startAccessPolling() {
  refreshAccessSessions()
  accessTimer = setInterval(refreshAccessSessions, ACCESS_POLL_MS)
}

function stopAccessPolling() {
  if (accessTimer) {
    clearInterval(accessTimer)
    accessTimer = null
  }
}

// Click Menu items: dispatch by Menu origin to parent Component to execute, then Close Menu
function onContextAction(act) {
  if (!act || act.enabled === false) return
  if (contextMenu.value.kind === 'node') {
    if (act.id === 'node-rename') {
      // Rename pops up Input box in/at big hall, Not going through parent Component's Node action dispatch
      openRenameDialog(contextMenu.value.nodeId, contextMenu.value.name)
    } else {
      emit('nodeContextRun', { action: act, nodeId: contextMenu.value.nodeId })
    }
  } else if (act.id === 'pet-add-to-group') {
    // Add to group pops up Group Select box in/at big hall
    openGroupDialog(contextMenu.value.agentId, contextMenu.value.name)
  } else if (act.id === 'pet-remove-from-group') {
    // Remove from group pops up Group List in/at big hall (only this Agent's belongs to Group)
    openRemoveGroupDialog(contextMenu.value.agentId, contextMenu.value.name)
  } else {
    emit('contextRun', act)
  }
  closeContextMenu()
}

// dragging Status
const DRAG_THRESHOLD = 4 // exceed this displacement regarded as dragging and not Click
let dragState = null // { pet, startX, startY, offsetX, offsetY, moved }
// Mark whether the current gesture already triggered the right-click menu (long press will fire contextmenu before pointerup,
// Need to use this to suppress the click triggered by pointerup, to avoid long press also switching Agent active state)
let contextMenuTriggered = false

function onPetPointerDown(pet, event) {
  // Only respond to mouse left button / touch / pen
  if (event.button !== undefined && event.button !== 0) return
  const stage = stageRef.value
  if (!stage) return
  // A new gesture starts, reset right-click menu mark
  contextMenuTriggered = false
  // Touch/pen: prevent browser default gestures (scroll, zoom), otherwise pointermove will be interrupted by pointercancel
  if (event.pointerType && event.pointerType !== 'mouse') {
    event.preventDefault()
  }
  const rect = stage.getBoundingClientRect()
  dragState = {
    pet,
    startX: event.clientX,
    startY: event.clientY,
    offsetX: event.clientX - rect.left - pet.x,
    offsetY: event.clientY - rect.top - pet.y,
    moved: false,
    rect,
    pointerId: event.pointerId,
    target: event.currentTarget,
  }
  // Capture pointer: after the finger leaves the Pet element it can still keep receiving pointermove, making dragging smoother
  if (event.pointerId !== undefined && event.currentTarget && event.currentTarget.setPointerCapture) {
    try {
      event.currentTarget.setPointerCapture(event.pointerId)
    } catch (e) {
      /* Ignore scenarios where capture is not supported */
    }
  }
  window.addEventListener('pointermove', onPetPointerMove)
  window.addEventListener('pointerup', onPetPointerUp)
  window.addEventListener('pointercancel', onPetPointerCancel)
}

function onPetPointerMove(event) {
  if (!dragState) return
  const { pet } = dragState
  const dx = event.clientX - dragState.startX
  const dy = event.clientY - dragState.startY
  if (!dragState.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return
  dragState.moved = true
  pet.dragging = true
  // Cancel the pending click when dragging
  if (clickTimer) {
    clearTimeout(clickTimer)
    clickTimer = null
  }
  const rect = dragState.rect
  const nx = event.clientX - rect.left - dragState.offsetX
  const ny = event.clientY - rect.top - dragState.offsetY
  const clamped = clampPos(nx, ny)
  pet.x = clamped.x
  pet.y = clamped.y
  pet.target = { x: clamped.x, y: clamped.y }
  // Recompute the stacked container position during dragging to ensure the Input/Output box always stays within the visible area 
  layoutPetStack(pet)
  // Prevent page scroll when touch-dragging
  if (event.cancelable && event.pointerType && event.pointerType !== 'mouse') {
    event.preventDefault()
  }
}

function releasePointerCapture() {
  if (!dragState) return
  const { pointerId, target } = dragState
  if (pointerId !== undefined && target && target.releasePointerCapture) {
    try {
      target.releasePointerCapture(pointerId)
    } catch (e) {
      /* Ignore when already released or not captured */
    }
  }
}

function onPetPointerUp() {
  window.removeEventListener('pointermove', onPetPointerMove)
  window.removeEventListener('pointerup', onPetPointerUp)
  window.removeEventListener('pointercancel', onPetPointerCancel)
  if (!dragState) return
  const { pet, moved } = dragState
  releasePointerCapture()
  dragState = null
  if (pet.dragging) {
    pet.dragging = false
    // Record the drop point when dragging ends, to avoid the next mount returning to the old position
    rememberPosition(pet)
    // Keep floating from the current position after release
    pet.target = pickTarget()
    return
  }
  // No drag occurred: treat as a click
  // If this gesture already triggered the right-click menu (long press), then suppress the click, to avoid also switching Agent active state
  if (!moved && !contextMenuTriggered) onPetClick(pet)
  contextMenuTriggered = false
}

// When the pointer is cancelled by the browser (e.g. touch taken over by a system gesture), safely reset to avoid a dangling dragState
function onPetPointerCancel() {
  window.removeEventListener('pointermove', onPetPointerMove)
  window.removeEventListener('pointerup', onPetPointerUp)
  window.removeEventListener('pointercancel', onPetPointerCancel)
  if (!dragState) return
  const { pet } = dragState
  releasePointerCapture()
  dragState = null
  if (pet.dragging) {
    pet.dragging = false
    rememberPosition(pet)
    pet.target = pickTarget()
  }
}

// Click: judge with a delay, to avoid conflicting with double click (double click cancels the click action)
// Semantics: "always select and expand"; cancel selection only via clicking an empty spot on the stage (onStageClick)
let clickTimer = null
function onPetClick(pet) {
  if (clickTimer) {
    clearTimeout(clickTimer)
    clickTimer = null
  }
  clickTimer = setTimeout(() => {
    clickTimer = null
    // Clicking again when active: hide this Agent's output and cancel active, rather than expanding again
    if (activePetId.value === pet.agentId && pet.active) {
      hideActiveOutputAndClose()
      return
    }
    openPanel(pet)
  }, 250)
}

// Double click: enter this Agent's detail view (cancel the pending click)
function onPetDblClick(pet) {
  if (clickTimer) {
    clearTimeout(clickTimer)
    clickTimer = null
  }
  closePanel(pet)
  emit('selectAgent', pet.agentId)
}

function openPanel(pet, focusInput = false) {
  // Expand only one at a time
  if (activePetId.value && activePetId.value !== pet.agentId) {
    const prev = petAgents.value.find(p => p.agentId === activePetId.value)
    if (prev) closePanel(prev)
  }
  activePetId.value = pet.agentId
  pet.active = true
  pet.typing = false
  // Active means opening this Agent's output display: only pet.active can make the stack container show,
  // The output bubble is still blocked by isOutputHidden, so this Agent must be removed from the hidden set (not rolled back when canceling active)
  if (hiddenOutputIds.value.has(pet.agentId)) {
    const next = new Set(hiddenOutputIds.value)
    next.delete(pet.agentId)
    hiddenOutputIds.value = next
    saveHiddenOutputs()
  }
  refreshPetData(pet)
  // Two cases for focusing the input box:
  // 1) Keyboard arrow-key selection (focusInput=true): the keyboard navigation intent is clear, always give focus to the input box;
  // 2) Mouse click opens and this Agent has a pending input request: only then auto-focus, to avoid interrupting the user viewing output.
  if (focusInput) {
    focusPetInput(pet.agentId, true)
  } else if (pet.hasInputRequest && pet.inputMode !== 'confirm') {
    focusPetInput(pet.agentId, true)
  }
}

function closePanel(pet) {
  if (!pet) return
  pet.active = false
  pet.typing = false
  // Keep pet.inputText: collapsing the panel (e.g. clicking an empty spot to cancel active) should not lose the user's unsent draft
  if (activePetId.value === pet.agentId) activePetId.value = null
}

// Exit current Pet selected status (called by the parent component's ESC shortcut):
// Return false when there is no selection, so the parent component can judge whether ESC was already consumed
function closeActivePanel() {
  closeContextMenu()
  if (!activePetId.value) return false
  const pet = petAgents.value.find(p => p.agentId === activePetId.value)
  if (pet) closePanel(pet)
  else activePetId.value = null
  return true
}

// In active state "hide this Agent's output and cancel selection" (called by the parent component's Ctrl+W):
// Unlike toggleAgentOutput, this is idempotently set to hidden, and pressing repeatedly will not show the output again 
function hideActiveOutputAndClose() {
  const agentId = activePetId.value
  if (!agentId) return false
  if (!hiddenOutputIds.value.has(agentId)) {
    const next = new Set(hiddenOutputIds.value)
    next.add(agentId)
    hiddenOutputIds.value = next
    saveHiddenOutputs()
  }
  const pet = petAgents.value.find(p => p.agentId === agentId)
  if (pet) closePanel(pet)
  else activePetId.value = null
  return true
}

function onInputPointerDown(pet) {
  pet.typing = true
}

// Multi-line input box shortcuts, kept consistent with the Agent Panel:
// Ctrl+Enter / Ctrl+D send; Enter newline; up/down arrows browse history when on the first/last line; Ctrl+C sends a done signal when the input is empty
function handlePetKeydown(pet, event) {
  if (handlePetCtrlKeydown(pet, event)) return
  if (event.key === '@') {
    // Reuse the @ button logic: first write the @ at the correct position in the input box, then trigger completion.
    // This way the @ is kept in the input box when canceling completion (the parent component's right lobby source will not re-insert the @)
    event.preventDefault()
    insertAtSymbol(pet)
    return
  }
  if (event.ctrlKey && (event.key === 'Enter' || event.key.toLowerCase() === 'd')) {
    event.preventDefault()
    submitPet(pet)
    return
  }
  if (event.key === 'ArrowUp' && !event.ctrlKey && !event.altKey && !event.metaKey) {
    const textarea = event.target
    if (isCursorAtFirstLine(textarea)) {
      event.preventDefault()
      if (props.historyNav) {
        const val = props.historyNav(pet.agentId, 'up', pet.inputText || '')
        if (typeof val === 'string') pet.inputText = val
      }
    }
    return
  }
  if (event.key === 'ArrowDown' && !event.ctrlKey && !event.altKey && !event.metaKey) {
    const textarea = event.target
    if (isCursorAtLastLine(textarea)) {
      event.preventDefault()
      if (props.historyNav) {
        const val = props.historyNav(pet.agentId, 'down', pet.inputText || '')
        if (typeof val === 'string') pet.inputText = val
      }
    }
    return
  }
  if (event.ctrlKey && event.key === 'c') {
    const hasText = (pet.inputText || '').trim().length > 0
    // Only intercept the Ctrl+C done signal when there is no selected text and the input is empty
    const hasSelection = event.target.selectionStart !== event.target.selectionEnd
    if (!hasText && !hasSelection && pet.inputMode === 'multi') {
      event.preventDefault()
      emit('complete', pet.agentId)
    }
  }
}

// Single-line input box shortcuts: Enter send; @ open completion
function handlePetSingleKeydown(pet, event) {
  if (handlePetCtrlKeydown(pet, event)) return
  if (event.key === '@') {
    // Same as multi-line input: write the @ first then trigger completion, the @ must be kept when canceling completion
    event.preventDefault()
    insertAtSymbol(pet)
    return
  }
  if (event.key === 'Enter' && !event.ctrlKey && !event.altKey && !event.metaKey) {
    event.preventDefault()
    submitPet(pet)
  }
}

// Right Ctrl quick double-click: send (same as Agent Panel row)
const DOUBLE_TAP_MS = 300 // Double-click detection window
const QUICK_TAP_MS = 250  // Single "quick press" detection
let ctrlDownTime = 0
let lastQuickTapTime = 0

function handlePetCtrlKeydown(pet, event) {
  if (event.code !== 'ControlRight') return false
  event.preventDefault()
  const now = Date.now()
  // The previous was a quick click and the interval is within the double-click window → judge as double-click send
  if (lastQuickTapTime && now - lastQuickTapTime < DOUBLE_TAP_MS) {
    lastQuickTapTime = 0
    submitPet(pet)
    return true
  }
  ctrlDownTime = now
  return true
}

function handlePetCtrlKeyup(event) {
  if (event.code !== 'ControlRight') return
  event.preventDefault()
  // A very short press time is treated as a "quick click", and recorded for the next double-click judgment
  if (ctrlDownTime && Date.now() - ctrlDownTime < QUICK_TAP_MS) {
    lastQuickTapTime = Date.now()
  } else {
    lastQuickTapTime = 0
  }
  ctrlDownTime = 0
}

// Input change: detect whether @ was just typed (including Chinese input method), trigger completion
function handlePetInput(pet, event) {
  const target = event.target
  const cursorPosition = target.selectionStart
  const textBeforeCursor = target.value.substring(0, cursorPosition)
  if (textBeforeCursor.endsWith('@')) {
    emit('openCompletions', pet.agentId, cursorPosition - 1)
  }
}

// Click "@" button: insert @ at the cursor and trigger completion (equivalent to manually typing @)
function insertAtSymbol(pet) {
  if (!pet) return
  const el = stageRef.value && stageRef.value.querySelector(`[data-pet-input="${pet.agentId}"]`)
  const value = pet.inputText || ''
  const start = el && typeof el.selectionStart === 'number' ? el.selectionStart : value.length
  const end = el && typeof el.selectionEnd === 'number' ? el.selectionEnd : value.length
  const next = value.substring(0, start) + '@' + value.substring(end)
  pet.inputText = next
  pet.typing = true
  const atPos = start
  requestAnimationFrame(() => {
    const target = stageRef.value && stageRef.value.querySelector(`[data-pet-input="${pet.agentId}"]`)
    if (target) {
      try { target.setSelectionRange(atPos + 1, atPos + 1) } catch (e) { /* ignore */ }
      target.focus()
    }
  })
  emit('openCompletions', pet.agentId, atPos)
}

function isCursorAtFirstLine(textarea) {
  const pos = textarea.selectionStart
  return !textarea.value.substring(0, pos).includes('\n')
}

function isCursorAtLastLine(textarea) {
  const pos = textarea.selectionEnd
  return !textarea.value.substring(pos).includes('\n')
}

function submitPet(pet) {
  const text = pet.inputMode === 'single' ? pet.inputText : pet.inputText.trim()
  if (pet.inputMode !== 'single' && !text) return
  emit('sendInput', pet.agentId, text, pet.inputMode)
  pet.inputText = ''
  pet.typing = false
  refreshPetData(pet)
}

// Done: same as the Panel's "Done" button, sends a done signal (handled by the parent component)
function completePet(pet) {
  if (!pet || !pet.agentId) return
  emit('complete', pet.agentId)
  refreshPetData(pet)
}

function submitConfirm(pet, confirmed) {
  emit('sendInput', pet.agentId, confirmed ? 'y' : 'n', 'confirm')
  refreshPetData(pet)
}

// Dashboard time: independent 1s timer refresh (the refresh loop will return early when the sprite is hidden, cannot depend on it)
const dashNow = ref(new Date())
let dashTimer = null
const WEEKDAYS = ['Weekday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
function pad2(n) {
  return String(n).padStart(2, '0')
}
const dashTime = computed(() => {
  const d = dashNow.value
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
})
const dashDate = computed(() => {
  const d = dashNow.value
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${WEEKDAYS[d.getDay()]}`
})

// Cron refresh: status light, output bubble, input state (output/confirm are always shown, need to refresh for all pets)
let refreshTimer = null
function refreshLoop() {
  // SpriteHidehourNoNeed RefreshanyPetData
  if (!showPets.value) return
  for (const pet of petAgents.value) {
    const agent = (props.agents || []).find(a => a.agent_id === pet.agentId)
    if (agent && props.getStatusClass) {
      const statusClass = props.getStatusClass(agent)
      if (statusClass !== pet.statusClass) {
        pet.statusClass = statusClass
        pet.classes = `status-${statusClass}${pet.faceLeft ? ' face-left' : ''}`
      }
    }
    // Do not overwrite the input box content while inputting, but still refresh output/confirm state
    if (!pet.typing) {
      // When output is hidden and the interaction panel is not expanded, skip the heavier output (markdown) refresh;
      // Active pets (with interaction panel expanded) still need refreshing to keep their output panel updated in real time
      if (!isOutputHidden(pet.agentId) || pet.active) {
        refreshPetData(pet)
      } else {
        layoutPetStack(pet)
      }
    }
  }
}

onMounted(() => {
  measureStage()
  syncPets()
  updateIsMobile()
  rafId = requestAnimationFrame(step)
  refreshTimer = setInterval(refreshLoop, 800)
  dashTimer = setInterval(() => { dashNow.value = new Date() }, 1000)
  startExtensionInstalledWatch()
  startExtensionVersionPolling()
  startAccessPolling()
  window.addEventListener('keydown', onGlobalKeydown)
  window.addEventListener('resize', closeContextMenu)
  window.addEventListener('resize', updateIsMobile)
  window.addEventListener('blur', closeContextMenu)
  if (typeof ResizeObserver !== 'undefined' && stageRef.value) {
    resizeObserver = new ResizeObserver(() => measureStage())
    resizeObserver.observe(stageRef.value)
  }
})

// The Pet that should currently respond to confirm shortcuts: the confirm panel is shown without needing to expand,
// So preferentially take the one already expanded, otherwise take the first Pet in confirm state
function activeConfirmPet() {
  const confirming = petAgents.value.filter(p => p.inputMode === 'confirm')
  if (confirming.length === 0) return null
  if (activePetId.value) {
    const active = confirming.find(p => p.agentId === activePetId.value)
    if (active) return active
  }
  return confirming[0]
}

// Whether there is an input inside a popup layer in progress (rename/new group, etc.), this should not respond to confirm shortcuts
function isTypingInDialog(e) {
  const el = e.target
  if (!el || !el.tagName) return false
  const tag = el.tagName.toLowerCase()
  return tag === 'input' || tag === 'textarea' || el.isContentEditable
}

// Global key press: Esc closes the right-click menu and popup layer; in confirm state y/n/Enter respond to confirm (same as Panel)
function onGlobalKeydown(e) {
  if (e.key === 'Escape') {
    closeContextMenu()
    closeRenameDialog()
    closeGroupDialog()
    closeRemoveGroupDialog()
    closeDaemonDialog()
    return
  }
  // Do not intercept when there is an input inside the popup layer, to avoid accidentally triggering confirm
  if (isTypingInDialog(e)) return
  if (e.ctrlKey || e.altKey || e.metaKey) return
  const pet = activeConfirmPet()
  if (!pet) return
  if (e.key === 'y' || e.key === 'Y') {
    e.preventDefault()
    submitConfirm(pet, true)
    return
  }
  if (e.key === 'n' || e.key === 'N') {
    e.preventDefault()
    submitConfirm(pet, false)
    return
  }
  if (e.key === 'Enter') {
    e.preventDefault()
    submitConfirm(pet, pet.confirmDefault !== false)
  }
}

onUnmounted(() => {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = null
  // Persist Pet position to disk once when leaving the lobby (component unmount)
  savePositions()
  window.removeEventListener('pointermove', onPetPointerMove)
  window.removeEventListener('pointerup', onPetPointerUp)
  window.removeEventListener('keydown', onGlobalKeydown)
  window.removeEventListener('resize', closeContextMenu)
  window.removeEventListener('resize', updateIsMobile)
  window.removeEventListener('blur', closeContextMenu)
  dragState = null
  if (clickTimer) {
    clearTimeout(clickTimer)
    clickTimer = null
  }
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  if (dashTimer) {
    clearInterval(dashTimer)
    dashTimer = null
  }
  stopExtensionVersionPolling()
  stopExtensionInstalledWatch()
  stopAccessPolling()
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
})

// Sync PetInst when agents change
watch(() => props.agents, () => syncPets(), { deep: false })

// Notify the parent component when the selected Pet changes (used for "current Agent" to close the menu)
// immediate: sync once when the component mounts (clear any old selected state left in the parent component)
watch(activePetId, (id) => {
  emit('activePetChange', id || null)
}, { immediate: true })

// Notify the parent component when the selected Node changes (used for "Node" to close shortcuts and command panel)
// immediate: sync once when the component mounts (clear any old selected state left in the parent component)
watch(activeNodeId, (id) => {
  emit('activeNodeChange', id || null)
}, { immediate: true })

// For the parent component to write back the completion text: replace the @ and following search term with the completion value, and sync the DOM cursor
function insertCompletionText(agentId, text, cursorPos, hasAtSymbol) {
  const pet = petAgents.value.find(p => p.agentId === agentId)
  if (!pet) return
  const value = pet.inputText || ''
  let start
  let end
  if (hasAtSymbol && typeof cursorPos === 'number' && cursorPos >= 0 && cursorPos <= value.length) {
    // cursorPos points to the position of the @ symbol: replace this @
    start = cursorPos
    end = cursorPos + 1
  } else {
    // If there is no @ it can be deleted: insert at the recorded cursor position, append to the end if not recorded
    start = (typeof cursorPos === 'number' && cursorPos >= 0 && cursorPos <= value.length) ? cursorPos : value.length
    end = start
  }
  const inserted = `'${text}'`
  const next = value.substring(0, start) + inserted + value.substring(end)
  pet.inputText = next
  pet.typing = true
  const newPos = start + inserted.length
  requestAnimationFrame(() => {
    const el = stageRef.value && stageRef.value.querySelector(`[data-pet-input="${agentId}"]`)
    if (el) {
      el.value = next
      try { el.setSelectionRange(newPos, newPos) } catch (e) { /* ignore */ }
      el.focus()
    }
  })
}

// For the parent component to clear Node selection (e.g. after executing a Node action)
function closeActiveNode() {
  activeNodeId.value = null
}

// Called by the parent component: select Agent by direction (Ctrl+Alt+direction key)
// Has selection: based on the center of the currently selected Pet, choose the Pet in this direction that "has the smallest horizontal/vertical offset, then is nearest by vertical/horizontal distance".
// No selection: start from the opposite edge of this direction——→ take the first one on the far left, ← take the far right, ↓ take the topmost, ↑ take the bottommost,
//         then pressing the same direction repeatedly can advance one by one in this direction.
// Returning true means this request was already consumed (returns false when there is no Pet in the lobby, left to the parent component for area focus navigation)
function selectAgentInDirection(dir) {
  const pets = petAgents.value
  if (!pets.length) return false
  const cx = (pet) => pet.x + PET_W / 2
  const cy = (pet) => pet.y + PET_H / 2
  const current = pets.find(p => p.agentId === activePetId.value) || null

  let best = null
  let bestPrimary = Infinity
  let bestSecondary = Infinity
  for (const pet of pets) {
    if (current && pet.agentId === current.agentId) continue
    let primary
    let secondary
    if (!current) {
      // No selection: no direction filter, sort directly by "the opposite edge of this direction", take the first one
      // left → take the far right (x max); right → take the far left (x min); up → take the bottommost (y max); down → take the topmost (y min)
      if (dir === 'left') {
        primary = -cx(pet)
        secondary = cy(pet)
      } else if (dir === 'right') {
        primary = cx(pet)
        secondary = cy(pet)
      } else if (dir === 'up') {
        primary = -cy(pet)
        secondary = cx(pet)
      } else {
        primary = cy(pet)
        secondary = cx(pet)
      }
    } else {
      const dx = cx(pet) - cx(current)
      const dy = cy(pet) - cy(current)
      if (dir === 'left') {
        if (dx >= 0) continue
        primary = -dx
        secondary = Math.abs(dy)
      } else if (dir === 'right') {
        if (dx <= 0) continue
        primary = dx
        secondary = Math.abs(dy)
      } else if (dir === 'up') {
        if (dy >= 0) continue
        primary = -dy
        secondary = Math.abs(dx)
      } else {
        if (dy <= 0) continue
        primary = dy
        secondary = Math.abs(dx)
      }
    }
    if (primary < bestPrimary || (primary === bestPrimary && secondary < bestSecondary)) {
      best = pet
      bestPrimary = primary
      bestSecondary = secondary
    }
  }
  // No Pet in this direction: keep the current selection unchanged, but still give focus to the currently selected Pet's input box
  // (e.g. when there is only one Agent, or already at the edge of this direction, the keyboard navigation intent is still "active and input")
  if (!best) {
    if (current) focusPetInput(current.agentId, true)
    return true
  }
  // Same as clicking: select and expand the panel (only one at a time); after keyboard selection, focus the input box
  openPanel(best, true)
  return true
}

// Called by the parent component: select Node by direction (Ctrl+Shift+direction key)
// Has selection: based on the currently selected Node, choose the Node in this direction that "has the smallest horizontal/vertical offset, then is nearest by vertical/horizontal distance".
// No selection: start from the opposite edge of this direction——→ take the first one on the far left, ← take the far right, ↓ take the topmost, ↑ take the bottommost.
// Returning true means this request was already consumed (returns false when there is no Node in the lobby)
function selectNodeInDirection(dir) {
  const nodes = nodeItems.value
  if (!nodes.length) return false
  const current = nodes.find(n => n.node_id === activeNodeId.value) || null

  let best = null
  let bestPrimary = Infinity
  let bestSecondary = Infinity
  for (const node of nodes) {
    if (current && node.node_id === current.node_id) continue
    let primary
    let secondary
    if (!current) {
      // No selection: no direction filter, sort directly by "the opposite edge of this direction", take the first one
      if (dir === 'left') {
        primary = -node.x
        secondary = node.y
      } else if (dir === 'right') {
        primary = node.x
        secondary = node.y
      } else if (dir === 'up') {
        primary = -node.y
        secondary = node.x
      } else {
        primary = node.y
        secondary = node.x
      }
    } else {
      const dx = node.x - current.x
      const dy = node.y - current.y
      if (dir === 'left') {
        if (dx >= 0) continue
        primary = -dx
        secondary = Math.abs(dy)
      } else if (dir === 'right') {
        if (dx <= 0) continue
        primary = dx
        secondary = Math.abs(dy)
      } else if (dir === 'up') {
        if (dy >= 0) continue
        primary = -dy
        secondary = Math.abs(dx)
      } else {
        if (dy <= 0) continue
        primary = dy
        secondary = Math.abs(dx)
      }
    }
    if (primary < bestPrimary || (primary === bestPrimary && secondary < bestSecondary)) {
      best = node
      bestPrimary = primary
      bestSecondary = secondary
    }
  }
  // No Node in this direction: keep the current selection unchanged
  if (!best) return true
  activeNodeId.value = best.node_id
  return true
}

// Called by the parent component: rename Node (when nodeId is not passed, take the currently selected Node)
// Returning true means this request was already consumed (returns false when there is no Node or the popup layer is already open)
function renameActiveNode(nodeId) {
  const targetId = nodeId || activeNodeId.value
  if (!targetId) return false
  if (renameDialog.value.visible) return true
  const node = (props.nodes || []).find(n => n.node_id === targetId)
  openRenameDialog(targetId, (node && (node.short || node.name)) || targetId)
  return true
}

defineExpose({ insertCompletionText, toggleAgentOutput, isOutputHidden, openInstallExtensionDialog, openDaemonDialog, closeActivePanel, hideActiveOutputAndClose, closeActiveNode, renameActiveNode, selectAgentInDirection, selectNodeInDirection, toggleAllOutputs })
</script>

<style scoped>
.pet-lobby {
  position: absolute;
  inset: 0;
  overflow: hidden;
  border-radius: var(--tile-radius, 12px);
}

/* Floor-style background: perspective grid */
.pet-lobby-floor {
  position: absolute;
  inset: -20%;
  background-image:
    linear-gradient(rgba(32, 200, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(32, 200, 255, 0.08) 1px, transparent 1px);
  background-size: 56px 56px, 56px 56px;
  mask-image: radial-gradient(circle at 50% 55%, #000 0%, transparent 78%);
  -webkit-mask-image: radial-gradient(circle at 50% 55%, #000 0%, transparent 78%);
  animation: lobbyFloorDrift 40s linear infinite;
  pointer-events: none;
}

@keyframes lobbyFloorDrift {
  from { background-position: 0 0, 0 0; }
  to { background-position: 56px 56px, 56px 56px; }
}

/* Node and connection layer: above the floor, below the Pets, does not intercept interaction */
.pet-lobby-topology {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  /* The protagonist is the Agent: weaken the Node and connections overall, to avoid stealing the show */
  opacity: 0.4;
}

.pet-lobby-links {
  position: absolute;
  left: 0;
  top: 0;
  overflow: visible;
}

.lobby-link {
  stroke-linecap: round;
}

.lobby-link.is-flow {
  stroke-dasharray: 8 6;
  animation: lobby-flow 1.2s linear infinite;
}

@keyframes lobby-flow {
  to { stroke-dashoffset: -14; }
}

/* Node: server chassis shape (referencing the big-screen topology, but weakened overall to highlight the Agent) */
.lobby-node {
  /* The container layer as a whole has pointer-events: none (does not intercept Pet interaction), this spot individually restores Node clickability */
  pointer-events: auto;
  cursor: pointer;
  /* Default selection highlight when double-click is disabled */
  user-select: none;
  -webkit-user-select: none;
}
.lobby-node-body {
  transition: filter 0.15s ease;
}
/* Local execution plane Node (Browser extension / Local daemon service): display only, does not participate in Node click interaction */
.lobby-node.is-local {
  pointer-events: none;
}
.lobby-node.is-local .lobby-node-label {
  fill: rgba(180, 220, 240, 0.6);
}
.lobby-node.is-local .lobby-node-count {
  fill: rgba(150, 190, 210, 0.5);
}
/* Local execution plane curved connection */
.lobby-links-local .lobby-link {
  stroke-linecap: round;
}
/* Selected Node: chassis outline thickened and glowing + slightly enlarged, to clarify the target of the current Node action */
.lobby-node.active .lobby-node-body {
  stroke-width: 2.6;
  filter: drop-shadow(0 0 6px currentColor) brightness(1.25);
}
.lobby-node.active .lobby-node-label {
  fill: rgba(220, 245, 255, 0.95);
  font-weight: 600;
}
.lobby-node.active .lobby-node-count {
  fill: rgba(200, 235, 255, 0.8);
}

.lobby-node-led {
  filter: drop-shadow(0 0 2px currentColor);
  animation: lobby-led-blink 2.2s ease-in-out infinite;
}

@keyframes lobby-led-blink {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 0.25; }
}

.lobby-node-label {
  font-size: 11px;
  fill: rgba(180, 220, 240, 0.55);
  pointer-events: none;
}

.lobby-node-count {
  font-size: 10px;
  fill: rgba(150, 190, 210, 0.45);
  pointer-events: none;
}

.lobby-node-version {
  font-size: 9px;
  fill: rgba(150, 190, 210, 0.4);
  pointer-events: none;
}

/* Version and master inconsistent: mark red to indicate this Node is not updated */
.lobby-node-version.mismatch {
  fill: #ff5d6c;
  font-weight: 600;
}

.lobby-node.is-center .lobby-node-label {
  fill: rgba(255, 232, 154, 0.7);
}

.lobby-node.is-center .lobby-node-count {
  fill: rgba(255, 232, 154, 0.6);
  opacity: 0.9;
}

.lobby-node.is-center .lobby-node-version {
  fill: rgba(255, 232, 154, 0.5);
}

/* The Slogan above the floor: engraved in the ground, a weathered texture worn by years */
.pet-lobby-slogan {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%) perspective(600px) rotateX(52deg);
  transform-origin: center center;
  pointer-events: none;
  user-select: none;
  z-index: 1;
  opacity: 0.5;
}

.pet-lobby-slogan-text {
  display: block;
  font-size: clamp(28px, 5.2vw, 72px);
  font-weight: 800;
  letter-spacing: 0.22em;
  white-space: nowrap;
  /* The text itself: low-contrast gray-blue, like an engraving faded by the years */
  color: rgba(120, 160, 190, 0.32);
  /* Highlight on top + shadow below, creating an engraved recessed feel */
  text-shadow:
    0 1px 0 rgba(0, 0, 0, 0.55),
    0 -1px 1px rgba(150, 200, 230, 0.12),
    0 0 18px rgba(32, 200, 255, 0.08);
  /* Use noise/scratches mask to create mottled peeling */
  -webkit-mask-image:
    repeating-linear-gradient(96deg, #000 0 3px, rgba(0,0,0,0.35) 3px 5px, #000 5px 11px),
    radial-gradient(ellipse 140% 90% at 42% 46%, #000 30%, rgba(0,0,0,0.25) 62%, transparent 88%);
  -webkit-mask-composite: source-in;
  mask-image:
    repeating-linear-gradient(96deg, #000 0 3px, rgba(0,0,0,0.35) 3px 5px, #000 5px 11px),
    radial-gradient(ellipse 140% 90% at 42% 46%, #000 30%, rgba(0,0,0,0.25) 62%, transparent 88%);
  mask-composite: intersect;
  animation: lobbySloganWeather 9s ease-in-out infinite alternate;
}

/* Weathered feel: light and dark and wear slowly breathe, as if light and shadow pass over old floor tiles */
@keyframes lobbySloganWeather {
  from {
    opacity: 0.72;
    text-shadow:
      0 1px 0 rgba(0, 0, 0, 0.55),
      0 -1px 1px rgba(150, 200, 230, 0.12),
      0 0 18px rgba(32, 200, 255, 0.08);
  }
  to {
    opacity: 1;
    text-shadow:
      0 1px 0 rgba(0, 0, 0, 0.7),
      0 -1px 1px rgba(150, 200, 230, 0.2),
      0 0 26px rgba(32, 200, 255, 0.14);
  }
}

/* Overlay a very faint scratch/stain texture to enhance the aged look */
.pet-lobby-slogan::after {
  content: '';
  position: absolute;
  inset: -10% -6%;
  background:
    repeating-linear-gradient(78deg, transparent 0 6px, rgba(0, 0, 0, 0.18) 6px 7px, transparent 7px 15px),
    repeating-linear-gradient(-64deg, transparent 0 9px, rgba(180, 210, 230, 0.06) 9px 10px, transparent 10px 22px);
  mix-blend-mode: overlay;
  pointer-events: none;
}

.pet-lobby-glow {
  position: absolute;
  width: 50vmax;
  height: 50vmax;
  border-radius: 50%;
  filter: blur(48px);
  opacity: 0.4;
  pointer-events: none;
}
.pet-lobby-glow-a {
  top: -20%;
  left: -12%;
  background: radial-gradient(circle, rgba(32, 200, 255, 0.22) 0%, transparent 62%);
}
.pet-lobby-glow-b {
  bottom: -24%;
  right: -14%;
  background: radial-gradient(circle, rgba(54, 255, 124, 0.16) 0%, transparent 62%);
}

/* ===== Top-left corner instrument panel (current time + gateway address): same style as Node topology, weakened ===== */
.pet-lobby-dash {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 0;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(8, 18, 30, 0.55);
  border: 1px solid rgba(32, 200, 255, 0.18);
  backdrop-filter: blur(4px);
  pointer-events: none;
  user-select: none;
  opacity: 0.55;
  font-variant-numeric: tabular-nums;
}
.lobby-dash-time {
  font-size: 20px;
  line-height: 1.1;
  letter-spacing: 1px;
  color: rgba(180, 220, 240, 0.8);
}
.lobby-dash-date {
  margin-top: 2px;
  font-size: 10px;
  color: rgba(150, 190, 210, 0.5);
}
.lobby-dash-divider {
  height: 1px;
  margin: 7px 0 6px;
  background: linear-gradient(90deg, rgba(32, 200, 255, 0.28), transparent);
}
.lobby-dash-row {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  line-height: 1.6;
  color: rgba(150, 190, 210, 0.55);
}
.lobby-dash-label {
  flex: none;
  opacity: 0.75;
}
.lobby-dash-value {
  color: rgba(180, 220, 240, 0.7);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lobby-dash-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #8a9bb0;
  opacity: 0.7;
  flex: none;
}
/* Connection status colors: consistent with the top bar status dot semantics */
.lobby-dash-dot.is-online {
  background: #34d99b;
}
.lobby-dash-dot.is-connecting,
.lobby-dash-dot.is-reconnecting {
  background: #ffb347;
}
.lobby-dash-dot.is-offline {
  background: #ff5d6c;
}
/* Count of each Agent status: colored dot + number, compactly arranged */
.lobby-dash-agents {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}
.lobby-dash-agent-item {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.lobby-dash-agent-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  opacity: 0.8;
  flex: none;
}
.lobby-dash-agent-num {
  color: rgba(180, 220, 240, 0.7);
}

/* ===== Top-right corner switch group (roam + sprite display mode) ===== */
.pet-lobby-toggles {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 40;
  display: flex;
  align-items: center;
  gap: 8px;
}
.pet-lobby-roam-toggle,
.pet-lobby-display-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 12px;
  color: #d6f2ff;
  background: rgba(10, 24, 38, 0.86);
  border: 1px solid rgba(32, 200, 255, 0.4);
  border-radius: 999px;
  cursor: pointer;
  backdrop-filter: blur(6px);
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}
.pet-lobby-roam-toggle:hover,
.pet-lobby-display-toggle:hover {
  background: rgba(16, 40, 60, 0.95);
  border-color: rgba(32, 200, 255, 0.75);
}
.pet-lobby-roam-toggle.off,
.pet-lobby-display-toggle.off {
  color: #9fb4c4;
  border-color: rgba(120, 140, 160, 0.45);
}
.pet-lobby-roam-icon,
.pet-lobby-display-icon {
  font-size: 13px;
  line-height: 1;
}

/* Click: top space is limited, the switch group only shows icons, hides text */
@media (max-width: 768px) {
  .pet-lobby-toggles {
    gap: 6px;
  }
  .pet-lobby-roam-toggle,
  .pet-lobby-display-toggle {
    padding: 6px 8px;
  }
  .pet-lobby-roam-label,
  .pet-lobby-display-label {
    display: none;
  }
  .pet-lobby-roam-icon,
  .pet-lobby-display-icon {
    font-size: 15px;
  }
}

/* ===== Empty-state guide when there is no Agent ===== */
.pet-lobby-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 30;
  width: min(420px, 86vw);
  padding: 22px 24px;
  text-align: center;
  background: rgba(9, 16, 28, 0.86);
  border: 1px solid rgba(32, 200, 255, 0.28);
  border-radius: var(--tile-radius, 10px);
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}
.pet-lobby-empty-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-accent, #20c8ff);
  letter-spacing: 0.02em;
}
.pet-lobby-empty-desc {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.7;
  color: #b9cddd;
}
.pet-lobby-empty-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 16px;
}
.pet-lobby-empty-btn {
  padding: 8px 16px;
  font-size: 13px;
  font-family: inherit;
  color: #d6f2ff;
  background: rgba(10, 24, 38, 0.9);
  border: 1px solid rgba(32, 200, 255, 0.4);
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, filter 0.2s ease;
}
.pet-lobby-empty-btn:hover {
  background: rgba(16, 40, 60, 0.95);
  border-color: rgba(32, 200, 255, 0.8);
}
.pet-lobby-empty-btn.primary {
  color: #060911;
  font-weight: 700;
  background: var(--gradient-accent, linear-gradient(135deg, #20c8ff 0%, #36ff7c 100%));
  border-color: transparent;
}
.pet-lobby-empty-btn.primary:hover {
  filter: brightness(1.08);
}
.pet-lobby-empty-hint {
  margin-top: 14px;
  font-size: 12px;
  color: #8ba3b8;
}
.pet-lobby-empty-hint b {
  color: var(--color-accent, #20c8ff);
}
/* ===== Mini Pet ===== */
.lobby-pet {
  position: absolute;
  width: 72px;
  height: 82px;
  cursor: pointer;
  user-select: none;
  pointer-events: auto;
  /* Click: disable browser default touch gestures (scroll/zoom), otherwise dragging will be interrupted by system gestures */
  touch-action: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
  transition: filter 0.25s ease, opacity 0.25s ease;
  /* Each Pet establishes an independent stacking context, making "body + output/input box" participate in Z-index comparison as a whole,
     to avoid window A covering Pet B and window B covering Pet A in a crossing overlap */
  z-index: 1;
}
.lobby-pet:hover {
  filter: brightness(1.15);
}
.lobby-pet.active {
  z-index: 20;
}
/* When any Pet is active, the rest of the Pets and their output/input boxes dim, highlighting the current interaction target */
.lobby-pet.dimmed {
  opacity: 0.38;
  filter: brightness(0.55) saturate(0.6);
}
.lobby-pet.dimmed:hover {
  opacity: 0.7;
  filter: brightness(0.9) saturate(0.8);
}
.lobby-pet.dragging {
  cursor: grabbing;
  z-index: 20;
  filter: brightness(1.2);
}

.lobby-pet-inner {
  position: relative;
  width: 100%;
  height: 100%;
}

.lobby-pet-body {
  position: absolute;
  left: 50%;
  bottom: 12px;
  width: 52px;
  height: 46px;
  transform: translateX(-50%);
  animation: lobbyPetBob 2.6s ease-in-out infinite;
}

@keyframes lobbyPetBob {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(-3px); }
}

.lobby-pet-head {
  position: absolute;
  left: 50%;
  top: 0;
  width: 42px;
  height: 37px;
  transform: translateX(-50%);
  background: linear-gradient(160deg, #2ee6ff 0%, #1a9fd6 55%, #0e6f9e 100%);
  border-radius: 50% 50% 46% 46%;
  box-shadow: 0 0 10px rgba(32, 200, 255, 0.45), inset 0 -3px 6px rgba(0, 0, 0, 0.25),
    inset 0 2px 4px rgba(255, 255, 255, 0.18);
}

.lobby-pet-ear {
  position: absolute;
  top: -8px;
  width: 0;
  height: 0;
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-bottom: 12px solid #23b9e8;
  filter: drop-shadow(0 0 3px rgba(32, 200, 255, 0.5));
}
.lobby-pet-ear.l { left: 2px; transform: rotate(-18deg); }
.lobby-pet-ear.r { right: 2px; transform: rotate(18deg); }

.lobby-pet-eye {
  position: absolute;
  top: 14px;
  width: 7px;
  height: 8px;
  border-radius: 50%;
  background: #06131f;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.75);
  animation: lobbyPetBlink 4.2s infinite;
}
.lobby-pet-eye.l { left: 10px; }
.lobby-pet-eye.r { right: 10px; }

.lobby-pet-pupil {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: rgba(234, 252, 255, 0.9);
  transform: translate(-50%, -50%);
}

@keyframes lobbyPetBlink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

.lobby-pet-mouth {
  position: absolute;
  left: 50%;
  top: 27px;
  width: 10px;
  height: 5px;
  transform: translateX(-50%);
  border-bottom: 1.5px solid rgba(6, 19, 31, 0.75);
  border-radius: 0 0 4px 4px;
}

.lobby-pet-tail {
  position: absolute;
  right: -8px;
  bottom: 6px;
  width: 19px;
  height: 19px;
  border: 2px solid #23b9e8;
  border-color: #23b9e8 transparent transparent transparent;
  border-radius: 50%;
  transform-origin: 0% 100%;
  animation: lobbyPetTail 1.6s ease-in-out infinite;
  filter: drop-shadow(0 0 3px rgba(32, 200, 255, 0.45));
}

@keyframes lobbyPetTail {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(-16deg); }
}

.lobby-pet-shadow {
  position: absolute;
  left: 50%;
  bottom: 8px;
  width: 44px;
  height: 8px;
  transform: translateX(-50%);
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.35);
  filter: blur(2px);
  pointer-events: none;
}

/* Face direction flip */
.lobby-pet.face-left .lobby-pet-body {
  transform: translateX(-50%) scaleX(-1);
}

.lobby-pet-name {
  position: absolute;
  left: 50%;
  bottom: -4px;
  transform: translateX(-50%);
  /* Name shows in full: no truncation, no wrapping, allowed to overflow on both sides (centered, pointer-events: none so it does not block interaction) */
  max-width: none;
  white-space: nowrap;
  font-size: 11px;
  color: rgba(180, 220, 245, 0.85);
  text-shadow: 0 0 6px rgba(0, 0, 0, 0.6);
  pointer-events: none;
}

/* Working directory below the name: minor info, weakened display, truncate overly long paths */
.lobby-pet-dir {
  position: absolute;
  left: 50%;
  bottom: -17px;
  transform: translateX(-50%);
  max-width: 160px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 9px;
  color: rgba(150, 190, 215, 0.7);
  text-shadow: 0 0 6px rgba(0, 0, 0, 0.6);
  pointer-events: none;
}
/* Type icon: CodeAgent / regular Agent, kept consistent with the Sidebar list (SVG stroke linear) */
.lobby-pet-type {
  margin-right: 3px;
  font-size: 10px;
  line-height: 1;
  opacity: 0.9;
}

/* Lightweight distinction for CodeAgent: name tinted teal + a faint halo above the head (does not steal the show) */
.lobby-pet.is-code-agent .lobby-pet-name {
  color: rgba(150, 240, 220, 0.92);
}
.lobby-pet.is-code-agent .lobby-pet-head {
  box-shadow: 0 0 10px rgba(46, 230, 200, 0.5), inset 0 -3px 6px rgba(0, 0, 0, 0.25),
    inset 0 2px 4px rgba(255, 255, 255, 0.18);
}

/* Status light */
.lobby-pet-status {
  position: absolute;
  right: 4px;
  top: 4px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #6b8299;
  box-shadow: 0 0 6px rgba(0, 0, 0, 0.5);
}
.lobby-pet-status.running { background: #36ff7c; box-shadow: 0 0 8px rgba(54, 255, 124, 0.8); }
.lobby-pet-status.waiting_multi,
.lobby-pet-status.waiting_confirm,
.lobby-pet-status.waiting_single { background: #ffab3d; box-shadow: 0 0 8px rgba(255, 171, 61, 0.9); animation: lobbyStatusPulse 1.4s ease-in-out infinite; }
.lobby-pet-status.stopped { background: #6b8299; }

@keyframes lobbyStatusPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ===== Pet appearance by status ===== */

/* Running: blue, tail gently wagging, steady breathing */
.lobby-pet.status-running .lobby-pet-head {
  background: linear-gradient(160deg, #2ee6ff 0%, #1a9fd6 55%, #0e6f9e 100%);
}

/* Waiting for more input: amber, ears perked up, eyes wide open, halo pulsing */
.lobby-pet.status-waiting_multi .lobby-pet-head {
  background: linear-gradient(160deg, #ffd479 0%, #f2a52c 55%, #b76a0a 100%);
  box-shadow: 0 0 14px rgba(255, 171, 61, 0.7), inset 0 -3px 6px rgba(0, 0, 0, 0.25),
    inset 0 2px 4px rgba(255, 255, 255, 0.22);
  animation: lobbyPetWaitGlow 1.6s ease-in-out infinite;
}
.lobby-pet.status-waiting_multi .lobby-pet-ear {
  border-bottom-color: #f2a52c;
  filter: drop-shadow(0 0 4px rgba(255, 171, 61, 0.7));
}
.lobby-pet.status-waiting_multi .lobby-pet-ear.l { transform: rotate(-4deg); }
.lobby-pet.status-waiting_multi .lobby-pet-ear.r { transform: rotate(4deg); }
.lobby-pet.status-waiting_multi .lobby-pet-eye {
  width: 8px;
  height: 9px;
  animation: none;
}
.lobby-pet.status-waiting_multi .lobby-pet-tail {
  border-color: #f2a52c transparent transparent transparent;
  filter: drop-shadow(0 0 4px rgba(255, 171, 61, 0.6));
  animation-duration: 0.9s;
}
.lobby-pet.status-waiting_multi .lobby-pet-mouth {
  width: 8px;
  height: 7px;
  border: 1.5px solid rgba(6, 19, 31, 0.75);
  border-radius: 50%;
}

/* Waiting confirm (single line/confirm): orange-red, ears straight up, eyes wide, faster pulse */
.lobby-pet.status-waiting_single .lobby-pet-head,
.lobby-pet.status-waiting_confirm .lobby-pet-head {
  background: linear-gradient(160deg, #ff9d6b 0%, #f2603a 55%, #a82f14 100%);
  box-shadow: 0 0 16px rgba(255, 110, 70, 0.75), inset 0 -3px 6px rgba(0, 0, 0, 0.25),
    inset 0 2px 4px rgba(255, 255, 255, 0.22);
  animation: lobbyPetWaitGlow 1s ease-in-out infinite;
}
.lobby-pet.status-waiting_single .lobby-pet-ear,
.lobby-pet.status-waiting_confirm .lobby-pet-ear {
  border-bottom-color: #f2603a;
  filter: drop-shadow(0 0 4px rgba(255, 110, 70, 0.75));
}
.lobby-pet.status-waiting_single .lobby-pet-ear.l,
.lobby-pet.status-waiting_confirm .lobby-pet-ear.l { transform: rotate(0deg); }
.lobby-pet.status-waiting_single .lobby-pet-ear.r,
.lobby-pet.status-waiting_confirm .lobby-pet-ear.r { transform: rotate(0deg); }
.lobby-pet.status-waiting_single .lobby-pet-eye,
.lobby-pet.status-waiting_confirm .lobby-pet-eye {
  width: 9px;
  height: 10px;
  animation: none;
}
.lobby-pet.status-waiting_single .lobby-pet-pupil,
.lobby-pet.status-waiting_confirm .lobby-pet-pupil {
  width: 4px;
  height: 4px;
}
.lobby-pet.status-waiting_single .lobby-pet-tail,
.lobby-pet.status-waiting_confirm .lobby-pet-tail {
  border-color: #f2603a transparent transparent transparent;
  filter: drop-shadow(0 0 4px rgba(255, 110, 70, 0.65));
  animation-duration: 0.7s;
}
.lobby-pet.status-waiting_single .lobby-pet-mouth,
.lobby-pet.status-waiting_confirm .lobby-pet-mouth {
  width: 9px;
  height: 8px;
  border: 1.5px solid rgba(6, 19, 31, 0.8);
  border-radius: 50%;
}

/* Already stopped: gray-blue, eyes closed, tail still (usually not shown, kept as fallback) */
.lobby-pet.status-stopped .lobby-pet-head {
  background: linear-gradient(160deg, #8fa4b5 0%, #6b8299 55%, #47596b 100%);
  box-shadow: 0 0 6px rgba(120, 150, 175, 0.3), inset 0 -3px 6px rgba(0, 0, 0, 0.3);
}
.lobby-pet.status-stopped .lobby-pet-ear {
  border-bottom-color: #6b8299;
  filter: none;
}
.lobby-pet.status-stopped .lobby-pet-eye {
  height: 2px;
  border-radius: 2px;
  background: #06131f;
  animation: none;
}
.lobby-pet.status-stopped .lobby-pet-pupil { display: none; }
.lobby-pet.status-stopped .lobby-pet-tail {
  border-color: #6b8299 transparent transparent transparent;
  filter: none;
  animation: none;
}
.lobby-pet.status-stopped .lobby-pet-body { animation: none; }

@keyframes lobbyPetWaitGlow {
  0%, 100% { filter: brightness(1); }
  50% { filter: brightness(1.25); }
}

/* ===== Output bubble + input/confirm control stacked container ===== */
/* left / width / max-height dynamically calculated by JS (layoutPetStack), ensuring it always falls within the stage's visible area  */
.lobby-pet-stack {
  position: absolute;
  top: calc(100% + 4px);
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: default;
  z-index: 6;
  overflow-y: auto;
  overflow-x: hidden;
  touch-action: pan-y;
}
.lobby-pet-stack.stack-above {
  top: auto;
  bottom: calc(100% + 4px);
  flex-direction: column-reverse;
}

.lobby-pet-panel {
  width: 100%;
  background: rgba(10, 24, 38, 0.96);
  border: 1px solid rgba(32, 200, 255, 0.35);
  border-radius: 10px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.55), 0 0 16px rgba(32, 200, 255, 0.18);
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: default;
  /* The panel allows vertical touch scrolling (the Pet body already sets touch-action:none, needs to be restored here) */
  touch-action: pan-y;
}

/* OutputBubble（markdown） */
.lobby-pet-output-wrap {
  position: relative;
  width: 100%;
}
.lobby-pet-copy {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  font-size: 12px;
  line-height: 1;
  color: #9fd8ef;
  background: rgba(10, 24, 38, 0.85);
  border: 1px solid rgba(32, 200, 255, 0.35);
  border-radius: 6px;
  cursor: pointer;
  opacity: 0.35;
  transition: opacity 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}
.lobby-pet-output-wrap:hover .lobby-pet-copy {
  opacity: 1;
}
.lobby-pet-copy:hover {
  color: #dff1fb;
  border-color: rgba(32, 200, 255, 0.7);
}
.lobby-pet-copy.copied {
  opacity: 1;
  color: #34d99b;
  border-color: rgba(52, 217, 155, 0.7);
}
.lobby-pet-export {
  position: absolute;
  top: 6px;
  right: 32px;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  font-size: 12px;
  line-height: 1;
  color: #9fd8ef;
  background: rgba(10, 24, 38, 0.85);
  border: 1px solid rgba(32, 200, 255, 0.35);
  border-radius: 6px;
  cursor: pointer;
  opacity: 0.35;
  transition: opacity 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}
.lobby-pet-output-wrap:hover .lobby-pet-export {
  opacity: 1;
}
.lobby-pet-export:hover {
  color: #dff1fb;
  border-color: rgba(32, 200, 255, 0.7);
}
.lobby-pet-export.exported {
  opacity: 1;
  color: #34d99b;
  border-color: rgba(52, 217, 155, 0.7);
}
.lobby-pet-output {
  width: 100%;
  box-sizing: border-box;
  min-height: 120px;
  max-height: 60vh;
  overflow-y: auto;
  touch-action: pan-y;
  background: rgba(10, 24, 38, 0.94);
  border: 1px solid rgba(32, 200, 255, 0.28);
  border-radius: 10px;
  padding: 10px 32px 10px 12px;
  word-break: break-word;
  box-shadow: 0 8px 26px rgba(0, 0, 0, 0.5);
  font-family: 'Consolas', 'Microsoft YaHei', sans-serif;
}
/* Markdown text layout reuses the global .message-body.markdown-content styles, kept consistent with the Panel */

/* InputRow */
.lobby-pet-input-row {
  display: flex;
  align-items: flex-end;
  gap: 6px;
}
/* Click: the multi-line input box and buttons form two lines, to avoid buttons squeezing the input box width */
@media (max-width: 768px) {
  .lobby-pet-input-row-multi {
    flex-wrap: wrap;
  }
  .lobby-pet-input-row-multi .lobby-pet-textarea {
    flex: 1 1 100%;
  }
  .lobby-pet-input-row-multi .lobby-pet-at,
  .lobby-pet-input-row-multi .lobby-pet-complete,
  .lobby-pet-input-row-multi .lobby-pet-send {
    flex: 0 0 auto;
  }
  /* Button row right aligned: push the first button after the line break to the right, the rest follow it  */
  .lobby-pet-input-row-multi > button:first-of-type {
    margin-left: auto;
  }
}
.lobby-pet-textarea,
.lobby-pet-input {
  flex: 1;
  min-width: 0;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid rgba(32, 200, 255, 0.3);
  border-radius: 6px;
  color: #e6f6ff;
  font-size: 12px;
  font-family: inherit;
  padding: 5px 7px;
  resize: none;
  outline: none;
  /* The input box restores touch selection/scrolling (the Pet body already sets touch-action:none) */
  touch-action: auto;
}
.lobby-pet-textarea:focus,
.lobby-pet-input:focus {
  border-color: rgba(32, 200, 255, 0.7);
  box-shadow: 0 0 8px rgba(32, 200, 255, 0.25);
}
.lobby-pet-send {
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border-radius: 6px;
  border: 1px solid rgba(32, 200, 255, 0.4);
  background: rgba(32, 200, 255, 0.15);
  color: #7ee7ff;
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
}
.lobby-pet-send:hover { background: rgba(32, 200, 255, 0.3); }

.lobby-pet-complete {
  flex: 0 0 auto;
  height: 30px;
  padding: 0 8px;
  border-radius: 6px;
  border: 1px solid rgba(54, 255, 124, 0.4);
  background: rgba(54, 255, 124, 0.15);
  color: #a6ffcb;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}
.lobby-pet-complete:hover { background: rgba(54, 255, 124, 0.3); }

/* Click "@" button: same size as the Done button, convenient for touchscreen clicking */
.lobby-pet-at {
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border-radius: 6px;
  border: 1px solid rgba(32, 200, 255, 0.4);
  background: rgba(32, 200, 255, 0.15);
  color: #7ee7ff;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}
.lobby-pet-at:hover { background: rgba(32, 200, 255, 0.3); }

/* ConfirmBubble */
.lobby-pet-confirm {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.lobby-pet-confirm-msg {
  font-size: 12px;
  color: #ffd79a;
  background: rgba(255, 171, 61, 0.12);
  border-radius: 6px;
  padding: 6px 8px;
}
.lobby-pet-confirm-actions {
  display: flex;
  gap: 6px;
}
/* Default button always on the right: when default-yes, "Confirm" is on the right, otherwise "Cancel" is on the right  */
.lobby-pet-confirm-actions .lobby-pet-confirm-btn.yes { order: 1; }
.lobby-pet-confirm-actions .lobby-pet-confirm-btn.no { order: 2; }
.lobby-pet-confirm-actions.default-yes .lobby-pet-confirm-btn.yes { order: 2; }
.lobby-pet-confirm-actions.default-yes .lobby-pet-confirm-btn.no { order: 1; }
.lobby-pet-confirm-btn {
  flex: 1;
  padding: 5px 0;
  border-radius: 6px;
  border: 1px solid transparent;
  cursor: pointer;
  font-size: 12px;
}
.lobby-pet-confirm-btn.yes {
  background: rgba(54, 255, 124, 0.18);
  border-color: rgba(54, 255, 124, 0.5);
  color: #a6ffcb;
}
.lobby-pet-confirm-btn.no {
  background: rgba(255, 90, 90, 0.15);
  border-color: rgba(255, 90, 90, 0.45);
  color: #ffb3b3;
}
/* Agent right-click menu: actions for the current Agent */
.lobby-context-menu {
  position: absolute;
  z-index: 60;
  min-width: 300px;
  max-width: 380px;
  max-height: 60vh;
  overflow-y: auto;
  padding: 4px;
  border-radius: 10px;
  background: rgba(12, 22, 34, 0.96);
  border: 1px solid rgba(32, 200, 255, 0.35);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}
.lobby-context-title {
  padding: 6px 10px 8px;
  font-size: 12px;
  font-weight: 600;
  color: #9fe4ff;
  border-bottom: 1px solid rgba(32, 200, 255, 0.18);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* Menu items arranged in two columns, to avoid a single column being too long  */
.lobby-context-items {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px;
}
.lobby-context-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 10px;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: #d7e8f5;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}
.lobby-context-item:hover:not(:disabled) {
  background: rgba(32, 200, 255, 0.16);
}
.lobby-context-item:disabled {
  opacity: 0.4;
  cursor: default;
}
.lobby-context-icon {
  width: 18px;
  text-align: center;
}
.lobby-context-label {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Node rename popup layer */
/* Same z-index 3000 as other popup layers (CommandPanel/Settings, etc.); PetLobby is after them in the DOM,
    when the z-index is the same, those appearing later are on top, so they can cover the CommandPanel, ensuring that popup layers visible when triggered from the CommandPanel can be input */
.lobby-rename-mask {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(4, 10, 18, 0.55);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
}
.lobby-rename-dialog {
  width: min(360px, 86vw);
  padding: 16px;
  border-radius: 12px;
  background: rgba(12, 22, 34, 0.98);
  border: 1px solid rgba(32, 200, 255, 0.35);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.55);
}
.lobby-rename-title {
  font-size: 14px;
  font-weight: 600;
  color: #9fe4ff;
}
.lobby-rename-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #7f93a6;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.lobby-rename-input {
  width: 100%;
  margin-top: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(32, 200, 255, 0.3);
  background: rgba(6, 14, 24, 0.9);
  color: #d7e8f5;
  font-size: 13px;
  outline: none;
  box-sizing: border-box;
}
.lobby-rename-input:focus {
  border-color: rgba(32, 200, 255, 0.7);
}
.lobby-rename-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
.lobby-rename-btn {
  padding: 6px 16px;
  border-radius: 8px;
  border: 1px solid transparent;
  font-size: 13px;
  cursor: pointer;
}
.lobby-rename-btn.cancel {
  background: transparent;
  border-color: rgba(255, 255, 255, 0.18);
  color: #b6c6d4;
}
.lobby-rename-btn.cancel:hover {
  background: rgba(255, 255, 255, 0.08);
}
.lobby-rename-btn.ok {
  background: rgba(32, 200, 255, 0.9);
  color: #04121c;
  font-weight: 600;
}
.lobby-rename-btn.ok:hover {
  background: rgba(32, 200, 255, 1);
}
.lobby-rename-btn.ok:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
/* Buttons implemented with <a> (e.g. "Go to download page"): remove the underline and keep layout consistent with buttons */
a.lobby-rename-btn {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
  box-sizing: border-box;
}

/* Install browser extension popup layer: larger than the generic popup layer, ensuring the high-risk tips are fully readable without scrolling */
.lobby-install-dialog {
  width: min(760px, 94vw);
  max-height: 92vh;
  overflow-y: auto;
  padding: 20px 24px;
  border-radius: 12px;
  background: rgba(12, 22, 34, 0.98);
  border: 1px solid rgba(32, 200, 255, 0.35);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.55);
}
.lobby-install-steps {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.lobby-install-step {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12.5px;
  line-height: 1.6;
  color: #c3d6e4;
}
.lobby-install-step-no {
  flex: none;
  width: 18px;
  height: 18px;
  margin-top: 1px;
  border-radius: 50%;
  background: rgba(32, 200, 255, 0.18);
  border: 1px solid rgba(32, 200, 255, 0.5);
  color: #9fe4ff;
  font-size: 11px;
  text-align: center;
  line-height: 16px;
}
.lobby-install-step-text code {
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(6, 14, 24, 0.9);
  color: #9fe4ff;
  font-size: 12px;
}
.lobby-install-error {
  margin-top: 12px;
  font-size: 12px;
  color: #ff8b96;
}

/* Install extension button: red dot indicator when there is a new version (positioned at the button's top-right corner) */
.pet-lobby-install-toggle {
  position: relative;
}
.pet-lobby-update-dot {
  position: absolute;
  top: -2px;
  right: -2px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ff5d6c;
  box-shadow: 0 0 0 2px rgba(10, 24, 38, 0.86);
}
/* Version info and upgrade tip inside the popup layer */
.lobby-install-version {
  margin-top: 12px;
  font-size: 12px;
  color: #7f93a6;
}
.lobby-install-update {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 12.5px;
  line-height: 1.6;
  color: #ffd7a1;
  background: rgba(255, 170, 60, 0.12);
  border: 1px solid rgba(255, 170, 60, 0.4);
}
.lobby-install-update-icon {
  flex: none;
  color: #ffb347;
}
/* Risk tips and disclaimer inside the DownloadModal (height-sensitive permissions) */
.lobby-install-risk {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.65;
  color: #ffc9cf;
  background: rgba(255, 70, 90, 0.12);
  border: 1px solid rgba(255, 70, 90, 0.55);
  box-shadow: 0 0 0 1px rgba(255, 70, 90, 0.15) inset;
}
.lobby-install-risk-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #ff8b96;
}
.lobby-install-risk-icon {
  flex: none;
  font-size: 14px;
}
.lobby-install-risk-body {
  margin-top: 8px;
}
.lobby-install-risk-body p {
  margin: 0 0 6px;
}
.lobby-install-risk-body ul {
  margin: 0 0 6px;
  padding-left: 18px;
}
.lobby-install-risk-body li {
  margin-bottom: 2px;
}
.lobby-install-risk-body code {
  padding: 0 3px;
  border-radius: 3px;
  font-size: 11px;
  color: #ffd7dc;
  background: rgba(255, 70, 90, 0.18);
}
.lobby-install-risk-body strong {
  color: #ffb0b8;
}
.lobby-install-risk-warn {
  color: #ff9aa5;
}
.lobby-group-list {
  max-height: 220px;
  overflow-y: auto;
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.lobby-group-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: #d7e8f5;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
}
.lobby-group-item:hover {
  background: rgba(32, 200, 255, 0.16);
  border-color: rgba(32, 200, 255, 0.5);
}
.lobby-group-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lobby-group-count {
  flex: none;
  font-size: 12px;
  color: #7f93a6;
}
.lobby-group-empty {
  padding: 8px 2px;
  font-size: 12px;
  color: #7f93a6;
}
.lobby-group-create {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
.lobby-group-create .lobby-rename-input {
  margin-top: 0;
  flex: 1;
}
.lobby-group-create .lobby-rename-btn {
  flex: none;
  white-space: nowrap;
}
</style>
