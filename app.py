from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "billing.db"
app = Flask(__name__)
app.secret_key = "change-this-secret-key-before-deployment"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sku TEXT NOT NULL UNIQUE,
            price REAL NOT NULL CHECK(price >= 0),
            stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT NOT NULL UNIQUE,
            customer_name TEXT NOT NULL,
            customer_phone TEXT DEFAULT '',
            subtotal REAL NOT NULL,
            tax_rate REAL NOT NULL DEFAULT 0,
            tax_amount REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            product_name TEXT NOT NULL,
            sku TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            line_total REAL NOT NULL
        );
        """)
        count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            now = datetime.now().isoformat(timespec="seconds")
            db.executemany(
                "INSERT INTO products(name, sku, price, stock, created_at) VALUES(?,?,?,?,?)",
                [
                    ("Notebook", "ST-001", 45.00, 100, now),
                    ("Blue Pen", "ST-002", 10.00, 250, now),
                    ("USB Drive 32GB", "EL-001", 399.00, 30, now),
                    ("Water Bottle", "HM-001", 199.00, 45, now),
                ],
            )

@app.template_filter("money")
def money(value):
    return "₹{:,.2f}".format(float(value or 0))

@app.route("/")
def dashboard():
    with get_db() as db:
        product_count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        invoice_count = db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        revenue = db.execute("SELECT COALESCE(SUM(total), 0) FROM invoices").fetchone()[0]
        low_stock = db.execute("SELECT COUNT(*) FROM products WHERE stock <= 5").fetchone()[0]
        recent = db.execute("SELECT * FROM invoices ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("dashboard.html", product_count=product_count,
                           invoice_count=invoice_count, revenue=revenue,
                           low_stock=low_stock, recent=recent)

@app.route("/products", methods=["GET", "POST"])
def products():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sku = request.form.get("sku", "").strip().upper()
        try:
            price = float(request.form.get("price", ""))
            stock = int(request.form.get("stock", ""))
            if not name or not sku or price < 0 or stock < 0:
                raise ValueError
        except (ValueError, TypeError):
            flash("Enter a product name, SKU, non-negative price, and whole-number stock.", "error")
            return redirect(url_for("products"))
        try:
            with get_db() as db:
                db.execute("INSERT INTO products(name, sku, price, stock, created_at) VALUES(?,?,?,?,?)",
                           (name, sku, price, stock, datetime.now().isoformat(timespec="seconds")))
            flash("Product added successfully.", "success")
        except sqlite3.IntegrityError:
            flash("Product name and SKU must both be unique.", "error")
        return redirect(url_for("products"))
    with get_db() as db:
        items = db.execute("SELECT * FROM products ORDER BY name").fetchall()
    return render_template("products.html", products=items)

@app.route("/products/<int:product_id>/delete", methods=["POST"])
def delete_product(product_id):
    with get_db() as db:
        used = db.execute("SELECT COUNT(*) FROM invoice_items WHERE product_id=?", (product_id,)).fetchone()[0]
        if used:
            flash("This product appears on an invoice and cannot be deleted. Set its stock to zero instead.", "error")
        else:
            db.execute("DELETE FROM products WHERE id=?", (product_id,))
            flash("Product deleted.", "success")
    return redirect(url_for("products"))

@app.route("/api/products")
def products_api():
    with get_db() as db:
        rows = db.execute("SELECT id, name, sku, price, stock FROM products WHERE stock > 0 ORDER BY name").fetchall()
    return jsonify([dict(row) for row in rows])

@app.route("/billing", methods=["GET", "POST"])
def billing():
    if request.method == "POST":
        customer = request.form.get("customer_name", "").strip()
        phone = request.form.get("customer_phone", "").strip()
        try:
            tax_rate = Decimal(request.form.get("tax_rate", "0"))
            if tax_rate < 0 or tax_rate > 100:
                raise ValueError
        except (InvalidOperation, ValueError):
            flash("Tax rate must be between 0 and 100.", "error")
            return redirect(url_for("billing"))

        try:
            cart = __import__("json").loads(request.form.get("cart_json", "[]"))
            if not customer or not isinstance(cart, list) or not cart:
                raise ValueError
            with get_db() as db:
                db.execute("BEGIN IMMEDIATE")
                items = []
                subtotal = Decimal("0.00")
                for entry in cart:
                    product_id = int(entry["product_id"])
                    quantity = int(entry["quantity"])
                    if quantity < 1:
                        raise ValueError
                    product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
                    if product is None or product["stock"] < quantity:
                        raise ValueError
                    price = Decimal(str(product["price"]))
                    line_total = price * quantity
                    subtotal += line_total
                    items.append((product, quantity, price, line_total))
                tax_amount = (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
                total = subtotal + tax_amount
                now = datetime.now()
                invoice_no = "INV-" + now.strftime("%Y%m%d-%H%M%S") + "-" + str(now.microsecond // 1000).zfill(3)
                cursor = db.execute(
                    "INSERT INTO invoices(invoice_no, customer_name, customer_phone, subtotal, tax_rate, tax_amount, total, created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (invoice_no, customer, phone, float(subtotal), float(tax_rate), float(tax_amount), float(total), now.isoformat(timespec="seconds"))
                )
                invoice_id = cursor.lastrowid
                for product, quantity, price, line_total in items:
                    db.execute("INSERT INTO invoice_items(invoice_id, product_id, product_name, sku, quantity, unit_price, line_total) VALUES(?,?,?,?,?,?,?)",
                               (invoice_id, product["id"], product["name"], product["sku"], quantity, float(price), float(line_total)))
                    db.execute("UPDATE products SET stock=stock-? WHERE id=?", (quantity, product["id"]))
            flash("Invoice created successfully.", "success")
            return redirect(url_for("invoice_detail", invoice_id=invoice_id))
        except (ValueError, KeyError, TypeError, __import__("json").JSONDecodeError):
            flash("Could not create bill. Check the customer, cart quantities, and available stock.", "error")
            return redirect(url_for("billing"))
    with get_db() as db:
        items = db.execute("SELECT * FROM products WHERE stock > 0 ORDER BY name").fetchall()
    return render_template("billing.html", products=items)

@app.route("/invoices")
def invoices():
    with get_db() as db:
        rows = db.execute("SELECT * FROM invoices ORDER BY id DESC").fetchall()
    return render_template("invoices.html", invoices=rows)

@app.route("/invoices/<int:invoice_id>")
def invoice_detail(invoice_id):
    with get_db() as db:
        invoice = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if invoice is None:
            flash("Invoice not found.", "error")
            return redirect(url_for("invoices"))
        items = db.execute("SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY id", (invoice_id,)).fetchall()
    return render_template("invoice_detail.html", invoice=invoice, items=items)

@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
