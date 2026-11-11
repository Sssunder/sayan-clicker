"""Color tokens and typography definitions for Sayan Clicker."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePalette:
    key: str
    label: str
    bg_page: str
    bg_header: str
    bg_card: str
    bg_stage: str
    stage_halo: str
    stage_ring: str
    bg_pill: str
    bg_pill_hover: str
    bg_control: str
    bg_control_hover: str
    accent: str
    accent_hover: str
    accent_text: str
    sage: str
    sage_light: str
    gold: str
    gold_light: str
    text_heading: str
    text_body: str
    text_muted: str
    border: str
    bubble_bg: str
    bubble_border: str
    shadow: str


THEMES: dict[str, ThemePalette] = {
    "cozy": ThemePalette(
        key="cozy",
        label="Уютный Саян",
        bg_page="#F5F5F7",
        bg_header="#FFFFFF",
        bg_card="#FFFFFF",
        bg_stage="#F5F5F7",
        stage_halo="#FFE7D8",
        stage_ring="#F2D9C2",
        bg_pill="#FFF0EA",
        bg_pill_hover="#FFE1D3",
        bg_control="#EDEDF0",
        bg_control_hover="#E2E2E7",
        accent="#FF7A50",
        accent_hover="#E8663C",
        accent_text="#FFFFFF",
        sage="#487A60",
        sage_light="#E6F2EB",
        gold="#D97706",
        gold_light="#FEF3C7",
        text_heading="#1D1D1F",
        text_body="#3A3A3C",
        text_muted="#86868B",
        border="#E5E5EA",
        bubble_bg="#FFFFFF",
        bubble_border="#E5E5EA",
        shadow="#D9D9DE",
    ),
    "cyber": ThemePalette(
        key="cyber",
        label="Ночной Кибер-Кот",
        bg_page="#0B0B0F",
        bg_header="#1C1C1E",
        bg_card="#1C1C1E",
        bg_stage="#141419",
        stage_halo="#16324A",
        stage_ring="#1E4D6B",
        bg_pill="#1A2B3C",
        bg_pill_hover="#223A52",
        bg_control="#2C2C2E",
        bg_control_hover="#3A3A3C",
        accent="#06B6D4",
        accent_hover="#22D3EE",
        accent_text="#0B0F19",
        sage="#34D399",
        sage_light="#133A2E",
        gold="#FBBF24",
        gold_light="#3B2F13",
        text_heading="#F5F5F7",
        text_body="#D1D1D6",
        text_muted="#98989D",
        border="#38383A",
        bubble_bg="#1C1C1E",
        bubble_border="#06B6D4",
        shadow="#000000",
    ),
}


def get_theme(key: str) -> ThemePalette:
    """Return theme palette by key with safe fallback to cozy."""
    return THEMES.get(key, THEMES["cozy"])
