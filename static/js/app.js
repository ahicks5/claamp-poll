// CLAAMP • App JS (mobile-first, tiny)
/* global document, window */
(function(){
  const html = document.documentElement;
  html.classList.remove('no-js');

  // Mobile nav toggle
  const toggle = document.getElementById('nav-toggle');
  const nav = document.getElementById('site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
    });
  }

  // Header subtle state on scroll
  const header = document.querySelector('.site-header');
  let lastY = 0;
  if (header && window.matchMedia('(prefers-reduced-motion: no-preference)').matches) {
    window.addEventListener('scroll', () => {
      const y = window.scrollY || 0;
      header.classList.toggle('scrolled', y > 4);
      lastY = y;
    }, { passive: true });
  }

  // Focus-visible polyfill-like behavior for better keyboard outlines
  // Only show outlines when using keyboard
  let usingKey = false;
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      usingKey = true;
      html.classList.add('using-key');
    }
  });
  window.addEventListener('pointerdown', () => {
    if (usingKey) {
      usingKey = false;
      html.classList.remove('using-key');
    }
  });
})();
