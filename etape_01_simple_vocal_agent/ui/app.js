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
  setStatus('Traitement en cours...');
  setInputEnabled(false);

  try {
    const res = await fetch(`${API_BASE}/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, session_id: sessionId, skip_tts: false }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    handleAgentResponse(data);
  } catch (err) {
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
    const formData = new FormData();
    formData.append('audio', blob, 'recording.wav');
    if (sessionId) formData.append('session_id', sessionId);

    const res = await fetch(`${API_BASE}/voice`, { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    transcriptEl.textContent = data.transcript || '(inaudible)';
    handleAgentResponse(data);
  } catch (err) {
    transcriptEl.textContent = '(erreur)';
    addMessage(`Erreur audio : ${err.message}`, 'bot error');
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
  const url = URL.createObjectURL(new Blob([bytes], { type: 'audio/wav' }));
  return new Audio(url);
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
