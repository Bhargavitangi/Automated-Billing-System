(() => {
  const form = document.getElementById("billing-form");
  if (!form) return;
  const select = document.getElementById("product-select");
  const qtyInput = document.getElementById("item-qty");
  const body = document.getElementById("cart-body");
  const taxInput = document.getElementById("tax-rate");
  const cartJson = document.getElementById("cart-json");
  let cart = [];

  const money = n => new Intl.NumberFormat("en-IN", {style:"currency", currency:"INR"}).format(n);
  const selectedProduct = () => {
    const option = select.options[select.selectedIndex];
    if (!option || !option.value) return null;
    return {id:Number(option.value), name:option.dataset.name, sku:option.dataset.sku,
      price:Number(option.dataset.price), stock:Number(option.dataset.stock)};
  };

  function render() {
    body.innerHTML = "";
    if (!cart.length) {
      body.innerHTML = '<tr><td colspan="5" class="muted center">Your bill is empty. Add a product above.</td></tr>';
    }
    let subtotal = 0;
    cart.forEach((item, index) => {
      const line = item.price * item.quantity;
      subtotal += line;
      const row = document.createElement("tr");
      row.innerHTML = `<td><strong>${escapeHtml(item.name)}</strong><small class="table-sub">${escapeHtml(item.sku)}</small></td>
        <td>${money(item.price)}</td><td>${item.quantity}</td><td class="amount">${money(line)}</td>
        <td><button type="button" class="remove-item" aria-label="Remove item" data-index="${index}">×</button></td>`;
      body.appendChild(row);
    });
    const rate = Math.min(100, Math.max(0, Number(taxInput.value) || 0));
    const tax = Math.round(subtotal * rate) / 100;
    document.getElementById("subtotal").textContent = money(subtotal);
    document.getElementById("tax-amount").textContent = money(tax);
    document.getElementById("grand-total").textContent = money(subtotal + tax);
    cartJson.value = JSON.stringify(cart.map(item => ({product_id:item.id, quantity:item.quantity})));
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  }

  document.getElementById("add-item").addEventListener("click", () => {
    const product = selectedProduct();
    const quantity = Number(qtyInput.value);
    if (!product) { alert("Please select a product."); return; }
    if (!Number.isInteger(quantity) || quantity < 1) { alert("Quantity must be a whole number greater than zero."); return; }
    const existing = cart.find(item => item.id === product.id);
    const newQuantity = quantity + (existing ? existing.quantity : 0);
    if (newQuantity > product.stock) { alert(`Only ${product.stock} unit(s) are available.`); return; }
    if (existing) existing.quantity = newQuantity;
    else cart.push({...product, quantity});
    select.value = "";
    qtyInput.value = "1";
    render();
  });

  body.addEventListener("click", event => {
    const button = event.target.closest("[data-index]");
    if (!button) return;
    cart.splice(Number(button.dataset.index), 1);
    render();
  });
  taxInput.addEventListener("input", render);
  form.addEventListener("submit", event => {
    if (!cart.length) { event.preventDefault(); alert("Add at least one product to the bill."); return; }
    if (!form.elements.customer_name.value.trim()) { event.preventDefault(); alert("Enter the customer name."); }
  });
  render();
})();
