
// Newline char — defined once here, avoids Python \n→literal-newline bug inside strings
var NL = String.fromCharCode(10);

// ── Markdown renderer ──────────────────────────────────────────────────────
function renderMarkdown(text) {
    if (!text) return '';
    var NL = String.fromCharCode(10);
    var s = text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    // Fenced code blocks — split on ``` marker pairs
    var parts = s.split('```');
    for (var i = 1; i < parts.length; i += 2) {
        var code = parts[i];
        var firstNL = code.indexOf(NL);
        if (firstNL >= 0) {
            var tag = code.substring(0, firstNL).trim();
            if (/^[a-z]*$/.test(tag)) { code = code.substring(firstNL + 1); }
        }
        parts[i] = '<pre><code>' + code + '</code></pre>';
    }
    s = parts.join('');
    // Inline code
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Bold  — no regex backslash needed: split on marker
    s = s.split('**').map(function(p,i){return i%2===1?'<strong>'+p+'</strong>':p;}).join('');
    // Italic  — single *text* (not **bold**)
    s = s.replace(/([^*]|^)[*]([^*]+)[*]/g, '$1<em>$2</em>');
    // Headers  (# / ## / ###)
    s = s.replace(/^#{1,3} (.+)$/gm,
        '<strong style="font-size:1.02em;display:block;margin-bottom:0.2rem">$1</strong>');
    // Unordered list
    s = s.replace(/^[-*] (.+)$/gm,
        '<span style="display:block;padding-left:1rem;margin:0.1rem 0">• $1</span>');
    // Ordered list
    s = s.replace(/^[0-9]+[.] (.+)$/gm,
        '<span style="display:block;padding-left:1rem;margin:0.1rem 0">• $1</span>');
    // Newlines → <br>
    s = s.split(NL).join('<br>');
    return s;
}

// ── State ─────────────────────────────────────────────────────────────────
var isSending      = false;
var _streamDiv     = null;
var _streamRawText = '';

// ── Helpers ───────────────────────────────────────────────────────────────
function scrollBottom() {
    var box = document.getElementById('chat-messages');
    box.scrollTop = box.scrollHeight;
}

function hideWelcome() {
    var w = document.getElementById('welcome-card');
    if (w) w.style.display = 'none';
}

function quickSend(text) {
    document.getElementById('chat-input').value = text;
    sendChat();
}

// ── Add message row ────────────────────────────────────────────────────────
function addChat(who, text, type) {
    hideWelcome();
    var box  = document.getElementById('chat-messages');
    var row  = document.createElement('div');
    row.className = 'msg-row ' + who;

    var av   = document.createElement('div');
    av.className = 'msg-avatar ' + (who === 'ai' ? 'ai-av' : 'user-av');
    av.textContent = who === 'ai' ? '✦' : '👤';

    var bub  = document.createElement('div');
    bub.className = 'chat-bubble ' + who + (type ? ' ' + type : '');

    if (who === 'ai') {
        bub.innerHTML = renderMarkdown(text);
    } else {
        bub.textContent = text;
    }

    row.appendChild(av);
    row.appendChild(bub);
    box.appendChild(row);
    scrollBottom();
    return bub;
}

// ── Streaming ─────────────────────────────────────────────────────────────
function _createStreamBubble() {
    hideWelcome();
    _streamRawText = '';
    var box  = document.getElementById('chat-messages');
    var row  = document.createElement('div');
    row.className = 'msg-row ai';
    row.id = 'stream-row';

    var av   = document.createElement('div');
    av.className = 'msg-avatar ai-av';
    av.textContent = '✦';

    var bub  = document.createElement('div');
    bub.className = 'chat-bubble ai streaming';
    var cur  = document.createElement('span');
    cur.className = 'stream-cursor';
    bub.appendChild(cur);

    row.appendChild(av);
    row.appendChild(bub);
    box.appendChild(row);
    scrollBottom();
    return bub;
}

function appendChatChunk(text) {
    if (!_streamDiv) return;
    _streamRawText += text;
    var cur = _streamDiv.querySelector('.stream-cursor');
    if (cur) _streamDiv.insertBefore(document.createTextNode(text), cur);
    else     _streamDiv.appendChild(document.createTextNode(text));
    scrollBottom();
}

function finishChatStreamB64(b64) {
    try {
        _finalizeStream(JSON.parse(atob(b64)));
    } catch(e) {
        console.error('finishChatStreamB64:', e);
        if (_streamDiv) _streamDiv.classList.remove('streaming');
        _streamDiv = null; isSending = false;
    }
}

function _finalizeStream(data) {
    if (!_streamDiv) { isSending = false; return; }
    var cur = _streamDiv.querySelector('.stream-cursor');
    if (cur) cur.remove();
    _streamDiv.classList.remove('streaming');

    if (data.response_type === 'confirm' && data.pending_confirmation) {
        var _row = _streamDiv.parentElement;
        if (_row) _row.remove();
        _streamDiv = null; isSending = false;
        addConfirmation(data.text, data.pending_confirmation);
        return;
    }

    var finalText = data.text || _streamRawText || '';
    if (finalText) _streamDiv.innerHTML = renderMarkdown(finalText);
    _streamRawText = '';

    if (data.response_type === 'success') _streamDiv.classList.add('success');
    else if (data.response_type === 'warning') _streamDiv.classList.add('warning');
    else if (data.response_type === 'error')   _streamDiv.classList.add('error');

    _streamDiv = null; isSending = false;
}

// ── Send ──────────────────────────────────────────────────────────────────
async function sendChat() {
    if (isSending) return;
    var inp = document.getElementById('chat-input');
    var msg = inp.value.trim();
    if (!msg) return;
    inp.value = '';
    addChat('user', msg);
    isSending = true;
    _streamDiv = _createStreamBubble();
    try {
        var raw = await pywebview.api.start_chat_stream(msg);
        var r   = JSON.parse(raw);
        if (r.status !== 'streaming') {
            if (_streamDiv) {
                var cur2 = _streamDiv.querySelector('.stream-cursor');
                if (cur2) cur2.remove();
                _streamDiv.classList.remove('streaming');
                _streamDiv.innerHTML = renderMarkdown(r.response || '');
            }
            _streamDiv = null; isSending = false;
        }
    } catch(e) {
        if (_streamDiv) { _streamDiv.classList.remove('streaming'); _streamDiv.textContent = 'Hata: ' + e.message; }
        _streamDiv = null; isSending = false;
    }
}

// ── Mic ───────────────────────────────────────────────────────────────────
async function listenMic() {
    if (isSending) return;
    var btn = document.getElementById('mic-btn');
    btn.classList.add('listening');
    isSending = true;

    // placeholder listening row
    var box = document.getElementById('chat-messages');
    var lRow = document.createElement('div');
    lRow.className = 'msg-row user'; lRow.id = 'mic-listening';
    var lAv = document.createElement('div');
    lAv.className = 'msg-avatar user-av'; lAv.textContent = '👤';
    var lBub = document.createElement('div');
    lBub.className = 'chat-bubble user'; lBub.style.opacity = '0.5';
    lBub.textContent = '🎤 Dinleniyor...';
    lRow.appendChild(lAv); lRow.appendChild(lBub);
    box.appendChild(lRow); scrollBottom();

    try {
        var raw = await pywebview.api.listen_voice();
        var r   = JSON.parse(raw);
        if (r.status === 'recording') return;  // async — wait for receiveVoiceResult
        _handleVoiceResult(r);
    } catch(e) {
        var ml = document.getElementById('mic-listening');
        if (ml) ml.remove();
        addChat('ai', 'Ses hatası: ' + (e.message || e), 'warning');
        _resetMic();
    }
}

function receiveVoiceResult(raw) {
    try { _handleVoiceResult(JSON.parse(raw)); }
    catch(e) { addChat('ai', 'Sonuç alınamadı: ' + e, 'warning'); _resetMic(); }
}

function _handleVoiceResult(r) {
    var mlr = document.getElementById('mic-listening');
    if (mlr) mlr.remove();
    if (r.recognized_text) addChat('user', r.recognized_text);
    else if (!r.response || r.type !== 'warning') addChat('user', '🎤 (Anlaşılamadı)');
    if (r.type === 'confirm' && r.pending_confirmation)
        addConfirmation(r.response, r.pending_confirmation);
    else if (r.response) addChat('ai', r.response, r.type);
    _resetMic();
}

function _resetMic() {
    isSending = false;
    var mb = document.getElementById('mic-btn');
    if (mb) mb.classList.remove('listening');
}

// ── Confirmations ──────────────────────────────────────────────────────────
function addConfirmation(message, confirmation) {
    hideWelcome();
    var box  = document.getElementById('chat-messages');
    var row  = document.createElement('div');
    row.className = 'msg-row ai';
    var av   = document.createElement('div');
    av.className = 'msg-avatar ai-av'; av.textContent = '✦';
    var bub  = document.createElement('div');
    bub.className = 'chat-bubble ai confirm';
    var msgHtml = message.split(NL).join('<br>');
    bub.innerHTML =
        '<div style="margin-bottom:0.5rem">' + msgHtml + '</div>' +
        '<div class="confirm-btns">' +
          '<button class="confirm-btn yes" onclick="handleConfirm(\'' + confirmation.tool_name + '\',true,this)">✓ Evet, yap</button>' +
          '<button class="confirm-btn no"  onclick="handleConfirm(\'' + confirmation.tool_name + '\',false,this)">✗ Hayır, iptal</button>' +
        '</div>';
    row.appendChild(av); row.appendChild(bub);
    box.appendChild(row); scrollBottom();
}

async function handleConfirm(toolName, approved, btn) {
    var btns = btn.parentElement.querySelectorAll('button');
    for (var i = 0; i < btns.length; i++) btns[i].disabled = true;
    try {
        var raw = await pywebview.api.confirm_action(toolName, approved);
        var r   = JSON.parse(raw);
        addChat('ai', r.response, r.type);
    } catch(e) {
        addChat('ai', 'Hata: ' + (e.message || e), 'warning');
    }
}

// ── LLM status ────────────────────────────────────────────────────────────
async function checkLLMStatus() {
    try {
        var raw = await pywebview.api.get_llm_status();
        var r   = JSON.parse(raw);
        var pill  = document.getElementById('llm-status');
        var label = document.getElementById('llm-label');
        var mname = document.getElementById('model-name');
        if (r.available) {
            pill.className = 'status-pill online';
            label.textContent = 'Bağlı';
            if (mname) mname.textContent = r.active_model || 'gemma3:1b';
        } else {
            pill.className = 'status-pill offline';
            label.textContent = 'Offline';
            if (mname) mname.textContent = 'Ollama kapalı';
        }
    } catch(e) {
        var mn = document.getElementById('model-name');
        if (mn) mn.textContent = 'Bağlanıyor...';
    }
}

// ── Init ──────────────────────────────────────────────────────────────────
window.addEventListener('pywebviewready', () => {
    checkLLMStatus();
    setInterval(checkLLMStatus, 15000);
});

window.onerror = function(msg, src, line) {
    var box = document.getElementById('chat-messages');
    if (box) {
        var err = document.createElement('div');
        err.style.cssText = 'color:#f87171;font-size:0.75rem;padding:0.5rem;text-align:center;opacity:0.7';
        err.textContent = 'JS Hata: ' + msg + ' (' + line + ')';
        box.appendChild(err);
    }
};
