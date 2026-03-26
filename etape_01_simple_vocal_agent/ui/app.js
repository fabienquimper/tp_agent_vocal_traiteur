/**
 * Interface vocale – Traiteur Dupont
 * ────────────────────────────────────
 * Gère :
 *   - La saisie texte (envoi au /api/text)
 *   - L'enregistrement vocal (envoi au /api/voice)
 *   - L'affichage de la conversation
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
let currentAudio   = null;   // Audio en cours de lecture

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
      body: JSON.stringify({ text, skip_tts: false }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    addBotResponse(data);
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

  // Affiche immédiatement la bulle audio avec bouton lecture
  const { transcriptEl } = addAudioBubble(blob);

  try {
    const formData = new FormData();
    formData.append('audio', blob, 'recording.wav');

    const res = await fetch(`${API_BASE}/voice`, { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();

    // Met à jour la transcription dans la bulle audio
    transcriptEl.textContent = data.transcript || '(inaudible)';

    addBotResponse(data);
  } catch (err) {
    transcriptEl.textContent = '(erreur)';
    addMessage(`Erreur audio : ${err.message}`, 'bot error');
  } finally {
    micLabel.textContent = 'Maintenir pour parler';
    setStatus('');
    setInputEnabled(true);
  }
}

// ── Bulle audio utilisateur (affichée avant la réponse) ───────────────────────
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

  // Bouton lecture audio si disponible
  if (data.audio_base64) {
    const audio = base64ToAudio(data.audio_base64);
    const playBtn = makePlayBtn(audio, '▶ Écouter');
    bubble.appendChild(document.createElement('br'));
    bubble.appendChild(playBtn);

    // Lecture automatique
    stopCurrentAudio();
    audio.play().catch(() => {});
    currentAudio = audio;
    playBtn.textContent = '⏹ Arrêter';
  }

  if (data.intent) {
    const badge = document.createElement('div');
    badge.className = 'intent-badge';
    badge.textContent = intentLabel(data.intent);
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
function intentLabel(intent) {
  const labels = {
    info:              '📋 Informations',
    commande_simple:   '✅ Commande enregistrée',
    commande_complexe: '📞 Commande transmise à l\'équipe',
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
