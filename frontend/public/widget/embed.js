(function () {
  'use strict';

  const scriptTag = document.currentScript || document.querySelector('script[src*="embed.js"]');
  if (!scriptTag) return;

  const botId = scriptTag.getAttribute('data-bot-id');
  if (!botId) {
    console.error('Tisaa Chatbot: Missing data-bot-id attribute.');
    return;
  }

  // Change this to your deployed Next.js app URL
  const BASE_URL = scriptTag.getAttribute('data-base-url') || 'http://localhost:3000';
  const API_URL = scriptTag.getAttribute('data-api-url') || '';
  const widgetUrl = new URL(`${BASE_URL}/widget/${encodeURIComponent(botId)}`);
  if (API_URL) widgetUrl.searchParams.set('apiBase', API_URL);
  const WIDGET_URL = widgetUrl.toString();

  const iframe = document.createElement('iframe');
  iframe.src = WIDGET_URL;
  iframe.id = `tisaa-chatbot-${botId}`;
  iframe.setAttribute('aria-label', 'Tisaa AI Chat Widget');
  iframe.setAttribute('title', 'Chat with Tisaa AI');

  const styleIframe = (width, height, open) => {
    iframe.style.cssText = `
      position: fixed;
      bottom: 10px;
      right: 10px;
      width: ${width};
      height: ${height};
      border: none;
      z-index: 2147483647;
      background-color: transparent;
      color-scheme: normal;
      transition: width 0.3s ease, height 0.3s ease, opacity 0.2s ease;
      border-radius: ${open ? '24px' : '50%'};
      box-shadow: ${open ? '0 24px 80px rgba(0,0,0,0.2)' : '0 4px 24px rgba(0,0,0,0.15)'};
    `;
  };

  styleIframe('90px', '90px', false);
  document.body.appendChild(iframe);

  window.addEventListener('message', (event) => {
    if (event.origin !== BASE_URL) return;
    if (!event.data) return;

    if (event.data.type === 'CHAT_TOGGLED') {
      if (event.data.isOpen) {
        styleIframe('420px', '660px', true);
      } else {
        styleIframe('90px', '90px', false);
      }
    }

    if (event.data.type === 'GO_HOME') {
      window.location.href = '/';
    }
  });

  // Expose control API
  window.TisaaChat = {
    open: () => iframe.contentWindow?.postMessage({ type: 'OPEN' }, BASE_URL),
    close: () => iframe.contentWindow?.postMessage({ type: 'CLOSE' }, BASE_URL),
    destroy: () => { iframe.remove(); delete window.TisaaChat; },
  };
})();
