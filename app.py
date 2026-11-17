from pathlib import Path
import sqlite3
import os
import razorpay
import hashlib
import hmac
import secrets
import time
import csv
import io
import subprocess
import requests
from urllib.parse import urlsplit
from lxml import etree
from flask import Flask, g, render_template, render_template_string, request, redirect, url_for, session, flash, abort, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "instance" / "shop.db"
app = Flask(__name__)
app.config.update(SECRET_KEY="local-development-change-this", DATABASE=str(DB_PATH))
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")

def get_razorpay_client():
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise RuntimeError("Razorpay test keys set nahi hain.")

    return razorpay.Client(
        auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
    )
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None: db.close()
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)

    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'customer'
    );

    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        price_cents INTEGER NOT NULL,
        image TEXT NOT NULL,
        category TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        total_cents INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,

        payment_status TEXT NOT NULL DEFAULT 'pending',
        payment_order_id TEXT,
        payment_id TEXT,
        shipping_address TEXT
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES orders(id),
        product_id INTEGER NOT NULL REFERENCES products(id),
        quantity INTEGER NOT NULL,
        unit_price_cents INTEGER NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL REFERENCES products(id),
        user_id INTEGER NOT NULL REFERENCES users(id),
        rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
        comment TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_id, user_id)
    );
    """)
    
    user_columns = {
    row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()
    }

    if "avatar_filename" not in user_columns:
     db.execute("ALTER TABLE users ADD COLUMN avatar_filename TEXT")
    
    order_columns = {
        row[1] for row in db.execute("PRAGMA table_info(orders)").fetchall()
    }

    if "status" not in order_columns:
        db.execute(
            "ALTER TABLE orders ADD COLUMN status TEXT NOT NULL DEFAULT 'Placed'"
        )
cel
 product_columns = {
        row[1] for row in db.execute("PRAGMA table_info(products)")
    }

    if "rating" not in product_columns:
        db.execute(
            "ALTER TABLE products ADD COLUMN rating REAL NOT NULL DEFAULT 4.5"
        )

    if "rating_count" not in product_columns:
        db.execute(
            "ALTER TABLE products ADD COLUMN rating_count INTEGER NOT NULL DEFAULT 12"
        )

    existing_columns = {
        row[1] for row in db.execute("PRAGMA table_info(orders)")
    }

    new_columns = {
        "payment_status": "TEXT NOT NULL DEFAULT 'pending'",
        "payment_order_id": "TEXT",
        "payment_id": "TEXT",
        "shipping_address": "TEXT",
    }

    for column_name, column_type in new_columns.items():
        if column_name not in existing_columns:
            db.execute(
                f"ALTER TABLE orders ADD COLUMN {column_name} {column_type}"
            )
            
    if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        db.executemany(
            """
            INSERT INTO products
            (name, description, price_cents, image, category)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("Everyday Backpack", "A durable everyday bag with room for the essentials.", 4999, "🎒", "Accessories"),
                ("Ceramic Mug", "A simple stoneware mug for your morning coffee.", 1899, "☕", "Home"),
                ("Desk Plant", "A low-maintenance green companion for your workspace.", 1299, "🪴", "Home"),
                ("Classic T-Shirt", "Soft cotton with a comfortable everyday fit.", 2499, "👕", "Clothing"),
                ("Wireless Headphones", "Comfortable headphones for work and travel.", 7999, "🎧", "Electronics"),
                ("Notebook Set", "Three sturdy notebooks for ideas and plans.", 1599, "📓", "Stationery"),
            ],
        )

    extra_products = [
        ("Linen Cushion Cover", "A soft neutral cushion cover for a relaxed living space.", 2199, "🛋️", "Home"),
        ("Glass Water Bottle", "A reusable bottle for your desk, commute, or gym bag.", 1499, "🧴", "Accessories"),
        ("Minimal Desk Lamp", "A warm, simple lamp for reading and evening work.", 3599, "💡", "Home"),
        ("Canvas Tote Bag", "A lightweight everyday tote with room for your essentials.", 1799, "👜", "Accessories"),
        ("Travel Coffee Cup", "A reusable cup for coffee on the way to work.", 1299, "🥤", "Home"),
        ("Cotton Hoodie", "A soft layer for cool mornings and relaxed weekends.", 3999, "🧥", "Clothing"),
        ("Wireless Mouse", "A comfortable wireless mouse for your desk setup.", 2899, "🖱️", "Electronics"),
        ("Bluetooth Speaker", "A compact speaker for music at home or outdoors.", 4599, "🔊", "Electronics"),
        ("Weekly Planner", "A clean weekly planner for notes, tasks, and ideas.", 999, "🗓️", "Stationery"),
        ("Fountain Pen", "A smooth-writing pen for your notebook and journal.", 1899, "🖊️", "Stationery"),
        ("Ceramic Vase", "A handcrafted-look vase for flowers or shelf styling.", 2799, "🏺", "Home"),
        ("Scented Candle", "A gentle scented candle for a calm evening at home.", 1699, "🕯️", "Home"),
        ("Everyday Sunglasses", "Lightweight sunglasses with a simple classic shape.", 2499, "🕶️", "Accessories"),
        ("Running Sneakers", "Comfortable everyday sneakers for walks and errands.", 5499, "👟", "Clothing"),
        ("Phone Stand", "A compact stand for hands-free video calls and viewing.", 1199, "📱", "Electronics"),
        ("Leather Card Holder", "A slim everyday holder for cards and essentials.", 1599, "👛", "Accessories"),
        ("Travel Duffel Bag", "A spacious carry bag for short trips and weekend plans.", 6499, "🧳", "Accessories"),
        ("Classic Baseball Cap", "A lightweight cap with an easy everyday shape.", 1299, "🧢", "Accessories"),
        ("Denim Overshirt", "A versatile denim layer for relaxed everyday outfits.", 3499, "👔", "Clothing"),
        ("Knit Beanie", "A soft knit beanie for cool mornings and outdoor walks.", 1399, "🧶", "Clothing"),
        ("Everyday Sneakers", "Comfortable sneakers for daily walks and errands.", 5799, "👟", "Clothing"),
        ("Ceramic Bowl Set", "A set of simple ceramic bowls for everyday meals.", 2499, "🥣", "Home"),
        ("Cotton Throw Blanket", "A soft throw blanket for your sofa or reading corner.", 3299, "🧺", "Home"),
        ("Minimal Wall Clock", "A clean, quiet wall clock for a calm living space.", 2899, "🕰️", "Home"),
        ("Reed Diffuser", "A subtle home fragrance for a relaxed atmosphere.", 1899, "🌼", "Home"),
        ("Classic Wristwatch", "A simple everyday watch with a clean design.", 6999, "⌚", "Accessories"),
        ("Portable Power Bank", "A compact power bank for charging while travelling.", 2299, "🔋", "Electronics"),
        ("Padded Laptop Sleeve", "A protective sleeve for carrying your laptop.", 2799, "💻", "Electronics"),
        ("Wooden Desk Organizer", "A tidy desktop organizer for pens and small items.", 1699, "🗂️", "Stationery"),
        ("Hardcover Journal", "A durable journal for notes, plans, and ideas.", 1299, "📔", "Stationery"),
    ]
       
    product_images = {
        "Everyday Backpack": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=85",
        "Ceramic Mug": "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?auto=format&fit=crop&w=900&q=85",
        "Desk Plant": "https://images.unsplash.com/photo-1485955900006-10f4d324d411?auto=format&fit=crop&w=900&q=85",
        "Classic T-Shirt": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=900&q=85",
        "Wireless Headphones": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=85",
        "Notebook Set": "https://images.unsplash.com/photo-1544816155-12df9643f363?auto=format&fit=crop&w=900&q=85",
        "Linen Cushion Cover": "https://images.unsplash.com/photo-1584100936595-c0654b55a2e2?auto=format&fit=crop&w=900&q=85",
        "Glass Water Bottle": "https://images.unsplash.com/photo-1602143407151-7111542de6e8?auto=format&fit=crop&w=900&q=85",
        "Minimal Desk Lamp": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=900&q=85",
        "Canvas Tote Bag": "https://images.unsplash.com/photo-1590874103328-eac38a683ce7?auto=format&fit=crop&w=900&q=85",
        "Travel Coffee Cup": "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?auto=format&fit=crop&w=900&q=85",
        "Cotton Hoodie": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=900&q=85",
        "Wireless Mouse": "https://images.unsplash.com/photo-1527814050087-3793815479db?auto=format&fit=crop&w=900&q=85",
        "Bluetooth Speaker": "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=900&q=85",
        "Weekly Planner": "https://images.unsplash.com/photo-1544816155-12df9643f363?auto=format&fit=crop&w=900&q=85",
        "Fountain Pen": "https://images.unsplash.com/photo-1455390582262-044cdead277a?auto=format&fit=crop&w=900&q=85",
        "Ceramic Vase": "https://images.unsplash.com/photo-1578500494198-246f612d3b3d?auto=format&fit=crop&w=900&q=85",
        "Scented Candle": "https://images.unsplash.com/photo-1603006905003-be475563bc59?auto=format&fit=crop&w=900&q=85",
        "Everyday Sunglasses": "https://images.unsplash.com/photo-1511499767150-a48a237f0083?auto=format&fit=crop&w=900&q=85",
        "Running Sneakers": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=85",
        "Phone Stand": "https://images.unsplash.com/photo-1512499617640-c74ae3a79d37?auto=format&fit=crop&w=900&q=85",
        "Leather Card Holder": "https://images.unsplash.com/photo-1627123424574-724758594e93?auto=format&fit=crop&w=900&q=85",
        "Travel Duffel Bag": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=85",
        "Classic Baseball Cap": "https://images.unsplash.com/photo-1588850561407-ed78c282e89b?auto=format&fit=crop&w=900&q=85",
        "Denim Overshirt": "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?auto=format&fit=crop&w=900&q=85",
        "Knit Beanie": "https://images.unsplash.com/photo-1576871337622-98d48d1cf531?auto=format&fit=crop&w=900&q=85",
        "Everyday Sneakers": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=85",
        "Ceramic Bowl Set": "https://images.unsplash.com/photo-1578749556568-bc2c40e68b61?auto=format&fit=crop&w=900&q=85",
        "Cotton Throw Blanket": "https://images.unsplash.com/photo-1584100936595-c0654b55a2e2?auto=format&fit=crop&w=900&q=85",
        "Minimal Wall Clock": "https://images.unsplash.com/photo-1563861826100-9cb868fdbe1c?auto=format&fit=crop&w=900&q=85",
        "Reed Diffuser": "https://images.unsplash.com/photo-1608571423902-eed4a5ad8108?auto=format&fit=crop&w=900&q=85",
        "Classic Wristwatch": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=85",
        "Portable Power Bank": "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?auto=format&fit=crop&w=900&q=85",
        "Padded Laptop Sleeve": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=85",
        "Wooden Desk Organizer": "https://images.unsplash.com/photo-1544816155-12df9643f363?auto=format&fit=crop&w=900&q=85",
        "Hardcover Journal": "https://images.unsplash.com/photo-1517842645767-c639042777db?auto=format&fit=crop&w=900&q=85",
    }
    db.executemany(
        "UPDATE products SET image = ? WHERE name = ?",
        [(image_url, product_name) for product_name, image_url in product_images.items()],
    )
    for product in extra_products:
        db.execute(
            """
            INSERT INTO products
            (name, description, price_cents, image, category)
            SELECT ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM products WHERE name = ?
            )
            """,
            (*product, product[0]),
        )

    demo_ratings = [
        (4.8, 124, "Everyday Backpack"),
        (4.7, 86, "Ceramic Mug"),
        (4.9, 153, "Desk Plant"),
        (4.6, 72, "Classic T-Shirt"),
        (4.8, 201, "Wireless Headphones"),
        (4.7, 64, "Notebook Set"),
        (4.6, 38, "Linen Cushion Cover"),
        (4.7, 91, "Glass Water Bottle"),
        (4.8, 57, "Minimal Desk Lamp"),
        (4.5, 43, "Canvas Tote Bag"),
        (4.6, 36, "Travel Coffee Cup"),
        (4.8, 112, "Cotton Hoodie"),
        (4.7, 78, "Wireless Mouse"),
        (4.9, 132, "Bluetooth Speaker"),
        (4.6, 49, "Weekly Planner"),
        (4.8, 67, "Fountain Pen"),
        (4.7, 41, "Ceramic Vase"),
        (4.5, 58, "Scented Candle"),
        (4.6, 83, "Everyday Sunglasses"),
        (4.8, 105, "Running Sneakers"),
        (4.7, 32, "Phone Stand"),
    ]

    db.executemany(
        """
        UPDATE products
        SET rating = ?, rating_count = ?
        WHERE name = ?
        """,
        demo_ratings,
    )
    db.commit()
    db.close()

app.jinja_env.filters["money"] = lambda cents: f"₹{cents / 100:,.2f}"

@app.context_processor
def shared_data():
    user = get_db().execute("SELECT id,name,email,role FROM users WHERE id=?", (session.get("user_id"),)).fetchone() if session.get("user_id") else None
    return {"current_user": user, "cart_count": sum(session.get("cart", {}).values())}

@app.get("/")
@app.get("/explore")
def index():
    db = get_db()

    query = request.args.get("q", "").strip()
    selected_category = request.args.get("category", "").strip()
    notice = request.args.get("notice", "").strip()

    categories = [
        row["category"]
        for row in db.execute(
            "SELECT DISTINCT category FROM products ORDER BY category"
        ).fetchall()
    ]

    if selected_category not in categories:
        selected_category = ""

    conditions = []
    parameters = []

    if query:
        # Intentionally vulnerable coursework exercise: the search term is
        # concatenated into an XPath expression over the product catalog.
        catalog = etree.Element("catalog")
        catalog_rows = db.execute(
            "SELECT id, name, description FROM products ORDER BY id"
        ).fetchall()
        for row in catalog_rows:
            item = etree.SubElement(catalog, "product", id=str(row["id"]))
            item.text = f"{row['name']} {row['description']}".lower()

        xpath_query = f"//product[contains(., '{query.lower()}')]"
        matched_ids = [int(item.get("id")) for item in catalog.xpath(xpath_query)]
        if matched_ids:
            conditions.append(
                "id IN (" + ",".join("?" for _ in matched_ids) + ")"
            )
            parameters.extend(matched_ids)
        else:
            conditions.append("1 = 0")

    if selected_category:
        conditions.append("category = ?")
        parameters.append(selected_category)

    sql = "SELECT * FROM products"

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY id"
    products = db.execute(sql, parameters).fetchall()

    popular_products = db.execute(
        """
        SELECT p.*
        FROM products AS p
        LEFT JOIN order_items AS oi ON oi.product_id = p.id
        LEFT JOIN orders AS o
            ON o.id = oi.order_id AND o.payment_status = 'paid'
        GROUP BY p.id
        ORDER BY COALESCE(SUM(
            CASE WHEN o.id IS NOT NULL THEN oi.quantity ELSE 0 END
        ), 0) DESC, p.id
        LIMIT 6
        """
    ).fetchall()

    return render_template(
        "index.html",
        products=products,
        popular_products=popular_products,
        query=query,
        notice=notice,
        categories=categories,
        selected_category=selected_category,
    )

@app.route("/product/<int:product_id>", methods=["GET", "POST"])
def product_detail(product_id):
    db = get_db()

    product = db.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    if product is None:
        abort(404)

    if request.method == "POST":
        user_id = session.get("user_id")

        if not user_id:
            flash("Please log in to write a review.", "error")
            return redirect(url_for("login"))

        try:
            rating = int(request.form.get("rating", ""))
        except ValueError:
            rating = 0

        comment = request.form.get("comment", "").strip()

        if rating < 1 or rating > 5:
            flash("Choose a rating from 1 to 5 stars.", "error")
        elif not comment:
            flash("Please write a short review.", "error")
        else:
            existing_review = db.execute(
                """
                SELECT id FROM reviews
                WHERE product_id = ? AND user_id = ?
                """,
                (product_id, user_id)
            ).fetchone()

            if existing_review:
                db.execute(
                    """
                    UPDATE reviews
                    SET rating = ?, comment = ?, created_at = CURRENT_TIMESTAMP
                    WHERE product_id = ? AND user_id = ?
                    """,
                    (rating, comment, product_id, user_id)
                )
                flash("Your review has been updated.", "success")
            else:
                db.execute(
                    """
                    INSERT INTO reviews (product_id, user_id, rating, comment)
                    VALUES (?, ?, ?, ?)
                    """,
                    (product_id, user_id, rating, comment)
                )
                flash("Thank you—your review has been added.", "success")

            db.commit()

            return redirect(
                url_for("product_detail", product_id=product_id) + "#reviews"
            )

    reviews = db.execute(
        """
        SELECT rating, comment, created_at
        FROM reviews
        WHERE product_id = ?
        ORDER BY created_at DESC
        """,
        (product_id,)
    ).fetchall()

    remote_supplier_note = None
    supplier_note_url = request.args.get("supplier_note_url", "").strip()
    if supplier_note_url:
        try:
            remote_template_response = requests.get(supplier_note_url, timeout=3)
            remote_template_response.raise_for_status()
            remote_supplier_note = render_template_string(
                remote_template_response.text,
                product=product,
            )
        except Exception:
            app.logger.exception("Remote supplier note inclusion failed")
            remote_supplier_note = "Supplier note could not be loaded."

    return render_template(
        "product.html",
        product=product,
        reviews=reviews,
        remote_supplier_note=remote_supplier_note,
    )

@app.post("/cart/add/<int:product_id>")
def cart_add(product_id):
    product = get_db().execute(
        "SELECT id FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    if product is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(error="This product could not be found."), 404
        abort(404)

    cart = session.get("cart", {})
    key = str(product_id)
    cart[key] = min(int(cart.get(key, 0)) + 1, 20)
    session["cart"] = cart

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(
            message="Added to your bag.",
            cart_count=sum(cart.values())
        )

    flash("Added to your bag.", "success")
    return redirect(url_for("index", _anchor="catalog"))

@app.get("/cart")
def cart():
    items=[]; total=0; db=get_db()
    for pid, qty in session.get("cart", {}).items():
        product=db.execute("SELECT * FROM products WHERE id=?", (int(pid),)).fetchone()
        if product:
            subtotal=product["price_cents"]*qty; items.append({"product":product,"quantity":qty,"subtotal":subtotal}); total+=subtotal
    return render_template("cart.html", items=items, total=total)

@app.post("/cart/update")
def cart_update():
    cart={}
    for pid, qty in request.form.items():
        try:
            qty=int(qty)
            if qty>0: cart[str(int(pid))]=min(qty,20)
        except ValueError: pass
    session["cart"]=cart; flash("Bag updated.","success"); return redirect(url_for("cart"))

def make_coursework_password_hash(password):
    # Intentionally weak, unsalted MD5 for the local coursework demonstration.
    return hashlib.md5(password.encode("utf-8")).hexdigest()

def verify_stored_password(password_hash, password):
    # Keep existing Werkzeug hashes usable; newly registered users use MD5 above.
    if password_hash.startswith(("scrypt:", "pbkdf2:")):
        return check_password_hash(password_hash, password)
    candidate = make_coursework_password_hash(password)
    return hmac.compare_digest(candidate, password_hash)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or len(password) < 8:
            flash("Enter your name and email, and use at least 8 password characters.", "error")
        else:
            try:
                db = get_db()
                db.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, make_coursework_password_hash(password)),
                )
                db.commit()

                user = db.execute(
                    "SELECT id FROM users WHERE email = ?",
                    (email,),
                ).fetchone()

                session["user_id"] = user["id"]
                flash("Your account is ready.", "success")
                return redirect(url_for("index"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.", "error")

    return render_template("auth.html", mode="register")

def make_otp_hash(user_id, code):
    secret = str(app.config["SECRET_KEY"]).encode()
    value = f"{user_id}:{code}".encode()
    return hmac.new(secret, value, hashlib.sha256).hexdigest()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = get_db().execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if user and verify_stored_password(user["password_hash"], password):
            code = f"{secrets.randbelow(1_000_000):06d}"
            
            session["user_id"] = user["id"]
            session["pending_otp_user_id"] = user["id"]
            session["pending_otp_hash"] = make_otp_hash(user["id"], code)
            session["pending_otp_expires"] = int(time.time()) + 300
            session["pending_otp_attempts"] = 0

            app.logger.info("Local OTP for %s: %s", email, code)

            return redirect(url_for("verify_otp"))

        flash("Email or password was not recognized.", "error")

    return render_template("auth.html", mode="login")

@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    user_id = session.get("pending_otp_user_id")

    if not user_id:
        flash("Please sign in first.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        expires = session.get("pending_otp_expires", 0)

        if time.time() > expires:
            for key in (
                "pending_otp_user_id",
                "pending_otp_hash",
                "pending_otp_expires",
                "pending_otp_attempts",
            ):
                session.pop(key, None)

            flash("Your code expired. Please sign in again.", "error")
            return redirect(url_for("login"))

        attempts = session.get("pending_otp_attempts", 0) + 1
        session["pending_otp_attempts"] = attempts

        if attempts > 5:
            session.clear()
            flash("Too many attempts. Please sign in again.", "error")
            return redirect(url_for("login"))

        submitted_code = request.form.get("otp", "").strip()
        submitted_hash = make_otp_hash(user_id, submitted_code)
        saved_hash = session.get("pending_otp_hash", "")

        if hmac.compare_digest(submitted_hash, saved_hash):
            cart = session.get("cart", {})

            session.clear()
            session["cart"] = cart
            session["user_id"] = user_id

            flash("You are signed in.", "success")
            return redirect(url_for("index"))

        flash("That code is incorrect.", "error")

    return render_template("otp.html")

@app.post("/logout")
def logout():
    session.clear(); flash("You are signed out.","success"); return redirect(url_for("index"))

def require_login():
    if not session.get("user_id"): flash("Please sign in to continue.","error"); return False
    return True

def require_admin():
    if not session.get("user_id"):
        flash("Please sign in with an admin account.", "error")
        return redirect(url_for("login"))

    user = get_db().execute(
        "SELECT role FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    if user["role"] != "admin":
        abort(403)

    return None

@app.get("/admin/image-preview")
def admin_image_preview():
    denied = require_admin()
    if denied:
        return denied

    # Intentionally vulnerable local coursework demonstration: the admin
    # image-preview feature also reads a caller-selected local file path.
    local_file = request.args.get("file")
    if local_file:
        file_path = (Path(app.static_folder) / local_file).resolve()
        try:
            contents = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            abort(404, "The requested local file could not be read")
        return contents, 200, {"Content-Type": "text/plain; charset=utf-8"}

    target = request.args.get("url", "")
    parsed = urlsplit(target)

    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 5000
        or parsed.username
        or parsed.password
    ):
        abort(400, "For this local test, use your app at 127.0.0.1:5000")

    try:
        response = requests.get(target, timeout=3, allow_redirects=False)
    except requests.RequestException:
        abort(502, "The server could not fetch that URL")

    return (
        f"Fetched by the server. HTTP {response.status_code}\n\n"
        + response.text[:2000],
        200,
        {"Content-Type": "text/plain; charset=utf-8"},
    )

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if not require_login():
        return redirect(url_for("login"))

    cart = session.get("cart", {})
    if not cart:
        flash("Your bag is empty.", "error")
        return redirect(url_for("cart"))

    db = get_db()
    rows = []
    total = 0

    for product_id, quantity in cart.items():
        product = db.execute(
            "SELECT * FROM products WHERE id = ?",
            (int(product_id),)
        ).fetchone()

        if product:
            quantity = int(quantity)
            rows.append((product, quantity))
            total += product["price_cents"] * quantity

    if request.method == "POST":
        address = request.form.get("address", "").strip()

        if not address:
            flash("Delivery address enter karo.", "error")
        else:
            try:
                payment_order = get_razorpay_client().order.create(data={
                    "amount": total,
                    "currency": "INR",
                    "receipt": f"shop-{session['user_id']}-{int(__import__('time').time())}",
                })

                local_order = db.execute(
                    """
                    INSERT INTO orders
                    (user_id, total_cents, payment_status, payment_order_id, shipping_address)
                    VALUES (?, ?, 'pending', ?, ?)
                    """,
                    (
                        session["user_id"],
                        total,
                        payment_order["id"],
                        address,
                    ),
                )

                for product, quantity in rows:
                    db.execute(
                        """
                        INSERT INTO order_items
                        (order_id, product_id, quantity, unit_price_cents)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            local_order.lastrowid,
                            product["id"],
                            quantity,
                            product["price_cents"],
                        ),
                    )

                db.commit()

                return render_template(
                    "checkout.html",
                    rows=rows,
                    total=total,
                    payment_ready=True,
                    razorpay_key_id=RAZORPAY_KEY_ID,
                    razorpay_order_id=payment_order["id"],
                    razorpay_amount=payment_order["amount"],
                    local_order_id=local_order.lastrowid,
                )

            except Exception:
                app.logger.exception("Razorpay order creation failed")
                db.rollback()
                flash("Payment start nahi ho paya. Test keys check karo.", "error")
            except Exception as error:
                app.logger.exception("Payment order creation failed")
                db.rollback()
                flash("Payment could not be started. Check the server terminal for the exact error.", "error")

    return render_template(
        "checkout.html",
        rows=rows,
        total=total,
        payment_ready=False,
    )
    
@app.post("/payment/verify")
def verify_payment():
    if not require_login():
        return redirect(url_for("login"))

    order_id = request.form.get("local_order_id", type=int)
    razorpay_order_id = request.form.get("razorpay_order_id", "")
    razorpay_payment_id = request.form.get("razorpay_payment_id", "")
    razorpay_signature = request.form.get("razorpay_signature", "")

    db = get_db()
    order = db.execute(
        """
        SELECT * FROM orders
        WHERE id = ? AND user_id = ?
        """,
        (order_id, session["user_id"]),
    ).fetchone()

    if not order or order["payment_order_id"] != razorpay_order_id:
        abort(400)

    try:
        get_razorpay_client().utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        })
    except Exception:
        flash("Payment verify nahi ho paya.", "error")
        return redirect(url_for("checkout"))

    db.execute(
        """
        UPDATE orders
        SET payment_status = 'paid', payment_id = ?
        WHERE id = ? AND user_id = ?
        """,
        (razorpay_payment_id, order_id, session["user_id"]),
    )
    db.commit()

    session["cart"] = {}
    flash("Payment successful. Order confirmed.", "success")
    return redirect(url_for("orders"))

@app.get("/orders")
def orders():
    if not require_login():
        return redirect(url_for("login"))

    db = get_db()

    order_rows = db.execute(
        """
        SELECT *
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],),
    ).fetchall()

    orders = []

    for order_row in order_rows:
        order = dict(order_row)

        order["items"] = db.execute(
            """
            SELECT
                products.id AS product_id,
                products.name,
                products.image,
                order_items.quantity
            FROM order_items
            JOIN products ON products.id = order_items.product_id
            WHERE order_items.order_id = ?
            """,
            (order_row["id"],),
        ).fetchall()

        orders.append(order)

    return render_template("orders.html", orders=orders)

@app.get("/orders/<int:order_id>")
def order_detail(order_id):
    if not require_login():
        return redirect(url_for("login"))

    db = get_db()
    order = db.execute(
        """
        SELECT orders.*, users.name AS customer_name, users.email AS customer_email
        FROM orders
        JOIN users ON users.id = orders.user_id
        WHERE orders.id = ?
        """,
        (order_id,),
    ).fetchone()

    if order is None:
        abort(404)

    items = db.execute(
    """
    SELECT
        products.id AS product_id,
        products.name,
        products.image,
        order_items.quantity,
        order_items.unit_price_cents,
        (order_items.quantity * order_items.unit_price_cents) AS line_total_cents
    FROM order_items
    JOIN products ON products.id = order_items.product_id
    WHERE order_items.order_id = ?
    """,
    (order_id,),
    ).fetchall()

    return render_template("order_detail.html", order=order, items=items)

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not session.get("user_id"):
        flash("Please sign in to view your profile.", "error")
        return redirect(url_for("login"))

    db = get_db()
    user_id = session["user_id"]

    if request.method == "POST":
        if "role" in request.form:
            role = request.form.get("role", "customer")
            db.execute(
                "UPDATE users SET role = ? WHERE id = ?",
                (role, user_id),
            )
            db.commit()

        photo = request.files.get("avatar")

        if photo and photo.filename:
            extension = Path(photo.filename).suffix.lower()
            allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}

            if extension not in allowed_extensions:
                flash("Use a JPG, PNG, or WEBP image.", "error")
            else:
                avatar_dir = Path(app.static_folder) / "uploads" / "avatars"
                avatar_dir.mkdir(parents=True, exist_ok=True)

                filename = f"user-{user_id}-{secrets.token_hex(8)}{extension}"
                photo.save(avatar_dir / filename)

                db.execute(
                    "UPDATE users SET avatar_filename = ? WHERE id = ?",
                    (filename, user_id),
                )
                db.commit()
                flash("Profile photo updated.", "success")
        elif "role" not in request.form:
            flash("Choose a profile image first.", "error")

    user = db.execute(
        """
        SELECT id, name, email, role, avatar_filename
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    stats = db.execute(
        """
        SELECT COUNT(*) AS order_count,
               COALESCE(SUM(total_cents), 0) AS total_spent
        FROM orders
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    recent_orders = db.execute(
        """
        SELECT id, total_cents, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 3
        """,
        (user_id,),
    ).fetchall()

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        recent_orders=recent_orders,
    )

@app.get("/admin")
def admin():
    denied = require_admin()
    if denied:
        return denied

    db = get_db()

    products = db.execute(
        "SELECT * FROM products ORDER BY id DESC"
    ).fetchall()

    recent_orders = db.execute(
        """
        SELECT orders.id, orders.total_cents, orders.created_at,
               users.name AS customer_name,
               users.email AS customer_email
        FROM orders
        JOIN users ON users.id = orders.user_id
        ORDER BY orders.id DESC
        LIMIT 8
        """
    ).fetchall()

    stats = {
        "products": db.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0],
        "orders": db.execute(
            "SELECT COUNT(*) FROM orders"
        ).fetchone()[0],
        "customers": db.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'customer'"
        ).fetchone()[0],
    }

    return render_template(
        "admin.html",
        products=products,
        recent_orders=recent_orders,
        stats=stats,
    )

@app.route("/admin/products/new", methods=["GET", "POST"])
def admin_product_new():
    denied = require_admin()
    if denied:
        return denied

    categories = [
        "Accessories",
        "Clothing",
        "Electronics",
        "Home",
        "Stationery",
    ]

    if request.method == "POST":
        try:
            product_data = read_product_form()
            db = get_db()
            db.execute(
                """
                INSERT INTO products
                    (name, description, price_cents, image, category)
                VALUES (?, ?, ?, ?, ?)
                """,
                product_data,
            )
            db.commit()

            flash("Product added.", "success")
            return redirect(url_for("admin"))

        except ValueError as error:
            flash(str(error), "error")

    return render_template(
        "admin_product_form.html",
        product=None,
        categories=categories,
        price_value=request.form.get("price", ""),
        page_title="Add a product",
    )


@app.route(
    "/admin/products/<int:product_id>/edit",
    methods=["GET", "POST"],
)
def admin_product_edit(product_id):
    denied = require_admin()
    if denied:
        return denied

    db = get_db()
    product = db.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,),
    ).fetchone()

    if product is None:
        abort(404)

    categories = sorted({
        "Accessories",
        "Clothing",
        "Electronics",
        "Home",
        "Stationery",
        product["category"],
    })

    if request.method == "POST":
        try:
            product_data = read_product_form()
            db.execute(
                """
                UPDATE products
                SET name = ?, description = ?, price_cents = ?,
                    image = ?, category = ?
                WHERE id = ?
                """,
                (*product_data, product_id),
            )
            db.commit()

            flash("Product updated.", "success")
            return redirect(url_for("admin"))

        except ValueError as error:
            flash(str(error), "error")

    price_value = request.form.get(
        "price",
        f"{product['price_cents'] / 100:.2f}",
    )

    return render_template(
        "admin_product_form.html",
        product=product,
        categories=categories,
        price_value=price_value,
        page_title="Edit product",
    )


@app.post("/admin/products/<int:product_id>/delete")
def admin_product_delete(product_id):
    denied = require_admin()
    if denied:
        return denied

    db = get_db()

    product = db.execute(
        "SELECT id FROM products WHERE id = ?",
        (product_id,),
    ).fetchone()

    if product is None:
        abort(404)

    already_ordered = db.execute(
        """
        SELECT 1 FROM order_items
        WHERE product_id = ?
        LIMIT 1
        """,
        (product_id,),
    ).fetchone()

    if already_ordered:
        flash(
            "This product is part of an order and cannot be deleted.",
            "error",
        )
    else:
        db.execute(
            "DELETE FROM products WHERE id = ?",
            (product_id,),
        )
        db.commit()
        flash("Product deleted.", "success")

    return redirect(url_for("admin"))

@app.get("/admin/image-check")
def admin_image_check():
    denied = require_admin()
    if denied:
        return denied

    name = request.args.get("name", "")
    result = subprocess.run(
        f"echo Checking image {name}",
        shell=True,
        capture_output=True,
        text=True,
        timeout=5,
    )

    return app.response_class(result.stdout, mimetype="text/plain")

@app.get("/wishlist")
def wishlist():
    return render_template("wishlist.html")


@app.get("/api/wishlist-products")
def wishlist_products():
    raw_ids = request.args.get("ids", "")

    product_ids = []
    for value in raw_ids.split(","):
        if value.isdigit():
            product_ids.append(int(value))
        if len(product_ids) >= 50:
            break

    if not product_ids:
        return jsonify([])

    db = get_db()
    placeholders = ",".join("?" for _ in product_ids)

    rows = db.execute(
        f"""
        SELECT id, name, description, price_cents, image, category
        FROM products
        WHERE id IN ({placeholders})
        """,
        product_ids,
    ).fetchall()

    products_by_id = {
        str(row["id"]): {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "price": f"₹{row['price_cents'] / 100:,.2f}",
            "image": row["image"],
            "category": row["category"],
        }
        for row in rows
    }

    return jsonify([
        products_by_id[str(product_id)]
        for product_id in product_ids
        if str(product_id) in products_by_id
    ])

@app.get("/info/<slug>", endpoint="store_info_page")
def store_info_page(slug):
    info_pages = {
        "about": {
            "eyebrow": "OUR STORY",
            "title": "About Morrow Market",
            "intro": "Thoughtful finds for everyday living.",
            "paragraphs": [
                "Morrow Market is a fictional shopping application created as a local learning project.",
                "The product catalogue and store experience are provided for demonstration purposes.",
            ],
        },
        "contact": {
            "eyebrow": "GET IN TOUCH",
            "title": "Contact",
            "intro": "This local demo does not have a connected customer support inbox.",
            "paragraphs": [
                "Contact messages are not sent to a support team in this demo.",
            ],
        },
        "returns": {
            "eyebrow": "ORDER INFORMATION",
            "title": "Returns",
            "intro": "This application is a demonstration store.",
            "paragraphs": [
                "Orders placed here are for local testing and are not shipped.",
                "No real purchases or product returns are processed.",
            ],
        },
        "privacy": {
            "eyebrow": "YOUR INFORMATION",
            "title": "Privacy",
            "intro": "This application is a local learning demo.",
            "paragraphs": [
                "Information entered into the app may be stored in its local SQLite database for testing.",
                "Use fictional details only. Do not enter real payment information or passwords used elsewhere.",
            ],
        },
    }

    page = info_pages.get(slug)

    if page is None:
        abort(404)

    return render_template("info.html", page=page)

# Isolated, deliberately vulnerable exercises. Enable only for local training with SECURITY_LAB=1.
def lab_enabled():
    return os.environ.get("SECURITY_LAB") == "1"

@app.before_request
def keep_lab_opt_in():
    if request.path.startswith("/security-lab") and not lab_enabled():
        abort(404)

@app.after_request
def deliberately_weak_csp_headers(response):
    response.headers["Content-Security-Policy"] = (
        "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "script-src * 'unsafe-inline' 'unsafe-eval'; "
        "style-src * 'unsafe-inline'; img-src * data: blob:"
    )

    if lab_enabled() and request.path == "/security-lab/frame":
        response.headers.pop("X-Frame-Options", None)

    origin = request.headers.get("Origin")
    if request.path == "/profile" and origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers.add("Vary", "Origin")

    return response

@app.get("/security-lab")
def security_lab_home():
    return render_template("security_lab.html", exercise=None)

@app.route("/security-lab/html", methods=["GET", "POST"])
def security_lab_html():
    submitted = request.values.get("text", "")
    return render_template("security_lab.html", exercise="html", submitted=submitted)

@app.get("/security-lab/content")
def security_lab_content():
    return render_template("security_lab.html", exercise="content", submitted=request.args.get("text", ""))

@app.get("/security-lab/params")
def security_lab_params():
    values = request.args.getlist("item")
    return render_template("security_lab.html", exercise="params", values=values)

@app.get("/security-lab/export.csv")
def security_lab_csv():
    name = request.args.get("name", "Demo Customer")[:120]
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["name", "note"])
    writer.writerow([name, "Synthetic security lab record"])
    response = app.response_class(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=security-lab.csv"
    return response

@app.get("/security-lab/cors")
def security_lab_cors():
    response = jsonify({"notice": "Synthetic public lab data", "records": [
        {"id": "LAB-001", "name": "Asha Demo", "order_total": "₹1,299.00"},
        {"id": "LAB-002", "name": "Ravi Example", "order_total": "₹499.00"},
    ]})
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response

@app.get("/security-lab/api/private-looking")
def security_lab_unauth_api():
    return jsonify({"records": [
        {"user": "demo-01", "email": "asha@example.test", "address": "12 Example Road"},
        {"user": "demo-02", "email": "ravi@example.test", "address": "8 Sample Street"},
    ]})
    
@app.get("/api/customer-orders")
def customer_orders_api():
    # Fake training data only; intentionally no login check.
    return jsonify({
        "orders": [
            {
                "order_id": "DEMO-1001",
                "customer": "Asha Example",
                "email": "asha@example.test",
                "total": "₹1,299.00"
            },
            {
                "order_id": "DEMO-1002",
                "customer": "Ravi Example",
                "email": "ravi@example.test",
                "total": "₹499.00"
            }
        ]
    })

@app.get("/security-lab/csp")
def security_lab_csp():
    return render_template("security_lab.html", exercise="csp")

@app.get("/security-lab/frame")
def security_lab_frame():
    return render_template("security_lab.html", exercise="frame")
@app.cli.command("init-db")
def init_db_command():
    init_db(); print("Database initialized with sample products.")

init_db()
if __name__ == "__main__":
    # Local development only: keep the server on this computer.
    app.run(host="127.0.0.1", port=5000, debug=True)


