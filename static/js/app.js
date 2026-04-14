const state = {
    currentUser: null,
    currentChat: null,
    currentChatType: 'personal',
    chats: [],
    groups: [],
    usersStatus: [],
    lastMessageId: null,
    originalTitle: document.title,
    socket: null  // WebSocket соединение
};

// --- WebSocket Functions ---
function initSocket() {
    // Инициализируем Socket.IO соединение
    state.socket = io();
    
    state.socket.on('connect', () => {
        console.log('✅ WebSocket connected');
        // При подключении загружаем актуальный список пользователей
        loadUsers();
    });
    
    state.socket.on('disconnect', () => {
        console.log('⚠️ WebSocket disconnected');
    });
    
    state.socket.on('connect_error', (error) => {
        console.error('❌ WebSocket connection error:', error);
    });
    
    state.socket.on('new_message', (data) => {
        console.log('📨 New message received via WebSocket:', {
            id: data.id,
            sender: data.sender_name,
            chat_id: data.personal_chat_id || data.group_id
        });
        
        // Скрываем индикатор печатания, если получили сообщение (это ответ AI)
        if (data.sender_type === 'ai') {
            console.log('🤖 AI response received, hiding typing indicator');
            hideTypingIndicator();
        }
        
        // Исправлено: более надежная проверка соответствия чата
        let isCurrentChat = false;
        
        if (state.currentChat) {
            if (state.currentChatType === 'group' && data.group_id) {
                isCurrentChat = state.currentChat.id === data.group_id;
            } else if (state.currentChatType === 'personal' && data.personal_chat_id) {
                isCurrentChat = state.currentChat.id === data.personal_chat_id;
            }
        }
        
        console.log(`Current chat: type=${state.currentChatType}, id=${state.currentChat?.id}, isCurrent=${isCurrentChat}`);
        
        if (isCurrentChat) {
            // ✅ Проверяем, нет ли уже такого сообщения (защита от дублей)
            const existingMsg = document.querySelector(`.message[data-msg-id="${data.id}"]`);
            if (existingMsg) {
                console.log(`⚠️ Message ${data.id} already in DOM, skipping render`);
                return;
            }
            
            console.log(`✅ Rendering message ${data.id} in current chat`);
            // Добавляем сообщение в текущий чат
            renderSingleMessage(data);
        } else {
            // Если чат не открыт, показываем уведомление
            const chatName = data.chat_name || (data.group_id ? 'группе' : 'личном чате');
            showToast(`🔔 Новое сообщение в ${chatName}`);
            document.title = '🔔 Новое сообщение!';
            setTimeout(() => { document.title = state.originalTitle; }, 3000);
        }
    });
    
    // Событие: пользователь присоединился к чату/группе
    state.socket.on('user_joined', (data) => {
        console.log('👤 User joined:', data);
        loadUsers(); // Обновляем список онлайн-пользователей
        if (state.currentChatType === 'group' && state.currentChat?.id === data.group_id) {
            updateMembersList(); // Обновляем список участников группы
        }
    });
    
    // Событие: пользователь покинул чат/группу
    state.socket.on('user_left', (data) => {
        console.log('👋 User left:', data);
        loadUsers(); // Обновляем список онлайн-пользователей
        if (state.currentChatType === 'group' && state.currentChat?.id === data.group_id) {
            updateMembersList(); // Обновляем список участников группы
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
    });
}

function joinGroupRoom(groupId) {
    if (state.socket && state.socket.connected) {
        console.log(`🔗 Emitting join_group: ${groupId}`);
        state.socket.emit('join_group', { group_id: groupId });
    }
}

function joinPersonalRoom(personalChatId) {
    if (state.socket && state.socket.connected) {
        console.log(`🔗 Emitting join_personal: ${personalChatId}`);
        state.socket.emit('join_personal', { personal_chat_id: personalChatId });
    }
}

function sendMessageViaSocket(content, personalChatId, groupId) {
    if (state.socket && state.socket.connected) {
        state.socket.emit('send_message', {
            content: content,
            personal_chat_id: personalChatId,
            group_id: groupId
        });
        return true;
    }
    return false;
}

// ИСПРАВЛЕНО: используем id вместо client_id
function renderSingleMessage(m) {
    const container = document.getElementById('messages-container');
    if (!container) return;
    
    // Проверяем, нет ли уже такого сообщения в DOM
    const existingMsg = document.querySelector(`.message[data-msg-id="${m.id}"]`);
    if (existingMsg) return;
    
    // ИСПРАВЛЕНО: используем state.currentUser.id (не client_id)
    const isUser = m.sender_type === 'client' && m.sender_id === state.currentUser?.id;
    
    console.log(`📝 Rendering message: isUser=${isUser}, sender_id=${m.sender_id}, currentUser.id=${state.currentUser?.id}`);
    
    let senderHtml = '';
    
    // Логика имен для групповых чатов
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

function showToast(message) {
    // Простая реализация уведомления
    console.log('🍞 Toast:', message);
    
    // Визуальное отображение тоста (опционально)
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#333;color:white;padding:12px 20px;border-radius:8px;z-index:1000;animation:slideIn 0.3s ease;';
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ========== НОВЫЕ ФУНКЦИИ ДЛЯ ИНДИКАТОРА ПЕЧАТАНИЯ ==========
function showTypingIndicator() {
    let indicator = document.getElementById('typing-indicator');
    if (!indicator) {
        // Создаем индикатор, если его нет
        const container = document.getElementById('messages-container');
        if (!container) return;
        
        const indicatorHtml = `
            <div id="typing-indicator" class="typing-indicator hidden">
                <div class="message ai">
                    <div class="msg-sender" style="color: #e53935;">Gemma AI</div>
                    <div class="msg-content">
                        <span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
                    </div>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', indicatorHtml);
        indicator = document.getElementById('typing-indicator');
    }
    
    indicator.classList.remove('hidden');
    const container = document.getElementById('messages-container');
    container.scrollTop = container.scrollHeight;
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.classList.add('hidden');
        // Не удаляем элемент, чтобы можно было показать снова
    }
}
// ========== КОНЕЦ НОВЫХ ФУНКЦИЙ ==========

// --- Polling Functions (удалено, т.к. теперь используется WebSocket) ---
function stopMessagePolling() {
    // Очищаем lastMessageId и восстанавливаем заголовок
    state.lastMessageId = null;
    document.title = state.originalTitle;
}

// Добавляем функцию для обновления списка участников группы
function updateMembersList() {
    if (state.currentChatType !== 'group' || !state.currentChat) return;
    
    // Загружаем свежие данные о группе
    apiRequest(`/api/group/${state.currentChat.id}`)
        .then(data => {
            const membersList = document.getElementById('members-list');
            if (membersList && data.members) {
                membersList.innerHTML = data.members.map(m => 
                    `<div class="chat-item" style="padding:5px;"><div class="avatar" style="width:25px;height:25px;font-size:0.7rem">${m.login[0]}</div> ${m.login}</div>`
                ).join('');
            }
        })
        .catch(e => console.error('Ошибка обновления списка участников:', e));
}

// --- API Helpers ---
async function apiRequest(endpoint, method = 'GET', data = null) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (data) options.body = JSON.stringify(data);
    const res = await fetch(endpoint, options);
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || 'Ошибка');
    return json;
}

// Экспорт для использования в login.html
window.apiRequest = apiRequest;

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
    // Проверяем, находимся ли мы на странице index.html (есть auth-modal)
    const isIndexPage = document.getElementById('auth-modal');
    
    if (isIndexPage) {
        // Инициализируем только для index.html
        initAuth();
        checkSession();
        setupEventListeners();
    }
    // Для login.html инициализация происходит через встроенные скрипты
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
            // ИСПРАВЛЕНИЕ: добавляем поле id из client_id
            state.currentUser = {
                ...res,
                id: res.client_id,
                client_id: res.client_id
            };
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
        // ИСПРАВЛЕНИЕ: добавляем поле id из client_id
        state.currentUser = {
            ...user,
            id: user.client_id,  // <-- добавляем эту строку
            client_id: user.client_id
        };
        console.log('✅ User loaded:', state.currentUser);
        showApp();
    } catch (e) { 
        console.log('⚠️ No active session, showing auth modal');
        document.getElementById('auth-modal').classList.remove('hidden'); 
    }
}

function showApp() {
    document.getElementById('auth-modal').classList.add('hidden');
    document.getElementById('app-container').classList.remove('hidden');
    document.getElementById('user-display').textContent = state.currentUser.login;
    document.getElementById('user-avatar').textContent = state.currentUser.login[0].toUpperCase();
    
    initSocket(); // Инициализируем WebSocket при входе в приложение
    loadChats();
    checkAIAvailability();  // Проверка статуса AI при загрузке
    loadModels();  // ✅ Загружаем список моделей
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
    
    document.getElementById('logout-btn').onclick = () => {
        stopMessagePolling();
        if (state.socket && state.socket.connected) {
            state.socket.disconnect();
        }
        window.location.reload();
    };
    
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
    try {
        const data = await apiRequest('/api/client/chats');
        console.log('📥 Loaded chats:', data);
        state.chats = data.personal_chats || [];
        state.groups = data.groups || [];
        renderList('chats-list', state.chats, 'personal');
        renderList('groups-list', state.groups, 'group');
        loadUsers();
        loadInvitations(); // Загружаем приглашения при загрузке чатов
        
        // Если чаты уже были загружены и есть текущий чат, обновляем его состояние
        if (state.currentChat) {
            console.log('✅ Chats reloaded, current chat preserved');
        }
    } catch (error) {
        console.error('❌ Error loading chats:', error);
    }
}

// ИСПРАВЛЕНО: добавлена проверка существования элемента и fallback
function renderList(id, items, type) {
    const el = document.getElementById(id);
    if (!el) {
        console.error(`❌ Element #${id} not found in DOM`);
        return;
    }
    
    console.log(`📝 Rendering ${items.length} items for ${id}`, items);
    
    if (!items || items.length === 0) {
        el.innerHTML = `<div class="empty-state" style="padding:10px; color:#707579; text-align:center;">Нет ${type === 'personal' ? 'чатов' : 'групп'}</div>`;
        return;
    }
    
    el.innerHTML = items.map(i => `
        <div class="${type === 'personal' ? 'chat-item' : 'group-item'}" onclick="window.selectChat(${i.id}, '${type}')">
            <div class="avatar" style="width:35px; height:35px; font-size:1rem;">${((i.title || i.name) || '?')[0]}</div>
            <div style="flex:1; overflow:hidden;">
                <div style="font-weight:500;">${escapeHtml(i.title || i.name)}</div>
            </div>
        </div>
    `).join('');
}

async function selectChat(id, type) {
    // Останавливаем polling для предыдущего чата
    stopMessagePolling();
    
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
        
        // Устанавливаем lastMessageId на последнее сообщение из истории
        if (data.messages && data.messages.length > 0) {
            state.lastMessageId = data.messages[data.messages.length - 1].id;
        }
        
        // Подключаемся к комнате через WebSocket
        if (type === 'group') {
            joinGroupRoom(id);
        } else {
            joinPersonalRoom(id);
        }
        
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

    // Отладка в консоль
    console.log("🎨 Отрисовка сообщений. Тип чата:", state.currentChatType, "Мой ID:", state.currentUser ? state.currentUser.id : 'нет');

    c.innerHTML = msgs.map(m => {
        // ИСПРАВЛЕНО: используем id вместо client_id
        const isMe = state.currentUser && (m.sender_id === state.currentUser.id);
        
        let senderHtml = '';

        // Логика имен:
        // 1. Если это ГРУППА и пишет НЕ Я -> показываем имя участника
        if (state.currentChatType === 'group' && !isMe && m.sender_name) {
             senderHtml = `<span class="msg-sender" style="color: #3390ec; font-weight: bold; display:block; margin-bottom:2px; font-size:0.8rem;">${escapeHtml(m.sender_name)}</span>`;
        } 
        // 2. Если пишет ИИ (в любом чате) -> показываем "Gemma AI"
        else if (m.sender_type === 'ai') {
             senderHtml = `<span class="msg-sender" style="color: #e53935; font-weight: bold; display:block; margin-bottom:2px; font-size:0.8rem;">Gemma AI</span>`;
        }

        return `
        <div class="message ${isMe ? 'user' : 'ai'}">
            ${senderHtml}
            <div class="msg-content">${escapeHtml(m.content)}</div>
            <div class="msg-time">${new Date(m.created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</div>
        </div>
    `}).join('');
    
    c.scrollTop = c.scrollHeight;
}

// ========== МОДИФИЦИРОВАННАЯ ФУНКЦИЯ sendMessage ==========
async function sendMessage() {
    const inp = document.getElementById('message-input');
    const txt = inp.value.trim();
    if (!txt || !state.currentChat) return;

    // Проверяем команду смены имени ИИ
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

    // Проверяем, может ли это сообщение вызвать AI
    const aiToggle = document.getElementById('ai-enabled-toggle');
    const isAiEnabled = aiToggle && aiToggle.checked;
    
    // Определяем, есть ли триггер для AI
    const aiName = state.currentChat.ai_name || 'Гемма';
    const mightTriggerAi = isAiEnabled && (
        txt.startsWith('@') || 
        txt.startsWith('/gemma') || 
        txt.startsWith('/ai') ||
        txt.toLowerCase().startsWith(aiName.toLowerCase())
    );
    
    // Показываем индикатор печатания, если сообщение может вызвать AI
    if (mightTriggerAi) {
        showTypingIndicator();
    }

    // Очищаем поле ввода сразу
    inp.value = '';

    try {
        // Отправляем сообщение через WebSocket
        const sent = sendMessageViaSocket(
            txt,
            state.currentChatType === 'personal' ? state.currentChat.id : null,
            state.currentChatType === 'group' ? state.currentChat.id : null
        );

        if (!sent) {
            throw new Error('WebSocket не подключен');
        }

        // Если через 10 секунд не пришел ответ, скрываем индикатор
        setTimeout(() => {
            hideTypingIndicator();
        }, 10000);

    } catch(e) { 
        alert('Ошибка отправки: ' + e.message);
        hideTypingIndicator();
    }
}
// ========== КОНЕЦ МОДИФИЦИРОВАННОЙ ФУНКЦИИ ==========

// Вспомогательная функция для безопасности (защита от XSS)
function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
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
                    <span>${escapeHtml(u.login)}</span>
                </li>`
            ).join('');
        }
    } catch(e) {
        console.error('Ошибка загрузки пользователей:', e);
        const container = document.getElementById('users-list-container');
        if (container) container.innerHTML = '<li style="color:red;">Ошибка загрузки</li>';
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
        
        // Вешаем обработчики на кнопки "Принять"
        document.querySelectorAll('.accept-invite-btn').forEach(btn => {
            btn.onclick = async () => {
                const groupId = btn.dataset.groupId;
                await acceptInvite(parseInt(groupId));
            };
        });
    } catch(e) {
        console.error('Ошибка загрузки приглашений:', e);
        const container = document.getElementById('invitations-list');
        if (container) container.innerHTML = '<p style="color:red;">Ошибка загрузки</p>';
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

// Функция проверки доступности AI модели
async function checkAIAvailability() {
    const statusIcon = document.getElementById('ai-status-icon');
    const statusText = document.getElementById('ai-status-text');
    
    if (!statusIcon || !statusText) return;
    
    try {
        // Проверяем доступность Ollama через специальный эндпоинт
        const response = await fetch('/api/ai/status');
        const data = await response.json();
        
        if (data.available) {
            statusIcon.textContent = '🟢';
            statusText.textContent = 'AI готов';
            statusIcon.title = 'Модель доступна';
        } else {
            statusIcon.textContent = '🔴';
            statusText.textContent = 'AI недоступен';
            statusIcon.title = data.error || 'Модель не отвечает';
        }
    } catch (error) {
        statusIcon.textContent = '🔴';
        statusText.textContent = 'ошибка';
        statusIcon.title = 'Не удалось проверить статус AI';
        console.error('Ошибка проверки AI статуса:', error);
    }
}

// Вызывать при загрузке приложения и каждые 30 секунд
setInterval(checkAIAvailability, 30000);

// ========== НОВЫЕ ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ МОДЕЛЯМИ ==========

async function loadModels() {
   /// """Загружает список доступных моделей и заполняет селекторы"""///
    try {
        const response = await fetch('/api/ai/models');
        const data = await response.json();
        
        if (data.available && data.models) {
            const chatSelect = document.getElementById('chat-model-select');
            const visionSelect = document.getElementById('vision-model-select');
            
            if (!chatSelect || !visionSelect) return;
            
            // Заполняем селекторы
            const optionsHtml = data.models.map(m => 
                `<option value="${m.name}" title="${m.params}, ${m.size_gb}GB">
                    ${m.name} (${m.params})
                </option>`
            ).join('');
            
            chatSelect.innerHTML = optionsHtml;
            visionSelect.innerHTML = optionsHtml;
            
            // Устанавливаем текущие модели
            if (data.current_chat_model) {
                chatSelect.value = data.current_chat_model;
            }
            if (data.current_vision_model) {
                visionSelect.value = data.current_vision_model;
            }
            
            // Обработчики смены моделей
            chatSelect.onchange = async () => {
                await changeModel(chatSelect.value, false);
            };
            
            visionSelect.onchange = async () => {
                await changeModel(visionSelect.value, true);
            };
            
            console.log('✅ Models loaded:', data.models.length);
        } else {
            console.warn('⚠️ No models available');
            const chatSelect = document.getElementById('chat-model-select');
            const visionSelect = document.getElementById('vision-model-select');
            if (chatSelect) chatSelect.innerHTML = '<option>❌ Нет моделей</option>';
            if (visionSelect) visionSelect.innerHTML = '<option>❌ Нет моделей</option>';
        }
    } catch (error) {
        console.error('❌ Failed to load models:', error);
        const chatSelect = document.getElementById('chat-model-select');
        const visionSelect = document.getElementById('vision-model-select');
        if (chatSelect) chatSelect.innerHTML = '<option>⚠️ Ошибка</option>';
        if (visionSelect) visionSelect.innerHTML = '<option>⚠️ Ошибка</option>';
    }
}

async function changeModel(modelName, forVision) {
   /// """Меняет активную модель через API"""///
    if (!modelName) return;
    
    const type = forVision ? 'vision' : 'chat';
    const select = forVision ? 
        document.getElementById('vision-model-select') : 
        document.getElementById('chat-model-select');
    
    if (!select) return;
    
    try {
        // Показываем загрузку
        const originalValue = select.value;
        select.disabled = true;
        
        const response = await fetch('/api/ai/models/set', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: modelName,
                for_vision: forVision
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast(`✅ Модель ${type}: ${modelName}`);
            console.log(`✅ Model changed (${type}):`, modelName);
            
            // Обновляем статус AI
            checkAIAvailability();
        } else {
            throw new Error(result.error || 'Failed to change model');
        }
    } catch (error) {
        console.error(`❌ Failed to change ${type} model:`, error);
        showToast(`❌ Ошибка смены модели: ${error.message}`);
        // Возвращаем старое значение
        select.value = select.options[select.selectedIndex].value;
    } finally {
        select.disabled = false;
    }
}

// ========== КОНЕЦ НОВЫХ ФУНКЦИЙ ==========

// Функция для смены имени AI (нужно добавить)
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

// ========== ДИНАМИЧЕСКАЯ ЗАГРУЗКА МОДУЛЯ ИЗОБРАЖЕНИЙ ==========
async function loadImageModule() {
    try {
        const module = await import('./modules/images.js');
        module.setupImagePreview();
        module.setupImageUpload(
            () => state,  // Передаем функцию, возвращающую state
            showTypingIndicator,
            hideTypingIndicator,
            showToast
        );
        console.log('✅ Модуль изображений загружен');
    } catch (error) {
        console.error('❌ Ошибка загрузки модуля изображений:', error);
        // Fallback
        const uploadBtn = document.getElementById('upload-image-btn');
        if (uploadBtn) {
            uploadBtn.onclick = () => alert('Модуль изображений не загружен. Обновите страницу.');
        }
    }
}

// Загружаем модуль после полной загрузки DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadImageModule);
} else {
    loadImageModule();
}

// Заглушки для загрузки файлов
const audioBtn = document.getElementById('upload-audio-btn');
if (audioBtn) {
    audioBtn.onclick = () => alert('Загрузка аудио требует доработки бэкенда (endpoint /api/audio/transcribe-analyze)');
}

// ========== ГЛОБАЛЬНЫЕ ФУНКЦИИ ДЛЯ HTML ONCLICK ==========
// ЭТО САМОЕ ВАЖНОЕ - делаем функции доступными из HTML
window.selectChat = selectChat;
window.sendMessage = sendMessage;
window.runObserverAnalysis = runObserverAnalysis;
window.acceptInvite = acceptInvite;
window.setAiName = setAiName;
window.showToast = showToast;

console.log('✅ All global functions registered:', {
    selectChat: typeof window.selectChat,
    sendMessage: typeof window.sendMessage,
    runObserverAnalysis: typeof window.runObserverAnalysis
});