/* ═══════════════════════════════════════════════════════════════════
   PawReach – Landing Page Interactions (Redesign)
   ═══════════════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  initStickyNav();
  initScrollReveal(prefersReducedMotion);
  initMobileMenu();
  initCounterAnimation(prefersReducedMotion);
  initSmoothScroll();
  initRoleTabs();
  initTimelineProgress(prefersReducedMotion);
});

/* ── Sticky Navigation ── */
function initStickyNav() {
  const header = document.getElementById('site-header');
  if (!header) return;

  window.addEventListener('scroll', () => {
    if (window.scrollY > 60) {
      header.classList.add('scrolled');
    } else {
      header.classList.remove('scrolled');
    }
  }, { passive: true });
}

/* ── Scroll Reveal (IntersectionObserver) ── */
function initScrollReveal(prefersReducedMotion) {
  const elements = document.querySelectorAll('.reveal');
  if (prefersReducedMotion) {
    elements.forEach(el => el.classList.add('visible'));
    return;
  }

  let index = 0;
  elements.forEach((el) => {
    const delay = Math.min((index % 6) * 60, 300);
    el.style.transitionDelay = `${delay}ms`;
    index++;
  });

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  }, {
    threshold: 0.08,
    rootMargin: '0px 0px -30px 0px',
  });

  elements.forEach((el) => observer.observe(el));
}

/* ── Mobile Menu ── */
function initMobileMenu() {
  const toggle = document.getElementById('mobile-toggle');
  const panel = document.getElementById('mobile-nav-panel');
  const overlay = document.getElementById('mobile-nav-overlay');
  const closeBtn = document.getElementById('mobile-nav-close');

  if (!toggle || !panel || !overlay) return;

  function openMenu() {
    panel.style.display = 'flex';
    overlay.style.display = 'block';
    // Trigger reflow for transition
    panel.offsetHeight;
    panel.classList.add('open');
    overlay.classList.add('open');
    toggle.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeMenu() {
    panel.classList.remove('open');
    overlay.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
    setTimeout(() => {
      panel.style.display = 'none';
      overlay.style.display = 'none';
    }, 350);
  }

  toggle.addEventListener('click', openMenu);
  overlay.addEventListener('click', closeMenu);
  if (closeBtn) closeBtn.addEventListener('click', closeMenu);

  // Close on link click
  panel.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', closeMenu);
  });

  // Close on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && panel.classList.contains('open')) {
      closeMenu();
    }
  });
}

/* ── Counter Animation ── */
function initCounterAnimation(prefersReducedMotion) {
  const counters = document.querySelectorAll('.impact-number');
  if (!counters.length) return;

  if (prefersReducedMotion) return; // Keep static values

  const observed = new Set();

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting && !observed.has(entry.target)) {
        observed.add(entry.target);
        animateCounter(entry.target);
      }
    });
  }, { threshold: 0.5 });

  counters.forEach(counter => observer.observe(counter));
}

function animateCounter(el) {
  const text = el.textContent.trim();
  const hasPlus = text.includes('+');
  const numericStr = text.replace(/[^0-9.]/g, '');
  const target = parseFloat(numericStr);

  if (isNaN(target)) return;

  const isMin = text.includes('min');
  const isK = text.includes('K');
  const duration = 1400;
  const startTime = performance.now();

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic

    const current = Math.round(eased * target);

    if (isMin) {
      el.textContent = `${current} min`;
    } else if (isK) {
      const kVal = Math.round(eased * 85);
      el.textContent = kVal + 'K+';
    } else if (target >= 1000) {
      el.textContent = current.toLocaleString() + (hasPlus ? '+' : '');
    } else {
      el.textContent = current + (hasPlus ? '+' : '');
    }

    if (progress < 1) {
      requestAnimationFrame(update);
    }
  }

  el.textContent = '0';
  requestAnimationFrame(update);
}

/* ── Smooth Scroll ── */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', (e) => {
      const targetId = link.getAttribute('href');
      if (targetId === '#') return;

      const target = document.querySelector(targetId);
      if (target) {
        e.preventDefault();
        const headerHeight = document.getElementById('site-header')?.offsetHeight || 64;
        const top = target.getBoundingClientRect().top + window.scrollY - headerHeight - 16;
        window.scrollTo({ top, behavior: 'smooth' });
      }
    });
  });
}

/* ── Role-Based Workflow Tabs ── */
function initRoleTabs() {
  const tabs = document.querySelectorAll('.role-tab');
  const panels = document.querySelectorAll('.role-panel');
  const mockupBody = document.getElementById('role-mockup-body');

  if (!tabs.length || !panels.length) return;

  const mockupContent = {
    citizen: {
      header: 'Report an Animal',
      cards: [
        { title: 'Injured dog near Linking Road', desc: 'Animal appears unable to move. Located near the intersection.', status: 'Critical — Rescue dispatched', statusClass: 'critical' },
        { title: 'Your Case: PR-02481', desc: 'Responder Anjali R. is en route. ETA 6 minutes.', status: 'Responder En Route', statusClass: 'active-status' },
      ]
    },
    rescuer: {
      header: 'Nearby Cases',
      cards: [
        { title: 'PR-02481 · Dog · 1.7 km away', desc: 'Critical — Road accident near Bandra West. Navigate to location.', status: 'Accept & Navigate', statusClass: 'critical' },
        { title: 'PR-02479 · Cat · 3.2 km away', desc: 'Urgent — Stuck in drainage near Andheri. Awaiting rescuer.', status: 'View Details', statusClass: 'active-status' },
      ]
    },
    vet: {
      header: 'Incoming Cases',
      cards: [
        { title: 'PR-02481 · Dog · Road accident', desc: 'Triage: Suspected fracture, right hind leg. Photos and field notes attached.', status: 'Arriving in 6 min', statusClass: 'critical' },
        { title: 'Treatment: PR-02475 · Cat', desc: 'Day 3 post-surgery. Wound healing well. Appetite returning.', status: 'Recovery on track', statusClass: 'success' },
      ]
    },
    ngo: {
      header: 'Operations Dashboard',
      cards: [
        { title: '128 Active Cases', desc: 'Across 12 regions. 14 cases awaiting assignment. Average response: 2.4 hrs.', status: 'View All Cases', statusClass: 'active-status' },
        { title: 'Weekly Impact Report', desc: '89% successful recovery rate. Response time improved 18% from last month.', status: 'Download Report', statusClass: 'success' },
      ]
    },
    municipality: {
      header: 'City-wide Overview',
      cards: [
        { title: 'Mumbai Metro — Rescue Activity', desc: '142 active cases across 28 wards. 5 hotspots identified this week.', status: 'View Heatmap', statusClass: 'active-status' },
        { title: 'Compliance & Audit', desc: 'All cases logged with timestamps, responder IDs, and outcome records.', status: 'Fully compliant', statusClass: 'success' },
      ]
    },
  };

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const role = tab.dataset.role;

      // Update tabs
      tabs.forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');

      // Update text panels
      panels.forEach(p => p.classList.remove('active'));
      const activePanel = document.querySelector(`.role-panel[data-role="${role}"]`);
      if (activePanel) activePanel.classList.add('active');

      // Update mockup
      if (mockupBody && mockupContent[role]) {
        const data = mockupContent[role];
        mockupBody.innerHTML = `
          <div class="role-mockup-header-text">${data.header}</div>
          ${data.cards.map(card => `
            <div class="role-mockup-card">
              <div class="role-mockup-card-title">${card.title}</div>
              <div class="role-mockup-card-desc">${card.desc}</div>
              <div class="role-mockup-status ${card.statusClass}">● ${card.status}</div>
            </div>
          `).join('')}
        `;
      }
    });
  });
}

/* ── How It Works Timeline Progress ── */
function initTimelineProgress(prefersReducedMotion) {
  const progress = document.getElementById('how-progress');
  if (!progress || prefersReducedMotion) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        progress.classList.add('animated');
      }
    });
  }, { threshold: 0.3 });

  observer.observe(progress.parentElement);
}
