# -*- coding: utf-8 -*-
"""
sound.py —— 音律探索器 / Sound Explorer（给孩子用的乐音小工具）

Features / 功能
  1. 钢琴 88 键（A0 ~ C8）图形键盘：可点选、可点击发声，显示音名 / 唱名 / 频率
     88-key piano keyboard (A0–C8): click any key to hear it, showing note / solfege / frequency
  2. 右侧频率表：全部 88 键的「音名 + 唱名 + 频率」，点一下就播放
     Table of all 88 keys with frequency; click to play
  3. 波形可选：正弦 / 三角波 / 方波 / 锯齿波；可调音量、时长、A4 基准频率
     Waveforms: sine / triangle / square / sawtooth; volume, length, A4 reference
  4. 内置演示：C 大调音阶、C 大调和弦、八度对比
     Demos: C major scale, C major chord, octave comparison
  5. 麦克风实时采集（可自选设备）：显示频谱与主音（基频），给出最接近音名与音准偏差（音分）
     Live mic input (device selectable): spectrum + fundamental (YIN), nearest note, cents offset
  6. 音高尺：把哼唱的音高映射到钢琴键盘上，直观看到自己哼的是哪一个键
     Pitch ruler: maps your hummed pitch onto the keyboard

界面支持中 / 英双语：界面右上角的“界面”下拉框可随时切换，也可用 --lang en 启动。
Bilingual UI: switch from the "UI" combo box, or start with `--lang en`.

运行前安装依赖 / Install first:
    pip install numpy sounddevice
"""

import math
import queue
import sys
import tkinter as tk
from collections import deque
from tkinter import messagebox, ttk

# ------------------------- 依赖检查 -------------------------
MISSING = []
try:
    import numpy as np
except Exception:
    np = None
    MISSING.append("numpy")
try:
    import sounddevice as sd
except Exception:
    sd = None
    MISSING.append("sounddevice")

if MISSING:
    print("缺少依赖 / Missing dependencies, please run:")
    print("    pip install " + " ".join(MISSING))
    sys.exit(1)


# ------------------------- 乐理工具 -------------------------
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SOLFEGE = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
BLACK_PC = {1, 3, 6, 8, 10}
MIDI_LOW, MIDI_HIGH = 21, 108          # A0 ~ C8，共 88 键

# 波形：(内部名, 中文名, 英文名)
WAVES = [("sine", "正弦", "Sine"),
         ("triangle", "三角波", "Triangle"),
         ("square", "方波", "Square"),
         ("sawtooth", "锯齿波", "Sawtooth")]

# ------------------------- 界面文案（中 / 英） -------------------------
STRINGS = {
    "zh": {
        "app_title": "音律探索器 · 钢琴频率 & 哼唱测频",
        "language": "界面:",
        "timbre": "音色:", "volume": "音量:", "length": "时长(s):",
        "sustain": "按住持续发声", "a4_ref": "A4基准(Hz):",
        "custom_freq": "任意频率:", "play": "播放", "stop": "停止",
        "scale": "C大调音阶", "chord": "C大调和弦", "octave": "八度对比",
        "kb_title": "钢琴键盘（A0 ~ C8，共 88 键） · 左键点击发声",
        "tip_hover": "提示：把鼠标移到琴键上可以看音名和频率",
        "hover_fmt": "%s（%s）  %.2f Hz   —— 点击可发声",
        "selected_fmt": "已选中：%s（%s）  %.2f Hz",
        "mic_dev": "麦克风设备:", "refresh": "刷新",
        "hum_tip": "哼唱时请靠近麦克风、保持一个稳定长音",
        "start": "开始听音（打开麦克风）", "stop_listen": "停止听音",
        "listening_fmt": "正在听音：%s | %d Hz",
        "stopped_fmt": "已停止：%s", "mic_idle": "麦克风：未开启",
        "level_fmt": "正在听音：%s | %d Hz | 电平 %.4f %s",
        "snd_yes": "（有声音）", "snd_no": "（安静）",
        "no_device": "未找到可用的麦克风设备，请接好设备后点“刷新”",
        "det_title": "哼唱识别结果", "pitch": "主音:", "nearest": "最接近的键:",
        "tuning": "音准:", "in_tune": "很准！",
        "sharp_fmt": "偏高 %.0f 音分（唱低一点）", "flat_fmt": "偏低 %.0f 音分（唱高一点）",
        "ruler_title": "音高尺（红色=你哼的音，蓝色三角=选中的键）",
        "low": "低音", "high": "高音", "lo_short": "低", "hi_short": "高",
        "cents_title": "音准偏差（音分 cent，100 音分 = 1 个半音）",
        "spec_title": "实时频谱（红线=基频主音，虚线=泛音 2× 3×）",
        "no_sound": "（没有检测到声音）", "unsteady": "（有声音，但没识别出稳定的音高）",
        "unsteady_note": "有声音，但不是稳定的音", "hum_steady": "请哼一个持续的长音",
        "f0_fmt": "基频 %.1f Hz",
        "all_keys": "全部 88 键频率表（点击播放）",
        "white": "白键", "black": "黑键", "dash": "--",
        "sys_default": "系统默认", "def_mark": "★默认", "unknown_api": "未知接口",
        "err_play": "播放失败", "err_title": "提示", "err_mic": "无法打开麦克风",
        "msg_number": "请输入数字频率，例如 440", "msg_range": "频率请填 1 ~ 20000 Hz",
        "err_mic_msg": "设备：%s\n请确认已连接并被允许访问（Windows 隐私设置 → 麦克风）。\n\n错误信息：%s | %s",
    },
    "en": {
        "app_title": "Sound Explorer · Piano Frequencies & Pitch Detection",
        "language": "UI:",
        "timbre": "Wave:", "volume": "Vol:", "length": "Len(s):",
        "sustain": "Hold to sustain", "a4_ref": "A4 ref (Hz):",
        "custom_freq": "Freq:", "play": "Play", "stop": "Stop",
        "scale": "C major scale", "chord": "C major chord", "octave": "Octaves",
        "kb_title": "Piano keyboard (A0 – C8, 88 keys) · click a key to play",
        "tip_hover": "Tip: hover a key to see its note name and frequency",
        "hover_fmt": "%s (%s)  %.2f Hz   — click to play",
        "selected_fmt": "Selected: %s (%s)  %.2f Hz",
        "mic_dev": "Input device:", "refresh": "Refresh",
        "hum_tip": "Hum close to the mic and hold one steady note",
        "start": "Start listening", "stop_listen": "Stop listening",
        "listening_fmt": "Listening: %s | %d Hz",
        "stopped_fmt": "Stopped: %s", "mic_idle": "Microphone: off",
        "level_fmt": "Listening: %s | %d Hz | level %.4f %s",
        "snd_yes": "(sound)", "snd_no": "(quiet)",
        "no_device": "No input device found — connect a mic and click Refresh.",
        "det_title": "Pitch detection", "pitch": "Pitch:", "nearest": "Nearest key:",
        "tuning": "Tuning:", "in_tune": "In tune!",
        "sharp_fmt": "%.0f cents sharp (sing a bit lower)",
        "flat_fmt": "%.0f cents flat (sing a bit higher)",
        "ruler_title": "Pitch ruler (red = your voice, blue triangle = selected key)",
        "low": "low", "high": "high", "lo_short": "flat", "hi_short": "sharp",
        "cents_title": "Tuning offset (cents; 100 cents = 1 semitone)",
        "spec_title": "Live spectrum (red = fundamental, dashed = 2x / 3x harmonics)",
        "no_sound": "(no sound detected)", "unsteady": "(sound detected, but no steady pitch)",
        "unsteady_note": "Sound detected, but not a steady tone",
        "hum_steady": "Please hum one sustained note",
        "f0_fmt": "f0 %.1f Hz",
        "all_keys": "All 88 keys (click to play)",
        "white": "white", "black": "black", "dash": "--",
        "sys_default": "System default", "def_mark": "★default", "unknown_api": "unknown API",
        "err_play": "Playback failed", "err_title": "Notice", "err_mic": "Cannot open microphone",
        "msg_number": "Please enter a number, e.g. 440", "msg_range": "Frequency must be 1 – 20000 Hz",
        "err_mic_msg": "Device: %s\nCheck that it is connected and allowed (Windows Privacy → Microphone).\n\nError: %s | %s",
    },
}


def midi_to_freq(midi, a4=440.0):
    """MIDI 音高编号 -> 频率(Hz)，A4(69) = a4"""
    return a4 * (2.0 ** ((midi - 69) / 12.0))


def freq_to_midi(freq, a4=440.0):
    """频率(Hz) -> MIDI 音高编号（小数，含音分信息）"""
    return 69.0 + 12.0 * math.log2(freq / a4)


def note_name(midi):
    """MIDI 编号 -> (音名, 唱名)，如 (69) -> ('A4', 'La')"""
    pc = midi % 12
    return "%s%d" % (NOTE_NAMES[pc], midi // 12 - 1), SOLFEGE[pc]


# ------------------------- 合成音色 -------------------------
def make_tone(freq, dur, wave, vol, sr):
    """生成单音波形（带起振/收尾包络，避免爆音；谐波按奈奎斯特频率截断，避免混叠）"""
    n = max(1, int(dur * sr))
    t = np.arange(n) / float(sr)
    nyq = sr * 0.5

    if wave == "sine":
        y = np.sin(2 * np.pi * freq * t)
    else:
        # 加性合成：只累加奈奎斯特频率以下的谐波
        y = np.zeros_like(t)
        if wave == "square":                      # 方波：奇次谐波
            k = 1
            while freq * k < nyq * 0.95:
                y += np.sin(2 * np.pi * freq * k * t) / k
                k += 2
            y *= 4.0 / np.pi
        elif wave == "sawtooth":                  # 锯齿波：全部谐波
            k = 1
            while freq * k < nyq * 0.95:
                y += ((-1) ** (k + 1)) * np.sin(2 * np.pi * freq * k * t) / k
                k += 1
            y *= 2.0 / np.pi
        elif wave == "triangle":                  # 三角波：奇次谐波，1/k^2
            k, sign = 1, 1
            while freq * k < nyq * 0.95:
                y += sign * np.sin(2 * np.pi * freq * k * t) / (k * k)
                sign = -sign
                k += 2
            y *= 8.0 / (np.pi ** 2)
        else:
            y = np.sin(2 * np.pi * freq * t)

    peak = float(np.max(np.abs(y))) or 1.0
    y = y / peak                                   # 归一化，音量只由 vol 决定

    env = np.ones(n)
    a = max(1, int(0.015 * sr))
    r = max(1, int(min(0.25, dur * 0.4) * sr))
    env[:a] = np.linspace(0.0, 1.0, a)
    env[-r:] *= np.linspace(1.0, 0.0, r)

    return (y * env * float(vol)).astype(np.float32)


def yin_pitch(x, sr, fmin=60.0, fmax=2000.0, threshold=0.12, accept=0.35):
    """
    YIN 基频检测：比单纯的 FFT 峰值更稳，也不容易出现“低八度”误判。
      threshold : 强周期阈值，低于它认为是有声（高置信）
      accept    : 弱周期阈值，超过它认为没有在唱（避免把噪声当成低音）
    返回基频(Hz)，检测不到返回 None。
    """
    n = len(x)
    tau_min = max(2, int(sr / fmax))
    tau_max = min(n // 2, int(sr / fmin))
    if tau_max <= tau_min:
        return None

    # 1) 线性自相关（零填充后用 FFT 求，避免循环卷积污染）
    nfft = 1 << (2 * n - 1).bit_length()
    xf = np.fft.rfft(x, nfft)
    r = np.fft.irfft(xf * np.conj(xf))[:n]

    # 2) 差分函数 d(tau) = sum (x[j] - x[j+tau])^2
    cs = np.concatenate(([0.0], np.cumsum(x * x)))
    tau = np.arange(n)
    d = np.empty(n)
    d[0] = 0.0
    d[1:] = (cs[n - 1 - tau[1:]] + (cs[n] - cs[tau[1:]])) - 2.0 * r[1:]

    # 3) 累积均值归一化差分
    cum = np.cumsum(d[1:])
    dn = d[1:] / (cum / tau[1:] + 1e-12)      # dn[j] 对应 tau = j + 1

    # 4) 只考察局部极小点（真正的周期谷）
    lo, hi = tau_min - 1, tau_max - 1
    idx = np.arange(lo, hi + 1)
    if idx.size < 3:
        return None
    is_min = (dn[idx] <= dn[idx - 1]) & (dn[idx] <= dn[idx + 1])
    cand = idx[is_min]
    if cand.size == 0:
        return None
    cand_val = dn[cand]

    best = float(cand_val.min())
    if best > accept:                          # 周期性太差 -> 认为没在唱
        return None

    strong = cand[cand_val <= threshold]
    if strong.size:
        i = int(strong[0])                     # 取周期最短的高置信谷
    else:
        # 噪声较大时：在“接近最优”的谷里仍取周期最短的，避免掉到低八度
        pool = cand[cand_val <= best * 1.15 + 1e-9]
        i = int(pool[0]) if pool.size else int(cand[0])

    # 5) 抛物线插值求小数周期 -> 精确频率
    a, b, c = dn[i - 1], dn[i], dn[i + 1]
    den = a - 2.0 * b + c
    shift = 0.5 * (a - c) / den if den != 0 else 0.0
    if abs(shift) > 1:
        shift = 0.0
    period = (i + 1) + shift
    if period <= 0:
        return None
    return sr / period


# ------------------------- 主程序 -------------------------
class SoundApp:
    def __init__(self, root, lang="zh"):
        self.root = root
        self.lang = lang if lang in STRINGS else "zh"
        self._i18n = []                               # 需要随语言刷新的控件
        root.title(self.T("app_title"))
        root.geometry("1240x820")
        root.minsize(1000, 700)

        # ---- 状态变量 ----
        self.a4 = tk.DoubleVar(value=440.0)
        self.wave_idx = tk.IntVar(value=0)           # 波形序号（与语言无关）
        self.vol = tk.DoubleVar(value=0.35)
        self.dur = tk.DoubleVar(value=1.2)
        self.sustain = tk.BooleanVar(value=False)
        self.custom_freq = tk.StringVar(value="440")
        self.sel_midi = tk.IntVar(value=69)          # 当前选中的键（默认中央 A4）
        self.status = tk.StringVar()
        self.hover_midi = None
        self.keys = []                                # 键盘布局缓存

        # ---- 麦克风状态 ----
        self.mic_on = False
        self.stream = None
        self.mic_devices = []                         # 可用输入设备列表
        self.mic_label_to_index = {}                  # 下拉框文字 -> 设备序号
        self.mic_dev_var = tk.StringVar(value="")
        self.mic_dev_index = None                     # None = 系统默认
        self.dev_desc = self.T("sys_default")         # 当前设备描述
        self.q = queue.Queue()
        self.NFFT = 16384
        self.mic_buf = np.zeros(self.NFFT, dtype=np.float32)
        self.sr_in = self._default_sr(kind="input")
        self.sr_out = self._default_sr(kind="output")
        self.hist = deque(maxlen=7)                   # 主音平滑
        self.detected = None                          # {'f','midi','cents','X','freqs'}
        self.last_det_midi = None
        self.level = 0.0
        self.spec_disp = None
        self.spec_bins = None                         # 频谱像素列 -> FFT bin 区间
        self.spec_cols = 0
        self.mic_status = tk.StringVar(value=self.T("mic_idle"))
        self.det_var = tk.StringVar(value=self.T("dash") + " Hz")
        self.note_var = tk.StringVar(value=self.T("dash"))
        self.cents_var = tk.StringVar(value=self.T("dash"))

        self._build_ui()
        self._fill_list()
        self.root.after(120, self._first_draw)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- 多语言 ----------
    def T(self, key):
        """取当前语言的文案"""
        return STRINGS.get(self.lang, STRINGS["zh"]).get(key, key)

    def wave_labels(self):
        """当前语言下的波形名称列表"""
        return [w[1] if self.lang == "zh" else w[2] for w in WAVES]

    def wave_key(self):
        return WAVES[max(0, min(self.wave_idx.get(), len(WAVES) - 1))][0]

    def _reg(self, widget, key, attr="text"):
        """登记控件，语言切换时自动改文案"""
        self._i18n.append((widget, attr, key))
        try:
            widget.configure({attr: self.T(key)})
        except Exception:
            pass
        return widget

    def on_lang_changed(self, event=None):
        self.lang = "en" if self.lang_var.get() == "English" else "zh"
        self._apply_lang()

    def _apply_lang(self):
        for w, attr, key in self._i18n:
            try:
                w.configure({attr: self.T(key)})
            except Exception:
                pass
        self.root.title(self.T("app_title"))
        self.wave_combo.configure(values=self.wave_labels())
        self.wave_combo.current(self.wave_idx.get())
        self.refresh_devices()          # 下拉框首项“系统默认”也要跟着翻译
        self._fill_list()
        self.status.set(self.T("tip_hover"))
        self.mic_btn.configure(text=self.T("stop_listen") if self.mic_on else self.T("start"))
        if not self.mic_on:
            self.dev_desc = self.T("sys_default")
            self.mic_status.set(self.T("mic_idle"))
            self.det_var.set(self.T("dash") + " Hz")
            self.note_var.set(self.T("dash"))
            self.cents_var.set(self.T("dash"))
        self.draw_keyboard()
        self.draw_ruler()
        self.draw_cents()
        self._rebuild_spec_bins()

    # ---------- 采样率 ----------
    @staticmethod
    def _default_sr(kind="input"):
        try:
            idx = sd.default.device[0 if kind == "input" else 1]
            dev = sd.query_devices(idx, kind) if idx is not None else sd.query_devices(kind=kind)
            sr = int(dev.get("default_samplerate") or 44100)
            return sr
        except Exception:
            return 44100

    # ---------- 麦克风设备 ----------
    @staticmethod
    def list_input_devices():
        """枚举系统中所有可用的输入设备（麦克风）"""
        out = []
        try:
            devs = list(sd.query_devices())      # DeviceList 不是 list 的子类，先转成普通列表
        except Exception:
            devs = []
        try:
            default_in = sd.default.device[0]
        except Exception:
            default_in = None
        try:
            hostapis = list(sd.query_hostapis())
        except Exception:
            hostapis = []
        for i, d in enumerate(devs):
            if not isinstance(d, dict):
                continue
            try:
                if int(d.get("max_input_channels", 0) or 0) <= 0:
                    continue
            except Exception:
                continue
            sr = int(d.get("default_samplerate") or 44100)
            api = ""
            try:                                  # 驱动接口名（MME / DirectSound / WASAPI / WDM-KS）
                ha = int(d.get("hostapi", -1))
                if 0 <= ha < len(hostapis):
                    api = str(hostapis[ha].get("name", ""))
            except Exception:
                api = ""
            out.append({"index": i, "name": str(d.get("name", "设备 %d" % i)),
                        "sr": sr, "api": api, "is_default": (i == default_in)})
        return out

    def refresh_devices(self):
        """重新枚举设备并刷新下拉框"""
        prev_index = self.mic_dev_index          # 刷新后尽量保持原来的选择
        self.mic_devices = self.list_input_devices()
        labels = [self.T("sys_default")]
        self.mic_label_to_index = {}
        seen = set()
        for d in self.mic_devices:
            base = "%s · %s（%d Hz）" % (d["name"], d["api"] or self.T("unknown_api"), d["sr"])
            label = base if base not in seen else "%s #%d" % (base, d["index"])   # 同名设备保证唯一
            seen.add(base)
            if d["is_default"]:
                label += " " + self.T("def_mark")
            self.mic_label_to_index[label] = d["index"]
            labels.append(label)
        self.mic_combo.configure(values=labels)
        keep = None
        if prev_index is not None:
            for lb, ix in self.mic_label_to_index.items():
                if ix == prev_index:
                    keep = lb
                    break
        self.mic_dev_var.set(keep if keep else labels[0])
        self.apply_device()
        if len(self.mic_devices) == 0:
            self.mic_status.set(self.T("no_device"))

    def apply_device(self):
        """根据下拉框选择更新设备序号与采样率"""
        idx = self.mic_label_to_index.get(self.mic_dev_var.get())
        self.mic_dev_index = idx
        if idx is None:
            self.sr_in = self._default_sr("input")
            self.dev_desc = self.T("sys_default")
        else:
            d = next((x for x in self.mic_devices if x["index"] == idx), None)
            self.sr_in = (d["sr"] if d else self._default_sr("input"))
            self.dev_desc = (d["name"] if d else self.T("sys_default"))
        self.hist.clear()
        self.detected = None
        self.spec_disp = None
        if hasattr(self, "spec"):
            self._rebuild_spec_bins()

    def on_device_selected(self, event=None):
        """切换设备；若正在听音则自动用新设备重新开始"""
        self.apply_device()
        if self.mic_on:
            self.stop_mic()
            self.start_mic()

    # ---------- 界面 ----------
    def _build_ui(self):
        top = ttk.Frame(self.root, padding=(8, 6))
        top.pack(side=tk.TOP, fill=tk.X)

        self._reg(ttk.Label(top), "timbre").pack(side=tk.LEFT)
        self.wave_combo = ttk.Combobox(top, width=9, state="readonly", values=self.wave_labels())
        self.wave_combo.current(self.wave_idx.get())
        self.wave_combo.pack(side=tk.LEFT, padx=(2, 10))
        self.wave_combo.bind("<<ComboboxSelected>>",
                             lambda e: self.wave_idx.set(self.wave_combo.current()))

        self._reg(ttk.Label(top), "volume").pack(side=tk.LEFT)
        ttk.Scale(top, from_=0.05, to=1.0, orient=tk.HORIZONTAL, length=80,
                  variable=self.vol).pack(side=tk.LEFT, padx=(2, 10))

        self._reg(ttk.Label(top), "length").pack(side=tk.LEFT)
        ttk.Scale(top, from_=0.2, to=3.0, orient=tk.HORIZONTAL, length=80,
                  variable=self.dur).pack(side=tk.LEFT, padx=(2, 10))

        self._reg(ttk.Checkbutton(top, variable=self.sustain), "sustain").pack(side=tk.LEFT, padx=(0, 10))

        self._reg(ttk.Label(top), "a4_ref").pack(side=tk.LEFT)
        sp = ttk.Spinbox(top, from_=400, to=460, width=5, textvariable=self.a4,
                         command=self.on_a4_changed)
        sp.pack(side=tk.LEFT, padx=(2, 10))
        sp.bind("<Return>", lambda e: self.on_a4_changed())

        self._reg(ttk.Label(top), "custom_freq").pack(side=tk.LEFT)
        ttk.Entry(top, width=8, textvariable=self.custom_freq).pack(side=tk.LEFT, padx=2)
        self._reg(ttk.Button(top, width=6, command=self.play_custom), "play").pack(side=tk.LEFT, padx=2)
        self._reg(ttk.Button(top, width=6, command=self.stop_all), "stop").pack(side=tk.LEFT, padx=(2, 10))

        self._reg(ttk.Button(top, command=self.demo_scale), "scale").pack(side=tk.LEFT, padx=2)
        self._reg(ttk.Button(top, command=self.demo_chord), "chord").pack(side=tk.LEFT, padx=2)
        self._reg(ttk.Button(top, command=self.demo_octave), "octave").pack(side=tk.LEFT, padx=(2, 10))

        # 界面语言切换
        self._reg(ttk.Label(top), "language").pack(side=tk.LEFT)
        self.lang_var = tk.StringVar(value="English" if self.lang == "en" else "中文")
        lc = ttk.Combobox(top, width=7, state="readonly", textvariable=self.lang_var,
                          values=["中文", "English"])
        lc.current(1 if self.lang == "en" else 0)
        lc.pack(side=tk.LEFT, padx=2)
        lc.bind("<<ComboboxSelected>>", self.on_lang_changed)

        # ---- 钢琴键盘 ----
        kb_frame = ttk.LabelFrame(self.root, padding=(8, 6))
        self._reg(kb_frame, "kb_title")
        kb_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 6))
        self.kb = tk.Canvas(kb_frame, height=180, bg="#f2f2f2", highlightthickness=1,
                            highlightbackground="#999")
        self.kb.pack(fill=tk.X)
        self.kb.bind("<Configure>", lambda e: self.draw_keyboard())
        self.kb.bind("<Motion>", self.on_kb_motion)
        self.kb.bind("<Leave>", self.on_kb_leave)
        self.kb.bind("<ButtonPress-1>", self.on_kb_press)
        self.kb.bind("<ButtonRelease-1>", self.on_kb_release)

        ttk.Label(self.root, textvariable=self.status, anchor="w").pack(side=tk.TOP, fill=tk.X, padx=10)

        # ---- 下半部分 ----
        body = ttk.Frame(self.root, padding=(8, 6))
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        for i in range(6):
            left.rowconfigure(i, weight=1 if i >= 2 else 0)
        left.columnconfigure(0, weight=1)

        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew")

        # 麦克风控制行
        mic_bar = ttk.Frame(left)
        mic_bar.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.mic_btn = ttk.Button(mic_bar, command=self.toggle_mic)
        self._reg(self.mic_btn, "start")
        self.mic_btn.grid(row=0, column=0)
        self._reg(ttk.Label(mic_bar), "mic_dev").grid(row=0, column=1, padx=(10, 2))
        self.mic_combo = ttk.Combobox(mic_bar, width=30, state="readonly",
                                      textvariable=self.mic_dev_var)
        self.mic_combo.grid(row=0, column=2)
        self.mic_combo.bind("<<ComboboxSelected>>", self.on_device_selected)
        self._reg(ttk.Button(mic_bar, width=5, command=self.refresh_devices),
                  "refresh").grid(row=0, column=3, padx=6)
        self._reg(ttk.Label(mic_bar), "hum_tip").grid(row=0, column=4, padx=(10, 0))
        ttk.Label(mic_bar, textvariable=self.mic_status).grid(row=1, column=0, columnspan=5,
                                                              sticky="w", pady=(3, 0))

        # 识别结果
        info = ttk.Frame(left)
        info.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        big = ttk.LabelFrame(info, padding=(8, 4))
        self._reg(big, "det_title")
        big.pack(fill=tk.X)
        self._reg(ttk.Label(big), "pitch").grid(row=0, column=0, sticky="w")
        ttk.Label(big, textvariable=self.det_var, font=("Consolas", 16, "bold"),
                  foreground="#c0392b").grid(row=0, column=1, sticky="w", padx=(4, 20))
        self._reg(ttk.Label(big), "nearest").grid(row=0, column=2, sticky="w")
        ttk.Label(big, textvariable=self.note_var, font=("Microsoft YaHei", 12, "bold"),
                  foreground="#1a7f37").grid(row=0, column=3, sticky="w", padx=(4, 20))
        self._reg(ttk.Label(big), "tuning").grid(row=0, column=4, sticky="w")
        ttk.Label(big, textvariable=self.cents_var, font=("Microsoft YaHei", 11),
                  foreground="#1f4e79").grid(row=0, column=5, sticky="w", padx=4)

        # 音高尺
        ruler_box = ttk.LabelFrame(left, padding=(4, 2))
        self._reg(ruler_box, "ruler_title")
        ruler_box.grid(row=2, column=0, sticky="nsew", pady=(0, 4))
        self.ruler = tk.Canvas(ruler_box, height=120, bg="white", highlightthickness=1,
                               highlightbackground="#bbb")
        self.ruler.pack(fill=tk.BOTH, expand=True)
        self.ruler.bind("<Configure>", lambda e: self.draw_ruler())

        # 音分偏差
        cents_box = ttk.LabelFrame(left, padding=(4, 2))
        self._reg(cents_box, "cents_title")
        cents_box.grid(row=3, column=0, sticky="nsew", pady=(0, 4))
        self.cents_canvas = tk.Canvas(cents_box, height=78, bg="white", highlightthickness=1,
                                      highlightbackground="#bbb")
        self.cents_canvas.pack(fill=tk.BOTH, expand=True)
        self.cents_canvas.bind("<Configure>", lambda e: self.draw_cents())

        # 频谱
        spec_box = ttk.LabelFrame(left, padding=(4, 2))
        self._reg(spec_box, "spec_title")
        spec_box.grid(row=4, column=0, sticky="nsew")
        self.spec = tk.Canvas(spec_box, height=230, bg="white", highlightthickness=1,
                              highlightbackground="#bbb")
        self.spec.pack(fill=tk.BOTH, expand=True)
        self.spec.bind("<Configure>", lambda e: self._rebuild_spec_bins())

        # 频率表
        self._reg(ttk.Label(right), "all_keys").pack(anchor="w")
        lst_frame = ttk.Frame(right)
        lst_frame.pack(fill=tk.BOTH, expand=True)
        self.listbox = tk.Listbox(lst_frame, font=("Consolas", 10), activestyle="none")
        sb = ttk.Scrollbar(lst_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_list_select)

        self.refresh_devices()      # 枚举麦克风设备（放在最后，频谱画布已创建）

    def _first_draw(self):
        self.draw_keyboard()
        self.draw_ruler()
        self.draw_cents()
        self._rebuild_spec_bins()
        self.select_midi(self.sel_midi.get(), play=False)

    # ---------- 频率表 ----------
    def _fill_list(self):
        self.listbox.delete(0, tk.END)
        a4 = self.a4.get()
        for m in range(MIDI_LOW, MIDI_HIGH + 1):
            name, sol = note_name(m)
            f = midi_to_freq(m, a4)
            tag = self.T("black") if (m % 12) in BLACK_PC else self.T("white")
            self.listbox.insert(tk.END, "%-4s %-5s %8.2f Hz  %s" % (name, sol, f, tag))
        self.listbox.selection_clear(0, tk.END)

    def on_list_select(self, event):
        sel = self.listbox.curselection()
        if not sel:
            return
        m = MIDI_LOW + sel[0]
        self.select_midi(m, play=True)

    def on_a4_changed(self):
        try:
            v = float(self.a4.get())
        except Exception:
            return
        if not (400 <= v <= 460):
            return
        self._fill_list()
        self.hist.clear()
        self.detected = None
        self.draw_keyboard()
        self.draw_ruler()
        idx = self.sel_midi.get() - MIDI_LOW
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(idx)
        self.listbox.see(idx)

    # ---------- 选中 / 播放 ----------
    def select_midi(self, midi, play=True):
        if not (MIDI_LOW <= midi <= MIDI_HIGH):
            return
        self.sel_midi.set(midi)
        name, sol = note_name(midi)
        f = midi_to_freq(midi, self.a4.get())
        self.status.set(self.T("selected_fmt") % (name, sol, f))
        idx = midi - MIDI_LOW
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(idx)
        self.listbox.see(idx)
        self.custom_freq.set("%.2f" % f)
        self.draw_keyboard()
        self.draw_ruler()
        if play:
            self.play_freq(f)

    def play_freq(self, freq, dur=None):
        if freq is None or freq <= 0:
            return
        dur = self.dur.get() if dur is None else dur
        try:
            y = make_tone(freq, dur, self.wave_key(), self.vol.get(), self.sr_out)
            sd.stop()
            sd.play(y, self.sr_out, blocking=False)
        except Exception as e:
            messagebox.showerror(self.T("err_play"), str(e))

    def play_buffer(self, data):
        try:
            sd.stop()
            sd.play(data, self.sr_out, blocking=False)
        except Exception as e:
            messagebox.showerror(self.T("err_play"), str(e))

    def stop_all(self):
        try:
            sd.stop()
        except Exception:
            pass

    def play_custom(self):
        try:
            f = float(self.custom_freq.get())
        except Exception:
            messagebox.showinfo(self.T("err_title"), self.T("msg_number"))
            return
        if f <= 0 or f > 20000:
            messagebox.showinfo(self.T("err_title"), self.T("msg_range"))
            return
        self.play_freq(f)
        m = freq_to_midi(f, self.a4.get())
        nearest = int(round(m))
        if MIDI_LOW <= nearest <= MIDI_HIGH:
            self.select_midi(nearest, play=False)

    # ---------- 演示 ----------
    def demo_scale(self):
        # C4 D4 E4 F4 G4 A4 B4 C5
        notes = [60, 62, 64, 65, 67, 69, 71, 72]
        a4 = self.a4.get()
        for i, m in enumerate(notes):
            f = midi_to_freq(m, a4)
            self.root.after(int(i * 450),
                            lambda ff=f, mm=m: (self.select_midi(mm, play=False), self.play_freq(ff, 0.45)))

    def demo_chord(self):
        a4 = self.a4.get()
        freqs = [midi_to_freq(m, a4) for m in (60, 64, 67)]     # C4 E4 G4
        dur = max(0.8, self.dur.get())
        parts = [make_tone(f, dur, self.wave_key(), self.vol.get(), self.sr_out)
                 for f in freqs]
        y = np.mean(np.stack(parts), axis=0)
        self.play_buffer(np.asarray(y, dtype=np.float32))

    def demo_octave(self):
        a4 = self.a4.get()
        seq = [midi_to_freq(m, a4) for m in (60, 72, 60)]
        for i, f in enumerate(seq):
            self.root.after(int(i * 600), lambda ff=f: self.play_freq(ff, 0.5))

    # ---------- 键盘绘制与交互 ----------
    def _layout_keys(self):
        w = self.kb.winfo_width()
        h = self.kb.winfo_height()
        if w < 20 or h < 20:
            return False
        ww = w / 52.0            # 88 键里有 52 个白键
        bw = ww * 0.62
        bh = h * 0.62
        keys, wi = [], 0
        for m in range(MIDI_LOW, MIDI_HIGH + 1):
            black = (m % 12) in BLACK_PC
            if black:
                keys.append({"midi": m, "black": True,
                             "x": wi * ww - bw / 2.0, "w": bw, "h": bh})
            else:
                keys.append({"midi": m, "black": False,
                             "x": wi * ww, "w": ww, "h": h})
                wi += 1
        self.keys = keys
        self.ww, self.bw, self.bh = ww, bw, bh
        return True

    def key_fill(self, k):
        m = k["midi"]
        sel = self.sel_midi.get()
        det_m = self.detected["midi"] if self.detected else None
        if m == sel:
            return "#ff9f43" if not k["black"] else "#e07b1f"
        if det_m is not None and m == det_m:
            return "#7bd389" if not k["black"] else "#3fa34d"
        if self.hover_midi == m:
            return "#d6e4ff" if not k["black"] else "#4a5a7a"
        return "#ffffff" if not k["black"] else "#222222"

    def draw_keyboard(self):
        if not self._layout_keys():
            return
        c = self.kb
        c.delete("all")
        h = c.winfo_height()
        a4 = self.a4.get()

        for k in self.keys:
            if k["black"]:
                continue
            c.create_rectangle(k["x"], 0, k["x"] + k["w"], k["h"],
                               fill=self.key_fill(k), outline="#666", width=1)
        for k in self.keys:
            if not k["black"]:
                continue
            c.create_rectangle(k["x"], 0, k["x"] + k["w"], k["h"],
                               fill=self.key_fill(k), outline="#000", width=1)

        # 白键底部标音名（C 键额外标八度）
        for k in self.keys:
            if k["black"]:
                continue
            m = k["midi"]
            pc = m % 12
            label = "C%d" % (m // 12 - 1) if pc == 0 else NOTE_NAMES[pc]
            c.create_text(k["x"] + k["w"] / 2, h - 10, text=label,
                          font=("Consolas", 8), fill="#333")

        # 选中键上方标出频率
        sel = self.sel_midi.get()
        for k in self.keys:
            if k["midi"] == sel:
                f = midi_to_freq(sel, a4)
                c.create_text(k["x"] + k["w"] / 2, k["h"] * 0.42, text="%.1f" % f,
                              font=("Consolas", 8, "bold"), fill="#8a4b00")
                break

    def key_at(self, x, y):
        for k in reversed(self.keys):          # 黑键在上层，优先命中
            if k["black"] and k["x"] <= x < k["x"] + k["w"] and y < k["h"]:
                return k
        for k in self.keys:
            if not k["black"] and k["x"] <= x < k["x"] + k["w"]:
                return k
        return None

    def on_kb_motion(self, event):
        k = self.key_at(event.x, event.y)
        midi = k["midi"] if k else None
        if midi != self.hover_midi:
            self.hover_midi = midi
            self.draw_keyboard()
            if k is not None:
                name, sol = note_name(midi)
                f = midi_to_freq(midi, self.a4.get())
                self.status.set(self.T("hover_fmt") % (name, sol, f))
            else:
                self.status.set(self.T("tip_hover"))
            self.kb.configure(cursor="hand2" if k else "")

    def on_kb_leave(self, event):
        if self.hover_midi is not None:
            self.hover_midi = None
            self.draw_keyboard()

    def on_kb_press(self, event):
        k = self.key_at(event.x, event.y)
        if k is None:
            return
        d = 3.0 if self.sustain.get() else None
        self.select_midi(k["midi"], play=False)
        self.play_freq(midi_to_freq(k["midi"], self.a4.get()), dur=d)

    def on_kb_release(self, event):
        if self.sustain.get():
            self.stop_all()

    # ---------- 麦克风 ----------
    def toggle_mic(self):
        if self.mic_on:
            self.stop_mic()
        else:
            self.start_mic()

    def start_mic(self):
        self.q = queue.Queue()
        self.mic_buf = np.zeros(self.NFFT, dtype=np.float32)
        try:
            self.stream = sd.InputStream(device=self.mic_dev_index, channels=1,
                                         samplerate=self.sr_in, blocksize=1024,
                                         callback=self._mic_cb)
            self.stream.start()
        except Exception as e:
            # 该设备可能不支持上面查到的采样率，退回设备自己的默认值再试
            try:
                self.stream = sd.InputStream(device=self.mic_dev_index, channels=1,
                                             blocksize=1024, callback=self._mic_cb)
                self.stream.start()
                self.sr_in = int(self.stream.samplerate)
                self._rebuild_spec_bins()
            except Exception as e2:
                messagebox.showerror(self.T("err_mic"),
                                     self.T("err_mic_msg") % (self.dev_desc, e, e2))
                self.stream = None
                return
        self.mic_on = True
        self.mic_btn.configure(text=self.T("stop_listen"))
        self.mic_status.set(self.T("listening_fmt") % (self.dev_desc, self.sr_in))
        self.poll_mic()

    def stop_mic(self):
        self.mic_on = False
        try:
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass
        self.stream = None
        self.mic_btn.configure(text=self.T("start"))
        self.mic_status.set(self.T("stopped_fmt") % self.dev_desc)
        self.detected = None
        self.last_det_midi = None
        self.hist.clear()
        self.det_var.set(self.T("dash") + " Hz")
        self.note_var.set(self.T("dash"))
        self.cents_var.set(self.T("dash"))
        self.draw_keyboard()
        self.draw_ruler()
        self.draw_cents()

    def _mic_cb(self, indata, frames, time_info, status):
        self.q.put(indata[:, 0].copy())

    def poll_mic(self):
        if not self.mic_on:
            return
        changed = False
        while True:
            try:
                d = self.q.get_nowait()
            except queue.Empty:
                break
            n = len(d)
            if n >= self.NFFT:
                self.mic_buf[:] = d[-self.NFFT:]
            else:
                self.mic_buf[:-n] = self.mic_buf[n:]
                self.mic_buf[-n:] = d
            changed = True
        if changed:
            self.analyze()
        self.root.after(60, self.poll_mic)

    def analyze(self):
        x = self.mic_buf.astype(np.float64)
        rms = float(np.sqrt(np.dot(x, x) / len(x)))
        self.level = rms
        self.mic_status.set(self.T("level_fmt")
                            % (self.dev_desc, self.sr_in, rms,
                               self.T("snd_yes") if rms >= 0.0035 else self.T("snd_no")))
        if rms < 0.0035:                        # 静音门限
            self.hist.clear()
            self.set_detected(None)
            return

        N = len(x)
        w = np.hanning(N)
        X = np.abs(np.fft.rfft(x * w))
        freqs = np.fft.rfftfreq(N, 1.0 / self.sr_in)

        # YIN 自相关法测基频（对纯音和有泛音的人声都稳定）
        f = yin_pitch(x, self.sr_in, fmin=60.0, fmax=2000.0)
        if f is None or not (60.0 <= f <= 2000.0):
            # 有声音但周期性不强（噪声、说话声）：频谱照常显示，只是不给音高
            self.hist.clear()
            self.set_detected({"f": None, "midi": None, "cents": 0.0,
                               "X": X, "freqs": freqs, "rms": rms})
            return

        self.hist.append(f)
        f = float(np.median(self.hist))          # 中值平滑，读数更稳

        mi = freq_to_midi(f, self.a4.get())
        nearest = int(round(mi))
        cents = (mi - nearest) * 100.0
        self.set_detected({"f": f, "midi": nearest, "cents": cents, "X": X, "freqs": freqs, "rms": rms})

    def set_detected(self, det):
        self.detected = det
        if det is None:
            self.det_var.set(self.T("dash") + " Hz")
            self.note_var.set(self.T("dash"))
            self.cents_var.set(self.T("dash"))
            if self.last_det_midi is not None:
                self.last_det_midi = None
                self.draw_keyboard()
            self.draw_ruler()
            self.draw_cents()
            self.draw_spectrum()
            return

        if det["f"] is None:                     # 有声音但没听出稳定音高
            self.det_var.set(self.T("dash") + " Hz")
            self.note_var.set(self.T("unsteady_note"))
            self.cents_var.set(self.T("hum_steady"))
            if self.last_det_midi is not None:
                self.last_det_midi = None
                self.draw_keyboard()
            self.draw_ruler()
            self.draw_cents()
            self.draw_spectrum()
            return

        name, sol = note_name(det["midi"])
        self.det_var.set("%.1f Hz" % det["f"])
        self.note_var.set("%s（%s）  %.2f Hz" % (name, sol, midi_to_freq(det["midi"], self.a4.get()))
                          if self.lang == "zh"
                          else "%s (%s)  %.2f Hz" % (name, sol, midi_to_freq(det["midi"], self.a4.get())))
        c = det["cents"]
        if abs(c) < 8:
            tip = self.T("in_tune")
        elif c > 0:
            tip = self.T("sharp_fmt") % c
        else:
            tip = self.T("flat_fmt") % (-c)
        self.cents_var.set(tip)

        if det["midi"] != self.last_det_midi:
            self.last_det_midi = det["midi"]
            self.draw_keyboard()
        self.draw_ruler()
        self.draw_cents()
        self.draw_spectrum()

    # ---------- 音高尺 ----------
    def draw_ruler(self):
        c = self.ruler
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20 or h < 20:
            return
        a4 = self.a4.get()
        f0 = midi_to_freq(MIDI_LOW, a4) * 0.90
        f1 = midi_to_freq(MIDI_HIGH, a4) * 1.10
        lg0, lg1 = math.log10(f0), math.log10(f1)

        def px(f):
            return (math.log10(max(f, f0)) - lg0) / (lg1 - lg0) * w

        base = h * 0.62
        c.create_line(0, base, w, base, fill="#444", width=2)

        for m in range(MIDI_LOW, MIDI_HIGH + 1):
            f = midi_to_freq(m, a4)
            x = px(f)
            black = (m % 12) in BLACK_PC
            top = base - (h * 0.16 if black else h * 0.30)
            c.create_line(x, base, x, top, fill=("#888" if black else "#333"), width=1)
            if m % 12 == 0:                       # C 键标注
                c.create_text(x, top - 8, text="C%d" % (m // 12 - 1),
                              font=("Consolas", 8, "bold"), fill="#333")

        c.create_text(4, h - 6, text=self.T("low"), anchor="w", font=("Microsoft YaHei", 8), fill="#666")
        c.create_text(w - 4, h - 6, text=self.T("high"), anchor="e", font=("Microsoft YaHei", 8), fill="#666")

        # 选中的键（蓝色三角）
        sel = self.sel_midi.get()
        xs = px(midi_to_freq(sel, a4))
        c.create_polygon(xs - 6, base + 4, xs + 6, base + 4, xs, base + 16,
                         fill="#1f6feb", outline="#1f6feb")
        nm, _ = note_name(sel)
        c.create_text(xs, base + 28, text=nm, font=("Consolas", 9, "bold"), fill="#1f6feb")

        # 哼唱检测到的音（红线）
        if self.detected and self.detected["f"]:
            f = self.detected["f"]
            xd = px(f)
            c.create_line(xd, 4, xd, base, fill="#e74c3c", width=2)
            c.create_text(xd, 10, text="%.0f Hz" % f, font=("Consolas", 9, "bold"),
                          fill="#e74c3c", anchor="n")
            dm = self.detected["midi"]
            if MIDI_LOW <= dm <= MIDI_HIGH:
                c.create_line(px(midi_to_freq(dm, a4)), base - h * 0.34,
                              px(midi_to_freq(dm, a4)), base, fill="#e74c3c", width=1, dash=(3, 2))

    # ---------- 音分偏差 ----------
    def draw_cents(self):
        c = self.cents_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20 or h < 20:
            return
        top, bot = h * 0.30, h * 0.78
        mid = w / 2.0
        half = w * 0.42

        c.create_rectangle(mid - half, top, mid + half, bot, fill="#f7f7f7", outline="#ccc")
        for v in (-50, -25, 0, 25, 50):
            x = mid + v / 50.0 * half
            c.create_line(x, top, x, bot, fill=("#2e7d32" if v == 0 else "#ddd"),
                          width=2 if v == 0 else 1)
            c.create_text(x, bot + 12, text=("%+d" % v), font=("Consolas", 8), fill="#666")
        c.create_text(mid - half - 4, (top + bot) / 2, text=self.T("lo_short"), anchor="e",
                      font=("Microsoft YaHei", 9), fill="#666")
        c.create_text(mid + half + 4, (top + bot) / 2, text=self.T("hi_short"), anchor="w",
                      font=("Microsoft YaHei", 9), fill="#666")

        if self.detected and self.detected["f"]:
            cents = max(-50.0, min(50.0, self.detected["cents"]))
            x = mid + cents / 50.0 * half
            color = "#2e7d32" if abs(cents) < 8 else "#e67e22"
            c.create_line(x, top - 6, x, bot + 4, fill=color, width=3)
            c.create_polygon(x - 5, top - 8, x + 5, top - 8, x, top + 2, fill=color)
            c.create_text(x, h - 6, text="%+.0f" % cents, font=("Consolas", 9, "bold"), fill=color)

    # ---------- 频谱 ----------
    def _rebuild_spec_bins(self):
        w = self.spec.winfo_width()
        if w < 20:
            return
        self.spec_cols = int(w)
        freqs = np.fft.rfftfreq(self.NFFT, 1.0 / self.sr_in)
        edges = np.logspace(math.log10(40.0), math.log10(5000.0), self.spec_cols + 1)
        starts = np.searchsorted(freqs, edges[:-1])
        ends = np.searchsorted(freqs, edges[1:])
        ends = np.maximum(ends, starts + 1)
        ends = np.minimum(ends, len(freqs))
        self.spec_bins = list(zip(starts.tolist(), ends.tolist()))
        self.spec_disp = None
        self.draw_spectrum()

    def draw_spectrum(self):
        c = self.spec
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20 or h < 20 or self.spec_bins is None:
            return
        if int(w) != self.spec_cols:
            self._rebuild_spec_bins()
            return

        f0, f1 = 40.0, 5000.0
        lg0, lg1 = math.log10(f0), math.log10(f1)

        def px(f):
            return (math.log10(max(min(f, f1), f0)) - lg0) / (lg1 - lg0) * w

        # 频率网格（C1 ~ C8）
        a4 = self.a4.get()
        for m in range(24, 109, 12):
            f = midi_to_freq(m, a4)
            x = px(f)
            c.create_line(x, 0, x, h - 14, fill="#eee")
            c.create_text(x, h - 4, text="C%d" % (m // 12 - 1), font=("Consolas", 7), fill="#999")
        c.create_line(0, h - 16, w, h - 16, fill="#bbb")

        det = self.detected
        if det is None:
            c.create_text(w / 2, h / 2, text=self.T("no_sound"), fill="#aaa",
                          font=("Microsoft YaHei", 11))
            return

        X, freqs = det["X"], det["freqs"]
        ref = self.NFFT / 4.0
        vals = np.empty(self.spec_cols, dtype=np.float64)
        for j, (s, e) in enumerate(self.spec_bins):
            seg = X[s:e]
            vals[j] = float(seg.max()) if seg.size else 0.0
        db = 20.0 * np.log10(vals / ref + 1e-12)
        db = np.clip(db, -90.0, 0.0)

        if self.spec_disp is None or len(self.spec_disp) != len(db):
            self.spec_disp = db
        else:
            self.spec_disp = 0.55 * self.spec_disp + 0.45 * db      # 视觉平滑
        db = self.spec_disp

        def py(v):
            return h - 16 - (v + 90.0) / 90.0 * (h - 24)

        pts = [(j + 0.5, py(v)) for j, v in enumerate(db)]
        c.create_polygon([(0, h - 16)] + pts + [(w - 1, h - 16)],
                         fill="#cfe3f7", outline="")
        c.create_line(pts, fill="#2d7dd2", width=1, smooth=False)

        # 基频与泛音
        f = det["f"]
        if f is None:
            c.create_text(w / 2, 24, text=self.T("unsteady"), fill="#e67e22",
                          font=("Microsoft YaHei", 10))
            return
        for k, col, dash in ((1, "#e74c3c", None), (2, "#f39c12", (4, 3)), (3, "#f39c12", (4, 3))):
            ff = f * k
            if ff >= f1:
                continue
            x = px(ff)
            c.create_line(x, 0, x, h - 16, fill=col, width=(2 if k == 1 else 1), dash=dash)
            if k > 1:
                c.create_text(x + 3, 8, text="%d×" % k, anchor="nw",
                              font=("Consolas", 8), fill="#f39c12")
        c.create_text(px(f) + 4, h - 26, text=self.T("f0_fmt") % f, anchor="sw",
                      font=("Consolas", 9, "bold"), fill="#e74c3c")

    # ---------- 关闭 ----------
    def on_close(self):
        self.mic_on = False
        try:
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass
        try:
            sd.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Sound Explorer / 音律探索器")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh",
                    help="界面语言 UI language: zh=中文, en=English (默认 zh)")
    args = ap.parse_args()

    root = tk.Tk()
    SoundApp(root, lang=args.lang)
    root.mainloop()


if __name__ == "__main__":
    main()
