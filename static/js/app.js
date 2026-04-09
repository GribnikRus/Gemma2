const state = {
    currentUser: null,
    currentChat: null,
    currentChatType: 'personal',
    chats: [],
    groups: [],
    usersStatus: []
};

// --- API Helpers ---
async function apiRequest(endpoint, method = 'GET', data = null) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (data) options.body = JSON.stringify(data);
    const res = await fetch(endpoint, options);
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || 'Ошибка');
    return json;
}

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
    initAuth();
    checkSession();
    setupEventListeners();
});

function initAuth() {
    document.querySelectorAll('.tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const tab = btn.dataset.tab;
            document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
            document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
        });
    });

    document.getElementById('login-form').onsubmit = async (e) => {
        e.preventDefault();
        try {
            const login = document.getElementById('login-username').value;
            const pass = document.getElementById('login-password').value;
            const res = await apiRequest('/api/auth/login', 'POST', { login, password: pass });
            state.currentUser = res;
            showApp();
        } catch (err) { document.getElementById('login-error').textContent = err.message; }
    };

    document.getElementById('register-form').onsubmit = async (e) => {
        e.preventDefault();
        try {
            const login = document.getElementById('register-username').value;
            const pass = document.getElementById('register-password').value;
            await apiRequest('/api/auth/register', 'POST', { login, password: pass });
            alert('Успешно! Теперь войдите.');
            document.querySelector('.tab[data-tab="login"]').click();
        } catch (err) { document.getElementById('register-error').textContent = err.message; }
    };
}

async function checkSession() {
    try {
        const user = await apiRequest('/api/auth/me');
        state.currentUser = user;
        showApp();
    } catch (e) { document.getElementById('auth-modal').classList.remove('hidden'); }
}

function showApp() {
    document.getElementById('auth-modal').classList.add('hidden');
    document.getElementById('app-container').classList.remove('hidden');
    document.getElementById('user-display').textContent = state.currentUser.login;
    document.getElementById('user-avatar').textContent = state.currentUser.login[0].toUpperCase();
    loadChats();
}

function setupEventListeners() {
    // Меню
    const sidebar = document.getElementById('sidebar');
    const rightPanel = document.getElementById('right-panel');
    const overlay = document.getElementById('overlay');
    
    document.getElementById('menu-toggle').onclick = () => {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('active');
        rightPanel.classList.remove('open'); // Закрыть правую если открыта
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

    // Отправка
    document.getElementById('send-btn').onclick = sendMessage;
    document.getElementById('message-input').onkeypress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    };

    // Режимы
    document.querySelectorAll('.tool-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            switchMode(btn.dataset.mode);
            
            // Если нажат глаз, открываем правую панель
            if (btn.dataset.mode === 'observer') {
                rightPanel.classList.add('open');
                if (window.innerWidth <= 768) overlay.classList.add('active');
            }
        };
    });
    
    document.getElementById('logout-btn').onclick = () => window.location.reload();
    
    // Создание нового личного чата
    document.getElementById('new-chat-btn').onclick = async () => {
        const login = prompt('Введите логин пользователя для создания чата:');
        if (!login || !login.trim()) return;
        try {
            const chat = await apiRequest('/api/chat/personal/create', 'POST', { partner_login: login.trim() });
            loadChats(); // Обновить список чатов
            selectChat(chat.id, 'personal'); // Открыть созданный чат
        } catch(e) { alert(e.message); }
    };
    
    // AI Toggle
    document.getElementById('ai-enabled-toggle').onchange = async (e) => {
        if(!state.currentChat) return;
        try {
            await apiRequest('/api/chat/toggle_ai', 'POST', {
                chat_type: state.currentChatType,
                chat_id: state.currentChat.id
            });
        } catch(err) { alert('Ошибка переключения ИИ'); e.target.checked = !e.target.checked; }
    };
    
    // Анализатор
    document.getElementById('analyze-btn').onclick = runObserverAnalysis;
    
    // Приглашение
    document.getElementById('invite-user-btn').onclick = async () => {
        const login = document.getElementById('invite-login-input').value;
        if(!login || !state.currentChat) return;
        try {
            await apiRequest('/api/group/invite', 'POST', { group_id: state.currentChat.id, login });
            alert('Приглашено!');
            document.getElementById('invite-login-input').value = '';
        } catch(e) { alert(e.message); }
    };
    
    // Создание группы
    document.getElementById('create-group-btn').onclick = async () => {
        const nameInput = document.getElementById('new-group-name');
        const name = nameInput.value.trim();
        if(!name) return alert('Введите название группы');
        try {
            const group = await apiRequest('/api/group/create', 'POST', { name });
            alert(`Группа "${group.name}" создана!`);
            nameInput.value = '';
            loadChats(); // Перезагрузить список
        } catch(e) { alert(e.message); }
    };
}

async function loadChats() {
    const data = await apiRequest('/api/client/chats');
    state.chats = data.personal_chats || [];
    state.groups = data.groups || [];
    renderList('chats-list', state.chats, 'personal');
    renderList('groups-list', state.groups, 'group');
    loadUsers();
    loadInvitations(); // Загружаем приглашения при загрузке чатов
}

function renderList(id, items, type) {
    const el = document.getElementById(id);
    el.innerHTML = items.map(i => `
        <div class="${type === 'personal' ? 'chat-item' : 'group-item'}" onclick="selectChat(${i.id}, '${type}')">
            <div class="avatar" style="width:35px; height:35px; font-size:1rem;">${(i.title || i.name)[0]}</div>
            <div style="flex:1; overflow:hidden;">
                <div style="font-weight:500;">${i.title || i.name}</div>
            </div>
        </div>
    `).join('');
}

async function selectChat(id, type) {
    state.currentChatType = type;
    try {
        const data = await apiRequest(type === 'personal' ? `/api/chat/personal/${id}` : `/api/group/${id}`);
        state.currentChat = type === 'personal' ? data.chat : data.group;
        
        document.getElementById('current-chat-title').textContent = state.currentChat.title || state.currentChat.name;
        
        // === ВАЖНО: Синхронизируем переключатель ИИ с базой данных ===
        const aiToggle = document.getElementById('ai-enabled-toggle');
        if (aiToggle && state.currentChat) {
            // Если в базе false, то unchecked, иначе checked
            aiToggle.checked = (state.currentChat.ai_enabled !== false);
        }
        // ============================================================

        renderMessages(data.messages);
        
        // Мобильное меню закрыть
        document.getElementById('sidebar').classList.remove('open');
        document.getElementById('overlay').classList.remove('active');
        
        // Если группа, показать участников в правой панели
        const membersSec = document.getElementById('members-section');
        if (type === 'group') {
            membersSec.classList.remove('hidden');
            document.getElementById('members-list').innerHTML = data.members.map(m => 
                `<div class="chat-item" style="padding:5px;"><div class="avatar" style="width:25px;height:25px;font-size:0.7rem">${m.login[0]}</div> ${m.login}</div>`
            ).join('');
            // Загружаем приглашения при открытии группы
            loadInvitations();
        } else {
            membersSec.classList.add('hidden');
        }
    } catch(e) { alert(e.message); }
}

function renderMessages(msgs) {
    const c = document.getElementById('messages-container');
    if (!c) return;

    c.innerHTML = msgs.map(m => {
        const isUser = m.sender_type === 'client';
        let senderHtml = '';

        // Логика имен:
        // 1. Если это ГРУППА и пишет НЕ я -> показываем имя участника
        if (state.currentChatType === 'group' && !isUser && m.sender_name) {
             senderHtml = `<span class="msg-sender" style="color: #3390ec; font-weight: bold;">${m.sender_name}</span>`;
        } 
        // 2. Если пишет ИИ (в любом чате) -> показываем "Gemma"
        else if (!isUser) {
             senderHtml = `<span class="msg-sender" style="color: #e53935; font-weight: bold;">Gemma AI</span>`;
        }

        return `
        <div class="message ${isUser ? 'user' : 'ai'}">
            ${senderHtml}
            <div class="msg-content">${m.content}</div>
            <div class="msg-time">${new Date(m.created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</div>
        </div>
    `}).join('');
    
    c.scrollTop = c.scrollHeight;
}

async function sendMessage() {
    const inp = document.getElementById('message-input');
    const txt = inp.value.trim();
    if (!txt || !state.currentChat) return;
    
    // Отобразить сразу
    const c = document.getElementById('messages-container');
    c.innerHTML += `<div class="message user">${txt}<div class="msg-time">...</div></div>`;
    inp.value = '';
    c.scrollTop = c.scrollHeight;

    try {
        const res = await apiRequest('/api/chat/send', 'POST', {
            content: txt,
            personal_chat_id: state.currentChatType === 'personal' ? state.currentChat.id : null,
            group_id: state.currentChatType === 'group' ? state.currentChat.id : null
        });
        if (res.ai_message) {
            c.innerHTML += `<div class="message ai"><span class="msg-sender">Gemma</span>${res.ai_message.content}<div class="msg-time">${new Date().toLocaleTimeString()}</div></div>`;
        }
        c.scrollTop = c.scrollHeight;
    } catch(e) { alert(e.message); }
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
        
        if (onlineUsers.length === 0) {
            container.innerHTML = '<li style="padding:5px; color:#707579;">Нет пользователей онлайн</li>';
        } else {
            container.innerHTML = onlineUsers.map(u => 
                `<li style="padding:5px; display:flex; align-items:center; gap:8px;">
                    <span style="width:10px; height:10px; background:#0f0; border-radius:50%; box-shadow:0 0 5px #0f0;"></span>
                    <span>${u.login}</span>
                </li>`
            ).join('');
        }
    } catch(e) {
        console.error('Ошибка загрузки пользователей:', e);
        document.getElementById('users-list-container').innerHTML = '<li style="color:red;">Ошибка загрузки</li>';
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
            res = await apiRequest('/api/group/observe', 'POST', {
                group_id: state.currentChat.id,
                role_prompt: role
            });
        } else {
             res = await apiRequest('/api/chat/observe', 'POST', {
                personal_chat_id: state.currentChat.id,
                role_prompt: role
            });
        }
        resText.textContent = res.analysis || res.result;
    } catch(e) {
        resText.textContent = 'Ошибка: ' + e.message;
    }
}

// Загрузка приглашений
async function loadInvitations() {
    try {
        const data = await apiRequest('/api/invitations');
        const invitations = data.invitations || [];
        const container = document.getElementById('invitations-list');
        
        if (invitations.length === 0) {
            container.innerHTML = '<p style="color:#707579;font-size:0.9rem;">Нет входящих приглашений</p>';
            return;
        }
        
        container.innerHTML = invitations.map(inv => `
            <div class="chat-item" style="padding:5px;display:flex;justify-content:space-between;align-items:center;">
                <span>Группа: ${inv.group_name}</span>
                <button class="btn-sm accept-invite-btn" data-group-id="${inv.group_id}" style="background:#3390ec;color:white;border:none;padding:5px 10px;border-radius:4px;">Принять</button>
            </div>
        `).join('');
        
        // Вешаем обработчики на кнопки "Принять"
        document.querySelectorAll('.accept-invite-btn').forEach(btn => {
            btn.onclick = async () => {
                const groupId = btn.dataset.groupId;
                await acceptInvite(parseInt(groupId));
            };
        });
    } catch(e) {
        console.error('Ошибка загрузки приглашений:', e);
        document.getElementById('invitations-list').innerHTML = '<p style="color:red;">Ошибка загрузки</p>';
    }
}

// Принятие приглашения
async function acceptInvite(groupId) {
    try {
        await apiRequest('/api/invitations/accept', 'POST', { group_id: groupId });
        alert('Приглашение принято!');
        loadInvitations(); // Обновить список приглашений
        loadChats(); // Обновить список чатов/групп
    } catch(e) {
        alert(e.message);
    }
}

// Заглушки для загрузки файлов (пока нет бэкенда для мульти-фото/аудио в этом коде)
document.getElementById('upload-image-btn').onclick = () => alert('Загрузка изображений требует доработки бэкенда (endpoint /api/chat/vision)');
document.getElementById('upload-audio-btn').onclick = () => alert('Загрузка аудио требует доработки бэкенда (endpoint /api/audio/transcribe-analyze)');