import os
import sqlite3
import secrets
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify
)

from werkzeug.utils import secure_filename


app = Flask(__name__)


# ==========================================================
# CONFIG
# ==========================================================

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "majisa-development-secret-change-this"
)

ADMIN_USERNAME = os.environ.get(
    "ADMIN_USERNAME",
    "admin"
)

ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "change-this-password"
)

DATABASE = os.path.join(
    app.root_path,
    "majisa.db"
)

UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "images"
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}


# ==========================================================
# IMAGE HELPERS
# ==========================================================

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower() in ALLOWED_EXTENSIONS
    )


def save_product_image(file):

    if not file:
        return ""

    if not file.filename:
        return ""

    if not allowed_file(file.filename):
        raise ValueError(
            "Only JPG, JPEG, PNG and WEBP images are allowed."
        )

    original_name = secure_filename(
        file.filename
    )

    extension = os.path.splitext(
        original_name
    )[1].lower()

    filename = (
        f"product_"
        f"{secrets.token_hex(10)}"
        f"{extension}"
    )

    file.save(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )
    )

    return filename


def delete_product_image(filename):

    if not filename:
        return

    filename = os.path.basename(
        filename
    )

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    try:
        if os.path.isfile(file_path):
            os.remove(file_path)
    except OSError:
        pass


# ==========================================================
# DATABASE
# ==========================================================

def get_db():

    conn = sqlite3.connect(
        DATABASE
    )

    conn.row_factory = sqlite3.Row

    return conn


def add_column_if_missing(
    conn,
    table,
    column,
    definition
):

    columns = conn.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    existing = [
        row["name"]
        for row in columns
    ]

    if column not in existing:

        conn.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN {column} {definition}
            """
        )


def init_db():

    conn = get_db()

    # ------------------------------------------------------
    # PRODUCTS
    # ------------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            old_price REAL DEFAULT 0,
            image TEXT DEFAULT '',
            description TEXT DEFAULT '',
            stock INTEGER DEFAULT 0,
            featured INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------------------------------
    # USERS
    # ------------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT DEFAULT '',
            address TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------------------------------
    # ORDERS
    # ------------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            total REAL NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'Pending',
            payment_method TEXT DEFAULT 'COD',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------------------------------
    # ORDER ITEMS
    # ------------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL
        )
    """)

    # ------------------------------------------------------
    # REVIEWS
    # ------------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            rating INTEGER NOT NULL DEFAULT 5,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------------------------------
    # COUPONS
    # ------------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            discount REAL NOT NULL DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    """)

    # ------------------------------------------------------
    # STORE SETTINGS
    # ------------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            store_name TEXT DEFAULT 'Majisa Jewellers',
            phone TEXT DEFAULT '8949144970',
            email TEXT DEFAULT '',
            instagram TEXT DEFAULT 'majisa_art_jewellers',
            address TEXT DEFAULT '',
            city TEXT DEFAULT '',
            pincode TEXT DEFAULT '',
            business_hours TEXT DEFAULT '10:00 AM - 8:00 PM',
            currency TEXT DEFAULT 'INR',
            cod TEXT DEFAULT 'enabled',
            upi TEXT DEFAULT 'enabled',
            shipping_charge REAL DEFAULT 0,
            free_shipping REAL DEFAULT 999,
            delivery_time TEXT DEFAULT '5-7 business days',
            store_status TEXT DEFAULT 'open',
            maintenance_message TEXT DEFAULT ''
        )
    """)

    conn.execute("""
        INSERT OR IGNORE INTO settings
        (
            id,
            store_name,
            phone,
            instagram
        )
        VALUES
        (
            1,
            'Majisa Jewellers',
            '8949144970',
            'majisa_art_jewellers'
        )
    """)

    # ------------------------------------------------------
    # SAFE MIGRATIONS
    # ------------------------------------------------------

    add_column_if_missing(
        conn,
        "users",
        "reset_token",
        "TEXT DEFAULT ''"
    )

    add_column_if_missing(
        conn,
        "users",
        "reset_token_created",
        "TEXT DEFAULT ''"
    )

    add_column_if_missing(
        conn,
        "orders",
        "email",
        "TEXT DEFAULT ''"
    )

    add_column_if_missing(
        conn,
        "orders",
        "subtotal",
        "REAL DEFAULT 0"
    )

    add_column_if_missing(
        conn,
        "orders",
        "shipping",
        "REAL DEFAULT 0"
    )

    add_column_if_missing(
        conn,
        "orders",
        "discount",
        "REAL DEFAULT 0"
    )

    add_column_if_missing(
        conn,
        "orders",
        "payment_status",
        "TEXT DEFAULT 'Pending'"
    )

    conn.commit()
    conn.close()


init_db()


# ==========================================================
# HELPERS
# ==========================================================

def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get(
            "admin_logged_in"
        ):

            return redirect(
                url_for("admin_login")
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped


def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get("user_id"):

            return redirect(
                url_for(
                    "login",
                    next=request.path
                )
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped


def get_cart():

    return session.get(
        "cart",
        {}
    )


def save_cart(cart):

    session["cart"] = cart
    session.modified = True


def cart_count():

    cart = get_cart()

    return sum(
        int(quantity)
        for quantity in cart.values()
    )


def get_settings():

    conn = get_db()

    settings = conn.execute(
        """
        SELECT *
        FROM settings
        WHERE id = 1
        """
    ).fetchone()

    conn.close()

    return settings


# ==========================================================
# GLOBAL TEMPLATE DATA
# ==========================================================

@app.context_processor
def inject_global_data():

    return {
        "store_settings": get_settings(),
        "cart_count": cart_count(),
        "site_name": "Majisa Jewellers",
        "site_phone": "8949144970",
        "site_instagram": "majisa_art_jewellers"
    }


# ==========================================================
# HOME
# ==========================================================

@app.route("/")
def home():

    conn = get_db()

    featured = conn.execute("""
        SELECT *
        FROM products
        WHERE featured = 1
        ORDER BY id DESC
        LIMIT 8
    """).fetchall()

    latest = conn.execute("""
        SELECT *
        FROM products
        ORDER BY id DESC
        LIMIT 12
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        featured=featured,
        latest=latest
    )


# ==========================================================
# PRODUCTS
# ==========================================================

@app.route("/products")
def products():

    category = request.args.get(
        "category",
        ""
    ).strip()

    search = request.args.get(
        "search",
        ""
    ).strip()

    conn = get_db()

    if search:

        items = conn.execute("""
            SELECT *
            FROM products
            WHERE name LIKE ?
               OR category LIKE ?
               OR description LIKE ?
            ORDER BY id DESC
        """, (
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        )).fetchall()

    elif category:

        items = conn.execute("""
            SELECT *
            FROM products
            WHERE category = ?
            ORDER BY id DESC
        """, (
            category,
        )).fetchall()

    else:

        items = conn.execute("""
            SELECT *
            FROM products
            ORDER BY id DESC
        """).fetchall()

    categories = conn.execute("""
        SELECT DISTINCT category
        FROM products
        WHERE category != ''
        ORDER BY category
    """).fetchall()

    conn.close()

    return render_template(
        "products.html",
        products=items,
        categories=categories,
        selected_category=category,
        search=search
    )


@app.route("/product/<int:product_id>")
def product_detail(product_id):

    conn = get_db()

    product = conn.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    ).fetchone()

    reviews = conn.execute(
        """
        SELECT *
        FROM reviews
        WHERE product_id = ?
        ORDER BY id DESC
        """,
        (product_id,)
    ).fetchall()

    conn.close()

    if product is None:
        return "Product not found", 404

    return render_template(
        "product.html",
        product=product,
        reviews=reviews
    )


@app.route("/search")
def search():

    query = request.args.get(
        "q",
        ""
    ).strip()

    return redirect(
        url_for(
            "products",
            search=query
        )
    )


# ==========================================================
# CART
# ==========================================================

@app.route("/cart")
def cart():

    cart = get_cart()

    if not cart:

        return render_template(
            "cart.html",
            items=[],
            total=0
        )

    product_ids = list(
        cart.keys()
    )

    placeholders = ",".join(
        ["?"] * len(product_ids)
    )

    conn = get_db()

    products_list = conn.execute(
        f"""
        SELECT *
        FROM products
        WHERE id IN ({placeholders})
        """,
        product_ids
    ).fetchall()

    conn.close()

    items = []
    total = 0

    for product in products_list:

        quantity = int(
            cart.get(
                str(product["id"]),
                0
            )
        )

        subtotal = (
            product["price"] *
            quantity
        )

        total += subtotal

        items.append({
            "product": product,
            "quantity": quantity,
            "subtotal": subtotal
        })

    return render_template(
        "cart.html",
        items=items,
        total=total
    )


@app.route(
    "/cart/add/<int:product_id>",
    methods=["POST", "GET"]
)
def add_to_cart(product_id):

    conn = get_db()

    product = conn.execute(
        """
        SELECT id
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    ).fetchone()

    conn.close()

    if product is None:
        return "Product not found", 404

    cart = get_cart()

    key = str(product_id)

    cart[key] = (
        int(cart.get(key, 0)) + 1
    )

    save_cart(cart)

    return redirect(
        request.referrer or
        url_for("cart")
    )


@app.route(
    "/cart/remove/<int:product_id>",
    methods=["POST", "GET"]
)
def remove_from_cart(product_id):

    cart = get_cart()

    key = str(product_id)

    if key in cart:
        del cart[key]

    save_cart(cart)

    return redirect(
        url_for("cart")
    )


@app.route(
    "/cart/clear",
    methods=["POST", "GET"]
)
def clear_cart():

    session["cart"] = {}
    session.modified = True

    return redirect(
        url_for("cart")
    )


# ==========================================================
# WISHLIST
# ==========================================================

@app.route("/wishlist")
def wishlist():

    wishlist_ids = session.get(
        "wishlist",
        []
    )

    if not wishlist_ids:

        return render_template(
            "wishlist.html",
            products=[]
        )

    placeholders = ",".join(
        ["?"] * len(wishlist_ids)
    )

    conn = get_db()

    products_list = conn.execute(
        f"""
        SELECT *
        FROM products
        WHERE id IN ({placeholders})
        """,
        wishlist_ids
    ).fetchall()

    conn.close()

    return render_template(
        "wishlist.html",
        products=products_list
    )


@app.route(
    "/wishlist/toggle/<int:product_id>",
    methods=["POST", "GET"]
)
def toggle_wishlist(product_id):

    wishlist = session.get(
        "wishlist",
        []
    )

    if product_id in wishlist:
        wishlist.remove(product_id)
    else:
        wishlist.append(product_id)

    session["wishlist"] = wishlist
    session.modified = True

    return redirect(
        request.referrer or
        url_for("wishlist")
    )


# ==========================================================
# REGISTER
# ==========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        if not name or not email or not password:

            flash(
                "Please fill all required fields."
            )

            return redirect(
                url_for("register")
            )

        conn = get_db()

        try:

            conn.execute(
                """
                INSERT INTO users
                (
                    name,
                    email,
                    password,
                    phone
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    password,
                    phone
                )
            )

            conn.commit()

        except sqlite3.IntegrityError:

            conn.close()

            flash(
                "Email already registered."
            )

            return redirect(
                url_for("register")
            )

        conn.close()

        flash(
            "Registration successful. Please login."
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# ==========================================================
# LOGIN
# ==========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            AND password = ?
            """,
            (
                email,
                password
            )
        ).fetchone()

        conn.close()

        if user:

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            # ==========================================================
# LOGIN CONTINUED
# ==========================================================

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]

        next_page = request.args.get(
            "next"
        )

        if next_page:
            return redirect(next_page)

        return redirect(
            url_for("home")
        )

    flash(
        "Invalid email or password."
    )

    return render_template(
        "login.html"
    )


# ==========================================================
# LOGOUT
# ==========================================================

@app.route("/logout")
def logout():

    session.pop(
        "user_id",
        None
    )

    session.pop(
        "user_name",
        None
    )

    return redirect(
        url_for("home")
    )


# ==========================================================
# FORGOT PASSWORD
# ==========================================================

@app.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if user:

            token = secrets.token_urlsafe(
                32
            )

            conn.execute(
                """
                UPDATE users
                SET reset_token = ?,
                    reset_token_created = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    token,
                    user["id"]
                )
            )

            conn.commit()

            reset_url = url_for(
                "reset_password",
                token=token,
                _external=True
            )

            conn.close()

            return render_template(
                "forgot_password.html",
                message=(
                    "Password reset link generated."
                ),
                reset_url=reset_url
            )

        conn.close()

        flash(
            "No account found with this email."
        )

    return render_template(
        "forgot_password.html"
    )


# ==========================================================
# RESET PASSWORD
# ==========================================================

@app.route(
    "/reset-password/<token>",
    methods=["GET", "POST"]
)
def reset_password(token):

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE reset_token = ?
        """,
        (token,)
    ).fetchone()

    if user is None:

        conn.close()

        flash(
            "Invalid or expired reset link."
        )

        return redirect(
            url_for("forgot_password")
        )

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            request.form.get(
                "password_confirmation",
                ""
            )
        )

        if not password:

            conn.close()

            flash(
                "Password cannot be empty."
            )

            return redirect(
                url_for(
                    "reset_password",
                    token=token
                )
            )

        if (
            confirm_password
            and
            password != confirm_password
        ):

            conn.close()

            flash(
                "Passwords do not match."
            )

            return redirect(
                url_for(
                    "reset_password",
                    token=token
                )
            )

        conn.execute(
            """
            UPDATE users
            SET password = ?,
                reset_token = ''
            WHERE id = ?
            """,
            (
                password,
                user["id"]
            )
        )

        conn.commit()
        conn.close()

        flash(
            "Password reset successfully. Please login."
        )

        return redirect(
            url_for("login")
        )

    conn.close()

    return render_template(
        "reset_password.html",
        token=token
    )


# ==========================================================
# CHECKOUT
# ==========================================================

@app.route(
    "/checkout",
    methods=["GET", "POST"]
)
def checkout():

    if not get_cart():

        return redirect(
            url_for("cart")
        )

    if request.method == "POST":

        customer_name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        address = request.form.get(
            "address",
            ""
        ).strip()

        payment_method = request.form.get(
            "payment_method",
            "COD"
        )

        if (
            not customer_name
            or not phone
            or not address
        ):

            flash(
                "Please fill all checkout details."
            )

            return redirect(
                url_for("checkout")
            )

        cart = get_cart()

        product_ids = list(
            cart.keys()
        )

        placeholders = ",".join(
            ["?"] * len(product_ids)
        )

        conn = get_db()

        products_list = conn.execute(
            f"""
            SELECT *
            FROM products
            WHERE id IN ({placeholders})
            """,
            product_ids
        ).fetchall()

        subtotal = 0

        for product in products_list:

            quantity = int(
                cart.get(
                    str(product["id"]),
                    0
                )
            )

            subtotal += (
                product["price"] *
                quantity
            )

        settings = conn.execute(
            """
            SELECT *
            FROM settings
            WHERE id = 1
            """
        ).fetchone()

        shipping_charge = float(
            settings["shipping_charge"] or 0
        )

        free_shipping = float(
            settings["free_shipping"]
            or 999999999
        )

        shipping = (
            0
            if subtotal >= free_shipping
            else shipping_charge
        )

        total = subtotal + shipping

        cursor = conn.execute(
            """
            INSERT INTO orders
            (
                user_id,
                customer_name,
                phone,
                address,
                total,
                status,
                payment_method,
                email,
                subtotal,
                shipping,
                discount,
                payment_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.get("user_id"),
                customer_name,
                phone,
                address,
                total,
                "Pending",
                payment_method,
                email,
                subtotal,
                shipping,
                0,
                "Pending"
            )
        )

        order_id = cursor.lastrowid

        for product in products_list:

            quantity = int(
                cart.get(
                    str(product["id"]),
                    0
                )
            )

            conn.execute(
                """
                INSERT INTO order_items
                (
                    order_id,
                    product_id,
                    product_name,
                    price,
                    quantity
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    product["id"],
                    product["name"],
                    product["price"],
                    quantity
                )
            )

        conn.commit()
        conn.close()

        session["cart"] = {}

        return redirect(
            url_for(
                "order_success",
                order_id=order_id
            )
        )

    # ------------------------------------------------------
    # CHECKOUT GET PAGE
    # ------------------------------------------------------

    cart = get_cart()

    product_ids = list(
        cart.keys()
    )

    placeholders = ",".join(
        ["?"] * len(product_ids)
    )

    conn = get_db()

    products_list = conn.execute(
        f"""
        SELECT *
        FROM products
        WHERE id IN ({placeholders})
        """,
        product_ids
    ).fetchall()

    subtotal = 0

    for product in products_list:

        quantity = int(
            cart.get(
                str(product["id"]),
                0
            )
        )

        subtotal += (
            product["price"] *
            quantity
        )

    settings = conn.execute(
        """
        SELECT *
        FROM settings
        WHERE id = 1
        """
    ).fetchone()

    shipping_charge = float(
        settings["shipping_charge"] or 0
    )

    free_shipping = float(
        settings["free_shipping"]
        or 999999999
    )

    shipping = (
        0
        if subtotal >= free_shipping
        else shipping_charge
    )

    total = subtotal + shipping

    conn.close()

    return render_template(
        "checkout.html",
        products=products_list,
        subtotal=subtotal,
        shipping=shipping,
        total=total
    )


# ==========================================================
# ORDER SUCCESS
# ==========================================================

@app.route(
    "/order-success/<int:order_id>"
)
def order_success(order_id):

    return render_template(
        "order_success.html",
        order_id=order_id
    )


# ==========================================================
# CUSTOMER ORDERS
# ==========================================================

@app.route("/orders")
@login_required
def orders():

    user_id = session.get(
        "user_id"
    )

    conn = get_db()

    orders_list = conn.execute(
        """
        SELECT *
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    return render_template(
        "orders.html",
        orders=orders_list
    )


@app.route(
    "/order/<int:order_id>"
)
@login_required
def order_detail(order_id):

    user_id = session.get(
        "user_id"
    )

    conn = get_db()

    order = conn.execute(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        AND user_id = ?
        """,
        (
            order_id,
            user_id
        )
    ).fetchone()

    items = conn.execute(
        """
        SELECT *
        FROM order_items
        WHERE order_id = ?
        """,
        (
            order_id,
        )
    ).fetchall()

    conn.close()

    if order is None:

        return "Order not found", 404

    return render_template(
        "order_detail.html",
        order=order,
        items=items
    )


# ==========================================================
# REVIEWS
# ==========================================================

@app.route(
    "/product/<int:product_id>/review",
    methods=["POST"]
)
def add_review(product_id):

    name = request.form.get(
        "name",
        "Customer"
    ).strip()

    message = request.form.get(
        "message",
        ""
    ).strip()

    try:

        rating = int(
            request.form.get(
                "rating",
                5
            )
        )

    except ValueError:

        rating = 5

    rating = max(
        1,
        min(5, rating)
    )

    if name and message:

        conn = get_db()

        conn.execute(
            """
            INSERT INTO reviews
            (
                product_id,
                name,
                rating,
                message
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                product_id,
                name,
                rating,
                message
            )
        )

        conn.commit()
        conn.close()

    return redirect(
        url_for(
            "product_detail",
            product_id=product_id
        )
    )


# ==========================================================
# CONTACT / ABOUT / FAQ
# ==========================================================

@app.route("/contact")
def contact():

    return render_template(
        "contact.html"
    )


@app.route("/about")
def about():

    return render_template(
        "about.html"
    )


@app.route("/faq")
def faq():

    return render_template(
        "faq.html"
    )


# ==========================================================
# ADMIN LOGIN
# ==========================================================

@app.route(
    "/admin",
    methods=["GET", "POST"]
)
@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for("admin_dashboard")
        )

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            username == ADMIN_USERNAME
            and
            password == ADMIN_PASSWORD
        ):

            session.clear()

            session["admin_logged_in"] = True

            return redirect(
                url_for("admin_dashboard")
            )

        flash(
            "Invalid admin username or password."
        )

    return render_template(
        "admin_login.html"
    )


@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# ==========================================================
# ADMIN DASHBOARD
# ==========================================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    conn = get_db()

    products_count = conn.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    orders_count = conn.execute(
        "SELECT COUNT(*) FROM orders"
    ).fetchone()[0]

    users_count = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    reviews_count = conn.execute(
        "SELECT COUNT(*) FROM reviews"
    ).fetchone()[0]

    products_list = conn.execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()

    orders_list = conn.execute(
        """
        SELECT *
        FROM orders
        ORDER BY id DESC
        LIMIT 20
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        products=products_list,
        orders=orders_list,
        products_count=products_count,
        orders_count=orders_count,
        users_count=users_count,
        reviews_count=reviews_count,
        total_products=products_count,
        total_orders=orders_count,
        total_customers=users_count,
        total_users=users_count
    )


# ==========================================================
# ADMIN PRODUCTS
# ==========================================================

@app.route("/admin/products")
@admin_required
def admin_products():

    search = request.args.get(
        "q",
        ""
    ).strip()

    conn = get_db()

    if search:

        products_list = conn.execute(
            """
            SELECT *
            FROM products
            WHERE name LIKE ?
               OR category LIKE ?
            ORDER BY id DESC
            """,
            (
                f"%{search}%",
                f"%{search}%"
            )
        ).fetchall()

    else:

        products_list = conn.execute(
            """
            SELECT *
            FROM products
            ORDER BY id DESC
            """
        ).fetchall()

    categories = conn.execute(
        """
        SELECT DISTINCT category
        FROM products
        WHERE category != ''
        ORDER BY category
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_products.html",
        products=products_list,
        categories=categories,
        search=search
    )


# ==========================================================
# ADMIN ADD PRODUCT
# ==========================================================

@app.route(
    "/admin/product/add",
    methods=["POST"]
)
@admin_required
def admin_add_product():

    name = request.form.get(
        "name",
        ""
    ).strip()

    category = request.form.get(
        "category",
        ""
    ).strip()

    try:

        price = float(
            request.form.get(
                "price",
                0
            ) or 0
        )

    except ValueError:

        price = 0

            try:
            old_price = float(
                request.form.get(
                    "old_price",
                    0
                ) or 0
            )
        except ValueError:
            old_price = 0

        try:
            stock = int(
                request.form.get(
                    "stock",
                    0
                ) or 0
            )
        except ValueError:
            stock = 0

    description = request.form.get(
        "description",
        ""
    ).strip()

    featured = 1 if request.form.get(
        "featured"
    ) else 0

    image = ""

    # Multiple possible image field names
    image_file = (
        request.files.get("image")
        or
        request.files.get("product_image")
    )

    if image_file and image_file.filename:

        try:

            image = save_product_image(
                image_file
            )

        except ValueError as error:

            flash(str(error))

            return redirect(
                url_for("admin_products")
            )

    conn = get_db()

    conn.execute(
        """
        INSERT INTO products
        (
            name,
            category,
            price,
            old_price,
            image,
            description,
            stock,
            featured
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            category,
            price,
            old_price,
            image,
            description,
            stock,
            featured
        )
    )

    conn.commit()
    conn.close()

    flash(
        "Product added successfully."
    )

    return redirect(
        url_for("admin_products")
    )


# ==========================================================
# ADMIN EDIT PRODUCT
# ==========================================================

@app.route(
    "/admin/product/edit/<int:product_id>",
    methods=["GET", "POST"]
)
@admin_required
def admin_edit_product(product_id):

    conn = get_db()

    product = conn.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    ).fetchone()

    conn.close()

    if product is None:

        return "Product not found", 404

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        try:

            price = float(
                request.form.get(
                    "price",
                    0
                ) or 0
            )

        except ValueError:

            price = 0

        try:

            old_price = float(
                request.form.get(
                    "old_price",
                    0
                ) or 0
            )

        except ValueError:

            old_price = 0

        try:

            stock = int(
                request.form.get(
                    "stock",
                    0
                ) or 0
            )

        except ValueError:

            stock = 0

        description = request.form.get(
            "description",
            ""
        ).strip()

        featured = 1 if request.form.get(
            "featured"
        ) else 0

        image = product["image"]

        image_file = (
            request.files.get("image")
            or
            request.files.get("product_image")
        )

        if image_file and image_file.filename:

            try:

                new_image = save_product_image(
                    image_file
                )

                if new_image:

                    delete_product_image(
                        image
                    )

                    image = new_image

            except ValueError as error:

                flash(str(error))

                return redirect(
                    url_for(
                        "admin_edit_product",
                        product_id=product_id
                    )
                )

        conn = get_db()

        conn.execute(
            """
            UPDATE products
            SET name = ?,
                category = ?,
                price = ?,
                old_price = ?,
                image = ?,
                description = ?,
                stock = ?,
                featured = ?
            WHERE id = ?
            """,
            (
                name,
                category,
                price,
                old_price,
                image,
                description,
                stock,
                featured,
                product_id
            )
        )

        conn.commit()
        conn.close()

        flash(
            "Product updated successfully."
        )

        return redirect(
            url_for("admin_products")
        )

    return render_template(
        "admin_edit_product.html",
        product=product
    )


# ==========================================================
# ADMIN DELETE PRODUCT
# ==========================================================

@app.route(
    "/admin/product/delete/<int:product_id>",
    methods=["POST", "GET"]
)
@admin_required
def admin_delete_product(product_id):

    conn = get_db()

    product = conn.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    ).fetchone()

    if product is None:

        conn.close()

        flash(
            "Product not found."
        )

        return redirect(
            url_for("admin_products")
        )

    image = product["image"]

    conn.execute(
        """
        DELETE FROM products
        WHERE id = ?
        """,
        (product_id,)
    )

    conn.execute(
        """
        DELETE FROM reviews
        WHERE product_id = ?
        """,
        (product_id,)
    )

    conn.commit()
    conn.close()

    delete_product_image(
        image
    )

    flash(
        "Product deleted successfully."
    )

    return redirect(
        url_for("admin_products")
    )


# ==========================================================
# ADMIN ORDERS
# ==========================================================

@app.route("/admin/orders")
@admin_required
def admin_orders():

    status = request.args.get(
        "status",
        ""
    ).strip()

    conn = get_db()

    if status:

        orders_list = conn.execute(
            """
            SELECT *
            FROM orders
            WHERE status = ?
            ORDER BY id DESC
            """,
            (status,)
        ).fetchall()

    else:

        orders_list = conn.execute(
            """
            SELECT *
            FROM orders
            ORDER BY id DESC
            """
        ).fetchall()

    conn.close()

    return render_template(
        "admin_orders.html",
        orders=orders_list,
        selected_status=status
    )


# ==========================================================
# ADMIN ORDER DETAIL
# ==========================================================

@app.route(
    "/admin/order/<int:order_id>"
)
@admin_required
def admin_order_detail(order_id):

    conn = get_db()

    order = conn.execute(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()

    items = conn.execute(
        """
        SELECT *
        FROM order_items
        WHERE order_id = ?
        """,
        (order_id,)
    ).fetchall()

    conn.close()

    if order is None:

        return "Order not found", 404

    return render_template(
        "admin_order_detail.html",
        order=order,
        items=items
    )


# ==========================================================
# ADMIN UPDATE ORDER
# ==========================================================

@app.route(
    "/admin/order/<int:order_id>/update",
    methods=["POST"]
)
@admin_required
def admin_update_order(order_id):

    status = request.form.get(
        "status",
        "Pending"
    ).strip()

    payment_status = request.form.get(
        "payment_status",
        "Pending"
    ).strip()

    allowed_statuses = {
        "Pending",
        "Confirmed",
        "Processing",
        "Shipped",
        "Delivered",
        "Cancelled"
    }

    allowed_payment_statuses = {
        "Pending",
        "Paid",
        "Failed",
        "Refunded"
    }

    if status not in allowed_statuses:

        status = "Pending"

    if payment_status not in allowed_payment_statuses:

        payment_status = "Pending"

    conn = get_db()

    conn.execute(
        """
        UPDATE orders
        SET status = ?,
            payment_status = ?
        WHERE id = ?
        """,
        (
            status,
            payment_status,
            order_id
        )
    )

    conn.commit()
    conn.close()

    flash(
        "Order updated successfully."
    )

    return redirect(
        url_for(
            "admin_order_detail",
            order_id=order_id
        )
    )


# ==========================================================
# ADMIN USERS
# ==========================================================

@app.route("/admin/users")
@admin_required
def admin_users():

    conn = get_db()

    users_list = conn.execute(
        """
        SELECT *
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_users.html",
        users=users_list
    )


# ==========================================================
# ADMIN REVIEWS
# ==========================================================

@app.route("/admin/reviews")
@admin_required
def admin_reviews():

    conn = get_db()

    reviews_list = conn.execute(
        """
        SELECT
            reviews.*,
            products.name AS product_name
        FROM reviews
        LEFT JOIN products
            ON products.id = reviews.product_id
        ORDER BY reviews.id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_reviews.html",
        reviews=reviews_list
    )


@app.route(
    "/admin/review/delete/<int:review_id>",
    methods=["POST", "GET"]
)
@admin_required
def admin_delete_review(review_id):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM reviews
        WHERE id = ?
        """,
        (review_id,)
    )

    conn.commit()
    conn.close()

    flash(
        "Review deleted successfully."
    )

    return redirect(
        url_for("admin_reviews")
    )


# ==========================================================
# ADMIN SETTINGS
# ==========================================================

@app.route(
    "/admin/settings",
    methods=["GET", "POST"]
)
@admin_required
def admin_settings():

    conn = get_db()

    settings = conn.execute(
        """
        SELECT *
        FROM settings
        WHERE id = 1
        """
    ).fetchone()

    if request.method == "POST":

        store_name = request.form.get(
            "store_name",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        instagram = request.form.get(
            "instagram",
            ""
        ).strip()

        address = request.form.get(
            "address",
            ""
        ).strip()

        city = request.form.get(
            "city",
            ""
        ).strip()

        pincode = request.form.get(
            "pincode",
            ""
        ).strip()

        business_hours = request.form.get(
            "business_hours",
            ""
        ).strip()

        currency = request.form.get(
            "currency",
            "INR"
        ).strip()

        cod = (
            "enabled"
            if request.form.get("cod")
            else "disabled"
        )

        upi = (
            "enabled"
            if request.form.get("upi")
            else "disabled"
        )

        try:

            shipping_charge = float(
                request.form.get(
                    "shipping_charge",
                    0
                ) or 0
            )

        except ValueError:

            shipping_charge = 0

        try:

            free_shipping = float(
                request.form.get(
                    "free_shipping",
                    999
                ) or 999
            )

        except ValueError:

            free_shipping = 999

        delivery_time = request.form.get(
            "delivery_time",
            "5-7 business days"
        ).strip()

        store_status = request.form.get(
            "store_status",
            "open"
        ).strip()

        maintenance_message = request.form.get(
            "maintenance_message",
            ""
        ).strip()

        conn.execute(
            """
            UPDATE settings
            SET store_name = ?,
                phone = ?,
                email = ?,
                instagram = ?,
                address = ?,
                city = ?,
                pincode = ?,
                business_hours = ?,
                currency = ?,
                cod = ?,
                upi = ?,
                shipping_charge = ?,
                free_shipping = ?,
                delivery_time = ?,
                store_status = ?,
                maintenance_message = ?
            WHERE id = 1
            """,
            (
                store_name,
                phone,
                email,
                instagram,
                address,
                city,
                pincode,
                business_hours,
                currency,
                cod,
                upi,
                shipping_charge,
                free_shipping,
                delivery_time,
                store_status,
                maintenance_message
            )
        )

        conn.commit()

        settings = conn.execute(
            """
            SELECT *
            FROM settings
            WHERE id = 1
            """
        ).fetchone()

        flash(
            "Store settings updated successfully."
        )

    conn.close()

    return render_template(
        "admin_settings.html",
        settings=settings
    )


# ==========================================================
# API - CART COUNT
# ==========================================================

@app.route("/api/cart-count")
def api_cart_count():

    return jsonify({
        "count": cart_count()
    })


# ==========================================================
# API - PRODUCT
# ==========================================================

@app.route(
    "/api/product/<int:product_id>"
)
def api_product(product_id):

    conn = get_db()

    product = conn.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    ).fetchone()

    conn.close()

    if product is None:

        return jsonify({
            "success": False,
            "message": "Product not found"
        }), 404

    return jsonify({
        "success": True,
        "product": dict(product)
    })


# ==========================================================
# HEALTH CHECK
# ==========================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "ok"
    })


# ==========================================================
# FAVICON
# ==========================================================

@app.route("/favicon.ico")
def favicon():

    return (
        app.send_static_file(
            "images/favicon.ico"
        )
    )


# ==========================================================
# ERROR HANDLERS
# ==========================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "404.html"
    ), 404


@app.errorhandler(500)
def internal_server_error(error):

    return render_template(
        "500.html"
    ), 500


# ==========================================================
# APPLICATION START
# ==========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
