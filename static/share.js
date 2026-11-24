(function () {
  "use strict";
  // JSON comes from a non-executing <script type="application/json"> block; Jinja escaped "<" etc.
  const data = JSON.parse(document.getElementById("shareData").textContent);
  document.getElementById("shareTitle").textContent = data.conversation.title;

  const list = document.getElementById("messages");
  for (const m of data.messages) {
    const wrap = document.createElement("div");
    wrap.className = "msg " + (m.role === "user" ? "user" : "bot");
    const body = document.createElement("div");
    body.className = "msg-body";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.dir = "auto";
    if (m.role === "user") bubble.textContent = m.content;
    else bubble.innerHTML = window.MD.render(m.content);
    body.appendChild(bubble);
    if (m.sources && m.sources.length) {
      const d = document.createElement("details");
      d.className = "sources";
      const s = document.createElement("summary");
      s.textContent = "Sources (" + m.sources.length + ")";
      const ol = document.createElement("ol");
      for (const src of m.sources) {
        const li = document.createElement("li");
        const st = document.createElement("strong");
        st.textContent = src.title + (src.page ? " · p. " + src.page : "");
        const sp = document.createElement("span");
        sp.textContent = src.snippet;
        li.append(st, sp);
        ol.appendChild(li);
      }
      d.append(s, ol);
      body.appendChild(d);
    }
    wrap.appendChild(body);
    list.appendChild(wrap);
  }
  document.getElementById("printBtn").addEventListener("click", () => {
    document.querySelectorAll(".sources").forEach((d) => { d.open = true; });
    window.print();
  });
})();
