/**
 * Autenticación: login, logout y route guard.
 * Depende de api.js (getToken, setToken, clearToken, isLoggedIn, apiFetch, showToast).
 */

async function login(username, password) {
    const btn = document.getElementById('login-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Ingresando...'; }

    try {
        const res = await fetch('/api/v1/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });

        if (res.ok) {
            const data = await res.json();
            setToken(data.access_token);
            window.location.href = '/admin';
        } else if (res.status === 401) {
            showToast('Credenciales inválidas', 'error');
        } else {
            const err = await res.json().catch(() => ({}));
            showToast(err.detail || 'Error al iniciar sesión', 'error');
        }
    } catch {
        showToast('Error de conexión', 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Iniciar Sesión'; }
    }
}

function logout() {
    clearToken();
    window.location.href = '/admin/login';
}

async function checkAuth() {
    if (!isLoggedIn()) {
        window.location.href = '/admin/login';
        return false;
    }
    try {
        const res = await apiFetch('/api/v1/auth/me');
        if (!res.ok) {
            clearToken();
            window.location.href = '/admin/login';
            return false;
        }
        return true;
    } catch {
        clearToken();
        window.location.href = '/admin/login';
        return false;
    }
}

function updateNavbar() {
    const navLinks = document.querySelector('.nav-links');
    if (!navLinks) return;
    if (isLoggedIn()) {
        navLinks.innerHTML = `
            <a href="/">Catálogo</a>
            <a href="/admin">Panel Admin</a>
            <a href="#" onclick="logout(); return false;">Cerrar Sesión</a>
        `;
    } else {
        navLinks.innerHTML = `
            <a href="/">Catálogo</a>
            <a href="/admin/login">Admin</a>
        `;
    }
}

document.addEventListener('DOMContentLoaded', updateNavbar);
