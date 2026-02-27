/* ChattyStickers — Frontend JavaScript */

"use strict";

// ── Particles Background ─────────────────────────────────────────────────────
(function initParticles() {
    const container = document.getElementById("bgParticles");
    if (!container) return;
    const colors = ["#7c5bff", "#4f9eff", "#ff5bcd", "#2ef6a0", "#ffaa40"];
    for (let i = 0; i < 25; i++) {
        const p = document.createElement("div");
        p.className = "particle";
        const size = Math.random() * 6 + 3;
        const color = colors[Math.floor(Math.random() * colors.length)];
        const duration = Math.random() * 15 + 12;
        const delay = Math.random() * 15;
        const left = Math.random() * 100;
        p.style.cssText = `
      width:${size}px; height:${size}px;
      left:${left}%; bottom:-10px;
      background:${color};
      animation-duration:${duration}s;
      animation-delay:-${delay}s;
    `;
        container.appendChild(p);
    }
})();

// ── Character Counter ────────────────────────────────────────────────────────
const phraseInput = document.getElementById("phraseInput");
const charCount = document.getElementById("charCount");

phraseInput.addEventListener("input", () => {
    const len = phraseInput.value.length;
    charCount.textContent = `${len} / 300`;
    charCount.style.color = len > 250 ? "var(--accent-orange)" : "var(--text-muted)";
});

// ── Example Chips ────────────────────────────────────────────────────────────
function setExample(btn) {
    const text = btn.textContent.replace(/^[^\s]+\s/, ""); // Remove emoji
    phraseInput.value = btn.textContent.trim();
    charCount.textContent = `${phraseInput.value.length} / 300`;
    phraseInput.focus();
}

// ── State ────────────────────────────────────────────────────────────────────
let isGenerating = false;
let currentSessionId = null;
let currentExports = {};

// ── Pipeline Progress Simulation ─────────────────────────────────────────────
const PIPELINE_STEPS = [
    { id: "step-parse", label: "🧠 Analyzing text...", duration: 800, progress: 10 },
    { id: "step-image", label: "🎨 Generating AI Image (SDXL)...", duration: 15000, progress: 45 },
    { id: "step-tts", label: "🔊 Voice Synthesis TTS...", duration: 3000, progress: 60 },
    { id: "step-anim", label: "🎬 Animating sticker...", duration: 4000, progress: 80 },
    { id: "step-earcp", label: "🛡️ EARCP Verification...", duration: 1000, progress: 90 },
    { id: "step-export", label: "📦 Multi-format Export...", duration: 2000, progress: 98 },
];

function setStepState(stepId, state) {
    const el = document.getElementById(stepId);
    if (!el) return;
    el.classList.remove("active", "done");
    if (state === "active") el.classList.add("active");
    if (state === "done") el.classList.add("done");
}

let stepIndex = 0;

function advanceStep() {
    if (stepIndex > 0) {
        setStepState(PIPELINE_STEPS[stepIndex - 1].id, "done");
    }
    if (stepIndex >= PIPELINE_STEPS.length) return null;

    const step = PIPELINE_STEPS[stepIndex];
    setStepState(step.id, "active");
    document.getElementById("progressLabel").textContent = step.label;
    document.getElementById("progressBar").style.width = step.progress + "%";
    stepIndex++;
    return step;
}

// ── Main Generate Function ───────────────────────────────────────────────────
async function generateSticker() {
    const phrase = phraseInput.value.trim();
    if (!phrase) {
        phraseInput.focus();
        phraseInput.style.borderColor = "var(--accent-pink)";
        setTimeout(() => { phraseInput.style.borderColor = ""; }, 1500);
        return;
    }

    if (isGenerating) return;
    isGenerating = true;
    stepIndex = 0;

    // Reset UI
    document.getElementById("resultSection").style.display = "none";
    document.getElementById("errorCard").style.display = "none";
    const progressCard = document.getElementById("progressCard");
    progressCard.style.display = "block";
    progressCard.scrollIntoView({ behavior: "smooth", block: "center" });

    // Reset all steps
    PIPELINE_STEPS.forEach(s => setStepState(s.id, ""));
    document.getElementById("progressBar").style.width = "2%";

    const btn = document.getElementById("generateBtn");
    btn.disabled = true;
    btn.querySelector(".btn-text").textContent = "Generating...";
    btn.querySelector(".btn-icon").textContent = "⏳";

    // Start step animation
    let stepTimer = advanceStep();
    const stepInterval = setInterval(() => {
        const step = advanceStep();
        if (!step) clearInterval(stepInterval);
    }, 4000);

    try {
        const response = await fetch("/api/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phrase }),
        });

        clearInterval(stepInterval);

        // Mark all steps done
        PIPELINE_STEPS.forEach(s => setStepState(s.id, "done"));
        document.getElementById("progressBar").style.width = "100%";
        document.getElementById("progressLabel").textContent = "✨ Sticker ready !";

        const data = await response.json();

        await sleep(600);
        progressCard.style.display = "none";

        if (!response.ok || !data.success) {
            showError(data.error || "Unknown error", data.traceback);
        } else {
            currentSessionId = data.session_id;
            currentExports = data.export_urls || {};
            showResult(data);
        }

    } catch (err) {
        clearInterval(stepInterval);
        progressCard.style.display = "none";
        showError("Could not contact server. Check if Flask is running on localhost:5000", err.toString());
    } finally {
        isGenerating = false;
        btn.disabled = false;
        btn.querySelector(".btn-text").textContent = "Generate Sticker";
        btn.querySelector(".btn-icon").textContent = "✨";
    }
}

// ── Show Result ──────────────────────────────────────────────────────────────
function showResult(data) {
    const resultSection = document.getElementById("resultSection");
    resultSection.style.display = "block";
    resultSection.scrollIntoView({ behavior: "smooth", block: "start" });

    const sticker = data.sticker || {};
    const exportUrls = data.export_urls || {};

    // ── PRIMARY: Unified talking sticker video ─────────────────────────────
    const videoEl = document.getElementById("stickerVideo");
    const gifEl = document.getElementById("gifFallback");
    const audioBar = document.getElementById("stickerAudioBar");
    const badge = document.getElementById("previewLabel");

    const stickerUrl = sticker.url || exportUrls.webm || "";
    const gifUrl = sticker.preview_gif || exportUrls.gif || "";

    if (stickerUrl) {
        // Load MP4 with audio into video element
        videoEl.src = stickerUrl + "?t=" + Date.now();
        videoEl.muted = false; // audio ON by default
        videoEl.style.display = "block";
        gifEl.style.display = "none";
        badge.innerHTML = "🎬🔊 Multimedia Sticker";
        audioBar.style.display = "flex";

        // Auto-play with sound; fall back to muted if browser blocks
        videoEl.play().catch(() => {
            videoEl.muted = true;
            updateAudioToggleUI(true);
        });
    } else if (gifUrl) {
        // Fallback to GIF
        gifEl.src = gifUrl + "?t=" + Date.now();
        gifEl.style.display = "block";
        videoEl.style.display = "none";
        badge.innerHTML = "🎞️ GIF Animation";
        audioBar.style.display = "none";
    }

    // ── Source image thumbnail ─────────────────────────────────────────────
    const imgUrl = sticker.preview_image || "";
    const staticPreview = document.getElementById("staticPreview");
    if (imgUrl) {
        staticPreview.src = imgUrl;
        staticPreview.style.display = "block";
    }

    // ── Sticker info box ───────────────────────────────────────────────────
    const infoEl = document.getElementById("stickerFileInfo");
    if (infoEl) {
        const parsed = data.parsed || {};
        infoEl.innerHTML = `
      <div class="file-info-row">🎭 <strong>${parsed.subject || "AI Character"}</strong></div>
      <div class="file-info-row">💫 Emotion: <strong>${parsed.emotion || "?"}</strong></div>
      <div class="file-info-row">🗣 Language: <strong>${(parsed.language || "en").toUpperCase()}</strong></div>
      <div class="file-info-row">⏱ Generated in: <strong>${data.elapsed_s || "?"}s</strong></div>
      <div class="file-info-row">📁 Format: <strong>WebM + Integrated Voice</strong></div>
    `;
    }

    // ── Parsed tags ────────────────────────────────────────────────────────
    const parsed = data.parsed || {};
    const infoTagsEl = document.getElementById("parsedInfo");
    if (infoTagsEl) {
        infoTagsEl.innerHTML = [
            parsed.subject ? `<span class="info-tag">👤 <strong>${parsed.subject}</strong></span>` : "",
            parsed.emotion ? `<span class="info-tag">💫 <strong>${parsed.emotion}</strong></span>` : "",
            parsed.language ? `<span class="info-tag">🌐 <strong>${parsed.language.toUpperCase()}</strong></span>` : "",
            data.elapsed_s ? `<span class="info-tag">⏱ <strong>${data.elapsed_s}s</strong></span>` : "",
        ].filter(Boolean).join("");
    }

    // ── EARCP Report ───────────────────────────────────────────────────────
    renderEARCPReport(data.earcp_report || {});

    // ── Export buttons ─────────────────────────────────────────────────────
    renderExports(exportUrls, data.session_id);
}

// ── Audio toggle for the unified sticker video ────────────────────────────────
function toggleStickerAudio() {
    const videoEl = document.getElementById("stickerVideo");
    if (!videoEl) return;
    videoEl.muted = !videoEl.muted;
    updateAudioToggleUI(videoEl.muted);
    if (!videoEl.muted) videoEl.play();
}

function updateAudioToggleUI(isMuted) {
    const icon = document.getElementById("audioToggleIcon");
    const text = document.getElementById("audioToggleText");
    if (icon) icon.textContent = isMuted ? "🔇" : "🔊";
    if (text) text.textContent = isMuted ? "Sound OFF" : "Sound ON";
}


// ── EARCP Report Renderer ────────────────────────────────────────────────────
function renderEARCPReport(report) {
    const container = document.getElementById("earcpContent");
    if (!container) return;

    const score = report.earcp_score ?? 0;
    const grade = report.grade ?? "?";
    const P = report.performance_avg ?? 0;
    const C = report.coherence_avg ?? 0;
    const comps = report.component_scores ?? {};
    const cohs = report.coherence_scores ?? {};
    const weights = report.expert_weights ?? {};
    const notes = report.auto_correction_notes ?? [];

    const pct = Math.round(score * 100);
    const [gradeLetter] = grade.split(" -");
    const gradeColor = gradeToColor(gradeLetter);

    // Main score ring
    let html = `
    <div class="earcp-score-main">
      <div class="score-ring">
        <span class="score-pct" style="background: ${gradeColor}; -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;">${pct}%</span>
        <span class="score-label-sm">EARCP</span>
      </div>
      <div class="score-ring-info">
        <h3 style="color:var(--text-primary)">${grade}</h3>
        <p>Performance: <strong>${Math.round(P * 100)}%</strong> &nbsp;·&nbsp; Coherence: <strong>${Math.round(C * 100)}%</strong></p>
        <p style="margin-top:4px; font-size:0.8rem; color:var(--text-muted)">β=${report.beta ?? 0.65} · Formula: Q = β×P + (1-β)×C</p>
      </div>
    </div>
    <div class="earcp-breakdown">
  `;

    // Component performance scores
    html += `<div class="breakdown-box"><h4>📊 Component Scores</h4>`;
    const compIcons = { text: "📝", image: "🎨", audio: "🔊", animation: "🎬" };
    const compNames = { text: "Text", image: "Image", audio: "Audio", animation: "Animation" };
    for (const [key, val] of Object.entries(comps)) {
        const w = weights[key] ? ` (w=${(weights[key] * 100).toFixed(0)}%)` : "";
        html += `
      <div class="score-row">
        <span class="score-row-label">${compIcons[key] || ""} ${compNames[key] || key}${w}</span>
        <div class="score-bar"><div class="score-fill" style="width:${Math.round(val * 100)}%"></div></div>
        <span class="score-val">${Math.round(val * 100)}%</span>
      </div>`;
    }
    html += `</div>`;

    // Coherence scores
    html += `<div class="breakdown-box"><h4>🔗 Inter-component Coherence</h4>`;
    const cohIcons = { text_image: "📝↔🎨", text_audio: "📝↔🔊", animation_emotion: "🎬↔💫" };
    for (const [key, val] of Object.entries(cohs)) {
        html += `
      <div class="score-row">
        <span class="score-row-label">${cohIcons[key] || key}</span>
        <div class="score-bar"><div class="score-fill" style="width:${Math.round(val * 100)}%; background:var(--grad-blue)"></div></div>
        <span class="score-val">${Math.round(val * 100)}%</span>
      </div>`;
    }
    html += `</div>`;

    html += `</div>`;

    // Notes / auto-corrections
    if (notes.length > 0) {
        html += `<div class="earcp-notes"><h4>⚠ Auto-correction Notes</h4>`;
        notes.forEach(n => { html += `<div class="note-item">${n}</div>`; });
        html += `</div>`;
    }

    container.innerHTML = html;
}

function gradeToColor(letter) {
    const map = {
        A: "linear-gradient(135deg, #2ef6a0, #4f9eff)",
        B: "linear-gradient(135deg, #4f9eff, #7c5bff)",
        C: "linear-gradient(135deg, #7c5bff, #ff5bcd)",
        D: "linear-gradient(135deg, #ffaa40, #ff5b5b)",
        F: "linear-gradient(135deg, #ff5b5b, #ff1a1a)",
    };
    return map[letter] || map.B;
}

// ── Export Buttons Renderer ──────────────────────────────────────────────────
function renderExports(exportUrls, sessionId) {
    const grid = document.getElementById("exportGrid");
    if (!grid) return;

    const formats = [
        {
            key: "gif",
            icon: "🎞️",
            label: "GIF",
            desc: "Telegram · Discord\nAnimated loop",
            color: "gif",
        },
        {
            key: "webp",
            icon: "💬",
            label: "WEBP",
            desc: "WhatsApp · Telegram\nNative animated sticker",
            color: "webp",
        },
        {
            key: "webm",
            icon: "🎥",
            label: "WebM",
            desc: "All platforms\nWith sound + animation",
            color: "mp4", // keep color class if it matches CSS
        },
    ];

    grid.innerHTML = formats.map(f => {
        const url = exportUrls[f.key];
        const hasFile = !!url;
        if (!hasFile) {
            return `
        <div class="export-btn ${f.color}" style="opacity:0.4; cursor:not-allowed;">
          <span class="export-btn-icon">${f.icon}</span>
          <span class="export-btn-format">.${f.label}</span>
          <span class="export-btn-desc">Not available</span>
        </div>`;
        }
        const downloadUrl = `/api/download/${sessionId}/${f.key.toLowerCase()}`;
        return `
      <a href="${downloadUrl}" download class="export-btn ${f.color}">
        <span class="export-btn-icon">${f.icon}</span>
        <span class="export-btn-format">.${f.label}</span>
        <span class="export-btn-desc">${f.desc.replace('\n', '<br/>')}</span>
      </a>`;
    }).join("");
}

// ── Error Display ────────────────────────────────────────────────────────────
function showError(message, detail) {
    const errorCard = document.getElementById("errorCard");
    document.getElementById("errorTitle").textContent = "An error occurred";
    document.getElementById("errorMessage").textContent = message + (detail ? ` — ${detail.substring(0, 200)}` : "");
    errorCard.style.display = "block";
    errorCard.scrollIntoView({ behavior: "smooth", block: "center" });
}

function resetUI() {
    document.getElementById("errorCard").style.display = "none";
    document.getElementById("resultSection").style.display = "none";
    document.getElementById("progressCard").style.display = "none";
    phraseInput.focus();
}

// ── Keyboard shortcut (Ctrl+Enter) ───────────────────────────────────────────
phraseInput.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        generateSticker();
    }
});

// ── Utility ──────────────────────────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
