/**
 * Admin dashboard: CRUD productos, categorías, usuarios, config, import.
 * Depende de api.js (apiFetch, showToast) y auth.js (checkAuth).
 */

// Tabs
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
        });
    });
}

// === PRODUCTOS ===
async function loadProducts() {
    const res = await apiFetch('/api/v1/products/');
    if (!res.ok) return;
    const products = await res.json();
    const items = Array.isArray(products) ? products : (products.items || []);
    const tbody = document.querySelector('#products-table tbody');
    tbody.innerHTML = items.map(p => {
        const primaryImageUrl = getPrimaryImageUrl(p);
        const thumb = primaryImageUrl
            ? `<img src="${primaryImageUrl}" alt="" class="thumb">`
            : '<span class="thumb-empty">—</span>';
        const cats = (p.categories || []).map(c => c.name).join(', ') || '—';
        const tags = (p.tags || []).join(', ') || '—';
        const colorDots = (p.colors || []).map(c => `<span class="color-dot" style="background:${c.hex}" title="${c.name}"></span>`).join('');
        return `<tr>
            <td>${thumb}</td>
            <td>${p.sku}</td>
            <td>${p.name}</td>
            <td>${p.brand || '—'}</td>
            <td>${cats}</td>
            <td>${tags}</td>
            <td>${colorDots || '—'}</td>
            <td>$${p.cost.toFixed(2)}</td>
            <td>${p.unit}</td>
            <td>${p.currency}</td>
            <td class="actions-cell">
                <button class="btn-sm btn-edit" onclick="editProduct('${p.id}')">Editar</button>
                <button class="btn-sm btn-delete" onclick="deleteProduct('${p.id}')">Eliminar</button>
            </td>
        </tr>`;
    }).join('');
}

function getPrimaryImageUrl(product) {
    return (product.image_urls && product.image_urls.length) ? product.image_urls[0] : null;
}

function getImageFilename(imageUrl) {
    if (!imageUrl) return null;
    const parts = imageUrl.split('/');
    return parts.length ? parts[parts.length - 1] : null;
}

function renderImageManager(product) {
    const imgArea = document.getElementById('image-area');
    const imageUrls = product ? (product.image_urls || []) : [];
    const previews = imageUrls.map(url => {
        const filename = getImageFilename(url);
        return `<div class="img-preview-item">
            <img src="${url}" class="img-preview">
            <button class="btn-sm btn-delete" type="button" onclick="deleteProductImage('${product.id}', '${filename}')">Quitar imagen</button>
        </div>`;
    }).join('');

    imgArea.innerHTML = `
        ${previews || '<span class="hint">Sin imágenes cargadas</span>'}
        <input type="file" id="p-image" accept="image/png,image/jpeg,image/webp">
    `;
}

function showProductForm(product = null) {
    document.getElementById('product-form').classList.remove('hidden');
    loadCategoryCheckboxes(product);
    // Reset color state
    window._editColors = product ? [...(product.colors || [])] : [];
    renderColorList();
    if (product) {
        document.getElementById('form-title').textContent = 'Editar Producto';
        document.getElementById('product-edit-id').value = product.id;
        document.getElementById('p-name').value = product.name;
        document.getElementById('p-sku').value = product.sku;
        document.getElementById('p-sku').disabled = true;
        document.getElementById('p-cost').value = product.cost;
        document.getElementById('p-unit').value = product.unit;
        document.getElementById('p-currency').value = product.currency;
        document.getElementById('p-description').value = product.description || '';
        document.getElementById('p-brand').value = product.brand || '';
        document.getElementById('p-tags').value = (product.tags || []).join(', ');
        renderImageManager(product);
    } else {
        document.getElementById('form-title').textContent = 'Nuevo Producto';
        document.getElementById('product-edit-id').value = '';
        document.getElementById('p-name').value = '';
        document.getElementById('p-sku').value = '';
        document.getElementById('p-sku').disabled = false;
        document.getElementById('p-cost').value = '';
        document.getElementById('p-unit').value = 'unidad';
        document.getElementById('p-currency').value = 'USD';
        document.getElementById('p-description').value = '';
        document.getElementById('p-brand').value = '';
        document.getElementById('p-tags').value = '';
        renderImageManager();
    }
}

async function loadCategoryCheckboxes(product = null) {
    const container = document.getElementById('category-checkboxes');
    if (!container) return;
    try {
        const res = await apiFetch('/api/v1/categories/');
        if (!res.ok) return;
        const cats = await res.json();
        const selected = product ? (product.category_ids || []) : [];
        container.innerHTML = cats.map(c => `
            <label class="checkbox-label">
                <input type="checkbox" value="${c.id}" ${selected.includes(c.id) ? 'checked' : ''}>
                ${c.name}
            </label>
        `).join('');
    } catch {}
}

function hideProductForm() {
    document.getElementById('product-form').classList.add('hidden');
}

async function saveProduct() {
    const editId = document.getElementById('product-edit-id').value;
    const categoryIds = Array.from(document.querySelectorAll('#category-checkboxes input:checked')).map(cb => cb.value);
    const tags = document.getElementById('p-tags').value
        .split(',')
        .map(tag => tag.trim())
        .filter(Boolean);

    const data = {
        name: document.getElementById('p-name').value,
        sku: document.getElementById('p-sku').value,
        description: document.getElementById('p-description').value,
        brand: document.getElementById('p-brand').value,
        cost: parseFloat(document.getElementById('p-cost').value),
        unit: document.getElementById('p-unit').value,
        currency: document.getElementById('p-currency').value,
        category_ids: categoryIds,
        colors: window._editColors || [],
        tags,
    };

    let res;
    if (editId) {
        res = await apiFetch('/api/v1/products/' + editId, {
            method: 'PUT', body: JSON.stringify(data),
        });
    } else {
        res = await apiFetch('/api/v1/products/', {
            method: 'POST', body: JSON.stringify(data),
        });
    }

    if (res.ok) {
        const saved = await res.json();
        // Upload image if selected
        const fileInput = document.getElementById('p-image');
        if (fileInput && fileInput.files.length) {
            const form = new FormData();
            form.append('file', fileInput.files[0]);
            await apiFetch('/api/v1/products/' + (saved.id || editId) + '/image', {
                method: 'POST', body: form,
            });
        }
        showToast(editId ? 'Producto actualizado' : 'Producto creado');
        hideProductForm();
        loadProducts();
    } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || 'Error al guardar', 'error');
    }
}

async function editProduct(id) {
    const res = await apiFetch('/api/v1/products/' + id);
    if (res.ok) showProductForm(await res.json());
}

async function deleteProduct(id) {
    if (!confirm('¿Eliminar este producto?')) return;
    const res = await apiFetch('/api/v1/products/' + id, { method: 'DELETE' });
    if (res.ok) { showToast('Producto eliminado'); loadProducts(); }
    else showToast('Error al eliminar', 'error');
}

async function deleteProductImage(id, filename) {
    const res = await apiFetch('/api/v1/products/' + id + '/images/' + encodeURIComponent(filename), { method: 'DELETE' });
    if (res.ok) { showToast('Imagen eliminada'); loadProducts(); editProduct(id); }
    else showToast('Error al eliminar imagen', 'error');
}

// === COLORES (helpers para formulario de producto) ===
function renderColorList() {
    const container = document.getElementById('color-list');
    if (!container) return;
    const colors = window._editColors || [];
    container.innerHTML = colors.map((c, i) => `
        <span class="color-chip">
            <span class="color-dot" style="background:${c.hex}"></span>
            <span>${c.name}</span>
            <button type="button" class="btn-sm btn-delete" onclick="removeColor(${i})">×</button>
        </span>
    `).join('') || '<span class="hint">Sin colores</span>';
}

function addColor() {
    const colors = window._editColors || [];
    if (colors.length >= 6) { showToast('Máximo 6 colores', 'error'); return; }
    const name = document.getElementById('color-name-input').value.trim();
    const hex = document.getElementById('color-hex-input').value.toUpperCase();
    if (!name) { showToast('Ingresa un nombre para el color', 'error'); return; }
    colors.push({ name, hex });
    window._editColors = colors;
    document.getElementById('color-name-input').value = '';
    renderColorList();
}

function removeColor(index) {
    window._editColors.splice(index, 1);
    renderColorList();
}

// === CATEGORÍAS ===
async function loadCategories() {
    const res = await apiFetch('/api/v1/categories/');
    if (!res.ok) return;
    const cats = await res.json();
    const tbody = document.querySelector('#categories-table tbody');
    if (!tbody) return;
    tbody.innerHTML = cats.map(c => `
        <tr>
            <td>${c.name}</td>
            <td><code>${c.slug}</code></td>
            <td>${c.description || '—'}</td>
            <td>${c.is_active ? '✓' : '✗'}</td>
            <td class="actions-cell">
                <button class="btn-sm btn-edit" onclick="editCategory('${c.id}')">Editar</button>
                <button class="btn-sm btn-delete" onclick="deleteCategory('${c.id}')">Eliminar</button>
            </td>
        </tr>
    `).join('');
}

function showCategoryForm(cat = null) {
    document.getElementById('category-form').classList.remove('hidden');
    if (cat) {
        document.getElementById('cat-form-title').textContent = 'Editar Categoría';
        document.getElementById('cat-edit-id').value = cat.id;
        document.getElementById('cat-name').value = cat.name;
        document.getElementById('cat-description').value = cat.description || '';
        document.getElementById('cat-active').checked = cat.is_active;
    } else {
        document.getElementById('cat-form-title').textContent = 'Nueva Categoría';
        document.getElementById('cat-edit-id').value = '';
        document.getElementById('cat-name').value = '';
        document.getElementById('cat-description').value = '';
        document.getElementById('cat-active').checked = true;
    }
}

function hideCategoryForm() {
    document.getElementById('category-form').classList.add('hidden');
}

async function saveCategory() {
    const editId = document.getElementById('cat-edit-id').value;
    const data = {
        name: document.getElementById('cat-name').value,
        description: document.getElementById('cat-description').value,
        is_active: document.getElementById('cat-active').checked,
    };
    let res;
    if (editId) {
        res = await apiFetch('/api/v1/categories/' + editId, { method: 'PUT', body: JSON.stringify(data) });
    } else {
        res = await apiFetch('/api/v1/categories/', { method: 'POST', body: JSON.stringify(data) });
    }
    if (res.ok) {
        showToast(editId ? 'Categoría actualizada' : 'Categoría creada');
        hideCategoryForm();
        loadCategories();
    } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || 'Error al guardar categoría', 'error');
    }
}

async function editCategory(id) {
    const res = await apiFetch('/api/v1/categories/' + id);
    if (res.ok) showCategoryForm(await res.json());
}

async function deleteCategory(id) {
    if (!confirm('¿Eliminar esta categoría?')) return;
    const res = await apiFetch('/api/v1/categories/' + id, { method: 'DELETE' });
    if (res.ok) { showToast('Categoría eliminada'); loadCategories(); }
    else showToast('Error al eliminar', 'error');
}

// === USUARIOS ===
async function loadUsers() {
    const res = await apiFetch('/api/v1/users/');
    if (!res.ok) return;
    const users = await res.json();
    const tbody = document.querySelector('#users-table tbody');
    if (!tbody) return;
    tbody.innerHTML = users.map(u => `
        <tr>
            <td>${u.username}</td>
            <td>${u.email || '—'}</td>
            <td>${u.role || 'admin'}</td>
            <td>${u.is_active ? '✓' : '✗'}</td>
            <td class="actions-cell">
                <button class="btn-sm btn-delete" onclick="deleteUser('${u.id}')">Eliminar</button>
            </td>
        </tr>
    `).join('');
}

function showUserForm() {
    document.getElementById('user-form').classList.remove('hidden');
    document.getElementById('u-username').value = '';
    document.getElementById('u-email').value = '';
    document.getElementById('u-password').value = '';
}

function hideUserForm() {
    document.getElementById('user-form').classList.add('hidden');
}

async function saveUser() {
    const data = {
        username: document.getElementById('u-username').value,
        email: document.getElementById('u-email').value,
        password: document.getElementById('u-password').value,
    };
    const res = await apiFetch('/api/v1/users/', { method: 'POST', body: JSON.stringify(data) });
    if (res.ok) {
        showToast('Usuario creado');
        hideUserForm();
        loadUsers();
    } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || 'Error al crear usuario', 'error');
    }
}

async function deleteUser(id) {
    if (!confirm('¿Eliminar este usuario?')) return;
    const res = await apiFetch('/api/v1/users/' + id, { method: 'DELETE' });
    if (res.ok) { showToast('Usuario eliminado'); loadUsers(); }
    else showToast('Error al eliminar', 'error');
}

// === CONFIGURACIÓN ===
const BRANDING_KEYS = new Set(['site_logo', 'site_icon']);

async function loadConfig() {
    const res = await apiFetch('/api/v1/config/');
    if (!res.ok) return;
    const configs = await res.json();
    // Render non-branding configs
    const regularConfigs = configs.filter(c => !BRANDING_KEYS.has(c.key));
    document.getElementById('config-list').innerHTML = regularConfigs.map(c => {
        const isNumeric = typeof c.value === 'number';
        return `
        <div class="config-card">
            <div class="config-info">
                <strong>${c.key}</strong>
                <span class="config-desc">${c.description}</span>
            </div>
            <div class="config-edit">
                <input type="${isNumeric ? 'number' : 'text'}" id="cfg-${c.key}" value="${c.value}" ${isNumeric ? 'step="any"' : ''}>
                <button class="btn-sm btn-edit" onclick="updateConfig('${c.key}', ${isNumeric})">Guardar</button>
            </div>
        </div>
    `}).join('');
    // Update branding previews
    for (const c of configs) {
        if (c.key === 'site_logo' && c.value) {
            const el = document.getElementById('branding-logo-preview');
            if (el) { el.src = c.value; el.style.display = 'inline'; }
        }
        if (c.key === 'site_icon' && c.value) {
            const el = document.getElementById('branding-icon-preview');
            if (el) { el.src = c.value; el.style.display = 'inline'; }
        }
    }
}

async function updateConfig(key, isNumeric = true) {
    const raw = document.getElementById('cfg-' + key).value;
    const value = isNumeric ? parseFloat(raw) : raw;
    const res = await apiFetch('/api/v1/config/' + key, {
        method: 'PUT', body: JSON.stringify({ value }),
    });
    if (res.ok) showToast('Configuración actualizada');
    else showToast('Error al actualizar', 'error');
}

async function uploadBranding(key) {
    const inputId = key === 'site_logo' ? 'branding-logo-file' : 'branding-icon-file';
    const file = document.getElementById(inputId).files[0];
    if (!file) return showToast('Selecciona un archivo', 'error');
    const form = new FormData();
    form.append('file', file);
    const res = await apiFetch('/api/v1/config/branding/' + key, {
        method: 'POST', body: form,
    });
    if (res.ok) { showToast('Branding actualizado'); loadConfig(); }
    else { const e = await res.json(); showToast(e.detail || 'Error', 'error'); }
}

async function deleteBranding(key) {
    if (!confirm('¿Eliminar este archivo de branding?')) return;
    const res = await apiFetch('/api/v1/config/branding/' + key, { method: 'DELETE' });
    if (res.ok) { showToast('Branding eliminado'); loadConfig(); }
    else showToast('Error al eliminar', 'error');
}

// === IMPORTAR EXCEL ===
function handleFileSelect() {
    const file = document.getElementById('excel-file').files[0];
    document.getElementById('import-btn').disabled = !file;
}

async function importExcel() {
    const file = document.getElementById('excel-file').files[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    document.getElementById('import-btn').disabled = true;
    document.getElementById('import-btn').textContent = 'Importando...';
    const res = await apiFetch('/api/v1/products/import', { method: 'POST', body: form });
    const result = await res.json();
    document.getElementById('import-btn').textContent = 'Importar';
    if (res.ok) {
        document.getElementById('import-result').className = 'import-result';
        document.getElementById('import-result').innerHTML =
            `<strong>Resultado:</strong> ${result.created} creados, ${result.updated} actualizados, ${result.total} total`;
        showToast('Importación completada');
        loadProducts();
    } else {
        document.getElementById('import-result').className = 'import-result error';
        document.getElementById('import-result').textContent = result.detail || 'Error';
        showToast('Error en importación', 'error');
    }
    document.getElementById('import-btn').disabled = false;
}

// Init
document.addEventListener('DOMContentLoaded', async () => {
    if (!(await checkAuth())) return;
    initTabs();
    loadProducts();
    loadCategories();
    loadUsers();
    loadConfig();
});
