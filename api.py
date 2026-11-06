import json
import urllib.request
from datetime import date, datetime
from fastapi import FastAPI, HTTPException, Header
from models import OrderInput, OwnerLoginInput, ProductInput, ProductUpdateInput 

# 9 API's
app = FastAPI(title="CJGab Water Refilling Station - Ordering and Inventory API")

# --- Helper functions to read and save data.json ---
def load_data():
    with open("data.json", "r") as file:
        return json.load(file)

def save_data(data):
    with open("data.json", "w") as file:
        json.dump(data, file, indent=2)

def get_next_id(items):
    return max([item["id"] for item in items], default=0) + 1


# Owner-only endpoints call this. The password is in data.json -> settings
# Sent by the CLI in the request header: X-Owner-Password
def verify_owner(password: str | None, data):
    if password != data["settings"]["owner_password"]:
        raise HTTPException(status_code=401, detail="Wrong owner password")


# Gets the real Philippine date/time from an online time service so the receipt
# time cannot be faked by changing the computer clock. Falls back to the computer clock.
def get_timestamp():
    try:
        url = "https://worldtimeapi.org/api/timezone/Asia/Manila"
        with urllib.request.urlopen(url, timeout=4) as response:
            now = datetime.fromisoformat(json.loads(response.read().decode())["datetime"])
    except Exception:
        now = datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%I:%M %p")


# Water has no stock count (stock is None), only available / not available
def is_water(p):
    return p["stock"] is None

def is_available(p):
    return p["available"] if is_water(p) else p["stock"] > 0

def find_product(products, product_id):
    return next((p for p in products if p["id"] == product_id), None)

def name_taken(products, name, ignore_id=None):
    return any(p["name"].lower() == name.lower() and p["id"] != ignore_id for p in products)

# Builds the receipt (same format for the new order and when viewing an old one)
def build_receipt(o):
    return {
        "station": "CJGab Water Refilling Station",
        "receipt_no": f"{o['id']:04d}",
        "date": o["date"],
        "time": o["time"],
        "customer_name": o["customer_name"],
        "items": o["items"],
        "total": o["total"],
        "cash": o["cash"],
        "change": o["change"],
    }


# - - - - - - - - - - - - - - Customer APIs - - - - - - - - - - - - - -  #

# --- 1. (GET) View products and prices ---
@app.get("/products", status_code=200)
def get_products(available_only: bool = False):
    data = load_data()
    products = data["products"]

    # if available_only=true, sasalain lang ung mga available
    if available_only:
        return [p for p in products if is_available(p)]

    return products


# --- 2. (POST) Customer creates an order ---
@app.post("/orders", status_code=201)
def create_order(order: OrderInput):
    data = load_data()
    products = data["products"]
    orders = data["orders"]

    cart = {}  # item name -> item dict

    # validate every item first, para walang mababawas na stock kapag may mali
    for line in order.items:
        p = find_product(products, line.product_id)
        if p is None or not is_available(p):
            raise HTTPException(status_code=404, detail=f"Product ID {line.product_id} not found or not available")

        name = p["name"]
        if is_water(p):  # water: need to choose gallon type
            if line.gallon_type is None:
                raise HTTPException(status_code=400, detail=f"'{name}' needs a gallon_type (Round or Slim)")
            name += f" ({line.gallon_type})"
        else:
            already = cart.get(name, {"qty": 0})["qty"]
            if line.qty + already > p["stock"]:
                raise HTTPException(status_code=400, detail=f"Not enough stock for '{name}' ({p['stock']} left)")

        # same item entered twice = add the quantity
        item = cart.setdefault(name, {"product_id": p["id"], "name": name, "price": p["price"], "qty": 0})
        item["qty"] += line.qty

    items = list(cart.values())
    for i in items:
        i["amount"] = i["qty"] * i["price"]  # automatic calculation
    total = sum(i["amount"] for i in items)

    if order.cash < total:
        raise HTTPException(status_code=400, detail=f"Not enough cash. Total is P{total:.2f}")

    # deduct stock of non-water items
    for i in items:
        p = find_product(products, i["product_id"])
        if not is_water(p):
            p["stock"] -= i["qty"]

    day, clock = get_timestamp()
    new_order = {
        "id": get_next_id(orders),  # auto incremented, this is the receipt number
        "customer_name": order.customer_name.title(),
        "items": items,
        "total": total,
        "cash": order.cash,
        "change": order.cash - total,
        "date": day,
        "time": clock,
    }

    orders.append(new_order)
    save_data(data)
    return build_receipt(new_order)


# --- 3. (GET) View one receipt in full ---
@app.get("/orders/{receipt_no}", status_code=200)
def get_receipt(receipt_no: int):
    data = load_data()

    for o in data["orders"]:
        if o["id"] == receipt_no:
            return build_receipt(o)

    raise HTTPException(status_code=404, detail="Receipt number not found")


# - - - - - - - - - - - - - - Owner APIs (password needed) - - - - - - - - - - - - - -  #

# --- 4. (POST) Owner login check ---
@app.post("/owner/login", status_code=200)
def owner_login(login: OwnerLoginInput):
    data = load_data()
    verify_owner(login.password, data)
    return {"message": "Login successful"}

# --- 5. (GET) Order history (optional ?day=YYYY-MM-DD filter, no day = all orders) ---
@app.get("/owner/orders", status_code=200)
def order_history(day: str | None = None, x_owner_password: str | None = Header(default=None)):
    data = load_data()
    verify_owner(x_owner_password, data)
    orders = data["orders"]

    if day:
        try:
            datetime.strptime(day, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date. Example: 2026-11-01")
        orders = [o for o in orders if o["date"] == day]

    return orders


# --- 6. (POST) Add a product ---
@app.post("/owner/products", status_code=201)
def create_product(product: ProductInput, x_owner_password: str | None = Header(default=None)):
    data = load_data()
    verify_owner(x_owner_password, data)
    products = data["products"]

    name = product.name.title()
    if name_taken(products, name):
        raise HTTPException(status_code=400, detail=f"'{name}' already exists")

    new_product = {
        "id": get_next_id(products),  # auto incremented
        "name": name,
        "price": product.price,
        "stock": product.stock,  # None = water
        "available": True
    }

    products.append(new_product)
    save_data(data)
    return new_product


# --- 7. (PUT) Update a product (name, price, stock, available - send only what changes) ---
@app.put("/owner/products/{product_id}", status_code=200)
def update_product(product_id: int, updated: ProductUpdateInput, x_owner_password: str | None = Header(default=None)):
    data = load_data()
    verify_owner(x_owner_password, data)
    products = data["products"]

    p = find_product(products, product_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Product ID not found")

    if all(v is None for v in (updated.name, updated.price, updated.stock, updated.available)):
        raise HTTPException(status_code=400, detail="Nothing to update")

    # water has no stock count, other items have no available toggle
    if updated.stock is not None and is_water(p):
        raise HTTPException(status_code=400, detail="Water has no stock count, use 'available' instead")
    if updated.available is not None and not is_water(p):
        raise HTTPException(status_code=400, detail="Only water can be set Available / Not available, use 'stock' instead")

    if updated.name is not None:
        name = updated.name.title()
        if name_taken(products, name, ignore_id=product_id):
            raise HTTPException(status_code=400, detail=f"'{name}' already exists")
        p["name"] = name
    if updated.price is not None:
        p["price"] = updated.price
    if updated.stock is not None:
        p["stock"] = updated.stock
    if updated.available is not None:
        p["available"] = updated.available

    save_data(data)
    return p


# --- 8. (DELETE) Delete a product ---
@app.delete("/owner/products/{product_id}", status_code=200)
def delete_product(product_id: int, x_owner_password: str | None = Header(default=None)):
    data = load_data()
    verify_owner(x_owner_password, data)
    products = data["products"]

    for p in products:
        if p["id"] == product_id:
            products.remove(p)  # old receipts are not affected (items are copied in the order)
            save_data(data)
            return p  # returns the deleted product so the CLI can show what was removed

    raise HTTPException(status_code=404, detail="Product ID not found")


# --- 9. (GET) View all products (owner view, includes stock and availability) ---
@app.get("/owner/products", status_code=200)
def owner_get_products(x_owner_password: str | None = Header(default=None)):
    data = load_data()
    verify_owner(x_owner_password, data)
    return data["products"]
