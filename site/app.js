/* Общий скрипт сайта: главная и страницы клиентов. Каждая часть работает, только если её блок есть на странице. */

/* ===== Настройки сайта — меняются здесь ===== */
const CONFIG = {
  // Адрес приёма заявок (серверный обработчик, который передаёт заявку в Bitrix24). Пусто — форма в тестовом режиме.
  leadEndpoint: "",
  defaultWho: "sobstvennik",
  fontSwitch: false, // шрифт выбран 06.10: «как у Шрифтотеки» — Vela Sans везде
  // Номер счётчика Яндекс Метрики (даст она). Пусто — цели только пишутся в консоль.
  metrika: "",
};

/* плашка про cookies: показываем, пока посетитель не нажал «Хорошо» (её решение 10.10) */
(() => {
  const box = document.getElementById("cookie");
  if (!box) return;
  let ok = false;
  try { ok = localStorage.getItem("cookie-ok") === "1"; } catch (e) {}
  if (ok) return;
  /* дизайн-ревью 12.10: плашка стояла в конце страницы — с клавиатуры до «Хорошо» надо было пройти весь сайт */
  document.body.prepend(box);
  box.hidden = false;
  const room = () => document.body.style.setProperty("--cookie-h", box.hidden ? "0px" : box.offsetHeight + "px");
  document.body.classList.add("cookie-on"); room(); addEventListener("resize", room);
  document.getElementById("cookie-ok").addEventListener("click", () => {
    box.hidden = true; document.body.classList.remove("cookie-on"); room();
    try { localStorage.setItem("cookie-ok", "1"); } catch (e) {}
  });
})();

/* памятка при уходе со страницы (книги: подписка «при уходе, не перекрывая страницу»; её решение 10.10 — всплывающие
   можно): карточка в правом нижнем углу, только на компьютере (курсор ушёл к вкладкам), один раз для посетителя */
(() => {
  const card = document.getElementById("exit-card");
  const gift = document.getElementById("podarok") || document.getElementById("podarki");
  if (!card || !gift || matchMedia("(hover: none)").matches) return;
  try { if (localStorage.getItem("exit-shown")) return; } catch (e) {}
  const hide = () => { card.hidden = true; };
  document.getElementById("exit-x").addEventListener("click", hide);
  document.getElementById("exit-go").addEventListener("click", e => { e.preventDefault(); hide(); gift.scrollIntoView({behavior: "smooth", block: "start"}); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") hide(); });
  const onLeave = e => {
    if (e.clientY > 0 || performance.now() < 15000) return; // не пугать сразу: только после 15 секунд на странице
    document.removeEventListener("mouseout", onLeave);
    card.hidden = false;
    try { localStorage.setItem("exit-shown", "1"); } catch (e) {}
  };
  document.addEventListener("mouseout", onLeave);
})();

/* цели для Метрики (книги: Clarke «SEO 2025», Davidson — мерить заявки, звонки, памятки, а не просто визиты) */
const goal = name => {
  try { if (CONFIG.metrika && window.ym) window.ym(Number(CONFIG.metrika), "reachGoal", name); else console.log("цель:", name); } catch (e) {}
};
document.addEventListener("click", e => {
  const a = e.target.closest("a");
  if (!a) return;
  if (a.href.startsWith("tel:")) goal("phone_click");
  else if (a.dataset.gift) goal("gift_click");
  else if (a.dataset.ask) goal("ask_price");
});

/* переключатель пар шрифтов — на всех страницах, выбор запоминается */
if (CONFIG.fontSwitch) {
  const box = document.createElement("div");
  box.className = "fsw"; box.setAttribute("role", "group"); box.setAttribute("aria-label", "Шрифт");
  box.innerHTML = '<span>Шрифт:</span><button type="button" data-f="1">Didot + Erewhon + Geist</button>' +
    '<button type="button" data-f="2">Didot + Geist</button><button type="button" data-f="3">Didot + Vela Sans</button>' +
    '<button type="button" data-f="4">Erewhon + Geist</button><button type="button" data-f="5">Как у Шрифтотеки</button>';
  document.body.appendChild(box);
  const setF = n => { if (n === "1") document.documentElement.removeAttribute("data-font"); else document.documentElement.dataset.font = n;
    box.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", b.dataset.f === n));
    try { localStorage.setItem("font4", n); } catch (e) {} };
  let f0 = "1"; try { f0 = localStorage.getItem("font4") || "1"; } catch (e) {}
  setF(f0); box.addEventListener("click", e => { const b = e.target.closest("button"); if (b) setF(b.dataset.f); });
}

/* слайдер первого экрана: смена каждые 6 с, пауза при наведении и когда вкладка скрыта, свайп на телефоне */
(() => {
  const box = document.getElementById("slides");
  if (!box || box.children.length < 2) return;
  const hero = box.parentElement;
  const sl = [...box.children], dots = document.getElementById("sl-dots"), num = document.getElementById("sl-n");
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  sl.forEach(() => dots.appendChild(document.createElement("i")));
  /* кадры 2–6 скачиваем заранее, по одному, а не все сразу (замер 10.10: 6 фото = 2 МБ при открытии главной) */
  const prime = s => s && s.querySelectorAll("[data-srcset],[data-src]").forEach(el => {
    if (el.dataset.srcset) { el.srcset = el.dataset.srcset; el.removeAttribute("data-srcset"); }
    if (el.dataset.src) { el.src = el.dataset.src; el.removeAttribute("data-src"); }
  });
  addEventListener("load", () => setTimeout(() => prime(sl[1]), 1500));
  let i = 0, timer = null;
  const show = k => {
    i = (k + sl.length) % sl.length;
    prime(sl[i]); prime(sl[(i + 1) % sl.length]);
    sl.forEach((s, j) => { s.classList.toggle("is-on", j === i); s.setAttribute("aria-hidden", j !== i); });
    [...dots.children].forEach((d, j) => d.classList.toggle("on", j === i));
    num.textContent = String(i + 1).padStart(2, "0");
  };
  /* дизайн-ревью 12.10 (WCAG 2.2.2): кнопка «пауза» и пауза, пока фокус клавиатуры внутри первого экрана */
  const pauseBtn = hero.querySelector(".sl-pause");
  let held = false;
  const stop = () => { clearInterval(timer); timer = null; };
  const play = () => { stop(); if (!still && !held && !hero.contains(document.activeElement)) timer = setInterval(() => show(i + 1), 4500); };
  hero.querySelector(".sl-prev").addEventListener("click", () => { show(i - 1); play(); });
  hero.querySelector(".sl-next").addEventListener("click", () => { show(i + 1); play(); });
  if (pauseBtn) pauseBtn.addEventListener("click", () => {
    held = !held; pauseBtn.setAttribute("aria-pressed", held);
    pauseBtn.setAttribute("aria-label", held ? "Продолжить смену фото" : "Остановить смену фото");
    pauseBtn.textContent = held ? "▶" : "❚❚"; held ? stop() : play();
  });
  hero.addEventListener("mouseenter", stop); hero.addEventListener("mouseleave", play);
  hero.addEventListener("focusin", stop); hero.addEventListener("focusout", () => setTimeout(play));
  document.addEventListener("visibilitychange", () => document.hidden ? stop() : play());
  let x0 = null;
  hero.addEventListener("touchstart", e => { x0 = e.touches[0].clientX; }, {passive: true});
  hero.addEventListener("touchend", e => {
    if (x0 === null) return; const dx = e.changedTouches[0].clientX - x0; x0 = null;
    if (Math.abs(dx) > 50) { show(i + (dx < 0 ? 1 : -1)); play(); }
  });
  show(0); play();
})();


/* слайдер отзывов: бесконечная лента (её просьба 06.10) — после последнего сразу первый, без отката назад.
   За отзывами стоит копия; дойдя до копии, лента незаметно перескакивает на тот же отзыв в начале. */
document.querySelectorAll(".reviews").forEach(box => {
  const track = box.querySelector(".rv-track"), orig = [...track.children], n = orig.length;
  if (!n) return;
  orig.forEach(c => { const k = c.cloneNode(true); k.setAttribute("aria-hidden", "true"); k.querySelectorAll("a").forEach(a => a.tabIndex = -1); track.appendChild(k); });
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let i = 0, timer = null, busy = false;
  const step = () => orig[0].getBoundingClientRect().width + parseFloat(getComputedStyle(track).columnGap || 24);
  const place = (anim) => { track.style.transition = anim ? "" : "none"; track.style.transform = `translateX(${-i * step()}px)`; if (!anim) track.offsetHeight; };
  const next = () => { if (busy) return; busy = true; i++; place(true); };
  const prev = () => { if (busy) return; busy = true; if (i === 0) { i = n; place(false); } i--; requestAnimationFrame(() => place(true)); };
  track.addEventListener("transitionend", () => { busy = false; if (i >= n) { i -= n; place(false); } });
  const stop = () => { clearInterval(timer); timer = null; };
  const play = () => { stop(); if (!still) timer = setInterval(next, 7000); };
  box.querySelector(".rv-prev").addEventListener("click", () => { prev(); play(); });
  box.querySelector(".rv-next").addEventListener("click", () => { next(); play(); });
  box.addEventListener("mouseenter", stop); box.addEventListener("mouseleave", play);
  /* дизайн-ревью 12.10: свайп пальцем, как у первого экрана */
  let x0 = null;
  track.addEventListener("touchstart", e => { x0 = e.touches[0].clientX; stop(); }, {passive: true});
  track.addEventListener("touchend", e => {
    if (x0 === null) return; const dx = e.changedTouches[0].clientX - x0; x0 = null;
    if (Math.abs(dx) > 40) (dx < 0 ? next : prev)(); play();
  });
  addEventListener("resize", () => place(false));
  place(false); play();
});

/* меню на телефоне */
const top_ = document.getElementById("top"), burger = top_ && top_.querySelector(".burger");
if (burger) {
  const setMenu = open => {
    top_.classList.toggle("open", open);
    document.body.classList.toggle("menu-open", open); // дизайн-ревью 12.10: страница под меню не прокручивается
    burger.setAttribute("aria-expanded", open);
    burger.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
  };
  burger.addEventListener("click", () => setMenu(!top_.classList.contains("open")));
  top_.querySelectorAll(".nav a, .top-contacts a").forEach(a => a.addEventListener("click", () => setMenu(false)));
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && top_.classList.contains("open")) { setMenu(false); burger.focus(); }
  });
}

/* выпадающие списки в шапке: стрелка открывает/закрывает (мышью — открываются и наведением), Esc и клик мимо закрывают */
const navItems = [...document.querySelectorAll(".nav-item")];
const closeDd = except => navItems.forEach(it => { if (it !== except) { it.classList.remove("open"); it.querySelector(".nav-toggle").setAttribute("aria-expanded", "false"); } });
navItems.forEach(it => {
  const t = it.querySelector(".nav-toggle");
  t.addEventListener("click", e => {
    e.stopPropagation();
    const open = !it.classList.contains("open");
    closeDd(it); it.classList.toggle("open", open); t.setAttribute("aria-expanded", open);
  });
});
document.addEventListener("click", e => { if (!e.target.closest(".nav-item")) closeDd(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeDd(); });

const params = new URLSearchParams(location.search);
const whoSelect = document.getElementById("f-who");
const pageWho = document.body.dataset.who; // на странице клиента — кто этот клиент

/* выбор «Я — …» на главной (карточки); на страницах клиентов его нет */
const tabs = [...document.querySelectorAll('.who [role="tab"]')];
if (tabs.length) {
  const ids = tabs.map(t => t.getAttribute("aria-controls"));
  const choose = (id, scroll) => {
    if (!ids.includes(id)) return;
    tabs.forEach(t => {
      const on = t.getAttribute("aria-controls") === id;
      t.setAttribute("aria-selected", on);
      t.tabIndex = on ? 0 : -1;
      document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
    });
    if (whoSelect) whoSelect.value = id;
    try { localStorage.setItem("who", id); } catch (e) {}
    if (scroll) document.getElementById(id).scrollIntoView({behavior: "smooth", block: "start"});
  };
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => choose(t.getAttribute("aria-controls"), true));
    t.addEventListener("keydown", e => {
      const d = {ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1}[e.key];
      if (!d) return;
      e.preventDefault();
      const n = tabs[(i + d + tabs.length) % tabs.length];
      n.focus(); choose(n.getAttribute("aria-controls"), false);
    });
  });
  document.querySelectorAll("[data-go]").forEach(a => a.addEventListener("click", e => { e.preventDefault(); choose(a.dataset.go, true); }));
  /* раздел по ссылке: #montazh или ?for=montazh (партнёрские ссылки с UTM) */
  let start = params.get("for") || location.hash.slice(1);
  if (!ids.includes(start)) { try { start = localStorage.getItem("who"); } catch (e) { start = null; } }
  choose(ids.includes(start) ? start : CONFIG.defaultWho, ids.includes(location.hash.slice(1)));
}
document.querySelectorAll("[data-who]").forEach(b => b.addEventListener("click", () => { if (whoSelect) whoSelect.value = b.dataset.who; }));
if (pageWho && whoSelect) whoSelect.value = pageWho;

/* вернувшийся посетитель (Dahlström «Storytelling in Design», гл. 13: «как вернувшийся, я должна быстро попасть к своему»):
   страница клиента запоминается в этом браузере; на главной открывается уже готовая в HTML ссылка «ваш раздел» */
const MY = ["vladelcu", "assistentu", "dizayneru", "montazhnikam", "zastroyshchikam", "kommerciya"];
try { if (MY.includes(document.body.dataset.page)) localStorage.setItem("my-page", document.body.dataset.page); } catch (e) {}
const backMine = document.getElementById("back-mine");
if (backMine) {
  let m = null; try { m = localStorage.getItem("my-page"); } catch (e) {}
  const a = MY.includes(m) && backMine.querySelector('a[data-mine="' + m + '"]');
  if (a) { a.hidden = false; backMine.hidden = false; }
}

/* каталог (одна сетка без заголовков, её решение 10.10): раздел начинается с карточки id="k-N" и идёт до следующей k-N.
   Кнопка #k-N показывает только карточки раздела, #vse или без адреса — весь каталог (её «переключатель не работает», 12.10) */
const catCards = [...document.querySelectorAll(".cat-all .cat-card, .cat-grid .cat-card")];
if (catCards.length && document.querySelector(".chips .chip")) {
  let cur = "";
  catCards.forEach(c => { if (/^k-\d+$/.test(c.id)) cur = c.id; c.dataset.k = cur; });
  const chips = [...document.querySelectorAll(".chips .chip")];
  const applyCat = () => {
    const h = location.hash.slice(1), one = catCards.some(c => c.dataset.k === h);
    catCards.forEach(c => { c.hidden = one && c.dataset.k !== h; });
    chips.forEach(c => c.classList.toggle("on", one ? c.getAttribute("href") === "#" + h : c.getAttribute("href") === "#vse"));
  };
  chips.forEach(c => c.addEventListener("click", e => {
    e.preventDefault(); history.replaceState(null, "", c.getAttribute("href")); applyCat();
  }));
  applyCat();
  window.addEventListener("hashchange", applyCat);
}

/* «что дальше» после заявки (Fraser «SaaS Playbook»: сразу сказать, кто и когда свяжется, и дать, чем заняться) */
const NEXT = ' <span class="next">Что дальше: менеджер позвонит в течение 4 часов в рабочее время, договоримся о встрече на объекте и пришлём смету. Пока ждёте — посмотрите <a href="index.html#raboty">наши объекты</a>.</span>';

/* форма заявки */
const form = document.getElementById("lead-form");
/* дизайн-ревью 12.10: после «Запросить цену» и памятки видно, что добавлено, а поле задачи растёт по тексту */
const fitNote = () => { const n = form && form.elements.note; if (n) n.rows = Math.max(3, n.value.split("\n").length + 1); };
const added = line => {
  fitNote();
  let s = document.getElementById("f-added");
  if (!s) { s = document.createElement("p"); s.id = "f-added"; s.className = "added"; s.setAttribute("role", "status"); form.elements.note.after(s); }
  s.textContent = "Добавлено в заявку: " + line.replace(/^Запрос цены: /, "");
};
if (form) form.elements.note.addEventListener("input", fitNote);
/* каталог: «Запросить цену» вписывает позицию в заявку и ведёт к форме */
document.querySelectorAll("[data-ask]").forEach(b => b.addEventListener("click", e => {
  if (!form) return;
  e.preventDefault();
  const note = form.elements.note, line = (b.dataset.askPrefix || "Запрос цены: ") + b.dataset.ask;
  if (!note.value.includes(line)) note.value = (note.value ? note.value + "\n" : "") + line;
  added(line);
  document.getElementById("zayavka").scrollIntoView({behavior: "smooth", block: "start"});
  setTimeout(() => form.elements.phone.focus({preventScroll: true}), 600);
}));
/* Памятка: кнопка «Получить памятку» вписывает памятку в заявку; ссылка на PDF показывается после отправки */
let gift = null;
document.querySelectorAll("[data-gift]").forEach(b => b.addEventListener("click", e => {
  if (!form) return;
  e.preventDefault();
  gift = {file: "pdf/" + b.dataset.gift, title: b.dataset.giftTitle};
  const note = form.elements.note, line = "Хочу получить памятку «" + gift.title + "»";
  if (!note.value.includes(line)) note.value = (note.value ? note.value + "\n" : "") + line;
  if (form.elements.gift) form.elements.gift.value = b.dataset.gift;
  if (b.dataset.giftWho && whoSelect) whoSelect.value = b.dataset.giftWho;
  added(line);
  document.getElementById("zayavka").scrollIntoView({behavior: "smooth", block: "start"});
  setTimeout(() => form.elements.phone.focus({preventScroll: true}), 600);
}));
const giftLink = (test) => {
  if (!gift) return "";
  const em = form.elements.email && form.elements.email.value.trim();
  let s = em ? " Памятка «" + gift.title + "» придёт на " + em + "." : " Памятка «" + gift.title + "» придёт на почту, которую вы укажете менеджеру.";
  if (test) s += ' <a href="' + gift.file + '" target="_blank" rel="noopener">Открыть PDF</a>.';
  return s;
};
if (form) {
  /* метки UTM: из адреса, а если человек ушёл по ссылкам внутри сайта — из памяти вкладки */
  ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"].forEach(k => {
    let v = params.get(k);
    try { if (v) sessionStorage.setItem(k, v); else v = sessionStorage.getItem(k); } catch (e) {}
    if (v) form.elements[k].value = v;
  });
  form.elements.page.value = location.href;

  /* черновик формы (Fraser «SaaS Playbook»: не терять тех, кто начал и ушёл): поля хранятся только в этом браузере,
     при возврате подставляются; после отправки черновик стирается */
  const DRAFT = "lead-draft", keep = ["name", "phone", "email", "address", "area", "stage", "note"];
  try {
    const d = JSON.parse(localStorage.getItem(DRAFT) || "{}");
    keep.forEach(k => { if (d[k] && !form.elements[k].value) form.elements[k].value = d[k]; });
  } catch (e) {}
  form.addEventListener("input", () => {
    try { localStorage.setItem(DRAFT, JSON.stringify(Object.fromEntries(keep.map(k => [k, form.elements[k].value])))); } catch (e) {}
  });
  const clearDraft = () => { try { localStorage.removeItem(DRAFT); } catch (e) {} };

  const status = document.getElementById("f-status"), submit = document.getElementById("f-submit");
  const setErr = (input, errId, bad) => { input.setAttribute("aria-invalid", bad); document.getElementById(errId).hidden = !bad; };
  /* состояние под кнопкой: sending / ok / error / test — цвет и значок в styles.css (.form-status[data-state]) */
  const setState = (st, html) => { status.dataset.state = st; status.innerHTML = html; };
  let firstTouch = 0;
  form.addEventListener("focusin", () => { if (!firstTouch) firstTouch = Date.now(); });
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const phone = form.elements.phone, address = form.elements.address, consent = form.elements.consent;
    const digits = phone.value.replace(/\D/g, "");
    const phoneBad = !(digits.length === 11 && /^[78]/.test(digits)) && digits.length !== 10;
    const addrBad = address.value.trim().length < 3;
    /* почта необязательна, но если введена — проверяем (Мукминов: список плохих значений — без @, «user@», «@mail.ru», «user@.com», пробел) */
    const email = form.elements.email, em = email.value.trim();
    const emailBad = em !== "" && !/^[^\s@]{1,64}@[^\s@.][^\s@]*\.[^\s@.]{2,}$/.test(em);
    setErr(phone, "e-phone", phoneBad); setErr(address, "e-address", addrBad); setErr(email, "e-email", emailBad);
    if (phoneBad) return phone.focus();
    if (emailBad) return email.focus();
    if (addrBad) return address.focus();
    consent.setAttribute("aria-invalid", !consent.checked); consent.closest(".consent").classList.toggle("bad", !consent.checked);
    if (!consent.checked) { status.textContent = "Отметьте согласие на обработку данных — галочка над кнопкой"; return consent.focus(); }
    if (submit.disabled) return; // уже отправляется — второй клик не шлёт дубль
    /* сколько секунд заполняли форму: уходит на сервер, он отсеивает ботов до Bitrix24 и цели Метрики (находки 12.10) */
    form.elements.fill_s.value = Math.round((Date.now() - (firstTouch || Date.now())) / 1000);
    const data = Object.fromEntries(new FormData(form));
    /* защита от спам-ботов (книга Мукминова: B2B-формы первыми получают ботов): невидимое поле заполнено
       — делаем вид, что приняли, и ничего не шлём. Быстрее 3 секунд после открытия (автозаполнение, быстрый человек) —
       не пишем «принято», а тихо ждём до 3 секунд и отправляем (дизайн-ревью 12.10) */
    if (data.website) { setState("ok", "Заявка принята."); return; }
    if (performance.now() < 3000) await new Promise(r => setTimeout(r, 3000 - performance.now()));
    delete data.website;
    if (!CONFIG.leadEndpoint) {
      /* честное состояние, пока сервера нет: «принято» не пишем (находки 12.10) */
      setState("test", "Тестовый режим: приём заявок ещё не подключён, заявка не отправлена." + giftLink(true));
      console.log("Заявка (тест):", data);
      return;
    }
    /* три состояния (находки 12.10, TexterraBlog/12089): отправляется → принято (только после ответа сервера) → ошибка */
    submit.disabled = true; form.setAttribute("aria-busy", "true"); setState("sending", "Отправляем заявку…");
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 15000);
    try {
      const r = await fetch(CONFIG.leadEndpoint, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data), signal: ctl.signal});
      if (!r.ok) throw new Error(r.status);
      goal("form_submit"); clearDraft(); // цель и очистка черновика — только когда сервер принял заявку
      form.reset(); if (whoSelect) whoSelect.value = data.who;
      setState("ok", "Заявка принята." + giftLink(false) + NEXT);
    } catch (err) {
      /* запасной путь без контактов (её решение 10.10 — только заявка): данные остаются в форме и в черновике браузера */
      setState("error", "Заявка не дошла до нас — сбой связи или сервера. Всё, что вы ввели, сохранено: нажмите кнопку ещё раз через минуту. Если закроете страницу, поля заполнятся сами, когда вернётесь.");
    } finally { clearTimeout(timer); submit.disabled = false; form.removeAttribute("aria-busy"); }
  });
  form.elements.consent.addEventListener("change", e => {
    if (e.target.checked) { e.target.setAttribute("aria-invalid", "false"); e.target.closest(".consent").classList.remove("bad"); status.textContent = ""; }
  });
  ["phone", "address", "email"].forEach(n => form.elements[n].addEventListener("input", () => {
    form.elements[n].setAttribute("aria-invalid", "false"); document.getElementById("e-" + n).hidden = true;
  }));
}

/* шапка: мягкий переход под ней — только когда страницу прокрутили (на верху он ложился полосой на фото первого экрана) */
(() => {
  const top = document.getElementById("top");
  if (!top) return;
  const on = () => top.classList.toggle("scrolled", window.scrollY > 8);
  on(); window.addEventListener("scroll", on, {passive: true});
})();
