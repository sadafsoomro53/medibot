/* Interactive medical-themed background.
 * Floating crosses, rings, pills and molecule hexagons drift slowly, shift with the cursor
 * (parallax), get nudged away from it, link up with thin "molecule" lines, and ripple on click.
 * Exposes window.medibotBg.pulse(x?, y?) so the chat can trigger a wave while the bot is thinking.
 */
(function () {
  "use strict";

  const canvas = document.getElementById("bg-canvas");
  if (!canvas || !canvas.getContext) return;
  const ctx = canvas.getContext("2d");
  const host = canvas.parentElement;

  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const TYPES = ["cross", "ring", "pill", "hex", "dot", "cross", "dot", "hex"];

  let W = 0, H = 0, DPR = 1;
  let shapes = [];
  let ripples = [];
  let colors = {};
  let running = false;
  let lastT = 0;

  // Pointer state (target and smoothed), in canvas CSS pixels.
  const mouse = { x: 0, y: 0, sx: 0, sy: 0, active: false, glow: 0 };

  // ------------------------------------------------------------------ colours from CSS tokens
  function readColors() {
    const cs = getComputedStyle(document.documentElement);
    const get = (n, fb) => (cs.getPropertyValue(n).trim() || fb);
    colors = {
      accent: get("--accent", "#0f766e"),
      accent2: get("--accent-2", "#38bdf8"),
      accent3: get("--accent-3", "#f472b6"),
      line: get("--bg-line", "rgba(15,118,110,.18)"),
      glow: get("--bg-glow", "rgba(45,212,191,.16)"),
    };
  }

  // ------------------------------------------------------------------ setup
  function resize() {
    const r = host.getBoundingClientRect();
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    W = Math.max(1, r.width);
    H = Math.max(1, r.height);
    canvas.width = Math.round(W * DPR);
    canvas.height = Math.round(H * DPR);
    canvas.style.width = W + "px";
    canvas.style.height = H + "px";
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);

    const target = Math.round(Math.min(70, Math.max(18, (W * H) / 22000)));
    while (shapes.length < target) shapes.push(makeShape(true));
    if (shapes.length > target) shapes.length = target;
    if (!running) draw(0);
  }

  function rand(a, b) { return a + Math.random() * (b - a); }

  function makeShape(anywhere) {
    const depth = rand(0.35, 1); // 1 = close (bigger, faster parallax)
    const type = TYPES[(Math.random() * TYPES.length) | 0];
    const palette = Math.random();
    return {
      type,
      x: anywhere ? rand(0, W) : rand(-40, W + 40),
      y: anywhere ? rand(0, H) : H + 40,
      // base drift: slow upward float with slight sideways wander
      dx: rand(-0.08, 0.08) * depth,
      dy: rand(-0.22, -0.06) * depth,
      vx: 0, vy: 0,                         // extra velocity from cursor / ripples
      size: (type === "dot" ? rand(2, 4) : rand(9, 22)) * (0.6 + depth * 0.6),
      rot: rand(0, Math.PI * 2),
      vr: rand(-0.004, 0.004),
      depth,
      alpha: rand(0.25, 0.6) * (0.5 + depth * 0.5),
      color: palette < 0.6 ? "accent" : palette < 0.85 ? "accent2" : "accent3",
      phase: rand(0, Math.PI * 2),
    };
  }

  // ------------------------------------------------------------------ drawing primitives
  function roundRectPath(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function drawShape(s, px, py, t) {
    const breathe = 1 + Math.sin(t * 0.0012 + s.phase) * 0.06;
    const r = s.size * breathe;
    ctx.save();
    ctx.translate(px, py);
    ctx.rotate(s.rot);
    ctx.globalAlpha = s.alpha;
    ctx.strokeStyle = ctx.fillStyle = colors[s.color];
    ctx.lineWidth = Math.max(1.2, r * 0.14);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    switch (s.type) {
      case "cross": {
        const a = r * 0.34;
        roundRectPath(-a, -r, a * 2, r * 2, a * 0.6);
        ctx.globalAlpha = s.alpha * 0.55;
        ctx.fill();
        roundRectPath(-r, -a, r * 2, a * 2, a * 0.6);
        ctx.fill();
        break;
      }
      case "ring":
        ctx.beginPath();
        ctx.arc(0, 0, r, 0, Math.PI * 2);
        ctx.stroke();
        ctx.globalAlpha = s.alpha * 0.5;
        ctx.beginPath();
        ctx.arc(0, 0, r * 0.35, 0, Math.PI * 2);
        ctx.fill();
        break;
      case "pill": {
        const w = r * 2.2, h = r * 0.95;
        roundRectPath(-w / 2, -h / 2, w, h, h / 2);
        ctx.stroke();
        ctx.save();
        ctx.clip();
        ctx.globalAlpha = s.alpha * 0.45;
        ctx.fillRect(0, -h / 2, w / 2, h);
        ctx.restore();
        break;
      }
      case "hex":
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
          const ang = (Math.PI / 3) * i;
          const hx = Math.cos(ang) * r, hy = Math.sin(ang) * r;
          i ? ctx.lineTo(hx, hy) : ctx.moveTo(hx, hy);
        }
        ctx.closePath();
        ctx.stroke();
        ctx.globalAlpha = s.alpha * 0.9;
        for (let i = 0; i < 6; i += 2) {
          const ang = (Math.PI / 3) * i;
          ctx.beginPath();
          ctx.arc(Math.cos(ang) * r, Math.sin(ang) * r, ctx.lineWidth * 1.1, 0, Math.PI * 2);
          ctx.fill();
        }
        break;
      default: // dot
        ctx.beginPath();
        ctx.arc(0, 0, r, 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.restore();
  }

  // ------------------------------------------------------------------ frame
  function step(dt, t) {
    const k = dt / 16.67; // normalise to 60fps
    mouse.sx += (mouse.x - mouse.sx) * 0.08 * k;
    mouse.sy += (mouse.y - mouse.sy) * 0.08 * k;
    mouse.glow += ((mouse.active ? 1 : 0) - mouse.glow) * 0.06 * k;

    for (const s of shapes) {
      // cursor repulsion (soft, stronger for nearer shapes)
      if (mouse.active) {
        const ddx = s.x - mouse.x, ddy = s.y - mouse.y;
        const d2 = ddx * ddx + ddy * ddy;
        const R = 150;
        if (d2 < R * R && d2 > 0.01) {
          const d = Math.sqrt(d2);
          const f = (1 - d / R) * 0.35 * s.depth;
          s.vx += (ddx / d) * f * k;
          s.vy += (ddy / d) * f * k;
          s.vr += (ddx > 0 ? 1 : -1) * 0.0004 * f;
        }
      }
      // ripple shock-waves
      for (const rp of ripples) {
        const ddx = s.x - rp.x, ddy = s.y - rp.y;
        const d = Math.sqrt(ddx * ddx + ddy * ddy) || 1;
        if (Math.abs(d - rp.r) < 30) {
          const f = rp.strength * (1 - rp.r / rp.max) * s.depth;
          s.vx += (ddx / d) * f * k;
          s.vy += (ddy / d) * f * k;
        }
      }

      s.vx *= Math.pow(0.94, k);
      s.vy *= Math.pow(0.94, k);
      s.vr = s.vr * Math.pow(0.995, k);
      if (Math.abs(s.vr) < 0.0015) s.vr += (Math.random() - 0.5) * 0.0002;

      s.x += (s.dx + s.vx) * k;
      s.y += (s.dy + s.vy) * k + Math.sin(t * 0.0006 + s.phase) * 0.05 * k;
      s.rot += s.vr * k;

      // wrap around edges
      if (s.y < -50) { Object.assign(s, makeShape(false)); }
      if (s.y > H + 60) s.y = -40;
      if (s.x < -60) s.x = W + 50;
      if (s.x > W + 60) s.x = -50;
    }

    for (const rp of ripples) rp.r += rp.speed * k;
    ripples = ripples.filter((rp) => rp.r < rp.max);
  }

  function draw(t) {
    ctx.clearRect(0, 0, W, H);

    // cursor glow
    if (mouse.glow > 0.01) {
      const g = ctx.createRadialGradient(mouse.sx, mouse.sy, 0, mouse.sx, mouse.sy, 260);
      g.addColorStop(0, colors.glow);
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.globalAlpha = mouse.glow;
      ctx.fillStyle = g;
      ctx.fillRect(mouse.sx - 260, mouse.sy - 260, 520, 520);
      ctx.globalAlpha = 1;
    }

    // parallax offset: nearer shapes move more opposite to the cursor
    const cx = (mouse.sx - W / 2) / (W / 2 || 1);
    const cy = (mouse.sy - H / 2) / (H / 2 || 1);
    const par = mouse.active || mouse.glow > 0.01 ? 26 : 0;
    const pos = shapes.map((s) => [s.x - cx * par * s.depth * mouse.glow, s.y - cy * par * s.depth * mouse.glow]);

    // molecule links between close shapes, and to the cursor
    ctx.strokeStyle = colors.line;
    ctx.lineWidth = 1;
    const LINK = 130;
    for (let i = 0; i < shapes.length; i++) {
      const [ax, ay] = pos[i];
      for (let j = i + 1; j < shapes.length; j++) {
        if (Math.abs(shapes[i].depth - shapes[j].depth) > 0.35) continue;
        const [bx, by] = pos[j];
        const dx = ax - bx, dy = ay - by;
        const d2 = dx * dx + dy * dy;
        if (d2 < LINK * LINK) {
          ctx.globalAlpha = (1 - Math.sqrt(d2) / LINK) * 0.9;
          ctx.beginPath();
          ctx.moveTo(ax, ay);
          ctx.lineTo(bx, by);
          ctx.stroke();
        }
      }
      if (mouse.glow > 0.05) {
        const dx = ax - mouse.sx, dy = ay - mouse.sy;
        const d2 = dx * dx + dy * dy;
        if (d2 < 190 * 190) {
          ctx.globalAlpha = (1 - Math.sqrt(d2) / 190) * mouse.glow;
          ctx.beginPath();
          ctx.moveTo(ax, ay);
          ctx.lineTo(mouse.sx, mouse.sy);
          ctx.stroke();
        }
      }
    }
    ctx.globalAlpha = 1;

    // ripples
    for (const rp of ripples) {
      ctx.globalAlpha = (1 - rp.r / rp.max) * 0.5;
      ctx.strokeStyle = colors.accent;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(rp.x, rp.y, rp.r, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    for (let i = 0; i < shapes.length; i++) drawShape(shapes[i], pos[i][0], pos[i][1], t);
  }

  function loop(t) {
    if (!running) return;
    const dt = Math.min(50, t - (lastT || t));
    lastT = t;
    step(dt || 16.67, t);
    draw(t);
    requestAnimationFrame(loop);
  }

  function start() {
    if (running || reduceMotion.matches || document.hidden) return;
    running = true;
    lastT = 0;
    requestAnimationFrame(loop);
  }

  function stop() { running = false; }

  // ------------------------------------------------------------------ events
  function toLocal(e) {
    const r = canvas.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top, inside: e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom };
  }

  window.addEventListener("pointermove", (e) => {
    const p = toLocal(e);
    if (!mouse.active && p.inside) { mouse.sx = p.x; mouse.sy = p.y; }
    mouse.x = p.x; mouse.y = p.y;
    mouse.active = p.inside;
  }, { passive: true });
  document.addEventListener("pointerleave", () => { mouse.active = false; });
  window.addEventListener("blur", () => { mouse.active = false; });

  // Ripple when clicking empty space (not on buttons, inputs or messages).
  host.addEventListener("pointerdown", (e) => {
    if (e.target.closest("button, a, input, textarea, .bubble, .suggestion, .composer")) return;
    const p = toLocal(e);
    pulse(p.x, p.y);
  });

  function pulse(x, y) {
    if (reduceMotion.matches) return;
    ripples.push({
      x: x ?? W / 2, y: y ?? H * 0.45,
      r: 0, max: Math.max(W, H) * 0.6, speed: 6, strength: 0.9,
    });
    if (ripples.length > 6) ripples.shift();
  }

  window.addEventListener("resize", resize);
  if ("ResizeObserver" in window) new ResizeObserver(resize).observe(host);
  document.addEventListener("visibilitychange", () => (document.hidden ? stop() : start()));
  reduceMotion.addEventListener("change", () => (reduceMotion.matches ? (stop(), draw(0)) : start()));

  // re-read colours whenever the theme changes
  new MutationObserver(() => { readColors(); if (!running) draw(0); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { readColors(); if (!running) draw(0); });

  window.medibotBg = { pulse };

  readColors();
  resize();
  start();
})();
