import os
import sqlite3
import secrets
import hashlib
import hmac
import time
import json
import base64
from urllib.parse import urlparse, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from functools import wraps

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


# ==========================================================
# WHATSAPP CONFIG
# ==========================================================
# Set WHATSAPP_PROVIDER=meta or twilio.

WHATSAPP_PROVIDER = os.environ.get(
    "WHATSAPP_PROVIDER",
    "meta"
).strip().lower()

WHATSAPP_ADMIN_PHONE = os.environ.get(
    "WHATSAPP_ADMIN_PHONE",
    ""
).strip()

# Meta WhatsApp Cloud API
WHATSAPP_ACCESS_TOKEN = os.environ.get(
    "WHATSAPP_ACCESS_TOKEN",
    ""
).strip()

WHATSAPP_PHONE_NUMBER_ID = os.environ.get(
    "WHATSAPP_PHONE_NUMBER_ID",
    ""
).strip()

WHATSAPP_API_VERSION = os.environ.get(
    "WHATSAPP_API_VERSION",
    "v23.0"
).strip()

WHATSAPP_TEMPLATE_NAME = os.environ.get(
    "WHATSAPP_TEMPLATE_NAME",
    ""
).strip()

WHATSAPP_TEMPLATE_LANGUAGE = os.environ.get(
    "WHATSAPP_TEMPLATE_LANGUAGE",
    "en_US"
).strip()

# Twilio WhatsApp
TWILIO_ACCOUNT_SID = os.environ.get(
    "TWILIO_ACCOUNT_SID",
    ""
).strip()

TWILIO_AUTH_TOKEN = os.environ.get(
    "TWILIO_AUTH_TOKEN",
    ""
).strip()

TWILIO_WHATSAPP_FROM = os.environ.get(
    "TWILIO_WHATSAPP_FROM",
    ""
).strip()

TWILIO_CONTENT_SID = os.environ.get(
    "TWILIO_CONTENT_SID",
    ""
).strip()

TWILIO_CONTENT_VARIABLES = os.environ.get(
    "TWILIO_CONTENT_VARIABLES",
    ""
).strip()


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
# WHATSAPP HELPERS
# ==========================================================

def normalize_whatsapp_number(value):

    if not value:
        return ""

    value = str(value).strip()

    if value.lower().startswith(
        "whatsapp:"
    ):
        value = value.split(
            ":",
            1
        )[1]

    cleaned = "".join(
        ch for ch in value
        if ch.isdigit() or ch == "+"
    )

    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]

    if (
        cleaned
        and not cleaned.startswith("+")
        and len(cleaned) == 10
    ):
        cleaned = "+91" + cleaned

    return cleaned


def _http_json(
    url,
    payload,
    headers=None,
    timeout=20
):

    body = json.dumps(
        payload
    ).encode("utf-8")

    request_headers = {
        "Content-Type": "application/json"
    }

    if headers:
        request_headers.update(
            headers
        )

    req = Request(
        url,
        data=body,
        headers=request_headers,
        method="POST",
    )

    try:

        with urlopen(
            req,
            timeout=timeout
        ) as response:

            raw = response.read().decode(
                "utf-8",
                errors="replace"
            )

            try:
                data = (
                    json.loads(raw)
                    if raw
                    else {}
                )
            except json.JSONDecodeError:
                data = {
                    "raw": raw
                }

            return (
                True,
                response.status,
                data
            )

    except HTTPError as error:

        raw = error.read().decode(
            "utf-8",
            errors="replace"
        )

        try:
            data = (
                json.loads(raw)
                if raw
                else {}
            )
        except json.JSONDecodeError:
            data = {
                "raw": raw
            }

        return (
            False,
            error.code,
            data
        )

    except URLError as error:

        return (
            False,
            0,
            {
                "error": str(
                    error.reason
                )
            }
        )

    except Exception as error:

        return (
            False,
            0,
            {
                "error": str(error)
            }
        )


def _send_meta_whatsapp(
    to_number,
    body
):

    if (
        not WHATSAPP_ACCESS_TOKEN
        or not WHATSAPP_PHONE_NUMBER_ID
    ):
        return (
            False,
            "Meta WhatsApp credentials are missing."
        )

    to_number = normalize_whatsapp_number(
        to_number
    )

    if not to_number:
        return (
            False,
            "Recipient WhatsApp number is invalid."
        )

    url = (
        f"https://graph.facebook.com/"
        f"{WHATSAPP_API_VERSION}/"
        f"{WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    if WHATSAPP_TEMPLATE_NAME:

        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "template",
            "template": {
                "name": (
                    WHATSAPP_TEMPLATE_NAME
                ),
                "language": {
                    "code": (
                        WHATSAPP_TEMPLATE_LANGUAGE
                    )
                },
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {
                                "type": "text",
                                "text": body[:1024]
                            }
                        ]
                    }
                ]
            }
        }

    else:

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": body[:4096]
            }
        }

    ok, status, data = _http_json(
        url,
        payload,
        headers={
            "Authorization": (
                f"Bearer "
                f"{WHATSAPP_ACCESS_TOKEN}"
            )
        }
    )

    if ok:

        message_id = "sent"

        messages = (
            data.get("messages")
            or []
        )

        if messages:

            message_id = messages[
                0
            ].get(
                "id",
                "sent"
            )

        return (
            True,
            message_id
        )

    return (
        False,
        (
            f"Meta WhatsApp HTTP "
            f"{status}: {data}"
        )
    )


def _send_twilio_whatsapp(
    to_number,
    body
):

    if not all([
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN,
        TWILIO_WHATSAPP_FROM
    ]):

        return (
            False,
            "Twilio WhatsApp credentials are missing."
        )

    to_number = normalize_whatsapp_number(
        to_number
    )

    if not to_number:

        return (
            False,
            "Recipient WhatsApp number is invalid."
        )

    url = (
        "https://api.twilio.com/"
        "2010-04-01/Accounts/"
        f"{TWILIO_ACCOUNT_SID}/"
        "Messages.json"
    )

    from_number = (
        TWILIO_WHATSAPP_FROM
    )

    if not from_number.lower().startswith(
        "whatsapp:"
    ):

        from_number = (
            "whatsapp:"
            + from_number
        )

    form = {
        "To": (
            "whatsapp:"
            + to_number
        ),
        "From": from_number,
    }

    if TWILIO_CONTENT_SID:

        form[
            "ContentSid"
        ] = TWILIO_CONTENT_SID

        form[
            "ContentVariables"
        ] = (
            TWILIO_CONTENT_VARIABLES
            or json.dumps(
                {
                    "1": body[:1024]
                }
            )
        )

    else:

        form[
            "Body"
        ] = body[:1600]

    encoded = urlencode(
        form
    ).encode("utf-8")

    auth = base64.b64encode(
        (
            f"{TWILIO_ACCOUNT_SID}:"
            f"{TWILIO_AUTH_TOKEN}"
        ).encode("utf-8")
    ).decode("ascii")

    req = Request(
        url,
        data=encoded,
        headers={
            "Authorization": (
                f"Basic {auth}"
            ),
            "Content-Type": (
                "application/"
                "x-www-form-urlencoded"
            )
        },
        method="POST",
    )

    try:

        with urlopen(
            req,
            timeout=20
        ) as response:

            raw = response.read().decode(
                "utf-8",
                errors="replace"
            )

            data = (
                json.loads(raw)
                if raw
                else {}
            )

            return (
                True,
                data.get(
                    "sid",
                    "sent"
                )
            )

    except HTTPError as error:

        raw = error.read().decode(
            "utf-8",
            errors="replace"
        )

        try:
            data = (
                json.loads(raw)
                if raw
                else {}
            )
        except json.JSONDecodeError:
            data = {
                "raw": raw
            }

        return (
            False,
            (
                f"Twilio WhatsApp HTTP "
                f"{error.code}: {data}"
            )
        )

    except Exception as error:

        return (
            False,
            (
                "Twilio WhatsApp error: "
                f"{error}"
            )
        )


def send_whatsapp_message(
    to_number,
    body
):

    """
    Send WhatsApp notification.

    Messaging failure must never
    fail the order itself.
    """

    if not to_number or not body:
        return False

    try:

        if (
            WHATSAPP_PROVIDER
            == "twilio"
        ):

            ok, detail = (
                _send_twilio_whatsapp(
                    to_number,
                    body
                )
            )

        else:

            ok, detail = (
                _send_meta_whatsapp(
                    to_number,
                    body
                )
            )

        if ok:

            app.logger.info(
                "WhatsApp notification "
                "sent: %s",
                detail
            )

        else:

            app.logger.error(
                "WhatsApp notification "
                "failed: %s",
                detail
            )

        return ok

    except Exception:

        app.logger.exception(
            "Unexpected WhatsApp "
            "notification error"
        )

        return False


def notify_order_whatsapp(
    order_id,
    include_customer=True,
    include_admin=True,
    status=None
):

    conn = get_db()

    order = conn.execute(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()

    if order is None:

        conn.close()

        return False

    items = conn.execute(
        """
        SELECT
            order_items.*,
            products.name AS product_name
        FROM order_items
        LEFT JOIN products
            ON products.id =
               order_items.product_id
        WHERE order_items.order_id = ?
        ORDER BY order_items.id ASC
        """,
        (order_id,)
    ).fetchall()

    conn.close()

    customer_phone = (
        order["phone"]
        if "phone" in order.keys()
        else ""
    )

    customer_name = (
        order["name"]
        if "name" in order.keys()
        else "Customer"
    )

    order_status = (
        status
        or (
            order["status"]
            if "status" in order.keys()
            else "Pending"
        )
    )

    lines = [
        "🛍️ MAJISA ORDER",
        "",
        f"Order ID: #{order_id}",
        f"Customer: {customer_name}",
        f"Status: {order_status}",
    ]

    if "payment_method" in order.keys():

        lines.append(
            "Payment: "
            + str(
                order["payment_method"]
                or "-"
            )
        )

    if items:

        lines.append("")
        lines.append("Items:")

        for item in items:

            product_name = (
                item["product_name"]
                or "Product"
            )

            quantity = (
                item["quantity"]
                if "quantity"
                in item.keys()
                else 1
            )

            price = (
                item["price"]
                if "price"
                in item.keys()
                else 0
            )

            lines.append(
                f"- {product_name} "
                f"x {quantity} "
                f"₹{float(price):.2f}"
            )

    total_value = (
        order["total"]
        if "total" in order.keys()
        else 0
    )

    lines.extend([
        "",
        f"Total: ₹{float(total_value):.2f}",
    ])

    if "address" in order.keys():

        address = (
            order["address"]
            or ""
        ).strip()

        if address:

            lines.extend([
                "",
                "Address:",
                address
            ])

    customer_message = "\n".join(
        lines
    )

    sent_any = False

    if (
        include_customer
        and customer_phone
    ):

        sent_any = (
            send_whatsapp_message(
                customer_phone,
                customer_message
            )
            or sent_any
        )

    if (
        include_admin
        and WHATSAPP_ADMIN_PHONE
    ):

        admin_message = (
            "🔔 NEW/UPDATED ORDER\n\n"
            + customer_message
        )

        sent_any = (
            send_whatsapp_message(
                WHATSAPP_ADMIN_PHONE,
                admin_message
            )
            or sent_any
        )

    return sent_any


# ==========================================================
# DATABASE
# ==========================================================

def get_db():

    conn = sqlite3.connect(
        DATABASE
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    conn = get_db()

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            password TEXT,
            address TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT,
            description TEXT,
            price REAL DEFAULT 0,
            old_price REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            category TEXT,
            image TEXT,
            image2 TEXT,
            image3 TEXT,
            image4 TEXT,
            image5 TEXT,
            video TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            city TEXT,
            pincode TEXT,
            total REAL DEFAULT 0,
            payment_method TEXT,
            payment_status TEXT,
            status TEXT DEFAULT 'Pending',
            razorpay_order_id TEXT,
            razorpay_payment_id TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER DEFAULT 1,
            price REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            user_id INTEGER,
            name TEXT,
            rating INTEGER DEFAULT 5,
            comment TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            store_name TEXT DEFAULT 'MAJISA',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            instagram TEXT DEFAULT '',
            address TEXT DEFAULT '',
            city TEXT DEFAULT '',
            pincode TEXT DEFAULT '',
            business_hours TEXT DEFAULT '',
            currency TEXT DEFAULT 'INR',
            cod TEXT DEFAULT 'enabled',
            upi TEXT DEFAULT 'enabled',
            shipping_charge REAL DEFAULT 0,
            free_shipping REAL DEFAULT 999,
            delivery_time TEXT DEFAULT '5-7 business days',
            store_status TEXT DEFAULT 'open',
            maintenance_message TEXT DEFAULT ''
        );
        """
    )

    existing_settings = conn.execute(
        """
        SELECT id
        FROM settings
        WHERE id = 1
        """
    ).fetchone()

    if existing_settings is None:

        conn.execute(
            """
            INSERT INTO settings (
                id,
                store_name,
                currency,
                cod,
                upi,
                shipping_charge,
                free_shipping,
                delivery_time,
                store_status
            )
            VALUES (
                1,
                'MAJISA',
                'INR',
                'enabled',
                'enabled',
                0,
                999,
                '5-7 business days',
                'open'
            )
            """
        )

    conn.commit()

    conn.close()


init_db()


# ==========================================================
# AUTH HELPERS
# ==========================================================

def hash_password(password):

    salt = secrets.token_hex(
        16
    )

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120000
    )

    return (
        salt
        + "$"
        + digest.hex()
    )


def verify_password(
    password,
    stored
):

    if not stored:
        return False

    if "$" not in stored:
        return hmac.compare_digest(
            password,
            stored
        )

    salt, expected = (
        stored.split(
            "$",
            1
        )
    )

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120000
    ).hex()

    return hmac.compare_digest(
        digest,
        expected
    )


def admin_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if not session.get(
            "admin_logged_in"
        ):

            return redirect(
                url_for(
                    "admin_login"
                )
            )

        return func(
            *args,
            **kwargs
        )

    return wrapper


def user_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if not session.get(
            "user_id"
        ):

            return redirect(
                url_for(
                    "login"
                )
            )

        return func(
            *args,
            **kwargs
        )

    return wrapper


# ==========================================================
# GENERAL HELPERS
# ==========================================================

def now_string():

    return time.strftime(
        "%Y-%m-%d %H:%M:%S"
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


def cart_items():

    cart = session.get(
        "cart",
        {}
    )

    if not cart:
        return []

    conn = get_db()

    result = []

    for product_id, quantity in cart.items():

        try:
            product_id_int = int(
                product_id
            )
        except (
            TypeError,
            ValueError
        ):
            continue

        product = conn.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
            AND active = 1
            """,
            (product_id_int,)
        ).fetchone()

        if product is None:
            continue

        try:
            quantity_int = max(
                1,
                int(quantity)
            )
        except (
            TypeError,
            ValueError
        ):
            quantity_int = 1

        result.append(
            {
                "product": product,
                "quantity": quantity_int,
                "subtotal": (
                    float(
                        product["price"]
                    )
                    * quantity_int
                )
            }
        )

    conn.close()

    return result


def cart_count():

    total = 0

    for item in cart_items():

        total += item[
            "quantity"
        ]

    return total


def cart_total():

    total = 0

    for item in cart_items():

        total += item[
            "subtotal"
        ]

    return round(
        total,
        2
    )


def clear_cart():

    session[
        "cart"
    ] = {}

    session.modified = True


def product_image_url(
    filename
):

    if not filename:
        return ""

    filename = str(
        filename
    ).strip()

    if not filename:
        return ""

    return url_for(
        "static",
        filename=(
            "images/"
            + filename
        )
    )


def product_video_url(
    filename
):

    if not filename:
        return ""

    filename = str(
        filename
    ).strip()

    if not filename:
        return ""

    return url_for(
        "static",
        filename=(
            "images/"
            + filename
        )
    )


def slugify(value):

    value = str(
        value or ""
    ).strip().lower()

    result = []

    for char in value:

        if (
            char.isalnum()
            or char in (
                "-",
                "_"
            )
        ):

            result.append(
                char
            )

        elif char.isspace():

            result.append("-")

    slug = "".join(
        result
    )

    while "--" in slug:

        slug = slug.replace(
            "--",
            "-"
        )

    return slug.strip(
        "-"
    )


def unique_slug(
    conn,
    value,
    exclude_id=None
):

    base = slugify(
        value
    ) or "product"

    slug = base

    counter = 2

    while True:

        if exclude_id is None:

            row = conn.execute(
                """
                SELECT id
                FROM products
                WHERE slug = ?
                """,
                (slug,)
            ).fetchone()

        else:

            row = conn.execute(
                """
                SELECT id
                FROM products
                WHERE slug = ?
                AND id != ?
                """,
                (
                    slug,
                    exclude_id
                )
            ).fetchone()

        if row is None:
            return slug

        slug = (
            f"{base}-{counter}"
        )

        counter += 1


def save_uploaded_file(
    file
):

    if not file:
        return ""

    if not file.filename:
        return ""

    filename = secure_filename(
        file.filename
    )

    if not filename:
        return ""

    unique_name = (
        f"{int(time.time())}_"
        f"{secrets.token_hex(4)}_"
        f"{filename}"
    )

    path = os.path.join(
        app.config[
            "UPLOAD_FOLDER"
        ],
        unique_name
    )

    file.save(
        path
    )

    return unique_name


# ==========================================================
# CONTEXT
# ==========================================================

@app.context_processor
def inject_globals():

    return {
        "settings": get_settings(),
        "cart_count": cart_count(),
        "cart_total": cart_total(),
        "current_user_id": session.get(
            "user_id"
        ),
        "admin_logged_in": session.get(
            "admin_logged_in",
            False
        )
    }


# ==========================================================
# HOME
# ==========================================================

@app.route("/")
def index():

    conn = get_db()

    products = conn.execute(
        """
        SELECT *
        FROM products
        WHERE active = 1
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        products=products
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

    query = """
        SELECT *
        FROM products
        WHERE active = 1
    """

    params = []

    if category:

        query += """
            AND category = ?
        """

        params.append(
            category
        )

    if search:

        query += """
            AND (
                name LIKE ?
                OR description LIKE ?
                OR category LIKE ?
            )
        """

        search_value = (
            "%"
            + search
            + "%"
        )

        params.extend(
            [
                search_value,
                search_value,
                search_value
            ]
        )

    query += """
        ORDER BY id DESC
    """

    products_list = conn.execute(
        query,
        params
    ).fetchall()

    categories = conn.execute(
        """
        SELECT DISTINCT category
        FROM products
        WHERE active = 1
        AND category IS NOT NULL
        AND category != ''
        ORDER BY category
        """
    ).fetchall()

    conn.close()

    return render_template(
        "products.html",
        products=products_list,
        categories=categories,
        selected_category=category,
        search=search
    )


@app.route(
    "/product/<int:product_id>"
)
def product_detail(
    product_id
):

    conn = get_db()

    product = conn.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        AND active = 1
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

        return render_template(
            "404.html"
        ), 404

    return render_template(
        "product_detail.html",
        product=product,
        reviews=reviews
    )


# ==========================================================
# CART
# ==========================================================

@app.route("/cart")
def cart():

    items = cart_items()

    return render_template(
        "cart.html",
        items=items,
        total=cart_total()
    )


@app.route(
    "/cart/add/<int:product_id>",
    methods=["POST", "GET"]
)
def add_to_cart(
    product_id
):

    conn = get_db()

    product = conn.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        AND active = 1
        """,
        (product_id,)
    ).fetchone()

    conn.close()

    if product is None:

        flash(
            "Product not found."
        )

        return redirect(
            request.referrer
            or url_for("products")
        )

    cart = session.get(
        "cart",
        {}
    )

    key = str(
        product_id
    )

    current_quantity = cart.get(
        key,
        0
    )

    try:
        current_quantity = int(
            current_quantity
        )
    except (
        TypeError,
        ValueError
    ):
        current_quantity = 0

    requested_quantity = request.form.get(
        "quantity",
        1
    )

    try:
        requested_quantity = int(
            requested_quantity
        )
    except (
        TypeError,
        ValueError
    ):
        requested_quantity = 1

    requested_quantity = max(
        1,
        requested_quantity
    )

    stock = int(
        product["stock"]
        or 0
    )

    new_quantity = (
        current_quantity
        + requested_quantity
    )

    if stock > 0:

        new_quantity = min(
            new_quantity,
            stock
        )

    cart[key] = new_quantity

    session[
        "cart"
    ] = cart

    session.modified = True

    flash(
        "Product added to cart."
    )

    next_url = request.form.get(
        "next"
    ) or request.args.get(
        "next"
    )

    if next_url:

        return redirect(
            next_url
        )

    return redirect(
        request.referrer
        or url_for("cart")
    )


@app.route(
    "/cart/update",
    methods=["POST"]
)
def update_cart():

    cart = session.get(
        "cart",
        {}
    )

    for key in list(
        cart.keys()
    ):

        value = request.form.get(
            f"quantity_{key}"
        )

        if value is None:
            continue

        try:
            quantity = int(
                value
            )
        except (
            TypeError,
            ValueError
        ):
            quantity = 0

        if quantity <= 0:

            cart.pop(
                key,
                None
            )

        else:

            cart[key] = quantity

    session[
        "cart"
    ] = cart

    session.modified = True

    flash(
        "Cart updated."
    )

    return redirect(
        url_for("cart")
    )


@app.route(
    "/cart/remove/<int:product_id>",
    methods=["POST", "GET"]
)
def remove_from_cart(
    product_id
):

    cart = session.get(
        "cart",
        {}
    )

    cart.pop(
        str(product_id),
        None
    )

    session[
        "cart"
    ] = cart

    session.modified = True

    flash(
        "Product removed from cart."
    )

    return redirect(
        url_for("cart")
    )


@app.route(
    "/cart/clear",
    methods=["POST", "GET"]
)
def clear_cart_route():

    clear_cart()

    flash(
        "Cart cleared."
    )

    return redirect(
        url_for("cart")
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
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        address = request.form.get(
            "address",
            ""
        ).strip()

        if not name:

            flash(
                "Name is required."
            )

            return redirect(
                url_for("register")
            )

        if not password:

            flash(
                "Password is required."
            )

            return redirect(
                url_for("register")
            )

        if password != confirm_password:

            flash(
                "Passwords do not match."
            )

            return redirect(
                url_for("register")
            )

        conn = get_db()

        existing = conn.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if existing:

            conn.close()

            flash(
                "Email is already registered."
            )

            return redirect(
                url_for("register")
            )

        conn.execute(
            """
            INSERT INTO users (
                name,
                email,
                phone,
                password,
                address,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?
            )
            """,
            (
                name,
                email,
                phone,
                hash_password(
                    password
                ),
                address,
                now_string()
            )
        )

        conn.commit()

        user_id = conn.execute(
            """
            SELECT last_insert_rowid()
            """
        ).fetchone()[0]

        conn.close()

        session[
            "user_id"
        ] = user_id

        session[
            "user_name"
        ] = name

        flash(
            "Registration successful."
        )

        return redirect(
            url_for("index")
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
        ).strip()

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

        conn.close()

        if (
            user
            and verify_password(
                password,
                user["password"]
            )
        ):

            session[
                "user_id"
            ] = user["id"]

            session[
                "user_name"
            ] = user["name"]

            flash(
                "Login successful."
            )

            return redirect(
                request.args.get(
                    "next"
                )
                or url_for("index")
            )

        flash(
            "Invalid email or password."
        )

    return render_template(
        "login.html"
    )


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

    flash(
        "You have been logged out."
    )

    return redirect(
        url_for("index")
    )


# ==========================================================
# PROFILE
# ==========================================================

@app.route(
    "/profile",
    methods=["GET", "POST"]
)
@user_required
def profile():

    user_id = session.get(
        "user_id"
    )

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    if user is None:

        conn.close()

        session.pop(
            "user_id",
            None
        )

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        name = request.form.get(
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

        conn.execute(
            """
            UPDATE users
            SET
                name = ?,
                email = ?,
                phone = ?,
                address = ?
            WHERE id = ?
            """,
            (
                name,
                email,
                phone,
                address,
                user_id
            )
        )

        conn.commit()

        session[
            "user_name"
        ] = name

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        flash(
            "Profile updated successfully."
        )

    conn.close()

    return render_template(
        "profile.html",
        user=user
    )


# ==========================================================
# CHECKOUT
# ==========================================================

@app.route("/checkout")
def checkout():

    items = cart_items()

    if not items:

        flash(
            "Your cart is empty."
        )

        return redirect(
            url_for("products")
        )

    settings = get_settings()

    subtotal = cart_total()

    shipping_charge = float(
        settings["shipping_charge"]
        or 0
    )

    free_shipping = float(
        settings["free_shipping"]
        or 0
    )

    if (
        free_shipping > 0
        and subtotal >= free_shipping
    ):

        shipping_charge = 0

    total = round(
        subtotal
        + shipping_charge,
        2
    )

    user = None

    if session.get(
        "user_id"
    ):

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (
                session[
                    "user_id"
                ],
            )
        ).fetchone()

        conn.close()

    return render_template(
        "checkout.html",
        items=items,
        subtotal=subtotal,
        shipping_charge=shipping_charge,
        total=total,
        user=user,
        settings=settings
    )


# ==========================================================
# CREATE ORDER
# ==========================================================

@app.route(
    "/create-order",
    methods=["POST"]
)
def create_order():

    items = cart_items()

    if not items:

        return jsonify(
            {
                "success": False,
                "message": (
                    "Your cart is empty."
                )
            }
        ), 400

    name = request.form.get(
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

    city = request.form.get(
        "city",
        ""
    ).strip()

    pincode = request.form.get(
        "pincode",
        ""
    ).strip()

    payment_method = request.form.get(
        "payment_method",
        "cod"
    ).strip().lower()

    if not name:

        return jsonify(
            {
                "success": False,
                "message": (
                    "Name is required."
                )
            }
        ), 400

    if not phone:

        return jsonify(
            {
                "success": False,
                "message": (
                    "Phone number is required."
                )
            }
        ), 400

    settings = get_settings()

    subtotal = cart_total()

    shipping_charge = float(
        settings["shipping_charge"]
        or 0
    )

    free_shipping = float(
        settings["free_shipping"]
        or 0
    )

    if (
        free_shipping > 0
        and subtotal >= free_shipping
    ):

        shipping_charge = 0

    total = round(
        subtotal
        + shipping_charge,
        2
    )

    if (
        payment_method == "cod"
        and settings["cod"] != "enabled"
    ):

        return jsonify(
            {
                "success": False,
                "message": (
                    "Cash on Delivery is disabled."
                )
            }
        ), 400

    if (
        payment_method in (
            "upi",
            "razorpay"
        )
        and settings["upi"] != "enabled"
    ):

        return jsonify(
            {
                "success": False,
                "message": (
                    "Online payment is disabled."
                )
            }
        ), 400

    conn = get_db()

    user_id = session.get(
        "user_id"
    )

    payment_status = (
        "Pending"
        if payment_method
        in (
            "upi",
            "razorpay"
        )
        else "Pending"
    )

    order_status = (
        "Pending"
    )

    conn.execute(
        """
        INSERT INTO orders (
            user_id,
            name,
            email,
            phone,
            address,
            city,
            pincode,
            total,
            payment_method,
            payment_status,
            status,
            created_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?
        )
        """,
        (
            user_id,
            name,
            email,
            phone,
            address,
            city,
            pincode,
            total,
            payment_method,
            payment_status,
            order_status,
            now_string()
        )
    )

    order_id = conn.execute(
        """
        SELECT last_insert_rowid()
        """
    ).fetchone()[0]

    for item in items:

        product = item[
            "product"
        ]

        quantity = item[
            "quantity"
        ]

        price = float(
            product["price"]
            or 0
        )

        conn.execute(
            """
            INSERT INTO order_items (
                order_id,
                product_id,
                quantity,
                price
            )
            VALUES (
                ?, ?, ?, ?
            )
            """,
            (
                order_id,
                product["id"],
                quantity,
                price
            )
        )

        if int(
            product["stock"]
            or 0
        ) > 0:

            conn.execute(
                """
                UPDATE products
                SET stock =
                    CASE
                        WHEN stock >= ?
                        THEN stock - ?
                        ELSE 0
                    END
                WHERE id = ?
                """,
                (
                    quantity,
                    quantity,
                    product["id"]
                )
            )

    conn.commit()

    conn.close()

    # Send customer + admin notification.
    # Notification failure never cancels
    # the order.
    notify_order_whatsapp(
        order_id,
        include_customer=True,
        include_admin=True,
        status=order_status
    )

    if payment_method in (
        "upi",
        "razorpay"
    ):

        client = (
            get_razorpay_client()
        )

        if client is None:

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Razorpay is not configured."
                    ),
                    "order_id": order_id
                }
            ), 500

        try:

            razorpay_order = (
                client.order.create(
                    {
                        "amount": int(
                            round(
                                total * 100
                            )
                        ),
                        "currency": "INR",
                        "receipt": (
                            f"order_{order_id}"
                        ),
                        "notes": {
                            "order_id": str(
                                order_id
                            )
                        }
                    }
                )
            )

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
                    "payment_required": True,
                    "order_id": order_id,
                    "razorpay_order_id": (
                        razorpay_order["id"]
                    ),
                    "amount": int(
                        round(
                            total * 100
                        )
                    ),
                    "key_id": (
                        RAZORPAY_KEY_ID
                    )
                }
            )

        except Exception as error:

            app.logger.exception(
                "Razorpay order creation failed"
            )

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Unable to create "
                        "payment order."
                    ),
                    "error": str(
                        error
                    ),
                    "order_id": order_id
                }
            ), 500

    clear_cart()

    return jsonify(
        {
            "success": True,
            "payment_required": False,
            "order_id": order_id,
            "redirect": url_for(
                "order_success",
                order_id=order_id
            )
        }
    )


# ==========================================================
# RAZORPAY VERIFY
# ==========================================================

@app.route(
    "/razorpay/verify",
    methods=["POST"]
)
def razorpay_verify():

    data = request.get_json(
        silent=True
    ) or request.form

    order_id = data.get(
        "order_id"
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

    if not all([
        order_id,
        razorpay_order_id,
        razorpay_payment_id,
        razorpay_signature
    ]):

        return jsonify(
            {
                "success": False,
                "message": (
                    "Missing payment details."
                )
            }
        ), 400

    client = get_razorpay_client()

    if client is None:

        return jsonify(
            {
                "success": False,
                "message": (
                    "Razorpay is not configured."
                )
            }
        ), 500

    try:

        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": (
                    razorpay_order_id
                ),
                "razorpay_payment_id": (
                    razorpay_payment_id
                ),
                "razorpay_signature": (
                    razorpay_signature
                )
            }
        )

    except Exception:

        app.logger.exception(
            "Razorpay signature verification failed"
        )

        return jsonify(
            {
                "success": False,
                "message": (
                    "Payment verification failed."
                )
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

    if order is None:

        conn.close()

        return jsonify(
            {
                "success": False,
                "message": (
                    "Order not found."
                )
            }
        ), 404

    conn.execute(
        """
        UPDATE orders
        SET
            razorpay_order_id = ?,
            razorpay_payment_id = ?,
            payment_status = 'Paid',
            status = 'Confirmed'
        WHERE id = ?
        """,
        (
            razorpay_order_id,
            razorpay_payment_id,
            order_id
        )
    )

    conn.commit()

    conn.close()

    clear_cart()

    # Notify customer that payment/order
    # is confirmed.
    notify_order_whatsapp(
        order_id,
        include_customer=True,
        include_admin=True,
        status="Confirmed"
    )

    return jsonify(
        {
            "success": True,
            "redirect": url_for(
                "order_success",
                order_id=order_id
            )
        }
    )


# ==========================================================
# ORDER SUCCESS
# ==========================================================

@app.route(
    "/order-success/<int:order_id>"
)
def order_success(
    order_id
):

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

        return render_template(
            "404.html"
        ), 404

    return render_template(
        "order_success.html",
        order=order,
        items=items
    )


# ==========================================================
# MY ORDERS
# ==========================================================

@app.route("/orders")
@user_required
def my_orders():

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
def order_detail(
    order_id
):

    conn = get_db()

    order = conn.execute(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()

    if order is None:

        conn.close()

        return render_template(
            "404.html"
        ), 404

    user_id = session.get(
        "user_id"
    )

    if (
        not session.get(
            "admin_logged_in"
        )
        and (
            not user_id
            or order["user_id"]
            != user_id
        )
    ):

        conn.close()

        return (
            "Unauthorized",
            403
        )

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

    return render_template(
        "order_detail.html",
        order=order,
        items=items
    )


# ==========================================================
# REVIEW
# ==========================================================

@app.route(
    "/review/<int:product_id>",
    methods=["POST"]
)
@user_required
def add_review(
    product_id
):

    user_id = session.get(
        "user_id"
    )

    rating = request.form.get(
        "rating",
        5
    )

    comment = request.form.get(
        "comment",
        ""
    ).strip()

    try:
        rating = int(
            rating
        )
    except (
        TypeError,
        ValueError
    ):
        rating = 5

    rating = max(
        1,
        min(
            5,
            rating
        )
    )

    conn = get_db()

    user = conn.execute(
        """
        SELECT name
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    if user is None:

        conn.close()

        return redirect(
            url_for(
                "login"
            )
        )

    conn.execute(
        """
        INSERT INTO reviews (
            product_id,
            user_id,
            name,
            rating,
            comment,
            created_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?
        )
        """,
        (
            product_id,
            user_id,
            user["name"],
            rating,
            comment,
            now_string()
        )
    )

    conn.commit()

    conn.close()

    flash(
        "Review submitted successfully."
    )

    return redirect(
        url_for(
            "product_detail",
            product_id=product_id
        )
    )


# ==========================================================
# ADMIN LOGIN
# ==========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

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
            and hmac.compare_digest(
                password,
                ADMIN_PASSWORD
            )
        ):

            session[
                "admin_logged_in"
            ] = True

            flash(
                "Admin login successful."
            )

            return redirect(
                url_for(
                    "admin_dashboard"
                )
            )

        flash(
            "Invalid admin credentials."
        )

    return render_template(
        "admin_login.html"
    )


@app.route(
    "/admin/logout"
)
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )

    flash(
        "Admin logged out."
    )

    return redirect(
        url_for(
            "admin_login"
        )
    )


# ==========================================================
# ADMIN DASHBOARD
# ==========================================================

@app.route(
    "/admin"
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

    conn.close()

    return render_template(
        "admin_dashboard.html",
        products_count=products_count,
        orders_count=orders_count,
        users_count=users_count,
        reviews_count=reviews_count,
        total_sales=total_sales,
        recent_orders=recent_orders
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

    image_files = [
        request.files.get("image"),
        request.files.get("image2"),
        request.files.get("image3"),
        request.files.get("image4"),
        request.files.get("image5")
    ]

    saved_images = []

    try:

        for image_file in image_files:

            if (
                image_file
                and image_file.filename
            ):

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

        new_image_files = [
            request.files.get("image"),
            request.files.get("image2"),
            request.files.get("image3"),
            request.files.get("image4"),
            request.files.get("image5")
        ]

        new_images = []

        try:

            for index, image_file in enumerate(
                new_image_files
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

        for img in product[
            "images"
        ].split("|"):

            if img:

                image_names.append(
                    img
                )

    image_names = list(
        dict.fromkeys(
            image_names
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
def admin_order_detail(
    order_id
):

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
def admin_update_order(
    order_id
):

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

    notify_order_whatsapp(
        order_id,
        include_customer=True,
        include_admin=True,
        status=status
    )

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

@app.route(
    "/admin/users"
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
def admin_delete_review(
    review_id
):

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

    return jsonify(
        {
            "status": "ok"
        }
    )


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

    return render_template(
        "404.html"
    ), 404


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
