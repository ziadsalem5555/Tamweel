/**
 * Tamweel AI Chatbot Frontend Controller
 * Strictly scoped, resilient, and accessible widget integration.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    const widget = document.getElementById('tamweel-chat-widget');
    if (!widget) return;

    const apiUrl = widget.getAttribute('data-api-url') || '/chatbot/api/message/';
    const launcherBtn = document.getElementById('tw-chat-launcher');
    const drawer = document.getElementById('tw-chat-drawer');
    const closeBtn = document.getElementById('tw-chat-close-btn');
    const messagesContainer = document.getElementById('tw-chat-messages');
    const typingIndicator = document.getElementById('tw-chat-typing');
    const chatForm = document.getElementById('tw-chat-form');
    const chatInput = document.getElementById('tw-chat-input');
    const sendBtn = document.getElementById('tw-chat-send-btn');
    const charCount = document.getElementById('tw-chat-char-count');
    const iconOpen = launcherBtn.querySelector('.tw-chat-icon-open');
    const iconClose = launcherBtn.querySelector('.tw-chat-icon-close');

    let isOpen = false;
    let isSending = false;

    // Helper: Retrieve CSRF Token from Cookie
    function getCsrfToken() {
      let cookieValue = '';
      if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
          const cookie = cookies[i].trim();
          if (cookie.substring(0, 10) === 'csrftoken=') {
            cookieValue = decodeURIComponent(cookie.substring(10));
            break;
          }
        }
      }
      return cookieValue;
    }

    // Helper: Safe HTML Escaping & Formatting
    function formatMessageText(text) {
      const p = document.createElement('p');
      p.textContent = text;
      // Convert newlines to breaks
      return p.innerHTML.replace(/\n/g, '<br>');
    }

    // Scroll messages to bottom smoothly
    function scrollToBottom() {
      if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }
    }

    // Toggle Drawer Open / Close
    function toggleChat(forceState) {
      isOpen = typeof forceState === 'boolean' ? forceState : !isOpen;
      
      if (isOpen) {
        drawer.classList.remove('tw-d-none');
        launcherBtn.setAttribute('aria-expanded', 'true');
        if (iconOpen) iconOpen.classList.add('tw-d-none');
        if (iconClose) iconClose.classList.remove('tw-d-none');
        setTimeout(() => {
          chatInput.focus();
          scrollToBottom();
        }, 150);
      } else {
        drawer.classList.add('tw-d-none');
        launcherBtn.setAttribute('aria-expanded', 'false');
        if (iconOpen) iconOpen.classList.remove('tw-d-none');
        if (iconClose) iconClose.classList.add('tw-d-none');
      }
    }

    // Append a Message Bubble to the Chat Body
    function appendMessage(role, text) {
      const msgDiv = document.createElement('div');
      msgDiv.className = `tw-chat-msg tw-chat-msg-${role}`;

      const avatarDiv = document.createElement('div');
      avatarDiv.className = 'tw-chat-msg-avatar';
      avatarDiv.innerHTML = role === 'assistant' 
        ? '<i class="fa-solid fa-robot"></i>' 
        : '<i class="fa-solid fa-user"></i>';

      const bodyDiv = document.createElement('div');
      bodyDiv.className = 'tw-chat-msg-body';

      const bubbleDiv = document.createElement('div');
      bubbleDiv.className = 'tw-chat-bubble';

      const textElem = document.createElement('p');
      textElem.className = 'tw-chat-msg-text';
      textElem.innerHTML = formatMessageText(text);

      bubbleDiv.appendChild(textElem);
      bodyDiv.appendChild(bubbleDiv);

      msgDiv.appendChild(avatarDiv);
      msgDiv.appendChild(bodyDiv);

      messagesContainer.appendChild(msgDiv);
      scrollToBottom();
    }

    // Auto-resize input textarea and update char counter
    function handleInputChange() {
      const val = chatInput.value;
      const length = val.length;

      if (charCount) {
        charCount.textContent = length;
      }

      // Auto resize height
      chatInput.style.height = 'auto';
      chatInput.style.height = Math.min(chatInput.scrollHeight, 90) + 'px';

      // Enable / Disable Send Button
      if (val.trim().length > 0 && length <= 500 && !isSending) {
        sendBtn.disabled = false;
      } else {
        sendBtn.disabled = true;
      }
    }

    // Helper: Show & Reset Typing Indicator
    function showTypingIndicator() {
      if (typingIndicator) {
        const thinkingLabel = typingIndicator.querySelector('.tw-chat-thinking-label');
        if (thinkingLabel) {
          thinkingLabel.remove();
        }
        typingIndicator.classList.remove('tw-d-none');
        scrollToBottom();
      }
    }

    function hideTypingIndicator() {
      if (typingIndicator) {
        typingIndicator.classList.add('tw-d-none');
        const thinkingLabel = typingIndicator.querySelector('.tw-chat-thinking-label');
        if (thinkingLabel) {
          thinkingLabel.remove();
        }
      }
    }

    function showLongWaitStatus() {
      if (typingIndicator && !typingIndicator.classList.contains('tw-d-none')) {
        let thinkingLabel = typingIndicator.querySelector('.tw-chat-thinking-label');
        if (!thinkingLabel) {
          thinkingLabel = document.createElement('span');
          thinkingLabel.className = 'tw-chat-thinking-label';
          thinkingLabel.style.cssText = 'font-size: 0.78rem; color: #64748b; margin-left: 8px; align-self: center; font-style: italic;';
          typingIndicator.appendChild(thinkingLabel);
        }
        thinkingLabel.textContent = 'Still thinking… this may take a little longer.';
        scrollToBottom();
      }
    }

    // Send Message to Django API Endpoint
    async function sendMessage(text) {
      const cleanText = (text || chatInput.value).trim();
      if (!cleanText || isSending) return;

      if (cleanText.length > 500) {
        appendMessage('assistant', 'Please keep your message under 500 characters.');
        return;
      }

      // 1. Render User Message
      appendMessage('user', cleanText);

      // 2. Clear Input & Reset State
      chatInput.value = '';
      handleInputChange();
      isSending = true;
      sendBtn.disabled = true;
      chatInput.disabled = true;

      // 3. Show Typing Indicator
      showTypingIndicator();

      // 4. Setup AbortController (70s generous timeout) and 10s Long-Wait Indicator
      const controller = new AbortController();
      const abortTimer = setTimeout(() => {
        controller.abort();
      }, 70000);

      const longWaitTimer = setTimeout(() => {
        showLongWaitStatus();
      }, 10000);

      try {
        const response = await fetch(apiUrl, {
          method: 'POST',
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({ message: cleanText }),
        });

        // Hide typing indicator immediately once response headers arrive
        hideTypingIndicator();

        if (response.status === 429) {
          appendMessage(
            'assistant',
            "You've sent several messages quickly. Please wait a moment and try again."
          );
        } else if (response.ok) {
          const data = await response.json();
          if (data && data.reply) {
            appendMessage('assistant', data.reply);
          } else {
            appendMessage('assistant', "Sorry, I couldn't process that right now. Please try again.");
          }
        } else {
          appendMessage('assistant', "Sorry, I couldn't process that right now. Please try again.");
        }
      } catch (err) {
        hideTypingIndicator();
        if (err.name === 'AbortError') {
          appendMessage('assistant', 'Sorry, the AI is taking longer than expected. Please try again.');
        } else {
          appendMessage('assistant', "Sorry, I couldn't process that right now. Please check your connection and try again.");
        }
      } finally {
        clearTimeout(abortTimer);
        clearTimeout(longWaitTimer);
        hideTypingIndicator();
        isSending = false;
        chatInput.disabled = false;
        handleInputChange();
        setTimeout(() => chatInput.focus(), 50);
      }
    }

    // Event Listeners
    launcherBtn.addEventListener('click', function () {
      toggleChat();
    });

    closeBtn.addEventListener('click', function () {
      toggleChat(false);
    });

    chatForm.addEventListener('submit', function (e) {
      e.preventDefault();
      sendMessage();
    });

    chatInput.addEventListener('input', handleInputChange);

    chatInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    // Delegate Click on Suggestion Chips
    document.addEventListener('click', function (e) {
      const chip = e.target.closest('.tw-chat-chip');
      if (chip) {
        const question = chip.getAttribute('data-question');
        if (question) {
          sendMessage(question);
        }
      }
    });

    // Close on Escape Key
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen) {
        toggleChat(false);
      }
    });
  });
})();
