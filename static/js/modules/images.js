// Модуль для работы с изображениями

// Предпросмотр изображений
export function setupImagePreview() {
    const fileInput = document.getElementById('image-file');
    if (!fileInput) return;
    
    fileInput.onchange = (e) => {
        const container = document.getElementById('image-preview-container');
        if (!container) return;
        
        container.innerHTML = '';
        const files = Array.from(e.target.files);
        
        files.forEach(file => {
            const reader = new FileReader();
            reader.onload = (event) => {
                const img = document.createElement('img');
                img.src = event.target.result;
                img.style.cssText = 'width:60px;height:60px;object-fit:cover;border-radius:8px;margin:4px;border:2px solid #3390ec;cursor:pointer;';
                img.title = file.name;
                container.appendChild(img);
            };
            reader.readAsDataURL(file);
        });
    };
}

// Загрузка и анализ изображений
export function setupImageUpload(getState, showTypingIndicator, hideTypingIndicator, showToast) {
    const uploadBtn = document.getElementById('upload-image-btn');
    if (!uploadBtn) return;
    
    uploadBtn.onclick = async () => {
        const fileInput = document.getElementById('image-file');
        const files = fileInput.files;
        
        if (!files || files.length === 0) {
            alert('Выберите изображения');
            return;
        }
        
        const state = getState();
        if (!state.currentChat) {
            alert('Выберите чат');
            return;
        }
        
        // Берем текст из поля ввода сообщений
        const messageInput = document.getElementById('message-input');
        let prompt = messageInput ? messageInput.value.trim() : '';
        
        // Если поле ввода пустое - используем стандартный промт
        if (!prompt) {
            prompt = 'Опишите эти изображения подробно. Что на них изображено?';
        }
        
        // Очищаем поле ввода
        if (messageInput) {
            messageInput.value = '';
        }
        
        const uploadBtnEl = document.getElementById('upload-image-btn');
        const originalText = uploadBtnEl.textContent;
        uploadBtnEl.textContent = '⏳ Анализ...';
        uploadBtnEl.disabled = true;
        
        // ⚠️ Таймаут на случай, если WebSocket не сработает
        let timeoutId = null;
        
        try {
            if (showTypingIndicator) showTypingIndicator();
            
            const formData = new FormData();
            for (let i = 0; i < files.length; i++) {
                formData.append('files', files[i]);
            }
            formData.append('prompt', prompt);
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
            
            // ✅ НОВОЕ: Обрабатываем ответ 202 "processing"
            if (result.status === 'processing') {
                // Результат придёт через WebSocket, просто информируем пользователя
                if (showToast) {
                    showToast('📤 Анализ запущен. Ожидайте ответ в чате...');
                }
                
                // ⏱️ Ставим страховочный таймаут на 30 секунд
                timeoutId = setTimeout(() => {
                    console.warn('⚠️ Timeout: WebSocket message not received for vision analysis');
                    if (hideTypingIndicator) hideTypingIndicator();
                    if (showToast) {
                        showToast('⚠️ Задержка ответа. Попробуйте обновить страницу, если сообщение не появилось.');
                    }
                }, 30000);
                
            } else if (result.analysis) {
                // ✅ Старый путь: если анализ вернулся сразу (fallback)
                if (showToast) {
                    showToast(`✅ Анализ ${files.length} изображения(ий) завершен`);
                }
            }
            
            // Очищаем input файлов и превью
            fileInput.value = '';
            const previewContainer = document.getElementById('image-preview-container');
            if (previewContainer) {
                previewContainer.innerHTML = '';
            }
            
        } catch (error) {
            console.error('❌ Ошибка:', error);
            alert('Ошибка при анализе: ' + error.message);
            if (hideTypingIndicator) hideTypingIndicator();
        } finally {
            uploadBtnEl.textContent = originalText;
            uploadBtnEl.disabled = false;
            // ✅ Очищаем таймаут, если всё пришло вовремя
            if (timeoutId) clearTimeout(timeoutId);
        }
    };
}