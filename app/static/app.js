let map;
let newRoutePoints = [];
let newRouteMarkers = [];
let newRoutePolyline = null;
let displayedRoutePolyline = null;
let displayedRouteLabels = [];

function initMap() {
    map = L.map("map").setView([43.0, 44.0], 8);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    map.on("click", onMapClick);
}

function onMapClick(e) {
    const point = { lat: e.latlng.lat, lng: e.latlng.lng };
    newRoutePoints.push(point);

    const marker = L.circleMarker(e.latlng, {
        radius: 6,
        color: "#e94560",
        fillColor: "#e94560",
        fillOpacity: 0.9,
    }).addTo(map);
    newRouteMarkers.push(marker);

    updatePolyline();
    updateRouteInfo();
}

function updatePolyline() {
    if (newRoutePolyline) {
        map.removeLayer(newRoutePolyline);
    }
    if (newRoutePoints.length >= 2) {
        newRoutePolyline = L.polyline(newRoutePoints, {
            color: "#e94560",
            weight: 3,
            dashArray: "8, 6",
        }).addTo(map);
    }
}

function clearNewRoute() {
    newRoutePoints = [];
    newRouteMarkers.forEach((m) => map.removeLayer(m));
    newRouteMarkers = [];
    if (newRoutePolyline) {
        map.removeLayer(newRoutePolyline);
        newRoutePolyline = null;
    }
    document.getElementById("route-name").value = "";
    document.getElementById("route-desc").value = "";
    updateRouteInfo();
}

function updateRouteInfo() {
    document.getElementById("point-count").textContent = newRoutePoints.length;

    if (newRoutePoints.length < 2) {
        document.getElementById("route-distance").textContent = "0.00";
        return;
    }

    let dist = 0;
    for (let i = 0; i < newRoutePoints.length - 1; i++) {
        dist += haversine(newRoutePoints[i], newRoutePoints[i + 1]);
    }
    document.getElementById("route-distance").textContent = dist.toFixed(2);
}

function haversine(p1, p2) {
    const R = 6371;
    const toRad = (x) => (x * Math.PI) / 180;
    const dLat = toRad(p2.lat - p1.lat);
    const dLng = toRad(p2.lng - p1.lng);
    const a =
        Math.sin(dLat / 2) ** 2 +
        Math.cos(toRad(p1.lat)) * Math.cos(toRad(p2.lat)) * Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// --- Search & Filter ---

function searchRoutes() {
    const q = document.getElementById("search-input").value.trim();
    const myOnly = document.getElementById("my-routes-only").checked;
    loadRoutes(q, myOnly);
}

function filterMyRoutes() {
    const q = document.getElementById("search-input").value.trim();
    const myOnly = document.getElementById("my-routes-only").checked;
    loadRoutes(q, myOnly);
}

// --- API calls ---

async function loadRoutes(q = "", myOnly = false) {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (myOnly) params.set("my", "1");

    const res = await fetch(`/api/routes?${params}`);
    const routes = await res.json();
    const list = document.getElementById("route-list");
    list.innerHTML = "";

    routes.forEach((r) => {
        const li = document.createElement("li");
        const isOwner = currentUser && r.user_id === currentUser.id;
        li.innerHTML = `
            <span class="route-name">${r.name}</span>
            ${isOwner ? `<button class="btn-delete" onclick="event.stopPropagation(); deleteRoute(${r.id})">delete</button>` : ""}
            <div class="route-meta">${r.distance.toFixed(2)} km | ${r.points.length} points | by ${r.username || "unknown"}</div>
        `;
        li.onclick = () => showRouteDetail(r.id);
        list.appendChild(li);
    });
}

async function showRouteDetail(id) {
    const res = await fetch(`/api/routes/${id}`);
    const route = await res.json();

    if (displayedRoutePolyline) {
        map.removeLayer(displayedRoutePolyline);
    }
    displayedRouteLabels.forEach((m) => map.removeLayer(m));
    displayedRouteLabels = [];

    if (route.points.length < 2) return;

    displayedRoutePolyline = L.polyline(route.points, {
        color: "#790ddf",
        weight: 4,
    }).addTo(map);

    const labelStyle = "background:#16213e;color:#e0e0e0;padding:2px 6px;border-radius:3px;font-size:11px;white-space:nowrap;border:1px solid #0f3460;";

    const startIcon = L.divIcon({
        className: "",
        html: '<span style="' + labelStyle + '">Start</span>',
        iconAnchor: [-8, 12],
    });
    const endIcon = L.divIcon({
        className: "",
        html: '<span style="' + labelStyle + '">Finish</span>',
        iconAnchor: [-8, 12],
    });

    const first = route.points[0];
    const last = route.points[route.points.length - 1];

    displayedRouteLabels.push(
        L.marker([first.lat, first.lng], { icon: startIcon }).addTo(map),
        L.marker([last.lat, last.lng], { icon: endIcon }).addTo(map)
    );

    map.fitBounds(displayedRoutePolyline.getBounds(), { padding: [50, 100] });

    showRouteStats(route);
}

function showRouteStats(route) {
    const panel = document.getElementById("route-stats-panel");
    if (!panel) return;

    const stats = route.stats;
    panel.innerHTML = `
        <h3>${route.name}</h3>
        <p>${route.description || ""}</p>
        <div class="stats-grid">
            <div class="stat-item">
                <span class="stat-value">${stats.total_distance_km}</span>
                <span class="stat-label">km total</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${stats.total_elevation_gain_m}</span>
                <span class="stat-label">↑ gain m</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${stats.total_elevation_loss_m}</span>
                <span class="stat-label">↓ loss m</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${stats.max_altitude_m}</span>
                <span class="stat-label">max alt m</span>
            </div>
        </div>
    `;
    panel.style.display = "block";
}

async function saveRoute() {
    const name = document.getElementById("route-name").value.trim();
    const description = document.getElementById("route-desc").value.trim();

    if (!name) {
        alert("Enter a route name");
        return;
    }
    if (newRoutePoints.length < 2) {
        alert("Add at least 2 points on the map");
        return;
    }

    const res = await fetch("/api/routes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description, points: newRoutePoints }),
    });

    if (res.ok) {
        clearNewRoute();
        loadRoutes();
        loadStats();
    } else {
        const err = await res.json();
        alert(err.error || "Error saving route");
    }
}

async function deleteRoute(id) {
    if (!confirm("Delete this route?")) return;

    const res = await fetch(`/api/routes/${id}`, { method: "DELETE" });
    if (res.ok) {
        loadRoutes();
        loadStats();
        if (displayedRoutePolyline) {
            map.removeLayer(displayedRoutePolyline);
            displayedRoutePolyline = null;
        }
        displayedRouteLabels.forEach((m) => map.removeLayer(m));
        displayedRouteLabels = [];
    }
}

// --- Auth ---

let currentUser = null;

async function checkAuth() {
    const res = await fetch("/api/me");
    const user = await res.json();
    currentUser = user;
    updateAuthUI(user);
    loadRoutes(document.getElementById("search-input").value.trim(), document.getElementById("my-routes-only").checked);
}

function updateAuthUI(user) {
    const info = document.getElementById("user-info");
    const btnLogout = document.getElementById("btn-logout");
    const btnLogin = document.getElementById("btn-show-login");
    const btnRegister = document.getElementById("btn-show-register");
    const faSection = document.getElementById("2fa-section");
    const myRoutesCheckbox = document.getElementById("my-routes-only");

    if (user) {
        info.textContent = user.username;
        btnLogout.style.display = "inline";
        btnLogin.style.display = "none";
        btnRegister.style.display = "none";
        faSection.style.display = "block";
        myRoutesCheckbox.disabled = false;

        const status = document.getElementById("2fa-status");
        const setup = document.getElementById("2fa-setup");
        const disable = document.getElementById("2fa-disable");

        if (user.is_2fa_enabled) {
            status.innerHTML = '<span style="color:#4caf50">2FA: ON</span>';
            setup.style.display = "none";
            disable.style.display = "block";
        } else {
            status.innerHTML = '<span style="color:#999">2FA: OFF</span>';
            setup.style.display = "none";
            disable.style.display = "none";
        }
    } else {
        info.textContent = "";
        btnLogout.style.display = "none";
        btnLogin.style.display = "inline";
        btnRegister.style.display = "inline";
        faSection.style.display = "none";
        myRoutesCheckbox.disabled = true;
        myRoutesCheckbox.checked = false;
    }
}

function showForm(id) {
    hideForms();
    document.getElementById(id).style.display = "flex";
}

function hideForms() {
    document.getElementById("login-form").style.display = "none";
    document.getElementById("register-form").style.display = "none";
}

async function login() {
    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;
    const totpInput = document.getElementById("login-totp");
    const totpCode = totpInput.value.trim();

    const body = { username, password };
    if (totpCode) body.totp_code = totpCode;

    const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });

    const data = await res.json();

    if (res.ok && data.requires_2fa) {
        totpInput.style.display = "block";
        totpInput.focus();
        return;
    }

    if (res.ok) {
        hideForms();
        location.reload();
    } else {
        alert(data.error || "Login failed");
    }
}

async function register() {
    const username = document.getElementById("reg-username").value.trim();
    const email = document.getElementById("reg-email").value.trim();
    const password = document.getElementById("reg-password").value;

    const res = await fetch("/api/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password }),
    });

    if (res.ok) {
        hideForms();
        location.reload();
    } else {
        const err = await res.json();
        alert(err.error || "Registration failed");
    }
}

async function logout() {
    await fetch("/api/logout", { method: "POST" });
    location.reload();
}

// --- 2FA ---

async function enable2FA() {
    const res = await fetch("/api/2fa/enable", { method: "POST" });
    const data = await res.json();

    if (res.ok) {
        document.getElementById("2fa-qr").src = "data:image/png;base64," + data.qr_code;
        document.getElementById("2fa-secret").textContent = data.secret;
        document.getElementById("2fa-setup").style.display = "block";
    } else {
        alert(data.error);
    }
}

async function confirm2FA() {
    const code = document.getElementById("2fa-confirm-code").value.trim();
    if (!code) {
        alert("Enter the code from your authenticator app");
        return;
    }

    const res = await fetch("/api/2fa/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
    });

    const data = await res.json();

    if (res.ok) {
        alert("2FA enabled!");
        checkAuth();
    } else {
        alert(data.error);
    }
}

async function disable2FA() {
    const code = document.getElementById("2fa-disable-code").value.trim();
    if (!code) {
        alert("Enter the code from your authenticator app");
        return;
    }

    const res = await fetch("/api/2fa/disable", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
    });

    const data = await res.json();

    if (res.ok) {
        alert("2FA disabled!");
        document.getElementById("2fa-disable-code").value = "";
        checkAuth();
    } else {
        alert(data.error);
    }
}

function toggle2FASetup() {
    if (currentUser && currentUser.is_2fa_enabled) {
        const disable = document.getElementById("2fa-disable");
        disable.style.display = disable.style.display === "none" ? "block" : "none";
    } else {
        enable2FA();
    }
}

// --- Stats ---

async function loadStats() {
    const res = await fetch("/api/stats");
    const stats = await res.json();
    const el = document.getElementById("global-stats");
    if (el) {
        el.innerHTML = `
            <span>${stats.total_routes} routes</span> |
            <span>${stats.total_users} users</span> |
            <span>${stats.total_distance_km} km total</span>
        `;
    }
}

// --- Init ---

document.addEventListener("DOMContentLoaded", () => {
    initMap();
    loadRoutes();
    checkAuth();
    loadStats();
});
