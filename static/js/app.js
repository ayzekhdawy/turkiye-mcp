
// ===== State =====
const PROVIDERS = {
  openrouter: { name: "OpenRouter", needs_key: true, models: ["openai/gpt-4o-mini","anthropic/claude-3.5-sonnet","google/gemini-2.0-flash","meta-llama/llama-3.1-8b-instruct"], default_model: "openai/gpt-4o-mini" },
  openai: { name: "OpenAI", needs_key: true, models: ["gpt-4o-mini","gpt-4o","gpt-4-turbo"], default_model: "gpt-4o-mini" },
  anthropic: { name: "Anthropic", needs_key: true, models: ["claude-sonnet-4-20250514","claude-haiku-4-20250414"], default_model: "claude-haiku-4-20250414" },
  gemini: { name: "Google Gemini", needs_key: true, models: ["gemini-2.0-flash","gemini-1.5-pro"], default_model: "gemini-2.0-flash" },
  ollama_cloud: { name: "Ollama Cloud", needs_key: true, models: ["gpt-oss:120b","gpt-oss:20b","deepseek-v3.1:671b","qwen3-coder:480b","glm-4.6","kimi-k2:1t","qwen3:235b"], default_model: "gpt-oss:120b" },
  ollama: { name: "Ollama (Yerel)", needs_key: false, models: ["llama3.2","llama3.1","mistral","qwen2.5","gemma2","gpt-oss:20b"], default_model: "llama3.2" },
};

// Çalışma alanı durumu (sunucu = kaynak; localStorage = yedek)
let folders = [];               // [{id,name,created}]
let chats = JSON.parse(localStorage.getItem('turkiye_mcp_chats') || '[]'); // tam oturumlar (cache)
let activeChatId = localStorage.getItem('turkiye_mcp_active_chat') || null;
let collapsed = JSON.parse(localStorage.getItem('turkiye_mcp_collapsed') || '{}');
let serverOk = false;           // workspace API erişilebilir mi
let draggingSessionId = null;

// LLM yapılandırması — sağlayıcı başına ayrı anahtar
let currentProvider = localStorage.getItem('llm-provider') || 'openrouter';
let currentModel = localStorage.getItem('llm-model') || '';
let apiKeys = {};
try { apiKeys = JSON.parse(localStorage.getItem('llm-keys') || '{}'); } catch(e) { apiKeys = {}; }
// Geriye uyumluluk: eski tek anahtar
if (localStorage.getItem('llm-api-key') && !apiKeys[currentProvider]) {
  apiKeys[currentProvider] = localStorage.getItem('llm-api-key');
}
function keyFor(p){ return apiKeys[p] || ''; }
// Failover: yedek model zinciri [{provider, model}]
let fallbacks = [];
try { fallbacks = JSON.parse(localStorage.getItem('llm-fallbacks') || '[]'); } catch(e) { fallbacks = []; }
function getFallbacks(){ return fallbacks; }
// Tercihler
let currentTheme = localStorage.getItem('ui-theme') || 'dark';
let tokenBudget = parseInt(localStorage.getItem('token-budget') || '0', 10) || 0;
let gwTimeout = parseInt(localStorage.getItem('gw-timeout') || '0', 10) || 0;
let autoMemory = localStorage.getItem('auto-memory') !== '0'; // varsayılan açık
let budgetWarned = false;
function applyTheme(v){
  currentTheme = v || 'dark';
  document.body.classList.toggle('light', currentTheme === 'light');
  localStorage.setItem('ui-theme', currentTheme);
}

// Daraltılabilir kenar çubuğu
let sidebarCollapsed = localStorage.getItem('sidebar-collapsed') === '1';
function applySidebar(){
  const shell = document.querySelector('.shell');
  if (shell) shell.classList.toggle('sidebar-collapsed', sidebarCollapsed);
}
function toggleSidebar(){
  sidebarCollapsed = !sidebarCollapsed;
  localStorage.setItem('sidebar-collapsed', sidebarCollapsed ? '1' : '0');
  applySidebar();
}

// ===== Profesyonel ikon seti (lucide tarzı, tek tip çizgi ikonlar) =====
const ICONS = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  trash: '<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  scale: '<path d="M12 3v18M5 7h14M7 7l-3 7a4 4 0 0 0 6 0zM17 7l-3 7a4 4 0 0 0 6 0zM7 21h10"/>',
  plug: '<path d="M9 2v5M15 2v5M6 7h12v4a6 6 0 0 1-12 0zM12 17v5"/>',
  zap: '<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z"/>',
  wrench: '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.7 2.7-2.3-.4-.4-2.3 2.8-2.7z"/>',
  sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
  cog: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 0 1-4 0v-.1A1.6 1.6 0 0 0 6.7 19l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3 13.4H3a2 2 0 0 1 0-4h.1A1.6 1.6 0 0 0 5 6.7l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 10.6 3V3a2 2 0 0 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-1.1 2.7H21a2 2 0 0 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>',
  refs: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M9 13h6M9 17h4"/>',
  clipboard: '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>',
  filetext: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M9 13h6M9 17h4"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>'
};
function ic(name, cls){
  return '<svg class="ico' + (cls ? ' ' + cls : '') + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + (ICONS[name] || '') + '</svg>';
}
let isSending = false;
let saveTimer = null;

// ===== Toast =====
function toast(msg, isErr) {
  let t = document.getElementById('toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; document.body.appendChild(t); }
  t.textContent = msg;
  t.className = 'toast show' + (isErr ? ' err' : '');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.className = 'toast' + (isErr ? ' err' : ''); }, 2600);
}

// ===== Server sync =====
async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok && res.status >= 500) throw new Error('server ' + res.status);
  return res;
}

async function bootstrapWorkspace() {
  try {
    const res = await fetch('/api/workspace', {signal: AbortSignal.timeout(4000)});
    const data = await res.json();
    if (data.error) { serverOk = false; return; }
    serverOk = true;
    folders = data.folders || [];
    // Sunucu oturum metalarını yerel cache ile birleştir
    const metas = data.sessions || [];
    const byId = {};
    chats.forEach(c => byId[c.id] = c);
    // Sunucudaki her oturum için meta'yı uygula (mesajlar tembel yüklenir)
    metas.forEach(m => {
      const ex = byId[m.id];
      if (ex) { ex.title = m.title; ex.folderId = m.folderId; ex.updated = m.updated; ex._meta = true; }
      else { byId[m.id] = { id: m.id, title: m.title, folderId: m.folderId, updated: m.updated, messages: null, attachments: [], _meta: true }; }
    });
    chats = Object.values(byId).sort((a,b) => (b.updated||0) - (a.updated||0));
  } catch(e) {
    serverOk = false; // localStorage moduna düş
  }
}

// ===== Server Status =====
async function checkServerStatus() {
  try {
    const res = await fetch('/health', {signal: AbortSignal.timeout(3000)});
    const data = await res.json();
    const el = document.getElementById('server-status');
    el.className = 'status';
    el.innerHTML = '<span class="sdot"></span><span>' + (data.active_count||'?') + '/' + (data.total_count||'?') + ' modül aktif</span>';
  } catch(e) {
    const el = document.getElementById('server-status');
    el.className = 'status off';
    el.innerHTML = '<span class="sdot"></span><span>Bağlantı hatası</span>';
  }
}
checkServerStatus();
setInterval(checkServerStatus, 30000);

// ===== Chat & Workspace Management =====
function generateId() { return 's_' + Date.now().toString(36) + Math.random().toString(36).substr(2, 5); }

function generateTitle(msg) {
  const lower = msg.toLowerCase();
  const titleMap = {
    'yargitay':'Yargıtay Kararları','danistay':'Danıştay Kararları',
    'anayasa':'Anayasa Mahkemesi','asgari':'Asgari Ücret','resmi gazete':'Resmi Gazete',
    'ihale':'İhale Arama','borsa':'Borsa Verileri','doviz':'Döviz Kurları',
    'emsal':'Emsal Kararlar','sgk':'SGK Sorgulama','iskur':'İŞKUR Duyuruları',
    'mevzuat':'Mevzuat Arama','gib':'GİB Sirküler','kvkk':'KVKK Kararları',
    'kik':'KİK Kararları','sayistay':'Sayıştay Kararları',
  };
  for (const [kw, title] of Object.entries(titleMap)) {
    if (lower.includes(kw)) return title;
  }
  return msg.length > 35 ? msg.substring(0, 35) + '...' : msg;
}

function getActiveChat() { return chats.find(c => c.id === activeChatId); }

function newChat(folderId) {
  const chat = { id: generateId(), title: 'Yeni Sohbet', messages: [], attachments: [], folderId: folderId || null, created: Date.now(), updated: Date.now() };
  chats.unshift(chat);
  activeChatId = chat.id;
  saveChats();
  renderTree();
  renderChat();
  document.getElementById('chat-input').focus();
}

function saveChats() {
  // Yalnızca yüklenmiş (mesajları olan) oturumları yerel cache'e yaz
  const cache = chats.filter(c => Array.isArray(c.messages));
  try { localStorage.setItem('turkiye_mcp_chats', JSON.stringify(cache)); } catch(e) {}
  localStorage.setItem('turkiye_mcp_active_chat', activeChatId || '');
}

// Sunucuya kalıcı kaydet (debounce)
function persistSession(chat, immediate) {
  if (!chat) return;
  saveChats();
  if (!serverOk) return;
  const doSave = () => {
    fetch('/api/workspace/session', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        id: chat.id, title: chat.title, folderId: chat.folderId || null,
        messages: chat.messages || [], attachments: chat.attachments || [],
        created: chat.created, updated: Date.now()
      })
    }).catch(()=>{});
  };
  clearTimeout(saveTimer);
  if (immediate) doSave(); else saveTimer = setTimeout(doSave, 700);
}

// ----- Klasör işlemleri -----
async function createFolder() {
  const name = prompt('Klasör adı:', 'Yeni Klasör');
  if (!name) return;
  if (serverOk) {
    try {
      const r = await (await fetch('/api/workspace/folder', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'create',name})})).json();
      if (r.folder) folders.push(r.folder);
    } catch(e) { toast('Klasör oluşturulamadı', true); return; }
  } else {
    folders.push({ id: 'f_' + Date.now().toString(36), name, created: Date.now() });
  }
  renderTree();
}

async function renameFolder(id) {
  const f = folders.find(x => x.id === id); if (!f) return;
  const name = prompt('Klasör adı:', f.name);
  if (!name) return;
  f.name = name;
  if (serverOk) fetch('/api/workspace/folder', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'rename',id,name})}).catch(()=>{});
  renderTree();
}

async function deleteFolder(id) {
  if (!confirm('Klasör silinsin mi? İçindeki sohbetler "Genel" altına taşınır.')) return;
  folders = folders.filter(f => f.id !== id);
  chats.forEach(c => { if (c.folderId === id) c.folderId = null; });
  if (serverOk) fetch('/api/workspace/folder', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'delete',id})}).catch(()=>{});
  renderTree();
}

function toggleFolder(id) {
  collapsed[id] = !collapsed[id];
  localStorage.setItem('turkiye_mcp_collapsed', JSON.stringify(collapsed));
  renderTree();
}

function moveSession(sessionId, folderId) {
  const c = chats.find(x => x.id === sessionId); if (!c) return;
  c.folderId = folderId;
  if (serverOk) fetch('/api/workspace/session/delete', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:sessionId,action:'move',folderId})}).catch(()=>{});
  persistSession(c, true);
  renderTree();
}

// ----- Ağaç çizimi (data-attribute + delegated listener) -----
function sessionRowHtml(c) {
  const clip = (c.attachments && c.attachments.length) ? '<span class="sclip">📎</span>' : '';
  const act = (c.id === activeChatId ? ' active' : '');
  return '<div class="session-row' + act + '" draggable="true" data-row="session" data-id="' + c.id + '">' +
    '<span class="dot"></span>' + clip +
    '<span class="stitle">' + escapeHtml(c.title || 'Sohbet') + '</span>' +
    '<span class="del-btn" data-act="del-session" data-id="' + c.id + '">×</span></div>';
}

function folderRowHtml(fid, name, count, isCol, isGeneral) {
  const menu = isGeneral ? '' : (
    '<span class="fmenu" title="Yeni sohbet" data-act="folder-new" data-fid="' + fid + '">' + ic('plus') + '</span>' +
    '<span class="fmenu" title="Yeniden adlandır" data-act="folder-rename" data-fid="' + fid + '">' + ic('edit') + '</span>' +
    '<span class="fmenu" title="Sil" data-act="folder-del" data-fid="' + fid + '">' + ic('trash') + '</span>');
  return '<div class="folder-row' + (isCol ? ' collapsed' : '') + '" data-row="folder" data-fid="' + fid + '">' +
    '<svg class="caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M9 6l6 6-6 6"/></svg>' +
    '<span class="fname">' + escapeHtml(name) + '</span>' +
    '<span class="fcount">' + count + '</span>' + menu + '</div>';
}

function renderTree() {
  const tree = document.getElementById('tree');
  if (!tree) return;
  let html = '';

  folders.forEach(f => {
    const fSessions = chats.filter(c => c.folderId === f.id);
    const isCol = !!collapsed[f.id];
    html += folderRowHtml(f.id, f.name, fSessions.length, isCol, false);
    if (!isCol) html += fSessions.map(sessionRowHtml).join('');
  });

  const ungrouped = chats.filter(c => !c.folderId);
  const genCol = !!collapsed['__general__'];
  if (folders.length > 0 || ungrouped.length > 0) {
    html += folderRowHtml('__general__', 'Genel', ungrouped.length, genCol, true);
    if (!genCol) html += ungrouped.map(sessionRowHtml).join('');
  }

  if (chats.length === 0 && folders.length === 0) {
    html = '<div class="tree-empty">Henüz sohbet yok.<br>Bir soru sorun veya klasör oluşturun.</div>';
  }
  tree.innerHTML = html;
}

// Ağaç olaylarını tek bir delegasyonla bağla (bir kez)
function setupTree() {
  const tree = document.getElementById('tree');
  if (!tree || tree._wired) return;
  tree._wired = true;

  tree.addEventListener('click', (e) => {
    const actEl = e.target.closest('[data-act]');
    if (actEl) {
      e.stopPropagation();
      const act = actEl.getAttribute('data-act');
      const fid = actEl.getAttribute('data-fid');
      const id = actEl.getAttribute('data-id');
      if (act === 'del-session') deleteChat(id);
      else if (act === 'folder-new') newChat(fid);
      else if (act === 'folder-rename') renameFolder(fid);
      else if (act === 'folder-del') deleteFolder(fid);
      return;
    }
    const folderRow = e.target.closest('.folder-row');
    if (folderRow) { toggleFolder(folderRow.getAttribute('data-fid')); return; }
    const sessRow = e.target.closest('.session-row');
    if (sessRow) selectChat(sessRow.getAttribute('data-id'));
  });

  tree.addEventListener('dragstart', (e) => {
    const row = e.target.closest('.session-row');
    if (row) draggingSessionId = row.getAttribute('data-id');
  });
  tree.addEventListener('dragover', (e) => {
    const fr = e.target.closest('.folder-row');
    if (fr) { e.preventDefault(); fr.classList.add('drop-target'); }
  });
  tree.addEventListener('dragleave', (e) => {
    const fr = e.target.closest('.folder-row');
    if (fr) fr.classList.remove('drop-target');
  });
  tree.addEventListener('drop', (e) => {
    const fr = e.target.closest('.folder-row');
    if (fr && draggingSessionId) {
      e.preventDefault();
      fr.classList.remove('drop-target');
      const fid = fr.getAttribute('data-fid');
      moveSession(draggingSessionId, fid === '__general__' ? null : fid);
      draggingSessionId = null;
    }
  });
}

// Sidebar bellek aksiyonları (data-act delegasyonu)
(function() {
  const sidebar = document.querySelector('.sidebar');
  if (!sidebar || sidebar._memWired) return;
  sidebar._memWired = true;
  sidebar.addEventListener('click', function(e) {
    const actEl = e.target.closest('[data-act]');
    if (!actEl) return;
    const act = actEl.getAttribute('data-act');
    const memId = actEl.getAttribute('data-mem-id');
    if (act === 'add-memory') addMemory();
    else if (act === 'del-memory') deleteMemory(memId);
    else if (act === 'new-skill') { skillEditorOpen = true; loadSkillsPane(); }
    else if (act === 'save-new-skill') saveNewSkillFromEditor();
    else if (act === 'confirm-skill-save') confirmSaveSkill();
    else if (act === 'cancel-skill-save') closeSkillConfirm();
    else if (act === 'save-gw-config') saveGwConfig();
    else if (act === 'add-deadline') addDeadline();
    else if (act === 'filter-dl') { renderDeadlineList(actEl.getAttribute('data-filter')); actEl.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active')); actEl.classList.add('active'); }
    else if (act === 'complete-dl') completeDeadline(actEl.getAttribute('data-id'));
    else if (act === 'delete-dl') deleteDeadline(actEl.getAttribute('data-id'));
    else if (act === 'toggle-dl-section') { const dlList = document.getElementById('deadline-list'); if (dlList) dlList.style.display = dlList.style.display === 'none' ? '' : 'none'; }
    else if (act === 'add-dava') addDavaKarti();
    else if (act === 'filter-dk') renderDavaKartList(actEl.getAttribute('data-filter'));
    else if (act === 'delete-dk') deleteDavaKarti(actEl.getAttribute('data-id'));
    else if (act === 'update-dk-durum') updateDavaDurum(actEl.getAttribute('data-id'), actEl.getAttribute('data-durum'));
    else if (act === 'toggle-dk-section') { const dkList = document.getElementById('dava-list'); if (dkList) dkList.style.display = dkList.style.display === 'none' ? '' : 'none'; }
    else if (act === 'create-backup') createBackup();
    else if (act === 'restore-backup') restoreBackup(actEl.getAttribute('data-file'));
    else if (act === 'download-backup') downloadBackup(actEl.getAttribute('data-file'));
    else if (act === 'delete-backup') deleteBackup(actEl.getAttribute('data-file'));
    else if (act === 'toggle-backup-section') { const bkList = document.getElementById('backup-list'); if (bkList) bkList.style.display = bkList.style.display === 'none' ? '' : 'none'; }
  });
})();

async function selectChat(id) {
  activeChatId = id;
  const chat = getActiveChat();
  // Mesajlar tembel yüklü değilse sunucudan getir
  if (chat && chat.messages === null && serverOk) {
    try {
      const full = await (await fetch('/api/workspace/session?id=' + encodeURIComponent(id))).json();
      if (full && !full.error) { chat.messages = full.messages || []; chat.attachments = full.attachments || []; chat.created = full.created; }
      else chat.messages = [];
    } catch(e) { chat.messages = []; }
  }
  saveChats();
  renderTree();
  renderChat();
}

function deleteChat(id) {
  chats = chats.filter(c => c.id !== id);
  if (activeChatId === id) activeChatId = null;
  if (serverOk) fetch('/api/workspace/session/delete', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,action:'delete'})}).catch(()=>{});
  saveChats();
  renderTree();
  renderChat();
}

function renderChat() {
  const area = document.getElementById('chat-area');
  const welcome = document.getElementById('welcome-screen');
  const chat = getActiveChat();
  renderAttachments();
  updateTokenChip();

  if (!chat || !chat.messages || chat.messages.length === 0) {
    welcome.style.display = 'flex';
    area.querySelectorAll('.msg').forEach(el => el.remove());
    return;
  }

  welcome.style.display = 'none';
  area.querySelectorAll('.msg').forEach(el => el.remove());

  chat.messages.forEach((m, idx) => {
    const div = document.createElement('div');
    div.className = 'msg ' + m.role;
    div.setAttribute('data-msg-idx', idx);
    if (m.role === 'assistant') {
      // Taslak JSON tespiti — yapılandırılmış belge görünümü
      var draftData = null;
      try {
        var jsonMatch = m.text.match(/\{[\s\S]*?"type"\s*:\s*"(dava_dilekcesi|temyiz_dilekcesi|sozlesme|ihtarname|resmi_yazi)"[\s\S]*?\}/);
        if (jsonMatch) draftData = JSON.parse(jsonMatch[0]);
      } catch(e2) { draftData = null; }
      var contentHtml = (draftData && draftData.sections && draftData.sections.length > 0) ? renderDraftContent(draftData) : renderMarkdown(m.text);
      var docxBtn = (draftData) ? '<div class="copy-menu-item" data-copy-act="docx">' + ic('download') + ' DOCX olarak indir</div>' : '';
      div.innerHTML = '<div class="msg-bubble"><div class="msg-content">' + contentHtml + '</div>' +
        (m.sources ? renderSources(m.sources) : '') + renderMsgMeta(m) +
        '<div class="msg-actions">' +
        '<button data-copy-act="plain" title="Duz metin olarak kopyala">' + ic('copy') + '</button>' +
        '<button data-copy-act="toggle-menu" title="Kopyalama secenekleri" class="copy-chevron-btn">' + ic('chevron') + '</button>' +
        '<div class="copy-menu">' +
        '<div class="copy-menu-item" data-copy-act="plain">' + ic('copy') + ' Duz metin</div>' +
        '<div class="copy-menu-item" data-copy-act="markdown">' + ic('clipboard') + ' Markdown</div>' +
        '<div class="copy-menu-sep"></div>' +
        '<div class="copy-menu-item" data-copy-act="word">' + ic('download') + ' Word olarak indir</div>' +
        docxBtn +
        '</div></div></div>';
    } else {
      div.innerHTML = '<div class="msg-bubble">' + escapeHtml(m.text) + (m.sources ? renderSources(m.sources) : '') + '</div>';
    }
    area.appendChild(div);
  });
  area.scrollTop = area.scrollHeight;
  detectSkillBlocks();
}

// ----- Ekli belgeler (chips) -----
function renderAttachments() {
  const box = document.getElementById('attachments');
  if (!box) return;
  const chat = getActiveChat();
  const atts = (chat && chat.attachments) || [];
  if (!atts.length) { box.innerHTML = ''; return; }
  box.innerHTML = atts.map((a, i) =>
    '<div class="att-chip">' +
      '<span class="ai"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg></span>' +
      '<span class="aname">' + escapeHtml(a.name) + '</span>' +
      (a.refCount ? '<span class="aref">' + a.refCount + ' ref</span>' : '') +
      '<button class="emsal" title="Bu belge için emsal kararları ara" onclick="searchEmsal(' + i + ')">' + ic('scale') + ' Emsal</button>' +
      '<span class="ax" title="Kaldır" onclick="removeAttachment(' + i + ')">' + ic('x') + '</span>' +
    '</div>'
  ).join('');
}

function removeAttachment(i) {
  const chat = getActiveChat(); if (!chat || !chat.attachments) return;
  chat.attachments.splice(i, 1);
  persistSession(chat, true);
  renderChat();
}

function searchEmsal(i) {
  const chat = getActiveChat(); if (!chat || !chat.attachments || !chat.attachments[i]) return;
  const a = chat.attachments[i];
  const q = 'Bu belgedeki uyuşmazlık için emsal kararları ve içtihatları detaylıca getir: ' + (a.name || 'belge');
  document.getElementById('chat-input').value = q;
  sendMessage();
}

function buildDocumentContext() {
  const chat = getActiveChat();
  if (!chat || !chat.attachments || !chat.attachments.length) return '';
  return chat.attachments.map(a =>
    '### ' + a.name + (a.refs && a.refs.length ? ' (Referanslar: ' + a.refs.map(r=>r.value).join(', ') + ')' : '') + '\n' + (a.text || '')
  ).join('\n\n').substring(0, 14000);
}

function renderSources(sources) {
  if (!sources || sources.length === 0) return '';
  const tags = sources.map(s => {
    const safe = escapeHtml(s);
    return '<span class="source-tag" data-source="' + safe.replace(/"/g, '&quot;') + '">' + safe +
      '<button data-copy-act="copy-source" title="Kaynagi kopyala" class="src-copy">' + ic('copy') + '</button></span>';
  }).join('');
  return '<div class="sources">' + tags + '<button data-copy-act="copy-all-sources" class="sources-copy-all">Tumunu kopyala</button></div>';
}

function renderMsgMeta(m) {
  let html = '';
  if (m.skillsUsed && m.skillsUsed.length) {
    html += '<div class="skill-tags">' + m.skillsUsed.map(s => '<span class="skill-tag">⚡ ' + escapeHtml(s) + '</span>').join('') + '</div>';
  }
  const bits = [];
  if (m.usedModel) bits.push(escapeHtml(m.usedModel));
  if (m.fellBack) bits.push('🔁 yedek modele geçildi');
  if (m.usage && m.usage.total) {
    let t = '🔢 ' + fmtNum(m.usage.total) + ' token';
    if (m.usage.prompt || m.usage.completion) t += ' (' + fmtNum(m.usage.prompt||0) + '→' + fmtNum(m.usage.completion||0) + ')';
    bits.push(t);
  }
  if (m.context && m.context.window) {
    const pct = Math.round((m.context.ratio || 0) * 100);
    bits.push('📊 bağlam ~%' + pct + ' (' + fmtNum(m.context.window) + ')');
  }
  if (bits.length) html += '<div class="msg-foot">' + bits.join(' · ') + '</div>';
  return html;
}

function fmtNum(n) { return (n||0).toLocaleString('tr-TR'); }

function updateTokenChip() {
  const el = document.getElementById('token-chip');
  if (!el) return;
  const chat = getActiveChat();
  const t = (chat && chat.tokenTotal) || 0;
  if (t > 0) {
    el.style.display = '';
    const over = tokenBudget > 0 && t >= tokenBudget;
    el.textContent = '🔢 ' + fmtNum(t) + ' token' + (tokenBudget > 0 ? (' / ' + fmtNum(tokenBudget)) : '');
    el.classList.toggle('warn', over);
    if (over && !budgetWarned) { budgetWarned = true; toast('⚠️ Token bütçesi aşıldı (' + fmtNum(t) + ')', true); }
  } else { el.style.display = 'none'; el.classList.remove('warn'); }
}

function escapeHtml(text) {
  return String(text == null ? '' : text).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ===== Markdown Render =====
// NOT: Bu fonksiyon Python üçlü-tırnak string'i içinde olduğundan
// tarayıcıya ulaşması gereken HER ters bölü ÇİFT yazılır (\n, \d, \* ...).
function renderMarkdown(text) {
  if (!text) return '';
  // 0. Close unclosed fenced code blocks (streaming safety)
  var openFences = (text.match(/```/g) || []).length;
  if (openFences % 2 !== 0) text += '\n```';
  // 1. Extract fenced code blocks before any processing
  const codeBlocks = [];
  let processed = text.replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
    const idx = codeBlocks.length;
    codeBlocks.push({lang: lang || '', code: code});
    return '%%CB_' + idx + '%%';
  });
  // 2. Escape HTML
  let html = escapeHtml(processed);
  // 3. Standard markdown rules
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  html = html.replace(/^### (.*?)(?:\n|$)/gm, '<h4>$1</h4>');
  html = html.replace(/^## (.*?)(?:\n|$)/gm, '<h3>$1</h3>');
  html = html.replace(/^# (.*?)(?:\n|$)/gm, '<h2>$1</h2>');
  // Tablolar
  html = html.replace(/\n\|(.+)\|\n\|[-| :]+\|\n((?:\|.+\|\n?)+)/g, function(match, header, body) {
    const ths = header.split('|').map(s=>s.trim()).filter(Boolean).map(s=>'<th>'+s+'</th>').join('');
    const rows = body.trim().split('\n').map(row=>{
      const tds = row.split('|').map(s=>s.trim()).filter(Boolean).map(s=>'<td>'+s+'</td>').join('');
      return '<tr>'+tds+'</tr>';
    }).join('');
    return '<table class="md-table"><thead><tr>'+ths+'</tr></thead><tbody>'+rows+'</tbody></table>';
  });
  html = html.replace(/^[-*] (.*?)(?:\n|$)/gm, '<li>$1</li>');
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');
  html = html.replace(/^\d+\. (.*?)(?:\n|$)/gm, '<li>$1</li>');
  html = html.replace(/^---$/gm, '<hr>');
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\n/g, '<br>');
  html = html.replace(/(<\/h[234]>)<br>/g, '$1');
  html = html.replace(/(<\/table>)<br>/g, '$1');
  html = html.replace(/(<\/ul>)<br>/g, '$1');
  html = html.replace(/(<hr>)<br>/g, '$1');
  // 4. Restore fenced code blocks as rendered HTML
  html = html.replace(/%%CB_(\d+)%%/g, function(match, idxStr) {
    const idx = parseInt(idxStr, 10);
    if (idx >= codeBlocks.length) return match;
    const block = codeBlocks[idx];
    const langLabel = block.lang ? '<span class="code-lang">' + escapeHtml(block.lang) + '</span>' : '';
    const copyBtn = '<button data-copy-act="copy-code" class="code-copy" title="Kopyala">' + ic('copy') + ' Kopyala</button>';
    return '<div class="code-block"><div class="code-header">' + langLabel + copyBtn + '</div><pre>' + escapeHtml(block.code) + '</pre></div>';
  });
  return html;
}

// ===== Multi-format Copy & Export =====
function getMsgData(el) {
  const msgEl = el.closest('.msg');
  if (!msgEl) return null;
  const idx = parseInt(msgEl.getAttribute('data-msg-idx'), 10);
  const chat = getActiveChat();
  if (!chat || !chat.messages || isNaN(idx) || idx < 0 || idx >= chat.messages.length) return null;
  return chat.messages[idx];
}

function flashBtn(btn, icon) {
  btn.innerHTML = ic('check');
  setTimeout(function() { btn.innerHTML = ic(icon); }, 1500);
}

function copyAsPlainText(btn) {
  const bubble = btn.closest('.msg-bubble');
  const content = bubble.querySelector('.msg-content');
  const text = content ? content.innerText : bubble.innerText;
  navigator.clipboard.writeText(text).then(function() { flashBtn(btn, 'copy'); });
}

function copyAsMarkdown(btn) {
  const msg = getMsgData(btn);
  if (!msg) return;
  const md = msg.text || '';
  navigator.clipboard.writeText(md).then(function() { flashBtn(btn, 'clipboard'); });
}

function exportWord(btn) {
  const bubble = btn.closest('.msg-bubble');
  const content = bubble.querySelector('.msg-content');
  const htmlContent = content ? content.innerHTML : bubble.innerHTML;
  const chat = getActiveChat();
  const title = chat ? chat.title : 'TurkiyeMCP';
  const fullHtml = '<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8"><title>' + escapeHtml(title) + '</title><style>body{font-family:"Segoe UI",Tahoma,sans-serif;font-size:11pt;color:#1a1a2e}table{border-collapse:collapse;width:100%;margin:8pt 0}th,td{border:1px solid #ccc;padding:4pt 8pt;font-size:10pt}th{background:#6366f1;color:#fff}h2{color:#6366f1}h3{color:#818cf8}h4{color:#a5b4fc}code{background:#f1f5f9;padding:1pt 3pt;border-radius:3pt;font-size:10pt}strong{color:#6366f1}em{color:#8b5cf6}pre{background:#f1f5f9;padding:8pt;border-radius:4pt;font-family:Consolas,monospace;font-size:9pt}</style></head><body>' + htmlContent + '</body></html>';
  const blob = new Blob(['﻿', fullHtml], {type: 'application/msword'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = title.replace(/[^a-zA-Z0-9À-ÿ]/g, '_') + '.doc';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  flashBtn(btn, 'download');
}

// ===== Taslak Belge Görünümü ve DOCX İndirme =====

function renderDraftContent(data) {
  // Yapılandırılmış belge taslağını HTML olarak render et
  var html = '<div class="draft-document">';
  html += '<div class="draft-header">' + escapeHtml(data.title || 'Belge Tasla' + String.fromCharCode(287) + 'ı') + '</div>';

  // Taraflar tablosu
  if (data.metadata && data.metadata.parties && data.metadata.parties.length > 0) {
    html += '<table class="draft-parties"><thead><tr><th>S' + String.fromCharCode(305) + 'fat</th><th>Ad Soyad / Unvan</th></tr></thead><tbody>';
    data.metadata.parties.forEach(function(p) {
      html += '<tr><td>' + escapeHtml(p.role || '') + '</td><td>' + escapeHtml(p.name || '') + '</td></tr>';
    });
    html += '</tbody></table>';
  }

  // Konu
  if (data.metadata && data.metadata.subject) {
    html += '<div class="draft-subject"><strong>Konu:</strong> ' + escapeHtml(data.metadata.subject) + '</div>';
  }

  // Yasal referanslar
  if (data.metadata && data.metadata.legal_refs && data.metadata.legal_refs.length > 0) {
    html += '<div class="draft-refs"><strong>Yasal Dayanaklar:</strong> ' + data.metadata.legal_refs.map(function(r) { return escapeHtml(r); }).join(', ') + '</div>';
  }

  // Bölümler
  if (data.sections) {
    data.sections.forEach(function(s) {
      html += '<div class="draft-section">';
      if (s.heading) html += '<div class="draft-section-heading">' + escapeHtml(s.heading) + '</div>';
      if (s.body) html += '<div class="draft-section-body">' + renderMarkdown(s.body) + '</div>';
      html += '</div>';
    });
  }

  // Tarih
  if (data.metadata && data.metadata.date) {
    html += '<div class="draft-date">' + escapeHtml(data.metadata.date) + '</div>';
  }

  html += '</div>';
  return html;
}

function exportDraftAsDocx(btn) {
  // Asistan mesajından JSON taslağını çıkar ve DOCX olarak indir
  var msgEl = btn.closest('.msg');
  if (!msgEl) return;
  var idx = parseInt(msgEl.getAttribute('data-msg-idx'), 10);
  var chat = getActiveChat();
  if (!chat || !chat.messages || isNaN(idx) || idx < 0 || idx >= chat.messages.length) return;
  var m = chat.messages[idx];
  var draftData = null;
  try {
    var jsonMatch = m.text.match(/\{[\s\S]*?"type"\s*:\s*"(dava_dilekcesi|temyiz_dilekcesi|sozlesme|ihtarname|resmi_yazi)"[\s\S]*?\}/);
    if (jsonMatch) draftData = JSON.parse(jsonMatch[0]);
  } catch(e2) { toast('Taslak verisi okunamad' + String.fromCharCode(305), true); return; }
  if (!draftData) { toast('Taslak JSON bulunamad' + String.fromCharCode(305), true); return; }

  fetch('/api/export/docx', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      title: draftData.title || 'Belge',
      sections: draftData.sections || [],
      metadata: draftData.metadata || {},
      doc_type: draftData.type || ''
    })
  }).then(function(res) {
    if (!res.ok) return res.json().then(function(e) { throw new Error(e.error || 'DOCX olu' + String.fromCharCode(351) + 'turma hatas' + String.fromCharCode(305)); });
    return res.blob();
  }).then(function(blob) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    var safeTitle = (draftData.title || 'Belge').replace(/[^a-zA-Z0-9À-ÿ]/g, '_').substring(0, 50);
    a.download = safeTitle + '.docx';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    flashBtn(btn, 'download');
  }).catch(function(e) {
    toast('DOCX hatas' + String.fromCharCode(305) + ': ' + e.message, true);
  });
}

function toggleCopyMenu(btn) {
  const actions = btn.closest('.msg-actions');
  const menu = actions.querySelector('.copy-menu');
  document.querySelectorAll('.copy-menu.open').forEach(function(m) {
    if (m !== menu) m.classList.remove('open');
  });
  menu.classList.toggle('open');
}

function copyCodeBlock(btn) {
  const block = btn.closest('.code-block');
  const code = block.querySelector('pre');
  if (!code) return;
  navigator.clipboard.writeText(code.textContent).then(function() {
    btn.innerHTML = ic('check') + ' Kopyala';
    setTimeout(function() { btn.innerHTML = ic('copy') + ' Kopyala'; }, 1500);
  });
}

function copySource(btn) {
  const text = btn.getAttribute('data-source') || '';
  navigator.clipboard.writeText(text).then(function() {
    btn.innerHTML = ic('check');
    setTimeout(function() { btn.innerHTML = ic('copy'); }, 1500);
  });
}

function copyAllSources(btn) {
  const sourcesEl = btn.closest('.sources');
  if (!sourcesEl) return;
  const tags = sourcesEl.querySelectorAll('.source-tag');
  const texts = Array.from(tags).map(function(t) { return t.getAttribute('data-source') || t.textContent.trim(); });
  navigator.clipboard.writeText(texts.join('\n')).then(function() {
    btn.textContent = 'Kopyalandi';
    setTimeout(function() { btn.textContent = 'Tumunu kopyala'; }, 1500);
  });
}

// Close copy menus when clicking outside
document.addEventListener('click', function(e) {
  if (!e.target.closest('.msg-actions')) {
    document.querySelectorAll('.copy-menu.open').forEach(function(m) { m.classList.remove('open'); });
  }
});

// Delegated click handler for copy actions
document.getElementById('chat-area').addEventListener('click', function(e) {
  const actEl = e.target.closest('[data-copy-act]');
  if (!actEl) return;
  e.stopPropagation();
  const act = actEl.getAttribute('data-copy-act');
  if (act === 'plain') copyAsPlainText(actEl);
  else if (act === 'markdown') copyAsMarkdown(actEl);
  else if (act === 'word') exportWord(actEl);
  else if (act === 'docx') exportDraftAsDocx(actEl);
  else if (act === 'toggle-menu') toggleCopyMenu(actEl);
  else if (act === 'copy-code') copyCodeBlock(actEl);
  else if (act === 'copy-source') copySource(actEl);
  else if (act === 'copy-all-sources') copyAllSources(actEl);
  else if (act === 'save-skill') saveSkillFromBlock(actEl);
});

// ===== Send Message =====
function fill(msg) { document.getElementById('chat-input').value = msg; document.getElementById('chat-input').focus(); autoResize(document.getElementById('chat-input')); }
function autoResize(el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 140) + 'px'; }

// ===== Paste Handler =====
(function() {
  var chatInput = document.getElementById('chat-input');
  if (!chatInput) return;
  chatInput.addEventListener('paste', function(e) {
    var html = e.clipboardData.getData('text/html');
    if (html) {
      e.preventDefault();
      var text = e.clipboardData.getData('text/plain') || '';
      var start = chatInput.selectionStart;
      var end = chatInput.selectionEnd;
      var before = chatInput.value.substring(0, start);
      var after = chatInput.value.substring(end);
      chatInput.value = before + text + after;
      chatInput.selectionStart = chatInput.selectionEnd = start + text.length;
      autoResize(chatInput);
    }
    setTimeout(function() { autoResize(chatInput); }, 0);
  });
})();

let currentAbort = null;
const SEND_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>';
const STOP_ICON = '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>';

function setSendMode(sending) {
  const btn = document.getElementById('send-btn');
  if (!btn) return;
  if (sending) {
    btn.innerHTML = STOP_ICON; btn.classList.add('stopping');
    btn.title = 'Durdur'; btn.onclick = stopGeneration;
  } else {
    btn.innerHTML = SEND_ICON; btn.classList.remove('stopping');
    btn.title = 'Gönder'; btn.onclick = sendMessage;
  }
}

function stopGeneration() {
  if (currentAbort) { try { currentAbort.abort(); } catch(e) {} }
}

async function sendMessage() {
  var input = document.getElementById('chat-input');
  var msg = input.value.trim();
  if (!msg || isSending) return;
  input.value = '';
  autoResize(input);

  if (!activeChatId) newChat();
  var chat = getActiveChat();
  if (!chat) { newChat(); chat = getActiveChat(); }
  if (!Array.isArray(chat.messages)) chat.messages = [];

  var history = chat.messages
    .filter(function(m) { return m.role === 'user' || m.role === 'assistant'; })
    .slice(-12)
    .map(function(m) { return { role: m.role, text: m.text }; });

  if (chat.messages.length === 0) {
    chat.title = generateTitle(msg);
    renderTree();
  }

  chat.messages.push({ role: 'user', text: msg });
  chat.updated = Date.now();
  renderChat();
  persistSession(chat, true);

  isSending = true;
  setSendMode(true);

  // Streaming assistant message placeholder
  var assistantMsg = {
    role: 'assistant', text: '', sources: [], skillsUsed: [],
    usedModel: '', fellBack: false, usage: null, context: null
  };
  chat.messages.push(assistantMsg);
  var msgIdx = chat.messages.length - 1;

  // Show streaming bubble with typing indicator
  var welcome = document.getElementById('welcome-screen');
  if (welcome) welcome.style.display = 'none';
  var streamDiv = document.createElement('div');
  streamDiv.className = 'msg assistant';
  streamDiv.setAttribute('data-msg-idx', String(msgIdx));
  var streamBubble = document.createElement('div');
  streamBubble.className = 'msg-bubble';
  var streamContent = document.createElement('div');
  streamContent.className = 'msg-content';
  streamContent.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
  streamBubble.appendChild(streamContent);
  streamDiv.appendChild(streamBubble);
  var area = document.getElementById('chat-area');
  // Remove typing-indicator if it exists from old flow
  var oldTi = document.getElementById('typing-indicator');
  if (oldTi) oldTi.remove();
  area.appendChild(streamDiv);
  area.scrollTop = area.scrollHeight;

  currentAbort = new AbortController();
  var streamingText = '';
  var streamingReasoning = '';

  try {
    var provider = document.getElementById('llm-provider') ? document.getElementById('llm-provider').value : currentProvider;
    var model = (document.getElementById('llm-model') && document.getElementById('llm-model').value) || currentModel;
    var apiKey = keyFor(provider);
    var documentContext = buildDocumentContext();
    var atts = chat.attachments || [];
    var docType = atts.length ? (atts[atts.length - 1].docType || '') : '';
    var related = [];
    atts.forEach(function(a) { if (a.related && a.related.length) related = related.concat(a.related); });

    var fetchHeaders = {'Content-Type': 'application/json'};
    fetchHeaders['X-LLM-Provider'] = provider;
    fetchHeaders['X-LLM-Model'] = model;
    if (apiKey && PROVIDERS[provider].needs_key) fetchHeaders['X-API-Key'] = apiKey;

    var res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: fetchHeaders,
      signal: currentAbort.signal,
      body: JSON.stringify({
        message: msg, provider: provider, api_key: apiKey, model: model,
        history: history, document_context: documentContext, doc_type: docType,
        related: related, fallbacks: getFallbacks(), api_keys: apiKeys,
        timeout_override: gwTimeout || 0
      })
    });

    if (!res.ok) {
      // Non-SSE error response (e.g. 500)
      var errText = '';
      try { errText = await res.text(); } catch(e2) {}
      assistantMsg.text = '';
      streamContent.innerHTML = '<span style="color:var(--accent)">Hata: ' + escapeHtml(errText || res.statusText) + '</span>';
    } else {
      var reader = res.body.getReader();
      var decoder = new TextDecoder();
      var sseBuffer = '';
      var curEvent = '';
      var curData = '';

      while (true) {
        var result = await reader.read();
        if (result.done) break;
        sseBuffer += decoder.decode(result.value, {stream: true});

        // Parse SSE events from buffer
        var lines = sseBuffer.split('\n');
        sseBuffer = lines.pop(); // Keep incomplete line in buffer

        for (var i = 0; i < lines.length; i++) {
          var line = lines[i];
          if (line.indexOf('event: ') === 0) {
            curEvent = line.substring(7).trim();
          } else if (line.indexOf('data: ') === 0) {
            curData = line.substring(6);
          } else if (line === '' && curEvent && curData) {
            // End of SSE event — process it
            try {
              var payload = JSON.parse(curData);
              if (curEvent === 'token') {
                streamingText += (payload.content || '');
                streamingReasoning += (payload.reasoning || '');
                var display = streamingReasoning
                  ? '> ' + streamingReasoning + '\n\n' + streamingText
                  : streamingText;
                streamContent.innerHTML = renderMarkdown(display);
                area.scrollTop = area.scrollHeight;
              } else if (curEvent === 'meta') {
                assistantMsg.usedModel = (payload.provider || '') + ' \u00b7 ' + (payload.model || '');
              } else if (curEvent === 'done') {
                assistantMsg.sources = payload.sources || [];
                assistantMsg.skillsUsed = payload.skills_used || [];
                assistantMsg.attempts = payload.attempts || [];
                assistantMsg.usage = payload.usage || null;
                assistantMsg.context = payload.context || null;
                assistantMsg.fellBack = (payload.attempts || []).filter(function(a) { return a.status !== 'ok'; }).length > 0;
                if (payload.usage && payload.usage.total) {
                  chat.tokenTotal = (chat.tokenTotal || 0) + payload.usage.total;
                  updateTokenChip();
                }
                assistantMsg.text = streamingText;
                if (autoMemory) learnFromConversation(msg, streamingText, provider, model, apiKey);
              } else if (curEvent === 'error') {
                assistantMsg.text = '';
                streamingText = '';
                var errMsg = payload.message || 'Ba\u011flant\u0131 hatas\u0131';
                streamContent.innerHTML = '<span style="color:var(--accent)">Hata: ' + escapeHtml(errMsg) + '</span>';
                if (payload.needs_key) toast('API anahtar\u0131 gerekli \u2014 Ayarlar', true);
              }
            } catch(e2) { /* ignore parse errors for partial data */ }
            curEvent = '';
            curData = '';
          }
        }
      }
      // Process any remaining buffered data
      if (sseBuffer) {
        var remaining = sseBuffer.split('\n');
        for (var j = 0; j < remaining.length; j++) {
          var rline = remaining[j];
          if (rline.indexOf('event: ') === 0) curEvent = rline.substring(7).trim();
          else if (rline.indexOf('data: ') === 0) curData = rline.substring(6);
          if (curEvent && curData) {
            try {
              var rpay = JSON.parse(curData);
              if (rpay.content || rpay.reasoning) {
                streamingText += (rpay.content || '');
                streamingReasoning += (rpay.reasoning || '');
              }
            } catch(e3) {}
            curEvent = '';
            curData = '';
          }
        }
      }
      assistantMsg.text = streamingText || assistantMsg.text;
    }
  } catch(e) {
    if (e && e.name === 'AbortError') {
      assistantMsg.text = streamingText || '';
      if (!assistantMsg.text) {
        // Remove empty assistant message
        chat.messages.splice(chat.messages.indexOf(assistantMsg), 1);
        chat.messages.push({ role: 'system', text: '\u23f9 Yan\u0131t durduruldu.' });
      }
      toast('Yan\u0131t durduruldu');
    } else {
      chat.messages.splice(chat.messages.indexOf(assistantMsg), 1);
      chat.messages.push({ role: 'system', text: 'Ba\u011flant\u0131 hatas\u0131.' });
    }
  }

  currentAbort = null;
  isSending = false;
  setSendMode(false);
  chat.updated = Date.now();
  renderChat();
  persistSession(chat, true);
}

// ===== File Upload =====
async function handleFileUpload(input) {
  const file = input.files[0];
  input.value = '';
  if (!file) return;

  if (!activeChatId) newChat();
  let chat = getActiveChat();
  if (!chat) { newChat(); chat = getActiveChat(); }
  if (!Array.isArray(chat.messages)) chat.messages = [];
  if (!Array.isArray(chat.attachments)) chat.attachments = [];

  toast('📄 ' + file.name + ' yükleniyor…');
  const formData = new FormData();
  formData.append('file', file);
  formData.append('folderId', chat.folderId || '_root');

  // serverOk ise workspace'e (kalıcı), değilse eski uçlara düş
  const isPDF = file.name.toLowerCase().endsWith('.pdf');
  const endpoint = serverOk ? '/api/workspace/file' : (isPDF ? '/api/upload/pdf' : '/api/upload/uyap');

  try {
    const data = await (await fetch(endpoint, { method: 'POST', body: formData })).json();
    if (data.error) {
      chat.messages.push({ role: 'system', text: 'Dosya hatası: ' + data.error });
      toast('Dosya hatası: ' + data.error, true);
    } else {
      const text = (data.text || data.markdown || '');
      const refs = data.references || [];
      const u = data.understanding || {};
      const related = data.related || [];
      // Eki sohbete iliştir (bağlam + belge zekâsı)
      chat.attachments.push({
        name: file.name, text: text, refs: refs, refCount: refs.length,
        docType: u.type || '', typeLabel: u.type_label || '', subject: u.subject || '',
        parties: u.parties || [], related: related,
        fileId: (data.file && data.file.id) || null
      });
      let info = '📄 Belge eklendi: ' + file.name;
      if (u.type_label) info += '\n📑 Tür: ' + u.type_label + (u.subject ? ' — ' + u.subject : '');
      if (refs.length) info += '\n🔖 Referanslar: ' + refs.map(r => r.value).join(', ');
      if (related.length) info += '\n🔎 Çalışma alanınızda benzer kayıt: ' + related.map(r => r.title + ' (' + r.folder + ')').join('; ');
      info += '\n\nBu belge hakkında soru sorabilir, "⚖ Emsal" ile emsal kararları aratabilirsiniz.';
      chat.messages.push({ role: 'system', text: info });
      if (chat.title === 'Yeni Sohbet' || !chat.messages.filter(m=>m.role==='user').length) { chat.title = file.name.substring(0, 40); }
      if (data.parse_error) toast('Not: ' + data.parse_error, true);
      else toast('✓ ' + (u.type_label || 'Belge') + ' eklendi');
    }
    chat.updated = Date.now();
    renderTree();
    renderChat();
    persistSession(chat, true);
  } catch(e) {
    chat.messages.push({ role: 'system', text: 'Dosya yükleme hatası.' });
    toast('Dosya yükleme hatası', true);
    renderChat();
  }
}

// Drag & drop
const mainArea = document.querySelector('.main');
mainArea.addEventListener('dragover', e => { e.preventDefault(); document.getElementById('file-drop-overlay').classList.add('active'); });
mainArea.addEventListener('dragleave', e => { e.preventDefault(); document.getElementById('file-drop-overlay').classList.remove('active'); });
mainArea.addEventListener('drop', e => {
  e.preventDefault();
  document.getElementById('file-drop-overlay').classList.remove('active');
  if (e.dataTransfer.files.length) {
    document.getElementById('file-input').files = e.dataTransfer.files;
    handleFileUpload(document.getElementById('file-input'));
  }
});

// ===== Settings =====
function openSettings() { document.getElementById('overlay').classList.add('open'); loadConfig(); }
function closeSettings() { document.getElementById('overlay').classList.remove('open'); document.getElementById('test-status').textContent=''; }
function switchSettingsTab(t){
  document.getElementById('stab-conn').classList.toggle('active', t==='conn');
  document.getElementById('stab-pref').classList.toggle('active', t==='pref');
  document.getElementById('set-conn').style.display = t==='conn' ? '' : 'none';
  document.getElementById('set-pref').style.display = t==='pref' ? '' : 'none';
}

function loadConfig() {
  const prov = document.getElementById('llm-provider');
  prov.value = currentProvider;
  onProviderChange();
  if (currentModel) document.getElementById('llm-model').value = currentModel;
  updateModelChip();
  // Tercihler
  document.getElementById('ui-theme').value = currentTheme;
  document.getElementById('token-budget').value = tokenBudget || '';
  document.getElementById('gw-timeout').value = gwTimeout || '';
  document.getElementById('auto-memory').value = autoMemory ? '1' : '0';
  fetch('/api/workspace').then(r=>r.json()).then(d=>{
    const el = document.getElementById('data-dir'); if (el) el.value = d.dataDir || '—';
  }).catch(()=>{});
}

async function loadOllamaModels(selected) {
  const modelSel = document.getElementById('llm-model');
  try {
    const data = await (await fetch('/api/ollama/models')).json();
    if (data.ok && data.models && data.models.length) {
      modelSel.innerHTML = data.models.map(m => '<option value="' + m + '">' + m + '</option>').join('');
      modelSel.value = data.models.includes(selected) ? selected : data.models[0];
      currentModel = modelSel.value;
    }
  } catch(e) {}
}

function onProviderChange() {
  const prov = document.getElementById('llm-provider').value;
  const modelSel = document.getElementById('llm-model');
  const config = PROVIDERS[prov];
  modelSel.innerHTML = config.models.map(m => '<option value="' + m + '">' + m + '</option>').join('');
  let m = (prov === currentProvider && currentModel) ? currentModel : config.default_model;
  if (!config.models.includes(m)) m = config.default_model;
  modelSel.value = m;
  // Yerel Ollama: canlı model listesini çek (cloud proxy modelleri dahil)
  if (prov === 'ollama') loadOllamaModels(currentModel);
  // Sağlayıcı başına anahtar
  const keyInput = document.getElementById('llm-api-key');
  const field = document.getElementById('api-key-field');
  const hint = document.getElementById('api-key-hint');
  keyInput.value = keyFor(prov);
  if (config.needs_key) {
    field.style.opacity = '1'; keyInput.disabled = false;
    keyInput.placeholder = (prov === 'ollama_cloud') ? 'ollama.com API anahtarı' : 'sk-...';
    hint.textContent = (prov === 'anthropic') ? '(sk-ant-…)' : '';
  } else {
    field.style.opacity = '.5'; keyInput.disabled = true; keyInput.value = '';
    hint.textContent = '(gerekli değil — yerel)';
  }
  document.getElementById('test-status').textContent = '';
}

async function saveConfig() {
  currentProvider = document.getElementById('llm-provider').value;
  currentModel = document.getElementById('llm-model').value;
  const key = document.getElementById('llm-api-key').value.trim();
  if (PROVIDERS[currentProvider].needs_key) apiKeys[currentProvider] = key;
  localStorage.setItem('llm-provider', currentProvider);
  localStorage.setItem('llm-model', currentModel);
  localStorage.setItem('llm-keys', JSON.stringify(apiKeys));
  // Tercihler
  currentTheme = document.getElementById('ui-theme').value;
  tokenBudget = parseInt(document.getElementById('token-budget').value || '0', 10) || 0;
  gwTimeout = parseInt(document.getElementById('gw-timeout').value || '0', 10) || 0;
  autoMemory = document.getElementById('auto-memory').value === '1';
  localStorage.setItem('ui-theme', currentTheme);
  localStorage.setItem('token-budget', String(tokenBudget));
  localStorage.setItem('gw-timeout', String(gwTimeout));
  localStorage.setItem('auto-memory', autoMemory ? '1' : '0');
  applyTheme(currentTheme);
  budgetWarned = false;
  // keyring (yerel mod) — best effort
  try {
    await fetch('/api/chat/configure', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({provider: currentProvider, api_key: key, model: currentModel})
    });
  } catch(e) {}
  updateModelChip();
  closeSettings();
  toast('Ayarlar kaydedildi');
}

async function testConnection() {
  const provider = document.getElementById('llm-provider').value;
  const model = document.getElementById('llm-model').value;
  const key = document.getElementById('llm-api-key').value.trim();
  const status = document.getElementById('test-status');
  status.className = 'test-status pending';
  status.textContent = 'Test ediliyor…';
  try {
    const data = await (await fetch('/api/chat/test', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({provider, model, api_key: key})
    })).json();
    if (data.ok) { status.className = 'test-status ok'; status.textContent = '✓ ' + (data.message || 'Bağlantı başarılı'); }
    else { status.className = 'test-status err'; status.textContent = '✗ ' + (data.error || 'Başarısız'); }
  } catch(e) {
    status.className = 'test-status err'; status.textContent = '✗ Sunucuya ulaşılamadı';
  }
}

function updateModelChip() {
  const chip = document.getElementById('model-chip');
  const chipText = document.getElementById('model-chip-text');
  const prov = PROVIDERS[currentProvider];
  const hasKey = !prov.needs_key || keyFor(currentProvider);
  chip.className = 'model-chip' + (hasKey ? '' : ' warn');
  chipText.textContent = hasKey ? (prov.name + ' · ' + (currentModel || prov.default_model)) : 'API anahtarı gerekli';
}

// ===== System Panel (Gateway · Skills · Tools) =====
let skillList = [];
function openSystemPanel(){ document.getElementById('sys-overlay').classList.add('open'); switchPanelTab('gateway'); }
function closeSystemPanel(){ document.getElementById('sys-overlay').classList.remove('open'); }
function switchPanelTab(t){
  ['gateway','skills','tools','computer','cache','apikeys','deadlines','davalar'].forEach(x=>{
    const tab = document.getElementById('tab-'+x);
    const pane = document.getElementById('pane-'+x);
    if (tab) tab.classList.toggle('active', x===t);
    if (pane) pane.style.display = (x===t) ? '' : 'none';
  });
  if (t==='gateway') loadGatewayPane();
  else if (t==='skills') loadSkillsPane();
  else if (t==='tools') loadToolsPane();
  else if (t==='computer') loadComputerPane();
  else if (t==='cache') loadCachePane();
  else if (t==='apikeys') loadApiKeysPane();
  else if (t==='deadlines') loadDeadlinesPane();
  else if (t==='davalar') loadDavaKartlariPane();
}

async function loadGatewayPane(){
  const pane = document.getElementById('pane-gateway');
  // Sunucu tarafindaki config'i yukle
  let gwCfg = {providers: {}, default_chain: []};
  try {
    gwCfg = await (await fetch('/api/gateway/config')).json();
  } catch(e) {}

  // Saglayici URL/timeout duzenleme bolumu
  let provHtml = '<div class="tool-cat">Saglayici Ayarlari</div>';
  const pkeys = Object.keys(PROVIDERS);
  pkeys.forEach(k => {
    const p = PROVIDERS[k];
    const cfg = gwCfg.providers[k] || {};
    const url = cfg.url || '';
    const timeout = cfg.timeout || '';
    const dm = cfg.default_model || p.default_model || '';
    provHtml += '<div class="gw-prov-row" data-prov="'+k+'">' +
      '<div class="gw-prov-name">' + escapeHtml(p.name) + '</div>' +
      '<div class="gw-prov-fields">' +
      '<input class="gw-input gw-url" data-prov="'+k+'" value="'+escapeHtml(url||'')+'" placeholder="'+escapeHtml(url?'':('Varsayilan URL'))+'" />' +
      '<input class="gw-input gw-timeout" data-prov="'+k+'" type="number" min="10" max="600" value="'+escapeHtml(String(timeout))+'" placeholder="sn" style="width:60px" />' +
      '</div></div>';
  });
  provHtml += '<button class="btn-ghost" data-act="save-gw-config" style="margin-top:8px">' + ic('check') + ' Kaydet</button>';

  // Failover bolumu
  let fbHtml = '<div class="field"><label>Yedek Model (Failover)</label>' +
    '<div class="fallback-box"><select id="fb-provider" onchange="onFbProviderChange()"></select>' +
    '<select id="fb-model"></select></div>' +
    '<div style="display:flex;gap:8px;margin-top:8px">' +
    '<button class="btn-ghost" onclick="addFallback()">+ Yedek Ekle</button>' +
    '<button class="btn-ghost" onclick="clearFallbacks()">Temizle</button></div>' +
    '<div id="fb-list" style="margin-top:10px"></div></div>';

  pane.innerHTML = provHtml + fbHtml +
    '<div class="tool-cat">Saglayici Metrikleri</div><div id="gw-metrics">Yukleniyor...</div>';
  const fps = document.getElementById('fb-provider');
  fps.innerHTML = pkeys.map(k=>'<option value="'+k+'">'+PROVIDERS[k].name+'</option>').join('');
  onFbProviderChange();
  renderFbList();
  try {
    const data = await (await fetch('/api/gateway/status')).json();
    const p = data.providers || {};
    const keys = Object.keys(p);
    document.getElementById('gw-metrics').innerHTML = keys.length ? keys.map(k=>{
      const m = p[k];
      const tok = m.tokens ? (' · ' + fmtNum(m.tokens) + ' token') : '';
      return '<div class="gw-row"><div><b>'+escapeHtml(m.name)+'</b><div class="gw-stat">'+m.calls+' cagri · '+m.avg_latency_ms+'ms ort.'+tok+'</div></div>'+
        '<div class="gw-stat"><span class="gw-ok">✓'+m.ok+'</span> · <span class="gw-bad">✗'+(m.fail+m.empty)+'</span></div></div>';
    }).join('') : '<div class="sk-desc">Henuz cagri yapilmadi.</div>';
  } catch(e){ document.getElementById('gw-metrics').innerHTML = '<div class="sk-desc">Durum alinamadi.</div>'; }
}
async function saveGwConfig(){
  const providers = {};
  document.querySelectorAll('.gw-prov-row').forEach(row => {
    const pid = row.getAttribute('data-prov');
    const url = row.querySelector('.gw-url').value.trim();
    const timeout = parseInt(row.querySelector('.gw-timeout').value, 10) || 0;
    const entry = {};
    if (url) entry.url = url;
    if (timeout > 0) entry.timeout = timeout;
    if (Object.keys(entry).length) providers[pid] = entry;
  });
  const payload = {providers: providers, default_chain: fallbacks.slice(0, 4)};
  try {
    const res = await fetch('/api/gateway/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const data = await res.json();
    if (data.status === 'ok') {
      // JS PROVIDERS'i guncelle
      if (data.config && data.config.providers) {
        Object.keys(data.config.providers).forEach(k => {
          if (PROVIDERS[k]) {
            const c = data.config.providers[k];
            if (c.url) PROVIDERS[k]._url = c.url;
            if (c.default_model) PROVIDERS[k].default_model = c.default_model;
            if (c.models) PROVIDERS[k].models = c.models;
          }
        });
      }
      toast('Gateway ayarlari kaydedildi');
    } else {
      toast('Hata: ' + (data.error || 'Kaydedilemedi'), true);
    }
  } catch(e) { toast('Ayar kaydetme hatasi', true); }
}

function onFbProviderChange(){
  const prov = document.getElementById('fb-provider').value;
  document.getElementById('fb-model').innerHTML = PROVIDERS[prov].models.map(m=>'<option value="'+m+'">'+m+'</option>').join('');
}
function addFallback(){
  const prov = document.getElementById('fb-provider').value;
  const model = document.getElementById('fb-model').value;
  fallbacks.push({provider:prov, model:model});
  localStorage.setItem('llm-fallbacks', JSON.stringify(fallbacks));
  renderFbList(); toast('Yedek model eklendi');
}
function removeFallback(i){ fallbacks.splice(i,1); localStorage.setItem('llm-fallbacks', JSON.stringify(fallbacks)); renderFbList(); }
function clearFallbacks(){ fallbacks=[]; localStorage.setItem('llm-fallbacks','[]'); renderFbList(); }
function renderFbList(){
  const el = document.getElementById('fb-list'); if(!el) return;
  if(!fallbacks.length){ el.innerHTML='<div class="sk-desc">Yedek model yok. Birincil model hata/boş yanıt verirse sırayla denenir.</div>'; return; }
  el.innerHTML = fallbacks.map((f,i)=>{
    const nm = (PROVIDERS[f.provider] ? PROVIDERS[f.provider].name : f.provider) + ' · ' + f.model;
    return '<div class="tool-row"><span class="tdot"></span><code>'+escapeHtml(nm)+'</code><span style="margin-left:auto;cursor:pointer;color:var(--faint)" onclick="removeFallback('+i+')">×</span></div>';
  }).join('');
}

async function loadSkillsPane(){
  const pane = document.getElementById('pane-skills');
  pane.innerHTML = 'Yukleniyor...';
  try {
    const data = await (await fetch('/api/skills')).json();
    skillList = data.skills || [];
    let html = '<button class="sk-add-btn" data-act="new-skill">' + ic('plus') + ' Yeni Skill Olustur</button>';
    if (skillEditorOpen) {
      html += '<div class="sk-editor"><textarea id="skill-editor-input" placeholder="---\nname: Skill Adi\ndescription: Aciklama\ntriggers: [anahtar]\ndoc_types: [belge]\n---\nYonerge govdesi"></textarea><div class="sk-editor-actions"><button class="btn-primary" data-act="save-new-skill">Kaydet</button></div></div>';
    }
    html += skillList.map((s,i)=>
      '<div class="sk-row"><div class="sk-main"><div class="sk-name">'+escapeHtml(s.name)+'</div>'+
      '<div class="sk-desc">'+escapeHtml(s.description)+'</div></div>'+
      '<label class="sw"><input type="checkbox" '+(s.enabled?'checked':'')+' onchange="toggleSkill('+i+', this.checked)"><span class="track"><span class="knob"></span></span></label></div>'
    ).join('') || '<div class="sk-desc">Skill bulunamadi.</div>';
    pane.innerHTML = html;
  } catch(e){ pane.innerHTML='<div class="sk-desc">Skills alinamadi.</div>'; }
}
async function toggleSkill(i, enabled){
  const s = skillList[i]; if(!s) return;
  s.enabled = enabled;
  try { await fetch('/api/skills/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:s.name, enabled})}); toast(enabled?('⚡ '+s.name+' açildi'):(s.name+' kapatildi')); } catch(e){}
}

// ===== Skill Creation from Chat =====
let skillEditorOpen = false;

function detectSkillBlocks() {
  document.querySelectorAll('.code-block').forEach(function(block) {
    var lang = block.querySelector('.code-lang');
    if (lang && lang.textContent.toUpperCase() === 'SKILL.MD') {
      if (block.querySelector('.skill-save-btn')) return;
      var btn = document.createElement('button');
      btn.className = 'code-copy skill-save-btn';
      btn.innerHTML = ic('zap') + ' Skill olarak kaydet';
      btn.setAttribute('data-copy-act', 'save-skill');
      block.querySelector('.code-header').appendChild(btn);
    }
  });
}

async function saveSkillFromBlock(btn) {
  var block = btn.closest('.code-block');
  var code = block.querySelector('pre');
  if (!code) return;
  var content = code.textContent;
  var nameMatch = content.match(/^name:\s*(.+)$/m);
  var skillName = nameMatch ? nameMatch[1].trim() : '';
  if (!skillName) { toast('Skill adi bulunamadi', true); return; }
  showSkillConfirm(skillName, content);
}

function showSkillConfirm(name, content) {
  document.getElementById('skill-confirm-name').textContent = name;
  document.getElementById('skill-confirm-content').value = content;
  document.getElementById('skill-overlay').classList.add('open');
}

function closeSkillConfirm() {
  document.getElementById('skill-overlay').classList.remove('open');
}

async function confirmSaveSkill() {
  var content = document.getElementById('skill-confirm-content').value;
  var nameMatch = content.match(/^name:\s*(.+)$/m);
  var skillName = nameMatch ? nameMatch[1].trim() : '';
  if (!skillName || !content) { toast('Skill adi veya icerik eksik', true); return; }
  try {
    var res = await fetch('/api/skills/save', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:skillName, content:content})});
    var data = await res.json();
    if (data.status === 'ok') {
      toast('⚡ Yeni skill kaydedildi: ' + skillName);
      closeSkillConfirm();
    } else {
      toast('Hata: ' + (data.error || 'Kaydedilemedi'), true);
    }
  } catch(e) { toast('Kaydetme hatasi', true); }
}

async function saveNewSkillFromEditor() {
  var content = document.getElementById('skill-editor-input').value;
  var nameMatch = content.match(/^name:\s*(.+)$/m);
  var skillName = nameMatch ? nameMatch[1].trim() : '';
  if (!skillName || !content.trim()) { toast('Skill adi veya icerik eksik', true); return; }
  try {
    var res = await fetch('/api/skills/save', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:skillName, content:content})});
    var data = await res.json();
    if (data.status === 'ok') {
      toast('⚡ Yeni skill kaydedildi: ' + skillName);
      document.getElementById('skill-editor-input').value = '';
      skillEditorOpen = false;
      loadSkillsPane();
    } else {
      toast('Hata: ' + (data.error || 'Kaydedilemedi'), true);
    }
  } catch(e) { toast('Kaydetme hatasi', true); }
}

async function loadToolsPane(){
  const pane = document.getElementById('pane-tools');
  pane.innerHTML = 'Yükleniyor…';
  try {
    const data = await (await fetch('/api/tools')).json();
    const byCat = {};
    (data.tools||[]).forEach(t=>{ (byCat[t.category]=byCat[t.category]||[]).push(t); });
    let html = '<div class="sk-desc">'+data.available+' / '+data.total+' araç aktif</div>';
    Object.keys(byCat).forEach(cat=>{
      html += '<div class="tool-cat">'+escapeHtml(cat)+'</div>';
      html += byCat[cat].map(t=>'<div class="tool-row"><span class="tdot'+(t.available?'':' off')+'"></span><code>'+escapeHtml(t.name)+'</code><span class="tdesc">'+escapeHtml(t.description)+'</span></div>').join('');
    });
    pane.innerHTML = html;
  } catch(e){ pane.innerHTML='<div class="sk-desc">Araçlar alınamadı.</div>'; }
}

// ===== Modules =====
async function loadComputerPane(){
  const pane = document.getElementById('pane-computer');
  pane.innerHTML = 'Yukleniyor...';
  try {
    const data = await (await fetch('/api/computer/permissions')).json();
    if (!data.available) { pane.innerHTML = '<div class="sk-desc">Bilgisayar araclari kullanilamiyor.</div>'; return; }
    const perms = data.permissions || {};
    const riskColors = {low: 'var(--green)', medium: 'var(--accent)', high: '#ff4444'};
    const riskLabels = {low: 'Dusuk', medium: 'Orta', high: 'Yuksek'};
    let html = '<div class="tool-cat">Bilgisayar Araclari</div>';
    html += '<div class="sk-desc" style="margin-bottom:12px">Bu aracllar bilgisayariniza erisim saglar. Guvenlik icin varsayilan olarak kapalidir. Ihtiyaciniz olanlari acik hale getirin.</div>';
    const keys = Object.keys(perms);
    keys.forEach(k => {
      const p = perms[k];
      const rc = riskColors[p.risk] || 'var(--faint)';
      const rl = riskLabels[p.risk] || p.risk;
      html += '<div class="comp-row"><div class="comp-main"><div class="comp-name">' + escapeHtml(p.name) +
        ' <span class="comp-risk" style="color:' + rc + '">' + rl + '</span></div>' +
        '<div class="comp-desc">' + escapeHtml(p.desc) + '</div></div>' +
        '<label class="sw"><input type="checkbox" ' + (p.allowed ? 'checked' : '') +
        ' data-comp-tool="'+k+'" onchange="toggleComputerToolByAttr(this)"><span class="track"><span class="knob"></span></span></label></div>';
    });
    html += '<div class="tool-cat" style="margin-top:16px">Guvenlik Uyarisi</div>';
    html += '<div class="sk-desc">Komut Calistirma araci <b>yuksek risk</b> tasir. Tehlikeli komutlar otomatik engellenir ancak tum riskleri ortadan kaldirmaz. Dikkatli kullanin.</div>';
    pane.innerHTML = html;
  } catch(e) {
    pane.innerHTML = '<div class="sk-desc">Bilgisayar araclari yuklenemedi.</div>';
  }
}
function toggleComputerToolByAttr(el){ var name=el.getAttribute("data-comp-tool"); toggleComputerTool(name, el.checked); }
async function toggleComputerTool(name, enabled){
  try {
    const perms = {};
    perms[name] = enabled;
    const res = await fetch('/api/computer/permissions', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({permissions: perms})});
    const data = await res.json();
    if (data.status === 'ok') toast(enabled ? (name + ' acildi') : (name + ' kapatildi'));
    else toast('Hata: ' + (data.error || 'Guncellenemedi'), true);
  } catch(e) { toast('Izin guncelleme hatasi', true); }
}

async function loadModules() {
  try {
    const res = await fetch('/health');
    const data = await res.json();
    const moduleList = document.getElementById('module-list');
    if (!moduleList || !data.modules) return;
    const groups = {
      'Hukuk': ['resmi_gazete','mevzuat','bedesten','anayasa','kik','rekabet','sayistay','kvkk','sigorta_tahkim','uyusmazlik','emsal','ihale'],
      'Mali': ['gib','ivd','sgk','iskur','turmob','ismmmo'],
      'Mevzuat': ['mevzuat_bedesten','mevzuat_new'],
      'Süreler': ['deadlines'],
      'Davalar': ['davalar'],
      '\u0130hale': ['ihale'],
      'Borsa': ['borsa'],
    };
    let html = '';
    for (const [label, keys] of Object.entries(groups)) {
      const active = keys.filter(k => data.modules[k]).length;
      html += '<div class="mod"><div class="mod-left"><span class="sdot' + (active > 0 ? '' : ' off') + '"></span> ' + label + '</div><span class="mod-count">' + active + '/' + keys.length + '</span></div>';
    }
    moduleList.innerHTML = html;
  } catch(e) {}
}
loadModules();

// ===== \u00d6nbellek Y\u00f6netimi =====
async function loadCachePane(){
  const pane = document.getElementById('pane-cache');
  pane.innerHTML = 'Y\u00fckleniyor...';
  try {
    const stats = await (await fetch('/api/cache/stats')).json();
    let html = '<div class="tool-cat">Ara\u00e7 \u00d6nbelle\u011fi</div>';
    html += '<div class="sk-desc" style="margin-bottom:16px">Ara\u00e7 sonu\u00e7lar\u0131 TTL s\u00fcresi boyunca \u00f6nbellekte tutulur. H\u0131zl\u0131 yan\u0131tlar ve d\u013c\u015f API \u00e7a\u011fr\u0131lar\u0131n\u0131 azalt\u0131r.</div>';
    html += '<div class="comp-row"><div class="comp-main"><div class="comp-name">\u00d6nbellek Giri\u015fleri</div><div class="comp-desc">' + (stats.entries || 0) + ' kay\u0131t</div></div></div>';
    html += '<div class="comp-row"><div class="comp-main"><div class="comp-name">Hit Rate</div><div class="comp-desc">' + (stats.hit_rate || '0%') + '</div></div></div>';
    html += '<div class="comp-row"><div class="comp-main"><div class="comp-name">Hit / Miss</div><div class="comp-desc">' + (stats.hits || 0) + ' / ' + (stats.misses || 0) + '</div></div></div>';
    html += '<div style="margin-top:16px"><button class="btn-primary" onclick="clearCache()">&#x1f5d1; \u00d6nbelle\u011fi Temizle</button></div>';
    pane.innerHTML = html;
  } catch(e) {
    pane.innerHTML = '<div class="sk-desc">\u00d6nbellek bilgisi y\u00fcklenemedi.</div>';
  }
}
async function clearCache(){
  try {
    const res = await fetch('/api/cache/clear', {method:'POST'});
    const data = await res.json();
    toast(data.cleared + ' kay\u0131t silindi');
    loadCachePane();
  } catch(e) { toast('\u00d6nbellek temizleme hatas\u0131', true); }
}

// ===== API Anahtarlar\u0131 =====
const API_KEY_DEFS = [
  {id: 'tavily', label: 'Tavily API Anahtar\u0131', placeholder: 'tvly-...'},
  {id: 'brave', label: 'Brave API Token', placeholder: 'BSA...'},
  {id: 'mistral', label: 'Mistral API Anahtar\u0131', placeholder: 'sk-...'},
  {id: 'evds', label: 'EVDS API Anahtar\u0131', placeholder: 'EVDS anahtar\u0131'},
];
async function loadApiKeysPane(){
  const pane = document.getElementById('pane-apikeys');
  pane.innerHTML = 'Y\u00fckleniyor...';
  try {
    const keys = await (await fetch('/api/settings/api-keys')).json();
    let html = '<div class="tool-cat">API Anahtarlar\u0131</div>';
    html += '<div class="sk-desc" style="margin-bottom:16px">Arama ve OCR aralar i\u00e7in API anahtarlar\u0131. Varsay\u0131lan geli\u015ftirme anahtarlar\u0131 otomatik kullan\u0131l\u0131r; kendi anahtar\u0131n\u0131z\u0131 girerek s\u0131n\u0131rlar\u0131 art\u0131rabilirsiniz.</div>';
    API_KEY_DEFS.forEach(def => {
      const val = keys[def.id] || '';
      const hasFallback = keys[def.id + '_fallback'] === 'dev';
      html += '<div class="comp-row" style="flex-direction:column;align-items:stretch;gap:8px">';
      html += '<div class="comp-name">' + def.label + '</div>';
      if (val) html += '<div class="comp-desc" style="margin:0">Mevcut: <code>' + escapeHtml(val) + '</code></div>';
      else if (hasFallback) html += '<div class="comp-desc" style="margin:0;color:var(--accent)">Varsay\u0131lan geli\u015ftirme anahtar\u0131 kullan\u0131l\u0131yor</div>';
      else html += '<div class="comp-desc" style="margin:0;color:#ff8c00">Anahtar tan\u0131mlanmam\u0131\u015f</div>';
      html += '<div style="display:flex;gap:8px;align-items:center">';
      html += '<input type="password" id="apikey-' + def.id + '" placeholder="' + def.placeholder + '" style="flex:1;padding:6px 10px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-size:13px">';
      html += '<button class="btn-primary" style="padding:6px 14px;font-size:13px" onclick="saveApiKey(\'' + def.id + '\')">Kaydet</button>';
      if (val) html += '<button class="btn-ghost" style="padding:6px 10px;font-size:13px" onclick="deleteApiKey(\'' + def.id + '\')">Sil</button>';
      html += '</div></div>';
    });
    pane.innerHTML = html;
  } catch(e) {
    pane.innerHTML = '<div class="sk-desc">API anahtarlar\u0131 y\u00fcklenemedi.</div>';
  }
}
async function saveApiKey(id){
  const input = document.getElementById('apikey-' + id);
  if (!input || !input.value.trim()) { toast('Anahtar bo\u015f olamaz', true); return; }
  try {
    const payload = {}; payload[id] = input.value.trim();
    const res = await fetch('/api/settings/api-keys', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const data = await res.json();
    if (data[id] === 'saved') { toast('Anahtar kaydedildi'); loadApiKeysPane(); }
    else toast('Kay\u0131t ba\u015far\u0131s\u0131z', true);
  } catch(e) { toast('Anahtar kaydetme hatas\u0131', true); }
}
async function deleteApiKey(id){
  try {
    const payload = {}; payload[id] = '';
    const res = await fetch('/api/settings/api-keys', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const data = await res.json();
    if (data[id] === 'deleted') { toast('Anahtar silindi'); loadApiKeysPane(); }
    else toast('Silme ba\u015far\u0131s\u0131z', true);
  } catch(e) { toast('Anahtar silme hatas\u0131', true); }
}

// ===== Sure Takip (Deadlines) =====
let deadlines = [];
const DL_CATEGORIES = [
  {id:'ihtar_itiraz',label:'\u0130htar \u0130tiraz\u0131',days:7,badge:'dl-badge-ihtar'},
  {id:'odeme_emri_itiraz',label:'\u00d6deme Emri \u0130tiraz\u0131',days:7,badge:'dl-badge-odeme'},
  {id:'icra_itiraz',label:'\u0130cra \u0130tiraz\u0131',days:7,badge:'dl-badge-icra'},
  {id:'temyiz',label:'Temyiz',days:15,badge:'dl-badge-temyiz'},
  {id:'istinaf',label:'\u0130stinaf',days:15,badge:'dl-badge-istinaf'},
  {id:'yargitay_itiraz',label:'Yarg\u0131tay \u0130tiraz\u0131',days:15,badge:'dl-badge-yargitay'},
  {id:'idari_basvuru',label:'\u0130dari Ba\u015fvuru',days:30,badge:'dl-badge-idari'},
  {id:'diger',label:'Di\u011fer (manuel)',days:0,badge:'dl-badge-diger'}
];

async function loadDeadlines(){
  try {
    const res = await fetch('/api/deadlines');
    const data = await res.json();
    deadlines = data.deadlines || [];
  } catch(e) { deadlines = []; }
  renderDeadlineSidebar();
}

function renderDeadlineSidebar(){
  const list = document.getElementById('deadline-list');
  const count = document.getElementById('dl-count');
  if (!list || !count) return;
  const today = new Date().toISOString().slice(0,10);
  const active = deadlines.filter(d => d.status === 'active');
  const overdue = active.filter(d => d.deadline_date < today);
  const urgent = active.filter(d => {
    const diff = (new Date(d.deadline_date) - new Date(today)) / 86400000;
    return diff >= 0 && diff <= 3;
  });
  count.textContent = overdue.length > 0 ? overdue.length + '!' : (urgent.length > 0 ? urgent.length : '');
  if (active.length === 0) { list.innerHTML = '<div class="sk-desc" style="padding:4px 9px;font-size:11px">S\u00fcre yok</div>'; return; }
  const show = active.slice(0, 5);
  let html = '';
  show.forEach(d => {
    const cat = DL_CATEGORIES.find(c => c.id === d.category) || DL_CATEGORIES[7];
    const diff = Math.ceil((new Date(d.deadline_date) - new Date(today)) / 86400000);
    const isOverdue = diff < 0;
    const isUrgent = diff >= 0 && diff <= 3;
    const cls = isOverdue ? 'dl-overdue' : (isUrgent ? 'dl-urgent' : '');
    const daysText = isOverdue ? 'GEC\u0130KM\u0130\u015e!' : (diff === 0 ? 'Bug\u00fcn!' : diff + ' g\u00fcn');
    html += '<div class="dl-item ' + cls + '"><span class="dl-badge ' + cat.badge + '">' + cat.label + '</span><div style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + escapeHtml(d.title) + '</div><span class="dl-days" style="color:' + (isOverdue ? '#f44336' : (isUrgent ? '#ff9800' : 'var(--faint)')) + '">' + daysText + '</span></div>';
  });
  list.innerHTML = html;
}

function loadDeadlinesPane(){
  const pane = document.getElementById('pane-deadlines');
  pane.innerHTML = 'Y\u00fckleniyor...';
  let html = '<div class="tool-cat">Hukuki S\u00fcreler</div>';
  html += '<div class="sk-desc" style="margin-bottom:12px">Dava a\u00e7ma, temyiz, itiraz s\u00fcrelerini takip edin. TBK m.149 uyar\u0131nca ilk g\u00fcn hari\u00e7, son g\u00fcn dahil hesaplan\u0131r. Hafta sonu son g\u00fcn ise ilk i\u015f g\u00fcn\u00fcne kayd\u0131r\u0131l\u0131r.</div>';
  // Ekleme formu
  html += '<div class="dl-add-row">';
  html += '<select id="dl-cat">';
  DL_CATEGORIES.forEach(c => { html += '<option value="' + c.id + '">' + c.label + (c.days > 0 ? ' (' + c.days + ' g\u00fcn)' : '') + '</option>'; });
  html += '</select>';
  html += '<input type="text" id="dl-title" placeholder="S\u00fcre ba\u015fl\u0131\u011f\u0131" style="flex:1;min-width:100px">';
  html += '<input type="date" id="dl-start" value="' + new Date().toISOString().slice(0,10) + '">';
  html += '<input type="number" id="dl-days" placeholder="G\u00fcn" min="1" max="3650" style="width:50px" title="0 = kategori varsay\u0131lan\u0131">';
  html += '<button data-act="add-deadline">+</button>';
  html += '</div>';
  // Filtre
  html += '<div class="dl-filter-row">';
  html += '<button class="active" data-act="filter-dl" data-filter="active">Aktif</button>';
  html += '<button data-act="filter-dl" data-filter="completed">Tamamlanan</button>';
  html += '<button data-act="filter-dl" data-filter="all">T\u00fcm\u00fc</button>';
  html += '</div>';
  html += '<div id="dl-pane-list"></div>';
  pane.innerHTML = html;
  renderDeadlineList('active');
}

function renderDeadlineList(filter){
  const list = document.getElementById('dl-pane-list');
  if (!list) return;
  const today = new Date().toISOString().slice(0,10);
  let items = filter === 'all' ? deadlines : deadlines.filter(d => d.status === filter);
  if (filter === 'active') items = deadlines.filter(d => d.status === 'active' || d.deadline_date < today);
  if (items.length === 0) { list.innerHTML = '<div class="sk-desc">S\u00fcre bulunamad\u0131.</div>'; return; }
  let html = '';
  items.forEach(d => {
    const cat = DL_CATEGORIES.find(c => c.id === d.category) || DL_CATEGORIES[7];
    const diff = Math.ceil((new Date(d.deadline_date) - new Date(today)) / 86400000);
    const isOverdue = diff < 0 && d.status === 'active';
    const isUrgent = diff >= 0 && diff <= 3 && d.status === 'active';
    const cls = isOverdue ? 'dl-overdue' : (isUrgent ? 'dl-urgent' : '');
    const daysText = isOverdue ? 'GEC\u0130KM\u0130\u015e!' : (diff === 0 ? 'Bug\u00fcn!' : (d.status === 'completed' ? 'Tamamland\u0131' : diff + ' g\u00fcn'));
    const daysColor = isOverdue ? '#f44336' : (isUrgent ? '#ff9800' : 'var(--faint)');
    html += '<div class="dl-item ' + cls + '" data-dl-id="' + d.id + '">';
    html += '<span class="dl-badge ' + cat.badge + '">' + cat.label + '</span>';
    html += '<div style="flex:1">';
    html += '<div style="font-size:12px;font-weight:500;color:var(--text)">' + escapeHtml(d.title) + '</div>';
    html += '<div style="font-size:10px;color:var(--faint)">' + d.start_date + ' \u2192 ' + d.deadline_date + ' (' + d.days_allowed + ' g\u00fcn)</div>';
    if (d.description) html += '<div style="font-size:10px;color:var(--faint);margin-top:1px">' + escapeHtml(d.description) + '</div>';
    html += '</div>';
    html += '<span class="dl-days" style="color:' + daysColor + '">' + daysText + '</span>';
    html += '<div class="dl-actions">';
    if (d.status === 'active') html += '<button data-act="complete-dl" data-id="' + d.id + '">\u2713</button>';
    html += '<button data-act="delete-dl" data-id="' + d.id + '">\u2717</button>';
    html += '</div></div>';
  });
  list.innerHTML = html;
}

async function addDeadline(){
  const cat = document.getElementById('dl-cat');
  const title = document.getElementById('dl-title');
  const start = document.getElementById('dl-start');
  const days = document.getElementById('dl-days');
  if (!title.value.trim()) { toast('Ba\u015fl\u0131k bo\u015f olamaz', true); return; }
  try {
    const payload = {category: cat.value, title: title.value.trim(), start_date: start.value};
    if (days.value && parseInt(days.value) > 0) payload.days_allowed = parseInt(days.value);
    const res = await fetch('/api/deadlines', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const data = await res.json();
    if (data.error) { toast(data.error, true); return; }
    toast('S\u00fcre eklendi');
    title.value = '';
    days.value = '';
    await loadDeadlines();
    loadDeadlinesPane();
  } catch(e) { toast('S\u00fcre ekleme hatas\u0131', true); }
}

async function completeDeadline(id){
  try {
    const res = await fetch('/api/deadlines/complete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})});
    await res.json();
    toast('Tamamland\u0131');
    await loadDeadlines();
    loadDeadlinesPane();
  } catch(e) { toast('Hata', true); }
}

async function deleteDeadline(id){
  try {
    const res = await fetch('/api/deadlines/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})});
    await res.json();
    toast('Silindi');
    await loadDeadlines();
    loadDeadlinesPane();
  } catch(e) { toast('Silme hatas\u0131', true); }
}

// ===== Memory (Bellek) =====
let memories = [];

async function loadMemories() {
  try {
    const res = await fetch('/api/memory');
    const data = await res.json();
    memories = data.memories || [];
    renderMemories();
  } catch(e) { memories = []; renderMemories(); }
}

// Sohbetten otomatik bellek öğrenme (arka planda, yanıtı yavaşlatmaz)
function learnFromConversation(userMsg, assistantMsg, provider, model, apiKey) {
  if (!userMsg || !assistantMsg) return;
  const headers = {'Content-Type': 'application/json'};
  headers['X-LLM-Provider'] = provider; headers['X-LLM-Model'] = model;
  if (apiKey && PROVIDERS[provider] && PROVIDERS[provider].needs_key) headers['X-API-Key'] = apiKey;
  fetch('/api/memory/learn', { method: 'POST', headers, body: JSON.stringify({
    provider, model, api_key: apiKey, api_keys: apiKeys,
    history: [{role:'user', text:userMsg}, {role:'assistant', text:assistantMsg}]
  }) })
  .then(r => r.json())
  .then(d => {
    const addN = (d.added||[]).length, forgN = (d.forgotten||[]).length;
    if (addN || forgN) loadMemories();
    if (addN) toast('🧠 Belleğe eklendi: ' + d.added.map(a=>a.content).join(' · ').slice(0,70));
    if (forgN) toast('🧠 ' + forgN + ' bilgi unutuldu');
  })
  .catch(()=>{});
}

async function clearMemories() {
  if (!confirm('Tüm bellek kayıtları silinsin mi?')) return;
  try { await fetch('/api/memory/clear', {method:'POST'}); loadMemories(); toast('Bellek temizlendi'); } catch(e){}
}

function renderMemories() {
  const list = document.getElementById('memory-list');
  const count = document.getElementById('mem-count');
  if (count) count.textContent = memories.length ? memories.length : '';
  if (!memories.length) {
    list.innerHTML = '<div style="text-align:center;color:var(--faint);padding:12px;font-size:11px">Henuz bellek yok</div>';
    return;
  }
  const catLabels = {preference:'tercih', fact:'olgu', instruction:'talimat'};
  list.innerHTML = memories.map(function(m) {
    const auto = (m.source === 'auto') ? '<span class="mem-auto" title="Sohbetten otomatik öğrenildi">oto</span>' : '';
    return '<div class="mem-item" data-mem-id="' + m.id + '">' +
      '<span class="mem-badge ' + m.category + '">' + (catLabels[m.category]||m.category) + '</span>' + auto +
      '<span class="mem-text">' + escapeHtml(m.content) + '</span>' +
      '<span class="mem-del" data-act="del-memory" data-mem-id="' + m.id + '">' + ic('x') + '</span></div>';
  }).join('');
}

async function addMemory() {
  const cat = document.getElementById('mem-cat').value;
  const content = document.getElementById('mem-input').value.trim();
  if (!content) return;
  await fetch('/api/memory', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({category:cat, content:content})});
  document.getElementById('mem-input').value = '';
  loadMemories();
}

async function deleteMemory(id) {
  await fetch('/api/memory/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id:id})});
  loadMemories();
}

document.getElementById('mem-input').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') { e.preventDefault(); addMemory(); }
});
loadMemories();

// ===== Dava Kartları =====
const DK_TURLERI = [
  {id:'tazminat',label:'Tazminat',badge:'dk-badge-tazminat'},
  {id:'istirdat',label:'İstirdat',badge:'dk-badge-istirdat'},
  {id:'menfi_tespit',label:'Menfi Tespit',badge:'dk-badge-tespit'},
  {id:'icra_itiraz',label:'İcra İtiraz',badge:'dk-badge-icra'},
  {id:'aile_hukuku',label:'Aile Hukuku',badge:'dk-badge-aile'},
  {id:'miras',label:'Miras',badge:'dk-badge-miras'},
  {id:'ticari_uyumazlik',label:'Ticari Uyuşmazlık',badge:'dk-badge-ticari'},
  {id:'idari_dava',label:'İdari Dava',badge:'dk-badge-idari'},
  {id:'ceza',label:'Ceza',badge:'dk-badge-ceza'},
  {id:'is_hukuku',label:'İş Hukuku',badge:'dk-badge-is'},
  {id:'kira',label:'Kira',badge:'dk-badge-kira'},
  {id:'gayrimenkul',label:'Gayrimenkul',badge:'dk-badge-gmulk'},
  {id:'sozlesme',label:'Sözleşme',badge:'dk-badge-sozlesme'},
  {id:'diger',label:'Diğer',badge:'dk-badge-diger'}
];
const DK_DURUMLAR = {
  devam_ediyor:{label:'Devam Ediyor',cls:'dk-durum-devam_ediyor'},
  kazanildi:{label:'Kazanıldı',cls:'dk-durum-kazanildi'},
  kaybedildi:{label:'Kaybedildi',cls:'dk-durum-kaybedildi'},
  feragat:{label:'Feragat',cls:'dk-durum-feragat'},
  kabul:{label:'Kabul',cls:'dk-durum-kabul'}
};
let davaKartlari = [];

async function loadDavaKartlari(){
  try{
    const r = await fetch('/api/dava-kartlari');
    const d = await r.json();
    davaKartlari = d.kartlar || [];
  }catch(e){davaKartlari = [];}
  renderDavaKartSidebar();
}

function renderDavaKartSidebar(){
  const list = document.getElementById('dava-list');
  const badge = document.getElementById('dk-count');
  if(!list) return;
  const active = davaKartlari.filter(k => k.durum === 'devam_ediyor');
  if(badge) badge.textContent = active.length || '';
  if(active.length === 0){list.innerHTML = '<div class="sk-desc" style="padding:4px 9px;font-size:11px">Dava kartı yok</div>';return;}
  let html = '';
  active.slice(0,5).forEach(k => {
    const t = (DK_TURLERI.find(t => t.id === k.dava_turu) || {label:k.dava_turu});
    html += '<div class="dl-item" style="margin-bottom:3px"><span class="dk-badge '+(t.badge||'dk-badge-diger')+'">'+t.label+'</span><div class="dl-days" style="font-size:11px">'+k.esas_no+'</div><div style="font-size:10px;color:var(--faint)">'+(k.taraf_muvekkil||'')+' vs '+(k.taraf_karsi||'')+'</div></div>';
  });
  list.innerHTML = html;
}

async function loadDavaKartlariPane(){
  const pane = document.getElementById('pane-davalar');
  if(!pane) return;
  pane.innerHTML = '<div class="sk-desc">Yükleniyor...</div>';
  try{
    const r = await fetch('/api/dava-kartlari');
    const d = await r.json();
    davaKartlari = d.kartlar || [];
  }catch(e){davaKartlari = [];}
  let html = '<div class="tool-cat">Dava Kartları</div>';
  html += '<div class="sk-desc" style="margin-bottom:12px">Dava dosyalarınızı takip edin. Esas no, müvekkil, karşı taraf ve durum bilgisi saklayın.</div>';
  // Add form
  html += '<div class="dk-add-row">';
  html += '<select id="dk-tur">';
  DK_TURLERI.forEach(t => html += '<option value="'+t.id+'">'+t.label+'</option>');
  html += '</select>';
  html += '<input type="text" id="dk-esas" placeholder="Esas no (zorunlu)" style="flex:1;min-width:120px">';
  html += '<input type="text" id="dk-muvekkil" placeholder="Müvekkil" style="width:100px">';
  html += '<input type="text" id="dk-karsi" placeholder="Karşı taraf" style="width:100px">';
  html += '<input type="text" id="dk-daire" placeholder="Mahkeme/daire" style="width:120px">';
  html += '<input type="date" id="dk-acilis" style="width:110px">';
  html += '<button class="btn-primary" data-act="add-dava" style="padding:5px 12px;font-size:12px">Ekle</button>';
  html += '</div>';
  // Filter row
  html += '<div class="dk-filter-row">';
  html += '<button data-act="filter-dk" data-filter="all" class="active">Tümü</button>';
  Object.entries(DK_DURUMLAR).forEach(([k,v]) => html += '<button data-act="filter-dk" data-filter="'+k+'">'+v.label+'</button>');
  html += '</div>';
  html += '<div id="dk-list"></div>';
  pane.innerHTML = html;
  renderDavaKartList('all');
}

function renderDavaKartList(filter){
  const list = document.getElementById('dk-list');
  if(!list) return;
  let items = davaKartlari;
  if(filter && filter !== 'all') items = items.filter(k => k.durum === filter);
  if(items.length === 0){list.innerHTML = '<div class="sk-desc">Dava kartı bulunamadı.</div>';return;}
  let html = '';
  items.forEach(k => {
    const t = DK_TURLERI.find(t => t.id === k.dava_turu) || {label:k.dava_turu, badge:'dk-badge-diger'};
    const d = DK_DURUMLAR[k.durum] || {label:k.durum, cls:'dk-durum-devam_ediyor'};
    const taraflar = (k.taraf_muvekkil||k.taraf_karsi) ? (k.taraf_muvekkil||'—') + ' vs ' + (k.taraf_karsi||'—') : '';
    html += '<div class="dk-item">';
    html += '<div><span class="dk-badge '+(t.badge||'dk-badge-diger')+'">'+t.label+'</span><span class="dk-durum '+d.cls+'">'+d.label+'</span> <span class="dk-esas">'+k.esas_no+'</span></div>';
    if(k.daire) html += '<div class="dk-meta">'+k.daire+'</div>';
    if(taraflar) html += '<div class="dk-meta">'+taraflar+'</div>';
    if(k.konu) html += '<div class="dk-meta" style="color:var(--text)">'+k.konu+'</div>';
    if(k.acilis_tarihi) html += '<div class="dk-meta">Açılış: '+k.acilis_tarihi+'</div>';
    if(k.deadline_ids && k.deadline_ids.length) html += '<div class="dk-meta">⏰ '+k.deadline_ids.length+' süre bağlı</div>';
    html += '<div class="dk-actions">';
    if(k.durum === 'devam_ediyor'){
      html += '<button data-act="update-dk-durum" data-id="'+k.id+'" data-durum="kazanildi">✓ Kazanıldı</button>';
      html += '<button data-act="update-dk-durum" data-id="'+k.id+'" data-durum="kaybedildi">✗ Kaybedildi</button>';
      html += '<button data-act="update-dk-durum" data-id="'+k.id+'" data-durum="feragat">↩ Feragat</button>';
      html += '<button data-act="update-dk-durum" data-id="'+k.id+'" data-durum="kabul">✓ Kabul</button>';
    }
    html += '<button data-act="delete-dk" data-id="'+k.id+'" style="color:#ef4444">🗑</button>';
    html += '</div></div>';
  });
  list.innerHTML = html;
}

async function addDavaKarti(){
  const tur = document.getElementById('dk-tur');
  const esas = document.getElementById('dk-esas');
  const muvekkil = document.getElementById('dk-muvekkil');
  const karsi = document.getElementById('dk-karsi');
  const daire = document.getElementById('dk-daire');
  const acilis = document.getElementById('dk-acilis');
  if(!esas || !esas.value.trim()){toast('Esas numarası zorunlu',true);return;}
  try{
    const r = await fetch('/api/dava-kartlari',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      esas_no:esas.value.trim(), dava_turu:tur?tur.value:'diger',
      taraf_muvekkil:muvekkil?muvekkil.value.trim():'',
      taraf_karsi:karsi?karsi.value.trim():'',
      daire:daire?daire.value.trim():'',
      acilis_tarihi:acilis?acilis.value:''
    })});
    if(!r.ok){toast('Dava kartı eklenemedi',true);return;}
    toast('Dava kartı eklendi');
    if(esas) esas.value = '';
    if(muvekkil) muvekkil.value = '';
    if(karsi) karsi.value = '';
    if(daire) daire.value = '';
    if(acilis) acilis.value = '';
    await loadDavaKartlari();
    loadDavaKartlariPane();
  }catch(e){toast('Hata: '+e.message, true);}
}

async function deleteDavaKarti(id){
  try{
    await fetch('/api/dava-kartlari/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
    toast('Dava kartı silindi');
    await loadDavaKartlari();
    loadDavaKartlariPane();
  }catch(e){toast('Silme hatası', true);}
}

async function updateDavaDurum(id, durum){
  try{
    await fetch('/api/dava-kartlari/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id, durum})});
    toast('Durum güncellendi');
    await loadDavaKartlari();
    loadDavaKartlariPane();
  }catch(e){toast('Güncelleme hatası', true);}
}

// ===== Yedekleme =====
let backups = [];

async function loadBackups(){
  try{
    const r = await fetch('/api/backup');
    const d = await r.json();
    backups = d.backups || [];
  }catch(e){backups = [];}
  renderBackupList();
}

function renderBackupList(){
  const list = document.getElementById('backup-list');
  if(!list) return;
  if(backups.length === 0){
    list.innerHTML = '<div class="sk-desc" style="padding:4px 9px;font-size:11px">Henüz yedek yok</div>';
    return;
  }
  let html = '';
  backups.forEach(b => {
    html += '<div class="backup-item">';
    html += '<div class="backup-item-row">';
    html += '<div><div style="font-size:12px;font-weight:600">'+b.filename+'</div>';
    html += '<div class="backup-meta">'+b.size_formatted+' — '+b.created_str+'</div></div>';
    html += '<div class="backup-actions">';
    html += '<button class="bk-restore" data-act="restore-backup" data-file="'+b.filename+'" title="Geri yükle">↩</button>';
    html += '<button class="bk-download" data-act="download-backup" data-file="'+b.filename+'" title="İndir">↓</button>';
    html += '<button class="bk-delete" data-act="delete-backup" data-file="'+b.filename+'" title="Sil">🗑</button>';
    html += '</div></div></div>';
  });
  list.innerHTML = html;
}

async function createBackup(){
  toast('Yedek oluşturuluyor...');
  try{
    const r = await fetch('/api/backup/create',{method:'POST'});
    const d = await r.json();
    if(d.ok){
      toast('Yedek oluşturuldu: '+d.filename+' ('+d.size_formatted+')');
      await loadBackups();
    }else{
      toast('Yedek hatası: '+(d.error||'Bilinmeyen hata'), true);
    }
  }catch(e){toast('Yedek hatası: '+e.message, true);}
}

async function restoreBackup(filename){
  if(!confirm('"'+filename+'" yedeğini geri yüklemek istediğinize emin misiniz?\n\nMevcut veriler otomatik olarak yedeklenecek.')) return;
  toast('Geri yükleniyor...');
  try{
    const r = await fetch('/api/backup/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename})});
    const d = await r.json();
    if(d.ok){
      toast('Geri yükleme başarılı! ('+d.restored_files+' dosya). Sayfa yenilenecek.');
      setTimeout(()=>location.reload(), 1500);
    }else{
      toast('Geri yükleme hatası: '+(d.error||'Bilinmeyen hata'), true);
    }
  }catch(e){toast('Geri yükleme hatası: '+e.message, true);}
}

function downloadBackup(filename){
  window.open('/api/backup/download?file='+encodeURIComponent(filename), '_blank');
}

async function deleteBackup(filename){
  if(!confirm('"'+filename+'" yedeğini silmek istediğinize emin misiniz?')) return;
  try{
    const r = await fetch('/api/backup/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename})});
    const d = await r.json();
    if(d.status === 'ok'){
      toast('Yedek silindi');
      await loadBackups();
    }else{
      toast('Silme hatası: '+(d.error||'Bulunamadı'), true);
    }
  }catch(e){toast('Silme hatası: '+e.message, true);}
}

// ===== Init =====
async function init() {
  applyTheme(currentTheme);
  applySidebar();
  loadConfig();
  loadDeadlines();
  loadDavaKartlari();
  loadBackups();
  setupTree();
  await bootstrapWorkspace();   // sunucudan klasör + oturumları çek
  renderTree();
  // Kaldığı yerden devam: aktif oturum yoksa en son güncelleneni aç
  let target = activeChatId && chats.find(c => c.id === activeChatId) ? activeChatId : (chats[0] && chats[0].id);
  if (target) { await selectChat(target); }
  else { renderChat(); }
}
init();
