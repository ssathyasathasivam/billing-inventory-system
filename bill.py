import streamlit as st
import mysql.connector
from datetime import datetime
import pandas as pd

# ---------- Convert Amount to Words ----------
def amount_to_words(amount):
    """Convert numeric amount to words in English"""
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", 
             "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    
    def convert_below_1000(num):
        if num == 0:
            return ""
        elif num < 10:
            return ones[num]
        elif num < 20:
            return teens[num - 10]
        elif num < 100:
            return tens[num // 10] + ("" if num % 10 == 0 else " " + ones[num % 10])
        else:
            return ones[num // 100] + " Hundred" + ("" if num % 100 == 0 else " " + convert_below_1000(num % 100))
    
    if amount == 0:
        return "Zero"
    
    amount = int(round(amount))
    
    crores = amount // 10000000
    amount %= 10000000
    
    lakhs = amount // 100000
    amount %= 100000
    
    thousands = amount // 1000
    amount %= 1000
    
    remainder = amount
    
    result = []
    
    if crores > 0:
        result.append(convert_below_1000(crores) + " Crore")
    if lakhs > 0:
        result.append(convert_below_1000(lakhs) + " Lakh")
    if thousands > 0:
        result.append(convert_below_1000(thousands) + " Thousand")
    if remainder > 0:
        result.append(convert_below_1000(remainder))
    
    return " ".join(result) + " Rupees Only"

# ---------- Database Connection ----------
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Sathya@123",
        database="bill_system"
    )

# ---------- Data Functions ----------
def get_all_products():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, PRODUCT_NAME, PRODUCT_CODE, PACK_SIZE,
               AVAILABLE_STOCK, BILLING_PRICE, GST_AMOUNT
        FROM `import`
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def update_stock(product_id, new_qty):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE `import` SET AVAILABLE_STOCK=%s WHERE id=%s",
                   (new_qty, product_id))
    conn.commit()
    cursor.close()
    conn.close()

# helper to increment existing stock by a quantity
# this is used on the Inventory page when adding stock

def add_stock(product_id, qty):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE `import` \
                    SET AVAILABLE_STOCK = AVAILABLE_STOCK + %s \
                    WHERE id=%s",
                   (qty, product_id))
    conn.commit()
    cursor.close()
    conn.close()

def get_financial_year_string(dt=None):
    """Return financial year string like '25-26' for given date."""
    if dt is None:
        dt = datetime.now()
    year = dt.year
    # financial year begins in April
    if dt.month >= 4:
        start = year
        end = year + 1
    else:
        start = year - 1
        end = year
    return f"{str(start)[-2:]}-{str(end)[-2:]}"

def generate_invoice_no(cursor):
    """Generate next invoice number with prefix GURU/<fy>/<seq>."""
    fy = get_financial_year_string()
    prefix = f"GURU/{fy}/"
    cursor.execute(
        "SELECT invoice_no FROM invoices WHERE invoice_no LIKE %s ORDER BY id DESC LIMIT 1",
        (prefix + "%",)
    )
    row = cursor.fetchone()
    if row and row[0]:
        try:
            last_seq = int(row[0].rsplit("/", 1)[-1])
        except ValueError:
            last_seq = 0
        next_seq = last_seq + 1
    else:
        next_seq = 1
    return f"{prefix}{next_seq}"

def save_invoice_to_db(items, total_billing, total_gst, grand_total,
                       buyer_name=None, buyer_address=None, buyer_phone=None):
    conn = get_connection()
    cursor = conn.cursor()

    # use financial-year-based numbering per request
    invoice_no = generate_invoice_no(cursor)
    invoice_date = datetime.now()

    cursor.execute("""
        INSERT INTO invoices
        (invoice_no, invoice_date, buyer_name, buyer_address,
         buyer_phone, total_billing, total_gst, grand_total)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (invoice_no, invoice_date, buyer_name, buyer_address,
          buyer_phone, total_billing, total_gst, grand_total))

    invoice_id = cursor.lastrowid

    for p, qty in items:
        price = float(p["BILLING_PRICE"])
        gst = price * 0.18
        total = (price + gst) * qty

        cursor.execute("""
            INSERT INTO invoice_items
            (invoice_id, product_code, product_name, pack_size,
             quantity, unit_price, gst, total)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (invoice_id, p["PRODUCT_CODE"], p["PRODUCT_NAME"],
              p["PACK_SIZE"], qty, price, gst, total))

    conn.commit()
    cursor.close()
    conn.close()
    return invoice_no

# ---------- Invoice HTML ----------
def render_invoice_html(items, total_billing, total_gst,
                        grand_total, inv_no,
                        buyer_name="", buyer_address="", buyer_phone=""):
    date_str = datetime.now().strftime("%d-%m-%Y %H:%M")

    rows_html = ""
    sno = 1
    total_cgst = total_gst / 2
    total_sgst = total_gst / 2
    
    for p, qty in items:
        price = float(p["BILLING_PRICE"])
        taxable_value = price * qty
        gst_rate = 18

        rows_html += f"""
                <tr style="border:1px solid #ddd; text-align:center; font-size:0.75em;">
                    <td style="padding:2px 1px; border:1px solid #ddd;">{sno}</td>
                    <td style="padding:2px 1px; border:1px solid #ddd; text-align:left;">{p['PRODUCT_CODE']}</td>
                    <td style="padding:2px 1px; border:1px solid #ddd; text-align:left;">{p['PRODUCT_NAME']}</td>
                    <td style="padding:2px 1px; border:1px solid #ddd;">{p['PACK_SIZE']}</td>
                    <td style="padding:2px 1px; border:1px solid #ddd; text-align:right;">₹{price:.2f}</td>
                    <td style="padding:2px 1px; border:1px solid #ddd;">{gst_rate}%</td>
                    <td style="padding:2px 1px; border:1px solid #ddd;">{qty}</td>
                    <td style="padding:2px 1px; border:1px solid #ddd; text-align:right; font-weight:600;">₹{taxable_value:.2f}</td>
                </tr>
        """
        sno += 1

    # Calculate totals for summary
    amount_words = amount_to_words(grand_total)

    return f"""
    <div>
        <style>
            @page {{ size: A5 portrait; margin: 4mm; padding: 0; }}
            @media print {{
                .print-button {{ display:none !important; }}
                body {{ -webkit-print-color-adjust: exact; margin: 0; padding: 0; }}
                html {{ margin: 0; padding: 0; }}
            }}
            .invoice-wrap {{
                font-family: 'Segoe UI', Arial, sans-serif;
                width: 148mm;
                margin: 0 auto;
                padding: 6mm;
                background: #ffffff;
                color: #333;
                box-sizing: border-box;
                line-height: 1.2;
            }}
            .invoice-wrap h1 {{ margin: 0; padding: 0; }}
            .invoice-wrap p {{ margin: 2px 0; }}
            .invoice-wrap div {{ margin: 0; padding: 0; }}
        </style>

        <div class="invoice-wrap">
            <div style="text-align:right; margin-bottom:3px;">
                <button class="print-button" onclick="window.print()" style="padding:4px 10px; background:#007bff; color:white; border:none; border-radius:2px; cursor:pointer; font-size:0.75em;">Print</button>
            </div>

            <div style="text-align:center; border-bottom:1px solid #007bff; padding-bottom:4px; margin-bottom:5px;">
                <h1 style="font-size:16px; color:#007bff; margin:0; padding:0;">GURU AGENCIES</h1>
                <div style="font-size:0.7em; color:#666; margin-top:1px; line-height:1.1;">KAVARAYAR STREET, RAMANATHAPURAM 623504<br>
                    Phone: 7823941892 | GSTIN/UIN: 33LKAPS1968J1ZM</div>
                <div style="font-size:0.75em; font-weight:600; margin-top:2px;">TAX INVOICE</div>
            </div>

            <div style="display:flex; justify-content:space-between; font-size:0.75em; margin-bottom:5px; gap:4px;">
                <div style="flex:1;">
                    <div style="font-weight:600; font-size:0.7em;">BILL TO</div>
                    <div style="margin-top:1px; font-weight:600; font-size:0.72em;">{buyer_name}</div>
                    <div style="color:#666; white-space:pre-wrap; font-size:0.7em; line-height:1.1;">{buyer_address}</div>
                    <div style="color:#666; font-size:0.7em;">{buyer_phone}</div>
                </div>
                <div style="text-align:right; font-size:0.7em;">
                    <div>Inv #: <b>{inv_no}</b></div>
                    <div>{date_str}</div>
                </div>
            </div>

            <table style="width:100%; border-collapse:collapse; font-size:0.75em; border:1px solid #ddd; margin-bottom:3px;">
                <thead>
                    <tr style="background:#f2f6fb; color:#0b63a7; font-weight:700; text-align:center;">
                        <th style="padding:3px 2px; border:1px solid #ddd; width:5%;">S.No</th>
                        <th style="padding:3px 2px; border:1px solid #ddd; text-align:left; width:15%;">Code</th>
                        <th style="padding:3px 2px; border:1px solid #ddd; text-align:left; width:25%;">Category</th>
                        <th style="padding:3px 2px; border:1px solid #ddd; width:10%;">Pack</th>
                        <th style="padding:3px 2px; border:1px solid #ddd; text-align:right; width:10%;">Price</th>
                        <th style="padding:3px 2px; border:1px solid #ddd; width:7%;">GST%</th>
                        <th style="padding:3px 2px; border:1px solid #ddd; width:6%;">Qty</th>
                        <th style="padding:3px 2px; border:1px solid #ddd; text-align:right; width:12%;">Taxable</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
                <tfoot>
                    <tr style="background:#f7f9fb; font-weight:700; font-size:0.75em;">
                        <td colspan="7" style="padding:3px 2px; border:1px solid #ddd; text-align:right;">TOTAL</td>
                        <td style="padding:3px 2px; border:1px solid #ddd; text-align:right; color:#0b63a7;">₹{total_billing:,.2f}</td>
                    </tr>
                </tfoot>
            </table>

            <div style="margin:3px 0; padding:4px; background:#fbfdff; border:1px solid #ddd; border-radius:2px; font-size:0.72em;">
                <div style="display:flex; justify-content:space-between; padding:2px 0; border-bottom:1px solid #eee;"><span>Taxable Value:</span><span>₹{total_billing:,.2f}</span></div>
                <div style="display:flex; justify-content:space-between; padding:2px 0; border-bottom:1px solid #eee;"><span>Total GST:</span><span>₹{total_gst:,.2f}</span></div>
                <div style="display:flex; justify-content:space-between; padding:2px 0; color:#666; font-size:0.68em;"><span style="margin-left:8px;">CGST 9%</span><span>₹{total_cgst:,.2f}</span></div>
                <div style="display:flex; justify-content:space-between; padding:2px 0 3px 0; color:#666; font-size:0.68em;"><span style="margin-left:8px;">SGST 9%</span><span>₹{total_sgst:,.2f}</span></div>
                <div style="display:flex; justify-content:space-between; padding-top:3px; font-weight:800; color:#0b63a7; font-size:0.85em;"><span>TOTAL</span><span>₹{grand_total:,.2f}</span></div>
            </div>

            <div style="margin:3px 0; padding:3px; background:#eef7ff; border-left:3px solid #0b63a7; border-radius:2px; font-size:0.68em; line-height:1.1;">
                <div style="font-weight:700;">Amt in Words:</div>
                <div style="margin-top:1px; color:#0b63a7; font-weight:600;">{amount_words}</div>
            </div>

            <div style="margin-top:3px; text-align:center; color:#777; font-size:0.65em;">
                <div>Computer-generated invoice. No signature required.</div>
            </div>
        </div>
    </div>
    """

# ---------- UI ----------
st.set_page_config(page_title="Billing Pro", layout="wide")
st.title("🛒 Billing & Inventory System")

page = st.sidebar.radio("Go To",
                        ["Invoice", "Inventory",
                         "Sales History", "Customer Records",
                         "Reports"])

products = get_all_products()

# ---------- Reporting Queries ----------

def get_customer_sales():
    """Return total sales amount per customer."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT buyer_name, SUM(grand_total) AS total
        FROM invoices
        WHERE buyer_name IS NOT NULL
        GROUP BY buyer_name
        ORDER BY total DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def get_month_bills(year, month):
    """Return all invoices and items for a specific month."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT i.id, i.invoice_no, i.invoice_date, i.buyer_name, 
               i.buyer_phone, i.total_billing, i.total_gst, i.grand_total
        FROM invoices i
        WHERE YEAR(i.invoice_date) = %s AND MONTH(i.invoice_date) = %s
        ORDER BY i.invoice_date DESC
    """, (year, month))
    invoices = cursor.fetchall()
    
    all_data = []
    for inv in invoices:
        cursor.execute("""
            SELECT product_code, product_name, pack_size, quantity, unit_price, gst, total
            FROM invoice_items
            WHERE invoice_id = %s
        """, (inv["id"],))
        items = cursor.fetchall()
        
        for item in items:
            all_data.append({
                'Invoice No': inv['invoice_no'],
                'Date': inv['invoice_date'].strftime("%d-%m-%Y %H:%M") if inv['invoice_date'] else '',
                'Buyer Name': inv['buyer_name'] or '',
                'Buyer Phone': inv['buyer_phone'] or '',
                'Product Code': item['product_code'],
                'Product Name': item['product_name'],
                'Pack Size': item['pack_size'],
                'Quantity': item['quantity'],
                'Unit Price': float(item['unit_price']),
                'GST': float(item['gst'] * item['quantity']),
                'Total': float(item['total'])
            })
    
    cursor.close()
    conn.close()
    return all_data

# =====================================================
# ====================== INVOICE ======================
# =====================================================
if page == "Invoice":
    st.header("Create New Invoice")

    buyer_name = st.text_input("Name")
    buyer_address = st.text_area("Address")
    buyer_phone = st.text_input("Phone")

    # phone validation
    phone_valid = True
    if buyer_phone:
        if not buyer_phone.isdigit():
            st.error("Phone number must contain only digits")
            phone_valid = False
        elif len(buyer_phone) != 10:
            st.error(f"Phone number must be exactly 10 digits (got {len(buyer_phone)})")
            phone_valid = False

    if "invoice_items" not in st.session_state:
        st.session_state.invoice_items = []

    st.subheader("Add Item")

    # Product Name Dropdown
    product_names = sorted(list(set([p["PRODUCT_NAME"]
                                     for p in products])))

    col1, col2, col3, col4 = st.columns([3,2,1,1])

    with col1:
        selected_name = st.selectbox("Product Name",
                                     [""] + product_names)

    filtered_products = []
    pack_sizes = []

    if selected_name:
        filtered_products = [p for p in products
                             if p["PRODUCT_NAME"] == selected_name]
        pack_sizes = sorted(list(set([p["PACK_SIZE"]
                                      for p in filtered_products])))

    with col2:
        selected_pack = st.selectbox("Pack Size",
                                     [""] + pack_sizes)

    selected_product = None
    if selected_name and selected_pack:
        selected_product = next(
            (p for p in filtered_products
             if p["PACK_SIZE"] == selected_pack),
            None
        )

    with col3:
        qty = st.number_input("Qty", min_value=1, value=1)

    with col4:
        if st.button("Add"):
            if not selected_product:
                st.error("Select Product & Pack")
            elif qty > selected_product["AVAILABLE_STOCK"]:
                st.error("Not enough stock")
            else:
                st.session_state.invoice_items.append(
                    (selected_product, qty)
                )
                st.success("Item Added")

    # Display Items
    t_bill = t_gst = g_total = 0.0

    for idx, (p, q) in enumerate(st.session_state.invoice_items):
        price = float(p["BILLING_PRICE"])
        gst = price * 0.18
        total = (price + gst) * q

        st.write(
            f"{p['PRODUCT_NAME']} ({p['PACK_SIZE']}) "
            f"x{q} = ₹{total:.2f}"
        )

        t_bill += price * q
        t_gst += gst * q
        g_total += total

    if st.session_state.invoice_items:
        st.markdown("---")
        st.write(f"Total Billing: ₹{t_bill:.2f}")
        st.write(f"Total GST: ₹{t_gst:.2f}")
        st.subheader(f"Grand Total: ₹{g_total:.2f}")

        if st.button("Generate Invoice"):
            if not phone_valid:
                st.error("Please correct the phone number before generating invoice")
            else:
                inv_no = save_invoice_to_db(
                    st.session_state.invoice_items,
                    t_bill, t_gst, g_total,
                    buyer_name, buyer_address, buyer_phone
                )

                for p, q in st.session_state.invoice_items:
                    update_stock(
                        p["id"],
                        int(p["AVAILABLE_STOCK"]) - q
                    )

                st.success(f"Invoice {inv_no} Saved")
                st.components.v1.html(
                    render_invoice_html(
                        st.session_state.invoice_items,
                        t_bill, t_gst, g_total,
                        inv_no,
                        buyer_name, buyer_address, buyer_phone
                    ),
                    height=600
                )

                st.session_state.invoice_items = []

# =====================================================
# ====================== INVENTORY ====================
# =====================================================
if page == "Inventory":
    st.header("Stock List")
    # show limited columns (exclude billing_price and gst_amount)
    df_inv = pd.DataFrame(products)
    if not df_inv.empty:
        show_cols = [c for c in df_inv.columns if c not in ("BILLING_PRICE", "GST_AMOUNT")]
        st.table(df_inv[show_cols])
    else:
        st.write("No products to display")

    # allow adding quantity to existing products, similar to invoice logic
    st.subheader("Add Stock")

    if "inventory_additions" not in st.session_state:
        st.session_state.inventory_additions = []

    # dropdowns for product selection
    product_names = sorted(list(set([p["PRODUCT_NAME"] for p in products])))
    col1, col2, col3, col4 = st.columns([3,2,1,1])

    with col1:
        inv_selected_name = st.selectbox("Product Name", [""] + product_names)

    filtered_products = []
    pack_sizes = []
    if inv_selected_name:
        filtered_products = [p for p in products if p["PRODUCT_NAME"] == inv_selected_name]
        pack_sizes = sorted(list(set([p["PACK_SIZE"] for p in filtered_products])))

    with col2:
        inv_selected_pack = st.selectbox("Pack Size", [""] + pack_sizes)

    inv_selected_product = None
    if inv_selected_name and inv_selected_pack:
        inv_selected_product = next((p for p in filtered_products if p["PACK_SIZE"] == inv_selected_pack), None)

    with col3:
        inv_qty = st.number_input("Qty to Add", min_value=1, value=1)

    with col4:
        if st.button("Add to Inventory"):
            if not inv_selected_product:
                st.error("Select Product & Pack")
            else:
                st.session_state.inventory_additions.append((inv_selected_product, inv_qty))
                st.success("Added to list")

    # display additions
    if st.session_state.inventory_additions:
        st.markdown("---")
        st.write("### Pending Additions")
        for p, q in st.session_state.inventory_additions:
            st.write(f"{p['PRODUCT_NAME']} ({p['PACK_SIZE']}) +{q} units")

        if st.button("Update Inventory"):
            for p, q in st.session_state.inventory_additions:
                add_stock(p["id"], q)
            st.success("Inventory updated")
            st.session_state.inventory_additions = []
            # refresh products list to show updated values
            products = get_all_products()
            st.table(products)

# =====================================================
# ====================== REPORTS =======================
# =====================================================
if page == "Reports":
    st.header("Reports")

    st.subheader("Customer Sales Report")
    cust_data = get_customer_sales()
    if cust_data:
        df_cust = pd.DataFrame(cust_data)
        df_cust = df_cust.set_index("buyer_name")
        st.dataframe(df_cust)
        st.bar_chart(df_cust["total"])
    else:
        st.write("No customer sales data.")

    st.markdown("---")
    st.subheader("Download Monthly Bills")
    
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        selected_month = st.selectbox("Select Month", 
                                      range(1, 13), 
                                      format_func=lambda x: datetime(2000, x, 1).strftime("%B"))
    
    with col2:
        current_year = datetime.now().year
        selected_year = st.selectbox("Select Year", 
                                     range(current_year - 2, current_year + 1))
    
    with col3:
        if st.button("Generate Bills"):
            bills_data = get_month_bills(selected_year, selected_month)
            if bills_data:
                df_bills = pd.DataFrame(bills_data)
                csv = df_bills.to_csv(index=False)
                
                month_name = datetime(2000, selected_month, 1).strftime("%B")
                filename = f"Bills_{month_name}_{selected_year}.csv"
                
                st.download_button(
                    label="📥 Download Bills CSV",
                    data=csv,
                    file_name=filename,
                    mime="text/csv"
                )
                st.dataframe(df_bills, use_container_width=True)
            else:
                st.info(f"No bills found for {datetime(2000, selected_month, 1).strftime('%B')} {selected_year}")

# =====================================================
# ===================== SALES HISTORY =================
# =====================================================
if page == "Sales History":
    st.header("Sales History")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM invoices ORDER BY invoice_date DESC")

    for inv in cursor.fetchall():
        with st.expander(
            f"{inv['invoice_no']} | ₹{inv['grand_total']}"):
            # fetch detailed items for the invoice
            cursor.execute(
                "SELECT product_code, product_name, pack_size, quantity, unit_price "
                "FROM invoice_items WHERE invoice_id=%s",
                (inv["id"],))
            raw_items = cursor.fetchall()

            # build items list compatible with render_invoice_html
            items = []
            for row in raw_items:
                product = {
                    "PRODUCT_CODE": row["product_code"],
                    "PRODUCT_NAME": row["product_name"],
                    "PACK_SIZE": row["pack_size"],
                    "BILLING_PRICE": row["unit_price"]
                }
                items.append((product, row["quantity"]))

            # use stored totals from invoice record
            total_billing = inv.get("total_billing", 0)
            total_gst = inv.get("total_gst", 0)
            grand_total = inv.get("grand_total", 0)

            # render full invoice HTML inside the expander
            st.components.v1.html(
                render_invoice_html(
                    items,
                    total_billing,
                    total_gst,
                    grand_total,
                    inv["invoice_no"],
                    inv.get("buyer_name", ""),
                    inv.get("buyer_address", ""),
                    inv.get("buyer_phone", "")
                ),
                height=600
            )

    cursor.close()
    conn.close()

# =====================================================
# ================= CUSTOMER RECORDS ==================
# =====================================================
if page == "Customer Records":
    st.header("Customer History")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT DISTINCT buyer_name, buyer_phone
        FROM invoices
        WHERE buyer_name IS NOT NULL
    """)

    buyers = cursor.fetchall()
    names = [f"{b['buyer_name']} ({b['buyer_phone']})"
             for b in buyers if b["buyer_name"]]

    selected = st.selectbox("Select Buyer", [""] + names)

    if selected:
        name, phone = selected.rsplit(" (", 1)
        phone = phone.rstrip(")")

        cursor.execute("""
            SELECT * FROM invoices
            WHERE buyer_name=%s AND buyer_phone=%s
            ORDER BY invoice_date DESC
        """, (name, phone))

        for inv in cursor.fetchall():
            with st.expander(
                f"{inv['invoice_no']} | ₹{inv['grand_total']}"):
                cursor.execute("""
                    SELECT product_name, quantity, total
                    FROM invoice_items
                    WHERE invoice_id=%s
                """, (inv["id"],))
                st.table(cursor.fetchall())

    cursor.close()
    conn.close()






