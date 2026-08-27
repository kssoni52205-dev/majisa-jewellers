import os
import sqlite3
import secrets
import hashlib
import hmac
import time
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    send_from_directory
)

from werkzeug.utils import secure_filename


# ==========================================================
# APP
# ==========================================================

app = Flask(__name__)

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

app.config["MAX_CONTENT_LENGTH"] = (
    100 * 1024 * 1024
)


# ==========================================================
# RAZORPAY CONFIG
# ==========================================================

RAZORPAY_KEY_ID = os.environ.get(
    "RAZORPAY_KEY_ID",
    ""
)

RAZORPAY_KEY_SECRET = os.environ.get(
    "RAZORPAY_KEY_SECRET",
    ""
)

try:
    import razorpay
except ImportError:
    razorpay = None


def get_razorpay_client():

    if not RAZORPAY_KEY_ID:
        return None

    if not RAZORPAY_KEY_SECRET:
        return None

    if razorpay is None:
        return None

    return razorpay.Client(
        auth=(
            RAZORPAY_KEY_ID,
            RAZORPAY_KEY_SECRET
        )
    )


# ==========================================================
# FILE TYPES
# ==========================================================

ALLOWED_IMAGE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

ALLOWED_VIDEO_EXTENSIONS = {
    "mp4",
    "webm",
    "mov",
    "m4v"
}


# ==========================================================
# IMAGE HELPERS
# ==========================================================

def allowed_image_file(filename):

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(
        ".",
        1
    )[1].lower()

    return extension in ALLOWED_IMAGE_EXTENSIONS


def image_filename_only(filename):

    if not filename:
        return ""

    value = str(filename).strip()

    value = value.replace(
        "\\",
        "/"
    )

    value = value.split(
        "?",
        1
    )[0]

    if "/static/images/" in value:

        value = value.split(
            "/static/images/",
            1
        )[1]

    elif value.startswith(
        "static/images/"
    ):

        value = value[
            len("static/images/"):
        ]

    elif value.startswith(
        "/images/"
    ):

        value = value[
            len("/images/"):
        ]

    elif value.startswith(
        "images/"
    ):

        value = value[
            len("images/"):
        ]

    return os.path.basename(
        value
    )


def product_image_url(filename):

    clean_name = image_filename_only(
        filename
    )

    if not clean_name:
        return ""

    return url_for(
        "uploaded_image",
        filename=clean_name
    )


def product_video_url(filename):

    clean_name = image_filename_only(
        filename
    )

    if not clean_name:
        return ""

    return url_for(
        "uploaded_video",
        filename=clean_name
    )


def save_product_image(file):

    if not file:
        return ""

    if not file.filename:
        return ""

    if not allowed_image_file(
        file.filename
    ):

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
        "product_"
        + secrets.token_hex(10)
        + extension
    )

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    file.save(
        file_path
    )

    return filename


def delete_product_image(filename):

    clean_name = image_filename_only(
        filename
    )

    if not clean_name:
        return

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        clean_name
    )

    try:

        if os.path.isfile(
            file_path
        ):

            os.remove(
                file_path
            )

    except OSError:

        pass


# ==========================================================
# VIDEO HELPERS
# ==========================================================

def allowed_video_file(filename):

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(
        ".",
        1
    )[1].lower()

    return extension in ALLOWED_VIDEO_EXTENSIONS


def save_product_video(file):

    if not file:
        return ""

    if not file.filename:
        return ""

    if not allowed_video_file(
        file.filename
    ):

        raise ValueError(
            "Only MP4, WEBM, MOV and M4V videos are allowed."
        )

    original_name = secure_filename(
        file.filename
    )

    extension = os.path.splitext(
        original_name
    )[1].lower()

    filename = (
        "video_"
        + secrets.token_hex(10)
        + extension
    )

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    file.save(
        file_path
    )

    return filename


def delete_product_video(filename):

    clean_name = image_filename_only(
        filename
    )

    if not clean_name:
        return

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        clean_name
    )

    try:

        if os.path.isfile(
            file_path
        ):

            os.remove(
                file_path
            )

    except OSError:

        pass


# ==========================================================
# FILE SERVING
# ==========================================================

@app.route(
    "/static/images/<path:filename>"
)
def uploaded_static_image(filename):

    filename = os.path.basename(
        filename
    )

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


@app.route(
    "/media/image/<path:filename>"
)
def uploaded_image(filename):

    filename = os.path.basename(
        filename
    )

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


@app.route(
    "/media/video/<path:filename>"
)
def uploaded_video(filename):

    filename = os.path.basename(
        filename
    )

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# ==========================================================
# DATABASE
# ==========================================================

def get_db():

    conn = sqlite3.connect(
        DATABASE,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

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

    existing_columns = {
        row["name"]
        for row in columns
    }

    if column not in existing_columns:

        conn.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN {column} {definition}
            """
        )


def init_db():

    conn = get_db()

    # ======================================================
    # PRODUCTS
    # ======================================================

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS products (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            category TEXT NOT NULL,

            price REAL NOT NULL DEFAULT 0,

            old_price REAL DEFAULT 0,

            image TEXT DEFAULT '',

            image2 TEXT DEFAULT '',

            image3 TEXT DEFAULT '',

            image4 TEXT DEFAULT '',

            image5 TEXT DEFAULT '',

            images TEXT DEFAULT '',

            video TEXT DEFAULT '',

            description TEXT DEFAULT '',

            stock INTEGER DEFAULT 0,

            featured INTEGER DEFAULT 0,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # ======================================================
    # USERS
    # ======================================================

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL,

            phone TEXT DEFAULT '',

            address TEXT DEFAULT '',

            reset_token TEXT DEFAULT '',

            reset_token_created TEXT DEFAULT '',

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # ======================================================
    # ORDERS
    # ======================================================

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            customer_name TEXT NOT NULL,

            phone TEXT NOT NULL,

            address TEXT NOT NULL,

            total REAL NOT NULL DEFAULT 0,

            status TEXT DEFAULT 'Pending',

            payment_method TEXT DEFAULT 'COD',

            email TEXT DEFAULT '',

            subtotal REAL DEFAULT 0,

            shipping REAL DEFAULT 0,

            discount REAL DEFAULT 0,

            payment_status TEXT DEFAULT 'Pending',

            razorpay_order_id TEXT DEFAULT '',

            razorpay_payment_id TEXT DEFAULT '',

            razorpay_signature TEXT DEFAULT '',

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # ======================================================
    # ORDER ITEMS
    # ======================================================

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS order_items (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            order_id INTEGER NOT NULL,

            product_id INTEGER NOT NULL,

            product_name TEXT NOT NULL,

            price REAL NOT NULL,

            quantity INTEGER NOT NULL
        )
        """
    )

    # ======================================================
    # REVIEWS
    # ======================================================

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            product_id INTEGER NOT NULL,

            name TEXT NOT NULL,

            rating INTEGER NOT NULL DEFAULT 5,

            message TEXT NOT NULL,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # ======================================================
    # COUPONS
    # ======================================================

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS coupons (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            code TEXT UNIQUE NOT NULL,

            discount REAL NOT NULL DEFAULT 0,

            active INTEGER DEFAULT 1
        )
        """
    )

    # ======================================================
    # SETTINGS
    # ======================================================

    conn.execute(
        """
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
        """
    )

    conn.execute(
        """
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
        """
    )

    # ======================================================
    # SAFE MIGRATIONS
    # ======================================================

    products_columns = [
        ("image2", "TEXT DEFAULT ''"),
        ("image3", "TEXT DEFAULT ''"),
        ("image4", "TEXT DEFAULT ''"),
        ("image5", "TEXT DEFAULT ''"),
        ("images", "TEXT DEFAULT ''"),
        ("video", "TEXT DEFAULT ''")
    ]

    for column, definition in products_columns:

        add_column_if_missing(
            conn,
            "products",
            column,
            definition
        )

    users_columns = [
        ("reset_token", "TEXT DEFAULT ''"),
        ("reset_token_created", "TEXT DEFAULT ''")
    ]

    for column, definition in users_columns:

        add_column_if_missing(
            conn,
            "users",
            column,
            definition
        )

    order_columns = [
        ("email", "TEXT DEFAULT ''"),
        ("subtotal", "REAL DEFAULT 0"),
        ("shipping", "REAL DEFAULT 0"),
        ("discount", "REAL DEFAULT 0"),
        ("payment_status", "TEXT DEFAULT 'Pending'"),
        ("razorpay_order_id", "TEXT DEFAULT ''"),
        ("razorpay_payment_id", "TEXT DEFAULT ''"),
        ("razorpay_signature", "TEXT DEFAULT ''")
    ]

    for column, definition in order_columns:

        add_column_if_missing(
            conn,
            "orders",
            column,
            definition
        )

    conn.commit()

    conn.close()


init_db()


# ==========================================================
# PASSWORD HELPERS
# ==========================================================

def hash_password(password):

    salt = secrets.token_bytes(
        16
    )

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        310000
    )

    return (
        "pbkdf2_sha256$310000$"
        + salt.hex()
        + "$"
        + digest.hex()
    )


def verify_password(
    stored_password,
    password
):

    if not stored_password:
        return False

    if stored_password.startswith(
        "pbkdf2_sha256$"
    ):

        try:

            parts = stored_password.split(
                "$"
            )

            if len(parts) != 4:
                return False

            iterations = int(
                parts[1]
            )

            salt = bytes.fromhex(
                parts[2]
            )

            expected = bytes.fromhex(
                parts[3]
            )

            actual = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt,
                iterations
            )

            return hmac.compare_digest(
                actual,
                expected
            )

        except Exception:

            return False

    return hmac.compare_digest(
        str(stored_password),
        str(password)
    )


# ==========================================================
# AUTH HELPERS
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

        if not session.get(
            "user_id"
        ):

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


def safe_next_url(target):

    if not target:
        return None

    try:

        parsed = urlparse(
            target
        )

        if parsed.scheme:
            return None

        if parsed.netloc:
            return None

        if not target.startswith("/"):
            return None

        if target.startswith("//"):
            return None

        return target

    except Exception:

        return None


# ==========================================================
# CART
# ==========================================================

def get_cart():

    cart = session.get(
        "cart",
        {}
    )

    if not isinstance(
        cart,
        dict
    ):

        return {}

    return cart


def save_cart(cart):

    clean_cart = {}

    for product_id, quantity in cart.items():

        try:

            product_id = str(
                int(product_id)
            )

            quantity = int(
                quantity
            )

            if quantity > 0:

                clean_cart[
                    product_id
                ] = quantity

        except (
            ValueError,
            TypeError
        ):

            continue

    session["cart"] = clean_cart

    session.modified = True


def cart_count():

    total = 0

    for quantity in get_cart().values():

        try:

            total += max(
                0,
                int(quantity)
            )

        except (
            ValueError,
            TypeError
        ):

            pass

    return total


# ==========================================================
# SETTINGS
# ==========================================================

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

    settings = get_settings()

    return {
        "store_settings": settings,
        "cart_count": cart_count(),
        "site_name": (
            settings["store_name"]
            if settings
            else "Majisa Jewellers"
        ),
        "site_phone": (
            settings["phone"]
            if settings
            else "8949144970"
        ),
        "site_instagram": (
            settings["instagram"]
            if settings
            else "majisa_art_jewellers"
        ),
        "razorpay_key_id": RAZORPAY_KEY_ID,
        "image_url": product_image_url,
        "video_url": product_video_url
    }


# ==========================================================
# HOME
# ==========================================================

@app.route("/")
def home():

    conn = get_db()

    products = conn.execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()

    featured = conn.execute(
        """
        SELECT *
        FROM products
        WHERE featured = 1
        ORDER BY id DESC
        LIMIT 8
        """
    ).fetchall()

    latest = conn.execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        LIMIT 12
        """
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        products=products,
        featured=featured,
        latest=latest
    )


# ==========================================================
# PRODUCTS
# ==========================================================

@app.route(
    "/products"
)
def products():

    category = request.args.get(
        "category",
        ""
    ).strip()

    search = request.args.get(
        "search",
        ""
    ).strip()

    try:

        price_max = float(
            request.args.get(
                "price_max",
                ""
            )
        )

    except (
        ValueError,
        TypeError
    ):

        price_max = None

    conn = get_db()

    query = """
        SELECT *
        FROM products
        WHERE 1 = 1
    """

    params = []

    if search:

        query += """
            AND (
                name LIKE ?
                OR category LIKE ?
                OR description LIKE ?
            )
        """

        params.extend(
            [
                f"%{search}%",
                f"%{search}%",
                f"%{search}%"
            ]
        )

    if category:

        query += """
            AND category = ?
        """

        params.append(
            category
        )

    if price_max is not None:

        query += """
            AND price <= ?
        """

        params.append(
            price_max
        )

    query += """
        ORDER BY id DESC
    """

    items = conn.execute(
        query,
        params
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
        "products.html",
        products=items,
        categories=categories,
        selected_category=category,
        selected_price_max=(
            int(price_max)
            if price_max is not None
            and float(price_max).is_integer()
            else price_max
        ),
        search=search
    )


# ==========================================================
# PRODUCT DETAIL
# ==========================================================

@app.route(
    "/product/<int:product_id>"
)
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


# ==========================================================
# SEARCH
# ==========================================================

@app.route(
    "/search"
)
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

@app.route(
    "/cart"
)
def cart():

    cart_data = get_cart()

    if not cart_data:

        return render_template(
            "cart.html",
            items=[],
            total=0
        )

    product_ids = list(
        cart_data.keys()
    )

    if not product_ids:

        return render_template(
            "cart.html",
            items=[],
            total=0
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

    valid_cart = {}

    for product in products_list:

        quantity = int(
            cart_data.get(
                str(product["id"]),
                0
            )
        )

        if quantity <= 0:
            continue

        stock = int(
            product["stock"] or 0
        )

        if stock > 0:

            quantity = min(
                quantity,
                stock
            )

        if quantity <= 0:
            continue

        valid_cart[
            str(product["id"])
        ] = quantity

        subtotal = (
            float(product["price"] or 0)
            * quantity
        )

        total += subtotal

        items.append(
            {
                "product": product,
                "quantity": quantity,
                "subtotal": subtotal
            }
        )

    save_cart(
        valid_cart
    )

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
        SELECT id, stock
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    ).fetchone()

    conn.close()

    if product is None:

        return "Product not found", 404

    cart_data = get_cart()

    key = str(
        product_id
    )

    current_quantity = int(
        cart_data.get(
            key,
            0
        )
    )

    stock = int(
        product["stock"] or 0
    )

    if stock <= 0:

        flash(
            "This product is currently out of stock."
        )

        return redirect(
            request.referrer
            or url_for("cart")
        )

    if current_quantity >= stock:

        flash(
            "Sorry, available stock limit reached."
        )

        return redirect(
            request.referrer
            or url_for("cart")
        )

    cart_data[key] = (
        current_quantity + 1
    )

    save_cart(
        cart_data
    )

    return redirect(
        request.referrer
        or url_for("cart")
    )


@app.route(
    "/cart/remove/<int:product_id>",
    methods=["POST", "GET"]
)
def remove_from_cart(product_id):

    cart_data = get_cart()

    key = str(
        product_id
    )

    if key in cart_data:

        del cart_data[key]

    save_cart(
        cart_data
    )

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

@app.route(
    "/wishlist"
)
def wishlist():

    wishlist_ids = session.get(
        "wishlist",
        []
    )

    if not isinstance(
        wishlist_ids,
        list
    ):

        wishlist_ids = []

    wishlist_ids = [
        int(item)
        for item in wishlist_ids
        if str(item).isdigit()
    ]

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

    wishlist_ids = session.get(
        "wishlist",
        []
    )

    if not isinstance(
        wishlist_ids,
        list
    ):

        wishlist_ids = []

    if product_id in wishlist_ids:

        wishlist_ids.remove(
            product_id
        )

    else:

        wishlist_ids.append(
            product_id
        )

    session["wishlist"] = wishlist_ids

    session.modified = True

    return redirect(
        request.referrer
        or url_for("wishlist")
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

        if (
            not name
            or not email
            or not password
        ):

            flash(
                "Please fill all required fields."
            )

            return redirect(
                url_for("register")
            )

        if len(password) < 6:

            flash(
                "Password must be at least 6 characters."
            )

            return redirect(
                url_for("register")
            )

        hashed_password = hash_password(
            password
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
                    hashed_password,
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
            """,
            (email,)
        ).fetchone()

        if user and verify_password(
            user["password"],
            password
        ):

            if not str(
                user["password"]
            ).startswith(
                "pbkdf2_sha256$"
            ):

                conn.execute(
                    """
                    UPDATE users
                    SET password = ?
                    WHERE id = ?
                    """,
                    (
                        hash_password(password),
                        user["id"]
                    )
                )

                conn.commit()

            conn.close()

            session.clear()

            session["user_id"] = user[
                "id"
            ]

            session["user_name"] = user[
                "name"
            ]

            next_page = safe_next_url(
                request.args.get(
                    "next"
                )
            )

            if next_page:

                return redirect(
                    next_page
                )

            return redirect(
                url_for("home")
            )

        conn.close()

        flash(
            "Invalid email or password."
        )

    return render_template(
        "login.html"
    )


# ==========================================================
# LOGOUT
# ==========================================================

@app.route(
    "/logout"
)
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
                message="Password reset link generated.",
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

    token_created = user[
        "reset_token_created"
    ]

    if token_created:

        try:

            created_timestamp = time.mktime(
                time.strptime(
                    token_created[:19],
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            if (
                time.time()
                - created_timestamp
                > 3600
            ):

                conn.execute(
                    """
                    UPDATE users
                    SET reset_token = '',
                        reset_token_created = ''
                    WHERE id = ?
                    """,
                    (user["id"],)
                )

                conn.commit()

                conn.close()

                flash(
                    "Reset link expired. Please request a new one."
                )

                return redirect(
                    url_for("forgot_password")
                )

        except Exception:
            pass

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

        if len(password) < 6:

            conn.close()

            flash(
                "Password must be at least 6 characters."
            )

            return redirect(
                url_for(
                    "reset_password",
                    token=token
                )
            )

        if password != confirm_password:

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
                reset_token = '',
                reset_token_created = ''
            WHERE id = ?
            """,
            (
                hash_password(password),
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
# CHECKOUT DATA
# ==========================================================

def get_checkout_data():

    cart_data = get_cart()

    if not cart_data:
        return None

    product_ids = list(
        cart_data.keys()
    )

    if not product_ids:
        return None

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

    settings = conn.execute(
        """
        SELECT *
        FROM settings
        WHERE id = 1
        """
    ).fetchone()

    conn.close()

    subtotal = 0

    checkout_items = []

    for product in products_list:

        quantity = int(
            cart_data.get(
                str(product["id"]),
                0
            )
        )

        stock = int(
            product["stock"] or 0
        )

        if stock <= 0:
            continue

        quantity = min(
            quantity,
            stock
        )

        if quantity <= 0:
            continue

        item_subtotal = (
            float(product["price"] or 0)
            * quantity
        )

        subtotal += item_subtotal

        checkout_items.append(
            (
                product,
                quantity
            )
        )

    shipping_charge = float(
        settings["shipping_charge"]
        or 0
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

    total = (
        subtotal
        + shipping
    )

    return {
        "products": products_list,
        "items": checkout_items,
        "settings": settings,
        "subtotal": subtotal,
        "shipping": shipping,
        "total": total
    }


# ==========================================================
# CHECKOUT
# ==========================================================

@app.route(
    "/checkout",
    methods=["GET", "POST"]
)
def checkout():

    checkout_data = get_checkout_data()

    if not checkout_data:

        return redirect(
            url_for("cart")
        )

    products_list = checkout_data[
        "products"
    ]

    checkout_items = checkout_data[
        "items"
    ]

    settings = checkout_data[
        "settings"
    ]

    subtotal = checkout_data[
        "subtotal"
    ]

    shipping = checkout_data[
        "shipping"
    ]

    total = checkout_data[
        "total"
    ]

    if not checkout_items:

        session["cart"] = {}

        session.modified = True

        flash(
            "Products in your cart are out of stock."
        )

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
        ).strip().lower()

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
        ).strip().upper()

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

        allowed_payment_methods = {
            "COD",
            "UPI",
            "RAZORPAY"
        }

        if payment_method not in (
            allowed_payment_methods
        ):

            payment_method = "COD"

        if (
            payment_method == "COD"
            and settings["cod"] != "enabled"
        ):

            flash(
                "Cash on Delivery is currently unavailable."
            )

            return redirect(
                url_for("checkout")
            )

        if (
            payment_method == "UPI"
            and settings["upi"] != "enabled"
        ):

            flash(
                "UPI payment is currently unavailable."
            )

            return redirect(
                url_for("checkout")
            )

        # --------------------------------------------------
        # RAZORPAY
        # --------------------------------------------------

        if payment_method == "RAZORPAY":

            if not get_razorpay_client():

                flash(
                    "Online payment is not configured. Please contact the store."
                )

                return redirect(
                    url_for("checkout")
                )

            conn = get_db()

            try:

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
                        "RAZORPAY",
                        email,
                        subtotal,
                        shipping,
                        0,
                        "Pending"
                    )
                )

                order_id = cursor.lastrowid

                for product, quantity in checkout_items:

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

            except Exception:

                conn.rollback()

                conn.close()

                flash(
                    "Unable to create payment order."
                )

                return redirect(
                    url_for("checkout")
                )

            conn.close()

            return render_template(
                "checkout.html",
                products=products_list,
                subtotal=subtotal,
                shipping=shipping,
                total=total,
                razorpay_order_required=True,
                pending_order_id=order_id,
                razorpay_key_id=RAZORPAY_KEY_ID
            )

        # --------------------------------------------------
        # COD / UPI
        # --------------------------------------------------

        conn = get_db()

        try:

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

            for product, quantity in checkout_items:

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

                conn.execute(
                    """
                    UPDATE products
                    SET stock = MAX(
                        stock - ?,
                        0
                    )
                    WHERE id = ?
                    """,
                    (
                        quantity,
                        product["id"]
                    )
                )

            conn.commit()

        except Exception:

            conn.rollback()

            conn.close()

            flash(
                "Unable to create your order."
            )

            return redirect(
                url_for("checkout")
            )

        conn.close()

        session["cart"] = {}

        session.modified = True

        return redirect(
            url_for(
                "order_success",
                order_id=order_id
            )
        )

    return render_template(
        "checkout.html",
        products=products_list,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        razorpay_key_id=RAZORPAY_KEY_ID,
        razorpay_order_required=False,
        pending_order_id=None
    )


# ==========================================================
# RAZORPAY CREATE ORDER
# ==========================================================

@app.route(
    "/api/payment/create-order",
    methods=["POST"]
)
def create_razorpay_order():

    client = get_razorpay_client()

    if not client:

        return jsonify(
            {
                "success": False,
                "message": "Razorpay is not configured."
            }
        ), 503

    data = request.get_json(
        silent=True
    ) or {}

    try:

        order_id = int(
            data.get(
                "order_id"
            )
        )

    except (
        ValueError,
        TypeError
    ):

        return jsonify(
            {
                "success": False,
                "message": "Invalid order ID."
            }
        ), 400

    conn = get_db()

    order = conn.execute(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()

    conn.close()

    if order is None:

        return jsonify(
            {
                "success": False,
                "message": "Order not found."
            }
        ), 404

    if (
        session.get("user_id")
        and order["user_id"] is not None
        and int(order["user_id"])
        != int(session["user_id"])
    ):

        return jsonify(
            {
                "success": False,
                "message": "Unauthorized."
            }
        ), 403

    amount_paise = int(
        round(
            float(order["total"] or 0)
            * 100
        )
    )

    if amount_paise <= 0:

        return jsonify(
            {
                "success": False,
                "message": "Invalid payment amount."
            }
        ), 400

    try:

        razorpay_order = client.order.create(
            {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"order_{order_id}",
                "notes": {
                    "website_order_id": str(
                        order_id
                    )
                }
            }
        )

    except Exception:

        app.logger.exception(
            "Razorpay order creation failed"
        )

        return jsonify(
            {
                "success": False,
                "message": "Unable to create payment order."
            }
        ), 500

    conn = get_db()

    conn.execute(
        """
        UPDATE orders
        SET razorpay_order_id = ?
        WHERE id = ?
        """,
        (
            razorpay_order["id"],
            order_id
        )
    )

    conn.commit()

    conn.close()

    return jsonify(
        {
            "success": True,
            "order_id": razorpay_order["id"],
            "website_order_id": order_id,
            "amount": amount_paise,
            "currency": "INR",
            "key_id": RAZORPAY_KEY_ID
        }
    )


# ==========================================================
# RAZORPAY VERIFY PAYMENT
# ==========================================================

@app.route(
    "/api/payment/verify",
    methods=["POST"]
)
def verify_razorpay_payment():

    if not RAZORPAY_KEY_SECRET:

        return jsonify(
            {
                "success": False,
                "message": "Payment gateway not configured."
            }
        ), 503

    data = request.get_json(
        silent=True
    ) or {}

    website_order_id = data.get(
        "website_order_id"
    )

    razorpay_order_id = data.get(
        "razorpay_order_id"
    )

    razorpay_payment_id = data.get(
        "razorpay_payment_id"
    )

    razorpay_signature = data.get(
        "razorpay_signature"
    )

    if not all(
        [
            website_order_id,
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature
        ]
    ):

        return jsonify(
            {
                "success": False,
                "message": "Incomplete payment data."
            }
        ), 400

    try:

        website_order_id = int(
            website_order_id
        )

    except (
        ValueError,
        TypeError
    ):

        return jsonify(
            {
                "success": False,
                "message": "Invalid order ID."
            }
        ), 400

    conn = get_db()

    order = conn.execute(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        """,
        (website_order_id,)
    ).fetchone()

    if order is None:

        conn.close()

        return jsonify(
            {
                "success": False,
                "message": "Order not found."
            }
        ), 404

    if (
        order["razorpay_order_id"]
        and order["razorpay_order_id"]
        != razorpay_order_id
    ):

        conn.close()

        return jsonify(
            {
                "success": False,
                "message": "Payment order mismatch."
            }
        ), 400

    message = (
        str(razorpay_order_id)
        + "|"
        + str(razorpay_payment_id)
    )

    expected_signature = hmac.new(
        RAZORPAY_KEY_SECRET.encode(
            "utf-8"
        ),
        message.encode(
            "utf-8"
        ),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(
        expected_signature,
        str(razorpay_signature)
    ):

        conn.close()

        return jsonify(
            {
                "success": False,
                "message": "Invalid payment signature."
            }
        ), 400

    if order["payment_status"] == "Paid":

        conn.close()

        session["cart"] = {}

        session.modified = True

        return jsonify(
            {
                "success": True,
                "message": "Payment already verified.",
                "order_id": website_order_id,
                "redirect_url": url_for(
                    "order_success",
                    order_id=website_order_id
                )
            }
        )

    conn.execute(
        """
        UPDATE orders
        SET
            payment_status = 'Paid',
            status = 'Confirmed',
            razorpay_payment_id = ?,
            razorpay_signature = ?,
            razorpay_order_id = ?
        WHERE id = ?
        """,
        (
            razorpay_payment_id,
            razorpay_signature,
            razorpay_order_id,
            website_order_id
        )
    )

    items = conn.execute(
        """
        SELECT product_id, quantity
        FROM order_items
        WHERE order_id = ?
        """,
        (website_order_id,)
    ).fetchall()

    for item in items:

        conn.execute(
            """
            UPDATE products
            SET stock = MAX(
                stock - ?,
                0
            )
            WHERE id = ?
            """,
            (
                item["quantity"],
                item["product_id"]
            )
        )

    conn.commit()

    conn.close()

    session["cart"] = {}

    session.modified = True

    return jsonify(
        {
            "success": True,
            "message": "Payment verified successfully.",
            "order_id": website_order_id,
            "redirect_url": url_for(
                "order_success",
                order_id=website_order_id
            )
        }
    )


# ==========================================================
# RAZORPAY PAYMENT FAILURE
# ==========================================================

@app.route(
    "/api/payment/failed",
    methods=["POST"]
)
def razorpay_payment_failed():

    data = request.get_json(
        silent=True
    ) or {}

    try:

        order_id = int(
            data.get(
                "website_order_id"
            )
        )

    except (
        ValueError,
        TypeError
    ):

        return jsonify(
            {
                "success": False
            }
        ), 400

    conn = get_db()

    conn.execute(
        """
        UPDATE orders
        SET payment_status = 'Failed'
        WHERE id = ?
        """,
        (order_id,)
    )

    conn.commit()

    conn.close()

    return jsonify(
        {
            "success": True
        }
    )


# ==========================================================
# ORDER SUCCESS
# ==========================================================

@app.route(
    "/order-success/<int:order_id>"
)
def order_success(order_id):

    conn = get_db()

    order = conn.execute(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()

    conn.close()

    if order is None:

        return "Order not found", 404

    return render_template(
        "order_success.html",
        order_id=order_id,
        order=order
    )


# ==========================================================
# CUSTOMER ORDERS
# ==========================================================

@app.route(
    "/orders"
)
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
        SELECT
            order_items.*,
            products.image AS product_image
        FROM order_items
        LEFT JOIN products
            ON products.id = order_items.product_id
        WHERE order_items.order_id = ?
        ORDER BY order_items.id
        """,
        (order_id,)
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

    except (
        ValueError,
        TypeError
    ):

        rating = 5

    rating = max(
        1,
        min(
            5,
            rating
        )
    )

    if name and message:

        conn = get_db()

        product = conn.execute(
            """
            SELECT id
            FROM products
            WHERE id = ?
            """,
            (product_id,)
        ).fetchone()

        if product:

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

@app.route(
    "/contact"
)
def contact():

    return render_template(
        "contact.html"
    )


@app.route(
    "/about"
)
def about():

    return render_template(
        "about.html"
    )


@app.route(
    "/faq"
)
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
            hmac.compare_digest(
                username,
                ADMIN_USERNAME
            )
            and
            hmac.compare_digest(
                password,
                ADMIN_PASSWORD
            )
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


@app.route(
    "/admin/logout"
)
def admin_logout():

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# ==========================================================
# ADMIN DASHBOARD
# ==========================================================

@app.route(
    "/admin/dashboard"
)
@admin_required
def admin_dashboard():

    conn = get_db()

    products_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM products
        """
    ).fetchone()[0]

    orders_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM orders
        """
    ).fetchone()[0]

    users_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM users
        """
    ).fetchone()[0]

    reviews_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM reviews
        """
    ).fetchone()[0]

    total_sales = conn.execute(
        """
        SELECT COALESCE(
            SUM(total),
            0
        )
        FROM orders
        WHERE payment_status = 'Paid'
        """
    ).fetchone()[0]

    recent_orders = conn.execute(
        """
        SELECT *
        FROM orders
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()

    products_list = conn.execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        products_count=products_count,
        orders_count=orders_count,
        users_count=users_count,
        reviews_count=reviews_count,
        total_sales=total_sales,
        recent_orders=recent_orders,
        products=products_list,
        orders=recent_orders,
        total_products=products_count,
        total_orders=orders_count,
        total_customers=users_count,
        total_users=users_count
    )


# ==========================================================
# ADMIN PRODUCTS
# ==========================================================

@app.route(
    "/admin/products"
)
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
               OR description LIKE ?
            ORDER BY id DESC
            """,
            (
                f"%{search}%",
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

    if not name:

        flash(
            "Product name is required."
        )

        return redirect(
            url_for("admin_products")
        )

    if not category:

        flash(
            "Product category is required."
        )

        return redirect(
            url_for("admin_products")
        )

    try:

        price = float(
            request.form.get(
                "price",
                0
            ) or 0
        )

    except (
        ValueError,
        TypeError
    ):

        price = 0

    try:

        old_price = float(
            request.form.get(
                "old_price",
                0
            ) or 0
        )

    except (
        ValueError,
        TypeError
    ):

        old_price = 0

    try:

        stock = int(
            request.form.get(
                "stock",
                0
            ) or 0
        )

    except (
        ValueError,
        TypeError
    ):

        stock = 0

    price = max(
        0,
        price
    )

    old_price = max(
        0,
        old_price
    )

    stock = max(
        0,
        stock
    )

    description = request.form.get(
        "description",
        ""
    ).strip()

    featured = (
        1
        if request.form.get(
            "featured"
        )
        else 0
    )

    # Support both:
    # 1) Separate inputs image/image2/.../image5
    # 2) One multiple input named images

    image_files = []

    multiple_files = request.files.getlist(
        "images"
    )

    if multiple_files:

        for image_file in multiple_files:

            if (
                image_file
                and image_file.filename
            ):

                image_files.append(
                    image_file
                )

    separate_names = [
        "image",
        "image2",
        "image3",
        "image4",
        "image5"
    ]

    for field_name in separate_names:

        image_file = request.files.get(
            field_name
        )

        if (
            image_file
            and image_file.filename
        ):

            if len(image_files) < 5:

                image_files.append(
                    image_file
                )

    image_files = image_files[:5]

    saved_images = []

    try:

        for image_file in image_files:

            saved_image = save_product_image(
                image_file
            )

            if saved_image:

                saved_images.append(
                    saved_image
                )

    except ValueError as error:

        for saved_image in saved_images:

            delete_product_image(
                saved_image
            )

        flash(
            str(error)
        )

        return redirect(
            url_for("admin_products")
        )

    image = (
        saved_images[0]
        if len(saved_images) > 0
        else ""
    )

    image2 = (
        saved_images[1]
        if len(saved_images) > 1
        else ""
    )

    image3 = (
        saved_images[2]
        if len(saved_images) > 2
        else ""
    )

    image4 = (
        saved_images[3]
        if len(saved_images) > 3
        else ""
    )

    image5 = (
        saved_images[4]
        if len(saved_images) > 4
        else ""
    )

    images = "|".join(
        saved_images
    )

    video = ""

    video_file = request.files.get(
        "video"
    )

    if (
        video_file
        and video_file.filename
    ):

        try:

            video = save_product_video(
                video_file
            )

        except ValueError as error:

            for saved_image in saved_images:

                delete_product_image(
                    saved_image
                )

            flash(
                str(error)
            )

            return redirect(
                url_for("admin_products")
            )

    conn = get_db()

    try:

        conn.execute(
            """
            INSERT INTO products
            (
                name,
                category,
                price,
                old_price,
                image,
                image2,
                image3,
                image4,
                image5,
                images,
                video,
                description,
                stock,
                featured
            )
            VALUES
            (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                name,
                category,
                price,
                old_price,
                image,
                image2,
                image3,
                image4,
                image5,
                images,
                video,
                description,
                stock,
                featured
            )
        )

        conn.commit()

    except Exception:

        conn.rollback()

        conn.close()

        for saved_image in saved_images:

            delete_product_image(
                saved_image
            )

        if video:

            delete_product_video(
                video
            )

        app.logger.exception(
            "Unable to add product"
        )

        flash(
            "Unable to add product."
        )

        return redirect(
            url_for("admin_products")
        )

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

        if not name or not category:

            flash(
                "Product name and category are required."
            )

            return redirect(
                url_for(
                    "admin_edit_product",
                    product_id=product_id
                )
            )

        try:

            price = float(
                request.form.get(
                    "price",
                    0
                ) or 0
            )

        except (
            ValueError,
            TypeError
        ):

            price = 0

        try:

            old_price = float(
                request.form.get(
                    "old_price",
                    0
                ) or 0
            )

        except (
            ValueError,
            TypeError
        ):

            old_price = 0

        try:

            stock = int(
                request.form.get(
                    "stock",
                    0
                ) or 0
            )

        except (
            ValueError,
            TypeError
        ):

            stock = 0

        price = max(
            0,
            price
        )

        old_price = max(
            0,
            old_price
        )

        stock = max(
            0,
            stock
        )

        description = request.form.get(
            "description",
            ""
        ).strip()

        featured = (
            1
            if request.form.get(
                "featured"
            )
            else 0
        )

        old_images = [
            product["image"] or "",
            product["image2"] or "",
            product["image3"] or "",
            product["image4"] or "",
            product["image5"] or ""
        ]

        all_images = list(
            old_images
        )

        # Multiple "images" field
        multiple_files = request.files.getlist(
            "images"
        )

        # Separate fields
        separate_files = [
            request.files.get("image"),
            request.files.get("image2"),
            request.files.get("image3"),
            request.files.get("image4"),
            request.files.get("image5")
        ]

        # Prefer explicit separate inputs when used.
        supplied_files = []

        has_separate = any(
            file
            and file.filename
            for file in separate_files
        )

        if has_separate:

            supplied_files = separate_files

        elif multiple_files:

            supplied_files = multiple_files[:5]

        new_images = []

        try:

            if has_separate:

                for index, image_file in enumerate(
                    supplied_files
                ):

                    if (
                        image_file
                        and image_file.filename
                    ):

                        saved_image = save_product_image(
                            image_file
                        )

                        new_images.append(
                            saved_image
                        )

                        all_images[index] = (
                            saved_image
                        )

                    else:

                        new_images.append("")

            else:

                valid_new_images = []

                for image_file in supplied_files:

                    if (
                        image_file
                        and image_file.filename
                    ):

                        saved_image = save_product_image(
                            image_file
                        )

                        valid_new_images.append(
                            saved_image
                        )

                new_images = valid_new_images

                for index, saved_image in enumerate(
                    valid_new_images[:5]
                ):

                    all_images[index] = (
                        saved_image
                    )

        except ValueError as error:

            for new_image in new_images:

                if new_image:

                    delete_product_image(
                        new_image
                    )

            flash(
                str(error)
            )

            return redirect(
                url_for(
                    "admin_edit_product",
                    product_id=product_id
                )
            )

        image = all_images[0]
        image2 = all_images[1]
        image3 = all_images[2]
        image4 = all_images[3]
        image5 = all_images[4]

        images = "|".join(
            image_name
            for image_name in all_images
            if image_name
        )

        video = product["video"] or ""

        video_file = request.files.get(
            "video"
        )

        if (
            video_file
            and video_file.filename
        ):

            try:

                new_video = save_product_video(
                    video_file
                )

                if new_video:

                    delete_product_video(
                        video
                    )

                    video = new_video

            except ValueError as error:

                for new_image in new_images:

                    if new_image:

                        delete_product_image(
                            new_image
                        )

                flash(
                    str(error)
                )

                return redirect(
                    url_for(
                        "admin_edit_product",
                        product_id=product_id
                    )
                )

        conn = get_db()

        try:

            conn.execute(
                """
                UPDATE products
                SET
                    name = ?,
                    category = ?,
                    price = ?,
                    old_price = ?,
                    image = ?,
                    image2 = ?,
                    image3 = ?,
                    image4 = ?,
                    image5 = ?,
                    images = ?,
                    video = ?,
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
                    image2,
                    image3,
                    image4,
                    image5,
                    images,
                    video,
                    description,
                    stock,
                    featured,
                    product_id
                )
            )

            conn.commit()

        except Exception:

            conn.rollback()

            conn.close()

            for new_image in new_images:

                if new_image:

                    delete_product_image(
                        new_image
                    )

            if video != (
                product["video"] or ""
            ):

                delete_product_video(
                    video
                )

            app.logger.exception(
                "Unable to update product"
            )

            flash(
                "Unable to update product."
            )

            return redirect(
                url_for(
                    "admin_edit_product",
                    product_id=product_id
                )
            )

        conn.close()

        for index, old_image in enumerate(
            old_images
        ):

            new_image = all_images[
                index
            ]

            if (
                old_image
                and old_image != new_image
            ):

                delete_product_image(
                    old_image
                )

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

    image_names = [
        product["image"],
        product["image2"],
        product["image3"],
        product["image4"],
        product["image5"]
    ]

    if product["images"]:

        image_names.extend(
            [
                img
                for img in product[
                    "images"
                ].split("|")
                if img
            ]
        )

    image_names = list(
        dict.fromkeys(
            [
                image
                for image in image_names
                if image
            ]
        )
    )

    video = product["video"]

    conn.execute(
        """
        DELETE FROM reviews
        WHERE product_id = ?
        """,
        (product_id,)
    )

    conn.execute(
        """
        DELETE FROM products
        WHERE id = ?
        """,
        (product_id,)
    )

    conn.commit()

    conn.close()

    for image_name in image_names:

        delete_product_image(
            image_name
        )

    delete_product_video(
        video
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

@app.route(
    "/admin/orders"
)
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
        SELECT
            order_items.*,
            products.name AS product_name,
            products.image AS product_image
        FROM order_items
        LEFT JOIN products
            ON products.id =
               order_items.product_id
        WHERE order_items.order_id = ?
        ORDER BY order_items.id
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

    if payment_status not in (
        allowed_payment_statuses
    ):

        payment_status = "Pending"

    conn = get_db()

    conn.execute(
        """
        UPDATE orders
        SET
            status = ?,
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
# ADMIN USERS / CUSTOMERS
# ==========================================================

@app.route(
    "/admin/users"
)
@app.route(
    "/admin/customers"
)
@admin_required
def admin_users():

    conn = get_db()

    users_list = conn.execute(
        """
        SELECT
            id,
            name,
            email,
            phone,
            address,
            created_at
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

@app.route(
    "/admin/reviews"
)
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
            ON products.id =
               reviews.product_id
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

        except (
            ValueError,
            TypeError
        ):

            shipping_charge = 0

        try:

            free_shipping = float(
                request.form.get(
                    "free_shipping",
                    999
                ) or 999
            )

        except (
            ValueError,
            TypeError
        ):

            free_shipping = 999

        shipping_charge = max(
            0,
            shipping_charge
        )

        free_shipping = max(
            0,
            free_shipping
        )

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
            SET
                store_name = ?,
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

@app.route(
    "/api/cart-count"
)
def api_cart_count():

    return jsonify(
        {
            "count": cart_count()
        }
    )


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

        return jsonify(
            {
                "success": False,
                "message": "Product not found"
            }
        ), 404

    product_data = dict(
        product
    )

    product_data[
        "image_url"
    ] = product_image_url(
        product["image"]
    )

    product_data[
        "image2_url"
    ] = product_image_url(
        product["image2"]
    )

    product_data[
        "image3_url"
    ] = product_image_url(
        product["image3"]
    )

    product_data[
        "image4_url"
    ] = product_image_url(
        product["image4"]
    )

    product_data[
        "image5_url"
    ] = product_image_url(
        product["image5"]
    )

    product_data[
        "video_url"
    ] = product_video_url(
        product["video"]
    )

    return jsonify(
        {
            "success": True,
            "product": product_data
        }
    )


# ==========================================================
# API - IMAGE URL
# ==========================================================

@app.route(
    "/api/image-url"
)
def api_image_url():

    filename = request.args.get(
        "filename",
        ""
    )

    return jsonify(
        {
            "success": True,
            "url": product_image_url(
                filename
            )
        }
    )


# ==========================================================
# HEALTH
# ==========================================================

@app.route(
    "/health"
)
def health():

    try:

        conn = get_db()

        conn.execute(
            "SELECT 1"
        ).fetchone()

        conn.close()

        return jsonify(
            {
                "status": "ok"
            }
        )

    except Exception:

        app.logger.exception(
            "Health check failed"
        )

        return jsonify(
            {
                "status": "error"
            }
        ), 500


# ==========================================================
# FAVICON
# ==========================================================

@app.route(
    "/favicon.ico"
)
def favicon():

    favicon_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        "favicon.ico"
    )

    if os.path.isfile(
        favicon_path
    ):

        return send_from_directory(
            app.config["UPLOAD_FOLDER"],
            "favicon.ico"
        )

    return "", 204


# ==========================================================
# ERROR HANDLERS
# ==========================================================

@app.errorhandler(
    404
)
def page_not_found(error):

    try:

        return render_template(
            "404.html"
        ), 404

    except Exception:

        return "Page not found", 404


@app.errorhandler(
    413
)
def file_too_large(error):

    flash(
        "Uploaded file is too large."
    )

    return redirect(
        request.referrer
        or url_for(
            "admin_products"
        )
    )


@app.errorhandler(
    500
)
def internal_server_error(error):

    app.logger.exception(
        "Internal Server Error"
    )

    # Never render a missing 500.html here.
    # Otherwise the error handler itself can crash.
    return (
        "Internal Server Error",
        500
    )


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
