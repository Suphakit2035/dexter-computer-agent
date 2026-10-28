"""Floating desktop widget for the Dexter computer agent."""

import queue
import threading
import tkinter as tk
from typing import Callable


class DexterWidget:
    BG = "#101319"
    PANEL = "#191d25"
    PANEL_LIGHT = "#242a35"
    TEXT = "#f3f5f7"
    MUTED = "#9da6b4"
    ACCENT = "#19c37d"
    TRANSPARENT = "#010203"
    PANEL_WIDTH = 380
    PANEL_HEIGHT = 540

    def __init__(
        self,
        run_agent: Callable[[str], str],
        listen_command: Callable[[], str],
        speak: Callable[[str], None],
        api_key_available: bool,
    ) -> None:
        self.run_agent = run_agent
        self.listen_command = listen_command
        self.speak = speak
        self.api_key_available = api_key_available
        self.events: queue.Queue = queue.Queue()
        self.visibility_ack = threading.Event()
        self.busy = False
        self.expanded = False
        self.drag_origin = None
        self.dragged = False
        self.bubble_position = None
        self.hidden_for_agent = False

        self.root = tk.Tk()
        self.root.title("Dexter")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.wm_attributes("-transparentcolor", self.TRANSPARENT)
        except tk.TclError:
            pass

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"76x76+{screen_w - 112}+{screen_h - 150}")
        self.root.configure(bg=self.TRANSPARENT)
        self._build_bubble()

        self.panel_window = tk.Toplevel(self.root)
        self.panel_window.withdraw()
        self.panel_window.title("Dexter")
        self.panel_window.overrideredirect(True)
        self.panel_window.attributes("-topmost", True)
        self.panel_window.configure(bg=self.BG)
        self.panel_window.protocol("WM_DELETE_WINDOW", self.collapse)
        self._build_panel()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self._poll_events)

    def _build_bubble(self) -> None:
        self.bubble = tk.Canvas(
            self.root,
            width=76,
            height=76,
            bg=self.TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.bubble.place(x=0, y=0)
        self.bubble.create_oval(7, 7, 69, 69, fill=self.ACCENT, outline="#66e5ae", width=2)
        self.bubble.create_text(38, 38, text="D", fill="#082418", font=("Segoe UI", 24, "bold"))
        self.bubble.bind("<ButtonPress-1>", self._drag_start)
        self.bubble.bind("<B1-Motion>", self._drag_motion)
        self.bubble.bind("<ButtonRelease-1>", self._bubble_release)
        self.bubble.bind("<Enter>", lambda _event: self.bubble.configure(cursor="hand2"))

    def _build_panel(self) -> None:
        self.panel = tk.Frame(
            self.panel_window,
            bg=self.BG,
            highlightbackground="#303744",
            highlightthickness=1,
        )
        self.panel.pack(fill="both", expand=True)

        header = tk.Frame(self.panel, bg=self.BG, height=48)
        header.pack(fill="x", padx=14, pady=(8, 4))
        header.bind("<ButtonPress-1>", self._drag_start)
        header.bind("<B1-Motion>", self._drag_motion)
        header.bind("<ButtonRelease-1>", self._drag_end)

        brand = tk.Label(header, text="●  Dexter", bg=self.BG, fg=self.ACCENT, font=("Segoe UI", 12, "bold"))
        brand.pack(side="left", pady=7)
        brand.bind("<ButtonPress-1>", self._drag_start)
        brand.bind("<B1-Motion>", self._drag_motion)
        brand.bind("<ButtonRelease-1>", self._drag_end)

        self._make_button(header, "−", self.collapse, width=3).pack(side="right", padx=(4, 0))
        self._make_button(header, "×", self.close, width=3).pack(side="right")

        self.status = tk.Label(
            self.panel,
            text="พร้อมรับคำสั่ง",
            bg=self.BG,
            fg=self.MUTED,
            anchor="w",
            font=("Segoe UI", 9),
        )
        self.status.pack(fill="x", padx=16, pady=(0, 8))

        chat_area = tk.Frame(self.panel, bg=self.PANEL)
        chat_area.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.chat_canvas = tk.Canvas(chat_area, bg=self.PANEL, highlightthickness=0, bd=0)
        self.chat_canvas.pack(fill="both", expand=True)
        self.messages_frame = tk.Frame(self.chat_canvas, bg=self.PANEL)
        self.messages_window = self.chat_canvas.create_window(
            (0, 0), window=self.messages_frame, anchor="nw"
        )
        self.messages_frame.bind("<Configure>", self._update_chat_scrollregion)
        self.chat_canvas.bind("<Configure>", self._resize_messages_frame)
        self.chat_canvas.bind("<MouseWheel>", self._scroll_chat_with_wheel)

        self.input_hint = tk.Label(
            self.panel,
            text="พิมพ์คำสั่งในช่องนี้ หรือกดไมค์เพื่อพูด",
            bg=self.BG,
            fg=self.MUTED,
            anchor="w",
            font=("Segoe UI", 9),
        )
        self.input_hint.pack(fill="x", padx=16, pady=(0, 5))

        composer = tk.Frame(self.panel, bg=self.PANEL_LIGHT)
        composer.pack(fill="x", padx=12, pady=(0, 12))
        self.command_entry = tk.Entry(
            composer,
            bg="#11151b",
            fg=self.TEXT,
            insertbackground=self.TEXT,
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground="#3a4350",
            highlightcolor=self.ACCENT,
            font=("Segoe UI", 10),
        )
        self.command_entry.pack(side="left", fill="x", expand=True, padx=(10, 4), ipady=11)
        self.command_entry.bind("<Return>", lambda _event: self.send_text())

        self.mic_button = self._make_button(composer, "ไมค์", self.start_voice, width=7, accent=True)
        self.mic_button.pack(side="right", padx=(4, 6), pady=5)
        self.send_button = self._make_button(composer, "ส่ง", self.send_text, width=5)
        self.send_button.pack(side="right", pady=5)

        if not self.api_key_available:
            self.status.configure(text="ยังไม่พบ GEMINI_API_KEY", fg="#f2b45b")
            self._append("ตั้งค่า GEMINI_API_KEY ในไฟล์ .env ก่อนเริ่มสั่งงาน", "system")

    def _make_button(self, parent, label, command, width=4, accent=False):
        return tk.Button(
            parent,
            text=label,
            command=command,
            width=width,
            bg=self.ACCENT if accent else self.PANEL_LIGHT,
            fg="#092318" if accent else self.TEXT,
            activebackground="#45d99b" if accent else "#343c49",
            activeforeground=self.TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        )

    def _append(self, message: str, tag: str = "assistant") -> None:
        row = tk.Frame(self.messages_frame, bg=self.PANEL)
        row.pack(fill="x", padx=7, pady=4)

        if tag == "user":
            bubble_color, text_color, side = "#0e8f65", "#ffffff", "right"
        elif tag == "system":
            bubble_color, text_color, side = "#252c36", self.MUTED, "left"
        else:
            bubble_color, text_color, side = "#2a303a", self.TEXT, "left"

        bubble = tk.Label(
            row,
            text=message,
            bg=bubble_color,
            fg=text_color,
            justify="left",
            anchor="w",
            wraplength=260,
            padx=11,
            pady=8,
            font=("Segoe UI", 10),
        )
        bubble.pack(side=side, anchor="e" if side == "right" else "w")
        row.bind("<MouseWheel>", self._scroll_chat_with_wheel)
        bubble.bind("<MouseWheel>", self._scroll_chat_with_wheel)
        self.root.after_idle(self._scroll_chat_to_bottom)

    def _update_chat_scrollregion(self, _event=None) -> None:
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))

    def _resize_messages_frame(self, event) -> None:
        self.chat_canvas.itemconfigure(self.messages_window, width=event.width)

    def _scroll_chat_to_bottom(self) -> None:
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        self.chat_canvas.yview_moveto(1.0)

    def _scroll_chat_with_wheel(self, event) -> None:
        self.chat_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _drag_start(self, event) -> None:
        window = event.widget.winfo_toplevel()
        self.drag_origin = (event.x_root, event.y_root, window.winfo_x(), window.winfo_y(), window)
        self.dragged = False

    def _drag_motion(self, event) -> None:
        if not self.drag_origin:
            return
        start_x, start_y, win_x, win_y, window = self.drag_origin
        dx, dy = event.x_root - start_x, event.y_root - start_y
        if abs(dx) > 3 or abs(dy) > 3:
            self.dragged = True
            window.geometry(f"+{win_x + dx}+{win_y + dy}")

    def _drag_end(self, _event=None) -> None:
        self.drag_origin = None

    def _bubble_release(self, _event=None) -> None:
        was_dragged = self.dragged
        self._drag_end()
        if not was_dragged:
            self.expand()

    def expand(self) -> None:
        if self.expanded:
            return
        self.expanded = True
        self.bubble_position = (self.root.winfo_x(), self.root.winfo_y())
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(8, min(screen_w - self.PANEL_WIDTH - 8, self.root.winfo_x() - (self.PANEL_WIDTH - 84)))
        y = max(8, min(screen_h - self.PANEL_HEIGHT - 8, self.root.winfo_y() - (self.PANEL_HEIGHT - 90)))
        self.panel_window.geometry(f"{self.PANEL_WIDTH}x{self.PANEL_HEIGHT}+{x}+{y}")
        self.panel_window.deiconify()
        self.panel_window.lift()
        if self.api_key_available and not self.busy:
            self.status.configure(text="พร้อมรับคำสั่ง", fg=self.MUTED)
        self.panel_window.after(100, self._focus_command)

    def _focus_command(self) -> None:
        self.panel_window.lift()
        self.panel_window.focus_force()
        self.command_entry.focus_force()

    def collapse(self) -> None:
        if not self.expanded:
            return
        self.expanded = False
        self.panel_window.withdraw()
        x, y = self.bubble_position or (self.root.winfo_x(), self.root.winfo_y())
        self.root.geometry(f"76x76+{x}+{y}")
        self.root.deiconify()
        self.root.lift()

    def _set_busy(self, busy: bool, message: str) -> None:
        self.busy = busy
        self.status.configure(text=message, fg=self.ACCENT if busy else self.MUTED)
        self.mic_button.configure(state="disabled" if busy else "normal")
        self.send_button.configure(state="disabled" if busy else "normal")

    def _start_worker(self, worker: Callable[[], None], status: str) -> None:
        if self.busy:
            return
        if not self.api_key_available:
            self.status.configure(text="ยังไม่พบ GEMINI_API_KEY", fg="#f2b45b")
            return
        self._set_busy(True, status)
        threading.Thread(target=worker, daemon=True).start()

    def start_voice(self) -> None:
        self._start_worker(self._listen_and_run, "กำลังฟัง... พูดได้เลย")

    def _listen_and_run(self) -> None:
        try:
            command = self.listen_command()
            if not command:
                self.events.put(("done", "ไม่ได้ยินคำสั่ง ลองพูดอีกครั้งได้เลย"))
                return
            self.events.put(("user", command))
            self._run_command(command)
        except Exception as exc:
            self.events.put(("error", f"ฟังคำสั่งไม่สำเร็จ: {exc}"))

    def send_text(self) -> None:
        command = self.command_entry.get().strip()
        if not command or self.busy:
            return
        self.command_entry.delete(0, "end")
        self._append(command, "user")
        self._start_worker(lambda: self._run_command(command), "กำลังทำงาน...")

    def _run_command(self, command: str) -> None:
        try:
            self.events.put(("status", "กำลังทำงาน..."))
            self.speak(f"รับคำสั่งแล้วครับ กำลังดำเนินการ: {command}")
            self.visibility_ack.clear()
            self.events.put(("hide", ""))
            self.visibility_ack.wait(timeout=1.0)
            result = self.run_agent(command)
            self.speak(result)
            self.events.put(("done", result))
        except Exception as exc:
            self.events.put(("error", f"ทำคำสั่งไม่สำเร็จ: {exc}"))

    def _poll_events(self) -> None:
        while True:
            try:
                kind, message = self.events.get_nowait()
            except queue.Empty:
                break

            if kind == "user":
                self._append(message, "user")
            elif kind == "status":
                self.status.configure(text=message, fg=self.ACCENT)
            elif kind == "hide":
                self.root.withdraw()
                self.panel_window.withdraw()
                self.hidden_for_agent = True
                self.visibility_ack.set()
            elif kind == "done":
                self._restore_window()
                self._append(message, "assistant")
                self._set_busy(False, "พร้อมรับคำสั่ง")
            elif kind == "error":
                self._restore_window()
                self._append(message, "system")
                self._set_busy(False, "เกิดข้อผิดพลาด")

        self.root.after(100, self._poll_events)

    def _restore_window(self) -> None:
        if self.hidden_for_agent:
            self.hidden_for_agent = False
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            if self.expanded:
                self.panel_window.deiconify()
                self.panel_window.lift()
                self.panel_window.attributes("-topmost", True)
            else:
                self.root.lift()

    def close(self) -> None:
        if self.busy:
            self.status.configure(text="รอให้งานปัจจุบันเสร็จก่อนปิด", fg="#f2b45b")
            return
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def launch_widget(run_agent, listen_command, speak, api_key_available: bool) -> None:
    DexterWidget(run_agent, listen_command, speak, api_key_available).run()
