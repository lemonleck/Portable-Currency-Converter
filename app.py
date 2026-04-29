import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "company_rates.json"
ICON_PATH = APP_DIR / "assets" / "app_icon.png"
ICON_ICO_PATH = APP_DIR / "assets" / "app_icon.ico"

CNY = "CNY"
CURRENCIES = {
    "CNY": "人民币 CNY",
    "USD": "美元 USD",
    "EUR": "欧元 EUR",
    "GBP": "英镑 GBP",
}

DEFAULT_COMPANY_RATES = {
    "USD": "6.6",
    "EUR": "7.2",
    "GBP": "8.9",
}

PALETTE = {
    "bg": "#f3f6fb",
    "panel": "#ffffff",
    "ink": "#15202b",
    "muted": "#607086",
    "line": "#d9e2ee",
    "blue": "#225ea8",
    "blue_dark": "#194b88",
    "green": "#198f6b",
    "green_soft": "#dff4ec",
    "blue_soft": "#e7f0ff",
    "warning": "#9a4d00",
}


def money(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class CurrencyConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("便携汇率转换工具")
        self.geometry("820x560")
        self.minsize(760, 520)

        self.icon_image = None
        self.load_app_icon()

        self.company_rates = self.load_company_rates()
        self.realtime_cache = {}
        self.realtime_request_id = 0

        self.amount_var = tk.StringVar(value="100")
        self.from_currency_var = tk.StringVar(value="CNY")
        self.to_currency_var = tk.StringVar(value="EUR")
        self.company_result_var = tk.StringVar(value="")
        self.realtime_result_var = tk.StringVar(value="")
        self.company_result_number_var = tk.StringVar(value="")
        self.realtime_result_number_var = tk.StringVar(value="")
        self.company_rate_var = tk.StringVar(value="")
        self.realtime_rate_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="准备就绪")

        self.configure(bg=PALETTE["bg"])
        self.create_styles()
        self.create_widgets()
        self.bind_events()
        self.recalculate()

    def load_app_icon(self):
        if ICON_ICO_PATH.exists():
            try:
                self.iconbitmap(str(ICON_ICO_PATH))
            except tk.TclError:
                pass
        if not ICON_PATH.exists():
            return
        try:
            self.icon_image = tk.PhotoImage(file=str(ICON_PATH))
            self.iconphoto(True, self.icon_image)
        except tk.TclError:
            self.icon_image = None

    def create_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Root.TFrame", background=PALETTE["bg"])
        style.configure("Panel.TFrame", background=PALETTE["panel"])
        style.configure("Header.TLabel", background=PALETTE["bg"], foreground=PALETTE["ink"], font=("Microsoft YaHei UI", 22, "bold"))
        style.configure("Title.TLabel", background=PALETTE["panel"], foreground=PALETTE["ink"], font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("Body.TLabel", background=PALETTE["bg"], foreground=PALETTE["muted"], font=("Microsoft YaHei UI", 10))
        style.configure("PanelBody.TLabel", background=PALETTE["panel"], foreground=PALETTE["muted"], font=("Microsoft YaHei UI", 10))
        style.configure("Value.TLabel", background=PALETTE["panel"], foreground=PALETTE["ink"], font=("Microsoft YaHei UI", 24, "bold"))
        style.configure("Status.TLabel", background=PALETTE["bg"], foreground=PALETTE["muted"], font=("Microsoft YaHei UI", 10))
        style.configure("TEntry", padding=(10, 8), fieldbackground="#ffffff", bordercolor=PALETTE["line"], lightcolor=PALETTE["line"])
        style.configure("TCombobox", padding=(10, 7), fieldbackground="#ffffff", bordercolor=PALETTE["line"], arrowcolor=PALETTE["ink"])
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(12, 8), borderwidth=0)
        style.configure("Accent.TButton", background=PALETTE["blue"], foreground="#ffffff", font=("Microsoft YaHei UI", 10, "bold"), padding=(16, 10), borderwidth=0)
        style.map("Accent.TButton", background=[("active", PALETTE["blue_dark"]), ("pressed", PALETTE["blue_dark"])], foreground=[("disabled", "#d7dde7")])
        style.configure("Copy.TButton", background="#eef4fb", foreground=PALETTE["blue"], font=("Microsoft YaHei UI", 10, "bold"), padding=(10, 7), borderwidth=0)
        style.map("Copy.TButton", background=[("active", "#dce8f4"), ("pressed", "#dce8f4")], foreground=[("disabled", "#9aa9bd")])
        style.configure("Swap.TButton", background="#ecf2f8", foreground=PALETTE["ink"], font=("Microsoft YaHei UI", 12, "bold"), padding=(12, 8), borderwidth=0)
        style.map("Swap.TButton", background=[("active", "#dce8f4"), ("pressed", "#dce8f4")])

    def create_widgets(self):
        root = ttk.Frame(self, style="Root.TFrame", padding=(28, 24, 28, 18))
        root.pack(fill="both", expand=True)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(2, weight=1)

        header = ttk.Frame(root, style="Root.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        if self.icon_image:
            tk.Label(header, image=self.icon_image, bg=PALETTE["bg"], width=42, height=42).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))
        ttk.Label(header, text="汇率转换", style="Header.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(header, text="人民币与外币双向转换，同时查看公司报价汇率与实时参考汇率。", style="Body.TLabel").grid(row=1, column=1, sticky="w", pady=(4, 0))
        ttk.Button(header, text="设置公司汇率", style="Accent.TButton", command=self.open_settings).grid(row=0, column=2, rowspan=2, sticky="e")

        input_panel = tk.Frame(root, bg=PALETTE["panel"], padx=20, pady=18, highlightthickness=1, highlightbackground=PALETTE["line"])
        input_panel.grid(row=1, column=0, sticky="ew", pady=(24, 18))
        input_panel.grid_columnconfigure(0, weight=1)
        input_panel.grid_columnconfigure(1, weight=1)
        input_panel.grid_columnconfigure(2, minsize=68)
        input_panel.grid_columnconfigure(3, weight=1)

        ttk.Label(input_panel, text="金额", style="PanelBody.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(input_panel, text="源货币", style="PanelBody.TLabel").grid(row=0, column=1, sticky="w", padx=(14, 0))
        ttk.Label(input_panel, text="目标货币", style="PanelBody.TLabel").grid(row=0, column=3, sticky="w")

        amount_entry = ttk.Entry(input_panel, textvariable=self.amount_var, font=("Microsoft YaHei UI", 18), width=18)
        amount_entry.grid(row=1, column=0, sticky="ew", pady=(8, 0), padx=(0, 14), ipady=2)

        self.from_combo = ttk.Combobox(input_panel, textvariable=self.from_currency_var, values=list(CURRENCIES.keys()), state="readonly", font=("Microsoft YaHei UI", 12))
        self.from_combo.grid(row=1, column=1, sticky="ew", pady=(8, 0), padx=(14, 10), ipady=3)

        ttk.Button(input_panel, text="⇄", style="Swap.TButton", width=4, command=self.swap_currencies).grid(row=1, column=2, pady=(8, 0))

        self.to_combo = ttk.Combobox(input_panel, textvariable=self.to_currency_var, values=list(CURRENCIES.keys()), state="readonly", font=("Microsoft YaHei UI", 12))
        self.to_combo.grid(row=1, column=3, sticky="ew", pady=(8, 0), padx=(10, 0), ipady=3)

        results = ttk.Frame(root, style="Root.TFrame")
        results.grid(row=2, column=0, sticky="nsew")
        results.grid_columnconfigure(0, weight=1)
        results.grid_columnconfigure(1, weight=1)
        results.grid_rowconfigure(0, weight=1)

        self.create_result_card(results, 0, "公司固定汇率", self.company_result_var, self.company_result_number_var, self.company_rate_var, PALETTE["blue"], PALETTE["blue_soft"])
        self.create_result_card(results, 1, "实时参考汇率", self.realtime_result_var, self.realtime_result_number_var, self.realtime_rate_var, PALETTE["green"], PALETTE["green_soft"])

        status_bar = ttk.Frame(root, style="Root.TFrame")
        status_bar.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(status_bar, textvariable=self.status_var, style="Status.TLabel").pack(side="left")

    def create_result_card(self, parent, column, title, value_var, number_var, rate_var, accent, soft):
        card = tk.Frame(parent, bg=PALETTE["panel"], padx=20, pady=20, highlightthickness=1, highlightbackground=PALETTE["line"])
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 10) if column == 0 else (10, 0))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)

        top = tk.Frame(card, bg=PALETTE["panel"])
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        tk.Frame(top, width=8, height=26, bg=accent).grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Label(top, text=title, style="Title.TLabel").grid(row=0, column=1, sticky="w")

        tk.Frame(card, bg=soft, height=6).grid(row=1, column=0, sticky="ew", pady=(16, 20))
        value_row = tk.Frame(card, bg=PALETTE["panel"])
        value_row.grid(row=2, column=0, sticky="nsew")
        value_row.grid_columnconfigure(0, weight=1)
        ttk.Label(value_row, textvariable=value_var, style="Value.TLabel", wraplength=240).grid(row=0, column=0, sticky="nw")
        ttk.Button(value_row, text="复制", style="Copy.TButton", command=lambda: self.copy_number(number_var)).grid(row=0, column=1, sticky="ne", padx=(12, 0), pady=(3, 0))
        ttk.Label(card, textvariable=rate_var, style="PanelBody.TLabel", wraplength=320).grid(row=3, column=0, sticky="sw", pady=(18, 0))

    def bind_events(self):
        self.amount_var.trace_add("write", lambda *_: self.recalculate())
        self.from_combo.bind("<<ComboboxSelected>>", lambda _: self.on_currency_changed("from"))
        self.to_combo.bind("<<ComboboxSelected>>", lambda _: self.on_currency_changed("to"))

    def load_company_rates(self):
        if not CONFIG_PATH.exists():
            self.save_company_rates(DEFAULT_COMPANY_RATES)
            return DEFAULT_COMPANY_RATES.copy()

        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return DEFAULT_COMPANY_RATES.copy()

        rates = DEFAULT_COMPANY_RATES.copy()
        for currency in DEFAULT_COMPANY_RATES:
            value = str(data.get(currency, rates[currency])).strip()
            try:
                if Decimal(value) > 0:
                    rates[currency] = value
            except InvalidOperation:
                pass
        return rates

    def save_company_rates(self, rates):
        CONFIG_PATH.write_text(json.dumps(rates, ensure_ascii=False, indent=2), encoding="utf-8")

    def on_currency_changed(self, side):
        from_currency = self.from_currency_var.get()
        to_currency = self.to_currency_var.get()

        if from_currency == to_currency:
            if side == "from":
                self.to_currency_var.set("EUR" if from_currency == CNY else CNY)
            else:
                self.from_currency_var.set(CNY if to_currency != CNY else "USD")

        if self.from_currency_var.get() != CNY and self.to_currency_var.get() != CNY:
            if side == "from":
                self.to_currency_var.set(CNY)
            else:
                self.from_currency_var.set(CNY)

        self.recalculate()

    def swap_currencies(self):
        old_from = self.from_currency_var.get()
        self.from_currency_var.set(self.to_currency_var.get())
        self.to_currency_var.set(old_from)
        self.on_currency_changed("to")

    def recalculate(self):
        amount_text = self.amount_var.get().strip()
        from_currency = self.from_currency_var.get()
        to_currency = self.to_currency_var.get()

        try:
            amount = Decimal(amount_text)
        except InvalidOperation:
            self.company_result_var.set("请输入有效金额")
            self.realtime_result_var.set("请输入有效金额")
            self.company_result_number_var.set("")
            self.realtime_result_number_var.set("")
            self.company_rate_var.set("")
            self.realtime_rate_var.set("")
            self.status_var.set("金额格式不正确")
            return

        if amount < 0:
            self.company_result_var.set("金额不能为负数")
            self.realtime_result_var.set("金额不能为负数")
            self.company_result_number_var.set("")
            self.realtime_result_number_var.set("")
            self.company_rate_var.set("")
            self.realtime_rate_var.set("")
            self.status_var.set("金额不能为负数")
            return

        if from_currency == to_currency or (from_currency != CNY and to_currency != CNY):
            self.company_result_var.set("请选择包含人民币的货币对")
            self.realtime_result_var.set("请选择包含人民币的货币对")
            self.company_result_number_var.set("")
            self.realtime_result_number_var.set("")
            self.company_rate_var.set("")
            self.realtime_rate_var.set("")
            self.status_var.set("货币对需要有一侧是人民币")
            return

        company_value, company_rate_text = self.calculate_company(amount, from_currency, to_currency)
        self.company_result_var.set(self.format_result(company_value, to_currency))
        self.company_result_number_var.set(self.format_number(company_value))
        self.company_rate_var.set(company_rate_text)
        self.fetch_realtime(amount, from_currency, to_currency)

    def calculate_company(self, amount, from_currency, to_currency):
        foreign = to_currency if from_currency == CNY else from_currency
        rate = Decimal(self.company_rates[foreign])
        if from_currency == CNY:
            result = money(amount / rate)
            rate_text = f"公司汇率：1 {foreign} = {rate} CNY"
        else:
            result = money(amount * rate)
            rate_text = f"公司汇率：1 {from_currency} = {rate} CNY"
        return result, rate_text

    def fetch_realtime(self, amount, from_currency, to_currency):
        cache_key = (from_currency, to_currency)
        if cache_key in self.realtime_cache:
            self.apply_realtime(amount, from_currency, to_currency, self.realtime_cache[cache_key])
            return

        self.realtime_request_id += 1
        request_id = self.realtime_request_id
        self.realtime_result_var.set("获取中...")
        self.realtime_result_number_var.set("")
        self.realtime_rate_var.set("")
        self.status_var.set("正在获取实时汇率")

        thread = threading.Thread(
            target=self.fetch_realtime_worker,
            args=(request_id, amount, from_currency, to_currency),
            daemon=True,
        )
        thread.start()

    def fetch_realtime_worker(self, request_id, amount, from_currency, to_currency):
        query = urllib.parse.urlencode({"base": from_currency, "symbols": to_currency})
        url = f"https://api.frankfurter.dev/v1/latest?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Portable-Currency-Converter/1.0",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
            rate = Decimal(str(data["rates"][to_currency]))
        except (urllib.error.URLError, TimeoutError, KeyError, InvalidOperation, json.JSONDecodeError) as exc:
            self.after(0, self.show_realtime_error, request_id, str(exc))
            return

        self.realtime_cache[(from_currency, to_currency)] = rate
        self.after(0, self.apply_realtime, amount, from_currency, to_currency, rate, request_id)

    def apply_realtime(self, amount, from_currency, to_currency, rate, request_id=None):
        if request_id is not None and request_id != self.realtime_request_id:
            return
        result = money(amount * rate)
        self.realtime_result_var.set(self.format_result(result, to_currency))
        self.realtime_result_number_var.set(self.format_number(result))

        inverse = (Decimal("1") / rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        display_rate = rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        self.realtime_rate_var.set(f"实时汇率：1 {from_currency} = {display_rate} {to_currency}；1 {to_currency} = {inverse} {from_currency}")
        self.status_var.set("实时汇率已更新")

    def show_realtime_error(self, request_id, error):
        if request_id != self.realtime_request_id:
            return
        self.realtime_result_var.set("实时汇率暂不可用")
        self.realtime_result_number_var.set("")
        self.realtime_rate_var.set("请检查网络连接，或稍后重试。")
        self.status_var.set(f"实时汇率获取失败：{error}")

    def format_result(self, value, currency):
        return f"{value} {currency}"

    def format_number(self, value):
        return format(value, "f")

    def copy_number(self, number_var):
        number = number_var.get().strip()
        if not number:
            self.status_var.set("当前没有可复制的数字")
            return
        self.clipboard_clear()
        self.clipboard_append(number)
        self.update_idletasks()
        self.status_var.set(f"已复制：{number}")

    def open_settings(self):
        window = tk.Toplevel(self)
        window.title("设置公司汇率")
        window.geometry("420x330")
        window.resizable(False, False)
        window.transient(self)
        window.grab_set()
        window.configure(bg=PALETTE["bg"])
        if ICON_ICO_PATH.exists():
            try:
                window.iconbitmap(str(ICON_ICO_PATH))
            except tk.TclError:
                pass
        if self.icon_image:
            window.iconphoto(True, self.icon_image)

        frame = ttk.Frame(window, style="Root.TFrame", padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="公司固定汇率", style="Header.TLabel").pack(anchor="w")
        ttk.Label(frame, text="填写 1 单位外币对应多少人民币。", style="Body.TLabel").pack(anchor="w", pady=(4, 18))

        entries = {}
        for currency in DEFAULT_COMPANY_RATES:
            row = tk.Frame(frame, bg=PALETTE["panel"], padx=14, pady=10, highlightthickness=1, highlightbackground=PALETTE["line"])
            row.pack(fill="x", pady=5)
            row.grid_columnconfigure(1, weight=1)
            ttk.Label(row, text=f"1 {currency} =", style="PanelBody.TLabel", width=10).grid(row=0, column=0, sticky="w")
            var = tk.StringVar(value=self.company_rates[currency])
            entry = ttk.Entry(row, textvariable=var, font=("Microsoft YaHei UI", 11))
            entry.grid(row=0, column=1, sticky="ew", padx=8)
            ttk.Label(row, text="CNY", style="PanelBody.TLabel", width=6).grid(row=0, column=2, sticky="e")
            entries[currency] = var

        actions = ttk.Frame(frame, style="Root.TFrame")
        actions.pack(fill="x", pady=(18, 0))
        ttk.Button(actions, text="取消", command=window.destroy).pack(side="right")
        ttk.Button(actions, text="保存", style="Accent.TButton", command=lambda: self.save_settings(window, entries)).pack(side="right", padx=(0, 10))

    def save_settings(self, window, entries):
        new_rates = {}
        for currency, var in entries.items():
            value = var.get().strip()
            try:
                decimal_value = Decimal(value)
            except InvalidOperation:
                messagebox.showerror("格式错误", f"{currency} 的汇率不是有效数字。", parent=window)
                return
            if decimal_value <= 0:
                messagebox.showerror("格式错误", f"{currency} 的汇率必须大于 0。", parent=window)
                return
            new_rates[currency] = str(decimal_value.normalize())

        self.company_rates = new_rates
        self.save_company_rates(new_rates)
        self.recalculate()
        window.destroy()
        self.status_var.set("公司汇率已保存")


if __name__ == "__main__":
    app = CurrencyConverterApp()
    app.mainloop()
