// Show/hide password buttons
document.querySelectorAll('[data-toggle-pw]').forEach(function (b) {
  b.addEventListener('click', function () {
    var i = document.getElementById(b.dataset.togglePw);
    var show = i.type === 'password';
    i.type = show ? 'text' : 'password';
    b.textContent = show ? b.dataset.hide : b.dataset.show;
  });
});

// Live password checklist
function pwChecks(pw, confirm) {
  return {
    len: pw.length >= 8, upper: /[A-Z]/.test(pw), lower: /[a-z]/.test(pw),
    num: /\d/.test(pw), sym: /[^\w\s]|_/.test(pw), match: pw.length > 0 && pw === confirm
  };
}
function wirePasswordChecklist(pwId, cfId, listId, onChange) {
  var pw = document.getElementById(pwId), cf = document.getElementById(cfId), ul = document.getElementById(listId);
  if (!pw) return;
  function run() {
    var c = pwChecks(pw.value, cf.value), all = true;
    ul.querySelectorAll('li').forEach(function (li) {
      var ok = c[li.dataset.k]; li.classList.toggle('ok', ok); if (!ok) all = false;
    });
    if (onChange) onChange(all);
  }
  pw.addEventListener('input', run); cf.addEventListener('input', run); run();
}

// Debounced availability check
function debounce(fn, ms) { var t; return function () { var a = arguments; clearTimeout(t); t = setTimeout(function () { fn.apply(null, a); }, ms); }; }
function checkRemote(url, input, msgEl, cb) {
  fetch(url + encodeURIComponent(input.value)).then(function (r) { return r.json(); }).then(function (d) {
    msgEl.textContent = d.ok ? '✓' : d.msg;
    msgEl.className = 'field-msg ' + (d.ok ? 'good' : 'bad');
    cb(d.ok);
  }).catch(function () { cb(true); });
}

// Login: remember phone on this device (only if "remember" ticked)
(function () {
  var f = document.getElementById('login-form');
  if (!f) return;
  var phone = f.querySelector('[name=phone]'), rem = f.querySelector('[name=remember]');
  try {
    var saved = localStorage.getItem('cpg_phone');
    if (saved && !phone.value) { phone.value = saved; rem.checked = true; f.querySelector('[name=password]').focus(); }
  } catch (e) {}
  f.addEventListener('submit', function () {
    try { if (rem.checked) localStorage.setItem('cpg_phone', phone.value); else localStorage.removeItem('cpg_phone'); } catch (e) {}
  });
})();

// Multi-step registration
(function () {
  var form = document.getElementById('reg-form');
  if (!form) return;
  var steps = [].slice.call(form.querySelectorAll('.step')), bar = [].slice.call(document.querySelectorAll('.steps span'));
  var cur = 0, ok = { phone: false, meter: false, pw: false };
  var phone = form.phone, meter = form.meter_no;
  var pm = document.getElementById('phone-msg'), mm = document.getElementById('meter-msg');
  var label = document.getElementById('step-label');

  function show(n) {
    cur = n;
    steps.forEach(function (s, i) { s.classList.toggle('on', i === n); });
    bar.forEach(function (b, i) { b.classList.toggle('done', i <= n); });
    label.textContent = label.dataset.tpl.replace('{n}', n + 1).replace('{name}', steps[n].dataset.title);
    if (n === steps.length - 1) fillReview();
    var f = steps[n].querySelector('input:not([type=radio]):not([type=hidden])'); if (f) f.focus({ preventScroll: true });
  }
  function fillReview() {
    var t = form.querySelector('[name=acct_type]:checked');
    var map = { r_type: t ? t.nextElementSibling.textContent : '', r_name: form.elements['name'].value, r_phone: phone.value, r_email: form.email.value, r_meter: meter.value + ' (' + form.nickname.value + ')' };
    Object.keys(map).forEach(function (k) { document.getElementById(k).textContent = map[k]; });
  }
  var chkPhone = debounce(function () { if (phone.value.length >= 9) checkRemote('/api/check-phone?phone=', phone, pm, function (v) { ok.phone = v; }); }, 350);
  var chkMeter = debounce(function () { if (meter.value.replace(/\s/g, '').length >= 11) checkRemote('/api/check-meter?meter=', meter, mm, function (v) { ok.meter = v; }); }, 350);
  phone.addEventListener('input', function () { ok.phone = false; pm.textContent = ''; chkPhone(); });
  meter.addEventListener('input', function () { ok.meter = false; mm.textContent = ''; chkMeter(); });
  wirePasswordChecklist('password', 'confirm', 'pw-checks', function (v) { ok.pw = v; });

  function valid(n) {
    var s = steps[n];
    if (n === 1) {
      if (form.elements['name'].value.trim().length < 3) { form.elements['name'].focus(); return false; }
      if (!ok.phone) { phone.focus(); if (!pm.textContent) chkPhone(); return false; }
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.value)) { form.email.focus(); return false; }
    }
    if (n === 2) {
      if (!ok.meter) { meter.focus(); return false; }
    }
    if (n === 3 && !ok.pw) return false;
    return true;
  }
  form.addEventListener('click', function (e) {
    var b = e.target.closest('[data-go]'); if (!b) return;
    e.preventDefault();
    var d = parseInt(b.dataset.go, 10);
    if (d > 0 && !valid(cur)) return;
    show(cur + d);
  });
  form.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && cur < steps.length - 1 && e.target.tagName === 'INPUT') {
      e.preventDefault(); if (valid(cur)) show(cur + 1);
    }
  });
  // If the server sent the form back with an error, start at the first step
  if (phone.value) { chkPhone(); } if (meter.value) { chkMeter(); }
  show(0);
})();

// Reset page checklist
wirePasswordChecklist('rpw', 'rcf', 'rchecks', function (v) { var b = document.getElementById('rbtn'); if (b) b.disabled = !v; });

// "Try it" box: same tariff blocks and VAT as the server (Oct 2025 prices; VAT assumed, see app.py)
(function () {
  var box = document.getElementById('tryit');
  if (!box) return;
  var rwf = document.getElementById('t-rwf'), use = document.getElementById('t-use'), usedEl = document.getElementById('t-used');
  var out = { d: document.getElementById('t-days'), k: document.getElementById('t-kwh'), t: document.getElementById('t-date'), r: document.getElementById('t-rows') };
  var vat = parseFloat(box.dataset.vat || '0') / 100;
  var BLOCKS = [[0, 20, 89], [20, 50, 310], [50, 1e9, 369]];
  function calc(money, used) {
    var total = 0, rows = [];
    for (var i = 0; i < BLOCKS.length && money > 0.0001; i++) {
      var from = BLOCKS[i][0], to = BLOCKS[i][1], price = BLOCKS[i][2] * (1 + vat);
      var room = to - Math.max(used, from);
      if (room <= 0) continue;
      var kwh = Math.min(room, money / price);
      rows.push({ label: (to > 1e8 ? from + '+' : from + '–' + to) + ' kWh · ' + Math.round(price) + ' RWF/kWh', kwh: kwh });
      total += kwh; money -= kwh * price;
    }
    return { total: total, rows: rows };
  }
  function run() {
    var m = parseFloat(rwf.value), u = parseFloat(use.value), used = parseFloat(usedEl ? usedEl.value : '0') || 0;
    if (!(m > 0) || !(u > 0)) { out.d.textContent = '–'; out.k.textContent = '–'; out.t.textContent = '–'; if (out.r) out.r.innerHTML = ''; return; }
    var c = calc(m, Math.max(used, 0)), days = Math.floor(c.total / u);
    var buy = new Date(); buy.setDate(buy.getDate() + Math.max(days - 2, 0));
    var loc = document.documentElement.lang === 'fr' ? 'fr-FR' : 'en-GB';
    out.d.textContent = days; out.k.textContent = c.total.toFixed(1);
    out.t.textContent = buy.toLocaleDateString(loc, { weekday: 'short', day: 'numeric', month: 'short' });
    if (out.r) out.r.innerHTML = c.rows.map(function (r) { return '<div><span>' + r.label + '</span><b>' + r.kwh.toFixed(1) + ' kWh</b></div>'; }).join('');
  }
  [rwf, use, usedEl].forEach(function (el) { if (el) el.addEventListener('input', run); });
  run();
})();
