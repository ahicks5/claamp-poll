// Mobile nav toggle
(function () {
  const btn = document.getElementById('nav-toggle');
  const nav = document.getElementById('site-nav');
  if (!btn || !nav) return;

  function closeOnEsc(e){
    if (e.key === 'Escape') {
      nav.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
      document.removeEventListener('keydown', closeOnEsc);
    }
  }

  btn.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    btn.setAttribute('aria-expanded', String(open));
    if (open) {
      document.addEventListener('keydown', closeOnEsc);
    } else {
      document.removeEventListener('keydown', closeOnEsc);
    }
  });

  // Close on outside click (mobile dropdown mode)
  document.addEventListener('click', (e) => {
    if (!nav.classList.contains('open')) return;
    if (e.target === btn || btn.contains(e.target)) return;
    if (e.target === nav || nav.contains(e.target)) return;
    nav.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
  });
})();
