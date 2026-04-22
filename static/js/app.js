// ========== ИМПОРТЫ МОДУЛЕЙ ==========
import { renderSingleMessage, renderMessages, renderList, showTypingIndicator, hideTypingIndicator, showToast, clearModerationIndicators, updateModerationIndicators } from '/static/js/modules/ui.js';
import { enableMobileTypingMode, disableMobileTypingMode, setMessageInputEl, handleMobileResize } from '/static/js/modules/mobile.js';
import { loadModerationPrompts, analyzeGroupMessages, displayModerationSuggestions, applyModerationAction, applySelectedModeration, undoLastModeration } from '/static/js/modules/moderation.js';
import { loadPreModerationSettings, togglePreModeration, saveGroupTopic, savePsychologistPrompt, loadPreModerationPrompts, savePreModerationPrompt, checkMessageBeforeSend, handleMessageCheckResult, showImprovementToast, showModerationDialog } from '/static/js/modules/premoderation.js';
import { loadUsers as loadUsersModule, checkAdminRole } from '/static/js/modules/users.js';
import { initNotifications, notifyNewMessage, requestNotificationPermission, showNotification  } from '/static/js/modules/notifications.js';

console.log('🧪 Module test: premoderation.js loaded?', typeof loadPreModerationSettings);
if (typeof loadPreModerationSettings !== 'function') {
    console.error('❌ Функция не импортирована. Проверь: 1) type="module" 2) export в premoderation.js 3) путь к файлу');
}
// ========== СОСТОЯНИЕ ==========
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

let activeModerationMessageIds = [];
let initPromise = null;
let pendingMessageGroupId = null;
let pendingMessageCheck = null;
let pendingMessageContent = null;
let pendingMessageCallback = null;

// ========== ИНИЦИАЛИЗАЦИЯ ==========
document.addEventListener('DOMContentLoaded', () => {
    console.log('=== DOM CONTENT LOADED ===');
    if (!initPromise) {
        initPromise = initApp();
    }
});

async function initApp() {
    console.log('=== INIT APP START ===');
    
    try {
        const response = await fetch('/api/auth/me');
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            throw new Error('Not authenticated');
        }
        
        const user = await response.json();
        console.log('User data received:', user);
        
        state.currentUser = {
            ...user,
            id: user.client_id,
            client_id: user.client_id
        };
        console.log('✅ User loaded:', state.currentUser);
        
        showApp();
        console.log('=== INIT APP FINISHED ===');
        return true;
        
    } catch (e) { 
        console.error('❌ Init error:', e);
        window.location.href = '/login';
        return false;
    }
}

async function showApp() {
    if (state.appInitialized) {
        console.log('App already initialized, skipping');
        return;
    }
    state.appInitialized = true;
    
    console.log('=== SHOW APP START ===');
    
    const userDisplay = document.getElementById('user-display');
    const userAvatar = document.getElementById('user-avatar');
    const appContainer = document.getElementById('app-container');
    
    if (userDisplay) userDisplay.textContent = state.currentUser.login;
    if (userAvatar) userAvatar.textContent = state.currentUser.login[0].toUpperCase();
    if (appContainer) appContainer.style.display = 'flex';
    
    console.log('User display updated');
    
    await loadUserGenderToSelect();
    
    initSocket();
    loadChats();
    checkAIAvailability();
    loadModels();
    setupEventListeners();
    loadModerationPrompts(apiRequest, escapeHtml);
    setupImagePreview();
    setupImageUpload();
    initNotifications();

    console.log('=== SHOW APP FINISHED ===');
}

// ========== WEBSOCKET ==========
function initSocket() {
    console.log('=== INIT SOCKET ===');
    try {
        state.socket = io();
        
        state.socket.on('connect', async () => {
            console.log('✅ WebSocket connected');
            await loadUsersModule(apiRequest, escapeHtml, showToast, state, loadChats);
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
            
            // Объявляем переменную ДО использования
            let isCurrentChat = false;
            
            if (state.currentChat) {
                if (state.currentChatType === 'group' && data.group_id) {
                    isCurrentChat = state.currentChat.id === data.group_id;
                } else if (state.currentChatType === 'personal' && data.personal_chat_id) {
                    isCurrentChat = state.currentChat.id === data.personal_chat_id;
                }
            }
            
            // Уведомление (если чат не активен и сообщение не от текущего пользователя)
            if (!isCurrentChat && data.sender_id !== state.currentUser?.id) {
                if (typeof notifyNewMessage === 'function') {
                    notifyNewMessage(data.sender_name, data.content, data.group_id || data.personal_chat_id, state.currentChatType);
                }
            }
            
            if (isCurrentChat) {
                const existingMsg = document.querySelector(`.message[data-msg-id="${data.id}"]`);
                if (!existingMsg) {
                    renderSingleMessage(data, state, activeModerationMessageIds, showMessageMenu, escapeHtml);
                }
            } else {
                const chatName = data.chat_name || (data.group_id ? 'группе' : 'личном чате');
                showToast(`🔔 Новое сообщение в ${chatName}`);
                document.title = '🔔 Новое сообщение!';
                setTimeout(() => { document.title = state.originalTitle; }, 10000);
            }
        });
        
        state.socket.on('user_joined', async (data) => {
            console.log('👤 User joined:', data);
            await loadUsersModule(apiRequest, escapeHtml, showToast, state, loadChats);
            if (state.currentChatType === 'group' && state.currentChat?.id === data.group_id) {
                updateMembersList();
            }
        });
        
        state.socket.on('user_left', async (data) => {
            console.log('👋 User left:', data);
            await loadUsersModule(apiRequest, escapeHtml, showToast, state, loadChats);
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
        
        state.socket.on('message_moderated', (data) => {
            console.log('📢 Moderation update received:', data);
            const msgElement = document.querySelector(`.message[data-msg-id="${data.message_id}"]`);
            if (msgElement) {
                if (data.action === 'delete') {
                    msgElement.style.opacity = '0.5';
                    const contentElement = msgElement.querySelector('.msg-content');
                    if (contentElement) contentElement.innerHTML = '<em>Сообщение удалено модератором</em>';
                    const menuBtn = msgElement.querySelector('.message-menu-btn');
                    if (menuBtn) menuBtn.remove();
                } else if (data.action === 'edit' && data.new_content) {
                    const contentElement = msgElement.querySelector('.msg-content');
                    if (contentElement) contentElement.innerHTML = escapeHtml(data.new_content);
                    let editedSpan = msgElement.querySelector('.msg-edited');
                    if (!editedSpan) {
                        const timeElement = msgElement.querySelector('.msg-time');
                        if (timeElement) {
                            editedSpan = document.createElement('span');
                            editedSpan.className = 'msg-edited';
                            editedSpan.style.cssText = 'font-size:0.65rem; opacity:0.6; margin-left:8px;';
                            editedSpan.textContent = '(изменено модератором)';
                            timeElement.appendChild(editedSpan);
                        }
                    }
                }
            }
            showToast(`🔔 Сообщение ${data.action === 'delete' ? 'удалено' : 'изменено'} модератором`);
        });
        
        state.socket.on('message_check_result', (data) => {
            console.log('📋 Message check result:', data);
            if (pendingMessageCheck === data.task_id && pendingMessageCallback) {
                pendingMessageCallback(data.result);
                pendingMessageCheck = null;
                pendingMessageCallback = null;
            }
        });
        
        state.socket.on('moderation_undone', (data) => {
            console.log('↩️ Moderation undone:', data);
            const msgElement = document.querySelector(`.message[data-msg-id="${data.message_id}"]`);
            if (msgElement && data.old_content) {
                msgElement.style.opacity = '1';
                const contentElement = msgElement.querySelector('.msg-content');
                if (contentElement) contentElement.innerHTML = escapeHtml(data.old_content);
            }
            showToast(`↩️ Действие модератора отменено`);
        });
    } catch (err) {
        console.error('Socket init error:', err);
    }
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

// ========== ЗАГРУЗКА ЧАТОВ ==========
async function loadChats() {
    try {
        const data = await apiRequest('/api/client/chats');
        console.log('📥 Loaded chats:', data);
        state.chats = data.personal_chats || [];
        state.groups = data.groups || [];
        renderList('chats-list', state.chats, 'personal', state, escapeHtml);
        renderList('groups-list', state.groups, 'group', state, escapeHtml);
        await loadUsersModule(apiRequest, escapeHtml, showToast, state, loadChats);
        loadInvitations();
    } catch (error) {
        console.error('❌ Error loading chats:', error);
    }
}

// ========== ВЫБОР ЧАТА ==========
async function selectChat(id, type) {
    stopMessagePolling();
    
    state.currentChatType = type;
    try {
        const data = await apiRequest(type === 'personal' ? `/api/chat/personal/${id}` : `/api/group/${id}`);
        state.currentChat = type === 'personal' ? data.chat : data.group;
        
        const titleElem = document.getElementById('current-chat-title');
        if (titleElem) titleElem.textContent = state.currentChat.title || state.currentChat.name;
        
        renderMessages(data.messages, state, activeModerationMessageIds, showMessageMenu, escapeHtml);
        
        if (type === 'group') {
            joinGroupRoom(id);
        } else {
            joinPersonalRoom(id);
        }
        
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('overlay');
        if (sidebar) sidebar.classList.remove('open');
        if (overlay) overlay.classList.remove('active');
        
        const membersSec = document.getElementById('members-section');
        if (type === 'group') {
            console.log('Calling loadPreModerationSettings for group', state.currentChat.id);
            console.log('=== Calling loadPreModerationSettings ===');
            console.log('state.currentChat:', state.currentChat);
            loadPreModerationSettings(state, showToast, loadPreModerationPrompts);
            if (membersSec) membersSec.classList.remove('hidden');
            if (data.members) {
                const membersList = document.getElementById('members-list');
                if (membersList) {
                    membersList.innerHTML = data.members.map(m => 
                        `<div class="member-item"><div class="avatar" style="width:25px;height:25px;font-size:0.7rem">${escapeHtml(m.login[0])}</div> ${escapeHtml(m.login)}</div>`
                    ).join('');
                }
            }
            loadInvitations();
            loadPreModerationSettings(state, showToast, loadPreModerationPrompts);
        } else {
            if (membersSec) membersSec.classList.add('hidden');
            const preModSection = document.getElementById('pre-moderation-section');
            if (preModSection) preModSection.style.display = 'none';
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
 


    // Если есть изображения - отправляем их с текстом
    if (selectedImages.length > 0) {
        inp.value = '';
        await sendImagesWithPrompt(txt);
        return;
    }
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
    
    const aiName = state.currentChat?.ai_name || 'Гемма';
    const isAiCall = txt.startsWith('@') || 
        txt.startsWith('/gemma') || 
        txt.startsWith('/ai') ||
        txt.toLowerCase().startsWith(aiName.toLowerCase());

    const preModToggle = document.getElementById('pre-moderation-toggle');
    const isPreModEnabled = preModToggle && preModToggle.checked && state.currentChatType === 'group';
    
    if (isPreModEnabled && !isAiCall) {
        inp.value = '';
        
        const result = await new Promise((resolve) => {
            checkMessageBeforeSend(txt, resolve, state, showToast, handleMessageCheckResult, showImprovementToast, showModerationDialog, escapeHtml);
        });
        
        if (result === 'cancel') {
            inp.value = txt;
            return;
        }
        
        const messageToSend = (result && typeof result === 'string') ? result : txt;
        await actualSendMessage(messageToSend);
        return;
    }
    
    inp.value = '';
    await actualSendMessage(txt);
}
async function sendImagesWithPrompt(prompt) {
    if (!state.currentChat) {
        alert('Выберите чат');
        return;
    }
    
    if (selectedImages.length === 0) {
        alert('Нет изображений для отправки');
        return;
    }
    
    // Проверяем тип файлов
    const hasPDF = selectedImages.some(f => f.type === 'application/pdf');
    const hasImages = selectedImages.some(f => f.type.startsWith('image/'));
    
    if (hasPDF && hasImages) {
        alert('Нельзя загружать PDF и изображения одновременно');
        return;
    }
    
    try {
        showTypingIndicator();
        
        const formData = new FormData();
        
        if (hasPDF) {
            // Отправляем только первый PDF (можно несколько, но API принимает один)
            formData.append('file', selectedImages[0]);
            formData.append('prompt', prompt || 'Извлеки весь текст и опиши содержимое страниц подробно.');
            formData.append('chat_type', state.currentChatType);
            formData.append('chat_id', state.currentChat.id);
            
            const response = await fetch('/api/upload/pdf', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.error || 'Ошибка анализа PDF');
            }
            
            showToast(`📄 PDF анализ запущен (${result.pages_count} страниц)`);
            
        } else {
            // Отправляем изображения
            selectedImages.forEach(file => {
                formData.append('files', file);
            });
            formData.append('prompt', prompt || 'Опишите эти изображения подробно.');
            formData.append('chat_type', state.currentChatType);
            formData.append('chat_id', state.currentChat.id);
            
            const response = await fetch('/api/chat/vision', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.error || 'Ошибка анализа');
            }
            
            showToast(`✅ Анализ ${selectedImages.length} изображения(ий) запущен`);
        }
        
        // Очищаем после отправки
        selectedImages = [];
        const previewContainer = document.getElementById('image-preview-container');
        if (previewContainer) {
            previewContainer.innerHTML = '';
            previewContainer.classList.add('hidden');
        }
        
        const messageInput = document.getElementById('message-input');
        if (messageInput) messageInput.value = '';
        
        // Закрываем бар действий
        const actionsBar = document.getElementById('actions-bar');
        const toggleBtn = document.getElementById('actions-toggle-btn');
        if (actionsBar) actionsBar.classList.add('hidden');
        if (toggleBtn) toggleBtn.classList.remove('rotated');
        
        // Переключаемся обратно в режим чата
        switchMode('chat');
        
    } catch (error) {
        console.error('Error:', error);
        alert('Ошибка при анализе: ' + error.message);
    } finally {
        hideTypingIndicator();
    }
}
// Показать индикатор AI модерации
function showAIModerationIndicator() {
    const indicator = document.getElementById('ai-moderation-indicator');
    if (indicator) {
        indicator.classList.remove('hidden');
    }
}

// Скрыть индикатор AI модерации
function hideAIModerationIndicator() {
    const indicator = document.getElementById('ai-moderation-indicator');
    if (indicator) {
        indicator.classList.add('hidden');
    }
}

async function actualSendMessage(messageText) {
    console.log('Actual sending message:', messageText);
    const aiName = state.currentChat.ai_name || 'Гемма';
    const mightTriggerAi = messageText.startsWith('@') || 
        messageText.startsWith('/gemma') || 
        messageText.startsWith('/ai') ||
        messageText.toLowerCase().startsWith(aiName.toLowerCase());
    
    if (mightTriggerAi) {
        showTypingIndicator();
    }

    try {
        const sent = sendMessageViaSocket(
            messageText,
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
                    `<div class="member-item"><div class="avatar" style="width:25px;height:25px;font-size:0.7rem">${escapeHtml(m.login[0])}</div> ${escapeHtml(m.login)}</div>`
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

function switchMode(mode) {
    document.querySelectorAll('.input-wrapper').forEach(el => el.classList.add('hidden'));
    const container = document.getElementById(`${mode}-input-container`);
    if (container) container.classList.remove('hidden');
    
    // Обновляем активную кнопку в баре
    document.querySelectorAll('.action-btn').forEach(btn => {
        if (btn.dataset.action === mode) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

// ========== ФУНКЦИИ ДЛЯ ИЗОБРАЖЕНИЙ ==========
let selectedImages = [];

function setupImagePreview() {
    const fileInput = document.getElementById('image-file');
    if (!fileInput) return;
    
    fileInput.onchange = (e) => {
        const files = Array.from(e.target.files);
        const previewContainer = document.getElementById('image-preview-container');
        if (!previewContainer) return;
        
        files.forEach(file => {
            selectedImages.push(file);
            const reader = new FileReader();
            reader.onload = (event) => {
                const previewItem = document.createElement('div');
                previewItem.className = 'image-preview-item';
                previewItem.innerHTML = `
                    <img src="${event.target.result}" alt="preview">
                    <button class="image-preview-remove" data-filename="${file.name}">✕</button>
                `;
                previewContainer.appendChild(previewItem);
                previewContainer.classList.remove('hidden');
                
                previewItem.querySelector('.image-preview-remove').onclick = () => {
                    const index = selectedImages.findIndex(f => f.name === file.name);
                    if (index !== -1) selectedImages.splice(index, 1);
                    previewItem.remove();
                    if (selectedImages.length === 0) {
                        previewContainer.classList.add('hidden');
                    }
                };
            };
            reader.readAsDataURL(file);
        });
        fileInput.value = '';
    };
}

function setupImageUpload() {
    const fileInput = document.getElementById('image-file');
    if (!fileInput) return;
    
    // Обработчик выбора файлов
    fileInput.onchange = (e) => {
        const files = Array.from(e.target.files);
        const previewContainer = document.getElementById('image-preview-container');
        if (!previewContainer) return;
        
        files.forEach(file => {
            selectedImages.push(file);
            const reader = new FileReader();
            reader.onload = (event) => {
                const previewItem = document.createElement('div');
                previewItem.className = 'image-preview-item';
                previewItem.innerHTML = `
                    <img src="${event.target.result}" alt="preview">
                    <button class="image-preview-remove" data-filename="${file.name}">✕</button>
                `;
                previewContainer.appendChild(previewItem);
                previewContainer.classList.remove('hidden');
                
                previewItem.querySelector('.image-preview-remove').onclick = () => {
                    const index = selectedImages.findIndex(f => f.name === file.name);
                    if (index !== -1) selectedImages.splice(index, 1);
                    previewItem.remove();
                    if (selectedImages.length === 0) {
                        previewContainer.classList.add('hidden');
                    }
                };
            };
            reader.readAsDataURL(file);
        });
        fileInput.value = '';
    };
}

// ========== ФУНКЦИИ ДЛЯ ПАНЕЛИ ПРОМТОВ ==========
let promptsData = [];

async function loadPromptsPanel() {
    try {
        const response = await fetch('/api/moderation/prompts');
        const data = await response.json();
        promptsData = data.prompts || [];
        renderPromptsList(promptsData);
    } catch (error) {
        console.error('Error loading prompts:', error);
    }
}

function renderPromptsList(prompts) {
    const container = document.getElementById('prompts-list');
    if (!container) return;
    
    // Группируем по типу
    const grouped = {};
    prompts.forEach(p => {
        const type = p.type || 'moderation';
        if (!grouped[type]) grouped[type] = [];
        grouped[type].push(p);
    });
    
    const typeNames = {
        moderation: 'Модерация',
        psychologist: 'Психология'
    };
    
    container.innerHTML = Object.entries(grouped).map(([type, items]) => `
        <div class="prompt-category">
            <h4>${typeNames[type] || type}</h4>
            ${items.map(p => `
                <div class="prompt-item" data-prompt-text="${escapeHtml(p.description)}">
                    <div class="prompt-name">${escapeHtml(p.name)}</div>
                    <div class="prompt-description">${escapeHtml(p.description)}</div>
                </div>
            `).join('')}
        </div>
    `).join('');
    
    // Добавляем обработчики
    document.querySelectorAll('.prompt-item').forEach(item => {
        item.onclick = () => {
            const promptText = item.dataset.promptText;
            const messageInput = document.getElementById('message-input');
            if (messageInput && promptText) {
                messageInput.value = promptText;
                messageInput.focus();
                closePromptsPanel();
            }
        };
    });
}

function togglePromptsPanel() {
    const panel = document.getElementById('prompts-panel');
    if (panel) {
        panel.classList.toggle('open');
    }
}

function closePromptsPanel() {
    const panel = document.getElementById('prompts-panel');
    if (panel) {
        panel.classList.remove('open');
    }
}

// ========== ФУНКЦИИ ДЛЯ БАРА ДЕЙСТВИЙ ==========
function setupActionsBar() {
    const toggleBtn = document.getElementById('actions-toggle-btn');
    const actionsBar = document.getElementById('actions-bar');
    
    if (toggleBtn && actionsBar) {
        toggleBtn.onclick = (e) => {
            e.stopPropagation();
            actionsBar.classList.toggle('hidden');
            toggleBtn.classList.toggle('rotated');
        };
        
        // Закрыть при клике вне
        document.addEventListener('click', (e) => {
            if (!actionsBar.contains(e.target) && e.target !== toggleBtn) {
                actionsBar.classList.add('hidden');
                toggleBtn.classList.remove('rotated');
            }
        });
    }
    
    // Обработчики кнопок в баре
    document.querySelectorAll('.action-btn').forEach(btn => {
        btn.onclick = (e) => {
            e.stopPropagation();
            const action = btn.dataset.action;
            
            switch(action) {
                case 'image':
                    // switchMode('image');
                    document.getElementById('image-file')?.click();
                    break;
                case 'audio':
                    switchMode('audio');
                    document.getElementById('audio-file')?.click();
                    break;
                case 'observer':
                    switchMode('observer');
                    const rightPanel = document.getElementById('right-panel');
                    const overlay = document.getElementById('overlay');
                    if (rightPanel) rightPanel.classList.add('open');
                    if (overlay && window.innerWidth <= 768) overlay.classList.add('active');
                    break;
                case 'prompts':
                    loadPromptsPanel();
                    togglePromptsPanel();
                    break;
            }
            
            // Закрываем бар
            const actionsBar = document.getElementById('actions-bar');
            const toggleBtn = document.getElementById('actions-toggle-btn');
            if (actionsBar) actionsBar.classList.add('hidden');
            if (toggleBtn) toggleBtn.classList.remove('rotated');
        };
    });
}

// ========== ФУНКЦИИ AI ==========
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
        }
    } catch (error) {
        console.error('Failed to load models:', error);
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

async function runObserverAnalysis() {
    if(!state.currentChat) return alert('Выберите чат');
    const role = document.getElementById('observer-role').value;
    const resBox = document.getElementById('observer-results-container');
    const resText = document.getElementById('observer-analysis-result');
    if (resBox) resBox.classList.remove('hidden');
    if (resText) resText.textContent = 'Анализирую...';
    try {
        let res;
        if(state.currentChatType === 'group') {
            res = await apiRequest('/api/group/observe', 'POST', { group_id: state.currentChat.id, role_prompt: role });
        } else {
            res = await apiRequest('/api/chat/observe', 'POST', { personal_chat_id: state.currentChat.id, role_prompt: role });
        }
        if (resText) resText.textContent = res.analysis || res.result;
    } catch(e) {
        if (resText) resText.textContent = 'Ошибка: ' + e.message;
    }
}

async function loadInvitations() {
    try {
        const data = await apiRequest('/api/invitations');
        const invitations = data.invitations || [];
        const container = document.getElementById('invitations-list');
        if (!container) return;
        if (invitations.length === 0) {
            container.innerHTML = '<p>Нет входящих приглашений</p>';
            return;
        }
        container.innerHTML = invitations.map(inv => `
            <div class="invitation-item">
                <span>Группа: ${escapeHtml(inv.group_name)}</span>
                <button class="btn-sm accept-invite-btn" data-group-id="${inv.group_id}">Принять</button>
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

// ========== ФУНКЦИИ ПОЛЬЗОВАТЕЛЯ ==========
async function loadUserGenderToSelect() {
    try {
        const response = await fetch('/api/auth/me');
        const user = await response.json();
        const select = document.getElementById('gender-select');
        if (select && user.gender) {
            select.value = user.gender;
        }
    } catch (error) {
        console.error('Error loading gender:', error);
    }
}

async function inviteToGroup() {
    if (!state.currentChat || state.currentChatType !== 'group') {
        showToast('❌ Сначала выберите группу');
        return;
    }
    const login = document.getElementById('invite-login-input')?.value.trim();
    if (!login) {
        showToast('❌ Введите логин пользователя');
        return;
    }
    const groupId = state.currentChat.id;
    try {
        const response = await fetch(`/api/group/invite`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ group_id: groupId, login: login })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Ошибка приглашения');
        showToast(`✅ Приглашение отправлено пользователю ${login}`);
        document.getElementById('invite-login-input').value = '';
    } catch (error) {
        console.error('Error inviting user:', error);
        showToast(`❌ Ошибка: ${error.message}`);
    }
}

async function logout() {
    try {
        const response = await fetch('/api/auth/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
        if (response.ok) {
            if (state.socket && state.socket.connected) state.socket.disconnect();
            state.currentUser = null;
            state.currentChat = null;
            window.location.href = '/login';
        }
    } catch (error) {
        console.error('Logout error:', error);
        window.location.href = '/login';
    }
}

// ========== НАСТРОЙКА СОБЫТИЙ ==========
function setupEventListeners() {
    const sidebar = document.getElementById('sidebar');
    const rightPanel = document.getElementById('right-panel');
    const overlay = document.getElementById('overlay');
    
    // Кнопка меню (левая панель)
    const menuToggle = document.getElementById('menu-toggle');
    if (menuToggle) {
        menuToggle.onclick = () => {
            if (sidebar) sidebar.classList.toggle('open');
            if (overlay) overlay.classList.toggle('active');
            if (rightPanel) rightPanel.classList.remove('open');
        };
    }
    // Кнопка включения уведомлений
    const enableNotificationsBtn = document.getElementById('enable-notifications-btn');
    if (enableNotificationsBtn) {
        enableNotificationsBtn.onclick = async () => {
            const granted = await requestNotificationPermission();
            if (granted) {
                showToast('✅ Уведомления включены');
                enableNotificationsBtn.style.display = 'none';
            } else {
                showToast('❌ Не удалось включить уведомления');
            }
        };
    }
    
    // Кнопка информации (правая панель)
    const infoToggle = document.getElementById('info-toggle');
    if (infoToggle) {
        infoToggle.onclick = () => {
            if (rightPanel) rightPanel.classList.toggle('open');
            if (overlay && window.innerWidth <= 768) overlay.classList.toggle('active');
            if (sidebar) sidebar.classList.remove('open');
        };
    }
    
    // Кнопка закрытия правой панели
    const closeRightPanel = document.getElementById('close-right-panel');
    if (closeRightPanel) {
        closeRightPanel.onclick = () => {
            if (rightPanel) rightPanel.classList.remove('open');
            if (overlay && window.innerWidth <= 768) overlay.classList.remove('active');
        };
    }
    
    // Кнопка закрытия панели промтов
    const closePromptsPanel = document.getElementById('close-prompts-panel');
    if (closePromptsPanel) {
        closePromptsPanel.onclick = () => {
            document.getElementById('prompts-panel')?.classList.remove('open');
        };
    }
    
    // Затемнение
    if (overlay) {
        overlay.onclick = () => {
            if (sidebar) sidebar.classList.remove('open');
            if (rightPanel) rightPanel.classList.remove('open');
            overlay.classList.remove('active');
        };
    }
    
    // Отправка сообщения
    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) sendBtn.onclick = sendMessage;
    
    // Поле ввода
    const messageInput = document.getElementById('message-input');
    if (messageInput) {
        setMessageInputEl(messageInput);
        messageInput.addEventListener('focus', () => {
            if (window.innerWidth <= 768) enableMobileTypingMode();
        });
        messageInput.addEventListener('blur', () => {
            setTimeout(() => {
                if (window.innerWidth <= 768) disableMobileTypingMode();
            }, 150);
        });
        messageInput.onkeypress = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        };
    }
    
    // Создание группы
    const createGroupBtn = document.getElementById('create-group-btn');
    if (createGroupBtn) {
        createGroupBtn.onclick = async () => {
            const nameInput = document.getElementById('new-group-name');
            const name = nameInput?.value.trim();
            if (!name) {
                alert('Введите название группы');
                return;
            }
            try {
                const group = await apiRequest('/api/group/create', 'POST', { name });
                alert(`Группа "${group.name}" создана!`);
                if (nameInput) nameInput.value = '';
                await loadChats();
            } catch(e) {
                console.error('Error creating group:', e);
                alert(e.message);
            }
        };
    }
    
    // Выход
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.onclick = logout;
    }
    
    // Сохранение пола
    const saveGenderBtn = document.getElementById('save-gender-btn');
    if (saveGenderBtn) {
        saveGenderBtn.onclick = async () => {
            const select = document.getElementById('gender-select');
            const gender = select ? select.value : 'neutral';
            try {
                const response = await fetch('/api/user/gender', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ gender: gender })
                });
                if (!response.ok) throw new Error('Ошибка сохранения');
                if (state.currentUser) state.currentUser.gender = gender;
                showToast(`✅ Пол сохранен: ${gender === 'male' ? 'Мужской' : gender === 'female' ? 'Женский' : 'Не указан'}`);
            } catch (error) {
                console.error('Error saving gender:', error);
                showToast('❌ Ошибка при сохранении');
            }
        };
    }
    
    // Анализ диалога
    const analyzeBtn = document.getElementById('analyze-btn');
    if (analyzeBtn) analyzeBtn.onclick = runObserverAnalysis;
    
    // AI модерация
    const moderationAnalyzeBtn = document.getElementById('analyze-messages-btn');
    if (moderationAnalyzeBtn) {
        moderationAnalyzeBtn.onclick = () => analyzeGroupMessages(state, showToast, displayModerationSuggestions, apiRequest);
    }
    
    const moderationApplyBtn = document.getElementById('apply-moderation-btn');
    if (moderationApplyBtn) {
        moderationApplyBtn.onclick = () => applySelectedModeration(state, showToast, applyModerationAction, apiRequest);
    }
    
    const moderationUndoBtn = document.getElementById('undo-moderation-btn');
    if (moderationUndoBtn) {
        moderationUndoBtn.onclick = () => undoLastModeration(state, showToast, apiRequest, renderMessages);
    }
    
    const moderationSelectAllBtn = document.getElementById('select-all-moderation');
    if (moderationSelectAllBtn) {
        moderationSelectAllBtn.onclick = () => {
            const checkboxes = document.querySelectorAll('.moderation-checkbox');
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            checkboxes.forEach(cb => cb.checked = !allChecked);
            moderationSelectAllBtn.textContent = allChecked ? 'Выбрать все' : 'Снять все';
        };
    }
    
    // Пре-модерация
    const preModToggle = document.getElementById('pre-moderation-toggle');
    if (preModToggle) {
        preModToggle.onchange = (e) => togglePreModeration(state, showToast);
    }
    
    const saveTopicBtn = document.getElementById('save-topic-btn');
    if (saveTopicBtn) saveTopicBtn.onclick = () => saveGroupTopic(state, showToast);
    
    const savePreModPromptBtn = document.getElementById('save-pre-mod-prompt-btn');
    if (savePreModPromptBtn) savePreModPromptBtn.onclick = () => savePreModerationPrompt(state, showToast);
    
    // Приглашение в группу
    const inviteUserBtn = document.getElementById('invite-user-btn');
    if (inviteUserBtn) inviteUserBtn.onclick = inviteToGroup;
    
    // Поиск промтов
    const searchInput = document.getElementById('prompts-search');
    if (searchInput) {
        searchInput.oninput = (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const filtered = promptsData.filter(p => 
                p.name.toLowerCase().includes(searchTerm) || 
                p.description.toLowerCase().includes(searchTerm)
            );
            renderPromptsList(filtered);
        };
    }
    
    // Бар действий
    setupActionsBar();
    
    // Обработка resize
    window.addEventListener('resize', handleMobileResize);
    if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', handleMobileResize);
    }
}

// ========== ЗАГРУЗКА МОДУЛЯ ИЗОБРАЖЕНИЙ ==========
async function loadImageModule() {
    try {
        const module = await import('./modules/images.js');
        console.log('✅ Модуль изображений загружен');
    } catch (error) {
        console.error('❌ Ошибка загрузки модуля изображений:', error);
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadImageModule);
} else {
    loadImageModule();
}
// ========== РЕДАКТИРОВАНИЕ И УДАЛЕНИЕ СООБЩЕНИЙ ==========
function showMessageMenu(messageId, messageContent, isOwner, isGroupOwner) {
    const overlay = document.createElement('div');
    overlay.style.position = 'fixed';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.right = '0';
    overlay.style.bottom = '0';
    overlay.style.zIndex = '9998';
    overlay.style.backgroundColor = 'rgba(0,0,0,0.5)';
    
    const menu = document.createElement('div');
    menu.style.position = 'fixed';
    menu.style.backgroundColor = '#1f1f1f';
    menu.style.borderRadius = '12px';
    menu.style.padding = '8px';
    menu.style.zIndex = '9999';
    menu.style.minWidth = '150px';
    menu.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
    
    if (isOwner) {
        const editBtn = document.createElement('button');
        editBtn.textContent = '✏️ Редактировать';
        editBtn.style.cssText = 'display:flex; align-items:center; gap:8px; width:100%; padding:10px; background:none; border:none; color:white; cursor:pointer; border-radius:8px; font-size:14px;';
        editBtn.onmouseover = () => editBtn.style.backgroundColor = '#2b2b2b';
        editBtn.onmouseout = () => editBtn.style.backgroundColor = 'transparent';
        editBtn.onclick = () => {
            menu.remove();
            overlay.remove();
            window.editMessage(messageId, messageContent);
        };
        menu.appendChild(editBtn);
    }
    
    if (isOwner || isGroupOwner) {
        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = '🗑️ Удалить';
        deleteBtn.style.cssText = 'display:flex; align-items:center; gap:8px; width:100%; padding:10px; background:none; border:none; color:#e94560; cursor:pointer; border-radius:8px; font-size:14px;';
        deleteBtn.onmouseover = () => deleteBtn.style.backgroundColor = '#2b2b2b';
        deleteBtn.onmouseout = () => deleteBtn.style.backgroundColor = 'transparent';
        deleteBtn.onclick = () => {
            menu.remove();
            overlay.remove();
            window.deleteMessage(messageId, isGroupOwner);
        };
        menu.appendChild(deleteBtn);
    }
    
    overlay.onclick = () => {
        menu.remove();
        overlay.remove();
    };
    
    document.body.appendChild(overlay);
    document.body.appendChild(menu);
    
    menu.style.left = (window.event ? window.event.clientX - 80 : window.innerWidth / 2 - 75) + 'px';
    menu.style.top = (window.event ? window.event.clientY - 10 : window.innerHeight / 2) + 'px';
}

async function editMessage(messageId, oldContent) {
    console.log(`=== EDIT MESSAGE === ID: ${messageId}`);
    
    const newContent = prompt('Редактировать сообщение:', oldContent);
    if (!newContent || newContent.trim() === '') return;
    if (newContent === oldContent) return;
    
    const endpoint = state.currentChatType === 'personal' 
        ? `/api/chat/message/${messageId}/edit`
        : `/api/message/${messageId}/edit`;
    
    try {
        const response = await fetch(endpoint, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: newContent.trim() })
        });
        const data = await response.json();
        
        if (!response.ok) throw new Error(data.error || 'Ошибка редактирования');
        
        showToast('✅ Сообщение изменено');
        
        const msgElement = document.querySelector(`.message[data-msg-id="${messageId}"]`);
        if (msgElement) {
            const contentElement = msgElement.querySelector('.msg-content');
            if (contentElement) contentElement.innerHTML = escapeHtml(newContent.trim());
            
            let editedSpan = msgElement.querySelector('.msg-edited');
            if (!editedSpan) {
                const timeElement = msgElement.querySelector('.msg-time');
                if (timeElement) {
                    editedSpan = document.createElement('span');
                    editedSpan.className = 'msg-edited';
                    editedSpan.style.cssText = 'font-size:0.65rem; opacity:0.6; margin-left:8px;';
                    editedSpan.textContent = '(изменено)';
                    timeElement.appendChild(editedSpan);
                }
            }
        }
    } catch (error) {
        console.error('Error editing message:', error);
        showToast(`❌ Ошибка: ${error.message}`);
    }
}

async function deleteMessage(messageId, isGroupOwner) {
    console.log(`=== DELETE MESSAGE === ID: ${messageId}`);
    
    let confirmMsg = 'Вы уверены, что хотите удалить это сообщение?';
    if (isGroupOwner) confirmMsg = 'Вы ВЛАДЕЛЕЦ ГРУППЫ. Удалить это сообщение?';
    if (!confirm(confirmMsg)) return;
    
    const endpoint = state.currentChatType === 'personal' 
        ? `/api/chat/message/${messageId}/delete`
        : `/api/message/${messageId}/delete`;
    
    try {
        const response = await fetch(endpoint, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        
        if (!response.ok) throw new Error(data.error || 'Ошибка удаления');
        
        showToast('✅ Сообщение удалено');
        
        const msgElement = document.querySelector(`.message[data-msg-id="${messageId}"]`);
        if (msgElement) {
            msgElement.style.opacity = '0.5';
            const contentElement = msgElement.querySelector('.msg-content');
            if (contentElement) contentElement.innerHTML = '<em>Сообщение удалено</em>';
            const menuBtn = msgElement.querySelector('.message-menu-btn');
            if (menuBtn) menuBtn.remove();
        }
    } catch (error) {
        console.error('Error deleting message:', error);
        showToast(`❌ Ошибка: ${error.message}`);
    }
}
// ========== УДАЛЕНИЕ ПЕРСОНАЛЬНОГО ЧАТА ==========
async function deletePersonalChat(chatId) {
    console.log(`=== DELETE PERSONAL CHAT ===`);
    console.log(`Chat ID: ${chatId}`);
    
    const confirmed = confirm('Вы уверены, что хотите удалить этот чат? Все сообщения будут потеряны.');
    if (!confirmed) return;
    
    try {
        const response = await fetch(`/api/chat/personal/${chatId}/delete`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        
        if (!response.ok) throw new Error(data.error || 'Ошибка удаления чата');
        
        showToast('✅ Чат удален');
        
        if (state.currentChat && state.currentChat.id === chatId && state.currentChatType === 'personal') {
            state.currentChat = null;
            const titleElem = document.getElementById('current-chat-title');
            if (titleElem) titleElem.textContent = 'Выберите чат';
            const messagesContainer = document.getElementById('messages-container');
            if (messagesContainer) {
                messagesContainer.innerHTML = `
                    <div style="text-align:center; margin-top:50px; color:var(--tg-text-secondary);">
                        <div style="font-size:4rem; margin-bottom:16px;">🤖</div>
                        <h3 style="margin-bottom:8px;">Чат удален</h3>
                        <p>Выберите другой чат для общения</p>
                    </div>
                `;
            }
        }
        await loadChats();
    } catch (error) {
        console.error('Error deleting personal chat:', error);
        showToast(`❌ Ошибка: ${error.message}`);
    }
}
// ========== УДАЛЕНИЕ/ВЫХОД ИЗ ГРУППЫ ==========
async function deleteGroup(groupId) {
    console.log(`=== DELETE GROUP ===`);
    console.log(`Group ID: ${groupId}`);
    
    const confirmed = confirm('Вы ВЛАДЕЛЕЦ группы. Удаление приведет к потере всех сообщений для всех участников. Удалить группу?');
    if (!confirmed) return;
    
    try {
        const response = await fetch(`/api/group/${groupId}/delete`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        
        if (!response.ok) throw new Error(data.error || 'Ошибка удаления группы');
        
        showToast('✅ Группа удалена');
        
        if (state.currentChat && state.currentChat.id === groupId && state.currentChatType === 'group') {
            state.currentChat = null;
            const titleElem = document.getElementById('current-chat-title');
            if (titleElem) titleElem.textContent = 'Выберите чат';
            const messagesContainer = document.getElementById('messages-container');
            if (messagesContainer) {
                messagesContainer.innerHTML = `
                    <div style="text-align:center; margin-top:50px; color:var(--tg-text-secondary);">
                        <div style="font-size:4rem; margin-bottom:16px;">🤖</div>
                        <h3 style="margin-bottom:8px;">Группа удалена</h3>
                        <p>Выберите другой чат для общения</p>
                    </div>
                `;
            }
        }
        await loadChats();
    } catch (error) {
        console.error('Error deleting group:', error);
        showToast(`❌ Ошибка: ${error.message}`);
    }
}

async function leaveGroup(groupId, groupName) {
    console.log(`=== LEAVE GROUP ===`);
    console.log(`Group ID: ${groupId}, Name: ${groupName}`);
    
    const confirmed = confirm(`Вы уверены, что хотите покинуть группу "${groupName}"?`);
    if (!confirmed) return;
    
    try {
        const response = await fetch(`/api/group/${groupId}/leave`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        
        if (!response.ok) throw new Error(data.error || 'Ошибка выхода из группы');
        
        showToast(`✅ Вы покинули группу "${groupName}"`);
        
        if (state.currentChat && state.currentChat.id === groupId && state.currentChatType === 'group') {
            state.currentChat = null;
            const titleElem = document.getElementById('current-chat-title');
            if (titleElem) titleElem.textContent = 'Выберите чат';
            const messagesContainer = document.getElementById('messages-container');
            if (messagesContainer) {
                messagesContainer.innerHTML = `
                    <div style="text-align:center; margin-top:50px; color:var(--tg-text-secondary);">
                        <div style="font-size:4rem; margin-bottom:16px;">🤖</div>
                        <h3 style="margin-bottom:8px;">Вы покинули группу</h3>
                        <p>Выберите другой чат для общения</p>
                    </div>
                `;
            }
        }
        await loadChats();
    } catch (error) {
        console.error('Error leaving group:', error);
        showToast(`❌ Ошибка: ${error.message}`);
    }
}

// ========== ПЕРЕИМЕНОВАНИЕ ПЕРСОНАЛЬНОГО ЧАТА ==========
async function renamePersonalChat(chatId, currentTitle) {
    console.log(`=== RENAME PERSONAL CHAT ===`);
    console.log(`Chat ID: ${chatId}, Current title: "${currentTitle}"`);
    
    const newTitle = prompt('Введите новое название чата:', currentTitle);
    if (!newTitle || newTitle.trim() === '') return;
    if (newTitle === currentTitle) return;
    
    const trimmedTitle = newTitle.trim();
    if (trimmedTitle.length > 100) {
        showToast('❌ Название не может быть длиннее 100 символов');
        return;
    }
    
    try {
        const response = await fetch(`/api/chat/personal/${chatId}/rename`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: trimmedTitle })
        });
        const data = await response.json();
        
        if (!response.ok) throw new Error(data.error || 'Ошибка переименования');
        
        showToast(`✅ Чат переименован в "${trimmedTitle}"`);
        
        if (state.currentChat && state.currentChat.id === chatId && state.currentChatType === 'personal') {
            state.currentChat.title = trimmedTitle;
            const titleElem = document.getElementById('current-chat-title');
            if (titleElem) titleElem.textContent = trimmedTitle;
        }
        await loadChats();
    } catch (error) {
        console.error('Error renaming personal chat:', error);
        showToast(`❌ Ошибка: ${error.message}`);
    }
}
// ========== ГЛОБАЛЬНЫЕ ФУНКЦИИ ==========
window.selectChat = selectChat;
window.sendMessage = sendMessage;
window.runObserverAnalysis = runObserverAnalysis;
window.acceptInvite = acceptInvite;
window.setAiName = setAiName;
window.showToast = showToast;
window.deletePersonalChat = deletePersonalChat;
window.deleteGroup = deleteGroup;
window.leaveGroup = leaveGroup;
window.renamePersonalChat = renamePersonalChat;
window.showMessageMenu = showMessageMenu;
window.editMessage = editMessage;
window.deleteMessage = deleteMessage;
window.inviteToGroup = inviteToGroup;
window.logout = logout;
window.switchMode = switchMode;
window.renderMessages = renderMessages;
window.renderList = renderList;
window.renderSingleMessage = renderSingleMessage;
window.showTypingIndicator = showTypingIndicator;
window.hideTypingIndicator = hideTypingIndicator;
window.clearModerationIndicators = clearModerationIndicators;
window.updateModerationIndicators = updateModerationIndicators;
window.analyzeGroupMessages = analyzeGroupMessages;
window.applyModerationAction = applyModerationAction;
window.applySelectedModeration = applySelectedModeration;
window.undoLastModeration = undoLastModeration;
window.checkMessageBeforeSend = checkMessageBeforeSend;
window.loadPreModerationSettings = loadPreModerationSettings;
window.togglePreModeration = togglePreModeration;
window.saveGroupTopic = saveGroupTopic;
window.savePsychologistPrompt = savePsychologistPrompt;
window.savePreModerationPrompt = savePreModerationPrompt;
window.notifyNewMessage = notifyNewMessage;
window.requestNotificationPermission = requestNotificationPermission;



console.log('✅ App initialized');