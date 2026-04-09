/**
 * Gemma Hub - Frontend JavaScript
 * Обработка авторизации, чатов и всех режимов работы
 * Расширенный функционал: мультимодальность, аудио-лаборатория, ИИ-наблюдатель
 */

// ==================== ГЛОБАЛЬНОЕ СОСТОЯНИЕ ====================
const state = {
    currentUser: null,
    currentChat: null,
    currentChatType: 'personal', // 'personal' или 'group'
    currentMode: 'chat', // 'chat', 'image', 'audio', 'observer'
    chats: [],
    groups: [],
    selectedImages: [], // Для хранения выбранных изображений
    audioProcessing: false
};

// Роли наблюдателя с системными промтами
const OBSERVER_ROLES = {
    'Критик': 'Ты критический аналитик. Твоя задача — находить логические ошибки, противоречия и слабые аргументы в диалоге. Будь объективен, но строг.',
    'Саммаризатор': 'Ты эксперт по саммаризации. Твоя задача — создавать краткие, информативные резюме диалога, выделяя ключевые моменты и решения.',
    'Эксперт по фактам': 'Ты эксперт по проверке фактов. Твоя задача — анализировать утверждения участников на достоверность, указывать на возможные неточности и предоставлять корректную информацию.',
    'Психолог': 'Ты психолог-аналитик. Твоя задача — оценивать эмоциональный тон общения, выявлять паттерны поведения, конфликты и давать рекомендации по улучшению коммуникации.',
    'Custom': '' // Пользовательский промт
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

async function apiUpload(endpoint, files, additionalData = {}) {
    const formData = new FormData();
    
    // Поддержка множественных файлов
    if (files instanceof FileList || Array.isArray(files)) {
        const fileArray = files instanceof FileList ? Array.from(files) : files;
        fileArray.forEach((file, index) => {
            formData.append('files', file);
        });
    } else {
        formData.append('file', files);
    }
    
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
                // Показываем приложение БЕЗ перезагрузки
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
                // Показываем уведомление об успехе
                showToast('Регистрация успешна! Теперь войдите.');
                // Переключаем на форму входа
                switchToLoginTab();
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

// ==================== УТИЛИТЫ ====================

function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Показываем
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Скрываем через 3 секунды
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function switchToLoginTab() {
    const loginTab = document.querySelector('.tab-btn[data-tab="login"]');
    if (loginTab) {
        loginTab.click();
    }
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
    
    // Обработка переключения на кастомный промт в режиме наблюдателя
    setupObserverCustomPromptHandlers();
}

// Обработчики для кастомного промта наблюдателя
function setupObserverCustomPromptHandlers() {
    const roleSelect = document.getElementById('observer-role');
    const customInput = document.getElementById('observer-custom-prompt');
    const roleSelectQuick = document.getElementById('observer-role-quick');
    const customInputQuick = document.getElementById('observer-custom-prompt-quick');
    
    if (roleSelect && customInput) {
        roleSelect.addEventListener('change', () => {
            if (roleSelect.value === 'Custom') {
                customInput.classList.remove('hidden');
            } else {
                customInput.classList.add('hidden');
            }
        });
    }
    
    if (roleSelectQuick && customInputQuick) {
        roleSelectQuick.addEventListener('change', () => {
            if (roleSelectQuick.value === 'Custom') {
                customInputQuick.classList.remove('hidden');
            } else {
                customInputQuick.classList.add('hidden');
            }
        });
    }
}

// ==================== МУЛЬТИМОДАЛЬНОСТЬ: РАБОТА С НЕСКОЛЬКИМИ ИЗОБРАЖЕНИЯМИ ====================

// Обработка выбора файлов изображений
function handleImageFileSelect(event) {
    const input = event.target;
    const files = Array.from(input.files);
    const previewContainer = document.getElementById('image-preview-container');
    
    if (!previewContainer) return;
    
    previewContainer.innerHTML = '';
    state.selectedImages = [];
    
    files.forEach((file, index) => {
        if (!file.type.startsWith('image/')) return;
        
        state.selectedImages.push(file);
        
        const reader = new FileReader();
        reader.onload = (e) => {
            const preview = document.createElement('div');
            preview.className = 'image-preview';
            preview.innerHTML = `
                <img src="${e.target.result}" alt="Preview">
                <button type="button" class="remove-btn" data-index="${index}">×</button>
            `;
            previewContainer.appendChild(preview);
            
            // Обработчик удаления
            preview.querySelector('.remove-btn').addEventListener('click', () => {
                state.selectedImages.splice(index, 1);
                preview.remove();
            });
        };
        reader.readAsDataURL(file);
    });
}

// Загрузка и анализ нескольких изображений
async function uploadMultipleImages() {
    const promptInput = document.getElementById('image-prompt-input');
    const prompt = promptInput ? promptInput.value.trim() : 'Опишите эти изображения подробно.';
    
    if (state.selectedImages.length === 0 || !state.currentChat) {
        alert('Выберите хотя бы одно изображение');
        return;
    }
    
    try {
        showMessage('client', `📷 Загрузка ${state.selectedImages.length} изображения(ий)...`);
        
        // Отправляем файлы на сервер
        const result = await apiUpload('/api/chat/vision', state.selectedImages, {
            prompt: prompt,
            chat_type: state.currentChatType,
            chat_id: state.currentChat.id
        });
        
        // Показываем результат
        if (result.analysis) {
            showMessage('ai', `🖼️ Анализ ${state.selectedImages.length} изображения(ий):\n\n${result.analysis}`);
        } else {
            showMessage('ai', `✅ Анализ запущен. ID задачи: ${result.task_id}`);
        }
        
        // Очищаем
        state.selectedImages = [];
        const input = document.getElementById('image-file');
        if (input) input.value = '';
        const previewContainer = document.getElementById('image-preview-container');
        if (previewContainer) previewContainer.innerHTML = '';
        if (promptInput) promptInput.value = '';
        
    } catch (error) {
        console.error('Ошибка загрузки изображений:', error);
        showMessage('ai', `Ошибка: ${error.message}`);
    }
}

// ==================== АУДИО-ЛАБОРАТОРИЯ ====================

// Обработка выбора аудиофайла
function handleAudioFileSelect(event) {
    const input = event.target;
    const fileInfo = document.getElementById('audio-file-info');
    
    if (!fileInfo || !input.files[0]) return;
    
    const file = input.files[0];
    const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
    fileInfo.textContent = `🎵 ${file.name} (${sizeMB} MB)`;
}

// Транскрибация и анализ аудио
async function transcribeAndAnalyzeAudio() {
    const input = document.getElementById('audio-file');
    const file = input ? input.files[0] : null;
    
    if (!file || !state.currentChat) {
        alert('Выберите аудиофайл');
        return;
    }
    
    if (state.audioProcessing) {
        alert('Обработка уже идет...');
        return;
    }
    
    try {
        state.audioProcessing = true;
        showMessage('client', `🎤 Загрузка аудио для обработки: ${file.name}`);
        
        // Отправляем на сервер
        const result = await apiUpload('/api/audio/transcribe-analyze', file, {
            chat_id: state.currentChat.id
        });
        
        // Показываем результаты
        const resultsContainer = document.getElementById('audio-results-container');
        const transcriptionEl = document.getElementById('audio-transcription');
        const analysisEl = document.getElementById('audio-analysis');
        
        if (resultsContainer && transcriptionEl && analysisEl) {
            resultsContainer.classList.remove('hidden');
            transcriptionEl.textContent = result.transcription || 'Транскрибация недоступна';
            analysisEl.textContent = result.analysis || 'Анализ недоступен';
            
            showMessage('ai', '✅ Аудио обработано. Результаты ниже.');
        }
        
        // Очищаем input
        if (input) input.value = '';
        const fileInfo = document.getElementById('audio-file-info');
        if (fileInfo) fileInfo.textContent = '';
        
    } catch (error) {
        console.error('Ошибка обработки аудио:', error);
        showMessage('ai', `Ошибка: ${error.message}`);
    } finally {
        state.audioProcessing = false;
    }
}

// ==================== ЗАГРУЗКА ИЗОБРАЖЕНИЙ (старая функция, оставлена для совместимости) ====================
async function uploadImage() {
    // Вызываем новую функцию для множественных изображений
    uploadMultipleImages();
}

// ==================== ЗАГРУЗКА АУДИО (старая функция, обновлена) ====================
async function uploadAudio() {
    // Вызываем новую функцию транскрибации с анализом
    transcribeAndAnalyzeAudio();
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
    const customPromptInput = document.getElementById('observer-custom-prompt');
    
    let role = roleSelect ? roleSelect.value : 'Ты аналитик.';
    
    // Если выбран Custom, используем кастомный промт
    if (role === 'Custom' && customPromptInput) {
        role = customPromptInput.value.trim() || 'Ты аналитик.';
    }
    
    const analysisType = typeSelect ? typeSelect.value : 'quick';
    
    try {
        showMessage('ai', `👁️ Запуск анализа в роли "${role}"...`);
        
        const result = await apiRequest('/api/group/observe', 'POST', {
            group_id: state.currentChat.id,
            role_prompt: role,
            analysis_type: analysisType
        });
        
        // Выводим результат в панель наблюдателя
        const resultsContainer = document.getElementById('observer-results-container');
        const resultEl = document.getElementById('observer-analysis-result');
        
        if (resultsContainer && resultEl) {
            resultsContainer.classList.remove('hidden');
            resultEl.textContent = result.analysis;
        }
        
        showMessage('ai', `📊 Анализ завершен. Проанализировано сообщений: ${result.messages_analyzed}`);
        
    } catch (error) {
        console.error('Ошибка анализа:', error);
        showMessage('ai', `Ошибка: ${error.message}`);
    }
}

// Быстрый анализ из правой панели (для группового чата)
async function analyzeWithObserverQuick() {
    if (!state.currentChat || state.currentChatType !== 'group') {
        alert('Режим наблюдателя доступен только в групповых чатах');
        return;
    }
    
    const roleSelect = document.getElementById('observer-role-quick');
    const customPromptInput = document.getElementById('observer-custom-prompt-quick');
    const resultEl = document.getElementById('observer-quick-result');
    
    let role = roleSelect ? roleSelect.value : 'Критик';
    
    // Если выбран Custom, используем кастомный промт
    if (role === 'Custom' && customPromptInput) {
        role = customPromptInput.value.trim() || 'Ты аналитик.';
    }
    
    try {
        if (resultEl) {
            resultEl.classList.remove('hidden');
            resultEl.textContent = '⏳ Анализ...';
        }
        
        const result = await apiRequest('/api/group/observe', 'POST', {
            group_id: state.currentChat.id,
            role_prompt: role,
            analysis_type: 'quick'
        });
        
        if (resultEl) {
            resultEl.textContent = result.analysis;
        }
        
    } catch (error) {
        console.error('Ошибка быстрого анализа:', error);
        if (resultEl) {
            resultEl.textContent = `Ошибка: ${error.message}`;
        }
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
    
    // Обработчик выбора файлов изображений
    const imageFileInput = document.getElementById('image-file');
    if (imageFileInput) {
        imageFileInput.addEventListener('change', handleImageFileSelect);
    }

    // Загрузка аудио
    const uploadAudioBtn = document.getElementById('upload-audio-btn');
    if (uploadAudioBtn) {
        uploadAudioBtn.addEventListener('click', uploadAudio);
    }
    
    // Обработчик выбора аудиофайла
    const audioFileInput = document.getElementById('audio-file');
    if (audioFileInput) {
        audioFileInput.addEventListener('change', handleAudioFileSelect);
    }

    // Анализ наблюдателем
    const analyzeBtn = document.getElementById('analyze-btn');
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', analyzeWithObserver);
    }
    
    // Быстрый анализ из правой панели
    const analyzeQuickBtn = document.getElementById('analyze-quick-btn');
    if (analyzeQuickBtn) {
        analyzeQuickBtn.addEventListener('click', analyzeWithObserverQuick);
    }

    // Начальный режим
    setMode('chat');
});

// ==================== МОБИЛЬНОЕ МЕНЮ ====================
const hamburgerMenu = document.getElementById('hamburger-menu');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebar-overlay');

if (hamburgerMenu && sidebar) {
    hamburgerMenu.addEventListener('click', () => {
        sidebar.classList.toggle('open');
        if (sidebarOverlay) sidebarOverlay.classList.toggle('active');
    });
}

if (sidebarOverlay && sidebar) {
    sidebarOverlay.addEventListener('click', () => {
        sidebar.classList.remove('open');
        sidebarOverlay.classList.remove('active');
    });
}

// ==================== AI TOGGLE ====================
const aiToggle = document.getElementById('ai-enabled-toggle');
let currentAiEnabled = true;

if (aiToggle) {
    aiToggle.addEventListener('change', async () => {
        if (!state.currentChat) return;
        
        try {
            const chatType = state.currentChatType === 'personal' ? 'personal' : 'group';
            const result = await apiRequest('/api/chat/toggle_ai', 'POST', {
                chat_type: chatType,
                chat_id: state.currentChat.id
            });
            currentAiEnabled = result.ai_enabled;
            aiToggle.checked = currentAiEnabled;
            showToast(currentAiEnabled ? 'ИИ-ассистент включен' : 'ИИ-ассистент отключен');
        } catch (error) {
            console.error('Ошибка переключения ИИ:', error);
            showToast('Ошибка переключения ИИ');
        }
    });
}

// ==================== ПРИГЛАШЕНИЯ В ГРУППЫ ====================
const inviteUserBtn = document.getElementById('invite-user-btn');
if (inviteUserBtn) {
    inviteUserBtn.addEventListener('click', async () => {
        const loginInput = document.getElementById('invite-login-input');
        const login = loginInput.value.trim();
        
        if (!login || !state.currentChat || state.currentChatType !== 'group') {
            showToast('Выберите группу и введите логин');
            return;
        }
        
        try {
            await apiRequest('/api/group/invite', 'POST', {
                group_id: state.currentChat.id,
                login: login
            });
            showToast(`Приглашение отправлено пользователю ${login}`);
            loginInput.value = '';
        } catch (error) {
            showToast(error.message || 'Ошибка отправки приглашения');
        }
    });
}

// Загрузка входящих приглашений
async function loadInvitations() {
    try {
        const data = await apiRequest('/api/invitations');
        renderInvitations(data.invitations || []);
    } catch (error) {
        console.error('Ошибка загрузки приглашений:', error);
    }
}

function renderInvitations(invitations) {
    const container = document.getElementById('invitations-list');
    if (!container) return;
    
    if (invitations.length === 0) {
        container.innerHTML = '<div class="hint">Нет входящих приглашений</div>';
        return;
    }
    
    container.innerHTML = invitations.map(inv => `
        <div class="member-item" data-invitation-id="${inv.id}">
            <div class="member-avatar">${(inv.group_name || 'G').charAt(0).toUpperCase()}</div>
            <span>${escapeHtml(inv.group_name)}</span>
            <button class="btn btn-sm btn-primary accept-invite-btn" data-group-id="${inv.group_id}">Принять</button>
        </div>
    `).join('');
    
    container.querySelectorAll('.accept-invite-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const groupId = parseInt(btn.dataset.groupId);
            try {
                await apiRequest('/api/invitations/accept', 'POST', { group_id: groupId });
                showToast('Приглашение принято!');
                loadInvitations();
                loadChats(); // Обновить список групп
            } catch (error) {
                showToast(error.message || 'Ошибка принятия приглашения');
            }
        });
    });
}

// ==================== СТАТУС ПОЛЬЗОВАТЕЛЕЙ ====================
async function loadUsersStatus() {
    try {
        const data = await apiRequest('/api/users/list');
        // Сохраняем статусы для использования при рендеринге участников
        state.usersStatus = data.users || [];
    } catch (error) {
        console.error('Ошибка загрузки статусов:', error);
    }
}

function isUserOnline(login) {
    const user = state.usersStatus?.find(u => u.login === login);
    return user?.is_online || false;
}

function renderMembersWithStatus(members) {
    const container = document.getElementById('members-list');
    if (!container) return;
    
    container.innerHTML = members.map(member => {
        const online = isUserOnline(member.login);
        return `
            <div class="member-item">
                <span class="${online ? 'online-indicator' : 'offline-indicator'}"></span>
                <div class="member-avatar">${(member.login || 'U').charAt(0).toUpperCase()}</div>
                <span>${escapeHtml(member.login)} ${online ? '(онлайн)' : ''}</span>
            </div>
        `;
    }).join('');
}

// Переопределяем renderMembers для отображения статуса
const originalRenderMembers = renderMembers;
renderMembers = function(members) {
    renderMembersWithStatus(members);
};

// ==================== НАБЛЮДАТЕЛЬ ДЛЯ ЛИЧНЫХ ЧАТОВ ====================
async function analyzePersonalChatWithObserver() {
    if (!state.currentChat || state.currentChatType !== 'personal') {
        showToast('Выберите личный чат для анализа');
        return;
    }
    
    const roleSelect = document.getElementById('observer-role');
    const typeSelect = document.getElementById('observer-type');
    const customPromptInput = document.getElementById('observer-custom-prompt');
    
    let rolePrompt = OBSERVER_ROLES[roleSelect.value] || 'Проанализируй диалог.';
    if (roleSelect.value === 'Custom') {
        rolePrompt = customPromptInput.value || 'Проанализируй диалог.';
    }
    
    const analysisType = typeSelect.value;
    
    try {
        const result = await apiRequest('/api/chat/observe', 'POST', {
            personal_chat_id: state.currentChat.id,
            role_prompt: rolePrompt,
            analysis_type: analysisType
        });
        
        const resultsContainer = document.getElementById('observer-results-container');
        const resultText = document.getElementById('observer-analysis-result');
        
        if (resultsContainer && resultText) {
            resultsContainer.classList.remove('hidden');
            resultText.textContent = result.result;
        }
        
        showToast('Анализ завершен');
    } catch (error) {
        showToast(error.message || 'Ошибка анализа');
    }
}

// Модифицируем analyzeWithObserver для поддержки личных чатов
const originalAnalyzeWithObserver = window.analyzeWithObserver || null;
window.analyzeWithObserver = async function() {
    if (state.currentChatType === 'personal') {
        await analyzePersonalChatWithObserver();
    } else if (state.currentChatType === 'group') {
        if (originalAnalyzeWithObserver) {
            await originalAnalyzeWithObserver();
        }
    } else {
        showToast('Выберите чат для анализа');
    }
};

// ==================== ЗАГРУЗКА ПРИ ЗАПУСКЕ ====================
// Переопределяем loadChats для загрузки статусов и приглашений
const originalLoadChats = loadChats;
loadChats = async function() {
    await originalLoadChats();
    await loadUsersStatus();
    await loadInvitations();
};
