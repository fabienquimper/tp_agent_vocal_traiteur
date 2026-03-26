/**
 * Interface vocale – Traiteur Dupont
 * ────────────────────────────────────
 * Gère :
 *   - La saisie texte (envoi au /api/text)
 *   - L'enregistrement vocal (envoi au /api/voice)
 *   - L'affichage de la conversation
 *   - La lecture audio de la réponse
 */

'use strict';

// ── Configuration ──────────────────────────────────────────────────────────────
const API_BASE = '/api';          // Proxy nginx → agent:8000
const HEALTH_URL = '/api/../health';  // Vérifié au chargement

// ── Éléments DOM ───────────────────────────────────────────────────────────────
const chatArea   = document.getElementById('chatArea');
const textInput  = document.getElementById('textInput');
const sendBtn    = document.getElementById('sendBtn');
const micBtn     = document.getElementById('micBtn');
const micLabel   = document.getElementById('micLabel');
const statusBar  = document.getElementById('statusBar');
const statusDot  = document.getElementById('statusDot');

// ── État de l'enregistrement ──────────────────────────────────────────────────
let mediaRecorder = null;
let audioChunks   = [];
let isRecording   = false;

// ── Vérification de l'état du service ─────────────────────────────────────────
async function checkHealth() {
  try {
    const res = await fetch('/health');
    if (res.ok) {
      statusDot.className = 'status-dot online';
      statusDot.title = 'Service disponible';
    } else {
      throw new Error();
    }
  } catch {
    statusDot.className = 'status-dot offline';
    statusDot.title = 'Service indisponible';
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
      body: JSON.stringify({ text, skip_tts: false }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    addBotResponse(data);
    if (data.audio_base64) playAudioBase64(data.audio_base64);

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

    // Préférer le format WAV si supporté, sinon WebM
    const mimeType = MediaRecorder.isTypeSupported('audio/wav')
      ? 'audio/wav'
      : 'audio/webm';

    mediaRecorder = new MediaRecorder(stream, { mimeType });
    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(audioChunks, { type: mimeType });
      sendAudio(blob);
    };

    mediaRecorder.start();
    isRecording = true;
    micBtn.classList.add('recording');
    micLabel.textContent = 'Parlez... (relâcher pour envoyer)';
    setStatus('Enregistrement en cours...');

  } catch (err) {
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

  try {
    const formData = new FormData();
    formData.append('audio', blob, 'recording.wav');

    const res = await fetch(`${API_BASE}/voice`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // Affiche ce que le client a dit (transcription)
    if (data.transcript) addMessage(data.transcript, 'user');

    addBotResponse(data);
    if (data.audio_base64) playAudioBase64(data.audio_base64);

  } catch (err) {
    addMessage(`Erreur audio : ${err.message}`, 'bot error');
  } finally {
    micLabel.textContent = 'Maintenir pour parler';
    setStatus('');
    setInputEnabled(true);
  }
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
  const bubble = addMessage(data.response_text || '(pas de réponse)', 'bot');

  // Affiche le badge d'intention en sous-texte
  if (data.intent) {
    const badge = document.createElement('div');
    badge.className = 'intent-badge';
    badge.textContent = intentLabel(data.intent);
    bubble.appendChild(badge);
  }
}

function intentLabel(intent) {
  const labels = {
    info:                '📋 Informations',
    commande_simple:     '✅ Commande enregistrée',
    commande_complexe:   '📞 Commande transmise à l\'équipe',
    autre:               '💬 Conversation',
  };
  return labels[intent] || intent;
}

// ── Lecture audio ─────────────────────────────────────────────────────────────
function playAudioBase64(base64) {
  try {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    playAudioBuffer(bytes.buffer);
  } catch (err) {
    console.warn('Lecture audio échouée :', err);
  }
}

function playAudioBuffer(arrayBuffer) {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  ctx.decodeAudioData(arrayBuffer, (buffer) => {
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.start(0);
    source.onended = () => ctx.close();
  }, (err) => console.warn('Décodage audio échoué :', err));
}

// ── Utilitaires ───────────────────────────────────────────────────────────────
function scrollToBottom() {
  chatArea.scrollTop = chatArea.scrollHeight;
}

function setStatus(msg) {
  statusBar.textContent = msg;
}

function setInputEnabled(enabled) {
  textInput.disabled  = !enabled;
  sendBtn.disabled    = !enabled;
  micBtn.disabled     = !enabled;
}

function escapeHtml(str) {
  return str
    .replace(/&/g,  '&amp;')
    .replace(/</g,  '&lt;')
    .replace(/>/g,  '&gt;')
    .replace(/"/g,  '&quot;');
}

// ── Event listeners ───────────────────────────────────────────────────────────
sendBtn.addEventListener('click', sendText);
textInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendText(); });

// Enregistrement vocal : maintenir le bouton
micBtn.addEventListener('mousedown',  startRecording);
micBtn.addEventListener('mouseup',    stopRecording);
micBtn.addEventListener('mouseleave', stopRecording);  // Sécurité si souris quitte le bouton
micBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); });
micBtn.addEventListener('touchend',   (e) => { e.preventDefault(); stopRecording(); });

// ── Initialisation ────────────────────────────────────────────────────────────
checkHealth();
setInterval(checkHealth, 30_000);  // Vérification toutes les 30s
