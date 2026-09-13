from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_user, logout_user

from app import db
from app.auth import generate_secret, generate_qr_code_base64, verify_code
from app.distance import calculate_route_distance, get_route_stats
from app.elevation import enrich_points_with_elevation
from app.models import Route, User
from app.worker import worker, async_calculate_distance, async_get_stats, async_batch_process

bp = Blueprint("main", __name__)


# --- Pages ---

@bp.route("/")
def index():
    return render_template("index.html")


# --- Auth API ---

@bp.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({"error": "Username or email already exists"}), 409

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify({"message": "Registered", "user": {"id": user.id, "username": user.username}})


@bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "")
    password = data.get("password", "")
    totp_code = data.get("totp_code", "")

    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    if user.is_2fa_enabled:
        if not totp_code:
            return jsonify({"requires_2fa": True}), 200
        if not verify_code(user.totp_secret, totp_code):
            return jsonify({"error": "Invalid 2FA code"}), 401

    login_user(user)
    return jsonify({"message": "Logged in", "user": {"id": user.id, "username": user.username}})


@bp.route("/api/logout", methods=["POST"])
def logout():
    logout_user()
    return jsonify({"message": "Logged out"})


@bp.route("/api/me")
def me():
    if current_user.is_authenticated:
        return jsonify({
            "id": current_user.id,
            "username": current_user.username,
            "is_2fa_enabled": current_user.is_2fa_enabled,
        })
    return jsonify(None)


# --- 2FA API ---

@bp.route("/api/2fa/enable", methods=["POST"])
def enable_2fa():
    if not current_user.is_authenticated:
        return jsonify({"error": "Login required"}), 401

    secret = generate_secret()
    current_user.totp_secret = secret
    db.session.commit()

    qr_base64 = generate_qr_code_base64(secret, current_user.username)
    return jsonify({"secret": secret, "qr_code": qr_base64})


@bp.route("/api/2fa/confirm", methods=["POST"])
def confirm_2fa():
    if not current_user.is_authenticated:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json()
    code = data.get("code", "")

    if not current_user.totp_secret:
        return jsonify({"error": "Call /api/2fa/enable first"}), 400

    if not verify_code(current_user.totp_secret, code):
        return jsonify({"error": "Invalid code"}), 400

    current_user.is_2fa_enabled = True
    db.session.commit()
    return jsonify({"message": "2FA enabled"})


@bp.route("/api/2fa/disable", methods=["POST"])
def disable_2fa():
    if not current_user.is_authenticated:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json()
    code = data.get("code", "")

    if not current_user.is_2fa_enabled:
        return jsonify({"error": "2FA is not enabled"}), 400

    if not verify_code(current_user.totp_secret, code):
        return jsonify({"error": "Invalid code"}), 400

    current_user.is_2fa_enabled = False
    current_user.totp_secret = None
    db.session.commit()
    return jsonify({"message": "2FA disabled"})


# --- Routes CRUD ---

@bp.route("/api/routes", methods=["GET"])
def get_routes():
    q = request.args.get("q", "").strip()
    my_only = request.args.get("my", "") == "1"

    query = Route.query

    if q:
        query = query.filter(Route.name.ilike(f"%{q}%"))

    if my_only and current_user.is_authenticated:
        query = query.filter(Route.user_id == current_user.id)

    query = query.order_by(Route.created_at.desc())

    routes = query.all()
    return jsonify([r.to_dict() for r in routes])


@bp.route("/api/routes/<int:route_id>", methods=["GET"])
def get_route(route_id):
    route = db.session.get(Route, route_id)
    if not route:
        return jsonify({"error": "Not found"}), 404

    data = route.to_dict()
    data["stats"] = get_route_stats(route.get_points())
    return jsonify(data)


@bp.route("/api/routes", methods=["POST"])
def create_route():
    if not current_user.is_authenticated:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json()
    name = data.get("name", "").strip()
    points = data.get("points", [])
    description = data.get("description", "")

    if not name or len(points) < 2:
        return jsonify({"error": "Name and at least 2 points required"}), 400

    points = enrich_points_with_elevation(points)
    distance = calculate_route_distance(points)

    route = Route(
        user_id=current_user.id,
        name=name,
        description=description,
        distance=distance,
    )
    route.set_points(points)
    db.session.add(route)
    db.session.commit()
    return jsonify(route.to_dict()), 201


@bp.route("/api/routes/<int:route_id>", methods=["PUT"])
def update_route(route_id):
    if not current_user.is_authenticated:
        return jsonify({"error": "Login required"}), 401

    route = db.session.get(Route, route_id)
    if not route or route.user_id != current_user.id:
        return jsonify({"error": "Not found or not yours"}), 404

    data = request.get_json()
    if "name" in data:
        route.name = data["name"]
    if "description" in data:
        route.description = data["description"]
    if "points" in data and len(data["points"]) >= 2:
        points = enrich_points_with_elevation(data["points"])
        route.set_points(points)
        route.distance = calculate_route_distance(points)

    db.session.commit()
    return jsonify(route.to_dict())


@bp.route("/api/routes/<int:route_id>", methods=["DELETE"])
def delete_route(route_id):
    if not current_user.is_authenticated:
        return jsonify({"error": "Login required"}), 401

    route = db.session.get(Route, route_id)
    if not route or route.user_id != current_user.id:
        return jsonify({"error": "Not found or not yours"}), 404

    db.session.delete(route)
    db.session.commit()
    return jsonify({"message": "Deleted"})


# --- Statistics ---

@bp.route("/api/stats")
def global_stats():
    total_routes = Route.query.count()
    total_users = User.query.count()
    total_distance = db.session.query(db.func.sum(Route.distance)).scalar() or 0

    return jsonify({
        "total_routes": total_routes,
        "total_users": total_users,
        "total_distance_km": round(total_distance, 2),
    })


# --- Async Tasks ---

@bp.route("/api/tasks/calculate", methods=["POST"])
def start_calculation():
    """Start async distance calculation."""
    data = request.get_json()
    points = data.get("points", [])

    if len(points) < 2:
        return jsonify({"error": "At least 2 points required"}), 400

    task_id = f"calc_{id(points)}"
    worker.submit(task_id, async_calculate_distance, points)
    return jsonify({"task_id": task_id, "status": "pending"}), 202


@bp.route("/api/tasks/stats", methods=["POST"])
def start_stats():
    """Start async stats calculation."""
    data = request.get_json()
    points = data.get("points", [])

    if len(points) < 2:
        return jsonify({"error": "At least 2 points required"}), 400

    task_id = f"stats_{id(points)}"
    worker.submit(task_id, async_get_stats, points)
    return jsonify({"task_id": task_id, "status": "pending"}), 202


@bp.route("/api/tasks/batch", methods=["POST"])
def start_batch():
    """Start batch processing of multiple routes."""
    data = request.get_json()
    routes_data = data.get("routes", [])

    if not routes_data:
        return jsonify({"error": "No routes provided"}), 400

    task_id = f"batch_{id(routes_data)}"
    worker.submit(task_id, async_batch_process, routes_data)
    return jsonify({"task_id": task_id, "status": "pending"}), 202


@bp.route("/api/tasks/<task_id>")
def get_task(task_id):
    """Check task status and get result."""
    result = worker.get_result(task_id)
    return jsonify(result)
