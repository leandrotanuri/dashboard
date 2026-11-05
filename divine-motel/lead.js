// Antes de abrir o WhatsApp, pede nome + telefone, envia o lead pro GTM (dataLayer)
// e, se LEADS_ENDPOINT estiver preenchido, grava na planilha (ver leads-apps-script.gs).
(function () {
  const WHATSAPP = "5517992055344";
  const LEADS_ENDPOINT = "https://script.google.com/macros/s/AKfycbzybJm-422ZkYM4LckOXS2LamWp_zJxVRmxrEmf_Jj_PVkBbAgeFfeptxEfGFpdPZr-/exec"; // App da Web do Google Apps Script (planilha DIVINE MOTEL - Leads e UTMs)
  const LEAD_KEY = "divine_lead";
  const UTM_KEY = "divine_utm";
  const TRACK_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "fbclid", "gclid"];

  window.dataLayer = window.dataLayer || [];

  function read(storage, key) {
    try { return JSON.parse(storage.getItem(key) || "null"); } catch (e) { return null; }
  }
  function write(storage, key, value) {
    try { storage.setItem(key, JSON.stringify(value)); } catch (e) {}
  }

  // UTMs e click ids da visita (guardados na sessão pra não perder ao navegar)
  const tracking = read(sessionStorage, UTM_KEY) || {};
  const qs = new URLSearchParams(location.search);
  TRACK_KEYS.forEach(k => { if (qs.get(k)) tracking[k] = qs.get(k); });
  write(sessionStorage, UTM_KEY, tracking);

  const digits = s => (s || "").replace(/\D/g, "");
  function maskPhone(v) {
    const d = digits(v).slice(0, 11);
    if (d.length <= 2) return d.length ? "(" + d : "";
    if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
    if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
    return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
  }

  // Modal (estilo próprio pra funcionar nas 3 versões da LP)
  const style = document.createElement("style");
  style.textContent = `
    .lm-overlay{position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.6);display:none;align-items:center;justify-content:center;padding:16px}
    .lm-overlay.open{display:flex}
    .lm-box{position:relative;width:100%;max-width:400px;background:#fff;color:#1c1a19;border-radius:18px;padding:28px 24px 22px;font-family:Inter,system-ui,sans-serif;box-shadow:0 24px 60px rgba(0,0,0,.35)}
    .lm-box h3{font-family:Manrope,Inter,sans-serif;font-size:1.35rem;font-weight:800;margin:0 0 .3rem}
    .lm-box p{color:#6b645e;font-size:.95rem;margin:0 0 1.1rem;line-height:1.5}
    .lm-box label{display:block;font-size:.85rem;font-weight:600;margin:0 0 .3rem}
    .lm-box input{width:100%;box-sizing:border-box;font:inherit;font-size:1rem;padding:.8rem .9rem;border:1px solid #d9d3cd;border-radius:10px;margin-bottom:.9rem;color:#1c1a19;background:#fff}
    .lm-box input:focus{outline:2px solid #22c55e;border-color:transparent}
    .lm-box button[type=submit]{width:100%;border:0;border-radius:12px;padding:1rem;font:inherit;font-weight:700;font-size:1rem;background:#22c55e;color:#052e14;cursor:pointer}
    .lm-err{color:#c0262d;font-size:.85rem;margin:-.4rem 0 .8rem;min-height:1em}
    .lm-close{position:absolute;top:10px;right:12px;border:0;background:none;font-size:1.6rem;line-height:1;color:#8a827c;cursor:pointer}
    .lm-legal{font-size:.75rem;color:#8a827c;margin:.8rem 0 0;text-align:center}`;
  document.head.appendChild(style);

  const overlay = document.createElement("div");
  overlay.className = "lm-overlay";
  overlay.innerHTML = `
    <form class="lm-box" novalidate>
      <button type="button" class="lm-close" aria-label="Fechar">×</button>
      <h3>Quase lá! 😊</h3>
      <p>Deixe seu nome e WhatsApp pra gente te atender mais rápido.</p>
      <label for="lm-nome">Nome</label>
      <input id="lm-nome" name="nome" autocomplete="given-name" placeholder="Seu nome">
      <label for="lm-tel">WhatsApp</label>
      <input id="lm-tel" name="telefone" type="tel" inputmode="numeric" autocomplete="tel-national" placeholder="(17) 99999-9999">
      <div class="lm-err" role="alert"></div>
      <button type="submit">Continuar no WhatsApp</button>
      <p class="lm-legal">Seus dados são usados só para o atendimento do Divine Motel.</p>
    </form>`;
  document.body.appendChild(overlay);

  const form = overlay.querySelector("form");
  const nomeEl = form.querySelector("#lm-nome");
  const telEl = form.querySelector("#lm-tel");
  const errEl = form.querySelector(".lm-err");
  let pendingMsg = "";

  telEl.addEventListener("input", () => { telEl.value = maskPhone(telEl.value); });

  function open(msg) {
    pendingMsg = msg;
    errEl.textContent = "";
    overlay.classList.add("open");
    setTimeout(() => nomeEl.focus(), 50);
  }
  function close() { overlay.classList.remove("open"); }
  overlay.querySelector(".lm-close").addEventListener("click", close);
  overlay.addEventListener("click", e => { if (e.target === overlay) close(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") close(); });

  function sendLead(lead, interesse, repetido) {
    const payload = Object.assign({
      nome: lead.nome,
      telefone: lead.telefone,
      interesse: interesse,
      pagina: location.pathname,
      repetido: repetido
    }, tracking);

    // Nome/telefone vão só em user_data (formato de conversões otimizadas). Não mande como parâmetro pro GA4.
    window.dataLayer.push({
      event: "lead_whatsapp",
      lead_interesse: interesse,
      lead_pagina: location.pathname,
      lead_repetido: repetido,
      user_data: { phone_number: "+55" + digits(lead.telefone), address: { first_name: lead.nome } }
    });

    if (LEADS_ENDPOINT && navigator.sendBeacon) {
      navigator.sendBeacon(LEADS_ENDPOINT, JSON.stringify(payload));
    }
  }

  function goWhatsApp(lead, msg) {
    const text = `Olá! Sou ${lead.nome}. ${msg.replace(/^Olá!\s*/, "")}`;
    const url = `https://wa.me/${WHATSAPP}?text=${encodeURIComponent(text)}`;
    const win = window.open(url, "_blank", "noopener");
    if (!win) location.href = url;
  }

  form.addEventListener("submit", e => {
    e.preventDefault();
    const nome = nomeEl.value.trim();
    const tel = digits(telEl.value);
    if (nome.length < 2) { errEl.textContent = "Digite seu nome."; nomeEl.focus(); return; }
    if (tel.length < 10) { errEl.textContent = "Digite um WhatsApp válido com DDD."; telEl.focus(); return; }
    const lead = { nome: nome, telefone: maskPhone(tel) };
    write(localStorage, LEAD_KEY, lead);
    sendLead(lead, pendingMsg, false);
    close();
    goWhatsApp(lead, pendingMsg);
  });

  document.querySelectorAll(".js-wpp").forEach(el => {
    el.href = `https://wa.me/${WHATSAPP}`;
    el.addEventListener("click", e => {
      e.preventDefault();
      const msg = el.dataset.msg || "Olá!";
      const saved = read(localStorage, LEAD_KEY);
      // Quem já preencheu uma vez vai direto, sem formulário
      if (saved && saved.nome && saved.telefone) {
        sendLead(saved, msg, true);
        goWhatsApp(saved, msg);
      } else {
        open(msg);
      }
    });
  });
})();
