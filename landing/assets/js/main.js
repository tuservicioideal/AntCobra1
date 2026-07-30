(function () {
  "use strict";

  const header = document.querySelector(".site-header");
  const navToggle = document.querySelector(".nav-toggle");
  const mainNav = document.querySelector(".main-nav");

  // Header scroll effect
  function onScroll() {
    if (window.scrollY > 40) {
      header.classList.add("scrolled");
    } else {
      header.classList.remove("scrolled");
    }
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // Mobile nav toggle
  if (navToggle && mainNav) {
    function closeNav() {
      navToggle.setAttribute("aria-expanded", "false");
      mainNav.classList.remove("open");
      document.body.style.overflow = "";
    }

    function openNav() {
      navToggle.setAttribute("aria-expanded", "true");
      mainNav.classList.add("open");
      document.body.style.overflow = "hidden";
    }

    navToggle.addEventListener("click", function () {
      const expanded = navToggle.getAttribute("aria-expanded") === "true";
      if (expanded) {
        closeNav();
      } else {
        openNav();
      }
    });

    mainNav.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", closeNav);
    });

    window.addEventListener(
      "resize",
      function () {
        if (window.innerWidth > 1100 && mainNav.classList.contains("open")) {
          closeNav();
        }
      },
      { passive: true }
    );

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && mainNav.classList.contains("open")) {
        closeNav();
      }
    });
  }

  // Scroll reveal
  const revealElements = document.querySelectorAll(".reveal");

  if ("IntersectionObserver" in window && revealElements.length) {
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (prefersReduced) {
      revealElements.forEach(function (el) {
        el.classList.add("visible");
      });
    } else {
      const observer = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) {
              entry.target.classList.add("visible");
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
      );

      revealElements.forEach(function (el) {
        observer.observe(el);
      });
    }
  } else {
    revealElements.forEach(function (el) {
      el.classList.add("visible");
    });
  }

  // Animated counters
  const counters = document.querySelectorAll(".counter");

  if (counters.length && "IntersectionObserver" in window) {
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function animateCounter(el) {
      const target = parseInt(el.getAttribute("data-target"), 10);
      if (isNaN(target)) return;

      if (prefersReduced) {
        el.textContent = String(target);
        return;
      }

      const duration = 1600;
      const start = performance.now();

      function tick(now) {
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = String(Math.round(eased * target));
        if (progress < 1) {
          requestAnimationFrame(tick);
        }
      }

      requestAnimationFrame(tick);
    }

    const counterObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            animateCounter(entry.target);
            counterObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.4 }
    );

    counters.forEach(function (el) {
      counterObserver.observe(el);
    });
  } else {
    counters.forEach(function (el) {
      el.textContent = el.getAttribute("data-target");
    });
  }

  // FAQ: only one open at a time (optional UX)
  const faqItems = document.querySelectorAll(".faq-item");

  faqItems.forEach(function (item) {
    item.addEventListener("toggle", function () {
      if (item.open) {
        faqItems.forEach(function (other) {
          if (other !== item && other.open) {
            other.open = false;
          }
        });
      }
    });
  });
})();
