/**
 * Interface vocale – Traiteur Dupont
 * ────────────────────────────────────
 * Gère :
 *   - La saisie texte (envoi au /api/text)
 *   - L'enregistrement vocal (envoi au /api/voice)
 *   - L'affichage de la conversation
 *   - Le flow multi-tour de commande (collecte infos + paiement CB)
 *   - La lecture audio de la réponse avec bouton play/stop
 */

'use strict';

// ── Configuration ──────────────────────────────────────────────────────────────
const API_BASE = '/api';

// ── Éléments DOM ───────────────────────────────────────────────────────────────
const chatArea   = document.getElementById('chatArea');
const textInput  = document.getElementById('textInput');
const sendBtn    = document.getElementById('sendBtn');
const micBtn     = document.getElementById('micBtn');
const micLabel   = document.getElementById('micLabel');
const statusBar  = document.getElementById('statusBar');
const statusDot  = document.getElementById('statusDot');

// ── État ──────────────────────────────────────────────────────────────────────
let mediaRecorder  = null;
let audioChunks    = [];
let isRecording    = false;
let currentAudio   = null;

// Session de commande : ID unique par chargement de page, partagé avec le backend
let sessionId = null;
let currentOrderTotal = null;

// ── Vérification de l'état du service ─────────────────────────────────────────
async function checkHealth() {
  try {
    const res = await fetch('/health');
    statusDot.className = res.ok ? 'status-dot online' : 'status-dot offline';
  } catch {
    statusDot.className = 'status-dot offline';
  }
}

// ── Envoi d'un message texte ──────────────────────────────────────────────────
async function sendText() {
  const text = textInput.value.trim();
  if (!text) return;

  addMessage(text, 'user');
  textInput.value = '';
  setInputEnabled(false);

  const thinkingBubble = addThinkingBubble();
  try {
    const res = await fetch(`${API_BASE}/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, session_id: sessionId, skip_tts: false }),
    });
    thinkingBubble.remove();
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    handleAgentResponse(data);
  } catch (err) {
    thinkingBubble.remove();
    addMessage(`Erreur : ${err.message}`, 'bot error');
  } finally {
    setStatus('');
    setInputEnabled(true);
    textInput.focus();
  }
}

// ── Enregistrement et envoi de l'audio ────────────────────────────────────────
async function startRecording() {
  if (isRecording) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    const mimeType = MediaRecorder.isTypeSupported('audio/wav') ? 'audio/wav' : 'audio/webm';
    mediaRecorder = new MediaRecorder(stream, { mimeType });
    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      sendAudio(new Blob(audioChunks, { type: mimeType }));
    };
    mediaRecorder.start();
    isRecording = true;
    micBtn.classList.add('recording');
    micLabel.textContent = 'Parlez... (relâcher pour envoyer)';
    setStatus('Enregistrement en cours...');
  } catch {
    addMessage('Impossible d\'accéder au microphone. Vérifiez les permissions.', 'bot error');
  }
}

function stopRecording() {
  if (!isRecording || !mediaRecorder) return;
  mediaRecorder.stop();
  isRecording = false;
  micBtn.classList.remove('recording');
  micLabel.textContent = 'Traitement de l\'audio...';
  setStatus('Transcription en cours...');
}

async function sendAudio(blob) {
  setInputEnabled(false);
  const { transcriptEl } = addAudioBubble(blob);

  try {
    // ── Étape 1 : transcription ──────────────────────────────────────────────
    setStatus('Transcription en cours...');
    const sttForm = new FormData();
    sttForm.append('audio', blob, 'recording.wav');

    const sttRes = await fetch(`${API_BASE}/transcribe`, { method: 'POST', body: sttForm });
    if (!sttRes.ok) throw new Error(`STT HTTP ${sttRes.status}`);
    const sttData = await sttRes.json();
    const transcript = sttData.transcript?.trim() || '';

    // Affiche la transcription dès qu'elle est disponible
    transcriptEl.textContent = transcript || '(inaudible)';
    if (!transcript) { setStatus(''); setInputEnabled(true); return; }

    // ── Étape 2 : agent (LLM + TTS) ─────────────────────────────────────────
    const thinkingBubble = addThinkingBubble();
    setStatus('');

    const agentRes = await fetch(`${API_BASE}/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: transcript, session_id: sessionId, skip_tts: false }),
    });
    thinkingBubble.remove();

    if (!agentRes.ok) {
      const err = await agentRes.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${agentRes.status}`);
    }
    const data = await agentRes.json();
    handleAgentResponse(data);

  } catch (err) {
    transcriptEl.textContent = transcriptEl.textContent === '…' ? '(erreur)' : transcriptEl.textContent;
    addMessage(`Erreur : ${err.message}`, 'bot error');
  } finally {
    micLabel.textContent = 'Maintenir pour parler';
    setStatus('');
    setInputEnabled(true);
  }
}

// ── Gestion de la réponse de l'agent ──────────────────────────────────────────
function handleAgentResponse(data) {
  // Met à jour la session si le backend en retourne une
  if (data.session_id) sessionId = data.session_id;
  if (data.order_total != null) currentOrderTotal = data.order_total;

  addBotResponse(data);

  // Si l'agent attend la saisie CB, afficher le formulaire de paiement
  if (data.order_step === 'awaiting_card') {
    addPaymentForm(data.order_total ?? currentOrderTotal);
  }

  // Commande finalisée : nettoyer la session locale
  if (data.order_step === 'complete') {
    sessionId = null;
    currentOrderTotal = null;
  }
}

// ── Formulaire de paiement CB ─────────────────────────────────────────────────
function addPaymentForm(total) {
  const div = document.createElement('div');
  div.className = 'payment-form';

  div.innerHTML = `
    <p class="payment-title">💳 Paiement par carte bancaire</p>
    <p class="payment-amount">Montant : <strong>${total != null ? total.toFixed(2) + ' €' : '—'}</strong></p>
    <input class="payment-input" id="cardNumber" type="text" maxlength="19"
      placeholder="Numéro de carte (ex : 4242 4242 4242 4242)" autocomplete="off" />
    <div class="payment-row">
      <input class="payment-input" id="cardExpiry" type="text" maxlength="5" placeholder="MM/AA" />
      <input class="payment-input" id="cardCvv" type="text" maxlength="3" placeholder="CVV" />
    </div>
    <button class="btn-pay" id="payBtn">Payer ${total != null ? total.toFixed(2) + ' €' : ''}</button>
    <p class="payment-hint">
      Test : <code>4242 4242 4242 4242</code> → accepté &nbsp;|&nbsp;
      <code>4000 0000 0000 0002</code> → refusé
    </p>
  `;

  chatArea.appendChild(div);
  scrollToBottom();

  // Formatage automatique du numéro de carte (groupes de 4)
  const cardInput = div.querySelector('#cardNumber');
  cardInput.addEventListener('input', () => {
    const digits = cardInput.value.replace(/\D/g, '').slice(0, 16);
    cardInput.value = digits.replace(/(.{4})/g, '$1 ').trim();
  });

  div.querySelector('#payBtn').addEventListener('click', async () => {
    const card   = cardInput.value;
    const expiry = div.querySelector('#cardExpiry').value;
    const cvv    = div.querySelector('#cardCvv').value;

    if (card.replace(/\s/g, '').length !== 16) {
      showPaymentError(div, 'Numéro de carte invalide (16 chiffres).');
      return;
    }

    div.querySelector('#payBtn').disabled = true;
    div.querySelector('#payBtn').textContent = 'Traitement...';

    try {
      const res = await fetch(`${API_BASE}/payment/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, card_number: card, expiry, cvv }),
      });
      const result = await res.json();

      div.remove(); // Retire le formulaire

      if (result.success) {
        sessionId = null;
        currentOrderTotal = null;
        const totalLabel = (result.order_total > 0) ? `${result.order_total.toFixed(2)} €` : 'montant à confirmer';
        const msg = `✅ Paiement accepté ! Votre commande n°${result.order_id} est confirmée. Montant débité : ${totalLabel}.`;
        addMessage(msg, 'bot');
      } else {
        // Proposer règlement sur place
        addMessage(result.message, 'bot error');
        addOnSitePaymentChoice();
      }
    } catch (err) {
      showPaymentError(div, `Erreur réseau : ${err.message}`);
      div.querySelector('#payBtn').disabled = false;
      div.querySelector('#payBtn').textContent = 'Réessayer';
    }
  });
}

function showPaymentError(formDiv, msg) {
  let errEl = formDiv.querySelector('.payment-error');
  if (!errEl) {
    errEl = document.createElement('p');
    errEl.className = 'payment-error';
    formDiv.appendChild(errEl);
  }
  errEl.textContent = msg;
}

function addOnSitePaymentChoice() {
  const div = document.createElement('div');
  div.className = 'payment-choice';
  div.innerHTML = `
    <p>Souhaitez-vous quand même enregistrer la commande avec <strong>règlement sur place</strong> ?</p>
    <button class="btn-onsite" id="btnOnSite">Oui, régler sur place</button>
    <button class="btn-cancel" id="btnCancel">Annuler la commande</button>
  `;
  chatArea.appendChild(div);
  scrollToBottom();

  div.querySelector('#btnOnSite').addEventListener('click', async () => {
    div.remove();
    try {
      const res = await fetch(`${API_BASE}/payment/accept-on-site?session_id=${sessionId}`, {
        method: 'POST',
      });
      const result = await res.json();
      sessionId = null;
      currentOrderTotal = null;
      addMessage(`✅ ${result.message}`, 'bot');
    } catch (err) {
      addMessage(`Erreur : ${err.message}`, 'bot error');
    }
  });

  div.querySelector('#btnCancel').addEventListener('click', () => {
    div.remove();
    sessionId = null;
    currentOrderTotal = null;
    addMessage('Commande annulée. N\'hésitez pas à repasser une commande quand vous le souhaitez !', 'bot');
  });
}

// ── Bulle "Réflexion en cours..." animée ──────────────────────────────────────
const _THINKING_STEPS = [
  'Analyse de la demande...',
  'Classification en cours...',
  'Recherche dans la base de connaissances...',
  'Préparation de la réponse...',
  'Synthèse vocale...',
];

function addThinkingBubble() {
  const div = document.createElement('div');
  div.className = 'message bot thinking-msg';

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = '🤖';
  div.appendChild(avatar);

  const bubble = document.createElement('div');
  bubble.className = 'bubble thinking-bubble';

  const dotsEl = document.createElement('span');
  dotsEl.className = 'thinking-dots';
  dotsEl.textContent = '●●●';

  const textEl = document.createElement('span');
  textEl.className = 'thinking-text';
  textEl.textContent = _THINKING_STEPS[0];

  bubble.appendChild(dotsEl);
  bubble.appendChild(textEl);
  div.appendChild(bubble);
  chatArea.appendChild(div);
  scrollToBottom();

  // Rotation des messages toutes les 2,5s
  let idx = 0;
  const interval = setInterval(() => {
    idx = (idx + 1) % _THINKING_STEPS.length;
    textEl.textContent = _THINKING_STEPS[idx];
  }, 2500);

  // Retourne un objet avec remove() pour nettoyer proprement
  div.remove = () => {
    clearInterval(interval);
    div.parentNode?.removeChild(div);
  };
  return div;
}

// ── Bulle audio utilisateur ────────────────────────────────────────────────────
function addAudioBubble(blob) {
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);

  const div = document.createElement('div');
  div.className = 'message user';

  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  const playBtn = makePlayBtn(audio, '🎤 Message vocal');
  bubble.appendChild(playBtn);

  const transcriptEl = document.createElement('div');
  transcriptEl.className = 'audio-transcript';
  transcriptEl.textContent = '…';
  bubble.appendChild(transcriptEl);

  div.appendChild(bubble);
  chatArea.appendChild(div);
  scrollToBottom();
  return { bubble, transcriptEl };
}

// ── Affichage des messages ─────────────────────────────────────────────────────
function addMessage(text, type = 'bot') {
  const div = document.createElement('div');
  div.className = `message ${type}`;

  if (type !== 'user') {
    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = '🤖';
    div.appendChild(avatar);
  }

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = escapeHtml(text).replace(/\n/g, '<br>');
  div.appendChild(bubble);

  chatArea.appendChild(div);
  scrollToBottom();
  return bubble;
}

function addBotResponse(data) {
  const div = document.createElement('div');
  div.className = data.is_error ? 'message bot error' : 'message bot';

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = '🤖';
  div.appendChild(avatar);

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = escapeHtml(data.response_text || '(pas de réponse)').replace(/\n/g, '<br>');

  // Total de la commande si disponible
  if (data.order_total != null) {
    const totalEl = document.createElement('div');
    totalEl.className = 'order-total';
    totalEl.textContent = data.order_total > 0
      ? `Total estimé : ${data.order_total.toFixed(2)} €`
      : 'Total : prix à confirmer par notre équipe';
    bubble.appendChild(totalEl);
  }

  // Bouton lecture audio si disponible
  if (data.audio_base64) {
    const audio = base64ToAudio(data.audio_base64);
    const playBtn = makePlayBtn(audio, '▶ Écouter');
    bubble.appendChild(document.createElement('br'));
    bubble.appendChild(playBtn);

    stopCurrentAudio();
    audio.play().catch(() => {});
    currentAudio = audio;
    playBtn.textContent = '⏹ Arrêter';
  }

  if (data.intent && data.order_step !== 'awaiting_card') {
    const badge = document.createElement('div');
    badge.className = 'intent-badge';
    badge.textContent = intentLabel(data.intent, data.order_step);
    bubble.appendChild(badge);
  }

  div.appendChild(bubble);
  chatArea.appendChild(div);
  scrollToBottom();
}

// ── Bouton play/stop réutilisable ─────────────────────────────────────────────
function makePlayBtn(audio, label) {
  const btn = document.createElement('button');
  btn.className = 'btn-play-audio';
  btn.textContent = label;

  btn.addEventListener('click', () => {
    if (audio.paused) {
      stopCurrentAudio();
      audio.play().catch(() => {});
      currentAudio = audio;
      btn.textContent = '⏹ Arrêter';
    } else {
      audio.pause();
      audio.currentTime = 0;
      btn.textContent = label;
      currentAudio = null;
    }
  });

  audio.addEventListener('ended', () => {
    btn.textContent = label;
    if (currentAudio === audio) currentAudio = null;
  });

  return btn;
}

function stopCurrentAudio() {
  if (currentAudio && !currentAudio.paused) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
  }
}

// ── Conversion base64 → Audio ─────────────────────────────────────────────────
function base64ToAudio(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  // Détection du format depuis les magic bytes (WAV=RIFF, FLAC=fLaC, OGG=OggS, MP3=ID3/0xFF)
  let mime = 'audio/wav';
  if (bytes[0] === 0x66 && bytes[1] === 0x4C && bytes[2] === 0x61 && bytes[3] === 0x43) mime = 'audio/flac';
  else if (bytes[0] === 0x4F && bytes[1] === 0x67 && bytes[2] === 0x67 && bytes[3] === 0x53) mime = 'audio/ogg';
  else if (bytes[0] === 0x49 && bytes[1] === 0x44 && bytes[2] === 0x33) mime = 'audio/mpeg';
  const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
  return new Audio(url);
}

// ═══════════════════════════════════════════════════════════════════════════════
// Debug Panel
// ═══════════════════════════════════════════════════════════════════════════════

const debugFab     = document.getElementById('debugFab');
const debugOverlay = document.getElementById('debugOverlay');
const debugContent = document.getElementById('debugContent');
const debugBadge   = document.getElementById('debugOverallBadge');

debugFab.addEventListener('click', () => debugOpen());
document.getElementById('debugClose').addEventListener('click', () => debugClose());
document.getElementById('debugRefreshBtn').addEventListener('click', () => debugRefresh());
document.getElementById('debugTestBtn').addEventListener('click', () => debugFullTest());

// Fermer en cliquant sur le fond
debugOverlay.addEventListener('click', e => { if (e.target === debugOverlay) debugClose(); });
// Retirer aussi l'attribut hidden initial (héritage HTML, remplacé par la classe .open)
debugOverlay.removeAttribute('hidden');
// Fermer avec Escape
document.addEventListener('keydown', e => { if (e.key === 'Escape' && debugOverlay.classList.contains('open')) debugClose(); });

function debugOpen() {
  debugOverlay.classList.add('open');
  debugOverlay.removeAttribute('aria-hidden');
  debugRefresh();
}

function debugClose() {
  debugOverlay.classList.remove('open');
  debugOverlay.setAttribute('aria-hidden', 'true');
}

// ── Refresh (checks rapides) ──────────────────────────────────────────────────
async function debugRefresh() {
  debugContent.innerHTML = '<p class="debug-loading">⏳ Interrogation des services…</p>';
  debugBadge.className = 'debug-overall-badge dbg-spin';
  debugBadge.textContent = '…';

  try {
    const res = await fetch('/api/debug');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderDebug(data);
  } catch (err) {
    debugContent.innerHTML = `<div class="debug-section"><p style="color:#C62828;font-size:.85rem">
      Impossible de joindre l'agent : ${err.message}</p></div>`;
    debugBadge.className = 'debug-overall-badge dbg-err';
    debugBadge.textContent = 'erreur';
  }
}

// ── Test complet (appels réels LLM + TTS) ────────────────────────────────────
async function debugFullTest() {
  const btn = document.getElementById('debugTestBtn');
  btn.disabled = true;
  btn.textContent = '⏳ Test en cours…';

  // Conserver la section debug existante et ajouter le bloc test
  let testSection = document.getElementById('debugTestSection');
  if (!testSection) {
    testSection = document.createElement('div');
    testSection.id = 'debugTestSection';
    testSection.className = 'debug-section';
    debugContent.appendChild(testSection);
  }
  testSection.innerHTML = '<div class="debug-section-title">⚡ Test pipeline réel</div>' +
    '<p class="debug-loading" style="padding:8px 0">Appel LLM + TTS en cours (peut prendre 10–30 s)…</p>';

  try {
    const res = await fetch('/api/debug/test');
    const data = await res.json();
    renderTestResults(testSection, data.tests || {});
  } catch (err) {
    testSection.innerHTML += `<p style="color:#C62828;font-size:.82rem">Erreur : ${err.message}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '⚡ Test complet';
    testSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

// ── Rendus ────────────────────────────────────────────────────────────────────

const SERVICE_META = {
  ollama:    { icon: '🧠', label: 'LLM (Ollama local)' },
  stt:       { icon: '🎙', label: 'STT – Transcription' },
  tts:       { icon: '🔊', label: 'TTS – Synthèse vocale' },
  rag:       { icon: '📚', label: 'RAG – Base vectorielle' },
  hf_token:  { icon: '🔑', label: 'HuggingFace Token' },
};

function renderDebug(data) {
  const overall = data.overall || 'ok';
  const cls = { ok: 'dbg-ok', degraded: 'dbg-warn', error: 'dbg-err' }[overall] || 'dbg-spin';
  const lbl = { ok: '✓ OK', degraded: '⚠ Dégradé', error: '✗ Erreur' }[overall] || '…';
  debugBadge.className = `debug-overall-badge ${cls}`;
  debugBadge.textContent = lbl;

  let html = '';

  // Config active
  html += `<div class="debug-section">
    <div class="debug-section-title">Configuration active</div>
    ${cfgRow('LLM provider', data.config?.llm_provider || '?')}
    ${cfgRow('LLM model',    data.config?.llm_model    || '?')}
    ${cfgRow('STT service',  data.config?.stt_url      || '?')}
    ${cfgRow('TTS service',  data.config?.tts_url      || '?')}
    <div style="font-size:.72rem;color:#aaa;margin-top:6px;text-align:right">
      Diagnostics effectués en ${data.elapsed_ms ?? '?'} ms
    </div>
  </div>`;

  // Services
  html += `<div class="debug-section"><div class="debug-section-title">Services</div>`;
  for (const [key, info] of Object.entries(data.checks || {})) {
    html += renderServiceRow(key, info);
  }
  html += `</div>`;

  // Suggestions
  const sugs = data.suggestions || [];
  if (sugs.length > 0) {
    html += `<div class="debug-section"><div class="debug-section-title">💡 Solutions de repli</div>`;
    for (const s of sugs) html += renderSuggestion(s);
    html += `</div>`;
  }

  debugContent.innerHTML = html;

  // Réinsérer section test si elle existait
  const prev = document.getElementById('debugTestSection');
  if (!prev) {
    const ts = document.createElement('div');
    ts.id = 'debugTestSection';
    debugContent.appendChild(ts);
  }
}

function cfgRow(key, val) {
  return `<div class="debug-config-row">
    <span class="debug-config-key">${key}</span>
    <span class="debug-config-val" title="${val}">${val}</span>
  </div>`;
}

function renderServiceRow(key, info) {
  const meta  = SERVICE_META[key] || { icon: '⚙', label: key };
  const st    = info.status || 'error';
  const dotCls = { ok: 'dot-ok', warn: 'dot-warn', error: 'dot-error',
                   skipped: 'dot-skipped', degraded: 'dot-warn' }[st] || 'dot-error';
  const bdgCls = { ok: 'badge-ok', warn: 'badge-warn', error: 'badge-error',
                   skipped: 'badge-skipped', degraded: 'badge-warn' }[st] || 'badge-error';
  const bdgLbl = { ok: 'OK', warn: 'Dégradé', error: 'Erreur',
                   skipped: 'Inactif', degraded: 'Dégradé' }[st] || st;

  let detail = '';
  if (info.provider)   detail += `<span>provider: <b>${info.provider}</b></span>  `;
  if (info.model)      detail += `<span>modèle: <b>${info.model}</b></span>  `;
  if (info.voice)      detail += `<span>voix: <b>${info.voice}</b></span>  `;
  if (info.latency_ms !== undefined) detail += `<span>${info.latency_ms} ms</span>  `;
  if (info.chunks !== undefined)     detail += `<span>${info.chunks} chunks</span>  `;
  if (info.models_loaded?.length)    detail += `<span>modèles: ${info.models_loaded.join(', ')}</span>  `;
  if (info.llm_model)  detail += `<span>modèle LLM: <b>${info.llm_model}</b></span>  `;
  if (info.note)       detail += `<span style="color:#888">${info.note}</span>`;
  if (info.error)      detail += `<span class="debug-service-error">⚠ ${escHtml(info.error)}</span>`;

  return `<div class="debug-service-row">
    <div class="debug-dot ${dotCls}"></div>
    <div style="flex:1;min-width:0">
      <div class="debug-service-name">${meta.icon} ${meta.label}</div>
      ${detail ? `<div class="debug-service-meta">${detail}</div>` : ''}
    </div>
    <span class="debug-badge ${bdgCls}">${bdgLbl}</span>
  </div>`;
}

function renderSuggestion(s) {
  const cls = { error: 'sug-error', warning: 'sug-warning', info: 'sug-info' }[s.severity] || 'sug-info';
  const icon = { error: '🔴', warning: '🟡', info: '🔵' }[s.severity] || '💡';
  let html = `<div class="debug-suggestion ${cls}">
    <strong>${icon} ${escHtml(s.service)} — ${escHtml(s.message)}</strong>`;
  if (s.fix) html += `<div class="debug-fix">${escHtml(s.fix)}</div>`;
  if (s.alt) html += `<div class="debug-alt">Alternative : ${escHtml(s.alt)}</div>`;
  html += `</div>`;
  return html;
}

function renderTestResults(container, tests) {
  let html = '<div class="debug-section-title">⚡ Test pipeline réel</div>';
  for (const [key, res] of Object.entries(tests)) {
    const st = res.status || 'error';
    const dotCls = st === 'ok' ? 'dot-ok' : st === 'warn' ? 'dot-warn' : 'dot-error';
    const bdgCls = st === 'ok' ? 'badge-ok' : st === 'warn' ? 'badge-warn' : 'badge-error';
    const label = key === 'llm' ? '🧠 LLM' : key === 'tts' ? '🔊 TTS' : key;
    let detail = '';
    if (res.sample) detail = `« ${escHtml(res.sample)} »`;
    if (res.bytes)  detail = `${res.bytes} bytes audio`;
    if (res.error)  detail = `<span class="debug-service-error">${escHtml(res.error)}</span>`;

    html += `<div class="debug-test-row">
      <div class="debug-dot ${dotCls}" style="margin-top:1px"></div>
      <span class="debug-service-name">${label}</span>
      ${detail ? `<span style="flex:1;font-size:.8rem;color:#555;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${detail}</span>` : '<span style="flex:1"></span>'}
      <span class="debug-latency">${res.latency_ms ?? '?'} ms</span>
      <span class="debug-badge ${bdgCls}" style="margin-left:6px">${st}</span>
    </div>`;
    if (res.hint) html += `<div class="debug-hint">💡 ${escHtml(res.hint)}</div>`;
  }
  container.innerHTML = html;
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Labels d'intention ────────────────────────────────────────────────────────
function intentLabel(intent, step) {
  const stepLabels = {
    awaiting_name:    '👤 En attente : nom / prénom / téléphone',
    awaiting_phone:   '📞 En attente : téléphone',
    awaiting_payment: '💰 En attente : mode de paiement',
    awaiting_card:    '💳 En attente : paiement CB',
    complete:         '✅ Commande confirmée',
  };
  if (step && stepLabels[step]) return stepLabels[step];

  const labels = {
    info:              '📋 Informations',
    commande_simple:   '🛒 Commande en cours',
    commande_complexe: '🛒 Commande complexe en cours',
    autre:             '💬 Conversation',
  };
  return labels[intent] || intent;
}

// ── Utilitaires ───────────────────────────────────────────────────────────────
function scrollToBottom() { chatArea.scrollTop = chatArea.scrollHeight; }
function setStatus(msg)    { statusBar.textContent = msg; }
function setInputEnabled(enabled) {
  textInput.disabled = !enabled;
  sendBtn.disabled   = !enabled;
  micBtn.disabled    = !enabled;
}
function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Event listeners ───────────────────────────────────────────────────────────
sendBtn.addEventListener('click', sendText);
textInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendText(); });
micBtn.addEventListener('mousedown',  startRecording);
micBtn.addEventListener('mouseup',    stopRecording);
micBtn.addEventListener('mouseleave', stopRecording);
micBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); });
micBtn.addEventListener('touchend',   (e) => { e.preventDefault(); stopRecording(); });

// ── Init ──────────────────────────────────────────────────────────────────────
checkHealth();
setInterval(checkHealth, 30_000);
