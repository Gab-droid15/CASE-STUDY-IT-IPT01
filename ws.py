"""
Water Refilling Station - Ordering and Inventory System
Case Study: Integrative Programming

Problem: Workers sometimes record fewer gallons than the customer ordered
and keep the difference. Solution: the CUSTOMER enters their own order and
the program prints a receipt that the worker must follow. Only the OWNER
(password) can see sales, order history and manage the inventory.
"""

import json
import math
import urllib.request
from datetime import datetime
from getpass import getpass

STATION_NAME = "CJGab Water Refilling Station"
OWNER_PASSWORD = "owner123"

# Water has no stock count (only available / not available).
# Other items (gallons, caps) have a stock count.
inventory = {
    1: {"name": "Purified Refill", "price": 25.0, "stock": None, "available": True},
    2: {"name": "Alkaline Refill", "price": 30.0, "stock": None, "available": True},
    3: {"name": "Empty Round Gallon", "price": 150.0, "stock": 20, "available": True},
    4: {"name": "Empty Slim Gallon", "price": 180.0, "stock": 15, "available": True},
    5: {"name": "Gallon Cap", "price": 10.0, "stock": 100, "available": True},
}
next_product_id = 6
orders = []
next_receipt_no = 1


# ================================ API ====================================
def get_timestamp():
    """API: get the real Philippine date/time from an online time service so
    the receipt time cannot be faked by changing the computer clock.
    Falls back to the computer clock when there is no internet."""
    try:
        url = "https://worldtimeapi.org/api/timezone/Asia/Manila"
        with urllib.request.urlopen(url, timeout=4) as response:
            now = datetime.fromisoformat(json.loads(response.read().decode())["datetime"])
    except Exception:
        now = datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%I:%M %p")


# ============================ VALIDATION =================================
def ask_int(prompt, low=0, high=100000):
    while True:
        v = input(prompt).strip()
        if v.isdigit() and low <= int(v) <= high:
            return int(v)
        print(f"  Enter a whole number from {low} to {high}.")


def ask_float(prompt, low=0.0):
    while True:
        try:
            v = float(input(prompt).strip())
            if v >= low:
                return v
        except ValueError:
            pass
        print(f"  Enter a valid amount (at least {low}).")


def ask_text(prompt):
    while True:
        v = input(prompt).strip()
        if v and len(v) <= 30:
            return v.title()
        print("  Cannot be empty (max 30 characters).")


def ask_date():
    today = datetime.now().strftime("%Y-%m-%d")
    while True:
        v = input(f"Date (YYYY-MM-DD) [Enter = {today}]: ").strip() or today
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            print("  Invalid date. Example: 2026-11-01")


def yes_no(prompt):
    while True:
        a = input(prompt + " (y/n): ").strip().lower()
        if a in ("y", "n"):
            return a == "y"


# ============================== PRODUCTS =================================
def is_available(p):
    return p["available"] if p["stock"] is None else p["stock"] > 0


def status(p):
    if p["stock"] is None:
        return "Available" if p["available"] else "Not available"
    return f"{p['stock']} in stock" if p["stock"] > 0 else "Out of stock"


def show_products(items=None):
    items = inventory if items is None else items
    if not items:
        print("\nNo products found.")
        return
    print("\n" + "=" * 56)
    print(f"{'ID':<4}{'Product':<26}{'Price':>9}  Status")
    print("-" * 56)
    for pid, p in sorted(items.items()):
        print(f"{pid:<4}{p['name']:<26}{p['price']:>9.2f}  {status(p)}")
    print("=" * 56)


# ============================== ORDERS ===================================
def print_receipt(o):
    line = "=" * 50
    print(f"\n{line}\n{STATION_NAME.center(50)}\n{'ORDER RECEIPT'.center(50)}\n{line}")
    print(f"Receipt No : {o['receipt']:04d}")
    print(f"Date/Time  : {o['date']}  {o['time']}")
    print(f"Customer   : {o['customer']}")
    print("-" * 50)
    print(f"{'Product':<28}{'Qty':>4}{'Price':>8}{'Amount':>10}")
    for i in o["items"]:
        print(f"{i['name']:<28}{i['qty']:>4}{i['price']:>8.2f}{i['qty'] * i['price']:>10.2f}")
    print("-" * 50)
    print(f"{'TOTAL':<36}{'P' + format(o['total'], '.2f'):>14}")
    print(f"{'Cash':<36}{'P' + format(o['cash'], '.2f'):>14}")
    print(f"{'Change':<36}{'P' + format(o['cash'] - o['total'], '.2f'):>14}")
    print(line)
    print("WORKER: Serve EXACTLY the items above.".center(50))
    print("Customer: check that this matches your order.".center(50))
    print(line + "\n")


def show_orders(order_list):
    if not order_list:
        print("\nNo orders found.")
        return
    print("\n" + "=" * 62)
    print(f"{'Rcpt#':<7}{'Customer':<22}{'Time':<11}{'Items':>6}{'Total':>14}")
    print("-" * 62)
    for o in order_list:
        qty = sum(i["qty"] for i in o["items"])
        print(f"{o['receipt']:04d}   {o['customer']:<22}{o['time']:<11}{qty:>6}{o['total']:>14.2f}")
    print("-" * 62)
    print(f"{'TOTAL ORDERS: ' + str(len(order_list)):<30}"
          f"{'TOTAL SALES: P' + format(sum(o['total'] for o in order_list), ',.2f'):>32}")
    print("=" * 62)


def find_order(no):
    return next((o for o in orders if o["receipt"] == no), None)


def add_order(customer, items, cash, day, clock):
    global next_receipt_no
    total = sum(i["qty"] * i["price"] for i in items)
    order = {"receipt": next_receipt_no, "customer": customer, "items": items,
             "total": total, "cash": cash, "date": day, "time": clock}
    orders.append(order)
    next_receipt_no += 1
    return order


# ============================== CUSTOMER =================================
def create_order():
    print("\n--- NEW ORDER ---")
    customer = ask_text("Customer name: ")
    cart = {}   # item name -> {"pid", "name", "price", "qty"}

    while True:
        show_products()
        pid = ask_int("Enter product ID (0 = done): ")
        if pid == 0:
            break
        if pid not in inventory or not is_available(inventory[pid]):
            print("  Product not found or not available.")
            continue
        p = inventory[pid]
        name = p["name"]
        if p["stock"] is None:                       # water: choose gallon type
            print("  Gallon type: [1] Round  [2] Slim")
            name += " (Round)" if ask_int("  Choose: ", 1, 2) == 1 else " (Slim)"
            limit = 200
        else:
            limit = p["stock"] - cart.get(name, {"qty": 0})["qty"]
            if limit <= 0:
                print("  No more stock for that item.")
                continue
        qty = ask_int(f"  How many (max {limit})? ", 1, limit)
        item = cart.setdefault(name, {"pid": pid, "name": name, "price": p["price"], "qty": 0})
        item["qty"] += qty

    if not cart:
        print("No items ordered. Order cancelled.")
        return
    items = list(cart.values())
    total = sum(i["qty"] * i["price"] for i in items)

    print("\nYOUR ORDER:")
    for i in items:
        print(f"  {i['qty']} x {i['name']} = P{i['qty'] * i['price']:.2f}")
    print(f"  TOTAL: P{total:.2f}")
    if not yes_no("Confirm order?"):
        print("Order cancelled.")
        return

    while True:
        cash = ask_float("Cash given (0 = cancel): P")
        if cash == 0:
            print("Order cancelled.")
            return
        if cash >= total:
            break
        print("  Not enough cash.")

    for i in items:                                  # deduct stock of non-water items
        if inventory[i["pid"]]["stock"] is not None:
            inventory[i["pid"]]["stock"] -= i["qty"]
    day, clock = get_timestamp()
    print_receipt(add_order(customer, items, cash, day, clock))
    print("Give this receipt to the worker. Thank you!")


def view_my_orders():
    key = input("\nEnter your name or receipt number: ").strip().lower()
    found = [o for o in orders if key and (key in o["customer"].lower() or key.lstrip("0") == str(o["receipt"]))]
    show_orders(found)
    if found:
        no = ask_int("Receipt no. to view in full (0 = skip): ")
        if find_order(no) in found:
            print_receipt(find_order(no))


def customer_menu():
    while True:
        print("\n===== CUSTOMER MENU =====")
        print(" [1] Order\n [2] View my orders\n [3] View products and prices\n [0] Back")
        c = input("Choose: ").strip()
        if c == "1":
            create_order()
        elif c == "2":
            view_my_orders()
        elif c == "3":
            show_products()
        elif c == "0":
            return
        else:
            print("Invalid choice.")


# ============================== OWNER ====================================
def owner_login():
    for left in (2, 1, 0):
        try:
            pw = getpass("\nOwner password: ")
        except Exception:
            pw = input("\nOwner password: ")
        if pw == OWNER_PASSWORD:
            return True
        print(f"Wrong password. Attempts left: {left}")
    return False


def daily_sales():
    print("\n--- DAILY SALES ---")
    day = ask_date()
    todays = [o for o in orders if o["date"] == day]
    print("\n" + "=" * 54 + f"\n{'DAILY SALES - ' + day:^54}\n" + "=" * 54)
    if not todays:
        print("No orders on this date.\n" + "=" * 54)
        return
    sold = {}
    for o in todays:
        for i in o["items"]:
            q, a = sold.get(i["name"], (0, 0.0))
            sold[i["name"]] = (q + i["qty"], a + i["qty"] * i["price"])
    print(f"{'Product':<30}{'Qty':>6}{'Sales':>18}")
    for name, (q, a) in sold.items():
        print(f"{name:<30}{q:>6}{'P' + format(a, ',.2f'):>18}")
    print("-" * 54)
    print(f"{'TOTAL ORDERS':<36}{len(todays):>18}")
    print(f"{'TOTAL SALES':<36}{'P' + format(sum(o['total'] for o in todays), ',.2f'):>18}")
    print("=" * 54)


def order_history():
    print("\n--- ORDER HISTORY ---")
    day = ask_date()
    todays = [o for o in orders if o["date"] == day]
    print(f"\nAll orders on {day}:")
    show_orders(todays)
    if todays:
        no = ask_int("Receipt no. to view in full (0 = skip): ")
        if find_order(no) in todays:
            print_receipt(find_order(no))


def inventory_menu():
    global next_product_id
    while True:
        print("\n===== INVENTORY =====")
        print(" [1] View\n [2] Add product\n [3] Update product\n [4] Delete product\n [0] Back")
        c = input("Choose: ").strip()
        if c == "1":
            show_products()
        elif c == "2":
            name = ask_text("Product name: ")
            price = ask_float("Price: P", 0.01)
            is_water = yes_no("Is it water (no stock count)?")
            stock = None if is_water else ask_int("Starting stock: ")
            inventory[next_product_id] = {"name": name, "price": price, "stock": stock, "available": True}
            print(f"Added with ID {next_product_id}.")
            next_product_id += 1
        elif c in ("3", "4"):
            show_products()
            pid = ask_int("Product ID: ")
            if pid not in inventory:
                print("Product ID not found.")
                continue
            p = inventory[pid]
            if c == "4":
                if yes_no(f"Delete '{p['name']}'?"):
                    del inventory[pid]
                    print("Deleted. (Old receipts are not affected.)")
                continue
            if p["stock"] is None:
                print("Change: [1] Name  [2] Price  [3] Available / Not available")
            else:
                print("Change: [1] Name  [2] Price  [3] Stock")
            f = ask_int("Choose: ", 1, 3)
            if f == 1:
                p["name"] = ask_text("New name: ")
            elif f == 2:
                p["price"] = ask_float("New price: P", 0.01)
            elif p["stock"] is None:
                p["available"] = not p["available"]
            else:
                p["stock"] = ask_int("New stock: ")
            print("Updated.")
            show_products({pid: p})
        elif c == "0":
            return
        else:
            print("Invalid choice.")


def owner_menu():
    while True:
        print("\n===== OWNER MENU =====")
        print(" [1] Daily sales\n [2] Order history\n [3] Inventory\n [0] Log out")
        c = input("Choose: ").strip()
        if c == "1":
            daily_sales()
        elif c == "2":
            order_history()
        elif c == "3":
            inventory_menu()
        elif c == "0":
            return
        else:
            print("Invalid choice.")


# ========================= SAMPLE DATA (practice) ========================
def load_sample_orders():
    """Practice orders for Oct 29 - Nov 1, 2026.
    (pid, gallon type or None, quantity) per item."""
    sample = {
        "2026-10-29": [("08:15 AM", "Maria Santos", [(1, "Round", 5)]),
                       ("10:40 AM", "Jose Reyes", [(2, "Slim", 3), (1, "Round", 4)]),
                       ("01:25 PM", "Ana Cruz", [(1, "Slim", 10)]),
                       ("04:50 PM", "Pedro Garcia", [(1, "Round", 6), (5, None, 2)])],
        "2026-10-30": [("07:50 AM", "Liza Mendoza", [(2, "Round", 4)]),
                       ("09:30 AM", "Carlo Ramos", [(1, "Round", 8)]),
                       ("12:10 PM", "Rosa Bautista", [(1, "Slim", 5), (2, "Slim", 2)]),
                       ("03:45 PM", "Mark Villanueva", [(3, None, 1), (1, "Round", 3)]),
                       ("05:20 PM", "Joy Aquino", [(1, "Round", 7)])],
        "2026-10-31": [("08:05 AM", "Ben Torres", [(1, "Round", 10)]),
                       ("11:15 AM", "Nina Flores", [(2, "Round", 6)]),
                       ("02:30 PM", "Dante Castillo", [(1, "Slim", 4), (4, None, 1)]),
                       ("04:10 PM", "Grace Lopez", [(1, "Round", 5), (2, "Slim", 3)])],
        "2026-11-01": [("09:00 AM", "Ricky Navarro", [(1, "Round", 12)]),
                       ("10:55 AM", "Tess Morales", [(2, "Round", 5)]),
                       ("01:40 PM", "Aling Nena", [(1, "Slim", 6), (5, None, 3)]),
                       ("03:20 PM", "Kuya Boy", [(1, "Round", 9)]),
                       ("05:05 PM", "Hazel Domingo", [(2, "Slim", 4), (1, "Slim", 2)])],
    }
    for day, day_orders in sample.items():
        for clock, customer, lines in day_orders:
            items = []
            for pid, gallon, qty in lines:
                p = inventory[pid]
                items.append({"pid": pid, "name": p["name"] + (f" ({gallon})" if gallon else ""),
                              "price": p["price"], "qty": qty})
            total = sum(i["qty"] * i["price"] for i in items)
            add_order(customer, items, math.ceil(total / 100) * 100, day, clock)


# ============================== MAIN =====================================
def main():
    load_sample_orders()
    print("=" * 42)
    print(f"Welcome to {STATION_NAME}!")
    print("=" * 42)
    while True:
        print("\n===== START =====\n [1] Customer\n [2] Owner\n [0] Exit")
        c = input("Choose: ").strip()
        if c == "1":
            customer_menu()
        elif c == "2":
            if owner_login():
                owner_menu()
            else:
                print("Too many wrong attempts.")
        elif c == "0":
            print("Thank you! Goodbye.")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()