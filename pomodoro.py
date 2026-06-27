import tkinter as tk
from tkinter import font as tkfont
import winsound
import threading

# ══════════════════════════════════════════════════════════════════
# 全局配置
# ══════════════════════════════════════════════════════════════════

WORK_MINUTES = 25
SHORT_BREAK_MINUTES = 5
LONG_BREAK_MINUTES = 15
POMODOROS_BEFORE_LONG_BREAK = 4

# ── 颜色方案（浅色暖调：温暖·柔和·简洁）──────────────
BG      = "#F7F2EC"   # 窗口背景（米白）
SURFACE = "#EAE3D0"   # 标签栏背景（暖灰）
OVERLAY = "#D0D2CC"   # 次要按钮背景（中灰）
TEXT    = "#6F655E"   # 主要文字（深棕灰）
SUBTEXT = "#9A8E85"   # 次要文字（中棕灰）
RED     = "#C65A4A"   # 专注模式（陶土红）
GREEN   = "#6A9E6A"   # 短休模式（鼠尾草绿）
BLUE    = "#6A8EA8"   # 长休模式（灰蓝）

# 模式名 → 颜色 + 显示文字
MODE_COLORS = {
    "work":        {"arc": RED,   "label": "专注时间"},
    "short_break": {"arc": GREEN, "label": "短暂休息"},
    "long_break":  {"arc": BLUE,  "label": "长时休息"},
}

# 模式名 → 时长（分钟）
MODE_MINUTES = {
    "work":        WORK_MINUTES,
    "short_break": SHORT_BREAK_MINUTES,
    "long_break":  LONG_BREAK_MINUTES,
}

# ── 圆弧几何参数 ──────────────────────────────────────
CANVAS_SIZE = 320
ARC_CENTER  = CANVAS_SIZE // 2
ARC_RADIUS  = 130
ARC_WIDTH   = 14
# 外接矩形（两个方法共用，只算一次）
ARC_BBOX = (
    ARC_CENTER - ARC_RADIUS, ARC_CENTER - ARC_RADIUS,
    ARC_CENTER + ARC_RADIUS, ARC_CENTER + ARC_RADIUS,
)


# ══════════════════════════════════════════════════════════════════
# 主应用类
# ══════════════════════════════════════════════════════════════════

class PomodoroApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("番茄钟")
        self.resizable(False, False)
        self.configure(bg=BG)

        # 预创建字体对象：tkinter 每次收到字符串元组都会重新解析，
        # Font 对象只解析一次，传给 create_text / itemconfig 更高效
        self._font_time  = tkfont.Font(family="Courier New",        size=48, weight="bold")
        self._font_mode  = tkfont.Font(family="Microsoft YaHei UI", size=13)
        self._font_tip   = tkfont.Font(family="Microsoft YaHei UI", size=9)
        self._font_ui    = tkfont.Font(family="Microsoft YaHei UI", size=13)

        # ── 状态 ──
        self.mode           = "work"
        self.total_seconds  = WORK_MINUTES * 60
        self.remaining      = self.total_seconds
        self.running        = False
        self.pomodoro_count = 0
        self._after_id      = None

        self._build_ui()
        self._center_window()

    # ══════════════════════════════════════════════════
    # UI 构建（只运行一次）
    # ══════════════════════════════════════════════════

    def _build_ui(self):
        outer = tk.Frame(self, bg=BG, padx=24, pady=20)
        outer.pack()

        # ── 标题行 ──
        title_row = tk.Frame(outer, bg=BG)
        title_row.pack(fill="x")
        tk.Label(title_row, text="🍅 番茄钟", bg=BG, fg=RED,
                 font=("Microsoft YaHei UI", 16, "bold")).pack(side="left")
        self._count_label = tk.Label(title_row, text="", bg=BG, fg=SUBTEXT,
                                     font=self._font_ui)
        self._count_label.pack(side="right")

        # ── 模式标签页 ──
        tabs = tk.Frame(outer, bg=SURFACE, bd=0, highlightthickness=0)
        tabs.pack(fill="x", pady=(14, 0))
        for i in range(3):
            tabs.columnconfigure(i, weight=1)

        self._tab_btns = {}
        tab_defs = [("work", "专注"), ("short_break", "短休"), ("long_break", "长休")]
        for col, (mode_key, label) in enumerate(tab_defs):
            btn = tk.Button(
                tabs, text=label, bd=0, relief="flat", cursor="hand2",
                font=("Microsoft YaHei UI", 10), padx=0, pady=8,
                command=lambda m=mode_key: self._switch_mode(m),
            )
            btn.grid(row=0, column=col, sticky="nsew")
            self._tab_btns[mode_key] = btn

        # ── 画布 ──
        self._canvas = tk.Canvas(
            outer, width=CANVAS_SIZE, height=CANVAS_SIZE,
            bg=BG, highlightthickness=0,
        )
        self._canvas.pack(pady=(8, 0))

        # ── 圆点进度（创建一次，只 configure fg 颜色）──
        dots_frame = tk.Frame(outer, bg=BG)
        dots_frame.pack(pady=(0, 4))
        self._dot_labels = [
            tk.Label(dots_frame, text="●", bg=BG, fg=OVERLAY, font=("", 10))
            for _ in range(POMODOROS_BEFORE_LONG_BREAK)
        ]
        for lbl in self._dot_labels:
            lbl.pack(side="left", padx=3)

        # ── 控制按钮 ──
        ctrl = tk.Frame(outer, bg=BG)
        ctrl.pack()
        self._icon_btn(ctrl, "↺", self._reset, OVERLAY).pack(side="left", padx=(0, 14))
        self._start_btn = tk.Button(
            ctrl, text="开始", width=8,
            font=("Microsoft YaHei UI", 13, "bold"),
            bd=0, relief="flat", cursor="hand2",
            pady=10, padx=22,
            command=self._toggle,
        )
        self._start_btn.pack(side="left")
        self._icon_btn(ctrl, "⏭", self._skip, OVERLAY).pack(side="left", padx=(14, 0))

        # ── 画布元素（创建一次，后续用 itemconfig 更新）──
        # 背景圆圈（静态，永不更改）
        self._canvas.create_oval(*ARC_BBOX, outline=SURFACE, width=ARC_WIDTH)
        # 进度弧（每秒更新 extent；切换模式时更新 outline 颜色）
        self._arc_item = self._canvas.create_arc(
            *ARC_BBOX, start=90, extent=-359.99,
            outline=RED, width=ARC_WIDTH, style="arc",
        )
        # 时间数字（每秒更新 text）
        self._time_item = self._canvas.create_text(
            ARC_CENTER, ARC_CENTER - 14,
            text="25:00", fill=TEXT, font=self._font_time,
        )
        # 模式文字（切换模式时更新）
        self._mode_item = self._canvas.create_text(
            ARC_CENTER, ARC_CENTER + 44,
            text="专注时间", fill=RED, font=self._font_mode,
        )
        # 提示文字（开始/停止时更新）
        self._tip_item = self._canvas.create_text(
            ARC_CENTER, ARC_CENTER + 70,
            text="点击开始专注", fill=SUBTEXT, font=self._font_tip,
        )

        # 初始化所有与模式相关的颜色/样式
        self._apply_mode_style()

    def _icon_btn(self, parent, text, cmd, bg_color):
        return tk.Button(
            parent, text=text, font=("Segoe UI Symbol", 16),
            bd=0, relief="flat", cursor="hand2",
            bg=bg_color, fg=TEXT, activebackground=OVERLAY, activeforeground=TEXT,
            width=2, pady=6, command=cmd,
        )

    def _center_window(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    # ══════════════════════════════════════════════════
    # 模式样式（切换模式时调用一次，不在每帧调用）
    # ══════════════════════════════════════════════════

    def _apply_mode_style(self):
        """刷新所有与当前模式相关的颜色和文字（只在模式切换时调用）"""
        color = MODE_COLORS[self.mode]["arc"]
        label = MODE_COLORS[self.mode]["label"]

        self._canvas.itemconfig(self._arc_item,  outline=color)
        self._canvas.itemconfig(self._mode_item, text=label, fill=color)
        self._start_btn.configure(bg=color, fg=BG,
                                   activebackground=color, activeforeground=BG)
        for key, btn in self._tab_btns.items():
            if key == self.mode:
                btn.configure(bg=color, fg=BG,
                               activebackground=color, activeforeground=BG)
            else:
                btn.configure(bg=SURFACE, fg=SUBTEXT,
                               activebackground=OVERLAY, activeforeground=TEXT)

        completed_in_cycle = self.pomodoro_count % POMODOROS_BEFORE_LONG_BREAK
        for i, lbl in enumerate(self._dot_labels):
            lbl.configure(fg=RED if i < completed_in_cycle else OVERLAY)

    # ══════════════════════════════════════════════════
    # 每帧刷新（只更新真正每秒变化的内容）
    # ══════════════════════════════════════════════════

    def _update_display(self):
        """每秒调用：只更新倒计时数字和进度弧的角度"""
        mins, secs = divmod(self.remaining, 60)
        self._canvas.itemconfig(self._time_item, text=f"{mins:02d}:{secs:02d}")

        ratio = self.remaining / self.total_seconds
        if ratio > 0:
            self._canvas.itemconfig(
                self._arc_item, extent=-ratio * 359.99, state=tk.NORMAL,
            )
        else:
            # ratio == 0 时隐藏弧，避免 tkinter 将 360° 当作 0° 处理
            self._canvas.itemconfig(self._arc_item, state=tk.HIDDEN)

    # ══════════════════════════════════════════════════
    # 计时逻辑
    # ══════════════════════════════════════════════════

    def _toggle(self):
        if self.running:
            self._pause()
        else:
            self._start()

    def _start(self):
        self.running = True
        self._start_btn.configure(text="暂停")
        self._canvas.itemconfig(self._tip_item, text="")
        self._tick()

    def _stop(self):
        """停止计时并将按钮重置为"开始"——reset / switch / end 的公共入口"""
        self.running = False
        self._start_btn.configure(text="开始")
        self._canvas.itemconfig(self._tip_item, text="点击开始专注")
        if self._after_id:
            self.after_cancel(self._after_id)

    def _pause(self):
        """暂停（可继续），与 _stop 的区别：按钮文字变"继续"，提示隐藏"""
        self._stop()
        self._start_btn.configure(text="继续")
        self._canvas.itemconfig(self._tip_item, text="")

    def _reset(self):
        self._stop()
        self.remaining = self.total_seconds
        self._update_display()

    def _skip(self):
        self._stop()
        self._advance_mode(completed=False)

    def _tick(self):
        if not self.running:
            return
        if self.remaining > 0:
            self.remaining -= 1
            self._update_display()
            self._after_id = self.after(1000, self._tick)
        else:
            self._on_timer_end()

    def _on_timer_end(self):
        self._stop()
        self._advance_mode(completed=(self.mode == "work"))

    def _advance_mode(self, completed: bool):
        """
        决定并切换到下一阶段。
        completed=True  → 专注自然结束，计入番茄数
        completed=False → 用户手动跳过，不计数
        """
        if completed:
            self.pomodoro_count += 1
            self._count_label.configure(text=f"已完成 {self.pomodoro_count} 个番茄")
            threading.Thread(target=self._beep, daemon=True).start()

        if self.mode == "work":
            if completed and self.pomodoro_count % POMODOROS_BEFORE_LONG_BREAK == 0:
                next_mode = "long_break"
            else:
                next_mode = "short_break"
        else:
            next_mode = "work"

        self._set_mode(next_mode)

    def _switch_mode(self, mode):
        self._stop()
        self._set_mode(mode)

    def _set_mode(self, mode):
        """所有模式切换的唯一入口：更新状态、重置时间、刷新样式"""
        self.mode          = mode
        self.total_seconds = MODE_MINUTES[mode] * 60
        self.remaining     = self.total_seconds
        self._update_display()
        self._apply_mode_style()

    # ══════════════════════════════════════════════════
    # 提示音（后台线程，不阻塞 UI）
    # ══════════════════════════════════════════════════

    def _beep(self):
        for _ in range(3):
            winsound.Beep(880, 200)
            winsound.Beep(660, 150)


if __name__ == "__main__":
    app = PomodoroApp()
    app.mainloop()
