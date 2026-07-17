(function initScrollReveal() {
  const items = document.querySelectorAll('.scroll-reveal');
  if (!items.length) return;

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reducedMotion) {
    items.forEach((el) => el.classList.add('is-inview'));
    return;
  }

  function resolveScrollRoot() {
    const candidate =
      document.querySelector('[data-scroll-root]') ||
      document.querySelector('.main') ||
      document.scrollingElement;

    if (!candidate) return null;

    const style = getComputedStyle(candidate);
    const scrollable =
      style.overflowY === 'auto' ||
      style.overflowY === 'scroll' ||
      style.overflow === 'auto' ||
      style.overflow === 'scroll';

    if (scrollable && candidate.scrollHeight > candidate.clientHeight + 1) {
      return candidate;
    }

    return null;
  }

  document.documentElement.classList.add('motion-on');

  const observer = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-inview');
        obs.unobserve(entry.target);
      });
    },
    {
      root: resolveScrollRoot(),
      threshold: 0.08,
      rootMargin: '0px 0px -8% 0px',
    }
  );

  function observeItems() {
    items.forEach((el) => {
      if (el.classList.contains('check-hidden')) return;
      observer.observe(el);
    });
  }

  // Paint hidden state before intersection checks so transitions can run.
  requestAnimationFrame(() => {
    requestAnimationFrame(observeItems);
  });

  window.observeScrollReveal = (el) => {
    if (!el || el.classList.contains('is-inview')) return;
    requestAnimationFrame(() => observer.observe(el));
  };
})();
