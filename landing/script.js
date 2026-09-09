/* ═══════════════════════════════════════════════════════════════════
   PawReach – Landing Page Interactions
   ═══════════════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
  initStickyNav();
  initScrollAnimations();
  initMobileMenu();
  initMapInteractions();
  initCounterAnimation();
  initSmoothScroll();
});

/* ── Sticky Navigation ── */
function initStickyNav() {
  const header = document.getElementById('site-header');
  let lastScroll = 0;

  window.addEventListener('scroll', () => {
    const scroll = window.scrollY;
    if (scroll > 60) {
      header.classList.add('scrolled');
    } else {
      header.classList.remove('scrolled');
    }
    lastScroll = scroll;
  }, { passive: true });
}

/* ── Scroll Animations (Intersection Observer) ── */
function initScrollAnimations() {
  // Add fade-up class to animatable elements
  const selectors = [
    '.section-header',
    '.feature-card',
    '.step-item',
    '.testimonial-card',
    '.why-card',
    '.stat-card',
    '.map-demo',
    '.org-content',
    '.org-dashboard',
    '.emotional-content',
    '.trust-logos',
    '.cta-container',
  ];

  const elements = document.querySelectorAll(selectors.join(','));
  elements.forEach((el, i) => {
    el.classList.add('fade-up');
    el.style.transitionDelay = `${Math.min(i % 6, 4) * 80}ms`;
  });

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -40px 0px',
  });

  elements.forEach((el) => observer.observe(el));
}

/* ── Mobile Menu Toggle ── */
function initMobileMenu() {
  const toggle = document.getElementById('mobile-toggle');
  const nav = document.getElementById('main-nav');

  if (!toggle || !nav) return;

  toggle.addEventListener('click', () => {
    const isOpen = nav.style.display === 'flex';
    nav.style.display = isOpen ? 'none' : 'flex';
    nav.style.position = isOpen ? '' : 'absolute';
    nav.style.top = isOpen ? '' : '100%';
    nav.style.left = isOpen ? '' : '0';
    nav.style.right = isOpen ? '' : '0';
    nav.style.flexDirection = isOpen ? '' : 'column';
    nav.style.background = isOpen ? '' : 'white';
    nav.style.padding = isOpen ? '' : '16px';
    nav.style.boxShadow = isOpen ? '' : '0 8px 24px rgba(0,0,0,0.1)';
    nav.style.borderRadius = isOpen ? '' : '0 0 12px 12px';
    nav.style.zIndex = isOpen ? '' : '100';

    // Animate hamburger
    const spans = toggle.querySelectorAll('span');
    if (!isOpen) {
      spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
      spans[1].style.opacity = '0';
      spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
    } else {
      spans[0].style.transform = '';
      spans[1].style.opacity = '';
      spans[2].style.transform = '';
    }
  });
}

/* ── Map Interactions ── */
function initMapInteractions() {
  const pins = document.querySelectorAll('.map-pin');
  const caseCard = document.getElementById('case-card');

  // Case data for different pins
  const caseData = [
    {
      id: 'PR-02481', desc: 'Dog injured near roadway', priority: 'Critical',
      reported: '8 minutes ago', responder: '1.7 km', volunteer: 'Anjali R.',
      facility: 'City Veterinary Care', status: 'Responder En Route',
      step: 3
    },
    {
      id: 'PR-02479', desc: 'Cat stuck in drainage', priority: 'Critical',
      reported: '12 minutes ago', responder: '2.1 km', volunteer: 'Ravi K.',
      facility: 'PetCare Hospital', status: 'Dispatching',
      step: 2
    },
    {
      id: 'PR-02477', desc: 'Injured stray near market', priority: 'Urgent',
      reported: '22 minutes ago', responder: '0.8 km', volunteer: 'Priya M.',
      facility: 'Vetlife Clinic', status: 'Under Treatment',
      step: 4
    },
    {
      id: 'PR-02474', desc: 'Dog with limping gait', priority: 'Assigned',
      reported: '35 minutes ago', responder: '1.2 km', volunteer: 'Sunil D.',
      facility: 'Animal Aid Center', status: 'Volunteer Assigned',
      step: 3
    },
  ];

  pins.forEach((pin, i) => {
    pin.addEventListener('click', () => {
      const data = caseData[i % caseData.length];
      if (!caseCard) return;

      // Update card content
      caseCard.querySelector('.case-id').textContent = `Case ${data.id}`;
      caseCard.querySelector('.case-desc').textContent = data.desc;

      const priorityEl = caseCard.querySelector('.case-priority');
      priorityEl.textContent = data.priority;
      priorityEl.className = `case-priority ${data.priority.toLowerCase()}`;

      const values = caseCard.querySelectorAll('.case-value');
      if (values.length >= 4) {
        values[0].textContent = data.reported;
        values[1].textContent = data.responder;
        values[2].textContent = data.volunteer;
        values[3].textContent = data.facility;
      }

      caseCard.querySelector('.highlight-status').textContent = data.status;

      // Update progress steps
      const steps = caseCard.querySelectorAll('.progress-step');
      steps.forEach((step, j) => {
        step.className = 'progress-step';
        if (j < data.step) step.classList.add('completed');
        else if (j === data.step) step.classList.add('current');
      });

      // Animate card
      caseCard.style.animation = 'none';
      caseCard.offsetHeight; // trigger reflow
      caseCard.style.animation = 'cardPop 0.3s ease';
    });
  });

  // Filter interactions
  const filters = document.querySelectorAll('.filter-item');
  filters.forEach(filter => {
    filter.addEventListener('click', () => {
      filter.classList.toggle('active');
      const type = filter.dataset.filter;
      const matchingPins = document.querySelectorAll(`.map-pin.${type}`);
      matchingPins.forEach(pin => {
        pin.style.opacity = filter.classList.contains('active') ? '1' : '0.2';
      });
    });
  });

  // Add cardPop animation dynamically
  const style = document.createElement('style');
  style.textContent = `
    @keyframes cardPop {
      0% { transform: scale(0.95); opacity: 0.7; }
      100% { transform: scale(1); opacity: 1; }
    }
  `;
  document.head.appendChild(style);
}

/* ── Counter Animation ── */
function initCounterAnimation() {
  const counters = document.querySelectorAll('.stat-number');
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

  const isDecimal = text.includes('min');
  const duration = 1500;
  const startTime = performance.now();

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic

    const current = Math.round(eased * target);

    if (text.includes('min')) {
      el.textContent = `${current} min`;
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

        // Close mobile menu if open
        const nav = document.getElementById('main-nav');
        if (nav && nav.style.display === 'flex' && window.innerWidth <= 900) {
          nav.style.display = 'none';
          const spans = document.querySelectorAll('.mobile-toggle span');
          spans.forEach(s => { s.style.transform = ''; s.style.opacity = ''; });
        }
      }
    });
  });
}
