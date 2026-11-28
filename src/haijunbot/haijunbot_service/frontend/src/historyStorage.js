/**
 * Conversation history storage utility module
 * Stores conversation history in localStorage, with paginated loading, deletion and management
 */

const STORAGE_KEY = "haijunbot_chat_history";
const METADATA_KEY = "haijunbot_chat_metadata";
const MAX_MESSAGES_PER_PAGE = 50;
const MAX_TOTAL_MESSAGES = 1000;
// Storage size limit threshold (3MB): once exceeded, pruneHistory deletes the oldest
// messages by time, avoiding blowing the ~5MB localStorage quota on mobile that would
// make setItem throw QuotaExceededError.
const MAX_STORAGE_SIZE_BYTES = 3 * 1024 * 1024;

/**
 * Generate a unique ID
 */
function generateId() {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Get all history messages
 */
function getAllMessages() {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    if (!data) return [];
    return JSON.parse(data);
  } catch (error) {
    console.error("[historyStorage] Failed to load messages:", error);
    return [];
  }
}

/**
 * Save all messages to storage
 */
function saveAllMessages(messages) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    return true;
  } catch (error) {
    console.error("[historyStorage] Failed to save messages:", error);
    return false;
  }
}

/**
 * Save a single message
 * @param {Object} message - message object
 * @returns {boolean} - whether the save succeeded
 */
function saveMessage(message) {
  try {
    const messages = getAllMessages();

    // Check whether a message with the same ID already exists
    const existingIndex = messages.findIndex((m) => m.id === message.id);
    if (existingIndex >= 0) {
      // Update the existing message
      messages[existingIndex] = message;
    } else {
      // Append the new message at the end
      message.id = message.id || generateId();
      message.storageTimestamp = Date.now();
      messages.push(message);
    }

    // Limit the total number of messages
    if (messages.length > MAX_TOTAL_MESSAGES) {
      const removeCount = messages.length - MAX_TOTAL_MESSAGES;
      messages.splice(0, removeCount);
    }

    saveAllMessages(messages);
    pruneHistory({ removeOrphans: false });
    return true;
  } catch (error) {
    console.error("[historyStorage] Failed to save message:", error);
    return false;
  }
}

/**
 * Save messages in bulk
 * @param {Array} messages - messages array
 * @returns {boolean} - whether the save succeeded
 */
function saveMessages(messages) {
  try {
    const allMessages = getAllMessages();
    const existingIds = new Set(allMessages.map((m) => m.id));

    messages.forEach((msg) => {
      if (!msg.id) {
        msg.id = generateId();
        msg.storageTimestamp = Date.now();
      }
      if (!existingIds.has(msg.id)) {
        allMessages.push(msg);
      }
    });

    // Limit the total number of messages
    if (allMessages.length > MAX_TOTAL_MESSAGES) {
      const removeCount = allMessages.length - MAX_TOTAL_MESSAGES;
      allMessages.splice(0, removeCount);
    }

    saveAllMessages(allMessages);
    pruneHistory({ removeOrphans: false });
    return true;
  } catch (error) {
    console.error("[historyStorage] Failed to save messages:", error);
    return false;
  }
}

/**
 * Read history messages (paginated)
 * @param {number} count - number of messages to read
 * @param {number} offset - offset (counted from the end backwards)
 * @param {string} agentId - optional, only return messages for this Agent ID
 * @returns {Array} - messages array (newest first)
 */
function loadHistory(
  count = MAX_MESSAGES_PER_PAGE,
  offset = 0,
  agentId = null,
) {
  try {
    let messages = getAllMessages();
    if (messages.length === 0) return [];

    // If agentId is given, only return that Agent's messages
    if (agentId) {
      messages = messages.filter((msg) => msg.agent_id === agentId);
    }

    // Take from the end backwards: skip offset items, then take count items
    const start = Math.max(0, messages.length - offset - count);
    const end = messages.length - offset;
    const result = messages.slice(start, end);

    return result;
  } catch (error) {
    console.error("[historyStorage] Failed to load history:", error);
    return [];
  }
}

/**
 * Get the total number of history messages
 * @param {string} agentId - optional, only count messages for this Agent ID
 * @returns {number} - total message count
 */
function getTotalCount(agentId = null) {
  try {
    let messages = getAllMessages();

    // If agentId is given, only count that Agent's messages
    if (agentId) {
      messages = messages.filter((msg) => msg.agent_id === agentId);
    }

    return messages.length;
  } catch (error) {
    console.error("[historyStorage] Failed to get count:", error);
    return 0;
  }
}

/**
 * Delete all history messages
 * @returns {boolean} - whether the deletion succeeded
 */
function clearHistory() {
  try {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(METADATA_KEY);
    return true;
  } catch (error) {
    console.error("[historyStorage] Failed to clear history:", error);
    return false;
  }
}

/**
 * Clear the history for a specific Agent
 * @param {string} agentId - Agent ID
 * @returns {boolean} - whether the clear succeeded
 */
function clearHistoryForAgent(agentId) {
  try {
    const allMessages = getAllMessages();
    const filteredMessages = allMessages.filter(
      (msg) => msg.agent_id !== agentId,
    );

    if (filteredMessages.length !== allMessages.length) {
      saveAllMessages(filteredMessages);
      return true;
    }

    return true;
  } catch (error) {
    console.error("[historyStorage] Failed to clear agent history:", error);
    return false;
  }
}

/**
 * Get history metadata
 * @returns {Object} - metadata object
 */
function getMetadata() {
  try {
    const data = localStorage.getItem(METADATA_KEY);
    if (!data) {
      return {
        totalCount: 0,
        lastUpdated: null,
        storageSize: 0,
      };
    }
    return JSON.parse(data);
  } catch (error) {
    console.error("[historyStorage] Failed to load metadata:", error);
    return {
      totalCount: 0,
      lastUpdated: null,
      storageSize: 0,
    };
  }
}

/**
 * Update history metadata
 */
function updateMetadata() {
  try {
    const messages = getAllMessages();
    const metadata = {
      totalCount: messages.length,
      lastUpdated: Date.now(),
      storageSize: JSON.stringify(messages).length,
    };
    localStorage.setItem(METADATA_KEY, JSON.stringify(metadata));
    return metadata;
  } catch (error) {
    console.error("[historyStorage] Failed to update metadata:", error);
    return null;
  }
}

/**
 * Get history for a specific Agent
 * @param {string} agentId - Agent ID
 * @returns {Array} - messages array for that Agent
 */
function getHistoryForAgent(agentId) {
  try {
    const allMessages = getAllMessages();
    const agentMessages = allMessages.filter((msg) => msg.agent_id === agentId);
    return agentMessages;
  } catch (error) {
    console.error("[historyStorage] Failed to get agent history:", error);
    return [];
  }
}

/**
 * Set history for a specific Agent
 * @param {string} agentId - Agent ID
 * @param {Array} data - messages array
 * @returns {boolean} - whether the set succeeded
 */
function setHistoryForAgent(agentId, data) {
  try {
    const allMessages = getAllMessages();
    // Remove that Agent's old messages
    const otherMessages = allMessages.filter((msg) => msg.agent_id !== agentId);
    // Add the new messages
    const newMessages = data.map((msg) => ({
      ...msg,
      agent_id: agentId,
      id: msg.id || generateId(),
      storageTimestamp: msg.storageTimestamp || Date.now(),
    }));
    const combined = [...otherMessages, ...newMessages];
    saveAllMessages(combined);
    pruneHistory({ removeOrphans: false });
    return true;
  } catch (error) {
    console.error("[historyStorage] Failed to set agent history:", error);
    return false;
  }
}

/**
 * Get storage usage
 * @returns {Object} - storage info
 */
function getStorageInfo() {
  try {
    const messages = getAllMessages();
    const totalSize = JSON.stringify(messages).length;
    const metadata = getMetadata();

    return {
      totalCount: messages.length,
      totalSize: totalSize,
      totalSizeFormatted: formatBytes(totalSize),
      lastUpdated: metadata.lastUpdated
        ? new Date(metadata.lastUpdated).toLocaleString()
        : "never",
      maxMessages: MAX_TOTAL_MESSAGES,
      maxStorageSize: MAX_STORAGE_SIZE_BYTES,
    };
  } catch (error) {
    console.error("[historyStorage] Failed to get storage info:", error);
    return {
      totalCount: 0,
      totalSize: 0,
      totalSizeFormatted: "0 B",
      lastUpdated: "unknown",
      maxMessages: MAX_TOTAL_MESSAGES,
      maxStorageSize: MAX_STORAGE_SIZE_BYTES,
    };
  }
}

/**
 * Periodically clean up history messages:
 * 1. If removeOrphans is true, first remove orphan messages missing an agent_id
 *    (messages left over after an Agent was deleted that cannot be attributed);
 * 2. If the storage size still exceeds MAX_STORAGE_SIZE_BYTES, delete the oldest
 *    messages by storageTimestamp ascending until the size falls back within the limit.
 * The write paths (saveMessage/saveMessages/setHistoryForAgent) only do size cleanup
 * when triggered automatically (removeOrphans=false), avoiding the removal of valid
 * messages without an agent_id; orphans are only cleaned when explicitly invoked
 * (removeOrphans=true) after deleting/regenerating an Agent.
 * @param {Object} [options] - { removeOrphans: boolean }
 * @returns {Object} cleanup stats: { removedOrphans, removedBySize, totalRemoved, remainingCount, remainingSize }
 */
function pruneHistory(options = {}) {
  const { removeOrphans = true } = options;
  try {
    const allMessages = getAllMessages();
    if (allMessages.length === 0) {
      return {
        removedOrphans: 0,
        removedBySize: 0,
        totalRemoved: 0,
        remainingCount: 0,
        remainingSize: JSON.stringify([]).length,
      };
    }

    // 1. Clean up orphan messages (no agent_id); only runs on explicit calls
    let messages = allMessages;
    let removedOrphans = 0;
    if (removeOrphans) {
      messages = allMessages.filter(
        (msg) => msg.agent_id != null && msg.agent_id !== "",
      );
      removedOrphans = allMessages.length - messages.length;
    }

    // 2. Delete the oldest messages by the size threshold
    let removedBySize = 0;
    let size = JSON.stringify(messages).length;
    while (messages.length > 0 && size > MAX_STORAGE_SIZE_BYTES) {
      // Delete the message with the smallest (oldest) storageTimestamp; missing timestamps count as the oldest
      let oldestIndex = 0;
      for (let i = 1; i < messages.length; i++) {
        const a = messages[oldestIndex].storageTimestamp || 0;
        const b = messages[i].storageTimestamp || 0;
        if (b < a) oldestIndex = i;
      }
      messages.splice(oldestIndex, 1);
      removedBySize++;
      size = JSON.stringify(messages).length;
    }

    if (removedOrphans > 0 || removedBySize > 0) {
      saveAllMessages(messages);
    }

    return {
      removedOrphans,
      removedBySize,
      totalRemoved: removedOrphans + removedBySize,
      remainingCount: messages.length,
      remainingSize: size,
    };
  } catch (error) {
    console.error("[historyStorage] Failed to prune history:", error);
    return {
      removedOrphans: 0,
      removedBySize: 0,
      totalRemoved: 0,
      remainingCount: getAllMessages().length,
      remainingSize: JSON.stringify(getAllMessages()).length,
    };
  }
}

/**
 * Format a byte count
 */
function formatBytes(bytes) {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
}

// Export all methods
export default {
  saveMessage,
  saveMessages,
  loadHistory,
  getTotalCount,
  clearHistory,
  clearHistoryForAgent,
  getHistoryForAgent,
  setHistoryForAgent,
  getMetadata,
  updateMetadata,
  getStorageInfo,
  pruneHistory,
  MAX_MESSAGES_PER_PAGE,
  MAX_TOTAL_MESSAGES,
  MAX_STORAGE_SIZE_BYTES,
};
