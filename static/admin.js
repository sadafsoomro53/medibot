(function () {
  "use strict";
  const bars = document.getElementById("bars");
  const tip = document.getElementById("barTip");
  if (!bars) return;

  // Grow bars to their height (data-h = % of peak).
  requestAnimationFrame(() => {
    bars.querySelectorAll(".bar").forEach((b) => { b.style.height = (parseFloat(b.dataset.h) || 0) + "%"; });
  });

  function show(col) {
    const n = Number(col.dataset.count);
    tip.textContent = col.dataset.label + " · " + n + (n === 1 ? " answer" : " answers");
    const r = col.getBoundingClientRect(), host = bars.getBoundingClientRect();
    const bar = col.querySelector(".bar").getBoundingClientRect();
    tip.style.left = (r.left - host.left + r.width / 2) + "px";
    tip.style.top = (Math.min(bar.top, r.bottom - 4) - host.top - 6) + "px";
    tip.hidden = false;
  }
  bars.querySelectorAll(".bar-col").forEach((col) => {
    col.addEventListener("pointerenter", () => show(col));
    col.addEventListener("focus", () => show(col));
    col.addEventListener("pointerleave", () => { tip.hidden = true; });
    col.addEventListener("blur", () => { tip.hidden = true; });
  });

  const toggle = document.getElementById("toggleTable");
  const table = document.getElementById("dayTable");
  toggle.addEventListener("click", () => {
    const show = table.hidden;
    table.hidden = !show;
    toggle.setAttribute("aria-pressed", String(show));
    toggle.textContent = show ? "Hide table" : "Show table";
  });
})();
