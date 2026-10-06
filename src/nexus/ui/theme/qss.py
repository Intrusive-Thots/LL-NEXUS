"""Compile design tokens into a global QSS stylesheet + Qt palette.

The UI applies `build_stylesheet(theme)` once at startup and on theme change.
Components reference object names (e.g. `QFrame#NexusCard`) instead of inline
colours, keeping the visual vocabulary centralised.
"""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from .tokens import (
    BORDER_W, CONTROL_H_LG, CONTROL_H_MD, CONTROL_H_SM, PALETTE_DARK,
    PALETTE_LIGHT, RADIUS_LG, RADIUS_MD, RADIUS_PILL, RADIUS_SM, TYPOGRAPHY,
    Palette, font_stack,
)


def palette_for(theme: str = "dark") -> Palette:
    return PALETTE_LIGHT if theme == "light" else PALETTE_DARK


def apply_qt_palette(app: QApplication, p: Palette) -> None:
    pal = app.palette()
    pal.setColor(QPalette.ColorRole.Window, QColor(p.bg_root))
    pal.setColor(QPalette.ColorRole.Base, QColor(p.bg_input))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(p.bg_surface))
    pal.setColor(QPalette.ColorRole.Text, QColor(p.text_primary))
    pal.setColor(QPalette.ColorRole.Button, QColor(p.bg_raised))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(p.text_primary))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(p.accent_blue))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(p.text_inverse))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(p.text_muted))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(p.bg_overlay))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(p.text_primary))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(p.text_primary))
    app.setPalette(pal)


def build_stylesheet(theme: str = "dark", ui_scale: float = 1.0) -> str:
    p = palette_for(theme)
    s = lambda v: int(round(v * ui_scale))  # noqa: E731 — token scaling helper

    return f"""
/* ---------------------------------------------------------------- base */
QWidget {{
    font-family: "{font_stack()}";
    font-size: {s(TYPOGRAPHY.size_body)}px;
    color: {p.text_primary};
    background: {p.bg_root};
}}
QMainWindow, QDialog {{ background: {p.bg_root}; }}
QToolTip {{
    background: {p.bg_overlay}; color: {p.text_primary};
    border: {s(BORDER_W)}px solid {p.border_strong}; border-radius: {s(RADIUS_SM)}px;
    padding: {s(4)}px {s(8)}px;
}}

/* ------------------------------------------------------------- nav rail */
QListWidget#NavRail {{
    background: {p.bg_surface}; border: none;
    border-right: {s(BORDER_W)}px solid {p.border_subtle}; outline: none;
}}
QListWidget#NavRail::item {{
    padding: {s(10)}px {s(16)}px; border-radius: {s(RADIUS_MD)}px;
    margin: {s(2)}px {s(8)}px; color: {p.text_secondary};
    border: {s(BORDER_W)}px solid transparent;
}}
QListWidget#NavRail::item:hover {{ color: {p.text_primary}; background: {p.bg_raised}; }}
QListWidget#NavRail::item:selected {{
    color: {p.text_primary}; background: {p.bg_raised};
    border-left: {s(3)}px solid {p.accent_gold};
}}

/* --------------------------------------------------------------- cards */
QFrame#NexusCard {{
    background: {p.bg_surface};
    border: {s(BORDER_W)}px solid {p.border_subtle};
    border-radius: {s(RADIUS_LG)}px;
}}
QFrame#NexusCard[raised="true"] {{ background: {p.bg_raised}; }}
QFrame#ChampSelectHero {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p.bg_raised}, stop:1 {p.bg_surface});
    border: {s(BORDER_W)}px solid {p.accent_gold_soft};
    border-radius: {s(RADIUS_LG)}px;
}}

QLabel#SectionTitle {{
    color: {p.text_secondary}; font-size: {s(TYPOGRAPHY.size_caption)}px;
    font-weight: {TYPOGRAPHY.weight_semibold}; letter-spacing: 1px;
}}
QLabel#Headline {{ font-size: {s(TYPOGRAPHY.size_headline)}px; font-weight: {TYPOGRAPHY.weight_bold}; }}
QLabel#Display {{ font-size: {s(TYPOGRAPHY.size_display)}px; font-weight: {TYPOGRAPHY.weight_bold}; }}
QLabel#TimerValue {{
    font-size: {s(TYPOGRAPHY.size_timer)}px; font-weight: {TYPOGRAPHY.weight_bold};
    color: {p.text_primary};
}}
QLabel#TimerValue[urgent="true"] {{ color: {p.error}; }}
QLabel#Muted {{ color: {p.text_muted}; }}
QLabel#Secondary {{ color: {p.text_secondary}; }}
QLabel#Accent {{ color: {p.accent_gold}; }}

/* -------------------------------------------------------------- buttons */
QPushButton {{
    background: {p.bg_raised}; color: {p.text_primary};
    border: {s(BORDER_W)}px solid {p.border_strong};
    border-radius: {s(RADIUS_MD)}px;
    min-height: {s(CONTROL_H_MD)}px; padding: 0 {s(16)}px;
    font-weight: {TYPOGRAPHY.weight_semibold};
}}
QPushButton:hover {{ border-color: {p.accent_blue}; background: {p.bg_surface}; }}
QPushButton:pressed {{ background: {p.bg_input}; }}
QPushButton:focus-visible {{ border: {s(2)}px solid {p.accent_blue}; }}
QPushButton:disabled {{ color: {p.disabled_fg}; background: {p.disabled_bg};
                        border-color: {p.border_subtle}; }}
QPushButton[NexusVariant="primary"] {{
    background: {p.accent_gold}; color: {p.text_inverse};
    border: none; min-height: {s(CONTROL_H_LG)}px;
}}
QPushButton[NexusVariant="primary"]:hover {{ background: #D9AC4E; }}
QPushButton[NexusVariant="primary"]:disabled {{ background: {p.disabled_bg}; color: {p.disabled_fg}; }}
QPushButton[NexusVariant="danger"] {{
    background: transparent; color: {p.danger};
    border: {s(2)}px solid {p.danger}; min-height: {s(CONTROL_H_LG)}px;
}}
QPushButton[NexusVariant="danger"]:hover {{ background: rgba(255,75,71,0.12); }}
QPushButton[NexusVariant="ghost"] {{ background: transparent; border: none; color: {p.text_secondary}; }}
QPushButton[NexusVariant="ghost"]:hover {{ color: {p.text_primary}; }}

QToolButton#NexusIconButton {{
    background: transparent; border: {s(BORDER_W)}px solid transparent;
    border-radius: {s(RADIUS_MD)}px; padding: {s(4)}px; color: {p.text_secondary};
}}
QToolButton#NexusIconButton:hover {{ background: {p.bg_raised}; color: {p.text_primary};
                                    border-color: {p.border_subtle}; }}

/* --------------------------------------------------------------- inputs */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {p.bg_input}; border: {s(BORDER_W)}px solid {p.border_strong};
    border-radius: {s(RADIUS_MD)}px; min-height: {s(CONTROL_H_MD)}px;
    padding: 0 {s(10)}px; selection-background-color: {p.accent_blue};
    selection-color: {p.text_inverse};
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {p.accent_blue}; }}
QComboBox::drop-down {{ border: none; width: {s(24)}px; }}
QAbstractItemView {{
    background: {p.bg_surface}; border: {s(BORDER_W)}px solid {p.border_strong};
    border-radius: {s(RADIUS_MD)}px; outline: none;
}}
QAbstractItemView::item {{ padding: {s(6)}px {s(10)}px; border-radius: {s(RADIUS_SM)}px; }}
QAbstractItemView::item:selected {{ background: {p.bg_raised}; color: {p.text_primary}; }}

/* ---------------------------------------------------------------- misc */
QCheckBox, QRadioButton {{ spacing: {s(8)}px; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: {s(18)}px; height: {s(18)}px;
    border: {s(BORDER_W)}px solid {p.border_strong}; border-radius: {s(RADIUS_SM)}px;
    background: {p.bg_input};
}}
QRadioButton::indicator {{ border-radius: {s(9)}px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {p.accent_blue}; border-color: {p.accent_blue};
}}
QScrollBar:vertical {{ background: transparent; width: {s(10)}px; }}
QScrollBar::handle:vertical {{ background: {p.border_strong}; border-radius: {s(5)}px;
                               min-height: {s(28)}px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: {s(10)}px; }}
QScrollBar::handle:horizontal {{ background: {p.border_strong}; border-radius: {s(5)}px;
                                 min-width: {s(28)}px; }}
QSplitter::handle {{ background: {p.divider}; }}

QStatusBar {{ background: {p.bg_surface}; border-top: {s(BORDER_W)}px solid {p.border_subtle}; }}
QStatusBar QLabel {{ background: transparent; }}

/* tabs */
QTabBar::tab {{
    background: transparent; color: {p.text_secondary};
    padding: {s(8)}px {s(16)}px; border: none;
    border-bottom: {s(2)}px solid transparent;
}}
QTabBar::tab:selected {{ color: {p.text_primary}; border-bottom-color: {p.accent_gold}; }}
QTabBar::tab:hover {{ color: {p.text_primary}; }}

/* badges & status pill */
QLabel[NexusBadge="ok"]      {{ background: rgba(61,214,140,0.15); color: {p.ok};
    border-radius: {s(RADIUS_PILL)}px; padding: {s(2)}px {s(10)}px; font-weight: {TYPOGRAPHY.weight_semibold}; }}
QLabel[NexusBadge="warn"]    {{ background: rgba(232,178,58,0.15); color: {p.warn};
    border-radius: {s(RADIUS_PILL)}px; padding: {s(2)}px {s(10)}px; font-weight: {TYPOGRAPHY.weight_semibold}; }}
QLabel[NexusBadge="error"]   {{ background: rgba(240,82,79,0.15); color: {p.error};
    border-radius: {s(RADIUS_PILL)}px; padding: {s(2)}px {s(10)}px; font-weight: {TYPOGRAPHY.weight_semibold}; }}
QLabel[NexusBadge="info"]    {{ background: rgba(10,200,185,0.12); color: {p.info};
    border-radius: {s(RADIUS_PILL)}px; padding: {s(2)}px {s(10)}px; font-weight: {TYPOGRAPHY.weight_semibold}; }}
QLabel[NexusBadge="muted"]   {{ background: {p.bg_raised}; color: {p.text_muted};
    border-radius: {s(RADIUS_PILL)}px; padding: {s(2)}px {s(10)}px; }}

/* champion tiles */
QFrame[NexusTile="champion"] {{
    background: {p.bg_raised}; border: {s(BORDER_W)}px solid {p.border_subtle};
    border-radius: {s(RADIUS_MD)}px;
}}
QFrame[NexusTile="champion"]:hover {{ border-color: {p.accent_blue}; }}
QFrame[NexusTile="champion"][selected="true"] {{ border: {s(2)}px solid {p.accent_gold}; }}
QFrame[NexusTile="champion"][dimmed="true"] {{ border-color: {p.border_subtle}; }}

/* priority rows */
QListWidget#PriorityList {{ background: {p.bg_surface}; border: {s(BORDER_W)}px solid {p.border_subtle};
                            border-radius: {s(RADIUS_MD)}px; outline: none; }}
QListWidget#PriorityList::item {{
    padding: {s(8)}px {s(10)}px; border-bottom: {s(BORDER_W)}px solid {p.divider};
}}
QListWidget#PriorityList::item:selected {{ background: {p.bg_raised};
    border-left: {s(3)}px solid {p.accent_gold}; }}

/* activity rows / timeline */
QPlainTextEdit#Timeline {{
    background: {p.bg_input}; border: {s(BORDER_W)}px solid {p.border_subtle};
    border-radius: {s(RADIUS_MD)}px;
    font-family: "Cascadia Mono", "Consolas", monospace; font-size: {s(12)}px;
    color: {p.text_secondary};
}}

/* toasts */
QFrame#NexusToast {{
    background: {p.bg_overlay}; border: {s(BORDER_W)}px solid {p.border_strong};
    border-radius: {s(RADIUS_LG)}px;
}}
QFrame#NexusToast[level="critical"] {{ border-color: {p.error}; }}
QFrame#NexusToast[level="success"] {{ border-color: {p.ok}; }}

/* modal scrim */
QFrame#ModalScrim {{ background: rgba(4,6,9,190); }}
"""
