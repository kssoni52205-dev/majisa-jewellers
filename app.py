import os
import sqlite3
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

app = Flask(__name__)

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "majisa-development-secret-change-this"
)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "change-this-password"
)

DATABASE = "majisa.db"


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            discount REAL NOT NULL DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    conn.close()


# Database automatically initialize karega
init_db()


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


def get_cart():
    return session.get("cart", {})


def save_cart(cart):
    session["cart"] = cart
    session.modified = True


def cart_count():
    cart = get_cart()
    return sum(cart.values())


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route("/")
def home():
    conn = get_db()

    featured = conn.execute("""
        SELECT * FROM products
        WHERE featured = 1
        ORDER BY id DESC
        LIMIT 8
    """).fetchall()

    latest = conn.execute("""
        SELECT * FROM products
        ORDER BY id DESC
        LIMIT 12
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        featured=featured,
        latest=latest,
        cart_count=cart_count()
    )


# --------------------------------------------------
# PRODUCTS
# --------------------------------------------------

@app.route("/products")
def products():
    category = request.args.get("category", "").strip()
    search = request.args.get("search", "").strip()

    conn = get_db()

    if search:
        items = conn.execute("""
            SELECT * FROM products
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
            SELECT * FROM products
            WHERE category = ?
            ORDER BY id DESC
        """, (category,)).fetchall()

    else:
        items = conn.execute("""
            SELECT * FROM products
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
        search=search,
        cart_count=cart_count()
    )


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    conn = get_db()

    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    reviews = conn.execute("""
        SELECT * FROM reviews
        WHERE product_id = ?
        ORDER BY id DESC
    """, (product_id,)).fetchall()

    conn.close()

    if product is None:
        return "Product not found", 404

    return render_template(
        "product.html",
        product=product,
        reviews=reviews,
        cart_count=cart_count()
    )


# --------------------------------------------------
# SEARCH
# --------------------------------------------------

@app.route("/search")
def search():
    query = request.args.get("q", "").strip()

    return redirect(
        url_for("products", search=query)
    )


# --------------------------------------------------
# CART
# --------------------------------------------------

@app.route("/cart")
def cart():
    cart = get_cart()

    if not cart:
        return render_template(
            "cart.html",
            items=[],
            total=0,
            cart_count=0
        )

    product_ids = list(cart.keys())

    placeholders = ",".join(["?"] * len(product_ids))

    conn = get_db()

    products_list = conn.execute(
        f"""
        SELECT * FROM products
        WHERE id IN ({placeholders})
        """,
        product_ids
    ).fetchall()

    conn.close()

    items = []
    total = 0

    for product in products_list:
        quantity = cart.get(str(product["id"]), 0)

        subtotal = product["price"] * quantity
        total += subtotal

        items.append({
            "product": product,
            "quantity": quantity,
            "subtotal": subtotal
        })

    return render_template(
        "cart.html",
        items=items,
        total=total,
        cart_count=cart_count()
    )


@app.route("/cart/add/<int:product_id>", methods=["POST", "GET"])
def add_to_cart(product_id):
    conn = get_db()

    product = conn.execute(
        "SELECT id FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    conn.close()

    if product is None:
        return "Product not found", 404

    cart = get_cart()

    key = str(product_id)

    cart[key] = cart.get(key, 0) + 1

    save_cart(cart)

    return redirect(request.referrer or url_for("cart"))


@app.route("/cart/remove/<int:product_id>", methods=["POST", "GET"])
def remove_from_cart(product_id):
    cart = get_cart()

    key = str(product_id)

    if key in cart:
        del cart[key]

    save_cart(cart)

    return redirect(url_for("cart"))


@app.route("/cart/clear", methods=["POST", "GET"])
def clear_cart():
    session["cart"] = {}
    session.modified = True

    return redirect(url_for("cart"))


# --------------------------------------------------
# WISHLIST
# --------------------------------------------------

@app.route("/wishlist")
def wishlist():
    wishlist_ids = session.get("wishlist", [])

    if not wishlist_ids:
        return render_template(
            "wishlist.html",
            products=[],
            cart_count=cart_count()
        )

    placeholders = ",".join(["?"] * len(wishlist_ids))

    conn = get_db()

    products_list = conn.execute(
        f"""
        SELECT * FROM products
        WHERE id IN ({placeholders})
        """,
        wishlist_ids
    ).fetchall()

    conn.close()

    return render_template(
        "wishlist.html",
        products=products_list,
        cart_count=cart_count()
    )


@app.route("/wishlist/toggle/<int:product_id>", methods=["POST", "GET"])
def toggle_wishlist(product_id):
    wishlist = session.get("wishlist", [])

    if product_id in wishlist:
        wishlist.remove(product_id)
    else:
        wishlist.append(product_id)

    session["wishlist"] = wishlist
    session.modified = True

    return redirect(request.referrer or url_for("wishlist"))


# --------------------------------------------------
# LOGIN / REGISTER
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()

        if not name or not email or not password:
            flash("Please fill all required fields.")
            return redirect(url_for("register"))

        conn = get_db()

        try:
            conn.execute("""
                INSERT INTO users
                (name, email, password, phone)
                VALUES (?, ?, ?, ?)
            """, (
                name,
                email,
                password,
                phone
            ))

            conn.commit()

        except sqlite3.IntegrityError:
            conn.close()

            flash("Email already registered.")
            return redirect(url_for("register"))

        conn.close()

        flash("Registration successful. Please login.")

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()

        user = conn.execute("""
            SELECT * FROM users
            WHERE email = ? AND password = ?
        """, (
            email,
            password
        )).fetchone()

        conn.close()

        if user:

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(
                request.args.get(
                    "next",
                    url_for("home")
                )
            )

        flash("Invalid email or password.")

    return render_template("login.html")


@app.route("/logout")
def logout():

    session.pop("user_id", None)
    session.pop("user_name", None)

    return redirect(url_for("home"))


# --------------------------------------------------
# CHECKOUT
# --------------------------------------------------

@app.route("/checkout", methods=["GET", "POST"])
def checkout():

    if not get_cart():
        return redirect(url_for("cart"))

    if request.method == "POST":

        customer_name = request.form.get(
            "name",
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

        if not customer_name or not phone or not address:
            flash("Please fill all checkout details.")
            return redirect(url_for("checkout"))

        cart = get_cart()

        product_ids = list(cart.keys())

        placeholders = ",".join(
            ["?"] * len(product_ids)
        )

        conn = get_db()

        products_list = conn.execute(
            f"""
            SELECT * FROM products
            WHERE id IN ({placeholders})
            """,
            product_ids
        ).fetchall()

        total = 0

        for product in products_list:
            quantity = cart.get(
                str(product["id"]),
                0
            )

            total += product["price"] * quantity

        cursor = conn.execute("""
            INSERT INTO orders
            (
                user_id,
                customer_name,
                phone,
                address,
                total,
                payment_method
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session.get("user_id"),
            customer_name,
            phone,
            address,
            total,
            payment_method
        ))

        order_id = cursor.lastrowid

        for product in products_list:

            quantity = cart.get(
                str(product["id"]),
                0
            )

            conn.execute("""
                INSERT INTO order_items
                (
                    order_id,
                    product_id,
                    product_name,
                    price,
                    quantity
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                order_id,
                product["id"],
                product["name"],
                product["price"],
                quantity
            ))

        conn.commit()
        conn.close()

        session["cart"] = {}

        return redirect(
            url_for(
                "order_success",
                order_id=order_id
            )
        )

    return render_template(
        "checkout.html",
        cart_count=cart_count()
    )


@app.route("/order-success/<int:order_id>")
def order_success(order_id):
    return render_template(
        "order_success.html",
        order_id=order_id
    )


# --------------------------------------------------
# ORDERS
# --------------------------------------------------

@app.route("/orders")
def orders():

    user_id = session.get("user_id")

    if not user_id:
        return redirect(
            url_for(
                "login",
                next=url_for("orders")
            )
        )

    conn = get_db()

    orders_list = conn.execute("""
        SELECT * FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,)).fetchall()

    conn.close()

    return render_template(
        "orders.html",
        orders=orders_list,
        cart_count=cart_count()
    )


@app.route("/order/<int:order_id>")
def order_detail(order_id):

    conn = get_db()

    order = conn.execute(
        "SELECT * FROM orders WHERE id = ?",
        (order_id,)
    ).fetchone()

    items = conn.execute("""
        SELECT * FROM order_items
        WHERE order_id = ?
    """, (order_id,)).fetchall()

    conn.close()

    if order is None:
        return "Order not found", 404

    return render_template(
        "order_detail.html",
        order=order,
        items=items
    )


# --------------------------------------------------
# REVIEWS
# --------------------------------------------------

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

    rating = int(
        request.form.get(
            "rating",
            5
        )
    )

    rating = max(1, min(5, rating))

    if name and message:

        conn = get_db()

        conn.execute("""
            INSERT INTO reviews
            (
                product_id,
                name,
                rating,
                message
            )
            VALUES (?, ?, ?, ?)
        """, (
            product_id,
            name,
            rating,
            message
        ))

        conn.commit()
        conn.close()

    return redirect(
        url_for(
            "product_detail",
            product_id=product_id
        )
    )


# --------------------------------------------------
# CONTACT / ABOUT / FAQ
# --------------------------------------------------

@app.route("/contact")
def contact():
    return render_template(
        "contact.html",
        cart_count=cart_count()
    )


@app.route("/about")
def about():
    return render_template(
        "about.html",
        cart_count=cart_count()
    )


@app.route("/faq")
def faq():
    return render_template(
        "faq.html",
        cart_count=cart_count()
    )


# --------------------------------------------------
# ADMIN LOGIN
# --------------------------------------------------

@app.route("/admin", methods=["GET", "POST"])
def admin_login():

    if session.get("admin_logged_in"):
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
            and password == ADMIN_PASSWORD
        ):
            session.clear()
            session["admin_logged_in"] = True

            return redirect(
                url_for("admin_dashboard")
            )

        flash("Invalid admin username or password.")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# --------------------------------------------------
# ADMIN DASHBOARD
# --------------------------------------------------

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

    products_list = conn.execute("""
        SELECT * FROM products
        ORDER BY id DESC
    """).fetchall()

    orders_list = conn.execute("""
        SELECT * FROM orders
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        products=products_list,
        orders=orders_list,
        products_count=products_count,
        orders_count=orders_count,
        users_count=users_count,
        reviews_count=reviews_count
    )


# --------------------------------------------------
# ADMIN - ADD PRODUCT
# --------------------------------------------------

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

    price = float(
        request.form.get(
            "price",
            0
        ) or 0
    )

    old_price = float(
        request.form.get(
            "old_price",
            0
        ) or 0
    )

    image = request.form.get(
        "image",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    stock = int(
        request.form.get(
            "stock",
            0
        ) or 0
    )

    featured = 1 if request.form.get(
        "featured"
    ) else 0

    if not name or not category:
        flash("Product name and category are required.")
        return redirect(
            url_for("admin_dashboard")
        )

    conn = get_db()

    conn.execute("""
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
    """, (
        name,
        category,
        price,
        old_price,
        image,
        description,
        stock,
        featured
    ))

    conn.commit()
    conn.close()

    flash("Product added successfully.")

    return redirect(
        url_for("admin_dashboard")
    )


# --------------------------------------------------
# ADMIN - DELETE PRODUCT
# --------------------------------------------------

@app.route(
    "/admin/product/delete/<int:product_id>",
    methods=["POST"]
)
@admin_required
def admin_delete_product(product_id):

    conn = get_db()

    conn.execute(
        "DELETE FROM products WHERE id = ?",
        (product_id,)
    )

    conn.execute(
        "DELETE FROM reviews WHERE product_id = ?",
        (product_id,)
    )

    conn.commit()
    conn.close()

    flash("Product deleted.")

    return redirect(
        url_for("admin_dashboard")
    )


# --------------------------------------------------
# ADMIN - UPDATE ORDER STATUS
# --------------------------------------------------

@app.route(
    "/admin/order/status/<int:order_id>",
    methods=["POST"]
)
@admin_required
def admin_update_order(order_id):

    status = request.form.get(
        "status",
        "Pending"
    )

    allowed_statuses = [
        "Pending",
        "Confirmed",
        "Packed",
        "Shipped",
        "Delivered",
        "Cancelled"
    ]

    if status not in allowed_statuses:
        status = "Pending"

    conn = get_db()

    conn.execute("""
        UPDATE orders
        SET status = ?
        WHERE id = ?
    """, (
        status,
        order_id
    ))

    conn.commit()
    conn.close()

    flash("Order status updated.")

    return redirect(
        url_for("admin_dashboard")
    )


# --------------------------------------------------
# API - PRODUCTS
# --------------------------------------------------

@app.route("/api/products")
def api_products():

    conn = get_db()

    products_list = conn.execute("""
        SELECT * FROM products
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return jsonify([
        dict(product)
        for product in products_list
    ])


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.route("/health")
def health():

    return {
        "status": "ok",
        "app": "Majisa Jewellers"
    }


# --------------------------------------------------
# 404
# --------------------------------------------------

@app.errorhandler(404)
def page_not_found(error):

    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Page Not Found</title>
    </head>
    <body>
        <h1>404 - Page Not Found</h1>
        <p>The page you are looking for does not exist.</p>
    </body>
    </html>
    """, 404


# --------------------------------------------------
# RUN
# --------------------------------------------------

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
