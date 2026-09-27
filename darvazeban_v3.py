# -*- coding: utf-8 -*-
"""دروازه‌بان: برنامه رومیزی ثبت ورود و خروج خودروها."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog

APP_NAME = "دروازه‌بان"
DEFAULT_PASSWORD = "1234"

# نام ماه‌های شمسی
JALALI_MONTHS = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def app_directory():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


DATA_FILE = app_directory() / "darvazeban_data.json"


def gregorian_to_jalali(gy, gm, gd):
    """تبدیل تاریخ میلادی به شمسی (بدون کتابخانه خارجی)"""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666
        + (365 * gy)
        + ((gy2 + 3) // 4)
        - ((gy2 + 99) // 100)
        + ((gy2 + 399) // 400)
        + gd
        + g_d_m[gm - 1]
    )
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + (days % 31)
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def jalali_to_gregorian(jy, jm, jd):
    jy2 = jy - 979
    jm2 = jm - 1
    jd2 = jd - 1
    j_day_no = 365 * jy2 + (jy2 // 33) * 8 + ((jy2 % 33) + 3) // 4
    for i in range(jm2):
        j_day_no += 31 if i < 6 else 30
    j_day_no += jd2
    g_day_no = j_day_no + 79
    gy = 1600 + 400 * (g_day_no // 146097)
    g_day_no %= 146097
    leap = True
    if g_day_no >= 36525:
        g_day_no -= 1
        gy += 100 * (g_day_no // 36524)
        g_day_no %= 36524
        if g_day_no >= 365:
            g_day_no += 1
        else:
            leap = False
    gy += 4 * (g_day_no // 1461)
    g_day_no %= 1461
    if g_day_no >= 366:
        leap = False
        g_day_no -= 1
        gy += g_day_no // 365
        g_day_no %= 365
    gd = g_day_no + 1
    sal_a = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    for i in range(1, 13):
        v = sal_a[i]
        if gd <= v:
            gm = i
            break
        gd -= v
    return gy, gm, gd


def format_jalali_datetime(dt=None):
    """تاریخ و ساعت شمسی به صورت خوانا"""
    if dt is None:
        dt = datetime.now()
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    return f"{jd:02d} {JALALI_MONTHS[jm]} {jy}  |  {dt.strftime('%H:%M:%S')}"


def format_jalali_date(dt):
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    return f"{jy}/{jm:02d}/{jd:02d}"


class GatekeeperApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1050x720")
        self.root.minsize(850, 580)
        self.root.configure(bg="#1e1e2f")
        self.employees = []
        self.logs = []
        self.shifts = []
        self.password = DEFAULT_PASSWORD
        self.section_passwords = {"employees": "", "shifts": "", "reports": "", "settings": "", "guest": ""}
        self.section_locks = {"employees": True, "shifts": True, "reports": False, "settings": True, "guest": False}
        self.time_offset_seconds = 0
        self.use_custom_time = False
        self.selected_employee_index = None
        self.unlocked_sections = set()
        self.clock_label = None
        self.load_data()
        self.configure_style()
        self.show_login()

    def configure_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", font=("Tahoma", 10), rowheight=28)
        style.configure("Treeview.Heading", font=("Tahoma", 10, "bold"))

    def now(self):
        """زمان برنامه — مستقل و قابل تنظیم"""
        t = datetime.now()
        if self.use_custom_time:
            t = t + timedelta(seconds=self.time_offset_seconds)
        return t

    def set_app_datetime(self, jy, jm, jd, hour, minute, second=0):
        try:
            gy, gm, gd = jalali_to_gregorian(int(jy), int(jm), int(jd))
            desired = datetime(gy, gm, gd, int(hour), int(minute), int(second))
            self.time_offset_seconds = int((desired - datetime.now()).total_seconds())
            self.use_custom_time = True
            self.save_data()
            return True
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"تاریخ نامعتبر است:\n{exc}")
            return False

    def reset_app_time(self):
        self.time_offset_seconds = 0
        self.use_custom_time = False
        self.save_data()

    def load_data(self):
        if not DATA_FILE.exists():
            return
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            self.employees = data.get("employees", [])
            self.logs = data.get("logs", [])
            self.shifts = data.get("shifts", [])
            self.password = data.get("password", DEFAULT_PASSWORD)
            self.section_passwords = data.get("section_passwords", self.section_passwords)
            self.section_locks = data.get("section_locks", self.section_locks)
            self.time_offset_seconds = data.get("time_offset_seconds", 0)
            self.use_custom_time = data.get("use_custom_time", False)
        except (OSError, json.JSONDecodeError):
            messagebox.showwarning(APP_NAME, "فایل اطلاعات خوانده نشد؛ برنامه با اطلاعات خالی باز شد.")

    def save_data(self):
        data = {
            "employees": self.employees,
            "logs": self.logs,
            "shifts": self.shifts,
            "password": self.password,
            "section_passwords": self.section_passwords,
            "section_locks": self.section_locks,
            "time_offset_seconds": self.time_offset_seconds,
            "use_custom_time": self.use_custom_time,
        }
        try:
            DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"خطا در ذخیره اطلاعات:\n{exc}")

    def clear_window(self):
        if self.clock_label is not None:
            try:
                self.root.after_cancel(self._clock_job)
            except Exception:
                pass
            self.clock_label = None
        for widget in self.root.winfo_children():
            widget.destroy()

    def title_label(self, parent, text, size=18):
        return tk.Label(parent, text=text, bg="#1e1e2f", fg="white", font=("Tahoma", size, "bold"))

    def button(self, parent, text, command, color="#4CAF50"):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg="white",
            activebackground=color,
            activeforeground="white",
            font=("Tahoma", 11, "bold"),
            relief="flat",
            padx=10,
            pady=8,
            cursor="hand2",
        )

    # ---------- تقویم و ساعت شمسی ----------
    def start_clock(self, label):
        self.clock_label = label
        self._update_clock()

    def _update_clock(self):
        if self.clock_label is None:
            return
        try:
            mode = " (تنظیم‌شده)" if self.use_custom_time else ""
            self.clock_label.config(text=format_jalali_datetime(self.now()) + mode)
            self._clock_job = self.root.after(1000, self._update_clock)
        except Exception:
            pass

    # ---------- قفل رمز بخش‌ها ----------
    def _password_for_section(self, section):
        p = self.section_passwords.get(section, "")
        return p if p else self.password

    def require_section(self, section, title=None):
        if not self.section_locks.get(section, False):
            return True
        if section in self.unlocked_sections:
            return True
        name = title or section
        pwd = simpledialog.askstring(f"قفل — {name}", f"رمز «{name}» را وارد کنید:", show="*", parent=self.root)
        if pwd is None:
            return False
        if pwd == self._password_for_section(section):
            self.unlocked_sections.add(section)
            return True
        messagebox.showerror(APP_NAME, "رمز عبور اشتباه است.")
        return False

    def lock_all_sections(self):
        self.unlocked_sections.clear()
        messagebox.showinfo(APP_NAME, "همه بخش‌های قفل‌دار دوباره قفل شدند.")

    # ---------- ورود ----------
    def show_login(self):
        self.clear_window()
        self.unlocked_sections.clear()
        frame = tk.Frame(self.root, bg="#1e1e2f", padx=60, pady=70)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        self.title_label(frame, "🚪 دروازه‌بان", 24).pack(pady=(0, 8))

        # ساعت شمسی در صفحه ورود
        clock = tk.Label(frame, text="", bg="#1e1e2f", fg="#90caf9", font=("Tahoma", 12))
        clock.pack(pady=(0, 16))
        self.start_clock(clock)

        tk.Label(frame, text="رمز عبور را وارد کنید", bg="#1e1e2f", fg="white", font=("Tahoma", 12)).pack()
        self.password_entry = tk.Entry(frame, show="*", font=("Tahoma", 14), justify="center", width=26)
        self.password_entry.pack(pady=14, ipady=7)
        self.password_entry.bind("<Return>", lambda event: self.login())
        self.button(frame, "ورود", self.login).pack(fill="x")
        self.login_error = tk.Label(frame, text="", bg="#1e1e2f", fg="#f44336", font=("Tahoma", 11))
        self.login_error.pack(pady=10)
        self.password_entry.focus_set()

    def login(self):
        if self.password_entry.get() == self.password:
            self.unlocked_sections.clear()
            self.show_main()
        else:
            self.login_error.config(text="رمز عبور اشتباه است")

    def logout(self):
        self.unlocked_sections.clear()
        self.show_login()

    # ---------- صفحه اصلی ----------
    def show_main(self):
        self.clear_window()
        top = tk.Frame(self.root, bg="#1e1e2f", padx=15, pady=8)
        top.pack(fill="x")
        self.title_label(top, "🚪 دروازه‌بان", 18).pack(side="right")

        # ساعت و تاریخ شمسی (مستقل از تنظیمات نمایش سیستم)
        clock = tk.Label(top, text="", bg="#1e1e2f", fg="#90caf9", font=("Tahoma", 12, "bold"))
        clock.pack(side="left")
        self.start_clock(clock)

        # --- جستجوی سریع کارمند ---
        search_frame = tk.Frame(self.root, bg="#1e1e2f", padx=15)
        search_frame.pack(fill="x", pady=(0, 6))

        tk.Label(search_frame, text="🔎 جستجوی سریع:", bg="#1e1e2f", fg="#90caf9", font=("Tahoma", 11)).pack(
            side="right", padx=(0, 8)
        )
        self.quick_search = tk.Entry(search_frame, font=("Tahoma", 12), justify="right")
        self.quick_search.pack(side="right", fill="x", expand=True, ipady=6)
        self.quick_search.bind("<KeyRelease>", self._on_quick_search)
        self.quick_search.bind("<Down>", lambda e: self._focus_suggest())
        self.quick_search.bind("<Return>", lambda e: self._select_first_suggest())

        self.suggest_frame = tk.Frame(self.root, bg="#2a2a3d")
        self.suggest_list = tk.Listbox(
            self.suggest_frame,
            font=("Tahoma", 11),
            height=5,
            justify="right",
            bg="#2a2a3d",
            fg="white",
            selectbackground="#4CAF50",
            activestyle="none",
        )
        self.suggest_list.pack(fill="x", padx=15)
        self.suggest_list.bind("<Double-Button-1>", lambda e: self._apply_suggestion())
        self.suggest_list.bind("<Return>", lambda e: self._apply_suggestion())
        self.suggest_frame.pack_forget()

        # ورودی پلاک ۴ فیلدی
        entry_frame = tk.Frame(self.root, bg="#1e1e2f", padx=15)
        entry_frame.pack(fill="x")
        self._entry_frame = entry_frame

        plate_inputs = tk.Frame(entry_frame, bg="#1e1e2f")
        plate_inputs.pack(side="right", fill="x", expand=True, padx=(0, 8))

        part4_frame = tk.Frame(plate_inputs, bg="#1e1e2f")
        part4_frame.pack(side="right", padx=3)
        tk.Label(part4_frame, text="ایران", bg="#1e1e2f", fg="#90caf9", font=("Tahoma", 9)).pack()
        self.plate_part4 = tk.Entry(part4_frame, font=("Tahoma", 16), justify="center", width=3)
        self.plate_part4.pack(ipady=8)

        tk.Label(plate_inputs, text="-", bg="#1e1e2f", fg="#888", font=("Tahoma", 14)).pack(side="right")

        self.plate_part3 = tk.Entry(plate_inputs, font=("Tahoma", 16), justify="center", width=4)
        self.plate_part3.pack(side="right", ipady=8, padx=3)
        tk.Label(plate_inputs, text="-", bg="#1e1e2f", fg="#888", font=("Tahoma", 14)).pack(side="right")

        self.plate_part2 = tk.Entry(plate_inputs, font=("Tahoma", 16), justify="center", width=3)
        self.plate_part2.pack(side="right", ipady=8, padx=3)
        tk.Label(plate_inputs, text="-", bg="#1e1e2f", fg="#888", font=("Tahoma", 14)).pack(side="right")

        self.plate_part1 = tk.Entry(plate_inputs, font=("Tahoma", 16), justify="center", width=3)
        self.plate_part1.pack(side="right", ipady=8, padx=3)

        self.button(entry_frame, "✅ بررسی پلاک", self.check_plate).pack(side="left")

        self.plate_part1.bind("<KeyRelease>", lambda e: self._auto_next(self.plate_part1, 2, self.plate_part2))
        self.plate_part2.bind("<KeyRelease>", lambda e: self._auto_next(self.plate_part2, 1, self.plate_part3))
        self.plate_part3.bind("<KeyRelease>", lambda e: self._auto_next(self.plate_part3, 3, self.plate_part4))
        self.plate_part4.bind("<KeyRelease>", lambda e: self._limit_length(self.plate_part4, 2))

        for entry in (self.plate_part1, self.plate_part2, self.plate_part3, self.plate_part4):
            entry.bind("<Return>", lambda event: self.check_plate())

        self.plate_part1.focus_set()

        # نوار دکمه‌ها
        nav = tk.Frame(self.root, bg="#1e1e2f", padx=15, pady=10)
        nav.pack(fill="x")
        self.button(nav, "📊 گزارش‌ها", lambda: self.require_section("reports", "گزارش‌ها") and self.show_report(), "#2196F3").pack(side="right", padx=3)
        self.button(nav, "🔄 تحویل / دریافت شیفت", self.show_shifts, "#ff9800").pack(side="right", padx=3)
        self.button(nav, "👥 مدیریت کارمندان", self._open_employees_locked, "#607d8b").pack(side="right", padx=3)
        self.button(nav, "🔍 جستجوی پیشرفته", self.show_search, "#607d8b").pack(side="right", padx=3)
        self.button(nav, "👤 مهمان", lambda: self.require_section("guest", "ثبت مهمان") and self.show_guest(), "#9c27b0").pack(side="right", padx=3)
        self.button(nav, "⚙️ تنظیمات", self._open_settings, "#795548").pack(side="right", padx=3)
        self.button(nav, "🔒 قفل همه", self.lock_all_sections, "#455a64").pack(side="right", padx=3)
        self.button(nav, "خروج", self.logout, "#f44336").pack(side="left", padx=3)

        self.result_label = tk.Label(
            self.root,
            text="",
            justify="right",
            anchor="e",
            bg="#2a2a3d",
            fg="white",
            font=("Tahoma", 13),
            padx=18,
            pady=15,
            height=5,
        )
        self.result_label.pack(fill="x", padx=15, pady=5)

        tk.Label(
            self.root, text="📋 آخرین ورود/خروج‌ها", bg="#1e1e2f", fg="white", font=("Tahoma", 14, "bold")
        ).pack(pady=(10, 3))
        log_frame = tk.Frame(self.root, bg="#1e1e2f", padx=15, pady=8)
        log_frame.pack(fill="both", expand=True)
        self.recent_tree = self.make_tree(
            log_frame, ("زمان", "پلاک", "نام", "نوع", "اقدام"), (180, 150, 230, 120, 100)
        )
        self.refresh_recent_logs()

    def _open_employees_locked(self):
        if self.require_section("employees", "مدیریت کارمندان"):
            self.show_employees()

    def _open_settings(self):
        if self.require_section("settings", "تنظیمات"):
            self.show_settings()

    def make_tree(self, parent, columns, widths):
        frame = tk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor="center")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="left", fill="y")
        tree.pack(side="right", fill="both", expand=True)
        return tree

    def format_time(self, value):
        try:
            dt = datetime.fromisoformat(value)
            return f"{format_jalali_date(dt)} - {dt.strftime('%H:%M:%S')}"
        except (TypeError, ValueError):
            return value

    def format_plate(self, plate):
        if not plate:
            return plate
        p = plate.replace(" ", "").replace("-", "")
        if len(p) == 8:
            return f"{p[0:2]} {p[2:3]} {p[3:6]} {p[6:8]}"
        return plate

    def refresh_recent_logs(self):
        if not hasattr(self, "recent_tree"):
            return
        for item in self.recent_tree.get_children():
            self.recent_tree.delete(item)
        for log in reversed(self.logs[-12:]):
            self.recent_tree.insert(
                "",
                "end",
                values=(
                    self.format_time(log["time"]),
                    self.format_plate(log["plate"]),
                    log["name"],
                    log["type"],
                    log["action"],
                ),
            )

    def _auto_next(self, current, max_len, next_widget):
        text = current.get()
        if len(text) > max_len:
            current.delete(max_len, "end")
            text = current.get()
        if len(text) >= max_len:
            next_widget.focus_set()

    def _limit_length(self, entry, max_len):
        text = entry.get()
        if len(text) > max_len:
            entry.delete(max_len, "end")

    def _on_quick_search(self, event=None):
        q = self.quick_search.get().strip().casefold()
        self.suggest_list.delete(0, "end")
        self._suggest_data = []
        if not q:
            self.suggest_frame.pack_forget()
            return
        matches = []
        for emp in self.employees:
            text = " ".join(
                [emp.get("plate", ""), emp.get("name", ""), emp.get("unit", ""), emp.get("car", "")]
            ).casefold()
            if q in text:
                matches.append(emp)
        if not matches:
            self.suggest_frame.pack_forget()
            return
        for emp in matches[:8]:
            display = f"{self.format_plate(emp['plate'])}  |  {emp['name']}  |  {emp.get('unit', '')}"
            if emp.get("car"):
                display += f"  |  {emp['car']}"
            self.suggest_list.insert("end", display)
            self._suggest_data.append(emp)
        try:
            self.suggest_frame.pack(fill="x", before=self._entry_frame)
        except Exception:
            self.suggest_frame.pack(fill="x")

    def _focus_suggest(self, event=None):
        if self.suggest_list.size() > 0:
            self.suggest_list.focus_set()
            self.suggest_list.selection_set(0)
            self.suggest_list.activate(0)

    def _select_first_suggest(self, event=None):
        if self.suggest_list.size() > 0:
            self.suggest_list.selection_set(0)
            self._apply_suggestion()

    def _apply_suggestion(self, event=None):
        sel = self.suggest_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if not hasattr(self, "_suggest_data") or idx >= len(self._suggest_data):
            return
        emp = self._suggest_data[idx]
        plate = emp.get("plate", "")
        p = plate.replace(" ", "").replace("-", "")
        self.clear_plate_fields()
        if len(p) >= 8:
            self.plate_part1.insert(0, p[0:2])
            self.plate_part2.insert(0, p[2:3])
            self.plate_part3.insert(0, p[3:6])
            self.plate_part4.insert(0, p[6:8])
        else:
            self.plate_part1.insert(0, p)
        self.quick_search.delete(0, "end")
        self.suggest_frame.pack_forget()
        self.plate_part4.focus_set()

    def get_plate_string(self):
        p1 = self.plate_part1.get().strip()
        p2 = self.plate_part2.get().strip()
        p3 = self.plate_part3.get().strip()
        p4 = self.plate_part4.get().strip()
        return f"{p1}{p2}{p3}{p4}"

    def clear_plate_fields(self):
        for entry in (self.plate_part1, self.plate_part2, self.plate_part3, self.plate_part4):
            entry.delete(0, "end")
        self.plate_part1.focus_set()

    def check_plate(self):
        p1 = self.plate_part1.get().strip()
        p2 = self.plate_part2.get().strip()
        p3 = self.plate_part3.get().strip()
        p4 = self.plate_part4.get().strip()

        if not (p1 and p2 and p3 and p4):
            messagebox.showwarning(APP_NAME, "لطفاً تمام بخش‌های پلاک را کامل وارد کنید.")
            return
        if len(p1) != 2 or not p1.isdigit():
            messagebox.showwarning(APP_NAME, "فیلد اول باید دقیقاً ۲ رقم باشد.")
            self.plate_part1.focus_set()
            return
        if len(p2) != 1:
            messagebox.showwarning(APP_NAME, "فیلد دوم باید یک حرف باشد.")
            self.plate_part2.focus_set()
            return
        if len(p3) != 3 or not p3.isdigit():
            messagebox.showwarning(APP_NAME, "فیلد سوم باید دقیقاً ۳ رقم باشد.")
            self.plate_part3.focus_set()
            return
        if len(p4) != 2 or not p4.isdigit():
            messagebox.showwarning(APP_NAME, "فیلد چهارم باید دقیقاً ۲ رقم باشد.")
            self.plate_part4.focus_set()
            return

        plate = self.get_plate_string()
        display_plate = f"{p1} {p2} {p3} {p4}"

        is_entry = messagebox.askyesno("نوع حرکت", "این حرکت ورود است؟\n\nبله = ورود\nخیر = خروج")
        action = "ورود" if is_entry else "خروج"
        found = next((employee for employee in self.employees if employee["plate"] == plate), None)
        now = self.now().isoformat(timespec="seconds")
        if found:
            text = (
                f"✅ کارمند شرکت\nنام: {found['name']}\nواحد: {found['unit']}\n"
                f"ماشین: {found.get('car') or '—'}\nپلاک: {display_plate}\nاقدام: {action}\n\n🚪 در را باز کنید"
            )
            self.result_label.config(text=text, bg="#2e7d32")
            log = {"time": now, "plate": plate, "name": found["name"], "type": "کارمند", "action": action}
        else:
            text = f"⚠️ غریبه / تحویل\nپلاک: {display_plate}\nاقدام: {action}\n\nلطفاً مدارک را بررسی کنید"
            self.result_label.config(text=text, bg="#c62828")
            log = {"time": now, "plate": plate, "name": "نامشخص", "type": "غریبه", "action": action}
        self.logs.append(log)
        self.save_data()
        self.refresh_recent_logs()
        self.clear_plate_fields()

    def new_window(self, title, size="850x580"):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry(size)
        win.configure(bg="#1e1e2f")
        win.transient(self.root)
        return win


    def show_settings(self):
        win = self.new_window("تنظیمات", "640x700")
        self.title_label(win, "⚙️ تنظیمات", 18).pack(pady=10)
        form = tk.Frame(win, bg="#1e1e2f", padx=25)
        form.pack(fill="both", expand=True)

        tk.Label(form, text="📅 تاریخ و ساعت برنامه (شمسی — مستقل از ویندوز)", bg="#1e1e2f", fg="#90caf9",
                 font=("Tahoma", 12, "bold")).pack(anchor="e", pady=(8, 4))
        tk.Label(form, text="این زمان برای ثبت ورود/خروج استفاده می‌شود.", bg="#1e1e2f", fg="#aaa",
                 font=("Tahoma", 9)).pack(anchor="e")

        now = self.now()
        jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
        time_row = tk.Frame(form, bg="#1e1e2f")
        time_row.pack(fill="x", pady=8)
        fields = {}
        for key, label, val, w in (("jy", "سال", jy, 5), ("jm", "ماه", jm, 3), ("jd", "روز", jd, 3),
                                    ("h", "ساعت", now.hour, 3), ("m", "دقیقه", now.minute, 3), ("s", "ثانیه", now.second, 3)):
            box = tk.Frame(time_row, bg="#1e1e2f")
            box.pack(side="right", padx=4)
            tk.Label(box, text=label, bg="#1e1e2f", fg="white", font=("Tahoma", 9)).pack()
            e = tk.Entry(box, font=("Tahoma", 12), justify="center", width=w)
            e.insert(0, str(val))
            e.pack()
            fields[key] = e

        def apply_time():
            if self.set_app_datetime(fields["jy"].get(), fields["jm"].get(), fields["jd"].get(),
                                     fields["h"].get(), fields["m"].get(), fields["s"].get() or 0):
                messagebox.showinfo(APP_NAME, "تاریخ و ساعت برنامه تنظیم شد.")

        def sync_system():
            self.reset_app_time()
            messagebox.showinfo(APP_NAME, "ساعت برنامه با سیستم هماهنگ شد.")

        btn_t = tk.Frame(form, bg="#1e1e2f")
        btn_t.pack(fill="x", pady=6)
        self.button(btn_t, "✓ اعمال تاریخ/ساعت", apply_time, "#4CAF50").pack(side="right", padx=4)
        self.button(btn_t, "↺ همگام با سیستم", sync_system, "#607d8b").pack(side="right", padx=4)

        tk.Label(form, text="🔑 رمز ورود به برنامه", bg="#1e1e2f", fg="#90caf9",
                 font=("Tahoma", 12, "bold")).pack(anchor="e", pady=(16, 4))
        login_pwd = tk.Entry(form, font=("Tahoma", 12), justify="right", show="*")
        login_pwd.pack(fill="x", ipady=5)
        login_pwd.insert(0, self.password)

        tk.Label(form, text="🔐 رمز و قفل هر بخش", bg="#1e1e2f", fg="#90caf9",
                 font=("Tahoma", 12, "bold")).pack(anchor="e", pady=(16, 4))
        tk.Label(form, text="رمز خالی = رمز ورود. قفل روشن = قبل از باز شدن رمز می‌پرسد.",
                 bg="#1e1e2f", fg="#aaa", font=("Tahoma", 9)).pack(anchor="e")

        sections = [("employees", "مدیریت کارمندان"), ("shifts", "تحویل شیفت"),
                    ("reports", "گزارش‌ها"), ("settings", "تنظیمات"), ("guest", "ثبت مهمان")]
        lock_vars, pwd_entries = {}, {}
        for key, title in sections:
            row = tk.Frame(form, bg="#2a2a3d", padx=8, pady=5)
            row.pack(fill="x", pady=2)
            var = tk.BooleanVar(value=self.section_locks.get(key, False))
            lock_vars[key] = var
            tk.Checkbutton(row, text="قفل", variable=var, bg="#2a2a3d", fg="white",
                           selectcolor="#333", activebackground="#2a2a3d", font=("Tahoma", 10)).pack(side="left")
            e = tk.Entry(row, font=("Tahoma", 11), justify="right", show="*", width=14)
            e.pack(side="left", padx=6, ipady=2)
            e.insert(0, self.section_passwords.get(key, ""))
            pwd_entries[key] = e
            tk.Label(row, text=title, bg="#2a2a3d", fg="white", font=("Tahoma", 11)).pack(side="right")

        def save_settings():
            new_login = login_pwd.get().strip()
            if len(new_login) < 4:
                messagebox.showwarning(APP_NAME, "رمز ورود باید حداقل ۴ کاراکتر باشد.")
                return
            self.password = new_login
            for key, _ in sections:
                self.section_passwords[key] = pwd_entries[key].get().strip()
                self.section_locks[key] = lock_vars[key].get()
            self.save_data()
            self.unlocked_sections.clear()
            messagebox.showinfo(APP_NAME, "تنظیمات ذخیره شد.")
            win.destroy()

        self.button(form, "💾 ذخیره تنظیمات", save_settings, "#4CAF50").pack(fill="x", pady=16)

    # ---------- گزارش روزانه / ماهانه / سه‌ماهه ----------
    def _filter_logs(self, period):
        """period: day | month | quarter"""
        now = self.now()
        filtered = []
        for log in self.logs:
            try:
                dt = datetime.fromisoformat(log["time"])
            except (TypeError, ValueError):
                continue
            if period == "day":
                if dt.date() == now.date():
                    filtered.append(log)
            elif period == "month":
                if dt.year == now.year and dt.month == now.month:
                    filtered.append(log)
            elif period == "quarter":
                q = (now.month - 1) // 3
                if dt.year == now.year and (dt.month - 1) // 3 == q:
                    filtered.append(log)
        return filtered

    def show_report(self):
        win = self.new_window("گزارش‌ها", "980x650")
        self.title_label(win, "📊 گزارش ورود و خروج", 18).pack(pady=10)

        period_var = tk.StringVar(value="day")
        period_frame = tk.Frame(win, bg="#1e1e2f")
        period_frame.pack(pady=5)
        for text, val in (("روزانه", "day"), ("ماهانه", "month"), ("سه‌ماهه", "quarter")):
            tk.Radiobutton(
                period_frame,
                text=text,
                variable=period_var,
                value=val,
                bg="#1e1e2f",
                fg="white",
                selectcolor="#333",
                activebackground="#1e1e2f",
                activeforeground="white",
                font=("Tahoma", 11),
                command=lambda: refresh(),
            ).pack(side="right", padx=12)

        summary_label = tk.Label(win, text="", bg="#1e1e2f", fg="white", font=("Tahoma", 11))
        summary_label.pack(pady=5)

        frame = tk.Frame(win, bg="#1e1e2f", padx=15, pady=8)
        frame.pack(fill="both", expand=True)
        tree = self.make_tree(frame, ("زمان", "پلاک", "نام", "نوع", "اقدام"), (180, 140, 210, 120, 100))

        def refresh():
            period = period_var.get()
            logs = self._filter_logs(period)
            for item in tree.get_children():
                tree.delete(item)
            for log in reversed(logs):
                tree.insert(
                    "",
                    "end",
                    values=(
                        self.format_time(log["time"]),
                        self.format_plate(log["plate"]),
                        log["name"],
                        log["type"],
                        log["action"],
                    ),
                )
            emp_in = sum(1 for log in logs if log["type"] == "کارمند" and log["action"] == "ورود")
            emp_out = sum(1 for log in logs if log["type"] == "کارمند" and log["action"] == "خروج")
            guests = sum(1 for log in logs if log["type"] == "مهمان")
            strangers = sum(1 for log in logs if log["type"] == "غریبه")
            period_name = {"day": "روزانه", "month": "ماهانه", "quarter": "سه‌ماهه"}[period]
            summary_label.config(
                text=(
                    f"دوره: {period_name}  |  تاریخ شمسی: {format_jalali_date(self.now())}  |  "
                    f"کارمند ورود: {emp_in}  |  کارمند خروج: {emp_out}  |  مهمان: {guests}  |  غریبه: {strangers}"
                )
            )
            win._current_logs = logs
            win._period_name = period_name

        def copy_report():
            logs = getattr(win, "_current_logs", [])
            period_name = getattr(win, "_period_name", "")
            lines = [f"گزارش {period_name} - {format_jalali_datetime(self.now())}", ""]
            lines += [
                f"{self.format_time(log['time'])} - {self.format_plate(log['plate'])} - "
                f"{log['name']} ({log['type']} - {log['action']})"
                for log in logs
            ]
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(lines))
            self.root.update()
            messagebox.showinfo(APP_NAME, "گزارش در حافظه موقت کپی شد.")

        def save_text():
            logs = getattr(win, "_current_logs", [])
            period_name = getattr(win, "_period_name", "")
            lines = [f"گزارش {period_name} - {format_jalali_datetime(self.now())}", ""]
            lines += [
                f"{self.format_time(log['time'])} - {self.format_plate(log['plate'])} - "
                f"{log['name']} ({log['type']} - {log['action']})"
                for log in logs
            ]
            path = app_directory() / f"report_{period_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            try:
                path.write_text("\n".join(lines), encoding="utf-8")
                messagebox.showinfo(APP_NAME, f"گزارش ذخیره شد:\n{path}")
            except OSError as exc:
                messagebox.showerror(APP_NAME, f"خطا در ذخیره:\n{exc}")

        btn_row = tk.Frame(win, bg="#1e1e2f")
        btn_row.pack(pady=10)
        self.button(btn_row, "📤 کپی گزارش", copy_report, "#2196F3").pack(side="right", padx=6)
        self.button(btn_row, "💾 ذخیره فایل متنی", save_text, "#00897b").pack(side="right", padx=6)

        refresh()

    def show_shifts(self):
        if not self.require_section("shifts", "تحویل شیفت"):
            return
        win = self.new_window("تحویل / دریافت شیفت")
        self.title_label(win, "🔄 تحویل / دریافت شیفت", 18).pack(pady=12)
        form = tk.Frame(win, bg="#1e1e2f", padx=25)
        form.pack(fill="x")
        tk.Label(form, text="نوع شیفت", bg="#1e1e2f", fg="white", font=("Tahoma", 11)).pack(anchor="e")
        shift_type = ttk.Combobox(
            form, values=["دریافت", "تحویل"], state="readonly", font=("Tahoma", 11), justify="right"
        )
        shift_type.set("دریافت")
        shift_type.pack(fill="x", pady=4)
        tk.Label(form, text="نام نگهبان", bg="#1e1e2f", fg="white", font=("Tahoma", 11)).pack(anchor="e")
        name = tk.Entry(form, font=("Tahoma", 11), justify="right")
        name.pack(fill="x", pady=4, ipady=5)
        tk.Label(form, text="توضیحات (اختیاری)", bg="#1e1e2f", fg="white", font=("Tahoma", 11)).pack(anchor="e")
        note = tk.Text(form, height=3, font=("Tahoma", 11))
        note.pack(fill="x", pady=4)
        logs_frame = tk.Frame(win, bg="#1e1e2f", padx=15, pady=8)
        logs_frame.pack(fill="both", expand=True)
        tree = self.make_tree(logs_frame, ("زمان", "نوع", "نام نگهبان", "توضیحات"), (180, 100, 180, 300))

        def refresh():
            for item in tree.get_children():
                tree.delete(item)
            for shift in reversed(self.shifts[-20:]):
                tree.insert(
                    "",
                    "end",
                    values=(
                        self.format_time(shift["time"]),
                        shift["type"],
                        shift["name"],
                        shift.get("note", ""),
                    ),
                )

        def save_shift():
            guard = name.get().strip()
            if not guard:
                messagebox.showwarning(APP_NAME, "نام نگهبان را وارد کنید.")
                return
            self.shifts.append(
                {
                    "time": self.now().isoformat(timespec="seconds"),
                    "type": shift_type.get(),
                    "name": guard,
                    "note": note.get("1.0", "end").strip(),
                }
            )
            self.save_data()
            name.delete(0, "end")
            note.delete("1.0", "end")
            refresh()
            messagebox.showinfo(APP_NAME, "شیفت ثبت شد.")

        self.button(form, "ثبت شیفت", save_shift).pack(fill="x", pady=8)
        refresh()

    def show_employees(self):
        win = self.new_window("مدیریت کارمندان", "950x620")
        self.title_label(win, "👥 مدیریت کارمندان", 18).pack(pady=12)
        controls = tk.Frame(win, bg="#1e1e2f", padx=15)
        controls.pack(fill="x")
        frame = tk.Frame(win, bg="#1e1e2f", padx=15, pady=10)
        frame.pack(fill="both", expand=True)
        tree = self.make_tree(frame, ("پلاک", "نام و نام خانوادگی", "واحد", "نوع ماشین"), (180, 260, 180, 200))

        def refresh():
            for item in tree.get_children():
                tree.delete(item)
            for index, employee in enumerate(self.employees):
                tree.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=(
                        self.format_plate(employee["plate"]),
                        employee["name"],
                        employee["unit"],
                        employee.get("car", ""),
                    ),
                )

        def selected_index():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning(APP_NAME, "ابتدا یک کارمند را انتخاب کنید.")
                return None
            return int(selection[0])

        self.button(controls, "➕ افزودن کارمند", lambda: self.employee_form(refresh)).pack(side="right", padx=4)
        self.button(
            controls, "✏️ ویرایش کارمند", lambda: self.employee_form(refresh, selected_index()), "#2196F3"
        ).pack(side="right", padx=4)

        def delete():
            index = selected_index()
            if index is None:
                return
            if messagebox.askyesno(APP_NAME, "آیا از حذف این کارمند مطمئن هستید؟"):
                self.employees.pop(index)
                self.save_data()
                refresh()

        self.button(controls, "🗑 حذف کارمند", delete, "#f44336").pack(side="right", padx=4)
        refresh()

    def employee_form(self, refresh_callback, index=None):
        if index is None and self.selected_employee_index is not None:
            self.selected_employee_index = None
        if index is not None and (index < 0 or index >= len(self.employees)):
            return
        win = self.new_window("افزودن / ویرایش کارمند", "520x500")
        title = "ویرایش کارمند" if index is not None else "اضافه کردن کارمند"
        self.title_label(win, title, 16).pack(pady=15)
        form = tk.Frame(win, bg="#1e1e2f", padx=30)
        form.pack(fill="both", expand=True)
        existing = self.employees[index] if index is not None else {}

        tk.Label(form, text="پلاک (مطابق فرمت ایرانی)", bg="#1e1e2f", fg="white", font=("Tahoma", 11)).pack(
            anchor="e", pady=(4, 0)
        )
        plate_frame = tk.Frame(form, bg="#1e1e2f")
        plate_frame.pack(fill="x", pady=3)

        part4 = tk.Entry(plate_frame, font=("Tahoma", 14), justify="center", width=3)
        part4.pack(side="right", ipady=5, padx=2)
        tk.Label(plate_frame, text="-", bg="#1e1e2f", fg="#888", font=("Tahoma", 12)).pack(side="right")
        part3 = tk.Entry(plate_frame, font=("Tahoma", 14), justify="center", width=4)
        part3.pack(side="right", ipady=5, padx=2)
        tk.Label(plate_frame, text="-", bg="#1e1e2f", fg="#888", font=("Tahoma", 12)).pack(side="right")
        part2 = tk.Entry(plate_frame, font=("Tahoma", 14), justify="center", width=3)
        part2.pack(side="right", ipady=5, padx=2)
        tk.Label(plate_frame, text="-", bg="#1e1e2f", fg="#888", font=("Tahoma", 12)).pack(side="right")
        part1 = tk.Entry(plate_frame, font=("Tahoma", 14), justify="center", width=3)
        part1.pack(side="right", ipady=5, padx=2)

        old_plate = existing.get("plate", "")
        if len(old_plate) >= 8:
            part1.insert(0, old_plate[0:2])
            part2.insert(0, old_plate[2:3])
            part3.insert(0, old_plate[3:6])
            part4.insert(0, old_plate[6:8])
        elif old_plate:
            part1.insert(0, old_plate)

        entries = {}
        for key, label in (("name", "نام و نام خانوادگی"), ("unit", "واحد"), ("car", "نوع ماشین (اختیاری)")):
            tk.Label(form, text=label, bg="#1e1e2f", fg="white", font=("Tahoma", 11)).pack(anchor="e", pady=(8, 0))
            entry = tk.Entry(form, font=("Tahoma", 11), justify="right")
            entry.pack(fill="x", ipady=5, pady=3)
            entry.insert(0, existing.get(key, ""))
            entries[key] = entry

        def save():
            p1 = part1.get().strip()
            p2 = part2.get().strip()
            p3 = part3.get().strip()
            p4 = part4.get().strip()
            if not (p1 and p2 and p3 and p4):
                messagebox.showwarning(APP_NAME, "لطفاً تمام بخش‌های پلاک را کامل وارد کنید.")
                return
            if len(p1) != 2 or not p1.isdigit():
                messagebox.showwarning(APP_NAME, "فیلد اول پلاک باید دقیقاً ۲ رقم باشد.")
                return
            if len(p2) != 1:
                messagebox.showwarning(APP_NAME, "فیلد دوم پلاک باید یک حرف باشد.")
                return
            if len(p3) != 3 or not p3.isdigit():
                messagebox.showwarning(APP_NAME, "فیلد سوم پلاک باید دقیقاً ۳ رقم باشد.")
                return
            if len(p4) != 2 or not p4.isdigit():
                messagebox.showwarning(APP_NAME, "فیلد چهارم پلاک باید دقیقاً ۲ رقم باشد.")
                return
            plate = f"{p1}{p2}{p3}{p4}"
            name = entries["name"].get().strip()
            unit = entries["unit"].get().strip()
            car = entries["car"].get().strip()
            if not name or not unit:
                messagebox.showwarning(APP_NAME, "نام و واحد الزامی است.")
                return
            duplicate = next(
                (i for i, item in enumerate(self.employees) if item["plate"] == plate and i != index), None
            )
            if duplicate is not None:
                messagebox.showwarning(APP_NAME, "این پلاک قبلاً ثبت شده است.")
                return
            employee = {"plate": plate, "name": name, "unit": unit, "car": car}
            if index is None:
                self.employees.append(employee)
            else:
                self.employees[index] = employee
            self.save_data()
            refresh_callback()
            win.destroy()
            messagebox.showinfo(APP_NAME, "اطلاعات ذخیره شد.")

        self.button(form, "ذخیره", save).pack(fill="x", pady=15)
        part1.focus_set()

    def show_guest(self):
        p1 = self.plate_part1.get().strip()
        p2 = self.plate_part2.get().strip()
        p3 = self.plate_part3.get().strip()
        p4 = self.plate_part4.get().strip()
        if not (p1 and p2 and p3 and p4):
            messagebox.showwarning(APP_NAME, "ابتدا پلاک را کامل وارد کنید.")
            return
        if (
            len(p1) != 2
            or not p1.isdigit()
            or len(p2) != 1
            or len(p3) != 3
            or not p3.isdigit()
            or len(p4) != 2
            or not p4.isdigit()
        ):
            messagebox.showwarning(APP_NAME, "پلاک را به درستی وارد کنید.")
            return

        plate = f"{p1}{p2}{p3}{p4}"
        display_plate = f"{p1} {p2} {p3} {p4}"

        win = self.new_window("ثبت مهمان", "480x420")
        self.title_label(win, "👤 ثبت مهمان", 16).pack(pady=12)
        form = tk.Frame(win, bg="#1e1e2f", padx=30)
        form.pack(fill="both", expand=True)
        tk.Label(
            form, text=f"پلاک: {display_plate}", bg="#1e1e2f", fg="#90caf9", font=("Tahoma", 13, "bold")
        ).pack(anchor="e", pady=(0, 12))
        tk.Label(form, text="فامیل", bg="#1e1e2f", fg="white", font=("Tahoma", 11)).pack(anchor="e")
        family = tk.Entry(form, font=("Tahoma", 12), justify="right")
        family.pack(fill="x", ipady=6, pady=4)
        tk.Label(form, text="محل اعزام", bg="#1e1e2f", fg="white", font=("Tahoma", 11)).pack(
            anchor="e", pady=(10, 0)
        )
        place = tk.Entry(form, font=("Tahoma", 12), justify="right")
        place.pack(fill="x", ipady=6, pady=4)

        def save_guest(action):
            fam = family.get().strip()
            plc = place.get().strip()
            if not fam:
                messagebox.showwarning(APP_NAME, "فامیل را وارد کنید.")
                return
            if not plc:
                messagebox.showwarning(APP_NAME, "محل اعزام را وارد کنید.")
                return
            name = f"{fam} (مهمان - {plc})"
            now = self.now().isoformat(timespec="seconds")
            log = {"time": now, "plate": plate, "name": name, "type": "مهمان", "action": action}
            self.logs.append(log)
            self.save_data()
            self.refresh_recent_logs()
            text = (
                f"👤 مهمان ثبت شد\nفامیل: {fam}\nمحل اعزام: {plc}\nپلاک: {display_plate}\nاقدام: {action}"
            )
            self.result_label.config(text=text, bg="#6a1b9a")
            self.clear_plate_fields()
            win.destroy()
            messagebox.showinfo(APP_NAME, f"مهمان با موفقیت ثبت شد ({action})")

        btn_frame = tk.Frame(form, bg="#1e1e2f")
        btn_frame.pack(fill="x", pady=20)
        self.button(btn_frame, "✅ ورود", lambda: save_guest("ورود"), "#4CAF50").pack(
            side="right", fill="x", expand=True, padx=(4, 0)
        )
        self.button(btn_frame, "🚪 خروج", lambda: save_guest("خروج"), "#f44336").pack(
            side="left", fill="x", expand=True, padx=(0, 4)
        )
        family.focus_set()

    def show_search(self):
        win = self.new_window("جستجوی پیشرفته", "900x580")
        self.title_label(win, "🔍 جستجوی پیشرفته", 18).pack(pady=12)
        form = tk.Frame(win, bg="#1e1e2f", padx=20)
        form.pack(fill="x")
        query = tk.Entry(form, font=("Tahoma", 12), justify="right")
        query.pack(side="right", fill="x", expand=True, ipady=6, padx=(0, 8))
        result_frame = tk.Frame(win, bg="#1e1e2f", padx=15, pady=12)
        result_frame.pack(fill="both", expand=True)
        tree = self.make_tree(result_frame, ("پلاک", "نام و نام خانوادگی", "واحد", "نوع ماشین"), (180, 260, 180, 180))

        def search():
            q = query.get().strip().casefold()
            for item in tree.get_children():
                tree.delete(item)
            if not q:
                return
            for employee in self.employees:
                text = " ".join(
                    [
                        employee.get("plate", ""),
                        employee.get("name", ""),
                        employee.get("unit", ""),
                        employee.get("car", ""),
                    ]
                ).casefold()
                if q in text:
                    tree.insert(
                        "",
                        "end",
                        values=(
                            self.format_plate(employee["plate"]),
                            employee["name"],
                            employee["unit"],
                            employee.get("car", ""),
                        ),
                    )

        self.button(form, "جستجو", search, "#2196F3").pack(side="left")
        query.bind("<Return>", lambda event: search())
        query.focus_set()


def main():
    root = tk.Tk()
    GatekeeperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
