# -*- coding: utf-8 -*-
"""دروازه‌بان: برنامه رومیزی ثبت ورود و خروج خودروها."""
import json
import sys
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

APP_NAME = "دروازه‌بان"
DEFAULT_PASSWORD = "1234"


def app_directory():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


DATA_FILE = app_directory() / "darvazeban_data.json"


class GatekeeperApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1000x700")
        self.root.minsize(800, 550)
        self.root.configure(bg="#1e1e2f")
        self.employees = []
        self.logs = []
        self.shifts = []
        self.password = DEFAULT_PASSWORD
        self.selected_employee_index = None
        self.load_data()
        self.configure_style()
        self.show_login()

    def configure_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", font=("Tahoma", 10), rowheight=28)
        style.configure("Treeview.Heading", font=("Tahoma", 10, "bold"))

    def load_data(self):
        if not DATA_FILE.exists():
            return
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            self.employees = data.get("employees", [])
            self.logs = data.get("logs", [])
            self.shifts = data.get("shifts", [])
            self.password = data.get("password", DEFAULT_PASSWORD)
        except (OSError, json.JSONDecodeError):
            messagebox.showwarning(APP_NAME, "فایل اطلاعات خوانده نشد؛ برنامه با اطلاعات خالی باز شد.")

    def save_data(self):
        data = {
            "employees": self.employees,
            "logs": self.logs,
            "shifts": self.shifts,
            "password": self.password,
        }
        try:
            DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"خطا در ذخیره اطلاعات:\n{exc}")

    def clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def title_label(self, parent, text, size=18):
        return tk.Label(parent, text=text, bg="#1e1e2f", fg="white", font=("Tahoma", size, "bold"))

    def button(self, parent, text, command, color="#4CAF50"):
        return tk.Button(parent, text=text, command=command, bg=color, fg="white", activebackground=color,
                         activeforeground="white", font=("Tahoma", 11, "bold"), relief="flat", padx=10, pady=8,
                         cursor="hand2")

    def show_login(self):
        self.clear_window()
        frame = tk.Frame(self.root, bg="#1e1e2f", padx=60, pady=70)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        self.title_label(frame, "🚪 دروازه‌بان", 24).pack(pady=(0, 16))
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
            self.show_main()
        else:
            self.login_error.config(text="رمز عبور اشتباه است")

    def logout(self):
        self.show_login()

    def show_main(self):
        self.clear_window()
        top = tk.Frame(self.root, bg="#1e1e2f", padx=15, pady=12)
        top.pack(fill="x")
        self.title_label(top, "🚪 دروازه‌بان", 20).pack()

        # --- جستجوی سریع کارمند ---
        search_frame = tk.Frame(self.root, bg="#1e1e2f", padx=15)
        search_frame.pack(fill="x", pady=(0, 6))

        tk.Label(search_frame, text="🔎 جستجوی سریع:", bg="#1e1e2f", fg="#90caf9", font=("Tahoma", 11)).pack(side="right", padx=(0, 8))
        self.quick_search = tk.Entry(search_frame, font=("Tahoma", 12), justify="right")
        self.quick_search.pack(side="right", fill="x", expand=True, ipady=6)
        self.quick_search.bind("<KeyRelease>", self._on_quick_search)
        self.quick_search.bind("<Down>", lambda e: self._focus_suggest())
        self.quick_search.bind("<Return>", lambda e: self._select_first_suggest())

        # لیست پیشنهادات
        self.suggest_frame = tk.Frame(self.root, bg="#2a2a3d")
        self.suggest_list = tk.Listbox(self.suggest_frame, font=("Tahoma", 11), height=5, justify="right",
                                       bg="#2a2a3d", fg="white", selectbackground="#4CAF50", activestyle="none")
        self.suggest_list.pack(fill="x", padx=15)
        self.suggest_list.bind("<Double-Button-1>", lambda e: self._apply_suggestion())
        self.suggest_list.bind("<Return>", lambda e: self._apply_suggestion())
        self.suggest_frame.pack_forget()  # مخفی در ابتدا

        # ورودی پلاک به صورت ۴ فیلد مطابق پلاک ایرانی
        entry_frame = tk.Frame(self.root, bg="#1e1e2f", padx=15)
        entry_frame.pack(fill="x")
        self._entry_frame = entry_frame

        plate_inputs = tk.Frame(entry_frame, bg="#1e1e2f")
        plate_inputs.pack(side="right", fill="x", expand=True, padx=(0, 8))

        # ترتیب از راست به چپ: ۲ رقم | حرف | ۳ رقم | ۲ رقم  (مثل عکس پلاک)
        # فیلد چهارم (۲ رقم سمت راست پلاک) + برچسب ایران
        part4_frame = tk.Frame(plate_inputs, bg="#1e1e2f")
        part4_frame.pack(side="right", padx=3)
        tk.Label(part4_frame, text="ایران", bg="#1e1e2f", fg="#90caf9", font=("Tahoma", 9)).pack()
        self.plate_part4 = tk.Entry(part4_frame, font=("Tahoma", 16), justify="center", width=3)
        self.plate_part4.pack(ipady=8)

        tk.Label(plate_inputs, text="-", bg="#1e1e2f", fg="#888", font=("Tahoma", 14)).pack(side="right")

        # فیلد سوم (۳ رقم)
        self.plate_part3 = tk.Entry(plate_inputs, font=("Tahoma", 16), justify="center", width=4)
        self.plate_part3.pack(side="right", ipady=8, padx=3)
        tk.Label(plate_inputs, text="-", bg="#1e1e2f", fg="#888", font=("Tahoma", 14)).pack(side="right")

        # فیلد دوم (حرف)
        self.plate_part2 = tk.Entry(plate_inputs, font=("Tahoma", 16), justify="center", width=3)
        self.plate_part2.pack(side="right", ipady=8, padx=3)
        tk.Label(plate_inputs, text="-", bg="#1e1e2f", fg="#888", font=("Tahoma", 14)).pack(side="right")

        # فیلد اول (۲ رقم سمت چپ)
        self.plate_part1 = tk.Entry(plate_inputs, font=("Tahoma", 16), justify="center", width=3)
        self.plate_part1.pack(side="right", ipady=8, padx=3)

        self.button(entry_frame, "✅ بررسی پلاک", self.check_plate).pack(side="left")

        # پر شدن خودکار فیلدها
        self.plate_part1.bind("<KeyRelease>", lambda e: self._auto_next(self.plate_part1, 2, self.plate_part2))
        self.plate_part2.bind("<KeyRelease>", lambda e: self._auto_next(self.plate_part2, 1, self.plate_part3))
        self.plate_part3.bind("<KeyRelease>", lambda e: self._auto_next(self.plate_part3, 3, self.plate_part4))
        self.plate_part4.bind("<KeyRelease>", lambda e: self._limit_length(self.plate_part4, 2))

        # اتصال کلید Enter به بررسی
        for entry in (self.plate_part1, self.plate_part2, self.plate_part3, self.plate_part4):
            entry.bind("<Return>", lambda event: self.check_plate())

        self.plate_part1.focus_set()

        nav = tk.Frame(self.root, bg="#1e1e2f", padx=15, pady=10)
        nav.pack(fill="x")
        self.button(nav, "📊 گزارش روزانه", self.show_report, "#2196F3").pack(side="right", padx=3)
        self.button(nav, "🔄 تحویل / دریافت شیفت", self.show_shifts, "#ff9800").pack(side="right", padx=3)
        self.button(nav, "👥 مدیریت کارمندان", self.show_employees, "#607d8b").pack(side="right", padx=3)
        self.button(nav, "🔍 جستجوی پیشرفته", self.show_search, "#607d8b").pack(side="right", padx=3)
        self.button(nav, "👤 مهمان", self.show_guest, "#9c27b0").pack(side="right", padx=3)
        self.button(nav, "خروج", self.logout, "#f44336").pack(side="left", padx=3)

        self.result_label = tk.Label(self.root, text="", justify="right", anchor="e", bg="#2a2a3d", fg="white",
                                     font=("Tahoma", 13), padx=18, pady=15, height=5)
        self.result_label.pack(fill="x", padx=15, pady=5)

        tk.Label(self.root, text="📋 آخرین ورود/خروج‌ها", bg="#1e1e2f", fg="white", font=("Tahoma", 14, "bold")).pack(pady=(10, 3))
        log_frame = tk.Frame(self.root, bg="#1e1e2f", padx=15, pady=8)
        log_frame.pack(fill="both", expand=True)
        self.recent_tree = self.make_tree(log_frame, ("زمان", "پلاک", "نام", "نوع", "اقدام"), (150, 150, 230, 120, 100))
        self.refresh_recent_logs()

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
            return datetime.fromisoformat(value).strftime("%Y/%m/%d - %H:%M:%S")
        except (TypeError, ValueError):
            return value

    def format_plate(self, plate):
        """نمایش زیبای پلاک با فاصله (مثل عکس)"""
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
            self.recent_tree.insert("", "end", values=(self.format_time(log["time"]), self.format_plate(log["plate"]), log["name"], log["type"], log["action"]))

    def _auto_next(self, current, max_len, next_widget):
        """بعد از پر شدن فیلد، فوکوس به فیلد بعدی برود"""
        text = current.get()
        if len(text) > max_len:
            current.delete(max_len, "end")
            text = current.get()
        if len(text) >= max_len:
            next_widget.focus_set()

    def _limit_length(self, entry, max_len):
        """محدود کردن طول فیلد آخر"""
        text = entry.get()
        if len(text) > max_len:
            entry.delete(max_len, "end")

    def _on_quick_search(self, event=None):
        """جستجوی زنده و نمایش پیشنهادات"""
        q = self.quick_search.get().strip().casefold()
        self.suggest_list.delete(0, "end")
        self._suggest_data = []

        if not q:
            self.suggest_frame.pack_forget()
            return

        matches = []
        for emp in self.employees:
            text = " ".join([
                emp.get("plate", ""),
                emp.get("name", ""),
                emp.get("unit", ""),
                emp.get("car", "")
            ]).casefold()
            if q in text:
                matches.append(emp)

        if not matches:
            self.suggest_frame.pack_forget()
            return

        # نمایش حداکثر ۸ مورد
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
        """با انتخاب پیشنهاد، فیلدهای پلاک پر شوند"""
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
        """ترکیب چهار فیلد پلاک به یک رشته استاندارد"""
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

        # اعتبارسنجی ساده طول فیلدها
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

        plate = self.get_plate_string()  # مثلاً: 11ب33411
        display_plate = f"{p1} {p2} {p3} {p4}"  # برای نمایش زیبا: 11 ب 334 11

        is_entry = messagebox.askyesno("نوع حرکت", "این حرکت ورود است؟\n\nبله = ورود\nخیر = خروج")
        action = "ورود" if is_entry else "خروج"
        found = next((employee for employee in self.employees if employee["plate"] == plate), None)
        now = datetime.now().isoformat(timespec="seconds")
        if found:
            text = f"✅ کارمند شرکت\nنام: {found['name']}\nواحد: {found['unit']}\nماشین: {found.get('car') or '—'}\nپلاک: {display_plate}\nاقدام: {action}\n\n🚪 در را باز کنید"
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

    def show_report(self):
        win = self.new_window("گزارش روزانه", "950x620")
        self.title_label(win, "📊 گزارش روزانه", 18).pack(pady=12)
        today = datetime.now().date()
        today_logs = [log for log in self.logs if datetime.fromisoformat(log["time"]).date() == today]
        emp_in = sum(log["type"] == "کارمند" and log["action"] == "ورود" for log in today_logs)
        emp_out = sum(log["type"] == "کارمند" and log["action"] == "خروج" for log in today_logs)
        strangers = sum(log["type"] == "غریبه" for log in today_logs)
        tk.Label(win, text=f"تاریخ: {today.strftime('%Y/%m/%d')}     |     کارمند ورود: {emp_in}     |     کارمند خروج: {emp_out}     |     غریبه‌ها: {strangers}", bg="#1e1e2f", fg="white", font=("Tahoma", 11)).pack(pady=5)
        frame = tk.Frame(win, bg="#1e1e2f", padx=15, pady=10)
        frame.pack(fill="both", expand=True)
        tree = self.make_tree(frame, ("زمان", "پلاک", "نام", "نوع", "اقدام"), (180, 140, 210, 120, 100))
        for log in reversed(today_logs):
            tree.insert("", "end", values=(self.format_time(log["time"]), self.format_plate(log["plate"]), log["name"], log["type"], log["action"]))
        self.button(win, "📤 کپی گزارش", lambda: self.copy_report(today_logs, today), "#2196F3").pack(pady=10)

    def copy_report(self, today_logs, today):
        lines = [f"گزارش روزانه - {today.strftime('%Y/%m/%d')}", ""]
        lines += [f"{self.format_time(log['time'])} - {self.format_plate(log['plate'])} - {log['name']} ({log['type']} - {log['action']})" for log in today_logs]
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))
        self.root.update()
        messagebox.showinfo(APP_NAME, "گزارش در حافظه موقت کپی شد.")

    def show_shifts(self):
        win = self.new_window("تحویل / دریافت شیفت")
        self.title_label(win, "🔄 تحویل / دریافت شیفت", 18).pack(pady=12)
        form = tk.Frame(win, bg="#1e1e2f", padx=25)
        form.pack(fill="x")
        tk.Label(form, text="نوع شیفت", bg="#1e1e2f", fg="white", font=("Tahoma", 11)).pack(anchor="e")
        shift_type = ttk.Combobox(form, values=["دریافت", "تحویل"], state="readonly", font=("Tahoma", 11), justify="right")
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
                tree.insert("", "end", values=(self.format_time(shift["time"]), shift["type"], shift["name"], shift.get("note", "")))

        def save_shift():
            guard = name.get().strip()
            if not guard:
                messagebox.showwarning(APP_NAME, "نام نگهبان را وارد کنید.")
                return
            self.shifts.append({"time": datetime.now().isoformat(timespec="seconds"), "type": shift_type.get(), "name": guard, "note": note.get("1.0", "end").strip()})
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
                tree.insert("", "end", iid=str(index), values=(self.format_plate(employee["plate"]), employee["name"], employee["unit"], employee.get("car", "")))

        def selected_index():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning(APP_NAME, "ابتدا یک کارمند را انتخاب کنید.")
                return None
            return int(selection[0])

        self.button(controls, "➕ افزودن کارمند", lambda: self.employee_form(refresh)).pack(side="right", padx=4)
        self.button(controls, "✏️ ویرایش کارمند", lambda: self.employee_form(refresh, selected_index()), "#2196F3").pack(side="right", padx=4)

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

        # --- پلاک به صورت ۴ فیلد ---
        tk.Label(form, text="پلاک (مطابق فرمت ایرانی)", bg="#1e1e2f", fg="white", font=("Tahoma", 11)).pack(anchor="e", pady=(4, 0))
        plate_frame = tk.Frame(form, bg="#1e1e2f")
        plate_frame.pack(fill="x", pady=3)

        # از راست به چپ: ۲رقم | حرف | ۳رقم | ۲رقم
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

        # پر کردن فیلدها در حالت ویرایش
        old_plate = existing.get("plate", "")
        if len(old_plate) >= 8:  # فرمت بدون فاصله: ۲+۱+۳+۲
            part1.insert(0, old_plate[0:2])
            part2.insert(0, old_plate[2:3])
            part3.insert(0, old_plate[3:6])
            part4.insert(0, old_plate[6:8])
        elif old_plate:
            # اگر فرمت قدیمی بود، کل را در فیلد اول بگذار
            part1.insert(0, old_plate)

        # --- سایر فیلدها ---
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

            duplicate = next((i for i, item in enumerate(self.employees) if item["plate"] == plate and i != index), None)
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
        """ثبت مهمان با پلاک وارد شده در صفحه اصلی"""
        p1 = self.plate_part1.get().strip()
        p2 = self.plate_part2.get().strip()
        p3 = self.plate_part3.get().strip()
        p4 = self.plate_part4.get().strip()

        if not (p1 and p2 and p3 and p4):
            messagebox.showwarning(APP_NAME, "ابتدا پلاک را کامل وارد کنید.")
            return
        if len(p1) != 2 or not p1.isdigit() or len(p2) != 1 or len(p3) != 3 or not p3.isdigit() or len(p4) != 2 or not p4.isdigit():
            messagebox.showwarning(APP_NAME, "پلاک را به درستی وارد کنید.")
            return

        plate = f"{p1}{p2}{p3}{p4}"
        display_plate = f"{p1} {p2} {p3} {p4}"

        win = self.new_window("ثبت مهمان", "480x420")
        self.title_label(win, "👤 ثبت مهمان", 16).pack(pady=12)

        form = tk.Frame(win, bg="#1e1e2f", padx=30)
        form.pack(fill="both", expand=True)

        tk.Label(form, text=f"پلاک: {display_plate}", bg="#1e1e2f", fg="#90caf9", font=("Tahoma", 13, "bold")).pack(anchor="e", pady=(0, 12))

        tk.Label(form, text="فامیل", bg="#1e1e2f", fg="white", font=("Tahoma", 11)).pack(anchor="e")
        family = tk.Entry(form, font=("Tahoma", 12), justify="right")
        family.pack(fill="x", ipady=6, pady=4)

        tk.Label(form, text="محل اعزام", bg="#1e1e2f", fg="white", font=("Tahoma", 11)).pack(anchor="e", pady=(10, 0))
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
            now = datetime.now().isoformat(timespec="seconds")
            log = {"time": now, "plate": plate, "name": name, "type": "مهمان", "action": action}
            self.logs.append(log)
            self.save_data()
            self.refresh_recent_logs()

            text = f"👤 مهمان ثبت شد\nفامیل: {fam}\nمحل اعزام: {plc}\nپلاک: {display_plate}\nاقدام: {action}"
            self.result_label.config(text=text, bg="#6a1b9a")
            self.clear_plate_fields()
            win.destroy()
            messagebox.showinfo(APP_NAME, f"مهمان با موفقیت ثبت شد ({action})")

        btn_frame = tk.Frame(form, bg="#1e1e2f")
        btn_frame.pack(fill="x", pady=20)
        self.button(btn_frame, "✅ ورود", lambda: save_guest("ورود"), "#4CAF50").pack(side="right", fill="x", expand=True, padx=(4, 0))
        self.button(btn_frame, "🚪 خروج", lambda: save_guest("خروج"), "#f44336").pack(side="left", fill="x", expand=True, padx=(0, 4))

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
                text = " ".join([employee.get("plate", ""), employee.get("name", ""), employee.get("unit", ""), employee.get("car", "")]).casefold()
                if q in text:
                    tree.insert("", "end", values=(self.format_plate(employee["plate"]), employee["name"], employee["unit"], employee.get("car", "")))

        self.button(form, "جستجو", search, "#2196F3").pack(side="left")
        query.bind("<Return>", lambda event: search())
        query.focus_set()


def main():
    root = tk.Tk()
    GatekeeperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
