(() => {
  const $ = s => document.querySelector(s);
  const products = JSON.parse($('#products-data').textContent);
  const byId = Object.fromEntries(products.map(p => [p.id, p]));
  const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
  const url = $('#billing').dataset.checkoutUrl;
  const fm = n => '₹' + (+n || 0).toFixed(2);
  const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let cart = [];   // [{id, qty}]
  let query = '';

  const discount = () => Math.min(100, Math.max(0, +$('#disc').value || 0));

  function totals() {
    const sub = cart.reduce((a, i) => a + i.qty * +byId[i.id].price, 0);
    const dv = sub * discount() / 100, tax = (sub - dv) * 0.05;
    return {sub, dv, tax, total: sub - dv + tax};
  }

  function renderProducts() {
    const q = query.toLowerCase();
    const list = products.filter(p => p.stock > 0 && (p.name + p.sku).toLowerCase().includes(q));
    $('#pg').innerHTML = list.map(p =>
      `<button class="pc" data-add="${p.id}"><b>${esc(p.name)}</b><span>${fm(p.price)}</span><small>${esc(p.sku)} · ${p.stock} in stock</small></button>`
    ).join('') || '<p class="mut">No matching product in stock.</p>';
  }

  function renderCart() {
    $('#lines').innerHTML = cart.map(i => {
      const p = byId[i.id];
      return `<div class="ln"><span>${esc(p.name)}<br><small class="mut">${fm(p.price)}</small></span>
        <span><button class="g" data-qty="-1" data-id="${i.id}">−</button> ${i.qty} <button class="g" data-qty="1" data-id="${i.id}">+</button></span></div>`;
    }).join('') || '<p class="mut">Tap a product to add it.</p>';
    renderTotals();
  }

  function renderTotals() {
    const t = totals();
    $('#totals').innerHTML =
      `<div class="tot"><span>Subtotal</span><span>${fm(t.sub)}</span></div>
       <div class="tot"><span>Discount</span><span>−${fm(t.dv)}</span></div>
       <div class="tot"><span>GST 5%</span><span>${fm(t.tax)}</span></div>
       <div class="tot f"><span>Total</span><span>${fm(t.total)}</span></div>`;
  }

  function change(id, d) {
    const line = cart.find(i => i.id === id), p = byId[id];
    if (!line) { if (d > 0) cart.push({id, qty: 1}); }
    else { line.qty = Math.min(p.stock, line.qty + d); if (line.qty < 1) cart = cart.filter(i => i.id !== id); }
    renderCart();
  }

  $('#pg').addEventListener('click', e => { const b = e.target.closest('[data-add]'); if (b) change(+b.dataset.add, 1); });
  $('#lines').addEventListener('click', e => { const b = e.target.closest('[data-qty]'); if (b) change(+b.dataset.id, +b.dataset.qty); });
  $('#bs').addEventListener('input', e => { query = e.target.value; renderProducts(); });
  $('#disc').addEventListener('input', renderTotals);
  $('#clear').addEventListener('click', () => { cart = []; $('#disc').value = 0; $('#cerr').textContent = ''; renderCart(); });

  $('#pay-btn').addEventListener('click', async e => {
    if (!cart.length) return;
    const btn = e.currentTarget;
    btn.disabled = true; $('#cerr').textContent = '';
    try {
      const r = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
        body: JSON.stringify({items: cart, discount: discount(), payment: $('#pay').value}),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || 'Could not complete the bill.');
      location.href = j.receipt_url;
    } catch (err) {
      $('#cerr').textContent = err.message;
      btn.disabled = false;
    }
  });

  renderProducts(); renderCart();
})();
