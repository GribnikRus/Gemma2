const state = {
    currentUser: null,
    currentChat: null,
    currentChatType: 'personal',
    chats: [],
    groups: [],
    usersStatus: [],
    lastMessageId: null,
    originalTitle: document.title,
    socket: null,
    appInitialized: false
};

// ========== ИНИЦИАЛИЗАЦИЯ ==========
document.addEventListener('DOMContentLoaded', () => {
    // Просто запускаем приложение, считая что пользователь уже авторизован
    initApp();
});

let initInProgress = false; // Защита от повторных вызовов

async function initApp() {
    // Защита от повторного вызова
    if (initInProgress) {
        console.log('Init already in progress, skipping');
        return;
    }
    initInProgress = true;
    
    console.log('=== INIT APP START ===');
    
    try {
        // Загружаем информацию о текущем пользователе
        console.log('Fetching /api/auth/me...');
        const user = await apiRequest('/api/auth/me');
        console.log('User data received:', user);
        
        state.currentUser = {
            ...user,
            id: user.client_id,
            client_id: user.client_id
        };
        console.log('✅ User loaded:', state.currentUser);
        
        // Показываем интерфейс
        showApp();
        console.log('=== INIT APP FINISHED ===');
        
    } catch (e) { 
        console.error('❌ Init error:', e);
        console.log('Redirecting to /login');
        window.location.href = '/login';
    } finally {
        initInProgress = false;
    }
}
function showApp() {
    if (state.appInitialized) return;
    state.appInitialized = true;
    
    document.getElementById('user-display').textContent = state.currentUser.login;
    document.getElementById('user-avatar').textContent = state.currentUser.login[0].toUpperCase();
    
    initSocket();
    loadChats();
    checkAIAvailability();
    loadModels();
    setupEventListeners();
}

// ========== WEBSOCKET ==========
function initSocket() {
    state.socket = io();
    
    state.socket.on('connect', () => {
        console.log('✅ WebSocket connected');
        loadUsers();
    });
    
    state.socket.on('disconnect', () => {
        console.log('⚠️ WebSocket disconnected');
    });
    
    state.socket.on('connect_error', (error) => {
        console.error('❌ WebSocket connection error:', error);
    });
    
    state.socket.on('new_message', (data) => {
        console.log('📨 New message received:', data);
        
        if (data.sender_type === 'ai') {
            hideTypingIndicator();
        }
        
        let isCurrentChat = false;
        if (state.currentChat) {
            if (state.currentChatType === 'group' && data.group_id) {
                isCurrentChat = state.currentChat.id === data.group_id;
            } else if (state.currentChatType === 'personal' && data.personal_chat_id) {
                isCurrentChat = state.currentChat.id === data.personal_chat_id;
            }
        }
        
        if (isCurrentChat) {
            const existingMsg = document.querySelector(`.message[data-msg-id="${data.id}"]`);
            if (!existingMsg) {
                renderSingleMessage(data);
            }
        } else {
            const chatName = data.chat_name || (data.group_id ? 'группе' : 'личном чате');
            showToast(`🔔 Новое сообщение в ${chatName}`);
            document.title = '🔔 Новое сообщение!';
            setTimeout(() => { document.title = state.originalTitle; }, 3000);
        }
    });
    
    state.socket.on('user_joined', (data) => {
        console.log('👤 User joined:', data);
        loadUsers();
        if (state.currentChatType === 'group' && state.currentChat?.id === data.group_id) {
            updateMembersList();
        }
    });
    
    state.socket.on('user_left', (data) => {
        console.log('👋 User left:', data);
        loadUsers();
        if (state.currentChatType === 'group' && state.currentChat?.id === data.group_id) {
            updateMembersList();
        }
    });
    
    state.socket.on('joined_group', (data) => {
        console.log(`✅ Joined group room: group_${data.group_id}`);
    });
    
    state.socket.on('joined_personal', (data) => {
        console.log(`✅ Joined personal chat room: personal_${data.personal_chat_id}`);
    });
    
    state.socket.on('error', (data) => {
        console.error('❌ WebSocket error:', data.message);
        showToast(`⚠️ ${data.message}`);
    });
}

function joinGroupRoom(groupId) {
    if (state.socket && state.socket.connected) {
        console.log(`🔗 Joining group: ${groupId}`);
        state.socket.emit('join_group', { group_id: groupId });
    }
}

function joinPersonalRoom(personalChatId) {
    if (state.socket && state.socket.connected) {
        console.log(`🔗 Joining personal chat: ${personalChatId}`);
        state.socket.emit('join_personal', { personal_chat_id: personalChatId });
    }
}

function sendMessageViaSocket(content, personalChatId, groupId) {
    if (!state.socket || !state.socket.connected) {
        console.error('❌ WebSocket not connected');
        return false;
    }
    
    state.socket.emit('send_message', {
        content: content,
        personal_chat_id: personalChatId,
        group_id: groupId
    });
    return true;
}

// ========== ОТОБРАЖЕНИЕ СООБЩЕНИЙ ==========
function renderSingleMessage(m) {
    const container = document.getElementById('messages-container');
    if (!container) return;
    
    const existingMsg = document.querySelector(`.message[data-msg-id="${m.id}"]`);
    if (existingMsg) return;
    
    const currentUserId = state.currentUser?.id || state.currentUser?.client_id;
    const isUser = m.sender_type === 'client' && m.sender_id === currentUserId;
    
    let senderHtml = '';
    
    if (state.currentChatType === 'group' && !isUser && m.sender_name) {
        senderHtml = `<span class="msg-sender" style="color: #3390ec; font-weight: bold;">${escapeHtml(m.sender_name)}</span>`;
    } else if (!isUser && m.sender_type === 'ai') {
        senderHtml = `<span class="msg-sender" style="color: #e53935; font-weight: bold;">Gemma AI</span>`;
    }
    
    const msgHtml = `
    <div class="message ${isUser ? 'user' : 'ai'}" data-msg-id="${m.id}">
        ${senderHtml}
        <div class="msg-content">${escapeHtml(m.content)}</div>
        <div class="msg-time">${new Date(m.created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</div>
    </div>`;
    
    container.insertAdjacentHTML('beforeend', msgHtml);
    container.scrollTop = container.scrollHeight;
}

function renderMessages(msgs) {
    const c = document.getElementById('messages-container');
    if (!c) return;
    
    const currentUserId = state.currentUser?.id || state.currentUser?.client_id;
    
    c.innerHTML = msgs.map(m => {
        const isMe = m.sender_type === 'client' && m.sender_id === currentUserId;
        
        let senderHtml = '';
        if (state.currentChatType === 'group' && !isMe && m.sender_name) {
            senderHtml = `<span class="msg-sender" style="color: #3390ec; font-weight: bold; display:block; margin-bottom:2px; font-size:0.8rem;">${escapeHtml(m.sender_name)}</span>`;
        } else if (m.sender_type === 'ai') {
            senderHtml = `<span class="msg-sender" style="color: #e53935; font-weight: bold; display:block; margin-bottom:2px; font-size:0.8rem;">Gemma AI</span>`;
        }
        
        return `
        <div class="message ${isMe ? 'user' : 'ai'}">
            ${senderHtml}
            <div class="msg-content">${escapeHtml(m.content)}</div>
            <div class="msg-time">${new Date(m.created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</div>
        </div>`;
    }).join('');
    
    c.scrollTop = c.scrollHeight;
}

// ========== ЗАГРУЗКА ЧАТОВ ==========
async function loadChats() {
    try {
        const data = await apiRequest('/api/client/chats');
        console.log('📥 Loaded chats:', data);
        state.chats = data.personal_chats || [];
        state.groups = data.groups || [];
        renderList('chats-list', state.chats, 'personal');
        renderList('groups-list', state.groups, 'group');
        loadUsers();
        loadInvitations();
    } catch (error) {
        console.error('❌ Error loading chats:', error);
    }
}

function renderList(id, items, type) {
    const el = document.getElementById(id);
    if (!el) {
        console.error(`❌ Element #${id} not found`);
        return;
    }
    
    if (!items || items.length === 0) {
        el.innerHTML = `<div class="empty-state" style="padding:10px; color:#707579; text-align:center;">Нет ${type === 'personal' ? 'чатов' : 'групп'}</div>`;
        return;
    }
    
    el.innerHTML = items.map(i => {
        const displayName = i.title || i.name;
        const firstChar = displayName ? displayName[0] : '?';
        return `
            <div class="${type === 'personal' ? 'chat-item' : 'group-item'}" onclick="window.selectChat(${i.id}, '${type}')">
                <div class="avatar" style="width:35px; height:35px; font-size:1rem;">${escapeHtml(firstChar)}</div>
                <div style="flex:1; overflow:hidden;">
                    <div style="font-weight:500;">${escapeHtml(displayName)}</div>
                </div>
            </div>
        `;
    }).join('');
}

// ========== ВЫБОР ЧАТА ==========
async function selectChat(id, type) {
    stopMessagePolling();
    
    state.currentChatType = type;
    try {
        const data = await apiRequest(type === 'personal' ? `/api/chat/personal/${id}` : `/api/group/${id}`);
        state.currentChat = type === 'personal' ? data.chat : data.group;
        
        document.getElementById('current-chat-title').textContent = state.currentChat.title || state.currentChat.name;
        
        const aiToggle = document.getElementById('ai-enabled-toggle');
        if (aiToggle && state.currentChat) {
            aiToggle.checked = (state.currentChat.ai_enabled !== false);
        }
        
        renderMessages(data.messages);
        
        if (type === 'group') {
            joinGroupRoom(id);
        } else {
            joinPersonalRoom(id);
        }
        
        document.getElementById('sidebar').classList.remove('open');
        document.getElementById('overlay').classList.remove('active');
        
        const membersSec = document.getElementById('members-section');
        if (type === 'group') {
            membersSec.classList.remove('hidden');
            if (data.members) {
                document.getElementById('members-list').innerHTML = data.members.map(m => 
                    `<div class="chat-item" style="padding:5px;"><div class="avatar" style="width:25px;height:25px;font-size:0.7rem">${escapeHtml(m.login[0])}</div> ${escapeHtml(m.login)}</div>`
                ).join('');
            }
            loadInvitations();
        } else {
            membersSec.classList.add('hidden');
        }
    } catch(e) { 
        console.error('Error selecting chat:', e);
        alert(e.message); 
    }
}

// ========== ОТПРАВКА СООБЩЕНИЯ ==========
async function sendMessage() {
    const inp = document.getElementById('message-input');
    const txt = inp.value.trim();
    if (!txt || !state.currentChat) return;

    if (txt.startsWith('/setai ')) {
        const newName = txt.substring(7).trim();
        if (newName.length < 2) {
            alert('Имя должно содержать минимум 2 символа');
            inp.value = '';
            return;
        }
        await setAiName(newName);
        inp.value = '';
        return;
    }

    const aiToggle = document.getElementById('ai-enabled-toggle');
    const isAiEnabled = aiToggle && aiToggle.checked;
    const aiName = state.currentChat.ai_name || 'Гемма';
    const mightTriggerAi = isAiEnabled && (
        txt.startsWith('@') || 
        txt.startsWith('/gemma') || 
        txt.startsWith('/ai') ||
        txt.toLowerCase().startsWith(aiName.toLowerCase())
    );
    
    if (mightTriggerAi) {
        showTypingIndicator();
    }

    inp.value = '';

    try {
        const sent = sendMessageViaSocket(
            txt,
            state.currentChatType === 'personal' ? state.currentChat.id : null,
            state.currentChatType === 'group' ? state.currentChat.id : null
        );

        if (!sent) {
            throw new Error('WebSocket не подключен');
        }

        setTimeout(() => {
            hideTypingIndicator();
        }, 10000);

    } catch(e) { 
        console.error('Send error:', e);
        alert('Ошибка отправки: ' + e.message);
        hideTypingIndicator();
    }
}

// ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
function showTypingIndicator() {
    let indicator = document.getElementById('typing-indicator');
    if (!indicator) {
        const container = document.getElementById('messages-container');
        if (!container) return;
        container.insertAdjacentHTML('beforeend', `
            <div id="typing-indicator" class="typing-indicator hidden">
                <div class="message ai">
                    <div class="msg-sender" style="color: #e53935;">Gemma AI</div>
                    <div class="msg-content"><span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></div>
                </div>
            </div>
        `);
        indicator = document.getElementById('typing-indicator');
    }
    indicator.classList.remove('hidden');
    const container = document.getElementById('messages-container');
    container.scrollTop = container.scrollHeight;
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.classList.add('hidden');
}

function stopMessagePolling() {
    state.lastMessageId = null;
    document.title = state.originalTitle;
}

function updateMembersList() {
    if (state.currentChatType !== 'group' || !state.currentChat) return;
    apiRequest(`/api/group/${state.currentChat.id}`)
        .then(data => {
            const membersList = document.getElementById('members-list');
            if (membersList && data.members) {
                membersList.innerHTML = data.members.map(m => 
                    `<div class="chat-item" style="padding:5px;"><div class="avatar" style="width:25px;height:25px;font-size:0.7rem">${escapeHtml(m.login[0])}</div> ${escapeHtml(m.login)}</div>`
                ).join('');
            }
        })
        .catch(e => console.error('Error updating members:', e));
}

async function apiRequest(endpoint, method = 'GET', data = null) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (data) options.body = JSON.stringify(data);
    const res = await fetch(endpoint, options);
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || 'Ошибка');
    return json;
}

function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function showToast(message) {
    console.log('Toast:', message);
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#333;color:white;padding:12px 20px;border-radius:8px;z-index:1000;';
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function switchMode(mode) {
    document.querySelectorAll('.input-wrapper').forEach(el => el.classList.add('hidden'));
    document.getElementById(`${mode}-input-container`).classList.remove('hidden');
}

async function loadUsers() {
    try {
        const res = await apiRequest('/api/users/list');
        state.usersStatus = res.users;
        const container = document.getElementById('users-list-container');
        if (!container) return;
        const onlineUsers = res.users.filter(u => u.is_online && u.login !== state.currentUser.login);
        container.innerHTML = onlineUsers.length === 0 
            ? '<li style="padding:5px; color:#707579;">Нет пользователей онлайн</li>'
            : onlineUsers.map(u => `<li style="padding:5px; display:flex; align-items:center; gap:8px;"><span style="width:10px; height:10px; background:#0f0; border-radius:50%;"></span><span>${escapeHtml(u.login)}</span></li>`).join('');
    } catch(e) {
        console.error('Error loading users:', e);
    }
}

async function runObserverAnalysis() {
    if(!state.currentChat) return alert('Выберите чат');
    const role = document.getElementById('observer-role').value;
    const resBox = document.getElementById('observer-results-container');
    const resText = document.getElementById('observer-analysis-result');
    resBox.classList.remove('hidden');
    resText.textContent = 'Анализирую...';
    try {
        let res;
        if(state.currentChatType === 'group') {
            res = await apiRequest('/api/group/observe', 'POST', { group_id: state.currentChat.id, role_prompt: role });
        } else {
            res = await apiRequest('/api/chat/observe', 'POST', { personal_chat_id: state.currentChat.id, role_prompt: role });
        }
        resText.textContent = res.analysis || res.result;
    } catch(e) {
        resText.textContent = 'Ошибка: ' + e.message;
    }
}

async function loadInvitations() {
    try {
        const data = await apiRequest('/api/invitations');
        const invitations = data.invitations || [];
        const container = document.getElementById('invitations-list');
        if (!container) return;
        if (invitations.length === 0) {
            container.innerHTML = '<p style="color:#707579;font-size:0.9rem;">Нет входящих приглашений</p>';
            return;
        }
        container.innerHTML = invitations.map(inv => `
            <div class="chat-item" style="padding:5px;display:flex;justify-content:space-between;align-items:center;">
                <span>Группа: ${escapeHtml(inv.group_name)}</span>
                <button class="btn-sm accept-invite-btn" data-group-id="${inv.group_id}" style="background:#3390ec;color:white;border:none;padding:5px 10px;border-radius:4px;">Принять</button>
            </div>
        `).join('');
        document.querySelectorAll('.accept-invite-btn').forEach(btn => {
            btn.onclick = async () => {
                const groupId = btn.dataset.groupId;
                await acceptInvite(parseInt(groupId));
            };
        });
    } catch(e) {
        console.error('Error loading invitations:', e);
    }
}

async function acceptInvite(groupId) {
    try {
        await apiRequest('/api/invitations/accept', 'POST', { group_id: groupId });
        alert('Приглашение принято!');
        loadInvitations();
        loadChats();
    } catch(e) {
        alert(e.message);
    }
}

async function checkAIAvailability() {
    const statusIcon = document.getElementById('ai-status-icon');
    const statusText = document.getElementById('ai-status-text');
    if (!statusIcon || !statusText) return;
    try {
        const response = await fetch('/api/ai/status');
        const data = await response.json();
        if (data.available) {
            statusIcon.textContent = '🟢';
            statusText.textContent = 'AI готов';
        } else {
            statusIcon.textContent = '🔴';
            statusText.textContent = 'AI недоступен';
        }
    } catch (error) {
        statusIcon.textContent = '🔴';
        statusText.textContent = 'ошибка';
    }
}

async function loadModels() {
    try {
        const response = await fetch('/api/ai/models');
        const data = await response.json();
        if (data.available && data.models) {
            const chatSelect = document.getElementById('chat-model-select');
            const visionSelect = document.getElementById('vision-model-select');
            if (!chatSelect || !visionSelect) return;
            const optionsHtml = data.models.map(m => `<option value="${m.name}">${m.name}</option>`).join('');
            chatSelect.innerHTML = optionsHtml;
            visionSelect.innerHTML = optionsHtml;
            if (data.current_chat_model) chatSelect.value = data.current_chat_model;
            if (data.current_vision_model) visionSelect.value = data.current_vision_model;
            chatSelect.onchange = () => changeModel(chatSelect.value, false);
            visionSelect.onchange = () => changeModel(visionSelect.value, true);
        }
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

async function changeModel(modelName, forVision) {
    if (!modelName) return;
    const select = forVision ? document.getElementById('vision-model-select') : document.getElementById('chat-model-select');
    if (!select) return;
    try {
        select.disabled = true;
        const response = await fetch('/api/ai/models/set', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: modelName, for_vision: forVision })
        });
        const result = await response.json();
        if (result.success) {
            showToast(`✅ Модель изменена`);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        console.error('Failed to change model:', error);
        showToast(`❌ Ошибка смены модели`);
    } finally {
        select.disabled = false;
    }
}

async function setAiName(newName) {
    if (!state.currentChat) return;
    try {
        await apiRequest('/api/chat/set_ai_name', 'POST', {
            chat_type: state.currentChatType,
            chat_id: state.currentChat.id,
            new_name: newName
        });
        state.currentChat.ai_name = newName;
        showToast(`Имя AI изменено на "${newName}"`);
    } catch(e) {
        alert('Ошибка: ' + e.message);
    }
}

function setupEventListeners() {
    const sidebar = document.getElementById('sidebar');
    const rightPanel = document.getElementById('right-panel');
    const overlay = document.getElementById('overlay');
    
    document.getElementById('menu-toggle').onclick = () => {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('active');
        rightPanel.classList.remove('open');
    };
    document.getElementById('info-toggle').onclick = () => {
        rightPanel.classList.toggle('open');
        sidebar.classList.remove('open');
    };
    document.getElementById('close-right-panel').onclick = () => {
        rightPanel.classList.remove('open');
    };
    overlay.onclick = () => {
        sidebar.classList.remove('open');
        rightPanel.classList.remove('open');
        overlay.classList.remove('active');
    };
    document.getElementById('send-btn').onclick = sendMessage;
    document.getElementById('message-input').onkeypress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    };
    document.querySelectorAll('.tool-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            switchMode(btn.dataset.mode);
            if (btn.dataset.mode === 'observer') {
                rightPanel.classList.add('open');
                if (window.innerWidth <= 768) overlay.classList.add('active');
            }
        };
    });
    document.getElementById('logout-btn').onclick = () => {
        stopMessagePolling();
        if (state.socket && state.socket.connected) state.socket.disconnect();
        window.location.href = '/login';
    };
    document.getElementById('new-chat-btn').onclick = async () => {
        const login = prompt('Введите логин пользователя:');
        if (!login || !login.trim()) return;
        try {
            const chat = await apiRequest('/api/chat/personal/create', 'POST', { partner_login: login.trim() });
            loadChats();
            selectChat(chat.id, 'personal');
        } catch(e) { alert(e.message); }
    };
    document.getElementById('ai-enabled-toggle').onchange = async (e) => {
        if(!state.currentChat) return;
        try {
            await apiRequest('/api/chat/toggle_ai', 'POST', {
                chat_type: state.currentChatType,
                chat_id: state.currentChat.id
            });
        } catch(err) { alert('Ошибка переключения ИИ'); e.target.checked = !e.target.checked; }
    };
    document.getElementById('analyze-btn').onclick = runObserverAnalysis;
    document.getElementById('invite-user-btn').onclick = async () => {
        const login = document.getElementById('invite-login-input').value;
        if(!login || !state.currentChat) return;
        try {
            await apiRequest('/api/group/invite', 'POST', { group_id: state.currentChat.id, login });
            alert('Приглашено!');
            document.getElementById('invite-login-input').value = '';
        } catch(e) { alert(e.message); }
    };
    document.getElementById('create-group-btn').onclick = async () => {
        const nameInput = document.getElementById('new-group-name');
        const name = nameInput.value.trim();
        if(!name) return alert('Введите название группы');
        try {
            const group = await apiRequest('/api/group/create', 'POST', { name });
            alert(`Группа "${group.name}" создана!`);
            nameInput.value = '';
            loadChats();
        } catch(e) { alert(e.message); }
    };
}

setInterval(checkAIAvailability, 30000);

// ========== ДИНАМИЧЕСКАЯ ЗАГРУЗКА МОДУЛЯ ИЗОБРАЖЕНИЙ ==========
async function loadImageModule() {
    try {
        const module = await import('./modules/images.js');
        module.setupImagePreview();
        module.setupImageUpload(
            () => state,
            showTypingIndicator,
            hideTypingIndicator,
            showToast
        );
        console.log('✅ Модуль изображений загружен');
    } catch (error) {
        console.error('❌ Ошибка загрузки модуля изображений:', error);
        const uploadBtn = document.getElementById('upload-image-btn');
        if (uploadBtn) {
            uploadBtn.onclick = () => alert('Модуль изображений не загружен. Обновите страницу.');
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadImageModule);
} else {
    loadImageModule();
}

const audioBtn = document.getElementById('upload-audio-btn');
if (audioBtn) {
    audioBtn.onclick = () => alert('Загрузка аудио требует доработки бэкенда');
}

// ========== ГЛОБАЛЬНЫЕ ФУНКЦИИ ==========
window.selectChat = selectChat;
window.sendMessage = sendMessage;
window.runObserverAnalysis = runObserverAnalysis;
window.acceptInvite = acceptInvite;
window.setAiName = setAiName;
window.showToast = showToast;

console.log('✅ App initialized');