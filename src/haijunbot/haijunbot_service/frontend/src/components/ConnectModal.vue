<template>
  <div class="modal-overlay connect-overlay" v-if="visible">
    <div class="modal connect-modal">
      <div class="brand-panel">
        <div class="brand-header">
          <div class="brand-logo-wrap">
            <img src="/icons/haijunbot-pet.svg" alt="HaijunBot" class="brand-logo" />
          </div>
          <div class="brand-title">
            <h1>HAIJUNBOT</h1>
            <p>Taking AI from "working alone" to "working together"</p>
          </div>
        </div>
        <div class="quadrants">
          <div class="quadrant">
            <div class="quadrant-name">Single User, Single Agent</div>
            <div class="quadrant-value">Self-sufficient</div>
            <div class="quadrant-cap">Symbol-level code understanding · Impact analysis · Unattended operation · Cross-validation</div>
          </div>
          <div class="quadrant">
            <div class="quadrant-name">Single User, Multiple Agents</div>
            <div class="quadrant-value">One person drives a team</div>
            <div class="quadrant-cap">Orchestration network · Inter-agent communication · Multi-panel operations</div>
          </div>
          <div class="quadrant">
            <div class="quadrant-name">Multiple Users, Single Agent</div>
            <div class="quadrant-value">Team shares one AI</div>
            <div class="quadrant-cap">Multi-user authentication · ACL permissions · Shared collaboration · Chat room</div>
          </div>
          <div class="quadrant">
            <div class="quadrant-name">Multiple Users, Multiple Agents</div>
            <div class="quadrant-value">Distributed collaboration network</div>
            <div class="quadrant-cap">Multi-node multi-gateway · Cross-node communication · Node-level operations</div>
          </div>
        </div>
      </div>
      <div class="form-panel">
        <h2>Connect to HaijunBot</h2>
        <div v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </div>
        <div class="form-group">
          <label>Username</label>
          <input ref="usernameInput" :value="username" @input="$emit('update:username', $event.target.value)" type="text" placeholder="Enter admin for first-time use" />
        </div>
        <div class="form-group">
          <label>Password</label>
          <input :value="password" @input="$emit('update:password', $event.target.value)" type="password" placeholder="Enter password" @keydown.enter="$emit('connect')" />
        </div>
        <div class="form-group">
          <label>Gateway Address</label>
          <input :value="gatewayUrl" @input="$emit('update:gatewayUrl', $event.target.value)" placeholder="ws://current-domain:8000 or wss://example.com:8000" />
        </div>
        <button class="primary-btn" @click="$emit('connect')" :disabled="connecting">
          {{ connecting ? 'Connecting...' : 'Connect' }}
        </button>
      </div>
      <div class="quickstart">
          <button class="quickstart-toggle" type="button" @click="showQuickStart = !showQuickStart">
            <span>Quick Start: Installation & Deployment</span>
            <span class="quickstart-arrow" :class="{ open: showQuickStart }">▾</span>
          </button>
          <div v-show="showQuickStart" class="quickstart-body">
            <div class="qs-step">
              <div class="qs-step-title"><span class="qs-step-no">1</span>Install HaijunBot</div>
              <pre class="qs-code"><code>bash -c "$(curl -fsSL https://raw.githubusercontent.com/takebox/HaijunBot/main/scripts/quick-install.sh)"</code></pre>
              <div class="qs-hint">Users in China can replace the domain with gitee.com/takebox/HaijunBot</div>
            </div>
            <div class="qs-step">
              <div class="qs-step-title"><span class="qs-step-no">2</span>Configure Model</div>
              <pre class="qs-code"><code>hqc</code></pre>
              <div class="qs-hint">Interactive configuration of API Key, models and model groups</div>
            </div>
            <div class="qs-step">
              <div class="qs-step-title"><span class="qs-step-no">3</span>Start Agent</div>
              <pre class="qs-code"><code>hjb   # General-purpose Agent
hca   # Code Agent</code></pre>
              <div class="qs-hint">hjb is suitable for analysis, planning, and execution; hca specializes in reading code / modifying code / running validation</div>
            </div>
            <div class="qs-step">
              <div class="qs-step-title"><span class="qs-step-no">4</span>Start Master Service</div>
              <div class="qs-hint">The service starts in master or child mode (default master). Single-machine deployment only requires starting master, install as a systemd service:</div>
              <pre class="qs-code"><code>haijunbot-service install --node-mode master \
  --gateway-host 0.0.0.0 --gateway-port 8000 \
  --frontend-host 0.0.0.0 --frontend-port 5173
haijunbot-service start master</code></pre>
              <div class="qs-hint">Listens on 127.0.0.1:8000 (gateway) and 127.0.0.1:5173 (frontend) by default, adjustable via --gateway-host / --gateway-port / --frontend-host / --frontend-port; if --node-secret is not specified, one is auto-generated and saved, obtainable from top bar "Admin" > "Node Connection Secret" after startup</div>
            </div>
            <div class="qs-step">
              <div class="qs-step-title"><span class="qs-step-no">5</span>Get Initial Password and Connect</div>
              <div class="qs-hint">On first startup, a random admin password is auto-generated and printed to the service log; run <code>journalctl --user -u haijunbot-master -f</code> to view it.</div>
              <div class="qs-hint">Fill in username <code>admin</code> with the above password and gateway address on the right to enter.</div>
            </div>
            <div class="qs-step">
              <div class="qs-step-title"><span class="qs-step-no">6</span>Change admin Password</div>
              <div class="qs-hint"><b>Please change the admin password immediately after first login</b>: change it in "Settings > Change Password" (admins can also reset it from top bar "Admin" > "User Management").</div>
            </div>

            <div class="qs-sub">Distributed Deployment</div>
            <div class="topo">
              <div class="topo-node master">
                <div class="topo-node-title">Master Node</div>
                <div class="topo-node-sub">Unified entry · Scheduling · Multi-user</div>
              </div>
              <div class="topo-links">
                <span class="topo-line"></span>
                <span class="topo-line"></span>
                <span class="topo-line"></span>
              </div>
              <div class="topo-children">
                <div class="topo-node child"><div class="topo-node-title">Child 1</div><div class="topo-node-sub">Run Agents</div></div>
                <div class="topo-node child"><div class="topo-node-title">Child 2</div><div class="topo-node-sub">Run Agents</div></div>
                <div class="topo-node child"><div class="topo-node-title">Child N</div><div class="topo-node-sub">Run Agents</div></div>
              </div>
            </div>
            <div class="qs-hint">Master provides a unified entry point and scheduling; Child connects to Master and runs Agents on it, enabling cross-node task distribution.</div>
            <div class="qs-step">
              <div class="qs-step-title"><span class="qs-step-no">C</span>Child: Install and Start</div>
              <pre class="qs-code"><code>haijunbot-service install --node-mode child \
  --node-id worker-01 \
  --master-url ws://master-host:8000 \
  --node-secret your_secret_key
haijunbot-service start child</code></pre>
              <div class="qs-hint">node-id must be unique; node-secret must match the Master; child does not start the frontend, only master provides the frontend page</div>
            </div>
            <div class="qs-hint"><b>Switch mode</b>: use <code>haijunbot-service switch master|child</code> to switch (automatically stops the other mode and activates the target mode).</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'

const props = defineProps({
  visible: Boolean,
  connecting: Boolean,
  errorMessage: String,
  gatewayUrl: String,
  password: String,
  username: String
})

defineEmits(['update:visible', 'update:gatewayUrl', 'update:password', 'update:username', 'connect'])

const showQuickStart = ref(false)

// Username input ref: auto-focus when login screen opens for convenient input
const usernameInput = ref(null)
watch(
  () => props.visible,
  (val) => {
    if (val) nextTick(() => usernameInput.value?.focus())
  }
)
</script>

<style scoped>
.modal-overlay.connect-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100%;
  height: var(--app-height, 100dvh);
  background: var(--color-bg-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  box-sizing: border-box;
  overflow: hidden;
  /* Extend beyond safe area to prevent underlying page from showing through on rounded corners/notches */
  margin: calc(-1 * env(safe-area-inset-top, 0px)) calc(-1 * env(safe-area-inset-right, 0px))
          calc(-1 * env(safe-area-inset-bottom, 0px)) calc(-1 * env(safe-area-inset-left, 0px));
  padding: calc(20px + env(safe-area-inset-top, 0px)) calc(20px + env(safe-area-inset-right, 0px))
           calc(20px + env(safe-area-inset-bottom, 0px)) calc(20px + env(safe-area-inset-left, 0px));
}

/* Deep space background: radial glow + grid texture */
.modal-overlay.connect-overlay::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 18% 22%, rgba(32, 200, 255, 0.16), transparent 45%),
    radial-gradient(circle at 82% 78%, rgba(54, 255, 124, 0.10), transparent 45%);
  pointer-events: none;
}

.modal-overlay.connect-overlay::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(32, 200, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(32, 200, 255, 0.05) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: radial-gradient(circle at 50% 50%, #000 0%, transparent 78%);
  -webkit-mask-image: radial-gradient(circle at 50% 50%, #000 0%, transparent 78%);
  pointer-events: none;
}

.modal {
  position: relative;
  z-index: 1;
  background: rgba(9, 16, 28, 0.86);
  border: 1px solid var(--color-border-subtle);
  border-radius: 16px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(32, 200, 255, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  width: 100%;
  max-width: 880px;
  display: flex;
  flex-wrap: wrap;
  max-height: calc(var(--app-height, 100dvh) - 40px);
  overflow-y: auto;
  animation: cm-pop 0.42s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes cm-pop {
  from { opacity: 0; transform: translateY(14px) scale(0.985); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.brand-panel {
  position: relative;
  flex: 1;
  min-width: 0;
  padding: 40px 34px;
  background:
    linear-gradient(160deg, rgba(32, 200, 255, 0.10) 0%, transparent 42%),
    rgba(6, 9, 17, 0.55);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 30px;
  overflow: hidden;
}

/* Dynamic grid background */
.brand-panel::before {
  content: '';
  position: absolute;
  inset: -50%;
  background-image:
    linear-gradient(rgba(32, 200, 255, 0.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(32, 200, 255, 0.07) 1px, transparent 1px);
  background-size: 34px 34px;
  transform: perspective(420px) rotateX(52deg) translateY(-6%);
  mask-image: radial-gradient(ellipse 70% 60% at 50% 40%, #000 30%, transparent 78%);
  -webkit-mask-image: radial-gradient(ellipse 70% 60% at 50% 40%, #000 30%, transparent 78%);
  animation: grid-drift 22s linear infinite;
  pointer-events: none;
}

/* Breathing glow */
.brand-panel::after {
  content: '';
  position: absolute;
  top: -30%;
  left: -20%;
  width: 90%;
  height: 90%;
  background: radial-gradient(circle, rgba(32, 200, 255, 0.16), transparent 62%);
  filter: blur(28px);
  animation: aurora-breathe 9s ease-in-out infinite;
  pointer-events: none;
}

.brand-panel > * {
  position: relative;
  z-index: 1;
}

@keyframes grid-drift {
  from { background-position: 0 0, 0 0; }
  to { background-position: 34px 34px, 34px 34px; }
}

@keyframes aurora-breathe {
  0%, 100% { opacity: 0.55; transform: scale(1) translate(0, 0); }
  50% { opacity: 1; transform: scale(1.12) translate(6%, 4%); }
}

.brand-header {
  display: flex;
  align-items: center;
  gap: 16px;
  animation: brand-rise 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes brand-rise {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.brand-logo-wrap {
  position: relative;
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.brand-logo-wrap::before {
  content: '';
  position: absolute;
  inset: -6px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(32, 200, 255, 0.35), transparent 68%);
  filter: blur(4px);
  animation: logo-halo 3.6s ease-in-out infinite;
}

@keyframes logo-halo {
  0%, 100% { opacity: 0.7; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.14); }
}

.brand-logo {
  position: relative;
  width: 46px;
  height: 46px;
  object-fit: contain;
  flex-shrink: 0;
  filter: drop-shadow(0 0 10px rgba(32, 200, 255, 0.55));
}

.brand-title h1 {
  margin: 0;
  font-size: 26px;
  font-weight: 800;
  letter-spacing: 0.14em;
  background: linear-gradient(100deg, #20c8ff 0%, #7ee7ff 28%, #36ff7c 52%, #20c8ff 78%);
  background-size: 220% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
  animation: title-sheen 6s linear infinite;
}

@keyframes title-sheen {
  from { background-position: 0% 50%; }
  to { background-position: 220% 50%; }
}

.brand-title p {
  margin: 6px 0 0 0;
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}

.quadrants {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.quadrant {
  position: relative;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(18, 30, 50, 0.45);
  border: 1px solid var(--color-border-subtle);
  border-left: 2px solid var(--color-accent);
  overflow: hidden;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease,
    background 0.2s ease;
  animation: quadrant-in 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.quadrant:nth-child(1) { animation-delay: 0.10s; }
.quadrant:nth-child(2) { animation-delay: 0.18s; }
.quadrant:nth-child(3) { animation-delay: 0.26s; }
.quadrant:nth-child(4) { animation-delay: 0.34s; }

/* Highlight sweep on hover */
.quadrant::after {
  content: '';
  position: absolute;
  top: 0;
  left: -60%;
  width: 45%;
  height: 100%;
  background: linear-gradient(100deg, transparent, rgba(32, 200, 255, 0.16), transparent);
  transform: skewX(-18deg);
  transition: left 0.55s ease;
  pointer-events: none;
}

.quadrant:hover::after {
  left: 120%;
}

@keyframes quadrant-in {
  from { opacity: 0; transform: translateX(-10px); }
  to { opacity: 1; transform: translateX(0); }
}

.quadrant:hover {
  transform: translateX(3px) scale(1.012);
  background: rgba(32, 200, 255, 0.08);
  border-color: var(--color-border);
  box-shadow: 0 6px 22px rgba(0, 120, 190, 0.22), 0 0 0 1px rgba(32, 200, 255, 0.18);
}

.quadrant-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.quadrant-value {
  margin-top: 2px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-success);
}

.quadrant-cap {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}

.form-panel {
  width: 400px;
  flex-shrink: 0;
  padding: 40px 34px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-left: 1px solid var(--color-border-subtle);
  background: rgba(6, 9, 17, 0.35);
}

.connect-modal h2 {
  margin: 0 0 24px 0;
  font-size: 21px;
  font-weight: 600;
  color: var(--color-text-primary);
  letter-spacing: -0.02em;
}

.error-message {
  background: var(--color-error-subtle);
  border: 1px solid var(--color-error);
  border-radius: var(--tile-radius);
  padding: 12px;
  margin-bottom: 16px;
  color: var(--color-error);
  font-size: 14px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary);
  letter-spacing: 0.01em;
}

.form-group input {
  width: 100%;
  padding: 11px 14px;
  background: rgba(6, 9, 17, 0.85);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--tile-radius);
  color: var(--color-text-primary);
  font-size: 14px;
  box-sizing: border-box;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.form-group input:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px rgba(32, 200, 255, 0.14);
}

.form-group input::placeholder {
  color: var(--color-text-secondary);
}

.primary-btn {
  position: relative;
  width: 100%;
  padding: 11px 20px;
  background: var(--gradient-accent);
  background-size: 200% 100%;
  border: none;
  border-radius: var(--tile-radius);
  color: #060911;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.02em;
  cursor: pointer;
  margin-top: 8px;
  overflow: hidden;
  box-shadow: 0 6px 20px rgba(32, 200, 255, 0.28);
  transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease;
  animation: btn-sheen 4.5s ease-in-out infinite;
}

@keyframes btn-sheen {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}

.primary-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  filter: brightness(1.06);
  box-shadow: 0 10px 28px rgba(32, 200, 255, 0.4);
}

.primary-btn:active:not(:disabled) {
  transform: translateY(0);
}

.primary-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Quick start */
.quickstart {
  flex-basis: 100%;
  border-top: 1px solid var(--color-border-subtle);
  padding: 14px 34px 20px;
}

.quickstart-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: transparent;
  border: none;
  padding: 4px 0;
  color: var(--color-accent);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.quickstart-arrow {
  transition: transform 0.2s ease;
}

.quickstart-arrow.open {
  transform: rotate(180deg);
}

.quickstart-body {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-right: 4px;
}

.qs-step-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 6px;
}

.qs-step-no {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-accent-subtle);
  color: var(--color-accent);
  font-size: 11px;
  flex-shrink: 0;
}

.qs-code {
  margin: 0;
  padding: 9px 11px;
  background: rgba(0, 0, 0, 0.45);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--tile-radius-xs);
  overflow-x: auto;
}

.qs-code code {
  font-family: 'Consolas', 'Microsoft YaHei', monospace;
  font-size: 12px;
  color: var(--color-success);
  white-space: pre;
}

.qs-hint {
  margin-top: 5px;
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}

/* Distributed topology diagram */
.qs-sub {
  margin-top: 4px;
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-primary);
  letter-spacing: 0.02em;
}

.topo {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 14px 10px;
  border-radius: var(--tile-radius);
  background: rgba(0, 0, 0, 0.28);
  border: 1px solid var(--color-border-subtle);
  overflow: hidden;
}

.topo-node {
  padding: 8px 14px;
  border-radius: 8px;
  text-align: center;
  min-width: 96px;
}

.topo-node-title {
  font-size: 12px;
  font-weight: 700;
}

.topo-node-sub {
  margin-top: 2px;
  font-size: 10px;
  color: var(--color-text-secondary);
}

.topo-node.master {
  background: var(--color-accent-subtle);
  border: 1px solid var(--color-accent);
  color: var(--color-accent);
  box-shadow: 0 0 0 0 rgba(32, 200, 255, 0.5);
  animation: topo-pulse 2.4s ease-in-out infinite;
}

.topo-node.child {
  background: rgba(18, 30, 50, 0.7);
  border: 1px solid var(--color-border-subtle);
  color: var(--color-text-primary);
  animation: topo-fade-in 0.5s ease both;
}

.topo-node.child:nth-child(1) { animation-delay: 0.05s; }
.topo-node.child:nth-child(2) { animation-delay: 0.2s; }
.topo-node.child:nth-child(3) { animation-delay: 0.35s; }

.topo-links {
  display: flex;
  gap: 64px;
  height: 22px;
  align-items: flex-start;
}

.topo-line {
  width: 1px;
  height: 100%;
  background: linear-gradient(180deg, var(--color-accent), rgba(32, 200, 255, 0.15));
  transform-origin: top;
  animation: topo-flow 1.6s ease-in-out infinite;
}

.topo-line:nth-child(2) { animation-delay: 0.25s; }
.topo-line:nth-child(3) { animation-delay: 0.5s; }

.topo-children {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
}

@keyframes topo-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(32, 200, 255, 0.45); }
  50% { box-shadow: 0 0 0 6px rgba(32, 200, 255, 0); }
}

@keyframes topo-flow {
  0%, 100% { opacity: 0.35; transform: scaleY(0.75); }
  50% { opacity: 1; transform: scaleY(1); }
}

@keyframes topo-fade-in {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .modal-overlay.connect-overlay {
    padding: calc(16px + env(safe-area-inset-top, 0px)) calc(16px + env(safe-area-inset-right, 0px))
             calc(16px + env(safe-area-inset-bottom, 0px)) calc(16px + env(safe-area-inset-left, 0px));
  }

  .modal {
    max-width: 480px;
    max-height: calc(var(--app-height, 100dvh) - 32px);
    overflow-y: auto;
    display: block;
  }

  .brand-panel {
    padding: 28px 24px;
    gap: 20px;
  }

  .quadrants {
    gap: 10px;
  }

  .quadrant-cap {
    display: none;
  }

  .form-panel {
    width: 100%;
    padding: 28px 24px;
    border-left: none;
    border-top: 1px solid var(--color-border-subtle);
  }

  .quickstart {
    padding: 14px 24px 20px;
  }

  .topo {
    overflow: visible;
    padding: 12px 6px;
  }

  .topo-links {
    display: none;
  }

  .topo-children {
    margin-top: 10px;
    gap: 8px;
  }

  .topo-node {
    min-width: 0;
    flex: 1 1 30%;
    padding: 8px 6px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .modal {
    animation: none;
  }

  .quadrant,
  .quickstart-arrow,
  .primary-btn {
    transition: none;
  }

  .topo-node.master,
  .topo-node.child,
  .topo-line {
    animation: none;
  }

  .brand-panel::before,
  .brand-panel::after,
  .brand-header,
  .brand-logo-wrap::before,
  .brand-title h1,
  .quadrant,
  .primary-btn {
    animation: none;
  }

  .quadrant::after {
    display: none;
  }
}
</style>
