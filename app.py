import json
import os
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import ctypes
import csv
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


def enable_windows_high_dpi():
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


enable_windows_high_dpi()

if getattr(sys, "frozen", False):
    frozen_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    os.environ.setdefault("TCL_LIBRARY", str(frozen_root / "_tcl_data"))
    os.environ.setdefault("TK_LIBRARY", str(frozen_root / "_tk_data"))

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = APP_DIR

APP_CONFIG_DIR = Path(os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or Path.home()) / "PortableCurrencyConverter"
CONFIG_PATH = APP_CONFIG_DIR / "company_rates.json"
SETTINGS_PATH = APP_CONFIG_DIR / "settings.json"
HISTORY_PATH = APP_CONFIG_DIR / "history.json"
LEGACY_CONFIG_PATH = APP_DIR / "company_rates.json"
ICON_PATH = RESOURCE_DIR / "assets" / "app_icon.png"
ICON_ICO_PATH = RESOURCE_DIR / "assets" / "app_icon.ico"

CNY = "CNY"
CURRENCIES = {
    "CNY": "人民币 CNY",
    "USD": "美元 USD",
    "EUR": "欧元 EUR",
    "GBP": "英镑 GBP",
}

CURRENCY_SYMBOLS = {
    "CNY": "¥",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}

CURRENCY_DISPLAY = {
    code: f"{symbol}  {code}"
    for code, symbol in CURRENCY_SYMBOLS.items()
}

DEFAULT_COMPANY_RATES = {
    "USD": "6.6",
    "EUR": "7.2",
    "GBP": "8.9",
}

DEFAULT_SETTINGS = {
    "fee_amount": "30",
    "decimal_places": "2",
    "rounding": "ROUND_HALF_UP",
    "use_thousands": True,
    "default_from_currency": "CNY",
    "default_to_currency": "EUR",
    "default_amount": "3000",
    "auto_refresh": True,
    "network_timeout": "8",
}

ROUNDING_OPTIONS = {
    "四舍五入": ROUND_HALF_UP,
}

PALETTE = {
    "bg": "#f6f8fc",
    "shell": "#ffffff",
    "sidebar": "#f8fafd",
    "panel": "#ffffff",
    "ink": "#111827",
    "muted": "#6b7280",
    "line": "#d8e0ec",
    "blue": "#2f5fb8",
    "blue_dark": "#244b92",
    "green": "#2f8d62",
    "green_soft": "#e4f4ec",
    "blue_soft": "#edf4ff",
    "nav_active": "#eef5ff",
    "nav_text": "#2f5fb8",
    "warning": "#9a4d00",
    "danger": "#b42318",
}


def money(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class CurrencyConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.dpi_scale = max(1.0, self.winfo_fpixels("1i") / 96)
        self.title("便携汇率转换工具")
        self.geometry(self.scaled_geometry(1040, 760))
        self.minsize(self.scaled(940), self.scaled(680))

        self.icon_image = None
        self.load_app_icon()

        self.company_rates = self.load_company_rates()
        self.settings = self.load_settings()
        self.history = self.load_history()
        self.realtime_cache = {}
        self.realtime_request_id = 0
        self.last_realtime_at = ""
        self.current_record = None
        self.active_view = "quote"
        self.recalculate_after_id = None
        self.history_dirty = True

        self.amount_var = tk.StringVar(value=self.settings["default_amount"])
        self.from_currency_var = tk.StringVar(value=self.currency_label(self.settings["default_from_currency"]))
        self.to_currency_var = tk.StringVar(value=self.currency_label(self.settings["default_to_currency"]))
        self.company_result_var = tk.StringVar(value="")
        self.realtime_result_var = tk.StringVar(value="")
        self.company_result_number_var = tk.StringVar(value="")
        self.realtime_result_number_var = tk.StringVar(value="")
        self.company_rate_var = tk.StringVar(value="")
        self.realtime_rate_var = tk.StringVar(value="")
        self.risk_title_var = tk.StringVar(value="等待实时汇率")
        self.risk_detail_var = tk.StringVar(value="完成一次实时汇率刷新后，这里会显示差额、手续费和报价风险。")
        self.note_var = tk.StringVar(value="")
        self.history_search_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="准备就绪")
        self.status_time_var = tk.StringVar(value="")

        self.configure(bg=PALETTE["bg"])
        self.create_styles()
        self.create_widgets()
        self.bind_events()
        self.recalculate()

    def scaled(self, value):
        return int(round(value * self.dpi_scale))

    def scaled_geometry(self, width, height):
        return f"{self.scaled(width)}x{self.scaled(height)}"

    def currency_label(self, code):
        return CURRENCY_DISPLAY.get(code, code)

    def currency_code(self, value):
        value = str(value).strip()
        if value in CURRENCIES:
            return value
        code = value.split()[-1] if value else ""
        return code if code in CURRENCIES else value

    def set_currency(self, var, code):
        var.set(self.currency_label(code))

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
        style.configure("Shell.TFrame", background=PALETTE["shell"])
        style.configure("Sidebar.TFrame", background=PALETTE["sidebar"])
        style.configure("Panel.TFrame", background=PALETTE["panel"])
        style.configure("Header.TLabel", background=PALETTE["shell"], foreground=PALETTE["ink"], font=("Microsoft YaHei UI", 28, "bold"))
        style.configure("AppTitle.TLabel", background=PALETTE["sidebar"], foreground=PALETTE["ink"], font=("Microsoft YaHei UI", 12))
        style.configure("Title.TLabel", background=PALETTE["panel"], foreground=PALETTE["ink"], font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("Body.TLabel", background=PALETTE["shell"], foreground=PALETTE["muted"], font=("Microsoft YaHei UI", 11))
        style.configure("SidebarBody.TLabel", background=PALETTE["sidebar"], foreground=PALETTE["muted"], font=("Microsoft YaHei UI", 10))
        style.configure("PanelBody.TLabel", background=PALETTE["panel"], foreground=PALETTE["muted"], font=("Microsoft YaHei UI", 10))
        style.configure("Value.TLabel", background=PALETTE["panel"], foreground=PALETTE["ink"], font=("Microsoft YaHei UI", 26, "bold"))
        style.configure("Risk.TLabel", background=PALETTE["panel"], foreground=PALETTE["ink"], font=("Microsoft YaHei UI", 16, "bold"))
        style.configure("Status.TLabel", background=PALETTE["sidebar"], foreground=PALETTE["muted"], font=("Microsoft YaHei UI", 10))
        style.configure("TEntry", padding=(12, 9), fieldbackground="#ffffff", bordercolor=PALETTE["line"], lightcolor=PALETTE["line"])
        style.configure("TCombobox", padding=(12, 9), fieldbackground="#ffffff", bordercolor=PALETTE["line"], arrowcolor=PALETTE["ink"])
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(12, 8), borderwidth=0)
        style.configure("Accent.TButton", background=PALETTE["blue"], foreground="#ffffff", font=("Microsoft YaHei UI", 10, "bold"), padding=(16, 10), borderwidth=0)
        style.map("Accent.TButton", background=[("active", PALETTE["blue_dark"]), ("pressed", PALETTE["blue_dark"])], foreground=[("disabled", "#d7dde7")])
        style.configure("Copy.TButton", background="#f7faff", foreground=PALETTE["blue"], font=("Microsoft YaHei UI", 10, "bold"), padding=(10, 7), borderwidth=0)
        style.map("Copy.TButton", background=[("active", "#dce8f4"), ("pressed", "#dce8f4")], foreground=[("disabled", "#9aa9bd")])
        style.configure("Swap.TButton", background="#ecf2f8", foreground=PALETTE["ink"], font=("Microsoft YaHei UI", 12, "bold"), padding=(12, 8), borderwidth=0)
        style.map("Swap.TButton", background=[("active", "#dce8f4"), ("pressed", "#dce8f4")])

    def create_widgets(self):
        root = ttk.Frame(self, style="Shell.TFrame")
        root.pack(fill="both", expand=True)
        root.grid_columnconfigure(0, minsize=self.scaled(210))
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        sidebar = tk.Frame(root, bg=PALETTE["sidebar"], highlightthickness=1, highlightbackground=PALETTE["line"])
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.configure(width=self.scaled(210))
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(5, weight=1)

        brand = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=(22, 22, 18, 18))
        brand.grid(row=0, column=0, sticky="ew")
        if self.icon_image:
            tk.Label(brand, image=self.icon_image, bg=PALETTE["sidebar"], width=30, height=30).pack(side="left", padx=(0, 10))
        ttk.Label(brand, text="汇率转换工具", style="AppTitle.TLabel").pack(side="left")

        self.nav_buttons = {}
        self.create_nav_button(sidebar, "quote", "⇄", "汇率转换", 1, command=lambda: self.show_view("quote"))
        self.create_nav_button(sidebar, "history", "◷", "历史记录", 2, command=lambda: self.show_view("history"))
        self.create_nav_button(sidebar, "rates", "▥", "公司汇率", 3, command=self.open_settings)
        self.create_nav_button(sidebar, "settings", "⚙", "设置", 4, command=self.open_settings)

        status_box = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=(26, 0, 20, 30))
        status_box.grid(row=6, column=0, sticky="sew")
        ttk.Label(status_box, textvariable=self.status_var, style="Status.TLabel", wraplength=self.scaled(150)).pack(anchor="w")
        ttk.Label(status_box, textvariable=self.status_time_var, style="Status.TLabel", wraplength=self.scaled(150)).pack(anchor="w", pady=(6, 0))

        content = ttk.Frame(root, style="Shell.TFrame", padding=(44, 38, 44, 34))
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        self.quote_view = ttk.Frame(content, style="Shell.TFrame")
        self.history_view = ttk.Frame(content, style="Shell.TFrame")
        for view in (self.quote_view, self.history_view):
            view.grid(row=0, column=0, sticky="nsew")

        self.create_quote_view(self.quote_view)
        self.create_history_tab(self.history_view)
        self.show_view("quote")

    def create_nav_button(self, parent, key, icon, text, row, command):
        button = tk.Button(
            parent,
            text=f"{icon}   {text}",
            anchor="w",
            command=command,
            bd=0,
            padx=22,
            pady=14,
            font=("Microsoft YaHei UI", 11, "bold" if key == self.active_view else "normal"),
            bg=PALETTE["sidebar"],
            fg=PALETTE["muted"],
            activebackground=PALETTE["nav_active"],
            activeforeground=PALETTE["nav_text"],
            cursor="hand2",
        )
        button.grid(row=row, column=0, sticky="ew", padx=14, pady=4)
        self.nav_buttons[key] = button

    def show_view(self, view):
        self.active_view = view
        if view == "history":
            self.history_view.tkraise()
            if self.history_dirty:
                self.refresh_history_view()
                self.history_dirty = False
        else:
            self.quote_view.tkraise()
        self.update_nav_buttons()

    def update_nav_buttons(self):
        for key, button in self.nav_buttons.items():
            active = key == self.active_view
            button.configure(
                bg=PALETTE["nav_active"] if active else PALETTE["sidebar"],
                fg=PALETTE["nav_text"] if active else PALETTE["muted"],
                font=("Microsoft YaHei UI", 11, "bold" if active else "normal"),
            )

    def create_quote_view(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        header = ttk.Frame(parent, style="Shell.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ttk.Label(header, text="汇率转换", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="人民币与外币双向转换，同时查看公司报价汇率与实时参考汇率。", style="Body.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(header, text="⚙  设置公司汇率", style="Copy.TButton", command=self.open_settings).grid(row=0, column=1, rowspan=2, sticky="e")

        input_panel = tk.Frame(parent, bg=PALETTE["panel"], padx=26, pady=24, highlightthickness=1, highlightbackground=PALETTE["line"])
        input_panel.grid(row=1, column=0, sticky="ew", pady=(34, 24))
        for column in (0, 1, 3, 4):
            input_panel.grid_columnconfigure(column, weight=1)
        input_panel.grid_columnconfigure(2, minsize=70)
        input_panel.grid_columnconfigure(5, minsize=96)

        ttk.Label(input_panel, text="金额", style="PanelBody.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(input_panel, text="源货币", style="PanelBody.TLabel").grid(row=0, column=1, sticky="w", padx=(18, 0))
        ttk.Label(input_panel, text="目标货币", style="PanelBody.TLabel").grid(row=0, column=3, sticky="w")
        ttk.Label(input_panel, text="备注", style="PanelBody.TLabel").grid(row=0, column=4, sticky="w", padx=(18, 0))

        ttk.Entry(input_panel, textvariable=self.amount_var, font=("Microsoft YaHei UI", 18), width=15).grid(row=1, column=0, sticky="ew", pady=(12, 0), padx=(0, 18), ipady=4)
        currency_values = [self.currency_label(code) for code in CURRENCIES]
        self.from_combo = ttk.Combobox(input_panel, textvariable=self.from_currency_var, values=currency_values, state="readonly", font=("Microsoft YaHei UI", 12))
        self.from_combo.grid(row=1, column=1, sticky="ew", pady=(12, 0), padx=(18, 12), ipady=4)
        ttk.Button(input_panel, text="⇄", style="Swap.TButton", width=4, command=self.swap_currencies).grid(row=1, column=2, pady=(12, 0))
        self.to_combo = ttk.Combobox(input_panel, textvariable=self.to_currency_var, values=currency_values, state="readonly", font=("Microsoft YaHei UI", 12))
        self.to_combo.grid(row=1, column=3, sticky="ew", pady=(12, 0), padx=(12, 0), ipady=4)
        ttk.Entry(input_panel, textvariable=self.note_var, font=("Microsoft YaHei UI", 11), width=18).grid(row=1, column=4, sticky="ew", pady=(12, 0), padx=(18, 0), ipady=4)
        ttk.Button(input_panel, text="刷新实时", style="Copy.TButton", command=self.refresh_realtime_now).grid(row=1, column=5, sticky="ew", pady=(12, 0), padx=(18, 0))

        body = ttk.Frame(parent, style="Shell.TFrame")
        body.grid(row=2, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        results = ttk.Frame(body, style="Shell.TFrame")
        results.grid(row=0, column=0, sticky="nsew")
        results.grid_columnconfigure(0, weight=1)
        results.grid_columnconfigure(1, weight=1)
        results.grid_rowconfigure(0, weight=1)

        self.create_result_card(results, 0, "▥  公司固定汇率", self.company_result_var, self.company_result_number_var, self.company_rate_var, PALETTE["blue"], PALETTE["blue_soft"])
        self.create_result_card(results, 1, "↗  实时参考汇率", self.realtime_result_var, self.realtime_result_number_var, self.realtime_rate_var, PALETTE["green"], PALETTE["green_soft"])
        self.create_risk_panel(body)

    def create_result_card(self, parent, column, title, value_var, number_var, rate_var, accent, soft):
        card = tk.Frame(parent, bg=PALETTE["panel"], padx=24, pady=24, highlightthickness=1, highlightbackground=PALETTE["line"])
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 16) if column == 0 else (16, 0))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)

        top = tk.Frame(card, bg=PALETTE["panel"])
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        ttk.Label(top, text=title, style="Title.TLabel").grid(row=0, column=0, sticky="w")

        tk.Frame(card, bg=accent, height=2).grid(row=1, column=0, sticky="ew", pady=(18, 24))
        value_row = tk.Frame(card, bg=PALETTE["panel"])
        value_row.grid(row=2, column=0, sticky="nsew")
        value_row.grid_columnconfigure(0, weight=1)
        value_label = ttk.Label(value_row, textvariable=value_var, style="Value.TLabel", wraplength=360)
        value_label.grid(row=0, column=0, sticky="nw")
        if accent == PALETTE["blue"]:
            value_label.configure(foreground=PALETTE["blue"])
        else:
            value_label.configure(foreground=PALETTE["green"])
        ttk.Button(value_row, text="复制", style="Copy.TButton", command=lambda: self.copy_number(number_var)).grid(row=0, column=1, sticky="ne", padx=(12, 0), pady=(3, 0))
        ttk.Label(card, textvariable=rate_var, style="PanelBody.TLabel", wraplength=420).grid(row=3, column=0, sticky="sw", pady=(22, 0))

    def create_risk_panel(self, parent):
        panel = tk.Frame(parent, bg=PALETTE["panel"], padx=22, pady=18, highlightthickness=1, highlightbackground=PALETTE["line"])
        panel.grid(row=1, column=0, sticky="ew", pady=(18, 0))
        panel.grid_columnconfigure(0, weight=1)

        top = tk.Frame(panel, bg=PALETTE["panel"])
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        ttk.Label(top, textvariable=self.risk_title_var, style="Risk.TLabel", wraplength=620).grid(row=0, column=0, sticky="w")
        actions = ttk.Frame(top, style="Panel.TFrame")
        actions.grid(row=0, column=1, sticky="e")
        ttk.Button(actions, text="复制报价文本", style="Copy.TButton", command=self.copy_quote_text).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="导出 CSV", style="Copy.TButton", command=self.export_csv).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="导出 Excel", style="Copy.TButton", command=self.export_excel).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="导出 PDF", style="Copy.TButton", command=self.export_pdf).pack(side="left")

        ttk.Label(panel, textvariable=self.risk_detail_var, style="PanelBody.TLabel", wraplength=980, justify="left").grid(row=1, column=0, sticky="ew", pady=(12, 0))

    def create_history_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        header = ttk.Frame(parent, style="Shell.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ttk.Label(header, text="历史记录", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="搜索、复用最近的报价分析记录。", style="Body.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))

        filters = ttk.Frame(parent, style="Shell.TFrame")
        filters.grid(row=1, column=0, sticky="ew", pady=(28, 14))
        filters.grid_columnconfigure(0, weight=1)
        ttk.Entry(filters, textvariable=self.history_search_var, font=("Microsoft YaHei UI", 11)).grid(row=0, column=0, sticky="ew", padx=(0, 10), ipady=3)
        ttk.Button(filters, text="搜索", style="Copy.TButton", command=self.refresh_history_view).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(filters, text="再次计算", style="Accent.TButton", command=self.reuse_selected_history).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(filters, text="清空历史", command=self.clear_history).grid(row=0, column=3)

        table_frame = tk.Frame(parent, bg=PALETTE["panel"], highlightthickness=1, highlightbackground=PALETTE["line"])
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        columns = ("time", "pair", "amount", "company", "realtime", "net", "risk", "note")
        self.history_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        headings = {
            "time": "时间",
            "pair": "货币对",
            "amount": "金额",
            "company": "公司报价",
            "realtime": "实时参考",
            "net": "净收益/损失",
            "risk": "风险",
            "note": "备注",
        }
        widths = {"time": 150, "pair": 90, "amount": 110, "company": 130, "realtime": 130, "net": 130, "risk": 90, "note": 180}
        for col in columns:
            self.history_tree.heading(col, text=headings[col])
            self.history_tree.column(col, width=widths[col], anchor="w")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def bind_events(self):
        self.amount_var.trace_add("write", lambda *_: self.schedule_recalculate())
        self.note_var.trace_add("write", lambda *_: self.update_current_note())
        self.history_search_var.trace_add("write", lambda *_: self.schedule_history_refresh())
        self.from_combo.bind("<<ComboboxSelected>>", lambda _: self.on_currency_changed("from"))
        self.to_combo.bind("<<ComboboxSelected>>", lambda _: self.on_currency_changed("to"))

    def schedule_recalculate(self):
        if self.recalculate_after_id is not None:
            self.after_cancel(self.recalculate_after_id)
        self.recalculate_after_id = self.after(250, self.run_scheduled_recalculate)

    def run_scheduled_recalculate(self):
        self.recalculate_after_id = None
        self.recalculate()

    def schedule_history_refresh(self):
        self.history_dirty = True
        if self.active_view == "history":
            self.after(120, self.refresh_history_view)

    def load_company_rates(self):
        config_path = CONFIG_PATH if CONFIG_PATH.exists() else LEGACY_CONFIG_PATH
        if not config_path.exists():
            self.save_company_rates(DEFAULT_COMPANY_RATES)
            return DEFAULT_COMPANY_RATES.copy()

        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
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
        if config_path == LEGACY_CONFIG_PATH:
            self.save_company_rates(rates)
            try:
                LEGACY_CONFIG_PATH.unlink()
            except OSError:
                pass
        return rates

    def save_company_rates(self, rates):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(rates, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_settings(self):
        settings = DEFAULT_SETTINGS.copy()
        if SETTINGS_PATH.exists():
            try:
                data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                settings.update({key: data[key] for key in settings if key in data})
            except (OSError, json.JSONDecodeError):
                pass
        for key in ("default_from_currency", "default_to_currency"):
            if settings[key] not in CURRENCIES:
                settings[key] = DEFAULT_SETTINGS[key]
        if settings["default_from_currency"] == settings["default_to_currency"]:
            settings["default_from_currency"] = "CNY"
            settings["default_to_currency"] = "EUR"
        for key in ("fee_amount", "default_amount", "network_timeout"):
            try:
                if Decimal(str(settings[key])) < 0:
                    settings[key] = DEFAULT_SETTINGS[key]
            except InvalidOperation:
                settings[key] = DEFAULT_SETTINGS[key]
        try:
            if int(settings["decimal_places"]) < 0:
                settings["decimal_places"] = DEFAULT_SETTINGS["decimal_places"]
        except (TypeError, ValueError):
            settings["decimal_places"] = DEFAULT_SETTINGS["decimal_places"]
        return settings

    def save_settings(self):
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_history(self):
        if not HISTORY_PATH.exists():
            return []
        try:
            data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []

    def save_history(self):
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text(json.dumps(self.history[:200], ensure_ascii=False, indent=2), encoding="utf-8")

    def on_currency_changed(self, side):
        from_currency = self.currency_code(self.from_currency_var.get())
        to_currency = self.currency_code(self.to_currency_var.get())

        if from_currency == to_currency:
            if side == "from":
                self.set_currency(self.to_currency_var, "EUR" if from_currency == CNY else CNY)
            else:
                self.set_currency(self.from_currency_var, CNY if to_currency != CNY else "USD")

        if self.currency_code(self.from_currency_var.get()) != CNY and self.currency_code(self.to_currency_var.get()) != CNY:
            if side == "from":
                self.set_currency(self.to_currency_var, CNY)
            else:
                self.set_currency(self.from_currency_var, CNY)

        self.recalculate()

    def swap_currencies(self):
        old_from = self.currency_code(self.from_currency_var.get())
        self.set_currency(self.from_currency_var, self.currency_code(self.to_currency_var.get()))
        self.set_currency(self.to_currency_var, old_from)
        self.on_currency_changed("to")

    def recalculate(self):
        amount_text = self.amount_var.get().strip()
        from_currency = self.currency_code(self.from_currency_var.get())
        to_currency = self.currency_code(self.to_currency_var.get())

        try:
            amount = Decimal(amount_text)
        except InvalidOperation:
            self.current_record = None
            self.company_result_var.set("请输入有效金额")
            self.realtime_result_var.set("请输入有效金额")
            self.company_result_number_var.set("")
            self.realtime_result_number_var.set("")
            self.company_rate_var.set("")
            self.realtime_rate_var.set("")
            self.risk_title_var.set("无法分析报价风险")
            self.risk_detail_var.set("请输入有效金额后再计算。")
            self.status_var.set("金额格式不正确")
            return

        if amount < 0:
            self.current_record = None
            self.company_result_var.set("金额不能为负数")
            self.realtime_result_var.set("金额不能为负数")
            self.company_result_number_var.set("")
            self.realtime_result_number_var.set("")
            self.company_rate_var.set("")
            self.realtime_rate_var.set("")
            self.risk_title_var.set("无法分析报价风险")
            self.risk_detail_var.set("金额不能为负数。")
            self.status_var.set("金额不能为负数")
            return

        if from_currency == to_currency or (from_currency != CNY and to_currency != CNY):
            self.current_record = None
            self.company_result_var.set("请选择包含人民币的货币对")
            self.realtime_result_var.set("请选择包含人民币的货币对")
            self.company_result_number_var.set("")
            self.realtime_result_number_var.set("")
            self.company_rate_var.set("")
            self.realtime_rate_var.set("")
            self.risk_title_var.set("无法分析报价风险")
            self.risk_detail_var.set("货币对需要有一侧是人民币。")
            self.status_var.set("货币对需要有一侧是人民币")
            return

        company_value, company_rate_text = self.calculate_company(amount, from_currency, to_currency)
        self.company_result_var.set(self.format_result(company_value, to_currency))
        self.company_result_number_var.set(self.format_number(company_value))
        self.company_rate_var.set(company_rate_text)
        self.risk_title_var.set("等待实时汇率")
        self.risk_detail_var.set("实时汇率返回后会自动计算差额、手续费和净收益。")
        if self.settings.get("auto_refresh", True):
            self.fetch_realtime(amount, from_currency, to_currency)
        else:
            self.realtime_result_var.set("等待手动刷新")
            self.realtime_result_number_var.set("")
            self.realtime_rate_var.set("已关闭自动刷新，请点击“刷新实时”。")
            self.risk_detail_var.set("已关闭自动刷新，点击“刷新实时”后再判断报价风险。")

    def refresh_realtime_now(self):
        amount_text = self.amount_var.get().strip()
        from_currency = self.currency_code(self.from_currency_var.get())
        to_currency = self.currency_code(self.to_currency_var.get())
        try:
            amount = Decimal(amount_text)
        except InvalidOperation:
            self.status_var.set("金额格式不正确")
            return
        if amount < 0 or from_currency == to_currency or (from_currency != CNY and to_currency != CNY):
            self.status_var.set("请先输入有效金额和包含人民币的货币对")
            return
        self.fetch_realtime(amount, from_currency, to_currency, force=True)

    def calculate_company(self, amount, from_currency, to_currency):
        foreign = to_currency if from_currency == CNY else from_currency
        rate = Decimal(self.company_rates[foreign])
        if from_currency == CNY:
            result = self.round_money(amount / rate)
            rate_text = f"公司汇率：1 {foreign} = {rate} CNY"
        else:
            result = self.round_money(amount * rate)
            rate_text = f"公司汇率：1 {from_currency} = {rate} CNY"
        return result, rate_text

    def fetch_realtime(self, amount, from_currency, to_currency, force=False):
        cache_key = (from_currency, to_currency)
        if not force and cache_key in self.realtime_cache:
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
            timeout = float(self.settings.get("network_timeout", "8"))
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            rate = Decimal(str(data["rates"][to_currency]))
            updated_at = str(data.get("date") or datetime.now().strftime("%Y-%m-%d"))
        except (urllib.error.URLError, TimeoutError, KeyError, InvalidOperation, json.JSONDecodeError) as exc:
            self.after(0, self.show_realtime_error, request_id, str(exc))
            return

        self.realtime_cache[(from_currency, to_currency)] = rate
        self.after(0, self.apply_realtime, amount, from_currency, to_currency, rate, request_id, updated_at)

    def apply_realtime(self, amount, from_currency, to_currency, rate, request_id=None, updated_at=None):
        if request_id is not None and request_id != self.realtime_request_id:
            return
        result = self.round_money(amount * rate)
        self.realtime_result_var.set(self.format_result(result, to_currency))
        self.realtime_result_number_var.set(self.format_number(result))

        inverse = (Decimal("1") / rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        display_rate = rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        self.last_realtime_at = updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.realtime_rate_var.set(f"实时汇率：1 {from_currency} = {display_rate} {to_currency}；1 {to_currency} = {inverse} {from_currency}")
        self.update_risk_analysis(amount, from_currency, to_currency, rate, result)
        self.status_var.set("实时汇率已更新")
        self.status_time_var.set(f"更新于 {datetime.now().strftime('%H:%M:%S')}")

    def show_realtime_error(self, request_id, error):
        if request_id != self.realtime_request_id:
            return
        self.realtime_result_var.set("实时汇率暂不可用")
        self.realtime_result_number_var.set("")
        self.realtime_rate_var.set("请检查网络连接，或稍后重试。")
        self.risk_title_var.set("无法分析报价风险")
        self.risk_detail_var.set("实时汇率不可用，无法折算手续费和判断净收益。")
        self.status_var.set(f"实时汇率获取失败：{error}")
        self.status_time_var.set("")

    def update_risk_analysis(self, amount, from_currency, to_currency, realtime_rate, realtime_value):
        company_value, _ = self.calculate_company(amount, from_currency, to_currency)
        foreign = to_currency if from_currency == CNY else from_currency
        foreign_to_cny = Decimal("1") / realtime_rate if from_currency == CNY else realtime_rate
        fee_foreign = Decimal(str(self.settings.get("fee_amount", "30")))
        fee_cny = fee_foreign * foreign_to_cny

        if from_currency == CNY:
            quote_diff_foreign = company_value - realtime_value
            quote_diff_cny = quote_diff_foreign * foreign_to_cny
            percent = (quote_diff_cny / amount * Decimal("100")) if amount != 0 else Decimal("0")
        else:
            quote_diff_cny = company_value - realtime_value
            percent = (quote_diff_cny / realtime_value * Decimal("100")) if realtime_value != 0 else Decimal("0")

        net_cny = quote_diff_cny - fee_cny
        is_safe = net_cny >= 0
        risk_text = "安全" if is_safe else "有亏损风险"
        profit_label = "预计盈利" if is_safe else "预计亏损"
        self.risk_title_var.set(f"{'报价安全' if is_safe else '报价风险'}：{profit_label} {self.format_currency(abs(net_cny), CNY)}")
        self.risk_detail_var.set(
            f"差额收益：{self.format_currency(quote_diff_cny, CNY)}，差异 {self.format_percent(percent)}；"
            f"手续费成本：{self.format_currency(fee_foreign, foreign)} ≈ {self.format_currency(fee_cny, CNY)}；"
            f"{profit_label}：{self.format_currency(abs(net_cny), CNY)}。\n"
            f"判断逻辑：手续费折人民币必须小于公司汇率与实时汇率形成的人民币差额。当前结论：{risk_text}。"
        )

        self.current_record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "amount": self.format_number(amount),
            "from_currency": from_currency,
            "to_currency": to_currency,
            "company_result": self.format_currency(company_value, to_currency),
            "realtime_result": self.format_currency(realtime_value, to_currency),
            "company_rate": self.company_rate_var.get(),
            "realtime_rate": self.realtime_rate_var.get(),
            "quote_diff_cny": self.format_currency(quote_diff_cny, CNY),
            "difference_percent": self.format_percent(percent),
            "fee_foreign": self.format_currency(fee_foreign, foreign),
            "fee_cny": self.format_currency(fee_cny, CNY),
            "net_cny": self.format_currency(net_cny, CNY),
            "risk": risk_text,
            "updated_at": self.last_realtime_at,
            "note": self.note_var.get().strip(),
        }
        self.add_history_record(self.current_record)

    def format_result(self, value, currency):
        return self.format_currency(value, currency)

    def format_number(self, value):
        places = int(self.settings.get("decimal_places", "2"))
        value = self.round_decimal(Decimal(value), places)
        text = f"{value:,.{places}f}" if self.settings.get("use_thousands") else f"{value:.{places}f}"
        return text

    def format_currency(self, value, currency):
        symbol = CURRENCY_SYMBOLS.get(currency, "")
        return f"{symbol}{self.format_number(value)} {currency}"

    def format_percent(self, value):
        value = self.round_decimal(Decimal(value), 2)
        return f"{value:.2f}%"

    def round_money(self, value):
        return self.round_decimal(value, int(self.settings.get("decimal_places", "2")))

    def round_decimal(self, value, places):
        quant = Decimal("1").scaleb(-places)
        rounding = ROUNDING_OPTIONS.get("四舍五入", ROUND_HALF_UP)
        return value.quantize(quant, rounding=rounding)

    def copy_number(self, number_var):
        number = number_var.get().strip()
        if not number:
            self.status_var.set("当前没有可复制的数字")
            return
        self.clipboard_clear()
        self.clipboard_append(number)
        self.update_idletasks()
        self.status_var.set(f"已复制：{number}")

    def update_current_note(self):
        if self.current_record is not None:
            self.current_record["note"] = self.note_var.get().strip()

    def add_history_record(self, record):
        signature = (record["amount"], record["from_currency"], record["to_currency"], record["company_result"], record["realtime_result"])
        if self.history:
            latest = self.history[0]
            latest_signature = (latest.get("amount"), latest.get("from_currency"), latest.get("to_currency"), latest.get("company_result"), latest.get("realtime_result"))
            if latest_signature == signature:
                self.history[0] = record
            else:
                self.history.insert(0, record)
        else:
            self.history.insert(0, record)
        self.history = self.history[:200]
        self.save_history()
        self.history_dirty = True
        if self.active_view == "history" and hasattr(self, "history_tree"):
            self.refresh_history_view()
            self.history_dirty = False

    def refresh_history_view(self):
        if not hasattr(self, "history_tree"):
            return
        query = self.history_search_var.get().strip().lower()
        self.history_tree.delete(*self.history_tree.get_children())
        for index, record in enumerate(self.history):
            text = " ".join(str(value) for value in record.values()).lower()
            if query and query not in text:
                continue
            self.history_tree.insert("", "end", iid=str(index), values=(
                record.get("time", ""),
                f"{record.get('from_currency', '')}->{record.get('to_currency', '')}",
                record.get("amount", ""),
                record.get("company_result", ""),
                record.get("realtime_result", ""),
                record.get("net_cny", ""),
                record.get("risk", ""),
                record.get("note", ""),
            ))

    def reuse_selected_history(self):
        selection = self.history_tree.selection()
        if not selection:
            self.status_var.set("请先选择一条历史记录")
            return
        record = self.history[int(selection[0])]
        self.amount_var.set(str(record.get("amount", "0")).replace(",", ""))
        self.set_currency(self.from_currency_var, record.get("from_currency", "CNY"))
        self.set_currency(self.to_currency_var, record.get("to_currency", "EUR"))
        self.note_var.set(record.get("note", ""))
        self.status_var.set("已载入历史记录")
        self.recalculate()

    def clear_history(self):
        if not messagebox.askyesno("清空历史", "确定要清空所有历史记录吗？", parent=self):
            return
        self.history = []
        self.save_history()
        self.refresh_history_view()
        self.status_var.set("历史记录已清空")

    def quote_text(self):
        if not self.current_record:
            return ""
        record = self.current_record
        return "\n".join([
            "汇率报价分析",
            f"时间：{record['time']}",
            f"金额：{record['amount']} {record['from_currency']} -> {record['to_currency']}",
            f"公司汇率结果：{record['company_result']}",
            f"实时汇率结果：{record['realtime_result']}",
            f"公司汇率：{record['company_rate']}",
            f"实时汇率：{record['realtime_rate']}",
            f"报价差额：{record['quote_diff_cny']}",
            f"差异百分比：{record['difference_percent']}",
            f"手续费：{record['fee_foreign']}，折合 {record['fee_cny']}",
            f"净收益/损失：{record['net_cny']}",
            f"风险判断：{record['risk']}",
            f"实时汇率日期：{record['updated_at']}",
            f"备注：{record['note']}",
        ])

    def copy_quote_text(self):
        text = self.quote_text()
        if not text:
            self.status_var.set("当前没有可复制的报价分析")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()
        self.status_var.set("报价文本已复制")

    def export_csv(self):
        if not self.current_record:
            self.status_var.set("当前没有可导出的报价分析")
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile=f"汇率报价分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not path:
            return
        fields = self.export_fields()
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow([label for label, _ in fields])
            writer.writerow([value for _, value in fields])
        self.status_var.set("已导出 CSV")
        self.status_time_var.set(Path(path).name)

    def export_excel(self):
        if not self.current_record:
            self.status_var.set("当前没有可导出的报价分析")
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".xlsx",
            filetypes=[("Excel 工作簿", "*.xlsx")],
            initialfile=f"汇率报价分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        )
        if not path:
            return
        self.write_xlsx(path, self.export_fields())
        self.status_var.set("已导出 Excel")
        self.status_time_var.set(Path(path).name)

    def export_pdf(self):
        if not self.current_record:
            self.status_var.set("当前没有可导出的报价分析")
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".pdf",
            filetypes=[("PDF 文件", "*.pdf")],
            initialfile=f"汇率报价分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )
        if not path:
            return
        self.write_simple_pdf(path, self.quote_text())
        self.status_var.set("已导出 PDF")
        self.status_time_var.set(Path(path).name)

    def export_fields(self):
        record = self.current_record or {}
        return [
            ("时间", record.get("time", "")),
            ("金额", f"{record.get('amount', '')} {record.get('from_currency', '')}"),
            ("目标币种", record.get("to_currency", "")),
            ("公司汇率结果", record.get("company_result", "")),
            ("实时汇率结果", record.get("realtime_result", "")),
            ("公司汇率", record.get("company_rate", "")),
            ("实时汇率", record.get("realtime_rate", "")),
            ("报价差额", record.get("quote_diff_cny", "")),
            ("差异百分比", record.get("difference_percent", "")),
            ("手续费", f"{record.get('fee_foreign', '')} / {record.get('fee_cny', '')}"),
            ("净收益/损失", record.get("net_cny", "")),
            ("风险判断", record.get("risk", "")),
            ("实时汇率日期", record.get("updated_at", "")),
            ("备注", record.get("note", "")),
        ]

    def write_xlsx(self, path, fields):
        def xml_escape(value):
            return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        rows = []
        for row_index, row in enumerate((("字段", "内容"), *fields), start=1):
            cells = []
            for col_index, value in enumerate(row, start=1):
                col = chr(64 + col_index)
                cells.append(f'<c r="{col}{row_index}" t="inlineStr"><is><t>{xml_escape(value)}</t></is></c>')
            rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<cols><col min="1" max="1" width="18" customWidth="1"/><col min="2" max="2" width="64" customWidth="1"/></cols>'
            f'<sheetData>{"".join(rows)}</sheetData></worksheet>'
        )
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as workbook:
            workbook.writestr("[Content_Types].xml", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                '</Types>'
            ))
            workbook.writestr("_rels/.rels", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                '</Relationships>'
            ))
            workbook.writestr("xl/workbook.xml", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="报价分析" sheetId="1" r:id="rId1"/></sheets></workbook>'
            ))
            workbook.writestr("xl/_rels/workbook.xml.rels", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                '</Relationships>'
            ))
            workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    def write_simple_pdf(self, path, text):
        lines = text.splitlines()
        content_lines = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
        for index, line in enumerate(lines):
            if index:
                content_lines.append("T*")
            encoded = line.encode("utf-16-be").hex().upper()
            content_lines.append(f"<{encoded}> Tj")
        content_lines.append("ET")
        stream = "\n".join(content_lines).encode("ascii")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 6 0 R >>",
            b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H /DescendantFonts [5 0 R] >>",
            b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 2 >> >>",
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        ]
        data = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for index, obj in enumerate(objects, start=1):
            offsets.append(len(data))
            data.extend(f"{index} 0 obj\n".encode("ascii"))
            data.extend(obj)
            data.extend(b"\nendobj\n")
        xref = len(data)
        data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
        for offset in offsets[1:]:
            data.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        data.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii"))
        Path(path).write_bytes(bytes(data))

    def open_settings(self):
        window = tk.Toplevel(self)
        window.title("设置")
        window.geometry(self.scaled_geometry(680, 640))
        window.minsize(self.scaled(620), self.scaled(560))
        window.resizable(True, True)
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

        frame = ttk.Frame(window, style="Root.TFrame", padding=(28, 26, 28, 22))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="公司汇率与专业设置", style="Header.TLabel").pack(anchor="w")
        ttk.Label(frame, text="填写 1 单位外币对应多少人民币，并设置报价风控参数。", style="Body.TLabel").pack(anchor="w", pady=(4, 18))

        entries = {}
        ttk.Label(frame, text="公司固定汇率", style="Body.TLabel").pack(anchor="w")
        for currency in DEFAULT_COMPANY_RATES:
            row = tk.Frame(frame, bg=PALETTE["panel"], padx=18, pady=12, highlightthickness=1, highlightbackground=PALETTE["line"])
            row.pack(fill="x", pady=5)
            row.grid_columnconfigure(1, weight=1)
            ttk.Label(row, text=f"1 {currency} =", style="PanelBody.TLabel", width=10).grid(row=0, column=0, sticky="w")
            var = tk.StringVar(value=self.company_rates[currency])
            entry = ttk.Entry(row, textvariable=var, font=("Microsoft YaHei UI", 11))
            entry.grid(row=0, column=1, sticky="ew", padx=8)
            ttk.Label(row, text="CNY", style="PanelBody.TLabel", width=6).grid(row=0, column=2, sticky="e")
            entries[currency] = var

        settings_panel = tk.Frame(frame, bg=PALETTE["panel"], padx=18, pady=14, highlightthickness=1, highlightbackground=PALETTE["line"])
        settings_panel.pack(fill="x", pady=(14, 0))
        settings_panel.grid_columnconfigure(1, weight=1)
        settings_panel.grid_columnconfigure(3, weight=1)

        setting_vars = {
            "fee_amount": tk.StringVar(value=self.settings["fee_amount"]),
            "decimal_places": tk.StringVar(value=self.settings["decimal_places"]),
            "default_amount": tk.StringVar(value=self.settings["default_amount"]),
            "network_timeout": tk.StringVar(value=self.settings["network_timeout"]),
            "default_from_currency": tk.StringVar(value=self.settings["default_from_currency"]),
            "default_to_currency": tk.StringVar(value=self.settings["default_to_currency"]),
            "use_thousands": tk.BooleanVar(value=bool(self.settings["use_thousands"])),
            "auto_refresh": tk.BooleanVar(value=bool(self.settings["auto_refresh"])),
        }

        ttk.Label(settings_panel, text="手续费金额", style="PanelBody.TLabel").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(settings_panel, textvariable=setting_vars["fee_amount"]).grid(row=0, column=1, sticky="ew", padx=(10, 20), pady=6)
        ttk.Label(settings_panel, text="外币", style="PanelBody.TLabel").grid(row=0, column=2, sticky="w", pady=6)

        ttk.Label(settings_panel, text="小数位", style="PanelBody.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Combobox(settings_panel, textvariable=setting_vars["decimal_places"], values=["0", "1", "2", "3", "4"], state="readonly").grid(row=1, column=1, sticky="ew", padx=(10, 20), pady=6)
        ttk.Checkbutton(settings_panel, text="千分位显示", variable=setting_vars["use_thousands"]).grid(row=1, column=2, columnspan=2, sticky="w", pady=6)

        ttk.Label(settings_panel, text="默认金额", style="PanelBody.TLabel").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(settings_panel, textvariable=setting_vars["default_amount"]).grid(row=2, column=1, sticky="ew", padx=(10, 20), pady=6)
        ttk.Checkbutton(settings_panel, text="启动/变更时自动刷新", variable=setting_vars["auto_refresh"]).grid(row=2, column=2, columnspan=2, sticky="w", pady=6)

        ttk.Label(settings_panel, text="默认源币种", style="PanelBody.TLabel").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Combobox(settings_panel, textvariable=setting_vars["default_from_currency"], values=list(CURRENCIES.keys()), state="readonly").grid(row=3, column=1, sticky="ew", padx=(10, 20), pady=6)
        ttk.Label(settings_panel, text="默认目标币种", style="PanelBody.TLabel").grid(row=3, column=2, sticky="w", pady=6)
        ttk.Combobox(settings_panel, textvariable=setting_vars["default_to_currency"], values=list(CURRENCIES.keys()), state="readonly").grid(row=3, column=3, sticky="ew", padx=(10, 0), pady=6)

        ttk.Label(settings_panel, text="网络超时秒数", style="PanelBody.TLabel").grid(row=4, column=0, sticky="w", pady=6)
        ttk.Entry(settings_panel, textvariable=setting_vars["network_timeout"]).grid(row=4, column=1, sticky="ew", padx=(10, 20), pady=6)
        ttk.Label(settings_panel, text="舍入规则：四舍五入", style="PanelBody.TLabel").grid(row=4, column=2, columnspan=2, sticky="w", pady=6)

        actions = ttk.Frame(frame, style="Root.TFrame")
        actions.pack(fill="x", pady=(18, 0))
        ttk.Button(actions, text="取消", command=window.destroy).pack(side="right")
        ttk.Button(actions, text="保存", style="Accent.TButton", command=lambda: self.save_settings_window(window, entries, setting_vars)).pack(side="right", padx=(0, 10))

    def save_settings_window(self, window, entries, setting_vars):
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

        for key in ("fee_amount", "default_amount", "network_timeout"):
            value = setting_vars[key].get().strip()
            try:
                decimal_value = Decimal(value)
            except InvalidOperation:
                messagebox.showerror("格式错误", f"{key} 不是有效数字。", parent=window)
                return
            if decimal_value < 0:
                messagebox.showerror("格式错误", f"{key} 不能为负数。", parent=window)
                return

        if setting_vars["default_from_currency"].get() == setting_vars["default_to_currency"].get():
            messagebox.showerror("格式错误", "默认源币种和目标币种不能相同。", parent=window)
            return

        self.company_rates = new_rates
        self.save_company_rates(new_rates)
        self.settings.update({
            "fee_amount": setting_vars["fee_amount"].get().strip(),
            "decimal_places": setting_vars["decimal_places"].get(),
            "default_amount": setting_vars["default_amount"].get().strip(),
            "network_timeout": setting_vars["network_timeout"].get().strip(),
            "default_from_currency": setting_vars["default_from_currency"].get(),
            "default_to_currency": setting_vars["default_to_currency"].get(),
            "use_thousands": bool(setting_vars["use_thousands"].get()),
            "auto_refresh": bool(setting_vars["auto_refresh"].get()),
        })
        self.save_settings()
        self.recalculate()
        window.destroy()
        self.status_var.set("设置已保存")


if __name__ == "__main__":
    app = CurrencyConverterApp()
    app.mainloop()
