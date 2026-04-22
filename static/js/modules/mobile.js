/**
 * Модуль мобильного режима - управление отображением при вводе текста
 */

let isMobileTypingMode = false;
let messageInputEl = null;
let mobileResizeTimer = null;

/**
 * Включает режим "только чат" на мобильных:
 * - скрывает боковые панели, тулбар, лишние элементы шапки
 * - фиксирует поле ввода к низу экрана
 */
export function enableMobileTypingMode() {
    if (window.innerWidth > 768) return;
    
    const appContainer = document.getElementById('app-container');
    if (!appContainer) return;
    
    appContainer.classList.add('typing-mode');
    isMobileTypingMode = true;
    
    // Добавляем отступ для сообщений, чтобы не перекрывались полем ввода
    const messagesArea = document.getElementById('messages-container');
    if (messagesArea) {
        messagesArea.style.paddingBottom = '140px';
    }
    
    // Скрываем плавающие кнопки
    const floatingBtns = document.querySelectorAll('.floating-btn, .floating-actions');
    floatingBtns.forEach(btn => {
        btn.style.opacity = '0';
        btn.style.pointerEvents = 'none';
    });
    
    // Скрываем бар действий
    const actionsBar = document.getElementById('actions-bar');
    if (actionsBar) {
        actionsBar.classList.add('hidden');
    }
    const toggleBtn = document.getElementById('actions-toggle-btn');
    if (toggleBtn) {
        toggleBtn.classList.remove('rotated');
    }
    
    setTimeout(() => {
        if (messageInputEl) {
            messageInputEl.scrollIntoView({ behavior: 'auto', block: 'nearest' });
        }
        const messagesContainer = document.getElementById('messages-container');
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }, 100);
    
    console.log('📱 Mobile typing mode: ENABLED');
}

export function disableMobileTypingMode() {
    const appContainer = document.getElementById('app-container');
    if (!appContainer) return;
    
    appContainer.classList.remove('typing-mode');
    isMobileTypingMode = false;
    
    // Возвращаем отступ для сообщений
    const messagesArea = document.getElementById('messages-container');
    if (messagesArea) {
        messagesArea.style.paddingBottom = '';
                messagesArea.style.height = 'auto';
        setTimeout(() => {
            messagesArea.style.height = '';
            messagesArea.scrollTop = messagesArea.scrollHeight; // прокрутка вниз
        }, 50);
    }
    
    // Показываем плавающие кнопки
    const floatingBtns = document.querySelectorAll('.floating-btn, .floating-actions');
    floatingBtns.forEach(btn => {
        btn.style.opacity = '1';
        btn.style.pointerEvents = 'auto';
    });
    
    console.log('📱 Mobile typing mode: DISABLED');
}

/**
 * Обработчик resize: появление клавиатуры, поворот экрана
 */
export function handleMobileResize() {
    if (window.innerWidth > 768) {
        disableMobileTypingMode();
        return;
    }
    
    if (document.activeElement === messageInputEl && !isMobileTypingMode) {
        enableMobileTypingMode();
    }
    if (document.activeElement !== messageInputEl && isMobileTypingMode) {
        disableMobileTypingMode();
    }
}

/**
 * Устанавливает ссылку на поле ввода
 */
export function setMessageInputEl(el) {
    messageInputEl = el;
}

/**
 * Возвращает состояние мобильного режима
 */
export function getMobileTypingMode() {
    return isMobileTypingMode;
}

/**
 * Возвращает ссылку на поле ввода
 */
export function getMessageInputEl() {
    return messageInputEl;
}

/**
 * Возвращает таймер
 */
export function getMobileResizeTimer() {
    return mobileResizeTimer;
}

/**
 * Устанавливает таймер
 */
export function setMobileResizeTimer(timer) {
    mobileResizeTimer = timer;
}