/* MediBot front-end. No inline handlers (CSP); all user/bot text is escaped before rendering. */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const app = $("#app");
  const MAX_CHARS = parseInt(app.dataset.maxChars, 10) || 1000;
  const CSRF = document.querySelector('meta[name="csrf-token"]').content;
  const parseJSON = (s, fb) => { try { return JSON.parse(s); } catch (e) { return fb; } };
  const USER = parseJSON(app.dataset.user, null);
  const GOOGLE = app.dataset.google === "true";
  const EMERGENCY_NUMBERS = parseJSON(app.dataset.emergency, []);

  // ------------------------------------------------------------------ i18n
  const STRINGS = {
    en: {
      newChat: "New chat", symptomChecker: "Symptom checker", labReport: "Explain lab report",
      medicineLookup: "Medicine lookup", searchChats: "Search chats", theme: "Theme", install: "Install app",
      clearHistory: "Clear history", share: "Share", exportPdf: "Export PDF",
      emergencyTitle: "This may be an emergency.", emergencyText: "If you or someone else is in danger, call emergency services now.",
      welcomeTitle: "How can I help you", today: "today?",
      welcomeText: "Ask about diseases, symptoms, tests or treatments. Answers cite pages from trusted medical references.",
      symptomSub: "Answer a few questions to see what care you may need", labSub: "Upload a PDF or photo of your test results",
      attach: "Upload lab report", placeholder: "Ask a medical question…", speak: "Speak",
      disclaimer: "MediBot gives general information, not medical advice. Always consult a qualified doctor. In an emergency, call your local emergency number.",
      authTitle: "Save your chats on every device", login: "Log in", signup: "Sign up", name: "Name", email: "Email",
      password: "Password", passwordHint: "At least 8 characters, with a capital letter and a number.", google: "Continue with Google",
      labIntro: "Upload a PDF, or a clear photo or screenshot of your report (max 5 MB). The file is only used to create the explanation and is not stored.",
      dropText: "Click to choose a file, or drop it here", labNote: "Anything to add? (optional)", labNotePh: "e.g. I'm 45, feeling tired lately",
      explain: "Explain my report", medPh: "Medicine name, e.g. ibuprofen, paracetamol", search: "Search",
      medNote: "Source: U.S. FDA drug labels (openFDA). Dosage is not shown. Ask your doctor or pharmacist before taking any medicine.",
      shareTitle: "Share this chat", shareText: "Anyone with the link can read this conversation (read-only). You can turn the link off at any time.",
      copy: "Copy", copied: "Copied", stopSharing: "Stop sharing", sources: "Sources", page: "p.",
      emptyHistory: "Your conversations will appear here.", noMatch: "No chats match your search.",
      today_g: "Today", yesterday: "Yesterday", prev7: "Previous 7 days", prev30: "Previous 30 days", older: "Older",
      online: "Online", starting: "Starting AI…", offline: "Offline", connecting: "Connecting…",
      logout: "Log out", admin: "Admin dashboard", guestNote: "Log in to keep your chats on every device.", loginSignup: "Log in / Sign up",
      retry: "Retry", listen: "Listen", stop: "Stop", helpful: "Helpful", notHelpful: "Not helpful", thanks: "Thanks for the feedback!",
      symptomStart: "I'd like to check my symptoms.", symptomMode: "Symptom check", labsMode: "Lab report",
      deleteConfirm: 'Delete "%s"? This cannot be undone.', clearConfirm: "Delete all of your chats? This cannot be undone.",
      deleted: "Chat deleted.", cleared: "History cleared.", noChats: "No chats to clear.", tooLong: "Message is too long.",
      listening: "Listening… speak now", micDenied: "Microphone access was blocked.", shareFirst: "Send a message first, then share the chat.",
      linkOff: "Sharing turned off.", rename: "Rename chat", del: "Delete chat",
    },
    ur: {
      newChat: "نئی گفتگو", symptomChecker: "علامات کی جانچ", labReport: "لیب رپورٹ سمجھیں",
      medicineLookup: "دوائی کی معلومات", searchChats: "گفتگو تلاش کریں", theme: "تھیم", install: "ایپ انسٹال کریں",
      clearHistory: "تاریخ صاف کریں", share: "شیئر کریں", exportPdf: "پی ڈی ایف بنائیں",
      emergencyTitle: "یہ ایمرجنسی ہو سکتی ہے۔", emergencyText: "اگر آپ یا کوئی اور خطرے میں ہے تو فوراً ایمرجنسی سروس کو کال کریں۔",
      welcomeTitle: "آج میں آپ کی", today: "کیا مدد کروں؟",
      welcomeText: "بیماریوں، علامات، ٹیسٹ یا علاج کے بارے میں پوچھیں۔ جوابات میں معتبر طبی کتابوں کے صفحات کا حوالہ دیا جاتا ہے۔",
      symptomSub: "چند سوالوں کے جواب دیں اور جانیں کہ آپ کو کس قسم کی دیکھ بھال چاہیے", labSub: "اپنی ٹیسٹ رپورٹ کی پی ڈی ایف یا تصویر اپ لوڈ کریں",
      attach: "لیب رپورٹ اپ لوڈ کریں", placeholder: "اپنا طبی سوال لکھیں…", speak: "بول کر پوچھیں",
      disclaimer: "میڈی بوٹ عمومی معلومات دیتا ہے، طبی مشورہ نہیں۔ ہمیشہ مستند ڈاکٹر سے رجوع کریں۔ ایمرجنسی میں 1122 پر کال کریں۔",
      authTitle: "اپنی گفتگو ہر ڈیوائس پر محفوظ رکھیں", login: "لاگ ان", signup: "سائن اپ", name: "نام", email: "ای میل",
      password: "پاس ورڈ", passwordHint: "کم از کم 8 حروف، ایک بڑا حرف اور ایک عدد۔", google: "گوگل کے ساتھ جاری رکھیں",
      labIntro: "پی ڈی ایف یا رپورٹ کی واضح تصویر اپ لوڈ کریں (زیادہ سے زیادہ 5 MB)۔ فائل محفوظ نہیں کی جاتی۔",
      dropText: "فائل منتخب کرنے کے لیے کلک کریں یا یہاں چھوڑیں", labNote: "کچھ اور بتانا چاہیں؟ (اختیاری)", labNotePh: "مثلاً میری عمر 45 ہے، تھکاوٹ رہتی ہے",
      explain: "رپورٹ سمجھائیں", medPh: "دوائی کا نام، مثلاً ibuprofen، paracetamol", search: "تلاش",
      medNote: "ماخذ: امریکی FDA دوائی لیبل (openFDA)۔ خوراک نہیں دکھائی جاتی۔ کوئی بھی دوا لینے سے پہلے ڈاکٹر یا فارماسسٹ سے پوچھیں۔",
      shareTitle: "یہ گفتگو شیئر کریں", shareText: "لنک رکھنے والا کوئی بھی شخص یہ گفتگو پڑھ سکتا ہے۔ آپ کسی بھی وقت لنک بند کر سکتے ہیں۔",
      copy: "کاپی", copied: "کاپی ہو گیا", stopSharing: "شیئرنگ بند کریں", sources: "حوالہ جات", page: "صفحہ",
      emptyHistory: "آپ کی گفتگو یہاں نظر آئے گی۔", noMatch: "کوئی گفتگو نہیں ملی۔",
      today_g: "آج", yesterday: "کل", prev7: "پچھلے 7 دن", prev30: "پچھلے 30 دن", older: "پرانی",
      online: "آن لائن", starting: "AI شروع ہو رہا ہے…", offline: "آف لائن", connecting: "رابطہ ہو رہا ہے…",
      logout: "لاگ آؤٹ", admin: "ایڈمن ڈیش بورڈ", guestNote: "اپنی گفتگو ہر ڈیوائس پر رکھنے کے لیے لاگ ان کریں۔", loginSignup: "لاگ ان / سائن اپ",
      retry: "دوبارہ کوشش", listen: "سنیں", stop: "روکیں", helpful: "مفید", notHelpful: "مفید نہیں", thanks: "رائے کا شکریہ!",
      symptomStart: "میں اپنی علامات کی جانچ کرنا چاہتا/چاہتی ہوں۔", symptomMode: "علامات کی جانچ", labsMode: "لیب رپورٹ",
      deleteConfirm: '"%s" حذف کریں؟ یہ واپس نہیں ہو سکتا۔', clearConfirm: "اپنی تمام گفتگو حذف کریں؟ یہ واپس نہیں ہو سکتا۔",
      deleted: "گفتگو حذف ہو گئی۔", cleared: "تاریخ صاف ہو گئی۔", noChats: "کوئی گفتگو نہیں۔", tooLong: "پیغام بہت لمبا ہے۔",
      listening: "سن رہا ہوں… بولیں", micDenied: "مائیکروفون کی اجازت نہیں ملی۔", shareFirst: "پہلے کوئی پیغام بھیجیں، پھر شیئر کریں۔",
      linkOff: "شیئرنگ بند ہو گئی۔", rename: "نام تبدیل کریں", del: "حذف کریں",
    },
  };
  let lang = "en";
  try { if (localStorage.getItem("medibot-lang") === "ur") lang = "ur"; } catch (e) { /* ignore */ }
  const t = (k) => (STRINGS[lang] && STRINGS[lang][k]) || STRINGS.en[k] || k;

  function applyLanguage() {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ur" ? "rtl" : "ltr";
    document.querySelectorAll("[data-i18n]").forEach((n) => { n.textContent = t(n.dataset.i18n); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((n) => { n.placeholder = t(n.dataset.i18nPlaceholder); });
    document.querySelectorAll("[data-i18n-title]").forEach((n) => { n.title = t(n.dataset.i18nTitle); n.setAttribute("aria-label", n.title); });
    $("#langLabel").textContent = lang === "ur" ? "English" : "اردو";
    renderAccount();
    renderHistory();
    renderEmergencyNumbers();
  }

  // ------------------------------------------------------------------ elements & state
  const el = {
    sidebar: $("#sidebar"), scrim: $("#scrim"), openSidebar: $("#openSidebar"), closeSidebar: $("#closeSidebar"),
    newChat: $("#newChat"), search: $("#searchChats"), historyList: $("#historyList"), historyEmpty: $("#historyEmpty"),
    clearAll: $("#clearAll"), themeToggle: $("#themeToggle"), langToggle: $("#langToggle"), installApp: $("#installApp"),
    account: $("#account"), title: $("#chatTitle"), modeBadge: $("#modeBadge"), status: $("#status"),
    chatActions: $("#chatActions"), shareBtn: $("#shareBtn"), exportBtn: $("#exportBtn"),
    thread: $("#thread"), welcome: $("#welcome"), messages: $("#messages"), suggestions: $("#suggestions"),
    emergency: $("#emergency"), emergencyNumbers: $("#emergencyNumbers"), emergencyClose: $("#emergencyClose"),
    followups: $("#followups"), form: $("#composer"), input: $("#input"), send: $("#send"), counter: $("#counter"),
    attachBtn: $("#attachBtn"), micBtn: $("#micBtn"), toast: $("#toast"),
  };
  const state = { convId: null, conv: null, conversations: [], sending: false, newMode: "chat" };

  const ICONS = {
    bot: '<svg viewBox="0 0 24 24"><path d="M10 3h4v7h7v4h-7v7h-4v-7H3v-4h7z"/></svg>',
    copy: '<svg viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 012-2h10"/></svg>',
    check: '<svg viewBox="0 0 24 24"><path d="M5 12l5 5L20 7"/></svg>',
    retry: '<svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1015.5-6.2M21 3v6h-6"/></svg>',
    edit: '<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg>',
    trash: '<svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/></svg>',
    speaker: '<svg viewBox="0 0 24 24"><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 9a4 4 0 010 6M18.5 6.5a8 8 0 010 11"/></svg>',
    stop: '<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
    up: '<svg viewBox="0 0 24 24"><path d="M7 11v9H4v-9zM7 11l4-8a2 2 0 012 2v4h5.5a2 2 0 012 2.3l-1.2 7A2 2 0 0117.3 20H7"/></svg>',
    down: '<svg viewBox="0 0 24 24"><path d="M17 13V4h3v9zM17 13l-4 8a2 2 0 01-2-2v-4H5.5a2 2 0 01-2-2.3l1.2-7A2 2 0 016.7 4H17"/></svg>',
    book: '<svg viewBox="0 0 24 24"><path d="M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2zM4 19V5M8 7h7"/></svg>',
    clip: '<svg viewBox="0 0 24 24"><path d="M21 11l-8.5 8.5a5 5 0 01-7-7L14 4a3.5 3.5 0 015 5l-8.5 8.5a2 2 0 01-3-3L15 7"/></svg>',
  };

  // ------------------------------------------------------------------ API
  async function api(method, url, body) {
    const opts = { method, headers: { Accept: "application/json" }, credentials: "same-origin" };
    if (method !== "GET") opts.headers["X-CSRF-Token"] = CSRF;
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    let res;
    try { res = await fetch(url, opts); } catch (e) { throw new Error("Network error. Check your connection and try again."); }
    let data = {};
    try { data = await res.json(); } catch (e) { /* non-JSON */ }
    if (!res.ok) throw new Error(data.error || "Request failed (" + res.status + ").");
    return data;
  }

  /** POST and read an NDJSON event stream, calling onEvent for each event. */
  async function streamRequest(url, body, onEvent) {
    const headers = { "X-CSRF-Token": CSRF, Accept: "application/x-ndjson" };
    let payload = body;
    if (!(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    let res;
    try { res = await fetch(url, { method: "POST", headers, body: payload, credentials: "same-origin" }); }
    catch (e) { throw new Error("Network error. Check your connection and try again."); }
    if (!res.ok) {
      let data = {};
      try { data = await res.json(); } catch (e) { /* ignore */ }
      throw new Error(data.error || "Request failed (" + res.status + ").");
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (line) onEvent(JSON.parse(line));
      }
    }
    if (buf.trim()) onEvent(JSON.parse(buf));
  }

  // ------------------------------------------------------------------ helpers
  function fmtTime(iso) {
    const d = iso ? new Date(iso) : new Date();
    return d.toLocaleTimeString(lang === "ur" ? "ur-PK" : [], { hour: "numeric", minute: "2-digit" });
  }
  let toastTimer;
  function toast(msg) {
    el.toast.textContent = msg;
    el.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.toast.hidden = true; }, 3000);
  }
  function scrollToBottom(force) {
    const nearBottom = el.thread.scrollHeight - el.thread.scrollTop - el.thread.clientHeight < 160;
    if (force || nearBottom) el.thread.scrollTop = el.thread.scrollHeight;
  }
  function setTitle(conv) {
    const title = conv ? conv.title : "";
    el.title.textContent = title || t("newChat");
    document.title = (title ? title + " · " : "") + "MediBot";
    const mode = conv ? conv.mode : state.newMode;
    el.modeBadge.hidden = !(mode === "symptom" || mode === "labs");
    el.modeBadge.textContent = mode === "symptom" ? t("symptomMode") : mode === "labs" ? t("labsMode") : "";
    el.chatActions.hidden = !conv;
  }
  const showWelcome = (show) => { el.welcome.hidden = !show; };
  const button = (cls, html, label, onClick) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = cls;
    b.innerHTML = html;
    if (label) { b.title = label; b.setAttribute("aria-label", label); }
    if (onClick) b.addEventListener("click", onClick);
    return b;
  };

  // ------------------------------------------------------------------ emergency banner
  const EMERGENCY_RE = /chest pain|heart attack|can'?t breathe|cannot breathe|(difficulty|trouble) breathing|unconscious|seizure|severe bleeding|overdose|poison|suicid|kill (myself|me)|end my life|want to die|self[- ]harm|seene (mein|me) dard|saans nahi|behosh|khudkushi|سینے میں درد|سانس نہیں|بے ہوش|خودکشی/i;
  function renderEmergencyNumbers() {
    el.emergencyNumbers.replaceChildren(...EMERGENCY_NUMBERS.map(([label, num]) => {
      const a = document.createElement("a");
      a.href = "tel:" + String(num).replace(/[^\d+]/g, "");
      a.className = "em-num";
      const b = document.createElement("b");
      b.textContent = num;
      const s = document.createElement("span");
      s.textContent = label;
      a.append(b, s);
      return a;
    }));
  }
  function showEmergency() { el.emergency.hidden = false; el.thread.scrollTop = 0; }

  // ------------------------------------------------------------------ messages
  function sourcesNode(sources) {
    if (!sources || !sources.length) return null;
    const d = document.createElement("details");
    d.className = "sources";
    const s = document.createElement("summary");
    s.innerHTML = ICONS.book;
    const label = document.createElement("span");
    label.textContent = t("sources") + " (" + sources.length + ")";
    s.appendChild(label);
    const list = document.createElement("ol");
    for (const src of sources) {
      const li = document.createElement("li");
      const head = document.createElement("strong");
      head.textContent = src.title + (src.page ? " · " + t("page") + " " + src.page : "");
      const snip = document.createElement("span");
      snip.textContent = src.snippet;
      li.append(head, snip);
      list.appendChild(li);
    }
    d.append(s, list);
    return d;
  }

  function botActions(m, meta) {
    const content = () => m.content;
    const copy = button("meta-btn", ICONS.copy, t("copy"), async () => {
      try {
        await navigator.clipboard.writeText(content());
        copy.innerHTML = ICONS.check;
        setTimeout(() => { copy.innerHTML = ICONS.copy; }, 1500);
      } catch (e) { toast("Couldn't copy to clipboard."); }
    });
    meta.appendChild(copy);

    if ("speechSynthesis" in window) {
      const speak = button("meta-btn", ICONS.speaker, t("listen"), () => toggleSpeak(content(), speak));
      meta.appendChild(speak);
    }
    if (m.id) {
      const up = button("meta-btn fb" + (m.feedback === 1 ? " on" : ""), ICONS.up, t("helpful"));
      const down = button("meta-btn fb" + (m.feedback === -1 ? " on" : ""), ICONS.down, t("notHelpful"));
      const send = async (v) => {
        const value = m.feedback === v ? 0 : v;
        try {
          await api("POST", "/api/messages/" + m.id + "/feedback", { value });
          m.feedback = value;
          up.classList.toggle("on", value === 1);
          down.classList.toggle("on", value === -1);
          if (value) toast(t("thanks"));
        } catch (e) { toast(e.message); }
      };
      up.addEventListener("click", () => send(1));
      down.addEventListener("click", () => send(-1));
      meta.append(up, down);
    }
  }

  function messageNode(m) {
    const isUser = m.role === "user";
    const wrap = document.createElement("div");
    wrap.className = "msg " + (isUser ? "user" : "bot");

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    if (isUser) avatar.textContent = USER ? (USER.name || "U").charAt(0).toUpperCase() : "You";
    else avatar.innerHTML = ICONS.bot;

    const body = document.createElement("div");
    body.className = "msg-body";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.dir = "auto";
    if (isUser) bubble.textContent = m.content;
    else bubble.innerHTML = window.MD.render(m.content);
    body.appendChild(bubble);

    if (!isUser) {
      const src = sourcesNode(m.sources);
      if (src) body.appendChild(src);
    }
    const meta = document.createElement("div");
    meta.className = "msg-meta";
    const time = document.createElement("span");
    time.textContent = fmtTime(m.created_at);
    meta.appendChild(time);
    if (!isUser) botActions(m, meta);
    body.appendChild(meta);

    wrap.append(avatar, body);
    wrap._bubble = bubble;
    wrap._body = body;
    return wrap;
  }

  function streamingNode() {
    const node = document.createElement("div");
    node.className = "msg bot streaming";
    node.innerHTML = '<div class="avatar">' + ICONS.bot + '</div><div class="msg-body"><div class="bubble" dir="auto"><div class="typing" aria-label="MediBot is typing"><span></span><span></span><span></span></div></div></div>';
    node._bubble = node.querySelector(".bubble");
    return node;
  }

  function errorNode(message, onRetry) {
    const wrap = document.createElement("div");
    wrap.className = "msg bot error";
    wrap.innerHTML = '<div class="avatar">' + ICONS.bot + '</div>';
    const body = document.createElement("div");
    body.className = "msg-body";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = message;
    const meta = document.createElement("div");
    meta.className = "msg-meta";
    if (onRetry) meta.appendChild(button("meta-btn", ICONS.retry + "<span>" + t("retry") + "</span>", null, onRetry));
    body.append(bubble, meta);
    wrap.appendChild(body);
    return wrap;
  }

  function renderFollowups(list) {
    el.followups.replaceChildren();
    if (!list || !list.length || state.sending) return;
    list.forEach((q, i) => {
      const b = button("followup", "", null, () => sendMessage(q));
      b.textContent = q;
      b.dir = "auto";
      b.style.animationDelay = i * 70 + "ms";
      el.followups.appendChild(b);
    });
  }

  // ------------------------------------------------------------------ speech output
  let speakingBtn = null;
  function toggleSpeak(text, btn) {
    const synth = window.speechSynthesis;
    if (speakingBtn) {
      synth.cancel();
      const was = speakingBtn;
      speakingBtn.innerHTML = ICONS.speaker;
      speakingBtn = null;
      if (was === btn) return;
    }
    const plain = text.replace(/[*_#`>]/g, "").replace(/\n+/g, ". ");
    const u = new SpeechSynthesisUtterance(plain);
    const isUrdu = /[؀-ۿ]/.test(text);
    u.lang = isUrdu ? "ur-PK" : "en-US";
    const voice = synth.getVoices().find((v) => v.lang && v.lang.toLowerCase().startsWith(isUrdu ? "ur" : "en"));
    if (voice) u.voice = voice;
    u.onend = u.onerror = () => { if (speakingBtn === btn) { btn.innerHTML = ICONS.speaker; speakingBtn = null; } };
    btn.innerHTML = ICONS.stop;
    speakingBtn = btn;
    synth.speak(u);
  }

  // ------------------------------------------------------------------ speech input
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null;
  if (Recognition) {
    el.micBtn.hidden = false;
    el.micBtn.addEventListener("click", () => {
      if (recognizer) { recognizer.stop(); return; }
      recognizer = new Recognition();
      recognizer.lang = lang === "ur" ? "ur-PK" : "en-US";
      recognizer.interimResults = true;
      recognizer.continuous = false;
      const base = el.input.value ? el.input.value.trimEnd() + " " : "";
      recognizer.onresult = (e) => {
        let text = "";
        for (const r of e.results) text += r[0].transcript;
        el.input.value = (base + text).slice(0, MAX_CHARS);
        autoGrow(); updateComposer();
      };
      recognizer.onerror = (e) => { if (e.error === "not-allowed") toast(t("micDenied")); };
      recognizer.onend = () => { el.micBtn.classList.remove("recording"); recognizer = null; el.input.focus(); };
      el.micBtn.classList.add("recording");
      toast(t("listening"));
      recognizer.start();
    });
  }

  // ------------------------------------------------------------------ history sidebar
  function groupLabel(iso) {
    const d = new Date(iso), now = new Date();
    const sod = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const days = Math.round((sod(now) - sod(d)) / 86400000);
    if (days <= 0) return t("today_g");
    if (days === 1) return t("yesterday");
    if (days < 7) return t("prev7");
    if (days < 30) return t("prev30");
    return t("older");
  }

  function renderHistory() {
    const q = el.search.value.trim().toLowerCase();
    const items = state.conversations.filter((c) => !q || c.title.toLowerCase().includes(q));
    el.historyList.replaceChildren();
    el.historyEmpty.hidden = items.length > 0;
    el.historyEmpty.textContent = q ? t("noMatch") : t("emptyHistory");
    let last = null;
    for (const c of items) {
      const g = groupLabel(c.updated_at);
      if (g !== last) {
        const h = document.createElement("li");
        h.className = "history-group";
        h.textContent = g;
        el.historyList.appendChild(h);
        last = g;
      }
      el.historyList.appendChild(historyItem(c));
    }
  }

  function historyItem(c) {
    const li = document.createElement("li");
    li.className = "history-item" + (c.id === state.convId ? " active" : "");
    const link = button("history-link", "", null, () => { openConversation(c.id); closeSidebar(); });
    link.textContent = (c.mode === "symptom" ? "🩺 " : c.mode === "labs" ? "🧪 " : "") + c.title;
    link.title = c.title;
    link.dir = "auto";
    const actions = document.createElement("div");
    actions.className = "history-actions";
    actions.append(
      button("", ICONS.edit, t("rename"), () => startRename(li, c)),
      button("del", ICONS.trash, t("del"), () => deleteConversation(c)),
    );
    li.append(link, actions);
    return li;
  }

  function startRename(li, c) {
    const input = document.createElement("input");
    input.className = "rename-input";
    input.value = c.title;
    input.maxLength = 120;
    li.replaceChildren(input);
    input.focus();
    input.select();
    let done = false;
    const finish = async (save) => {
      if (done) return;
      done = true;
      const title = input.value.trim();
      if (save && title && title !== c.title) {
        try {
          const data = await api("PATCH", "/api/conversations/" + c.id, { title });
          Object.assign(c, data.conversation);
          if (c.id === state.convId) { state.conv = c; setTitle(c); }
        } catch (e) { toast(e.message); }
      }
      renderHistory();
    };
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") finish(true); if (e.key === "Escape") finish(false); });
    input.addEventListener("blur", () => finish(true));
  }

  async function loadConversations() {
    try {
      const data = await api("GET", "/api/conversations");
      state.conversations = data.conversations;
      renderHistory();
    } catch (e) { toast(e.message); }
  }

  async function deleteConversation(c) {
    if (!confirm(t("deleteConfirm").replace("%s", c.title))) return;
    try {
      await api("DELETE", "/api/conversations/" + c.id);
      state.conversations = state.conversations.filter((x) => x.id !== c.id);
      if (c.id === state.convId) newChat();
      renderHistory();
      toast(t("deleted"));
    } catch (e) { toast(e.message); }
  }

  async function clearAll() {
    if (!state.conversations.length) { toast(t("noChats")); return; }
    if (!confirm(t("clearConfirm"))) return;
    try {
      await api("DELETE", "/api/conversations");
      state.conversations = [];
      newChat();
      renderHistory();
      toast(t("cleared"));
    } catch (e) { toast(e.message); }
  }

  function upsertConversation(conv) {
    state.conversations = [conv, ...state.conversations.filter((c) => c.id !== conv.id)];
    renderHistory();
  }

  // ------------------------------------------------------------------ conversations
  function newChat(mode) {
    if (state.sending) return;
    state.convId = null;
    state.conv = null;
    state.newMode = mode || "chat";
    el.messages.replaceChildren();
    el.emergency.hidden = true;
    renderFollowups([]);
    showWelcome(!mode || mode === "chat");
    setTitle(null);
    history.replaceState(null, "", location.pathname);
    renderHistory();
    el.input.focus();
  }

  async function openConversation(id) {
    if (state.sending) return;
    try {
      const data = await api("GET", "/api/conversations/" + encodeURIComponent(id));
      state.convId = data.conversation.id;
      state.conv = data.conversation;
      el.messages.replaceChildren(...data.messages.map(messageNode));
      el.emergency.hidden = !data.messages.some((m) => m.emergency);
      showWelcome(data.messages.length === 0);
      setTitle(state.conv);
      const lastBot = [...data.messages].reverse().find((m) => m.role === "assistant");
      renderFollowups(lastBot ? lastBot.followups : []);
      history.replaceState(null, "", "#" + state.convId);
      renderHistory();
      scrollToBottom(true);
    } catch (e) {
      toast(e.message);
      newChat();
    }
  }

  // ------------------------------------------------------------------ sending (streaming)
  async function runStream(url, body, userNode, retry) {
    state.sending = true;
    updateComposer();
    renderFollowups([]);
    showWelcome(false);
    const node = streamingNode();
    el.messages.append(userNode, node);
    scrollToBottom(true);

    const bgPulse = () => window.medibotBg && window.medibotBg.pulse();
    bgPulse();
    const pulseTimer = setInterval(bgPulse, 1800);

    let raw = "", sources = [], frame = 0, finished = false;
    const paint = () => {
      frame = 0;
      node._bubble.innerHTML = window.MD.render(raw) + '<span class="caret" aria-hidden="true"></span>';
      scrollToBottom();
    };

    try {
      await streamRequest(url, body, (ev) => {
        if (ev.type === "meta" && ev.emergency) showEmergency();
        else if (ev.type === "sources") sources = ev.sources || [];
        else if (ev.type === "token") {
          if (!raw) clearInterval(pulseTimer);
          raw += ev.t;
          if (!frame) frame = requestAnimationFrame(paint);
        } else if (ev.type === "done") {
          finished = true;
          if (frame) cancelAnimationFrame(frame);
          const finalNode = messageNode(ev.assistant_message);
          node.replaceWith(finalNode);
          state.convId = ev.conversation.id;
          state.conv = ev.conversation;
          setTitle(ev.conversation);
          upsertConversation(ev.conversation);
          history.replaceState(null, "", "#" + ev.conversation.id);
          state.sending = false;
          renderFollowups(ev.assistant_message.followups);
        } else if (ev.type === "error") {
          throw new Error(ev.error);
        }
      });
      if (!finished) throw new Error("The connection was interrupted. Please try again.");
    } catch (e) {
      if (frame) cancelAnimationFrame(frame);
      node.remove();
      const err = errorNode(e.message, retry ? () => { err.remove(); userNode.remove(); retry(); } : null);
      el.messages.appendChild(err);
    } finally {
      clearInterval(pulseTimer);
      state.sending = false;
      updateComposer();
      scrollToBottom();
    }
  }

  function sendMessage(text, modeOverride) {
    text = (text || "").trim();
    if (!text || state.sending) return;
    if (text.length > MAX_CHARS) { toast(t("tooLong")); return; }
    if (EMERGENCY_RE.test(text)) showEmergency();
    const body = { message: text, conversation_id: state.convId };
    if (!state.convId) body.mode = modeOverride || state.newMode;
    const userNode = messageNode({ role: "user", content: text });
    runStream("/api/chat", body, userNode, () => sendMessage(text, modeOverride));
  }

  function updateComposer() {
    const len = el.input.value.trim().length;
    el.send.disabled = state.sending || len === 0 || len > MAX_CHARS;
    const remaining = MAX_CHARS - el.input.value.length;
    el.counter.textContent = remaining < 200 ? String(remaining) : "";
    el.counter.classList.toggle("over", remaining < 0);
  }
  function autoGrow() {
    el.input.style.height = "auto";
    el.input.style.height = Math.min(el.input.scrollHeight, 200) + "px";
  }

  // ------------------------------------------------------------------ tools
  function startSymptomCheck() {
    closeSidebar();
    newChat("symptom");
    sendMessage(t("symptomStart"), "symptom");
  }

  // Lab report
  const labsModal = $("#labsModal"), labFile = $("#labFile"), labPreview = $("#labPreview"), dropText = $("#dropText");
  function openLabs() {
    closeSidebar();
    $("#labsForm").reset();
    labPreview.hidden = true;
    dropText.textContent = t("dropText");
    $("#labsError").hidden = true;
    labsModal.showModal();
  }
  labFile.addEventListener("change", () => {
    const f = labFile.files[0];
    if (!f) return;
    dropText.textContent = f.name + " · " + Math.round(f.size / 1024) + " KB";
    if (f.type.startsWith("image/")) {
      labPreview.src = URL.createObjectURL(f);
      labPreview.hidden = false;
    } else labPreview.hidden = true;
  });
  const dropzone = $("#dropzone");
  ["dragenter", "dragover"].forEach((ev) => dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => dropzone.addEventListener(ev, () => dropzone.classList.remove("over")));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer.files.length) { labFile.files = e.dataTransfer.files; labFile.dispatchEvent(new Event("change")); }
  });
  $("#labsForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = labFile.files[0];
    const errEl = $("#labsError");
    if (!f) return;
    if (f.size > 5 * 1024 * 1024) { errEl.textContent = "File is too large (max 5 MB)."; errEl.hidden = false; return; }
    const note = $("#labNote").value.trim();
    labsModal.close();
    if (state.conv && state.conv.mode !== "labs") newChat("labs");
    if (!state.convId) { state.newMode = "labs"; setTitle(null); }
    const send = () => {
      const fd = new FormData();
      fd.append("file", f);
      if (note) fd.append("note", note);
      if (state.convId) fd.append("conversation_id", state.convId);
      const userNode = messageNode({ role: "user", content: "📎 " + f.name + (note ? "\n" + note : "") });
      runStream("/api/labs", fd, userNode, send);
    };
    send();
  });

  // Medicine lookup
  const medModal = $("#medModal"), medResult = $("#medResult");
  function openMedicine() { closeSidebar(); medModal.showModal(); $("#medQuery").focus(); }
  $("#medForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = $("#medQuery").value.trim();
    if (!q) return;
    medResult.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
    try {
      const { medicine: m } = await api("GET", "/api/medicine?q=" + encodeURIComponent(q));
      const card = document.createElement("div");
      card.className = "med-card";
      const h = document.createElement("h3");
      h.textContent = m.brand ? m.brand + " (" + m.generic + ")" : m.generic;
      card.appendChild(h);
      const sub = document.createElement("p");
      sub.className = "hint";
      sub.textContent = [m.route, m.manufacturer].filter(Boolean).join(" · ");
      card.appendChild(sub);
      if (m.corrected) {
        const fix = document.createElement("p");
        fix.className = "hint";
        fix.textContent = (lang === "ur" ? "نتائج برائے: " : "Showing results for: ") + m.corrected;
        card.insertBefore(fix, h);
      }
      for (const s of m.sections) {
        const det = document.createElement("details");
        if (["Uses", "Purpose"].includes(s.label)) det.open = true;
        const sum = document.createElement("summary");
        sum.textContent = s.label;
        const p = document.createElement("p");
        p.textContent = s.text;
        det.append(sum, p);
        card.appendChild(det);
      }
      const ask = button("ghost-btn ask-bot", ICONS.bot + "<span></span>", null, () => {
        medModal.close();
        newChat();
        sendMessage((lang === "ur" ? "دوائی کے بارے میں سمجھائیں: " : "Explain in simple words what this medicine is used for and its common side effects: ") + (m.generic || q));
      });
      ask.querySelector("span").textContent = lang === "ur" ? "MediBot سے آسان الفاظ میں پوچھیں" : "Ask MediBot to explain simply";
      card.appendChild(ask);
      medResult.replaceChildren(card);
    } catch (err) {
      const p = document.createElement("p");
      p.className = "form-error";
      p.textContent = err.message;
      medResult.replaceChildren(p);
    }
  });

  // Share & export
  const shareModal = $("#shareModal"), shareUrl = $("#shareUrl");
  el.shareBtn.addEventListener("click", async () => {
    if (!state.convId) { toast(t("shareFirst")); return; }
    try {
      const data = await api("POST", "/api/conversations/" + state.convId + "/share");
      state.conv = data.conversation;
      shareUrl.value = data.url;
      shareModal.showModal();
      shareUrl.select();
    } catch (e) { toast(e.message); }
  });
  $("#copyShare").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(shareUrl.value); toast(t("copied")); }
    catch (e) { shareUrl.select(); }
  });
  $("#unshareBtn").addEventListener("click", async () => {
    try {
      await api("DELETE", "/api/conversations/" + state.convId + "/share");
      shareModal.close();
      toast(t("linkOff"));
    } catch (e) { toast(e.message); }
  });
  el.exportBtn.addEventListener("click", () => {
    document.querySelectorAll(".sources").forEach((d) => { d.open = true; });
    window.print();
  });

  // ------------------------------------------------------------------ accounts
  function renderAccount() {
    el.account.replaceChildren();
    if (USER) {
      const row = document.createElement("div");
      row.className = "account-row";
      const av = document.createElement("span");
      av.className = "account-avatar";
      av.textContent = (USER.name || USER.email).charAt(0).toUpperCase();
      const info = document.createElement("div");
      info.className = "account-info";
      const n = document.createElement("strong");
      n.textContent = USER.name;
      const em = document.createElement("span");
      em.textContent = USER.email;
      info.append(n, em);
      const out = button("icon-btn", '<svg viewBox="0 0 24 24"><path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10"/></svg>', t("logout"), async () => {
        try { await api("POST", "/auth/logout"); } catch (e) { /* ignore */ }
        location.href = "/";
      });
      row.append(av, info, out);
      el.account.appendChild(row);
      if (USER.is_admin) {
        const a = document.createElement("a");
        a.className = "ghost-btn";
        a.href = "/admin";
        a.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg><span></span>';
        a.querySelector("span").textContent = t("admin");
        el.account.appendChild(a);
      }
    } else {
      const b = button("login-btn", "", null, () => openAuth("login"));
      b.textContent = t("loginSignup");
      const p = document.createElement("p");
      p.className = "account-note";
      p.textContent = t("guestNote");
      el.account.append(b, p);
    }
  }

  const authModal = $("#authModal"), authForm = $("#authForm"), authError = $("#authError");
  let authMode = "login";
  function setAuthMode(mode) {
    authMode = mode;
    authModal.querySelectorAll(".tab").forEach((tb) => tb.classList.toggle("active", tb.dataset.tab === mode));
    authModal.querySelectorAll(".signup-only").forEach((n) => { n.hidden = mode !== "signup"; });
    $("#authSubmit").textContent = t(mode);
    authForm.password.autocomplete = mode === "signup" ? "new-password" : "current-password";
    authError.hidden = true;
  }
  function openAuth(mode) {
    closeSidebar();
    setAuthMode(mode);
    $("#googleWrap").hidden = !GOOGLE;
    authModal.showModal();
    authForm.email.focus();
  }
  authModal.querySelectorAll(".tab").forEach((tb) => tb.addEventListener("click", () => setAuthMode(tb.dataset.tab)));
  authForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = { email: authForm.email.value, password: authForm.password.value };
    if (authMode === "signup") body.name = authForm.name.value;
    const submit = $("#authSubmit");
    submit.disabled = true;
    try {
      await api("POST", "/auth/" + authMode, body);
      location.reload(); // new session + CSRF token; chats from this browser are now in the account
    } catch (err) {
      authError.textContent = err.message;
      authError.hidden = false;
    } finally { submit.disabled = false; }
  });

  // ------------------------------------------------------------------ status, theme, sidebar, PWA
  async function pollStatus() {
    try {
      const res = await fetch("/healthz", { headers: { Accept: "application/json" } });
      const data = await res.json();
      if (data.ai_ready) { setStatus("ready", t("online")); return; }
      setStatus("loading", t("starting"));
    } catch (e) { setStatus("down", t("offline")); }
    setTimeout(pollStatus, 4000);
  }
  function setStatus(s, text) {
    el.status.dataset.state = s;
    el.status.querySelector(".status-text").textContent = text;
  }
  function openSidebar() { el.sidebar.classList.add("open"); el.scrim.hidden = false; }
  function closeSidebar() { el.sidebar.classList.remove("open"); el.scrim.hidden = true; }
  function toggleTheme() {
    const root = document.documentElement;
    const current = root.getAttribute("data-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("medibot-theme", next); } catch (e) { /* ignore */ }
  }

  let installPrompt = null;
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); installPrompt = e; el.installApp.hidden = false; });
  el.installApp.addEventListener("click", async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    await installPrompt.userChoice;
    installPrompt = null;
    el.installApp.hidden = true;
  });
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => { /* optional */ }));
  }

  // ------------------------------------------------------------------ wire up
  el.form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = el.input.value;
    el.input.value = "";
    autoGrow(); updateComposer();
    sendMessage(text);
  });
  el.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      if (!el.send.disabled) el.form.requestSubmit();
    }
  });
  el.input.addEventListener("input", () => { autoGrow(); updateComposer(); });
  el.suggestions.addEventListener("click", (e) => {
    const b = e.target.closest(".suggestion");
    if (!b) return;
    if (b.dataset.tool === "symptom") startSymptomCheck();
    else if (b.dataset.tool === "labs") openLabs();
    else sendMessage(b.dataset.q);
  });
  el.suggestions.addEventListener("pointermove", (e) => {
    const card = e.target.closest(".suggestion");
    if (!card) return;
    const r = card.getBoundingClientRect();
    card.style.setProperty("--mx", (e.clientX - r.left) + "px");
    card.style.setProperty("--my", (e.clientY - r.top) + "px");
  });
  el.newChat.addEventListener("click", () => { newChat(); closeSidebar(); });
  $("#toolSymptom").addEventListener("click", startSymptomCheck);
  $("#toolLabs").addEventListener("click", openLabs);
  $("#toolMedicine").addEventListener("click", openMedicine);
  el.attachBtn.addEventListener("click", openLabs);
  el.search.addEventListener("input", renderHistory);
  el.clearAll.addEventListener("click", clearAll);
  el.themeToggle.addEventListener("click", toggleTheme);
  el.langToggle.addEventListener("click", () => {
    lang = lang === "ur" ? "en" : "ur";
    try { localStorage.setItem("medibot-lang", lang); } catch (e) { /* ignore */ }
    applyLanguage();
    setTitle(state.conv);
  });
  el.emergencyClose.addEventListener("click", () => { el.emergency.hidden = true; });
  el.openSidebar.addEventListener("click", openSidebar);
  el.closeSidebar.addEventListener("click", closeSidebar);
  el.scrim.addEventListener("click", closeSidebar);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSidebar(); });
  // Close a modal when clicking its backdrop.
  document.querySelectorAll("dialog.modal").forEach((d) => d.addEventListener("click", (e) => { if (e.target === d) d.close(); }));

  // ------------------------------------------------------------------ boot
  applyLanguage();
  setTitle(null);
  updateComposer();
  pollStatus();
  loadConversations().then(() => {
    const id = location.hash.slice(1);
    if (/^[0-9a-f]{32}$/.test(id)) openConversation(id);
    else el.input.focus();
  });
})();
