// Applies the saved theme before first paint (kept tiny; CSP forbids inline scripts).
(function () {
  try {
    var t = localStorage.getItem("medibot-theme");
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
  } catch (e) { /* storage blocked: follow system theme */ }
})();
