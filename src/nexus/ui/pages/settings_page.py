"""Settings page — category list + scrollable settings sections (spec §27).

Categories: General · Appearance · Automation · Champion Selection ·
Notifications · Hotkeys · Accounts · Advanced. Every control binds to a real
field on core.preferences.settings.Settings and persists immediately via
SettingsStore.save(). Categories without backing settings show an honest
"not available yet" note instead of dead toggles.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QScrollArea, QVBoxLayout, QWidget,
)

from ...core.automation.config import BanMode
from ..components.base import NexusCard, NexusHeader
from ..theme import tokens as T


def _row(label_text: str, widget: QWidget) -> QHBoxLayout:
    h = QHBoxLayout(); h.setSpacing(T.SP_2)
    lab = QLabel(label_text); lab.setObjectName("FieldLabel")
    lab.setWordWrap(True)
    h.addWidget(lab, 1); h.addWidget(widget)
    return h


class SettingsPage(QWidget):
    CATEGORIES = ("General", "Appearance", "Automation", "Champion Selection",
                  "Notifications", "Hotkeys", "Accounts", "Advanced")

    def __init__(self, controller, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.settings = controller.settings

        root = QVBoxLayout(self)
        root.setContentsMargins(T.SP_4, T.SP_4, T.SP_4, T.SP_4)
        root.setSpacing(T.SP_3)
        root.addWidget(NexusHeader("Settings",
                                   "Preferences are saved immediately"))

        body = QHBoxLayout(); body.setSpacing(T.SP_4)
        self.nav = QListWidget(); self.nav.setObjectName("SettingsNav")
        self.nav.setFixedWidth(180)
        self.nav.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.nav.setAccessibleName("Settings categories")
        for name in self.CATEGORIES:
            self.nav.addItem(QListWidgetItem(name))
        self.nav.currentRowChanged.connect(self._show_category)
        body.addWidget(self.nav)

        self.pages_host = QVBoxLayout(); self.pages_host.setSpacing(T.SP_3)
        host = QWidget(); host.setLayout(self.pages_host)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(host)
        body.addWidget(scroll, 1)
        root.addLayout(body, 1)

        self._pages: dict[str, QWidget] = {}
        self._build_pages()
        self.nav.setCurrentRow(self.CATEGORIES.index("Automation"))

    # ------------------------------------------------------------------ pages
    def _bind_bool(self, section_obj, field_name: str,
                   after: Optional[Callable[[bool], None]] = None) -> QCheckBox:
        """Checkbox bound to a persisted bool setting; saves on toggle."""
        cb = QCheckBox()
        try:
            cb.setChecked(bool(getattr(section_obj, field_name)))
        except AttributeError:
            pass

        def setter(v: bool) -> None:
            try:
                setattr(section_obj, field_name, bool(v))
                self.controller.settings_store.save()
            except Exception:
                pass
            if after:
                after(bool(v))

        cb.toggled.connect(setter)
        return cb

    def _card_note(self, text: str) -> NexusCard:
        c = NexusCard(); lab = QLabel(text); lab.setWordWrap(True)
        lab.setObjectName("Secondary"); c.body.addWidget(lab); return c

    def _build_pages(self) -> None:
        s = self.settings

        # General -----------------------------------------------------------
        g = NexusCard(); g.body.addWidget(QLabel("GENERAL"))
        launch = self._bind_bool(s.general, "launch_on_startup")
        g.body.addLayout(_row("Start Nexus with Windows", launch))
        compact = self._bind_bool(s.general, "start_in_compact_mode")
        g.body.addLayout(_row("Start in compact mode", compact))
        motion = self._bind_bool(s.general, "reduced_motion")
        g.body.addLayout(_row("Reduced motion", motion))
        lang = QComboBox(); lang.addItems(["en"])
        lang.setCurrentText(s.general.language)
        lang.currentTextChanged.connect(
            lambda v: (setattr(s.general, "language", v),
                       self.controller.settings_store.save()))
        g.body.addLayout(_row("Language", lang))
        self._pages["General"] = g

        # Appearance ----------------------------------------------------------
        a = NexusCard(); a.body.addWidget(QLabel("APPEARANCE"))
        theme_box = QComboBox(); theme_box.addItems(["dark", "light"])
        theme_box.setCurrentText(s.appearance.theme)
        theme_box.currentTextChanged.connect(self._set_theme)
        a.body.addLayout(_row("Theme", theme_box))
        accent = QComboBox()
        accent.addItems(["hextech-gold", "hextech-blue", "emerald", "violet"])
        accent.setCurrentText(s.appearance.accent)
        accent.currentTextChanged.connect(
            lambda v: (setattr(s.appearance, "accent", v),
                       self.controller.settings_store.save()))
        a.body.addLayout(_row("Accent colour", accent))
        size = QComboBox(); size.addItems(["small", "medium", "large"])
        size.setCurrentText(s.appearance.compact_size)
        size.currentTextChanged.connect(
            lambda v: (setattr(s.appearance, "compact_size", v),
                       self.controller.settings_store.save()))
        a.body.addLayout(_row("Compact overlay size", size))
        self._pages["Appearance"] = a

        # Automation -----------------------------------------------------------
        au = NexusCard(); au.body.addWidget(QLabel("AUTOMATION"))
        master = QCheckBox("Master automation switch")
        master.setChecked(s.automation.master_enabled)
        master.toggled.connect(self.controller.set_automation_enabled)
        au.body.addWidget(master)
        accept = QCheckBox("Auto-accept ready checks")
        accept.setChecked(s.automation.auto_accept_ready)
        accept.toggled.connect(
            lambda v: self.controller.update_config(auto_accept_ready=v))
        au.body.addWidget(accept)
        pick = QCheckBox("Auto-pick when recommended")
        pick.setChecked(s.automation.auto_pick)
        pick.toggled.connect(
            lambda v: self.controller.update_config(auto_pick=v))
        au.body.addWidget(pick)
        ban_mode = QComboBox()
        ban_mode.addItems([m.value for m in BanMode])
        ban_mode.setCurrentText(s.automation.ban_mode.value)
        ban_mode.currentTextChanged.connect(
            lambda v: self.controller.update_config(ban_mode=BanMode(v)))
        au.body.addLayout(_row("Ban mode", ban_mode))
        note = QLabel("Consequential actions require confirmed authoritative "
                      "state and post-action verification.")
        note.setObjectName("Secondary"); note.setWordWrap(True)
        au.body.addWidget(note)
        self._pages["Automation"] = au

        # Champion Selection -----------------------------------------------------
        cs = NexusCard(); cs.body.addWidget(QLabel("CHAMPION SELECTION"))
        toast_rec = self._bind_bool(s.notifications, "toast_recommendation")
        cs.body.addLayout(_row("Toast when a recommendation is made", toast_rec))
        info = QLabel("Rank champions on the Profile page. Auto-pick and ban "
                      "behaviour live under Automation.")
        info.setObjectName("Secondary"); info.setWordWrap(True)
        cs.body.addWidget(info)
        self._pages["Champion Selection"] = cs

        # Notifications -----------------------------------------------------------
        n = NexusCard(); n.body.addWidget(QLabel("NOTIFICATIONS"))
        errors_cb = self._bind_bool(s.notifications, "toast_errors")
        n.body.addLayout(_row("Show toasts for errors", errors_cb))
        sound_cb = self._bind_bool(s.notifications, "sound_kill_switch")
        n.body.addLayout(_row("Sound kill-switch (mute all alerts)", sound_cb))
        bus_toggle = QCheckBox("Enable in-app toasts entirely")
        bus_toggle.setChecked(self.controller.notifications.enabled)
        bus_toggle.toggled.connect(
            lambda v: setattr(self.controller.notifications, "enabled", bool(v)))
        n.body.addWidget(bus_toggle)
        self._pages["Notifications"] = n

        # Hotkeys -------------------------------------------------------------------
        hk = NexusCard(); hk.body.addWidget(QLabel("HOTKEYS"))
        for label, field_name in (("Emergency stop", "emergency_stop"),
                                  ("Toggle compact overlay", "toggle_compact"),
                                  ("Accept queue / ready check", "accept_queue"),
                                  ("Focus search", "focus_search")):
            lab = QLabel(str(getattr(s.hotkeys, field_name, "")))
            lab.setObjectName("Headline")
            row = QLabel(label); row.setObjectName("Secondary")
            h = QHBoxLayout(); h.setSpacing(T.SP_2)
            h.addWidget(row, 1); h.addWidget(lab)
            hk.body.addLayout(h)
        hint = QLabel("Hotkey remapping is not available yet; these are the "
                      "built-in bindings.")
        hint.setObjectName("Secondary"); hint.setWordWrap(True)
        hk.body.addWidget(hint)
        self._pages["Hotkeys"] = hk

        # Accounts --------------------------------------------------------------------
        self._pages["Accounts"] = self._card_note(
            "Account switching is not available yet.\n"
            "Nexus follows the account signed in to the League client.")

        # Advanced ----------------------------------------------------------------------
        adv = NexusCard(); adv.body.addWidget(QLabel("ADVANCED"))
        dev_cb = self._bind_bool(s.developer, "developer_mode")
        adv.body.addLayout(_row("Developer mode (diagnostics page)", dev_cb))
        log_cb = self._bind_bool(s.developer, "log_raw_events")
        adv.body.addLayout(_row("Log raw LCU events", log_cb))
        sim_state = QLabel(
            "Simulation mode: " + ("ON" if s.developer.simulation_mode else "OFF")
            + " (use --simulate at launch)")
        sim_state.setObjectName("Secondary")
        adv.body.addWidget(sim_state)
        self._pages["Advanced"] = adv

        for w in self._pages.values():
            self.pages_host.addWidget(w)
        self.pages_host.addStretch(1)

    # ------------------------------------------------------------------ slots
    def _show_category(self, row: int) -> None:
        if 0 <= row < len(self.CATEGORIES):
            name = self.CATEGORIES[row]
            for cat, w in self._pages.items():
                w.setVisible(cat == name)

    def _set_theme(self, theme: str) -> None:
        try:
            from ..theme.qss import build_qss
            self.window().setStyleSheet(build_qss(theme))
            self.settings.appearance.theme = theme
            self.controller.settings_store.save()
        except Exception:
            pass
