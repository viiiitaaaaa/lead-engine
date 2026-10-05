/* Общий скрипт сайта: главная и страницы клиентов. Каждая часть работает, только если её блок есть на странице. */

/* ===== Настройки сайта — меняются здесь ===== */
const CONFIG = {
  // Адрес приёма заявок (серверный обработчик, который передаёт заявку в Bitrix24). Пусто — форма в тестовом режиме.
  leadEndpoint: "",
  defaultWho: "sobstvennik",
  phone: "8 (495) 266-05-24",
};

/* слайдер первого экрана: смена каждые 6 с, пауза при наведении и когда вкладка скрыта, свайп на телефоне */
(() => {
  const box = document.getElementById("slides");
  if (!box || box.children.length < 2) return;
  const hero = box.parentElement;
  const sl = [...box.children], dots = document.getElementById("sl-dots"), num = document.getElementById("sl-n");
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  sl.forEach(() => dots.appendChild(document.createElement("i")));
  let i = 0, timer = null;
  const show = k => {
    i = (k + sl.length) % sl.length;
    sl.forEach((s, j) => { s.classList.toggle("is-on", j === i); s.setAttribute("aria-hidden", j !== i); });
    [...dots.children].forEach((d, j) => d.classList.toggle("on", j === i));
    num.textContent = String(i + 1).padStart(2, "0");
  };
  const stop = () => { clearInterval(timer); timer = null; };
  const play = () => { stop(); if (!still) timer = setInterval(() => show(i + 1), 6000); };
  hero.querySelector(".sl-prev").addEventListener("click", () => { show(i - 1); play(); });
  hero.querySelector(".sl-next").addEventListener("click", () => { show(i + 1); play(); });
  hero.addEventListener("mouseenter", stop); hero.addEventListener("mouseleave", play);
  document.addEventListener("visibilitychange", () => document.hidden ? stop() : play());
  let x0 = null;
  hero.addEventListener("touchstart", e => { x0 = e.touches[0].clientX; }, {passive: true});
  hero.addEventListener("touchend", e => {
    if (x0 === null) return; const dx = e.changedTouches[0].clientX - x0; x0 = null;
    if (Math.abs(dx) > 50) { show(i + (dx < 0 ? 1 : -1)); play(); }
  });
  show(0); play();
})();

/* меню на телефоне */
const top_ = document.getElementById("top"), burger = top_ && top_.querySelector(".burger");
if (burger) {
  burger.addEventListener("click", () => {
    const open = top_.classList.toggle("open");
    burger.setAttribute("aria-expanded", open);
    burger.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
  });
  top_.querySelectorAll(".nav a, .top-contacts a").forEach(a => a.addEventListener("click", () => {
    top_.classList.remove("open"); burger.setAttribute("aria-expanded", "false");
  }));
}

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

/* форма заявки */
const form = document.getElementById("lead-form");
if (form) {
  /* метки UTM: из адреса, а если человек ушёл по ссылкам внутри сайта — из памяти вкладки */
  ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"].forEach(k => {
    let v = params.get(k);
    try { if (v) sessionStorage.setItem(k, v); else v = sessionStorage.getItem(k); } catch (e) {}
    if (v) form.elements[k].value = v;
  });
  form.elements.page.value = location.href;

  const status = document.getElementById("f-status"), submit = document.getElementById("f-submit");
  const setErr = (input, errId, bad) => { input.setAttribute("aria-invalid", bad); document.getElementById(errId).hidden = !bad; };
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const phone = form.elements.phone, address = form.elements.address, consent = form.elements.consent;
    const digits = phone.value.replace(/\D/g, "");
    const phoneBad = !(digits.length === 11 && /^[78]/.test(digits)) && digits.length !== 10;
    const addrBad = address.value.trim().length < 3;
    setErr(phone, "e-phone", phoneBad); setErr(address, "e-address", addrBad);
    if (phoneBad) return phone.focus();
    if (addrBad) return address.focus();
    if (!consent.checked) { status.textContent = "Отметьте согласие на обработку данных"; return consent.focus(); }
    const data = Object.fromEntries(new FormData(form));
    if (!CONFIG.leadEndpoint) {
      status.textContent = "Тестовый режим: приём заявок ещё не подключён, заявка не отправлена.";
      console.log("Заявка (тест):", data);
      return;
    }
    submit.disabled = true; status.textContent = "Отправляем…";
    try {
      const r = await fetch(CONFIG.leadEndpoint, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
      if (!r.ok) throw new Error(r.status);
      form.reset(); if (whoSelect) whoSelect.value = data.who;
      status.textContent = "Заявка принята. Менеджер позвонит вам в рабочее время.";
    } catch (err) {
      status.textContent = "Не получилось отправить. Позвоните нам: " + CONFIG.phone;
    } finally { submit.disabled = false; }
  });
  ["phone", "address"].forEach(n => form.elements[n].addEventListener("input", () => {
    form.elements[n].setAttribute("aria-invalid", "false"); document.getElementById("e-" + n).hidden = true;
  }));
}
