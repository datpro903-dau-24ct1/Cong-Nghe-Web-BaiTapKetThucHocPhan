/**
 * Hệ thống Animation 60fps cho Shop Mô hình Anime:
 * 1. Thanh tiến trình cuộn trang (Neon Scroll Progress)
 * 2. Hạt năng lượng Anime lơ lửng tương tác chuột (Canvas Mana Particles)
 * 3. Hiệu ứng nghiêng 3D (3D Tilt) + Đèn chiếu Spotlight theo chuột cho Card & Hero
 * 4. Hiệu ứng xuất hiện khi cuộn trang (ScrollTrigger / IntersectionObserver Stagger)
 * 5. Nút bấm từ tính (Magnetic Buttons) + Sóng xung kích (Neon Ripple)
 * 6. Phóng ảnh kính lúp & Lightbox toàn màn hình cho trang Chi tiết sản phẩm
 * 7. Đếm số tự động (Count-Up) cho thống kê Dashboard
 */
(function () {
  "use strict";

  var prefersReducedMotion =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* --------------------------------------------------------------------------
   * 1. Header kính mờ & Thanh tiến trình cuộn trang (Scroll Progress Bar)
   * -------------------------------------------------------------------------- */
  var header = document.querySelector(".site-header");
  var progressBar = document.createElement("div");
  progressBar.className = "scroll-progress-bar";
  document.body.appendChild(progressBar);

  var backToTop = document.createElement("button");
  backToTop.type = "button";
  backToTop.className = "back-to-top";
  backToTop.setAttribute("aria-label", "Lên đầu trang");
  backToTop.innerHTML = "↑";
  document.body.appendChild(backToTop);
  backToTop.addEventListener("click", function () {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  function updateScrollUI() {
    var scrollTop = window.scrollY || document.documentElement.scrollTop;
    if (header) {
      header.classList.toggle("scrolled", scrollTop > 16);
    }
    backToTop.classList.toggle("visible", scrollTop > 320);
    var docHeight =
      document.documentElement.scrollHeight -
      document.documentElement.clientHeight;
    var progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
    progressBar.style.width = progress.toFixed(2) + "%";
  }
  window.addEventListener("scroll", updateScrollUI, { passive: true });
  updateScrollUI();

  /* Đóng menu dropdown khi click ra ngoài */
  document.addEventListener("click", function (e) {
    document.querySelectorAll("details.menu[open]").forEach(function (d) {
      if (!d.contains(e.target)) d.open = false;
    });
  });

  if (prefersReducedMotion) return;

  /* --------------------------------------------------------------------------
   * 2. Canvas Hạt năng lượng Anime (Mana / Sakura Glow Particles)
   * -------------------------------------------------------------------------- */
  var canvas = document.createElement("canvas");
  canvas.className = "anime-particles-canvas";
  canvas.setAttribute("aria-hidden", "true");
  document.body.prepend(canvas);
  var ctx = canvas.getContext("2d");
  var particles = [];
  var mouse = { x: -9999, y: -9999 };

  function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  window.addEventListener("resize", resizeCanvas, { passive: true });
  resizeCanvas();

  window.addEventListener(
    "mousemove",
    function (e) {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    },
    { passive: true }
  );

  var PARTICLE_COUNT = Math.min(72, Math.max(48, Math.floor(window.innerWidth / 20)));
  for (var i = 0; i < PARTICLE_COUNT; i++) {
    particles.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 2.3 + 0.9,
      vx: (Math.random() - 0.5) * 0.4,
      vy: -Math.random() * 0.6 - 0.18,
      alpha: Math.random() * 0.48 + 0.2,
      hue: Math.random() > 0.45 ? "236, 72, 153" : "139, 92, 246",
      pulse: Math.random() * Math.PI * 2,
    });
  }

  function animateParticles() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (var i = 0; i < particles.length; i++) {
      var p = particles[i];
      p.pulse += 0.025;
      p.x += p.vx + Math.sin(p.pulse) * 0.18;
      p.y += p.vy;

      var dx = p.x - mouse.x;
      var dy = p.y - mouse.y;
      var distSq = dx * dx + dy * dy;
      if (distSq < 14400 && distSq > 1) {
        var dist = Math.sqrt(distSq);
        p.x += (dx / dist) * 0.8;
        p.y += (dy / dist) * 0.8;
      }

      if (p.y < -10) {
        p.y = canvas.height + 10;
        p.x = Math.random() * canvas.width;
      }
      if (p.x < -10) p.x = canvas.width + 10;
      if (p.x > canvas.width + 10) p.x = -10;

      var curAlpha = p.alpha * (0.7 + 0.3 * Math.sin(p.pulse));
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(" + p.hue + "," + curAlpha.toFixed(3) + ")";
      ctx.shadowBlur = 10;
      ctx.shadowColor = "rgba(" + p.hue + ",0.6)";
      ctx.fill();
    }
    requestAnimationFrame(animateParticles);
  }
  requestAnimationFrame(animateParticles);

  /* --------------------------------------------------------------------------
   * 3. Hiệu ứng 3D Tilt & Spotlight theo con trỏ chuột cho Card / KPI / Services
   * -------------------------------------------------------------------------- */
  var tiltCards = document.querySelectorAll(".grid .card, .kpi-card, .services li");
  tiltCards.forEach(function (card) {
    card.classList.add("interactive-tilt");
    var rafId = null;

    card.addEventListener("mousemove", function (e) {
      var rect = card.getBoundingClientRect();
      var x = e.clientX - rect.left;
      var y = e.clientY - rect.top;
      var centerX = rect.width / 2;
      var centerY = rect.height / 2;
      var rotateX = ((y - centerY) / centerY) * -6.5;
      var rotateY = ((x - centerX) / centerX) * 6.5;

      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(function () {
        card.style.setProperty("--mouse-x", x.toFixed(0) + "px");
        card.style.setProperty("--mouse-y", y.toFixed(0) + "px");
        card.style.transform =
          "perspective(900px) translateY(-7px) rotateX(" +
          rotateX.toFixed(2) +
          "deg) rotateY(" +
          rotateY.toFixed(2) +
          "deg) scale3d(1.015, 1.015, 1.015)";
      });
    });

    card.addEventListener("mouseleave", function () {
      if (rafId) cancelAnimationFrame(rafId);
      card.style.transform = "";
    });
  });

  /* Parallax nhẹ cho Hero Banner */
  var hero = document.querySelector(".hero");
  if (hero) {
    hero.addEventListener("mousemove", function (e) {
      var rect = hero.getBoundingClientRect();
      var x = ((e.clientX - rect.left) / rect.width) * 100;
      var y = ((e.clientY - rect.top) / rect.height) * 100;
      hero.style.setProperty("--hero-x", x.toFixed(1) + "%");
      hero.style.setProperty("--hero-y", y.toFixed(1) + "%");
    });
  }

  /* --------------------------------------------------------------------------
   * 4. Scroll Reveal tuần tự (IntersectionObserver Stagger)
   * -------------------------------------------------------------------------- */
  var revealElements = document.querySelectorAll(
    ".grid .card, .services li, .kpi-card, .dashboard-panel, .review-item, .cart-line, .addr"
  );
  if ("IntersectionObserver" in window && revealElements.length) {
    revealElements.forEach(function (el) {
      el.classList.add("reveal-init");
    });

    var observer = new IntersectionObserver(
      function (entries) {
        var visibleBatch = [];
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            visibleBatch.push(entry.target);
            observer.unobserve(entry.target);
          }
        });
        visibleBatch.forEach(function (el, idx) {
          el.style.transitionDelay = Math.min(idx * 55, 380) + "ms";
          el.classList.add("reveal-visible");
          setTimeout(function () {
            el.style.transitionDelay = "";
          }, Math.min(idx * 55, 380) + 600);
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -30px 0px" }
    );

    revealElements.forEach(function (el) {
      observer.observe(el);
    });
  }

  /* --------------------------------------------------------------------------
   * 5. Nút bấm từ tính (Magnetic Button) & Sóng xung kích (Neon Click Ripple)
   * -------------------------------------------------------------------------- */
  document.querySelectorAll(".btn").forEach(function (btn) {
    btn.addEventListener("mousemove", function (e) {
      var rect = btn.getBoundingClientRect();
      var dx = e.clientX - (rect.left + rect.width / 2);
      var dy = e.clientY - (rect.top + rect.height / 2);
      btn.style.transform =
        "translate(" +
        (dx * 0.16).toFixed(1) +
        "px, " +
        (dy * 0.22 - 2).toFixed(1) +
        "px)";
    });
    btn.addEventListener("mouseleave", function () {
      btn.style.transform = "";
    });
    btn.addEventListener("click", function (e) {
      var rect = btn.getBoundingClientRect();
      var ripple = document.createElement("span");
      ripple.className = "btn-ripple";
      var size = Math.max(rect.width, rect.height) * 1.4;
      ripple.style.width = ripple.style.height = size + "px";
      ripple.style.left = e.clientX - rect.left - size / 2 + "px";
      ripple.style.top = e.clientY - rect.top - size / 2 + "px";
      btn.appendChild(ripple);
      setTimeout(function () {
        ripple.remove();
      }, 600);
    });
  });

  /* --------------------------------------------------------------------------
   * 6. Gallery Chi tiết sản phẩm: Chuyển ảnh mượt, Zoom kính lúp & Lightbox
   * -------------------------------------------------------------------------- */
  var mainImg = document.getElementById("main-image");
  var thumbBtns = document.querySelectorAll(".thumbs button[data-src]");
  if (mainImg) {
    if (thumbBtns.length) {
      thumbBtns[0].classList.add("active");
      thumbBtns.forEach(function (btn) {
        btn.addEventListener("click", function () {
          thumbBtns.forEach(function (b) {
            b.classList.remove("active");
          });
          btn.classList.add("active");
          mainImg.classList.remove("switching");
          void mainImg.offsetWidth;
          mainImg.classList.add("switching");
        });
      });
    }

    /* Click vào ảnh chính để mở Lightbox toàn màn hình */
    mainImg.style.cursor = "zoom-in";
    mainImg.addEventListener("click", function () {
      var overlay = document.createElement("div");
      overlay.className = "lightbox-overlay";
      overlay.innerHTML =
        '<button type="button" class="lightbox-close" aria-label="Đóng">×</button>' +
        '<img class="lightbox-img" src="' +
        mainImg.src +
        '" alt="' +
        (mainImg.alt || "") +
        '">';
      document.body.appendChild(overlay);

      function closeLightbox() {
        overlay.classList.add("closing");
        setTimeout(function () {
          overlay.remove();
        }, 220);
      }
      overlay.addEventListener("click", function (e) {
        if (e.target === overlay || e.target.classList.contains("lightbox-close")) {
          closeLightbox();
        }
      });
      document.addEventListener(
        "keydown",
        function onKey(e) {
          if (e.key === "Escape") {
            closeLightbox();
            document.removeEventListener("keydown", onKey);
          }
        }
      );
    });
  }

  /* --------------------------------------------------------------------------
   * 7. Hiệu ứng chạy số (Count-Up) & Thanh biểu đồ tỉ lệ cho Dashboard
   * -------------------------------------------------------------------------- */
  document.querySelectorAll(".stat-table").forEach(function (table) {
    var bars = table.querySelectorAll(".stat-bar-fill[data-bar-val]");
    var maxVal = 0;
    bars.forEach(function (b) {
      var v = parseFloat(String(b.dataset.barVal).replace(/,/g, "")) || 0;
      if (v > maxVal) maxVal = v;
    });
    if (maxVal > 0) {
      setTimeout(function () {
        bars.forEach(function (b) {
          var v = parseFloat(String(b.dataset.barVal).replace(/,/g, "")) || 0;
          var pct = Math.max(6, Math.round((v / maxVal) * 100));
          b.style.width = pct + "%";
        });
      }, 150);
    }
  });

  document.querySelectorAll(".kpi-value").forEach(function (el) {
    var rawText = el.textContent.trim();
    var match = rawText.match(/^([\d.,]+)(.*)$/);
    if (!match) return;
    var numStr = match[1].replace(/[.,]/g, "");
    var target = parseInt(numStr, 10);
    var suffix = match[2] || "";
    if (isNaN(target) || target <= 0) return;

    var startTime = performance.now();
    var duration = 1100;
    function step(now) {
      var t = Math.min((now - startTime) / duration, 1);
      var eased = 1 - Math.pow(1 - t, 3);
      var current = Math.round(target * eased);
      el.textContent = current.toLocaleString("vi-VN") + suffix;
      if (t < 1) requestAnimationFrame(step);
      else el.textContent = rawText;
    }
    requestAnimationFrame(step);
  });

  /* --------------------------------------------------------------------------
   * 8. Hiệu ứng 1: Ảnh bay vào Giỏ hàng theo đường cong Parabol (Fly-to-Cart)
   * -------------------------------------------------------------------------- */
  var addToCartForm = document.querySelector("form.add-to-cart");
  var cartLink = document.querySelector(".cart-link");
  if (addToCartForm && mainImg && cartLink) {
    var isSubmittingCart = false;
    addToCartForm.addEventListener("submit", function (e) {
      if (isSubmittingCart) return;
      e.preventDefault();
      isSubmittingCart = true;

      var imgRect = mainImg.getBoundingClientRect();
      var cartRect = cartLink.getBoundingClientRect();

      var startX = imgRect.left + imgRect.width / 2 - 34;
      var startY = imgRect.top + imgRect.height / 2 - 34;
      var endX = cartRect.left + cartRect.width / 2 - 14;
      var endY = cartRect.top + cartRect.height / 2 - 14;

      var flyer = document.createElement("img");
      flyer.src = mainImg.src;
      flyer.className = "fly-to-cart-clone";
      flyer.style.left = startX + "px";
      flyer.style.top = startY + "px";
      document.body.appendChild(flyer);

      var startTime = performance.now();
      var duration = 560;
      /* Điểm đỉnh đường cong Parabol cao hơn điểm đầu & cuối */
      var ctrlX = (startX + endX) / 2;
      var ctrlY = Math.min(startY, endY) - 130;

      function animateFly(now) {
        var t = Math.min((now - startTime) / duration, 1);
        var inv = 1 - t;
        /* Đường cong Bézier bậc 2 (Parabol) */
        var x = inv * inv * startX + 2 * inv * t * ctrlX + t * t * endX;
        var y = inv * inv * startY + 2 * inv * t * ctrlY + t * t * endY;
        var scale = 1 - t * 0.68;
        var rot = t * 360;

        flyer.style.left = x.toFixed(1) + "px";
        flyer.style.top = y.toFixed(1) + "px";
        flyer.style.transform =
          "scale(" + scale.toFixed(2) + ") rotate(" + rot.toFixed(0) + "deg)";
        flyer.style.opacity = (1 - t * 0.25).toFixed(2);

        if (t < 1) {
          requestAnimationFrame(animateFly);
        } else {
          flyer.remove();
          cartLink.classList.add("cart-bounce");
          setTimeout(function () {
            addToCartForm.submit();
          }, 160);
        }
      }
      requestAnimationFrame(animateFly);
    });
  }

  /* --------------------------------------------------------------------------
   * 9. Hiệu ứng 3: Bộ chọn 5 Ngôi sao đánh giá tương tác (Interactive Star Picker)
   * -------------------------------------------------------------------------- */
  var ratingSelect = document.querySelector('.review-form select[name="rating"]');
  if (ratingSelect) {
    var starLabels = {
      1: "1/5 - Rất tệ",
      2: "2/5 - Chưa tốt",
      3: "3/5 - Bình thường",
      4: "4/5 - Hài lòng",
      5: "5/5 - Tuyệt vời!",
    };
    var picker = document.createElement("div");
    picker.className = "star-picker";
    var currentVal = parseInt(ratingSelect.value, 10) || 5;
    var stars = [];

    var caption = document.createElement("span");
    caption.className = "star-picker-caption";

    function renderStars(activeVal) {
      stars.forEach(function (btn, idx) {
        btn.classList.toggle("lit", idx + 1 <= activeVal);
      });
      caption.textContent = starLabels[activeVal] || activeVal + "/5";
    }

    for (var s = 1; s <= 5; s++) {
      (function (score) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "star-btn";
        btn.setAttribute("aria-label", score + " sao");
        btn.textContent = "★";
        btn.addEventListener("mouseenter", function () {
          renderStars(score);
        });
        btn.addEventListener("click", function () {
          currentVal = score;
          ratingSelect.value = String(score);
          renderStars(currentVal);
        });
        stars.push(btn);
        picker.appendChild(btn);
      })(s);
    }

    picker.addEventListener("mouseleave", function () {
      renderStars(currentVal);
    });

    picker.appendChild(caption);
    ratingSelect.classList.add("sr-only-select");
    ratingSelect.parentNode.insertBefore(picker, ratingSelect.nextSibling);
    renderStars(currentVal);
  }

  /* --------------------------------------------------------------------------
   * 10. Hiệu ứng 4: Cụm nút Tăng / Giảm số lượng [-] [+] (Quantity Stepper)
   * -------------------------------------------------------------------------- */
  document
    .querySelectorAll('.add-to-cart input[type="number"], .cart-qty input[type="number"]')
    .forEach(function (input) {
      if (input.parentNode.classList.contains("qty-stepper")) return;
      var wrapper = document.createElement("div");
      wrapper.className = "qty-stepper";

      var minusBtn = document.createElement("button");
      minusBtn.type = "button";
      minusBtn.className = "qty-btn";
      minusBtn.setAttribute("aria-label", "Giảm số lượng");
      minusBtn.textContent = "−";

      var plusBtn = document.createElement("button");
      plusBtn.type = "button";
      plusBtn.className = "qty-btn";
      plusBtn.setAttribute("aria-label", "Tăng số lượng");
      plusBtn.textContent = "+";

      input.parentNode.insertBefore(wrapper, input);
      wrapper.appendChild(minusBtn);
      wrapper.appendChild(input);
      wrapper.appendChild(plusBtn);

      function syncLimits() {
        var val = parseInt(input.value, 10) || 1;
        var min = parseInt(input.min, 10) || 1;
        var max = parseInt(input.max, 10) || 9999;
        minusBtn.disabled = val <= min;
        plusBtn.disabled = val >= max;
      }

      function stepValue(delta) {
        var val = parseInt(input.value, 10) || 1;
        var min = parseInt(input.min, 10) || 1;
        var max = parseInt(input.max, 10) || 9999;
        var next = Math.min(max, Math.max(min, val + delta));
        if (next !== val) {
          input.value = next;
          input.classList.remove("qty-pop");
          void input.offsetWidth;
          input.classList.add("qty-pop");
        }
        syncLimits();
      }

      minusBtn.addEventListener("click", function () {
        stepValue(-1);
      });
      plusBtn.addEventListener("click", function () {
        stepValue(1);
      });
      input.addEventListener("input", syncLimits);
      syncLimits();
    });

  /* --------------------------------------------------------------------------
   * 11. Hiệu ứng 5: Thông báo Toast có thanh đếm ngược 5 giây & nút đóng [×]
   * -------------------------------------------------------------------------- */
  document.querySelectorAll(".messages li").forEach(function (toast, idx) {
    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "toast-close";
    closeBtn.setAttribute("aria-label", "Đóng thông báo");
    closeBtn.textContent = "×";

    var timerBar = document.createElement("span");
    timerBar.className = "toast-timer";

    toast.appendChild(closeBtn);
    toast.appendChild(timerBar);

    function dismissToast() {
      if (toast.classList.contains("toast-leaving")) return;
      toast.classList.add("toast-leaving");
      setTimeout(function () {
        toast.remove();
      }, 280);
    }

    closeBtn.addEventListener("click", dismissToast);
    setTimeout(dismissToast, 5000 + idx * 400);
  });
})();
