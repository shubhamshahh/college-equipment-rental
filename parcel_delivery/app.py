import os
import math
import random
import uuid
from datetime import datetime
from functools import wraps

import qrcode
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

app = Flask(__name__)
app.secret_key = "change-this-secret-key-in-production"

QR_FOLDER = os.path.join("static", "uploads", "qrcodes")
os.makedirs(QR_FOLDER, exist_ok=True)

# ---------------------------------------------------------------------------
# DATABASE CONFIG  -> change these to match your MySQL setup
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Shubham@#7633",
    "database": "equipment_rental_db",
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


# ---------------------------------------------------------------------------
# MAPS / PRICING CONFIG
# ---------------------------------------------------------------------------
# Get a free-tier API key from https://console.cloud.google.com/
# Enable: Maps JavaScript API + Places API
GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY"

# Default map center (used until institution is selected / geolocation runs)
DEFAULT_LAT = 22.4707
DEFAULT_LNG = 70.0577

# Porter-style pricing
BASE_FEE = 15.0          # flat pickup fee
RATE_PER_KM = 8.0        # per km after that


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance in km between two lat/lng points."""
    if None in (lat1, lng1, lat2, lng2):
        return 0.0
    try:
        lat1, lng1, lat2, lng2 = map(float, (lat1, lng1, lat2, lng2))
    except (TypeError, ValueError):
        return 0.0

    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


def calculate_fare(distance_km):
    distance_fee = round(distance_km * RATE_PER_KM, 2)
    total = round(BASE_FEE + distance_fee, 2)
    return BASE_FEE, distance_fee, total


def generate_otp():
    return str(random.randint(100000, 999999))


@app.context_processor
def inject_map_config():
    return {
        "GOOGLE_MAPS_API_KEY": GOOGLE_MAPS_API_KEY,
        "DEFAULT_LAT": DEFAULT_LAT,
        "DEFAULT_LNG": DEFAULT_LNG,
        "BASE_FEE": BASE_FEE,
        "RATE_PER_KM": RATE_PER_KM,
    }


# ---------------------------------------------------------------------------
# AUTH HELPERS
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                flash("You don't have access to that page.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated
    return decorator


STATUS_FLOW = [
    "pending", "accepted", "arrived_pickup", "picked_up",
    "in_transit", "arrived_drop", "delivered",
]


def log_status(cursor, order_id, status, note=""):
    cursor.execute(
        "INSERT INTO order_status_log (order_id, status, note) VALUES (%s, %s, %s)",
        (order_id, status, note),
    )


# ---------------------------------------------------------------------------
# HOME
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("home.html")


@app.route("/dashboard")
@login_required
def dashboard():
    if session["role"] == "sender":
        return redirect(url_for("sender_orders"))
    elif session["role"] == "rider":
        return redirect(url_for("rider_dashboard"))
    elif session["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# AUTH ROUTES
# ---------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role", "sender")
        vehicle_type = request.form.get("vehicle_type") or None
        vehicle_number = request.form.get("vehicle_number", "").strip() or None

        if role not in ("sender", "rider"):
            role = "sender"

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO users (name, email, password, phone, role, vehicle_type, vehicle_number)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (name, email, hashed_pw, phone, role, vehicle_type, vehicle_number),
            )
            conn.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except mysql.connector.IntegrityError:
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))
        finally:
            cursor.close()
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# SENDER ROUTES
# ---------------------------------------------------------------------------
@app.route("/send-parcel", methods=["GET", "POST"])
@role_required("sender")
def send_parcel():
    if request.method == "POST":
        parcel_title = request.form["parcel_title"].strip()
        parcel_description = request.form.get("parcel_description", "").strip()
        parcel_size = request.form.get("parcel_size", "small")
        receiver_name = request.form["receiver_name"].strip()
        receiver_phone = request.form["receiver_phone"].strip()

        pickup_address = request.form["pickup_address"].strip()
        pickup_lat = request.form["pickup_lat"]
        pickup_lng = request.form["pickup_lng"]

        drop_address = request.form["drop_address"].strip()
        drop_lat = request.form["drop_lat"]
        drop_lng = request.form["drop_lng"]

        notes = request.form.get("notes", "").strip()

        if not all([pickup_lat, pickup_lng, drop_lat, drop_lng]):
            flash("Please select both pickup and drop locations on the map.", "warning")
            return redirect(url_for("send_parcel"))

        distance_km = haversine_km(pickup_lat, pickup_lng, drop_lat, drop_lng)
        base_fee, distance_fee, total_fare = calculate_fare(distance_km)

        order_ref = f"PCL-{uuid.uuid4().hex[:10].upper()}"
        pickup_otp = generate_otp()
        drop_otp = generate_otp()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO orders
                (sender_id, parcel_title, parcel_description, parcel_size,
                 receiver_name, receiver_phone,
                 pickup_address, pickup_lat, pickup_lng,
                 drop_address, drop_lat, drop_lng,
                 distance_km, base_fee, rate_per_km, distance_fee, total_fare,
                 order_ref, pickup_otp, drop_otp, status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)
            """,
            (
                session["user_id"], parcel_title, parcel_description, parcel_size,
                receiver_name, receiver_phone,
                pickup_address, pickup_lat, pickup_lng,
                drop_address, drop_lat, drop_lng,
                distance_km, base_fee, RATE_PER_KM, distance_fee, total_fare,
                order_ref, pickup_otp, drop_otp, notes,
            ),
        )
        conn.commit()
        order_id = cursor.lastrowid

        log_status(cursor, order_id, "pending", "Order placed by sender")
        conn.commit()

        # Generate QR encoding the order reference (for rider verification)
        qr_data = f"ORDER_ID:{order_id}|REF:{order_ref}"
        qr_filename = f"qr_{order_id}.png"
        qr_path = os.path.join(QR_FOLDER, qr_filename)
        img = qrcode.make(qr_data)
        img.save(qr_path)

        cursor.execute("UPDATE orders SET qr_code=%s WHERE id=%s", (qr_filename, order_id))
        conn.commit()
        cursor.close()
        conn.close()

        flash("Parcel order placed! Looking for a rider...", "success")
        return redirect(url_for("order_detail", order_id=order_id))

    return render_template("send_parcel.html")


@app.route("/my-orders")
@role_required("sender")
def sender_orders():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT o.*, r.name AS rider_name, r.phone AS rider_phone
        FROM orders o
        LEFT JOIN users r ON o.rider_id = r.id
        WHERE o.sender_id = %s
        ORDER BY o.created_at DESC
        """,
        (session["user_id"],),
    )
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("sender_orders.html", orders=orders)


# ---------------------------------------------------------------------------
# RIDER ROUTES
# ---------------------------------------------------------------------------
@app.route("/rider/dashboard")
@role_required("rider")
def rider_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Orders this rider currently has in progress
    cursor.execute(
        """
        SELECT o.*, s.name AS sender_name, s.phone AS sender_phone
        FROM orders o
        JOIN users s ON o.sender_id = s.id
        WHERE o.rider_id = %s AND o.status NOT IN ('delivered','cancelled')
        ORDER BY o.created_at DESC
        """,
        (session["user_id"],),
    )
    active_orders = cursor.fetchall()

    # Available orders waiting for a rider
    cursor.execute(
        """
        SELECT o.*, s.name AS sender_name
        FROM orders o
        JOIN users s ON o.sender_id = s.id
        WHERE o.status = 'pending' AND o.rider_id IS NULL
        ORDER BY o.created_at ASC
        """
    )
    available_orders = cursor.fetchall()

    cursor.execute(
        "SELECT is_available FROM users WHERE id = %s", (session["user_id"],)
    )
    rider_status = cursor.fetchone()

    cursor.close()
    conn.close()
    return render_template(
        "rider_dashboard.html",
        active_orders=active_orders,
        available_orders=available_orders,
        is_available=rider_status["is_available"] if rider_status else 1,
    )


@app.route("/rider/toggle-availability", methods=["POST"])
@role_required("rider")
def toggle_availability():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT is_available FROM users WHERE id = %s", (session["user_id"],))
    row = cursor.fetchone()
    new_status = 0 if row["is_available"] else 1
    cursor.execute("UPDATE users SET is_available=%s WHERE id=%s", (new_status, session["user_id"]))
    conn.commit()
    cursor.close()
    conn.close()
    flash(f"You are now {'Online' if new_status else 'Offline'}.", "info")
    return redirect(url_for("rider_dashboard"))


@app.route("/rider/accept/<int:order_id>", methods=["POST"])
@role_required("rider")
def accept_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    order = cursor.fetchone()

    if not order or order["status"] != "pending" or order["rider_id"] is not None:
        flash("This order is no longer available.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("rider_dashboard"))

    cursor.execute(
        """
        UPDATE orders
        SET rider_id=%s, status='accepted', accepted_at=%s
        WHERE id=%s
        """,
        (session["user_id"], datetime.now(), order_id),
    )
    log_status(cursor, order_id, "accepted", f"Accepted by rider #{session['user_id']}")
    conn.commit()
    cursor.close()
    conn.close()

    flash("Order accepted! Head to the pickup location.", "success")
    return redirect(url_for("order_detail", order_id=order_id))


# ---------------------------------------------------------------------------
# ORDER DETAIL + STATUS UPDATES (shared by sender & rider)
# ---------------------------------------------------------------------------
@app.route("/order/<int:order_id>")
@login_required
def order_detail(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT o.*, s.name AS sender_name, s.phone AS sender_phone,
               r.name AS rider_name, r.phone AS rider_phone,
               r.vehicle_type, r.vehicle_number
        FROM orders o
        JOIN users s ON o.sender_id = s.id
        LEFT JOIN users r ON o.rider_id = r.id
        WHERE o.id = %s
        """,
        (order_id,),
    )
    order = cursor.fetchone()

    if not order:
        cursor.close()
        conn.close()
        flash("Order not found.", "danger")
        return redirect(url_for("dashboard"))

    allowed_ids = {order["sender_id"], order["rider_id"]}
    if session["user_id"] not in allowed_ids and session["role"] != "admin":
        cursor.close()
        conn.close()
        flash("Not authorized to view this order.", "danger")
        return redirect(url_for("dashboard"))

    cursor.execute(
        "SELECT * FROM order_status_log WHERE order_id = %s ORDER BY created_at ASC",
        (order_id,),
    )
    status_log = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template(
        "order_detail.html",
        order=order,
        status_log=status_log,
        status_flow=STATUS_FLOW,
    )


@app.route("/order/<int:order_id>/advance", methods=["POST"])
@role_required("rider")
def advance_order(order_id):
    """Rider moves the order to the next status in the flow
    (arrived_pickup -> picked_up requires pickup OTP,
     arrived_drop -> delivered requires drop OTP)."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    order = cursor.fetchone()

    if not order or order["rider_id"] != session["user_id"]:
        flash("Not authorized.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for("rider_dashboard"))

    current_status = order["status"]
    next_action = request.form.get("next_status")
    entered_otp = request.form.get("otp", "").strip()

    try:
        current_index = STATUS_FLOW.index(current_status)
    except ValueError:
        current_index = -1

    if next_action not in STATUS_FLOW:
        flash("Invalid status transition.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for("order_detail", order_id=order_id))

    next_index = STATUS_FLOW.index(next_action)
    if next_index != current_index + 1:
        flash("Status must move forward one step at a time.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("order_detail", order_id=order_id))

    # OTP checks at the critical handoff points
    if next_action == "picked_up":
        if entered_otp != order["pickup_otp"]:
            flash("Incorrect pickup OTP. Ask the sender for the correct code.", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for("order_detail", order_id=order_id))
        cursor.execute(
            "UPDATE orders SET status=%s, picked_up_at=%s WHERE id=%s",
            (next_action, datetime.now(), order_id),
        )
    elif next_action == "delivered":
        if entered_otp != order["drop_otp"]:
            flash("Incorrect drop OTP. Ask the receiver for the correct code.", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for("order_detail", order_id=order_id))
        cursor.execute(
            "UPDATE orders SET status=%s, delivered_at=%s WHERE id=%s",
            (next_action, datetime.now(), order_id),
        )
    else:
        cursor.execute("UPDATE orders SET status=%s WHERE id=%s", (next_action, order_id))

    log_status(cursor, order_id, next_action, "Updated by rider")
    conn.commit()
    cursor.close()
    conn.close()

    flash(f"Status updated to: {next_action.replace('_', ' ').title()}", "success")
    return redirect(url_for("order_detail", order_id=order_id))


@app.route("/order/<int:order_id>/cancel", methods=["POST"])
@login_required
def cancel_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    order = cursor.fetchone()

    if not order:
        cursor.close()
        conn.close()
        flash("Order not found.", "danger")
        return redirect(url_for("dashboard"))

    if session["user_id"] != order["sender_id"] and session["role"] != "admin":
        flash("Only the sender can cancel this order.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for("order_detail", order_id=order_id))

    if order["status"] in ("delivered", "cancelled"):
        flash("This order can no longer be cancelled.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("order_detail", order_id=order_id))

    cursor.execute("UPDATE orders SET status='cancelled' WHERE id=%s", (order_id,))
    log_status(cursor, order_id, "cancelled", "Cancelled by sender")
    conn.commit()
    cursor.close()
    conn.close()

    flash("Order cancelled.", "info")
    return redirect(url_for("order_detail", order_id=order_id))


# ---------------------------------------------------------------------------
# REVIEWS (sender rates rider after delivery)
# ---------------------------------------------------------------------------
@app.route("/order/<int:order_id>/review", methods=["POST"])
@role_required("sender")
def add_review(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    order = cursor.fetchone()

    if not order or order["sender_id"] != session["user_id"] or order["status"] != "delivered":
        flash("You can only review completed deliveries you sent.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("order_detail", order_id=order_id))

    rating = int(request.form["rating"])
    comment = request.form.get("comment", "").strip()

    cursor.execute(
        """
        INSERT INTO reviews (order_id, rider_id, sender_id, rating, comment)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (order_id, order["rider_id"], session["user_id"], rating, comment),
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("Thanks for your feedback!", "success")
    return redirect(url_for("order_detail", order_id=order_id))


# ---------------------------------------------------------------------------
# ADMIN DASHBOARD
# ---------------------------------------------------------------------------
@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT o.*, s.name AS sender_name, r.name AS rider_name
        FROM orders o
        JOIN users s ON o.sender_id = s.id
        LEFT JOIN users r ON o.rider_id = r.id
        ORDER BY o.created_at DESC
        LIMIT 100
        """
    )
    orders = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) AS total FROM orders")
    total_orders = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM orders WHERE status='delivered'")
    delivered_orders = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role='rider'")
    total_riders = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role='sender'")
    total_senders = cursor.fetchone()["total"]

    cursor.execute("SELECT COALESCE(SUM(total_fare),0) AS revenue FROM orders WHERE status='delivered'")
    revenue = cursor.fetchone()["revenue"]

    cursor.close()
    conn.close()
    return render_template(
        "admin_dashboard.html",
        orders=orders,
        total_orders=total_orders,
        delivered_orders=delivered_orders,
        total_riders=total_riders,
        total_senders=total_senders,
        revenue=revenue,
    )


# ---------------------------------------------------------------------------
# API: fare estimate (optional live AJAX endpoint)
# ---------------------------------------------------------------------------
@app.route("/api/estimate-fare")
def estimate_fare():
    try:
        plat, plng = float(request.args["pickup_lat"]), float(request.args["pickup_lng"])
        dlat, dlng = float(request.args["drop_lat"]), float(request.args["drop_lng"])
    except (KeyError, ValueError):
        return jsonify({"error": "invalid coordinates"}), 400

    distance = haversine_km(plat, plng, dlat, dlng)
    base, dist_fee, total = calculate_fare(distance)
    return jsonify({
        "distance_km": distance,
        "base_fee": base,
        "distance_fee": dist_fee,
        "total_fare": total,
    })


# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
