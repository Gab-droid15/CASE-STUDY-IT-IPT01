import requests
BASE_URL = "http://127.0.0.1:8000"
STATION = "CJGab Water Refilling Station"

# ---------------------------------------------------------------- helpers
def call(method, path, owner_password=None, **kwargs):
    """Sends a request to the API. Returns the JSON, or None if there was an error (error is printed)."""
    headers = {"X-Owner-Password": owner_password} if owner_password else {}
    try:
        res = requests.request(method, BASE_URL + path, headers=headers, timeout=10, **kwargs)
    except requests.exceptions.ConnectionError:
        print("\n! Cannot connect to the API. Is 'uvicorn api:app --reload' running?")
        return None

    if res.status_code >= 400:
        detail = res.json().get("detail", "Something went wrong")
        if isinstance(detail, list):  # validation errors from pydantic
            detail = "; ".join(d["msg"] for d in detail)
        print(f"\n! {detail}")
        return None
    return res.json()


def ask_int(prompt, minimum=0):
    while True:
        try:
            value = int(input(prompt).strip())
            if value >= minimum:
                return value
        except ValueError:
            pass
        print(f"  Please enter a whole number ({minimum} or higher).")


def ask_float(prompt, minimum=0.0):
    while True:
        try:
            value = float(input(prompt).strip())
            if value >= minimum:
                return value
        except ValueError:
            pass
        print(f"  Please enter a valid amount ({minimum} or higher).")


def ask_yes_no(prompt):
    while True:
        answer = input(prompt + " (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  Please type y or n.")


def stock_text(p):
    if p["stock"] is None:  # water
        return "Available" if p["available"] else "Not available"
    return f"{p['stock']} left" if p["stock"] > 0 else "Out of stock"


def print_products(products, show_status=True):
    print("\n" + "-" * 62)
    print(f"{'ID':<4}{'Product':<26}{'Price':>10}   {'Status' if show_status else ''}")
    print("-" * 62)
    for p in products:
        status = stock_text(p) if show_status else ""
        print(f"{p['id']:<4}{p['name']:<26}{'P' + format(p['price'], ',.2f'):>10}   {status}")
    print("-" * 62)


def print_receipt(r):
    print("\n" + "=" * 46)
    print(f"{r['station']:^46}")
    print("=" * 46)
    print(f"Receipt No: {r['receipt_no']}")
    print(f"Date: {r['date']}   Time: {r['time']}")
    print(f"Customer: {r['customer_name']}")
    print("-" * 46)
    print(f"{'Item':<26}{'Qty':>4}{'Price':>7}{'Amount':>9}")
    for i in r["items"]:
        print(f"{i['name']:<26}{i['qty']:>4}{i['price']:>7.0f}{i['amount']:>9.2f}")
    print("-" * 46)
    print(f"{'TOTAL':<37}{r['total']:>9.2f}")
    print(f"{'CASH':<37}{r['cash']:>9.2f}")
    print(f"{'CHANGE':<37}{r['change']:>9.2f}")
    print("=" * 46)
    print("WORKER: Serve EXACTLY the items above.")
    print("CUSTOMER: Check that this matches your order.")
# ---------------------------------------------------------------- customer
def show_cart(cart):
    print("\n--- Your Order ---")
    for n, c in enumerate(cart, 1):
        print(f"{n}. {c['name']} x{c['qty']} = P{c['qty'] * c['price']:,.2f}")
    print(f"TOTAL: P{sum(c['qty'] * c['price'] for c in cart):,.2f}")


def order_flow():
    products = call("GET", "/products", params={"available_only": True})
    if products is None:
        return
    if not products:
        print("\nSorry, no products are available right now.")
        return

    customer_name = ""
    while not customer_name or len(customer_name) > 30:
        customer_name = input("\nEnter your name: ").strip()
        if not customer_name or len(customer_name) > 30:
            print("  Name must be 1 to 30 characters.")

    cart = []  # each: product_id, name, price, qty, gallon_type, stock

    while True:
        print_products(products)
        pid = ask_int("Enter product ID to order (0 to finish): ")
        if pid == 0:
            if not cart:
                if ask_yes_no("Your order is empty. Cancel order?"):
                    print("Order cancelled.")
                    return
                continue
            break

        p = next((x for x in products if x["id"] == pid), None)
        if p is None:
            print("  Invalid product ID.")
            continue

        gallon_type, name = None, p["name"]
        if p["stock"] is None:  # water needs the gallon type
            print("Gallon type:  1. Round   2. Slim")
            gallon_type = "Round" if ask_int("Choose (1-2): ", 1) == 1 else "Slim"
            name += f" ({gallon_type})"

        qty = ask_int("Quantity: ", 1)

        if p["stock"] is not None:  # check stock (including what is already in the cart)
            already = sum(c["qty"] for c in cart if c["product_id"] == pid)
            if qty + already > p["stock"]:
                print(f"  Not enough stock. Only {p['stock'] - already} more available.")
                continue

        existing = next((c for c in cart if c["name"] == name), None)
        if existing:
            existing["qty"] += qty
        else:
            cart.append({"product_id": pid, "name": name, "price": p["price"],
                         "qty": qty, "gallon_type": gallon_type})

        show_cart(cart)
        if not ask_yes_no("Add another item?"):
            break

    # ---- confirmation
    show_cart(cart)
    total = sum(c["qty"] * c["price"] for c in cart)
    cash = ask_float(f"\nEnter cash (total is P{total:,.2f}): ", total)

    if not ask_yes_no(f"Confirm order? Total P{total:,.2f}, Cash P{cash:,.2f}"):
        print("Order cancelled.")
        return

    body = {
        "customer_name": customer_name,
        "items": [{"product_id": c["product_id"], "qty": c["qty"], "gallon_type": c["gallon_type"]} for c in cart],
        "cash": cash,
    }
    receipt = call("POST", "/orders", json=body)
    if receipt:
        print_receipt(receipt)
        input("\nPress Enter to go back to the menu...")


def customer_menu():
    while True:
        print("\n===== CUSTOMER =====")
        print("1. Order")
        print("2. View products and prices")
        print("0. Back")
        choice = input("Choose: ").strip()

        if choice == "1":
            order_flow()
        elif choice == "2":
            products = call("GET", "/products")
            if products is not None:
                print_products(products)
        elif choice == "0":
            return
        else:
            print("  Invalid choice.")
# ---------------------------------------------------------------- owner
def order_history(password):
    day = input("\nEnter date (YYYY-MM-DD) or 0 to view all orders: ").strip()
    params = None if day == "0" else {"day": day}

    orders = call("GET", "/owner/orders", owner_password=password, params=params)
    if orders is None:
        return
    if not orders:
        print("\nNo orders found.")
        return

    print("\n" + "-" * 78)
    print(f"{'Receipt':<9}{'Date':<12}{'Time':<10}{'Customer':<18}{'Items':>6}{'Total':>12}")
    print("-" * 78)
    for o in orders:
        items = sum(i["qty"] for i in o["items"])
        print(f"{o['id']:04d}     {o['date']:<12}{o['time']:<10}{o['customer_name']:<18}{items:>6}{o['total']:>12,.2f}")
    print("-" * 78)
    print(f"Total orders: {len(orders)}    Total sales: P{sum(o['total'] for o in orders):,.2f}")
    
    # optionally open a full receipt
    while True:
        no = ask_int("\nEnter receipt no. to view full receipt (0 to go back): ")
        if no == 0:
            return
        receipt = call("GET", f"/orders/{no}")
        if receipt:
            print_receipt(receipt)


def add_product(password):
    print("\n--- Add Product ---")
    name = input("Product name: ").strip()
    price = ask_float("Price: ", 0.01)
    is_water = ask_yes_no("Is this a water refill (no stock count)?")
    stock = None if is_water else ask_int("Starting stock: ", 0)

    product = call("POST", "/owner/products", owner_password=password,
                   json={"name": name, "price": price, "stock": stock})
    if product:
        print(f"\nAdded: {product['name']} (ID {product['id']})")


def edit_product(password):
    pid = ask_int("\nEnter product ID to edit (0 to cancel): ")
    if pid == 0:
        return

    while True:
        products = call("GET", "/owner/products", owner_password=password)
        if products is None:
            return
        p = next((x for x in products if x["id"] == pid), None)
        if p is None:
            print("  Product ID not found.")
            return

        print(f"\n--- Editing: {p['name']} | P{p['price']:,.2f} | {stock_text(p)} ---")
        print("1. Change name")
        print("2. Change price")
        if p["stock"] is None:
            print("3. Set Available / Not available")
        else:
            print("3. Change stock")
        print("0. Done")
        choice = input("Choose: ").strip()

        payload = None
        if choice == "1":
            payload = {"name": input("New name: ").strip()}
        elif choice == "2":
            payload = {"price": ask_float("New price: ", 0.01)}
        elif choice == "3":
            if p["stock"] is None:
                payload = {"available": ask_yes_no("Is it available now?")}
            else:
                payload = {"stock": ask_int("New stock count: ", 0)}
        elif choice == "0":
            return
        else:
            print("  Invalid choice.")
            continue

        if call("PUT", f"/owner/products/{pid}", owner_password=password, json=payload):
            print("\nProduct updated.")


def delete_product(password):
    pid = ask_int("\nEnter product ID to delete (0 to cancel): ")
    if pid == 0:
        return
    if not ask_yes_no(f"Are you sure you want to delete product ID {pid}?"):
        print("Cancelled.")
        return

    deleted = call("DELETE", f"/owner/products/{pid}", owner_password=password)
    if deleted:
        print(f"\nDeleted: {deleted['name']}")


def inventory_menu(password):
    while True:
        products = call("GET", "/owner/products", owner_password=password)
        if products is None:
            return
        print("\n===== INVENTORY =====")
        print_products(products)
        print("1. Add product")
        print("2. Edit product (name, price, stock)")
        print("3. Delete product")
        print("0. Back")
        choice = input("Choose: ").strip()

        if choice == "1":
            add_product(password)
        elif choice == "2":
            edit_product(password)
        elif choice == "3":
            delete_product(password)
        elif choice == "0":
            return
        else:
            print("  Invalid choice.")


def owner_menu():
    # ---- login (3 tries)
    password = None
    for attempt in range(3):
        entered = input("\nEnter owner password: ").strip()
        if call("POST", "/owner/login", json={"password": entered}):
            password = entered
            break
        if attempt < 2:
            print("  Try again.")
    if password is None:
        print("Too many failed attempts. Returning to main menu.")
        return

    print("\nLogin successful. Welcome, Sir!")
    while True:
        print("\n===== OWNER =====")
        print("1. Order History")
        print("2. Inventory")
        print("0. Log out")
        choice = input("Choose: ").strip()

        if choice == "1":
            order_history(password)
        elif choice == "2":
            inventory_menu(password)
        elif choice == "0":
            print("Logged out.")
            return
        else:
            print("  Invalid choice.")

# ---------------------------------------------------------------- main
def main():
    while True:
        print("\n" + "=" * 40)
        print(f"{STATION:^40}")
        print("=" * 40)
        print("1. Customer")
        print("2. Owner")
        print("0. Exit")
        choice = input("Choose: ").strip()

        if choice == "1":
            customer_menu()
        elif choice == "2":
            owner_menu()
        elif choice == "0":
            print("Thank you! Goodbye.")
            break
        else:
            print("  Invalid choice.")


if __name__ == "__main__":
    main()
