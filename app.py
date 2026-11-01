"""TradeDesk Pro 0.5.0 desktop entry point."""
import json
import tkinter as tk
from tkinter import ttk, messagebox

from database import init_db, get_connection
from migrations import migrate
from services.security_service import (
    AuthenticationError, authenticate, create_initial_setup, setup_is_complete,
)
from services.inventory_service import stock_report
from services.pos_service import create_invoice
from services.licensing import generate_machine_fingerprint, is_license_valid


class SetupDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("TradeDesk Pro — First-time Setup")
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        self.grab_set()
        fields = [
            ("Company name *", "name"), ("GSTIN", "gstin"), ("UPI ID", "upi_id"),
            ("Address", "address"), ("Phone", "phone"), ("Email", "email"),
            ("Financial year", "financial_year"), ("Administrator username *", "username"),
            ("Administrator password (12+ chars) *", "password"),
        ]
        self.entries = {}
        frame = ttk.Frame(self, padding=18)
        frame.grid(sticky="nsew")
        ttk.Label(frame, text="Set up your company and secure administrator account",
                  font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        for i, (label, key) in enumerate(fields, start=1):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", padx=(0, 12), pady=4)
            entry = ttk.Entry(frame, width=38, show="*" if key == "password" else "")
            entry.grid(row=i, column=1, sticky="ew", pady=4)
            self.entries[key] = entry
        ttk.Button(frame, text="Complete Setup", command=self.submit).grid(row=len(fields)+1, column=1, sticky="e", pady=(12, 0))
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.entries["name"].focus_set()

    def submit(self):
        values = {key: entry.get().strip() for key, entry in self.entries.items()}
        try:
            self.result = create_initial_setup(
                {key: values.get(key, "") for key in ("name", "gstin", "upi_id", "address", "phone", "email", "financial_year")},
                values["username"], values["password"],
            )
        except Exception as exc:
            messagebox.showerror("Setup failed", str(exc), parent=self)
            return
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


class LoginDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("TradeDesk Pro — Sign in")
        self.resizable(False, False)
        self.session = None
        self.transient(parent)
        self.grab_set()
        frame = ttk.Frame(self, padding=20)
        frame.grid(sticky="nsew")
        ttk.Label(frame, text="TradeDesk Pro", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        ttk.Label(frame, text="Username").grid(row=1, column=0, sticky="w", pady=5)
        self.username = ttk.Entry(frame, width=30)
        self.username.grid(row=1, column=1, pady=5)
        ttk.Label(frame, text="Password").grid(row=2, column=0, sticky="w", pady=5)
        self.password = ttk.Entry(frame, width=30, show="*")
        self.password.grid(row=2, column=1, pady=5)
        ttk.Button(frame, text="Sign in", command=self.submit).grid(row=3, column=1, sticky="e", pady=(10, 0))
        self.password.bind("<Return>", lambda _event: self.submit())
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.username.focus_set()

    def submit(self):
        try:
            self.session = authenticate(self.username.get(), self.password.get())
        except AuthenticationError as exc:
            messagebox.showerror("Sign in failed", str(exc), parent=self)
            return
        self.destroy()

    def cancel(self):
        self.session = None
        self.destroy()


class ERPApp:
    def __init__(self, root, session):
        self.root = root
        self.session = session
        self.root.title("TradeDesk Pro 0.5.0")
        self.root.geometry("1200x760")
        self.root.configure(bg="#f3f5f9")
        self.load_license_from_file()
        self.build_ui()

    def load_license_from_file(self):
        try:
            with open("license.json", "r", encoding="utf-8") as f:
                self.license = json.load(f)
            machine = generate_machine_fingerprint()
            self.license_status = "VALID" if is_license_valid(self.license, machine) else "INVALID"
        except (FileNotFoundError, ValueError):
            self.license = None
            self.license_status = "NO LICENSE"

    def build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="TradeDesk Pro", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(top, text=f"Company ID: {self.session.company_id}  •  User: {self.session.username} ({self.session.role})").pack(anchor="w")
        ttk.Label(top, text=f"License: {self.license_status}").pack(anchor="w")
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)
        self.pos_tab = ttk.Frame(notebook)
        self.stock_tab = ttk.Frame(notebook)
        notebook.add(self.pos_tab, text="POS")
        notebook.add(self.stock_tab, text="Inventory")
        self.build_pos_tab()
        self.build_inventory_tab()

    def build_pos_tab(self):
        frame = ttk.Frame(self.pos_tab, padding=10)
        frame.pack(fill="both", expand=True)
        left = ttk.LabelFrame(frame, text="Billing", padding=10)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Item Code").grid(row=0, column=0, sticky="w")
        self.item_code = ttk.Entry(left, width=30)
        self.item_code.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(left, text="Add Item", command=self.add_item_to_bill).grid(row=0, column=2, padx=5)
        columns = ("Item", "Qty", "Rate", "Amount")
        self.bill_tree = ttk.Treeview(left, columns=columns, show="headings", height=15)
        for col in columns:
            self.bill_tree.heading(col, text=col)
            self.bill_tree.column(col, width=120)
        self.bill_tree.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=10)
        self.total_var = tk.StringVar(value="0.00")
        ttk.Label(left, text="Total").grid(row=2, column=0, sticky="w")
        ttk.Label(left, textvariable=self.total_var, font=("Segoe UI", 12, "bold")).grid(row=2, column=1, sticky="w")
        ttk.Button(left, text="Save Invoice", command=self.save_invoice).grid(row=3, column=0, pady=10)

    def build_inventory_tab(self):
        frame = ttk.Frame(self.stock_tab, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Button(frame, text="Refresh Stock", command=self.refresh_stock).pack(anchor="w")
        columns = ("Code", "Name", "Qty", "Sale Price")
        self.stock_tree = ttk.Treeview(frame, columns=columns, show="headings", height=18)
        for col in columns:
            self.stock_tree.heading(col, text=col)
            self.stock_tree.column(col, width=180)
        self.stock_tree.pack(fill="both", expand=True, pady=10)
        self.refresh_stock()

    def add_item_to_bill(self):
        from services.security_service import require_permission, AuthorizationError
        try:
            require_permission(self.session, "pos.read")
        except AuthorizationError as exc:
            messagebox.showerror("Access denied", str(exc), parent=self.root)
            return
        code = self.item_code.get().strip()
        if not code:
            return
        conn = get_connection()
        item = conn.execute("SELECT * FROM item WHERE code=? AND company_id=?", (code, self.session.company_id)).fetchone()
        conn.close()
        if not item:
            messagebox.showerror("Not found", "Item not found in this company.", parent=self.root)
            return
        self.bill_tree.insert("", "end", values=(item["name"], "1", f"{item['sale_price']}", str(float(item["sale_price"]))))
        self.item_code.delete(0, "end")
        self.update_bill_total()

    def update_bill_total(self):
        total = sum(float(self.bill_tree.item(row, "values")[1]) * float(self.bill_tree.item(row, "values")[2]) for row in self.bill_tree.get_children())
        self.total_var.set(f"{total:.2f}")

    def save_invoice(self):
        from services.security_service import AuthorizationError
        if not self.bill_tree.get_children():
            messagebox.showwarning("Empty Bill", "No items in the bill.", parent=self.root)
            return
        invoice_no = f"INV-{__import__('time').time_ns()}"
        items = []
        for row in self.bill_tree.get_children():
            name, qty, rate, _amount = self.bill_tree.item(row, "values")
            conn = get_connection()
            item = conn.execute("SELECT id FROM item WHERE name=? AND company_id=? ORDER BY id LIMIT 1", (name, self.session.company_id)).fetchone()
            conn.close()
            if item:
                items.append({"item_id": item["id"], "qty": float(qty), "rate": float(rate), "discount": 0, "tax_rate": 0})
        try:
            result = create_invoice(invoice_no, 1, items, payment_mode="cash", session=self.session)
        except (ValueError, PermissionError) as exc:
            messagebox.showerror("Invoice failed", str(exc), parent=self.root)
            return
        messagebox.showinfo("Invoice Created", f"Invoice {invoice_no} saved. Total: {result['grand_total']}", parent=self.root)
        self.bill_tree.delete(*self.bill_tree.get_children())
        self.total_var.set("0.00")

    def refresh_stock(self):
        self.stock_tree.delete(*self.stock_tree.get_children())
        for row in stock_report(self.session):
            self.stock_tree.insert("", "end", values=(row["code"], row["name"], row["stock_qty"], row["sale_price"]))


def main():
    root = tk.Tk()
    root.withdraw()
    init_db()
    migrate()
    if not setup_is_complete():
        setup = SetupDialog(root)
        root.wait_window(setup)
        if setup.result is None:
            root.destroy()
            return
        session = setup.result
    else:
        login = LoginDialog(root)
        root.wait_window(login)
        if login.session is None:
            root.destroy()
            return
        session = login.session
    root.deiconify()
    ERPApp(root, session)
    root.mainloop()


if __name__ == "__main__":
    main()
