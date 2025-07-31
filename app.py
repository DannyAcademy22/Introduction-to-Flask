from flask import Flask, render_template, redirect, url_for, request, flash
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "my secret key"

DATA_FILE = os.path.join("data", "history.json")


def load_history():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    
# Función para guardar el historial en archivo JSON
def save_history(history):
    with open("history.json", "w") as f:
        json.dump(history, f, indent=4)


def calculate_balance_and_stock(history):
    balance = 0.0
    stock = {}

    for entry in history:
        if entry["type"] == "balance_add":
            balance += entry["amount"]
        elif entry["type"] == "balance_subtract":
            balance -= entry["amount"]
        elif entry["type"] == "purchase":
            total = entry["unit_price"] * entry["quantity"]
            balance -= total
            product = entry["product"]
            stock[product] = stock.get(product, 0) + entry["quantity"]
        elif entry["type"] == "sale":
            total = entry["unit_price"] * entry["quantity"]
            balance += total
            product = entry["product"]
            stock[product] = stock.get(product, 0) - entry["quantity"]

    return balance, stock

def calculate_stock(history):
    """Calculate current stock per product."""
    stock = {}
    for entry in history:
        # Validar que tenga las claves necesarias
        if "product" not in entry or "quantity" not in entry or "type" not in entry:
            print(f"Warning: invalid entry skipped: {entry}")
            continue

        product = entry["product"]
        qty = entry["quantity"]

        if entry["type"] == "purchase":
            stock[product] = stock.get(product, 0) + qty
        elif entry["type"] == "sale":
            stock[product] = stock.get(product, 0) - qty

    return stock




@app.route("/")
def index():
    history = load_history()
    balance, stock = calculate_balance_and_stock(history)
    return render_template("index.html", balance=balance, stock=stock)

@app.route("/purchase_form", methods=["GET", "POST"])
def purchase_form():
    if request.method == "POST":
        product = request.form.get("product")
        try:
            price = float(request.form.get("price"))
            quantity = int(request.form.get("quantity"))
        except ValueError:
            return render_template("purchase_form.html", error="Invalid price or quantity.")

        if price < 0 or quantity <= 0:
            return render_template("purchase_form.html", error="Price must be >= 0 and quantity > 0.")

        total_cost = price * quantity
        history_entry = {
            "type": "purchase",
            "product": product,
            "unit_price": price,
            "quantity": quantity,
            "total": total_cost
        }

        try:
            with open("data/history.json", "r", encoding="utf-8") as file:
                history = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            history = []

        history.append(history_entry)

        with open("data/history.json", "w", encoding="utf-8") as file:
            json.dump(history, file, indent=4)

        return redirect(url_for("index"))

    return render_template("purchase_form.html")


@app.route("/sale_form", methods=["GET", "POST"])
def sale_form():
    if request.method == "POST":
        product = request.form.get("product")
        try:
            unit_price = float(request.form.get("price"))
            quantity = int(request.form.get("quantity"))
        except (TypeError, ValueError):
            flash("Invalid input for price or quantity", "error")
            return redirect(url_for("sale_form"))

        if unit_price < 0 or quantity < 1 or not product:
            flash("Invalid input values", "error")
            return redirect(url_for("sale_form"))

        # Load current history
        with open("data/history.json", "r") as f:
            history = json.load(f)

        # Calculate current stock
        stock = calculate_stock(history)

        # Check if product exists and stock is enough
        available_qty = stock.get(product, 0)
        if available_qty < quantity:
            flash(f"Not enough stock for product '{product}'. Available: {available_qty}", "error")
            return redirect(url_for("sale_form"))

        # Append sale entry
        history.append({
            "type": "sale",
            "product": product,
            "unit_price": unit_price,
            "quantity": quantity
        })

        # Save updated history
        try:
            with open("data/history.json", "w") as f:
                json.dump(history, f, indent=4)
        except IOError:
            flash("Failed to save data", "error")
            return redirect(url_for("sale_form"))

        return redirect(url_for("index"))

    return render_template("sale_form.html")

@app.route('/balance_form', methods=['GET', 'POST'])
def balance_form():
    if request.method == 'POST':
        operation = request.form.get('operation')
        amount = request.form.get('amount')

        if operation not in ('add', 'subtract'):
            flash("Invalid operation selected.", "error")
            return redirect(url_for('balance_form'))

        try:
            amount = float(amount)
            if amount < 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            flash("Amount must be a positive number.", "error")
            return redirect(url_for('balance_form'))

        history = load_history()

        # Guardar el cambio de balance como una entrada del historial
        history.append({
            "type": "balance",
            "operation": operation,
            "amount": amount
        })

        save_history(history)
        flash(f"Balance successfully updated: {operation} {amount}", "success")
        return redirect(url_for('index'))

    return render_template('balance_form.html')


@app.route("/history")
@app.route("/history/<int:line_from>/<int:line_to>")
def history(line_from=None, line_to=None):
    history = load_history()  # Asegúrate de tener esta función

    entries = []
    for idx, entry in enumerate(history, start=1):
        op_type = entry.get("type")
        if op_type == "purchase":
            details = f"{entry['product']}, {entry['quantity']} units at ${entry['unit_price']:.2f}"
            operation = "Purchase"
        elif op_type == "sale":
            details = f"{entry['product']}, {entry['quantity']} units at ${entry['unit_price']:.2f}"
            operation = "Sale"
        elif op_type == "balance_add":
            details = f"${entry['amount']} added"
            operation = "Balance Add"
        elif op_type == "balance_subtract":
            details = f"${entry['amount']} subtracted"
            operation = "Balance Subtract"
        else:
            details = "Unknown"
            operation = "Unknown"

        date_str = entry.get("timestamp", datetime.now().isoformat())[:10]
        entries.append({
            "id": idx,
            "operation": operation,
            "details": details,
            "date": date_str,
        })

    # Filtrar por número de línea (id), no por posición en lista
    if line_from is not None and line_to is not None and line_from <= line_to:
        entries = [e for e in entries if line_from <= e["id"] <= line_to]
    else:
        q_from = request.args.get("lineFrom", type=int)
        q_to = request.args.get("lineTo", type=int)
        if q_from is not None and q_to is not None and q_from <= q_to:
            entries = [e for e in entries if q_from <= e["id"] <= q_to]
        elif q_from is not None:
            entries = [e for e in entries if e["id"] >= q_from]
        elif q_to is not None:
            entries = [e for e in entries if e["id"] <= q_to]

    return render_template("history.html", entries=entries)

if __name__ == "__main__":
    app.run(debug=True)
