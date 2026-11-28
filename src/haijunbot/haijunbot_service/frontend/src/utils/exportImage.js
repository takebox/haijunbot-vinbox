/**
 * Utility module for exporting DOM content as an image
 * Composes Markdown-rendered message content into a PNG with an info bar, preferring the clipboard and falling back to download on failure.
 */
import { toBlob } from "html-to-image";

// Image composition parameters (kept consistent with the frontend dark theme)
const PADDING = 24; // Padding around the content
const HEADER_H = 56; // Height of the top info bar
const FOOTER_H = 36; // Height of the bottom watermark
// Content layout width when exporting: narrow containers (pet bubble/narrow panel) are re-laid out at this width to avoid a tall, thin image
const EXPORT_WIDTH = 760;
// Browser canvas per-side size limit (about 32767 for Chrome/Firefox); leave room for the info bar and watermark
const MAX_CANVAS_SIDE = 32000;
const SCALE = 2; // Pixel ratio for high definition
const BG_COLOR = "#0b1424";
const HEADER_BG = "#0f1c30";
const BORDER_COLOR = "rgba(32, 200, 255, 0.25)";
const TEXT_PRIMARY = "#d6e4f0";
const TEXT_SECONDARY = "#8ba3b8";
const ACCENT = "#20c8ff";

/**
 * Whether this is a mobile/touch device
 * Mobile browsers generally do not support writing images via navigator.clipboard.write, and users usually prefer saving to the photo album,
 * so on mobile, beyond attempting to copy, always trigger an extra download.
 */
function isMobileDevice() {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  if (/Android|iPhone|iPad|iPod|Windows Phone|HarmonyOS|Mobile/i.test(ua))
    return true;
  // On iPadOS 13+ desktop mode the UA is the same as Mac; use the touch point count as an additional check
  return navigator.maxTouchPoints > 1 && /Macintosh/.test(ua);
}

/**
 * Truncate text to the maximum width, replacing the overflow with an ellipsis
 */
function truncateText(ctx, text, maxWidth) {
  const str = String(text || "");
  if (!str) return "";
  if (ctx.measureText(str).width <= maxWidth) return str;
  let result = str;
  while (result.length > 1 && ctx.measureText(result + "…").width > maxWidth) {
    result = result.slice(0, -1);
  }
  return result + "…";
}

/**
 * Render a DOM element to a PNG blob
 * Returns null if rendering fails
 *
 * Note: the target element is often inside a scroll container (e.g. pet bubble with max-height + overflow-y:auto),
 * and rendering it directly only captures the visible area, losing the overflow. So first clone it and remove the height/overflow limits,
 * mount it in an offscreen container and render at the full content size, then clean up after rendering.
 */
async function elementToBlob(el) {
  if (!el) return null;

  const clone = el.cloneNode(true);
  // Remove the height and overflow limits on the clone to ensure the full content is rendered
  clone.style.maxHeight = "none";
  clone.style.height = "auto";
  clone.style.overflow = "visible";
  clone.style.overflowY = "visible";
  // Use the larger of the original width and the target width: narrow containers (pet bubble/narrow panel) are laid out wide when exported,
  // avoiding a too-thin image that wraps the content excessively
  const sourceW = el.offsetWidth || el.getBoundingClientRect().width || 0;
  const exportW = Math.max(sourceW, EXPORT_WIDTH);
  clone.style.width = `${exportW}px`;
  clone.style.maxWidth = "none";
  clone.style.boxSizing = "border-box";

  const holder = document.createElement("div");
  holder.style.position = "fixed";
  holder.style.left = "-100000px";
  holder.style.top = "0";
  holder.style.width = `${exportW}px`;
  holder.style.background = BG_COLOR;
  holder.appendChild(clone);
  document.body.appendChild(holder);

  try {
    // Adapt the pixel ratio to the content height: the longer the content, the lower the ratio, to avoid the bitmap exceeding the browser canvas limit
    const fullH = clone.scrollHeight || clone.offsetHeight || 0;
    const pixelRatio =
      fullH * SCALE > MAX_CANVAS_SIDE
        ? Math.max(1, MAX_CANVAS_SIDE / fullH)
        : SCALE;
    const blob = await toBlob(clone, {
      backgroundColor: BG_COLOR,
      pixelRatio,
      // Skip interactive controls that are not part of the export (the copy/export buttons themselves)
      filter: (node) => {
        if (!node || !node.classList) return true;
        return (
          !node.classList.contains("lobby-pet-copy") &&
          !node.classList.contains("lobby-pet-export") &&
          !node.classList.contains("copy-message-btn") &&
          !node.classList.contains("export-message-btn")
        );
      },
    });
    return blob ? { blob, pixelRatio } : null;
  } catch (err) {
    console.error("[EXPORT-IMAGE] Element rendering failed:", err);
    return null;
  } finally {
    document.body.removeChild(holder);
  }
}

/**
 * Compose the content image and the info bar into the final PNG
 */
function composeImage(contentBitmap, meta, contentW, contentH, scale) {
  const headerText = String(meta.title || "HaijunBot");
  const subText = String(meta.subtitle || "");
  const timeText = String(meta.time || "");

  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  // The content image is a high-definition bitmap (already scaled up by the pixel ratio); the info bar and watermark are scaled up in sync to keep the visual proportions consistent
  const s = scale || SCALE;
  const padding = PADDING * s;
  const headerH = HEADER_H * s;
  const footerH = FOOTER_H * s;

  const width = contentW + padding * 2;
  const height = headerH + contentH + footerH + padding;

  canvas.width = width;
  canvas.height = height;

  // When the canvas size exceeds the browser limit it is silently set to 0, making drawing impossible
  if (!canvas.width || !canvas.height) {
    console.error("[EXPORT-IMAGE] Canvas size exceeds the limit:", width, height);
    return null;
  }

  // Background
  ctx.fillStyle = BG_COLOR;
  ctx.fillRect(0, 0, width, height);

  // Top info bar
  ctx.fillStyle = HEADER_BG;
  ctx.fillRect(0, 0, width, headerH);
  ctx.strokeStyle = BORDER_COLOR;
  ctx.lineWidth = 1 * s;
  ctx.beginPath();
  ctx.moveTo(0, headerH + 0.5);
  ctx.lineTo(width, headerH + 0.5);
  ctx.stroke();

  // Left: HaijunBot logo + title
  ctx.textBaseline = "middle";
  ctx.font = `bold ${16 * s}px sans-serif`;
  ctx.fillStyle = ACCENT;
  const brandText = "◆ HaijunBot";
  ctx.fillText(brandText, padding, headerH / 2);
  const brandW = ctx.measureText(brandText).width;

  ctx.font = `${15 * s}px sans-serif`;
  ctx.fillStyle = TEXT_PRIMARY;
  const titleMaxW =
    width - padding * 2 - brandW - 16 * s - (timeText ? 140 * s : 0);
  ctx.fillText(
    truncateText(ctx, headerText, Math.max(titleMaxW, 60 * s)),
    padding + brandW + 12 * s,
    headerH / 2,
  );

  // Right: time
  if (timeText) {
    ctx.font = `${13 * s}px sans-serif`;
    ctx.fillStyle = TEXT_SECONDARY;
    ctx.textAlign = "right";
    ctx.fillText(timeText, width - padding, headerH / 2);
    ctx.textAlign = "left";
  }

  // Content image
  ctx.drawImage(contentBitmap, padding, headerH, contentW, contentH);

  // Bottom watermark
  ctx.font = `${12 * s}px sans-serif`;
  ctx.fillStyle = TEXT_SECONDARY;
  ctx.textAlign = "center";
  const footerText = subText
    ? `${subText} · Generated by HaijunBot`
    : "Generated by HaijunBot";
  ctx.fillText(
    truncateText(ctx, footerText, width - padding * 2),
    width / 2,
    headerH + contentH + footerH / 2,
  );
  ctx.textAlign = "left";

  return canvas;
}

/**
 * Convert the canvas to a PNG blob
 */
function canvasToBlob(canvas) {
  return new Promise((resolve) => {
    try {
      canvas.toBlob((blob) => resolve(blob), "image/png");
    } catch (err) {
      console.error("[EXPORT-IMAGE] Failed to convert canvas to blob:", err);
      resolve(null);
    }
  });
}

/**
 * Trigger a browser download of the PNG
 */
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || `haijunbot-${Date.now()}.png`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Release after a delay, so some browsers do not revoke it before the download starts
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

/**
 * Copy the PNG blob to the clipboard
 * Returns true on success; returns false when the clipboard is unavailable (non-secure context/unsupported browser)
 */
async function copyBlobToClipboard(blob) {
  if (!blob) return false;
  if (typeof ClipboardItem === "undefined" || !navigator.clipboard?.write)
    return false;
  try {
    await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
    return true;
  } catch (err) {
    console.warn("[EXPORT-IMAGE] Clipboard write failed, falling back to download:", err);
    return false;
  }
}

/**
 * Export a DOM element as a PNG image with an info bar
 *
 * @param {HTMLElement} el Target element (the content container after Markdown rendering)
 * @param {Object} meta Info bar content
 * @param {string} meta.title Title (e.g. the Agent name)
 * @param {string} meta.subtitle Extra info for the bottom watermark (e.g. the Agent type)
 * @param {string} meta.time Time text in the top-right corner
 * @param {string} meta.filename File name when downloading (without extension)
 * @returns {Promise<{ok: boolean, mode?: 'clipboard'|'download', error?: string}>}
 */
export async function exportElementAsImage(el, meta = {}) {
  if (!el) {
    return { ok: false, error: "There is no content to export" };
  }

  // Cannot render when the element size is 0 (e.g. hidden)
  const rect = el.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    return { ok: false, error: "The content is empty or not visible" };
  }

  const rendered = await elementToBlob(el);
  if (!rendered) {
    return { ok: false, error: "Image generation failed" };
  }
  const { blob: contentBlob, pixelRatio } = rendered;

  // Decode to a bitmap, scaling proportionally to the maximum size
  let bitmap;
  try {
    bitmap = await createImageBitmap(contentBlob);
  } catch (err) {
    console.error("[EXPORT-IMAGE] Bitmap decoding failed:", err);
    return { ok: false, error: "Image generation failed" };
  }

  // Draw the content at the bitmap's original size, without scaling (to preserve clarity and complete content)
  const contentW = bitmap.width;
  let contentH = bitmap.height;

  // When the content is very tall, shrink it proportionally as a whole (rather than truncating), to avoid exceeding the canvas per-side limit and failing to create
  const maxContentH =
    MAX_CANVAS_SIDE - (HEADER_H + FOOTER_H + PADDING) * pixelRatio;
  let contentWFinal = contentW;
  if (contentH > maxContentH) {
    const shrink = maxContentH / contentH;
    contentH = maxContentH;
    contentWFinal = Math.max(1, Math.round(contentW * shrink));
  }

  const canvas = composeImage(
    bitmap,
    meta,
    contentWFinal,
    contentH,
    pixelRatio,
  );
  if (!canvas) {
    return { ok: false, error: "Image composition failed" };
  }

  const finalBlob = await canvasToBlob(canvas);
  if (!finalBlob) {
    return { ok: false, error: "Image generation failed" };
  }

  const filename = `${meta.filename || "haijunbot-export"}.png`;
  const mobile = isMobileDevice();
  const copied = await copyBlobToClipboard(finalBlob);

  // Mobile: writing images to the clipboard is generally unavailable, and users prefer saving to the album, so always download a copy in addition to copying
  if (mobile) {
    downloadBlob(finalBlob, filename);
    return { ok: true, mode: copied ? "clipboard+download" : "download" };
  }

  if (copied) {
    return { ok: true, mode: "clipboard" };
  }

  // Fall back to download when the clipboard is unavailable (e.g. a non-HTTPS environment)
  downloadBlob(finalBlob, filename);
  return { ok: true, mode: "download" };
}
