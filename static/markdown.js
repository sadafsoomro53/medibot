/* Minimal, safe Markdown renderer shared by the chat and share pages.
 * Text is HTML-escaped FIRST; the transforms afterwards only ever add a fixed set of tags. */
(function () {
  "use strict";

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function inline(s) {
    return s
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/__([^_]+)__/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  }

  function render(text) {
    const lines = escapeHtml(text || "").split(/\r?\n/);
    let html = "", list = null, para = [];
    const flushPara = () => { if (para.length) { html += "<p>" + inline(para.join("<br>")) + "</p>"; para = []; } };
    const closeList = () => { if (list) { html += "</" + list + ">"; list = null; } };

    for (const raw of lines) {
      const line = raw.trim();
      let m;
      if (!line) { flushPara(); closeList(); continue; }
      if ((m = line.match(/^#{1,6}\s+(.*)$/))) {
        flushPara(); closeList();
        html += "<h4>" + inline(m[1]) + "</h4>";
      } else if ((m = line.match(/^[-*•]\s+(.*)$/))) {
        flushPara();
        if (list !== "ul") { closeList(); html += "<ul>"; list = "ul"; }
        html += "<li>" + inline(m[1]) + "</li>";
      } else if ((m = line.match(/^\d+[.)]\s+(.*)$/))) {
        flushPara();
        if (list !== "ol") { closeList(); html += "<ol>"; list = "ol"; }
        html += "<li>" + inline(m[1]) + "</li>";
      } else if (/^-{3,}$/.test(line)) {
        flushPara(); closeList();
      } else {
        closeList();
        para.push(line);
      }
    }
    flushPara(); closeList();
    return html;
  }

  window.MD = { render, escapeHtml };
})();
