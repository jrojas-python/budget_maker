/**
 * HTTP wrapper con interceptor JWT para Budget Maker.
 */

const API_BASE = '/api/v1';

function getToken() {
    return localStorage.getItem('jwt_token');
}

function setToken(token) {
    localStorage.setItem('jwt_token', token);
}

function clearToken() {
    localStorage.removeItem('jwt_token');
}

function isLoggedIn() {
    return !!getToken();
}

async function apiFetch(url, options = {}) {
    const token = getToken();
    const headers = options.headers || {};

    if (token && !headers['Authorization']) {
        headers['Authorization'] = 'Bearer ' + token;
    }

    if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
    }

    const fullUrl = url.startsWith('/') ? url : API_BASE + '/' + url;

    const res = await fetch(fullUrl, { ...options, headers });

    if (res.status === 401) {
        clearToken();
        if (window.location.pathname.startsWith('/admin') && window.location.pathname !== '/admin/login') {
            window.location.href = '/admin/login';
        }
    }

    return res;
}

function showToast(msg, type = 'success') {
    let t = document.getElementById('toast');
    if (!t) {
        t = document.createElement('div');
        t.id = 'toast';
        document.body.appendChild(t);
    }
    t.textContent = msg;
    t.className = 'toast ' + type;
    setTimeout(() => t.className = 'toast hidden', 3000);
}

function showLoader(containerId) {
    const el = document.getElementById(containerId);
    if (el) el.innerHTML = '<div class="loading">Cargando...</div>';
}
