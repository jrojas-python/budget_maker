/**
 * Catálogo público: búsqueda, filtros, paginación, carrito y presupuesto.
 * Depende de api.js (apiFetch, showToast).
 */

const cart = {};
let taxPercent = 18;
let currentPage = 1;
let totalPages = 1;
let debounceTimer = null;

async function loadTax() {
    try {
        const res = await apiFetch('/api/v1/config/porcentaje_impuesto');
        if (res.ok) { const c = await res.json(); taxPercent = parseFloat(c.value); }
    } catch {}
}

async function loadCategories() {
    try {
        const res = await apiFetch('/api/v1/categories/?active_only=true');
        if (!res.ok) return;
        const cats = await res.json();
        const sel = document.getElementById('filter-category');
        if (!sel) return;
        cats.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.slug;
            opt.textContent = c.name;
            sel.appendChild(opt);
        });
    } catch {}
}

function buildSearchParams() {
    const params = new URLSearchParams();
    const q = document.getElementById('search-input')?.value.trim();
    if (q) params.set('q', q);

    const cat = document.getElementById('filter-category')?.value;
    if (cat) params.set('category_slug', cat);

    const minP = document.getElementById('filter-min-price')?.value;
    if (minP) params.set('min_price', minP);

    const maxP = document.getElementById('filter-max-price')?.value;
    if (maxP) params.set('max_price', maxP);

    const sort = document.getElementById('filter-sort')?.value;
    if (sort) params.set('sort_by', sort);

    params.set('page', currentPage);
    params.set('limit', 12);
    return params;
}

async function loadCatalog() {
    const grid = document.getElementById('catalog-grid');
    grid.innerHTML = '<div class="loading">Cargando productos...</div>';

    const params = buildSearchParams();
    let url, products, pagination;

    try {
        url = '/api/v1/products/search?' + params.toString();
        const res = await apiFetch(url);
        if (!res.ok) { grid.innerHTML = '<p class="cart-empty">Error al cargar productos.</p>'; return; }

        const data = await res.json();
        products = data.items || [];
        totalPages = data.pages || 1;
    } catch {
        grid.innerHTML = '<p class="cart-empty">Error de conexión.</p>';
        return;
    }

    if (!products.length) {
        grid.innerHTML = '<p class="cart-empty">No se encontraron productos.</p>';
        updatePagination();
        return;
    }

    window._products = {};
    grid.innerHTML = products.map(p => {
        window._products[p.sku] = p;
        const entry = cart[p.sku];
        const qty = entry ? entry.quantity : 0;
        const selectedColor = entry ? entry.color_hex : (p.colors && p.colors.length ? p.colors[0].hex : null);
        const primaryImageUrl = (p.image_urls && p.image_urls.length) ? p.image_urls[0] : null;
        const imgHtml = primaryImageUrl
            ? `<img src="${primaryImageUrl}" alt="${p.name}" class="product-img" loading="lazy">`
            : `<div class="product-img-placeholder"><span>Sin imagen</span></div>`;
        const catBadges = (p.categories || []).map(c => `<span class="badge">${c.name}</span>`).join('');
        const colorDots = (p.colors || []).map(c => {
            const sel = c.hex === selectedColor ? ' selected' : '';
            return `<span class="color-dot${sel}" style="background:${c.hex}" title="${c.name}" onclick="selectColor('${p.sku}','${c.hex}')"></span>`;
        }).join('');
        const colorSection = colorDots ? `<div class="color-selector">${colorDots}</div>` : '';
        return `
        <article class="product-card${qty > 0 ? ' selected' : ''}" id="card-${p.sku}" data-sku="${p.sku}">
            <figure class="product-figure">${imgHtml}</figure>
            <div class="product-info">
                <span class="product-sku">${p.sku}</span>
                ${catBadges ? '<div class="product-badges">' + catBadges + '</div>' : ''}
                ${colorSection}
                <h4>${p.name}</h4>                ${p.brand ? '<span class=\"product-brand\">' + p.brand + '</span>' : ''}
                ${p.description ? '<p class=\"product-description\">' + p.description + '</p>' : ''}                <p class="product-price">$${p.cost.toFixed(2)} <span class="product-unit">/ ${p.unit}</span></p>
            </div>
            <div class="product-actions">
                <button class="btn-sm btn-minus" onclick="changeQty('${p.sku}', -1)" ${qty === 0 ? 'disabled' : ''}>−</button>
                <span class="qty-display" id="qty-${p.sku}">${qty}</span>
                <button class="btn-sm btn-plus" onclick="changeQty('${p.sku}', 1)">+</button>
            </div>
        </article>`;
    }).join('');

    updatePagination();
}

function updatePagination() {
    const el = document.getElementById('pagination');
    if (!el) return;
    if (totalPages <= 1) { el.innerHTML = ''; return; }
    el.innerHTML = `
        <button class="btn btn-secondary" onclick="goPage(${currentPage - 1})" ${currentPage <= 1 ? 'disabled' : ''}>← Anterior</button>
        <span>Página ${currentPage} de ${totalPages}</span>
        <button class="btn btn-secondary" onclick="goPage(${currentPage + 1})" ${currentPage >= totalPages ? 'disabled' : ''}>Siguiente →</button>
    `;
}

function goPage(page) {
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    loadCatalog();
}

function onSearchInput() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => { currentPage = 1; loadCatalog(); }, 300);
}

function onFilterChange() {
    currentPage = 1;
    loadCatalog();
}

function selectColor(sku, hex) {
    if (cart[sku]) cart[sku].color_hex = hex;
    // Store selection on card for when item is added later
    const card = document.getElementById('card-' + sku);
    if (card) {
        card.dataset.selectedColor = hex;
        card.querySelectorAll('.color-dot').forEach(d => d.classList.remove('selected'));
        card.querySelectorAll('.color-dot').forEach(d => {
            if (d.style.background === hex || d.style.backgroundColor === hex.toLowerCase())
                d.classList.add('selected');
        });
    }
    updateCart();
}

function changeQty(sku, delta) {
    const entry = cart[sku];
    const current = entry ? entry.quantity : 0;
    const next = Math.max(0, current + delta);
    if (next === 0) {
        delete cart[sku];
    } else {
        const p = window._products[sku];
        const card = document.getElementById('card-' + sku);
        const selectedFromDom = card ? card.dataset.selectedColor : null;
        const defaultColor = p && p.colors && p.colors.length ? p.colors[0].hex : null;
        if (!cart[sku]) cart[sku] = { quantity: next, color_hex: selectedFromDom || defaultColor };
        else cart[sku].quantity = next;
    }

    const qtyEl = document.getElementById('qty-' + sku);
    if (qtyEl) qtyEl.textContent = next;
    const card = document.getElementById('card-' + sku);
    if (card) {
        card.classList.toggle('selected', next > 0);
        card.querySelector('.btn-minus').disabled = next === 0;
    }
    updateCart();
}

function updateCart() {
    const items = Object.entries(cart);
    const cartEl = document.getElementById('cart-items');
    const totalsEl = document.getElementById('cart-totals');
    const formEl = document.getElementById('client-form');
    const btnEl = document.getElementById('btn-create-budget');

    if (!items.length) {
        cartEl.innerHTML = '<p class="cart-empty">No hay productos seleccionados</p>';
        totalsEl.classList.add('hidden');
        formEl.classList.add('hidden');
        btnEl.disabled = true;
        return;
    }

    let subtotal = 0;
    cartEl.innerHTML = items.map(([sku, entry]) => {
        const p = window._products[sku];
        if (!p) return '';
        const qty = entry.quantity;
        const line = p.cost * qty;
        subtotal += line;
        const colorInfo = entry.color_hex
            ? `<span class="color-dot" style="background:${entry.color_hex};width:12px;height:12px"></span>`
            : '';
        return `<div class="cart-item"><span>${colorInfo} ${p.name} × ${qty}</span><span>$${line.toFixed(2)}</span></div>`;
    }).join('');

    const taxAmt = subtotal * (taxPercent / 100);
    const total = subtotal + taxAmt;

    document.getElementById('cart-subtotal').textContent = '$' + subtotal.toFixed(2);
    document.getElementById('cart-tax-pct').textContent = taxPercent;
    document.getElementById('cart-tax').textContent = '$' + taxAmt.toFixed(2);
    document.getElementById('cart-total').textContent = '$' + total.toFixed(2);

    totalsEl.classList.remove('hidden');
    formEl.classList.remove('hidden');
    btnEl.disabled = false;
}

async function createBudget() {
    const nombres = document.getElementById('c-nombres').value.trim();
    const apellidos = document.getElementById('c-apellidos').value.trim();
    if (!nombres || !apellidos) { showToast('Nombres y apellidos son requeridos', 'error'); return; }

    const items = Object.entries(cart).map(([sku, entry]) => {
        const obj = { sku, quantity: entry.quantity };
        if (entry.color_hex) obj.color_hex = entry.color_hex;
        return obj;
    });
    const body = {
        client_info: {
            nombres,
            apellidos,
            documento: document.getElementById('c-documento').value.trim(),
            direccion: document.getElementById('c-direccion').value.trim(),
            vendedor: document.getElementById('c-vendedor').value.trim(),
        },
        items,
    };

    const btn = document.getElementById('btn-create-budget');
    btn.disabled = true;
    btn.textContent = 'Creando...';

    const res = await apiFetch('/api/v1/budgets/', {
        method: 'POST',
        body: JSON.stringify(body),
    });

    btn.textContent = 'Crear Presupuesto';
    btn.disabled = false;

    if (res.ok) {
        const b = await res.json();
        document.getElementById('modal-code').textContent = b.code;
        const fecha = new Date(b.created_at);
        document.getElementById('modal-date').textContent = fecha.toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric' });

        document.getElementById('modal-client-name').textContent = b.client_info.nombres + ' ' + b.client_info.apellidos;
        document.getElementById('modal-client-doc').textContent = b.client_info.documento || '—';
        document.getElementById('modal-client-dir').textContent = b.client_info.direccion || '—';
        document.getElementById('modal-client-vendor').textContent = b.client_info.vendedor || '—';

        document.getElementById('modal-items').innerHTML = b.items.map(it => {
            const colorCell = it.color_hex
                ? `<span class="color-dot" style="background:${it.color_hex};width:12px;height:12px"></span> ${it.color_name || ''}`
                : '—';
            return `<tr><td>${it.sku}</td><td>${it.name}</td><td>${colorCell}</td><td>${it.quantity}</td><td>$${it.unit_cost.toFixed(2)}</td><td>$${it.line_total.toFixed(2)}</td></tr>`;
        }).join('');

        document.getElementById('modal-subtotal').textContent = '$' + b.subtotal.toFixed(2);
        document.getElementById('modal-tax-pct').textContent = b.tax_percent;
        document.getElementById('modal-tax').textContent = '$' + b.tax_amount.toFixed(2);
        document.getElementById('modal-total').textContent = '$' + b.total.toFixed(2);

        const baseUrl = window.location.origin;
        document.getElementById('modal-link').href = baseUrl + '/presupuesto/' + b.uuid;
        document.getElementById('modal-pdf').href = baseUrl + '/presupuesto/' + b.uuid + '/pdf';

        const clientName = (b.client_info.nombres + ' ' + b.client_info.apellidos).trim();
        let waLines = [
            `*COTIZACIÓN ${b.code}*`, `Cliente: ${clientName}`,
            `Fecha: ${document.getElementById('modal-date').textContent}`,
            `*${b.items.length} líneas · ${b.items.reduce((s, i) => s + i.quantity, 0)} unidades*`, '',
        ];
        b.items.forEach(it => {
            const colorTxt = it.color_name ? ` · ${it.color_name}` : '';
            waLines.push(`• ${it.sku} · ${it.name}${colorTxt} · ${it.quantity}x $${it.unit_cost.toFixed(2)}`);
        });
        waLines.push('', '*TOTALES:*', `Subtotal: $${b.subtotal.toFixed(2)}`, `Total: $${b.total.toFixed(2)}`);
        waLines.push('', `Ver online: ${baseUrl}/presupuesto/${b.uuid}`);
        document.getElementById('modal-whatsapp').href = 'https://wa.me/?text=' + encodeURIComponent(waLines.join('\n'));

        document.getElementById('budget-modal').classList.remove('hidden');
        showToast('Presupuesto creado: ' + b.code);
    } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || 'Error al crear presupuesto', 'error');
    }
}

function closeModal() {
    document.getElementById('budget-modal').classList.add('hidden');
    Object.keys(cart).forEach(sku => delete cart[sku]);
    loadCatalog();
    updateCart();
    document.querySelectorAll('.client-form input').forEach(i => i.value = '');
}

async function loadBrandingCatalog() {
    try {
        const res = await fetch('/api/v1/config/');
        if (!res.ok) return;
        const configs = await res.json();
        const map = {};
        configs.forEach(c => map[c.key] = c.value);
        if (map.site_subtitle) {
            const el = document.getElementById('catalog-subtitle');
            if (el) { el.textContent = map.site_subtitle; el.style.display = 'block'; }
        }
    } catch(e) {}
}

document.addEventListener('DOMContentLoaded', () => {
    loadTax();
    loadCategories();
    loadCatalog();
    loadBrandingCatalog();
});
