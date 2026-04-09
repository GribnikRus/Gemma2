/**
 * Gemma Hub - Frontend JavaScript
 * Обработка авторизации, чатов и всех режимов работы
 */

// ==================== ГЛОБАЛЬНОЕ СОСТОЯНИЕ ====================
const state = {
    currentUser: null,
    currentChat: null,
    currentChatType: 'personal', // 'personal' или 'group'
    currentMode: 'chat', // 'chat', 'image', 'audio', 'observer'
    chats: [],
    groups: []
};

// ==================== API ХЕЛПЕРЫ ====================
async function apiRequest(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    const response = await fetch(endpoint, options);
    
    // Пробуем распарсить JSON, даже если ошибка
    let result;
    try {
        result = await response.json();
    } catch (e) {
        result = { error: 'Неверный формат ответа сервера' };
    }
    
    if (!response.ok) {
        throw new Error(result.error || 'Ошибка запроса');
    }
    
    return result;
}

async function apiUpload(endpoint, file, additionalData = {}) {
    const formData = new FormData();
    formData.append('file', file);
    
    for (const [key, value] of Object.entries(additionalData)) {
        formData.append(key, value);
    }
    
    const response = await fetch(endpoint, {
        method: 'POST',
        body: formData
    });
    
    const result = await response.json();
    
    if (!response.ok) {
        throw new Error(result.error || 'Ошибка загрузки');
    }
    
    return result;
}

// ==================== АВТОРИЗАЦИЯ ====================
function initAuth() {
    // Переключение табов
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            if (tab === 'login') {
                document.getElementById('login-form').classList.remove('hidden');
                document.getElementById('register-form').classList.add('hidden');
            } else {
                document.getElementById('login-form').classList.add('hidden');
                document.getElementById('register-form').classList.remove('hidden');
            }
        });
    });
    
    // Форма входа
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            // ИСПРАВЛЕНО: используем login вместо username
            const login = document.getElementById('login-username').value;
            const password = document.getElementById('login-password').value;
            
            try {
                const result = await apiRequest('/api/auth/login', 'POST', { login, password });
                state.currentUser = result;
                showApp();
                loadChats();
            } catch (error) {
                const errorEl = document.getElementById('login-error');
                if (errorEl) errorEl.textContent = error.message;
                else alert(error.message);
            }
        });
    }
    
    // Форма регистрации
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            // ИСПРАВЛЕНО: используем login вместо username
            const login = document.getElementById('register-username').value;
            const password = document.getElementById('register-password').value;
            
            try {
                const result = await apiRequest('/api/auth/register', 'POST', { login, password });
                // После регистрации обычно просят войти, но если бэкенд сразу логинит:
                state.currentUser = result;
                showApp();
                loadChats();
            } catch (error) {
                const errorEl = document.getElementById('register-error');
                if (errorEl) errorEl.textContent = error.message;
                else alert(error.message);
            }
        });
    }
    
    // Кнопка выхода
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            try {
                await apiRequest('/api/auth/logout', 'POST');
                state.currentUser = null;
                window.location.reload(); // Перезагрузка для очистки состояния
            } catch (error) {
                console.error('Ошибка выхода:', error);
            }
        });
    }
}

function showAuth() {
    const modal = document.getElementById('auth-modal');
    const app = document.getElementById('app-container');
    if (modal) modal.classList.remove('hidden');
    if (app) app.classList.add('hidden');
}

function showApp() {
    const modal = document.getElementById('auth-modal');
    const app = document.getElementById('app-container');
    if (modal) modal.classList.add('hidden');
    if (app) app.classList.remove('hidden');
    
    if (state.currentUser) {
        const userDisplay = document.getElementById('user-display');
        if (userDisplay) {
            // ИСПРАВЛЕНО: используем login
            userDisplay.textContent = `@${state.currentUser.login}`;
        }
    }
}

// ==================== ЗАГРУЗКА ЧАТОВ ====================
async function loadChats() {
    try {
        const data = await apiRequest('/api/client/chats');
        state.chats = data.personal_chats || [];
        state.groups = data.groups || [];
        
        renderChatsList();
        renderGroupsList();
    } catch (error) {
        console.error('Ошибка загрузки чатов:', error);
    }
}

function renderChatsList() {
    const container = document.getElementById('chats-list');
    if (!container) return;
    
    container.innerHTML = state.chats.map(chat => `
        <div class="chat-item ${state.currentChat?.id === chat.id && state.currentChatType === 'personal' ? 'active' : ''}" 
             data-chat-id="${chat.id}" data-type="personal">
            <div class="chat-item-title">${escapeHtml(chat.title)}</div>
            <div class="chat-item-time">${formatDate(chat.updated_at)}</div>
        </div>
    `).join('');
    
    // Добавляем обработчики кликов
    container.querySelectorAll('.chat-item').forEach(item => {
        item.addEventListener('click', () => {
            const chatId = parseInt(item.dataset.chatId);
            const type = item.dataset.type;
            selectChat(chatId, type);
        });
    });
}

function renderGroupsList() {
    const container = document.getElementById('groups-list');
    if (!container) return;
    
    container.innerHTML = state.groups.map(group => `
        <div class="group-item ${state.currentChat?.id === group.id && state.currentChatType === 'group' ? 'active' : ''}" 
             data-group-id="${group.id}">
            <div class="group-item-title">${escapeHtml(group.name)}</div>
        </div>
    `).join('');
    
    container.querySelectorAll('.group-item').forEach(item => {
        item.addEventListener('click', () => {
            const groupId = parseInt(item.dataset.groupId);
            selectChat(groupId, 'group');
        });
    });
}

// ==================== ВЫБОР ЧАТА ====================
async function selectChat(chatId, type) {
    state.currentChatType = type;
    
    try {
        let data;
        if (type === 'personal') {
            data = await apiRequest(`/api/chat/personal/${chatId}`);
            state.currentChat = data.chat;
        } else {
            data = await apiRequest(`/api/group/${chatId}`);
            state.currentChat = data.group;
        }
        
        // Обновляем заголовок
        const titleEl = document.getElementById('current-chat-title');
        if (titleEl) {
            titleEl.textContent = type === 'personal' ? state.currentChat.title : state.currentChat.name;
        }
        
        // Рендерим сообщения
        renderMessages(data.messages || []);
        
        // Обновляем активный элемент в списке
        updateActiveChatItem(chatId, type);
        
        // Показываем правую панель для групп
        const rightPanel = document.getElementById('right-panel');
        if (type === 'group' && data.members) {
            if (rightPanel) rightPanel.classList.remove('hidden');
            renderMembers(data.members);
        } else {
            if (rightPanel) rightPanel.classList.add('hidden');
        }
        
    } catch (error) {
        console.error('Ошибка загрузки чата:', error);
        showMessage('ai', `Ошибка: ${error.message}`);
    }
}

function updateActiveChatItem(chatId, type) {
    document.querySelectorAll('.chat-item, .group-item').forEach(item => {
        item.classList.remove('active');
    });
    
    const selector = type === 'personal' 
        ? `.chat-item[data-chat-id="${chatId}"]`
        : `.group-item[data-group-id="${chatId}"]`;
    
    const activeItem = document.querySelector(selector);
    if (activeItem) {
        activeItem.classList.add('active');
    }
}

function renderMembers(members) {
    const container = document.getElementById('members-list');
    if (!container) return;
    
    // ИСПРАВЛЕНО: member.username -> member.login
    container.innerHTML = members.map(member => `
        <div class="member-item">
            <div class="member-avatar">${(member.login || 'U').charAt(0).toUpperCase()}</div>
            <span>${escapeHtml(member.login)}</span>
        </div>
    `).join('');
}

// ==================== РЕНДЕРИНГ СООБЩЕНИЙ ====================
function renderMessages(messages) {
    const container = document.getElementById('messages-container');
    if (!container) return;
    
    container.innerHTML = messages.map(msg => createMessageHTML(msg)).join('');
    scrollToBottom();
}

function createMessageHTML(msg) {
    const isUser = msg.sender_type === 'client';
    const avatar = isUser ? 'U' : 'AI';
    
    return `
        <div class="message ${isUser ? 'user' : 'ai'}">
            <div class="message-avatar">${avatar}</div>
            <div>
                <div class="message-content">${escapeHtml(msg.content)}</div>
                <div class="message-time">${formatDate(msg.created_at)}</div>
            </div>
        </div>
    `;
}

function showMessage(senderType, content) {
    const container = document.getElementById('messages-container');
    if (!container) return;
    
    // Удаляем welcome message если есть
    const welcome = container.querySelector('.welcome-message');
    if (welcome) welcome.remove();
    
    const msg = {
        sender_type: senderType,
        content: content,
        created_at: new Date().toISOString()
    };
    
    container.insertAdjacentHTML('beforeend', createMessageHTML(msg));
    scrollToBottom();
}

function scrollToBottom() {
    const container = document.getElementById('messages-container');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

// ==================== ОТПРАВКА СООБЩЕНИЙ ====================
async function sendMessage() {
    const input = document.getElementById('message-input');
    const content = input.value.trim();
    
    if (!content || !state.currentChat) return;
    
    try {
        // Показываем сообщение пользователя
        showMessage('client', content);
        input.value = '';
        
        // Отправляем на сервер
        const data = {
            content: content,
            personal_chat_id: state.currentChatType === 'personal' ? state.currentChat.id : null,
            group_id: state.currentChatType === 'group' ? state.currentChat.id : null
        };
        
        const result = await apiRequest('/api/chat/send', 'POST', data);
        
        // Показываем ответ ИИ
        if (result.ai_message) {
            showMessage('ai', result.ai_message.content);
        }
        
    } catch (error) {
        console.error('Ошибка отправки:', error);
        showMessage('ai', `Ошибка: ${error.message}`);
    }
}

// ==================== РЕЖИМЫ РАБОТЫ ====================
function setMode(mode) {
    state.currentMode = mode;
    
    // Обновляем кнопки режимов
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    
    // Показываем нужный контейнер ввода
    document.querySelectorAll('.input-container').forEach(container => {
        container.classList.add('hidden');
    });
    
    const activeContainer = document.getElementById(`${mode}-input-container`);
    if (activeContainer) {
        activeContainer.classList.remove('hidden');
    }
    
    // Показываем/скрываем кнопку наблюдателя для личных чатов
    const observerBtn = document.getElementById('observer-mode-btn');
    if (observerBtn) {
        observerBtn.style.display = state.currentChatType === 'group' ? 'inline-block' : 'none';
    }
}

// ==================== ЗАГРУЗКА ИЗОБРАЖЕНИЙ ====================
async function uploadImage() {
    const input = document.getElementById('image-file');
    const file = input.files[0];
    
    if (!file || !state.currentChat) {
        alert('Выберите изображение и чат');
        return;
    }
    
    try {
        showMessage('client', `📷 Загрузка изображения: ${file.name}`);
        
        const result = await apiUpload('/api/upload/image', file);
        
        // Показываем статус
        showMessage('ai', `✅ Анализ запущен. ID задачи: ${result.task_id}`);
        
        // Очищаем input
        input.value = '';
        
        // В реальном приложении здесь был бы polling статуса задачи
        setTimeout(async () => {
            // Эмуляция получения результата
            showMessage('ai', '🖼️ Результат анализа изображения будет доступен после завершения фоновой задачи.');
        }, 2000);
        
    } catch (error) {
        console.error('Ошибка загрузки:', error);
        showMessage('ai', `Ошибка: ${error.message}`);
    }
}

// ==================== ЗАГРУЗКА АУДИО ====================
async function uploadAudio() {
    const input = document.getElementById('audio-file');
    const file = input.files[0];
    
    if (!file || !state.currentChat) {
        alert('Выберите аудиофайл и чат');
        return;
    }
    
    try {
        showMessage('client', `🎤 Загрузка аудио: ${file.name}`);
        
        const result = await apiUpload('/api/upload/audio', file);
        
        showMessage('ai', `✅ Транскрибация запущена. ID задачи: ${result.task_id}`);
        
        input.value = '';
        
        setTimeout(async () => {
            showMessage('ai', '🎤 Результат транскрибации будет доступен после подключения Whisper API.');
        }, 2000);
        
    } catch (error) {
        console.error('Ошибка загрузки:', error);
        showMessage('ai', `Ошибка: ${error.message}`);
    }
}

// ==================== АНАЛИЗ НАБЛЮДАТЕЛЕМ ====================
async function analyzeWithObserver() {
    if (!state.currentChat || state.currentChatType !== 'group') {
        alert('Режим наблюдателя доступен только в групповых чатах');
        return;
    }
    
    const roleSelect = document.getElementById('observer-role');
    const typeSelect = document.getElementById('observer-type');
    
    const role = roleSelect ? roleSelect.value : 'Ты аналитик.';
    const analysisType = typeSelect ? typeSelect.value : 'quick';
    
    try {
        showMessage('ai', `👁️ Запуск анализа в роли "${role}"...`);
        
        const result = await apiRequest('/api/group/observe', 'POST', {
            group_id: state.currentChat.id,
            role_prompt: role,
            analysis_type: analysisType
        });
        
        showMessage('ai', `📊 Анализ завершен. Проанализировано сообщений: ${result.messages_analyzed}\n\n${result.analysis}`);
        
    } catch (error) {
        console.error('Ошибка анализа:', error);
        showMessage('ai', `Ошибка: ${error.message}`);
    }
}

// ==================== СОЗДАНИЕ НОВОГО ЧАТА ====================
async function createNewChat() {
    try {
        const result = await apiRequest('/api/chat/personal/create', 'POST', {
            title: 'Новый чат'
        });
        
        // Добавляем в список
        state.chats.unshift({
            id: result.id,
            title: result.title,
            updated_at: result.created_at
        });
        
        renderChatsList();
        selectChat(result.id, 'personal');
        
    } catch (error) {
        console.error('Ошибка создания чата:', error);
        alert(error.message);
    }
}

// ==================== СОЗДАНИЕ ГРУППЫ ====================
async function createGroup() {
    const input = document.getElementById('new-group-name');
    if (!input) return;
    
    const name = input.value.trim();
    
    if (!name) {
        alert('Введите название группы');
        return;
    }
    
    try {
        const result = await apiRequest('/api/group/create', 'POST', {
            name: name,
            description: ''
        });
        
        state.groups.unshift({
            id: result.id,
            name: result.name
        });
        
        renderGroupsList();
        selectChat(result.id, 'group');
        
        input.value = '';
        
    } catch (error) {
        console.error('Ошибка создания группы:', error);
        alert(error.message);
    }
}

// ==================== УТИЛИТЫ ====================
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}

// ==================== ИНИЦИАЛИЗАЦИЯ ====================
document.addEventListener('DOMContentLoaded', () => {
    // Инициализация авторизации
    initAuth();
    
    // Проверка сессии
    // Если мы уже на странице приложения (не логин), пробуем получить данные
    const appContainer = document.getElementById('app-container');
    if (appContainer) {
        apiRequest('/api/auth/me')
            .then(user => {
                state.currentUser = user;
                showApp();
                loadChats();
            })
            .catch(() => {
                // Если не удалось получить пользователя, показываем окно входа
                // Но так как у нас SPA внутри index.html, просто ничего не делаем или показываем модалку
                showAuth();
            });
    }
    
    // Кнопка нового чата
    const newChatBtn = document.getElementById('new-chat-btn');
    if (newChatBtn) {
        newChatBtn.addEventListener('click', createNewChat);
    }
    
    // Создание группы
    const createGroupBtn = document.getElementById('create-group-btn');
    if (createGroupBtn) {
        createGroupBtn.addEventListener('click', createGroup);
    }
    
    // Отправка сообщения
    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }
    
    const messageInput = document.getElementById('message-input');
    if (messageInput) {
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
    
    // Переключение режимов
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            setMode(btn.dataset.mode);
        });
    });
    
    // Загрузка изображений
    const uploadImageBtn = document.getElementById('upload-image-btn');
    if (uploadImageBtn) {
        uploadImageBtn.addEventListener('click', uploadImage);
    }
    
    // Загрузка аудио
    const uploadAudioBtn = document.getElementById('upload-audio-btn');
    if (uploadAudioBtn) {
        uploadAudioBtn.addEventListener('click', uploadAudio);
    }
    
    // Анализ наблюдателем
    const analyzeBtn = document.getElementById('analyze-btn');
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', analyzeWithObserver);
    }
    
    // Начальный режим
    setMode('chat');
});