# -*- coding: utf-8 -*-
"""
yeppi - core fuzzy logic for Yeppi food suggestion app
=============================================================
- Backend core: data loading, fuzzy engine, filters, scoring, delivery ETA,
  OSRM road-distance routing, order tracking simulation.
- This file contains data loading, fuzzy rules, scoring, routing, and order tracking logic.
- Run the UI with app_ui.py.

Run:
    pip install -r requirements.txt
    python fuzzy_logic_core.py --test
    python app_ui.py
Then open http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import sys
import time
import unicodedata
import uuid
from collections import Counter
from copy import deepcopy
from difflib import SequenceMatcher
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
import requests

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

# ============================================================
# 0) APP CONFIG
# ============================================================
APP_NAME = "yeppi"
BASE_DIR = Path(__file__).resolve().parent
DATASET_CANDIDATES = [
    # Final MVP dataset provided by the user. Keep this first so the app
    # uses the cleaned nutrition/goal columns without renaming the file.
    BASE_DIR / "data_restaurants.xlsx",
    BASE_DIR / "restaurants.xlsx",
    BASE_DIR / "DATASET APP GỢI Ý MÓN ĂN.xlsx",
    BASE_DIR / "DATASET APP GOI Y MON AN.xlsx",
]
DEFAULT_USER_LAT = 10.76126399256893
DEFAULT_USER_LNG = 106.66836872382974
DEFAULT_USER_LABEL = "UEH cơ sở B, 279 Nguyễn Tri Phương, Quận 10"
APP_TIMEZONE = "Asia/Ho_Chi_Minh"
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
OSRM_TIMEOUT = float(os.getenv("OSRM_TIMEOUT", "7"))
# x12 lets the tracking marker move visibly during demo. Set to 1 for real clock speed.
TRACKING_ACCELERATION = max(1.0, float(os.getenv("TRACKING_ACCELERATION", "12")))
TOP_N_RESULTS = 8

ORDERS: Dict[str, Dict[str, Any]] = {}
ROUTE_TABLE_CACHE: Dict[str, Dict[str, Dict[str, Any]]] = {}
ROUTE_GEOMETRY_CACHE: Dict[str, Dict[str, Any]] = {}
DATASET_CACHE: Dict[str, Any] = {"signature": None, "records": []}


def vietnam_now() -> datetime:
    """Current Vietnam time used for real opening-hour and ETA logic."""
    if ZoneInfo:
        return datetime.now(ZoneInfo(APP_TIMEZONE))
    return datetime.now()


def vietnam_now_time() -> dtime:
    return vietnam_now().time()


def vietnam_now_hhmm() -> str:
    return vietnam_now().strftime("%H:%M")


def delivery_label_for_coords(lat: float, lng: float, label: str = "") -> str:
    """Return a safe delivery label without relying on noisy reverse geocoding.

    The previous Nominatim-based label could display wrong districts, so the app
    now keeps the default UEH label for the default point and uses coordinates
    for browser GPS/manual positions. This keeps recommendations accurate while
    avoiding a fake address such as Thu Duc for a District 10 coordinate.
    """
    try:
        if haversine_km(float(lat), float(lng), DEFAULT_USER_LAT, DEFAULT_USER_LNG) <= 0.25:
            return DEFAULT_USER_LABEL
    except Exception:
        pass
    label = clean_str(label)
    if label and "thủ đức" not in label.lower() and "thu duc" not in strip_accents(label).lower():
        return label
    return f"Vị trí hiện tại ({float(lat):.5f}, {float(lng):.5f})"

# ============================================================
# 1) CONSTANTS / CATEGORY SYSTEM
# ============================================================
CATEGORIES = [
    "Noodles / Soup Meal",
    "Fast Food Meal",
    "Hotpot / BBQ / Buffet",
    "Casual Dining",
    "Healthy / Vegetarian Meal",
    "Seafood / Specialty Meal",
    "Drinks",
    "Snack / Street Food",
]

CATEGORY_LABELS = {
    "all": "Gợi ý",
    "Noodles / Soup Meal": "Bún · Phở · Mì",
    "Fast Food Meal": "Ăn nhanh",
    "Hotpot / BBQ / Buffet": "Lẩu nướng",
    "Casual Dining": "Cơm / món chính",
    "Healthy / Vegetarian Meal": "Healthy",
    "Seafood / Specialty Meal": "Hải sản",
    "Drinks": "Đồ uống",
    "Snack / Street Food": "Ăn vặt",
}

CATEGORY_ICONS = {
    "all": "✨",
    "Noodles / Soup Meal": "🍜",
    "Fast Food Meal": "🍗",
    "Hotpot / BBQ / Buffet": "🥘",
    "Casual Dining": "🍛",
    "Healthy / Vegetarian Meal": "🥗",
    "Seafood / Specialty Meal": "🦐",
    "Drinks": "🧋",
    "Snack / Street Food": "🍢",
}

CATEGORY_PHOTOS = {
    "Noodles / Soup Meal": [
        "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1552611052-33e04de081de?auto=format&fit=crop&w=900&q=80",
    ],
    "Fast Food Meal": [
        "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1626645738196-c2a7c87a8f58?auto=format&fit=crop&w=900&q=80",
    ],
    "Hotpot / BBQ / Buffet": [
        "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=900&q=80",
    ],
    "Casual Dining": [
        "https://images.unsplash.com/photo-1512058564366-18510be2db19?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=900&q=80",
    ],
    "Healthy / Vegetarian Meal": [
        "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=900&q=80",
    ],
    "Seafood / Specialty Meal": [
        "https://images.unsplash.com/photo-1559737558-2f5a35f4523b?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1559339352-11d035aa65de?auto=format&fit=crop&w=900&q=80",
    ],
    "Drinks": [
        "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1558857563-b371033873b8?auto=format&fit=crop&w=900&q=80",
    ],
    "Snack / Street Food": [
        "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?auto=format&fit=crop&w=900&q=80",
    ],
}

MENU_TEMPLATES = {
    "Noodles / Soup Meal": ["Món nước đặc biệt", "Tô thêm topping", "Trà tắc mát lạnh"],
    "Fast Food Meal": ["Combo ăn nhanh", "Món chính bán chạy", "Khoai / snack ăn kèm"],
    "Hotpot / BBQ / Buffet": ["Set lẩu nướng 2 người", "Món nướng đặc trưng", "Rau nấm ăn kèm"],
    "Casual Dining": ["Cơm phần đặc biệt", "Combo no bụng", "Canh / rau thêm"],
    "Healthy / Vegetarian Meal": ["Salad bowl", "Cơm gạo lứt", "Nước ép tươi"],
    "Seafood / Specialty Meal": ["Món đặc sản chính", "Set hải sản", "Món phụ dùng kèm"],
    "Drinks": ["Best seller size L", "Combo 2 ly", "Topping thêm"],
    "Snack / Street Food": ["Combo ăn vặt", "Món đường phố bán chạy", "Nước uống kèm"],
}

SIMILAR_CATEGORIES = {
    "Noodles / Soup Meal": ["Casual Dining", "Fast Food Meal", "Snack / Street Food"],
    "Fast Food Meal": ["Noodles / Soup Meal", "Snack / Street Food", "Casual Dining"],
    "Hotpot / BBQ / Buffet": ["Casual Dining", "Seafood / Specialty Meal"],
    "Casual Dining": ["Noodles / Soup Meal", "Fast Food Meal", "Hotpot / BBQ / Buffet"],
    "Healthy / Vegetarian Meal": ["Casual Dining", "Noodles / Soup Meal"],
    "Seafood / Specialty Meal": ["Hotpot / BBQ / Buffet", "Casual Dining"],
    "Drinks": ["Snack / Street Food", "Healthy / Vegetarian Meal"],
    "Snack / Street Food": ["Fast Food Meal", "Drinks", "Noodles / Soup Meal"],
}

COLUMN_ALIASES = {
    "id": ["Restaurant ID", "ID", "Mã quán", "Ma quan", "restaurant_id"],
    "name": ["Tên Nhà Hàng", "Ten Nha Hang", "Restaurant Name", "Tên quán", "name"],
    "coordinates": ["Tọa độ", "Toa do", "Coordinates", "LatLng", "location"],
    "lat": ["lat", "latitude", "vĩ độ", "vi do"],
    "lng": ["lng", "lon", "long", "longitude", "kinh độ", "kinh do"],
    "rating": ["Rating", "Đánh giá", "Danh gia"],
    "price": ["Giá Trung Bình / Người", "Gia Trung Binh / Nguoi", "price", "price_avg", "Giá"],
    "category": ["Category", "Meal Type", "meal_type", "Loại món", "Loai mon"],
    "calories": ["Calories Level (Low/Medium/High)", "Calories", "calories_level"],
    "healthy": ["Healthy Score (Unhealthy/ Normal / Healthy)", "Healthy Score", "Health", "healthy_score"],
    "diet_type": ["Diet Type", "Loại chế độ ăn", "Che do an", "diet_type", "Diet Preference"],
    "protein": ["Protein Level", "Protein", "Mức protein", "Muc protein", "protein_level"],
    "portion": ["Portion Size", "Khẩu phần", "Khau phan", "portion_size"],
    "cuisine": ["Cuisine (nếu có nhiều nước thì ghi nhiều nước)", "Cuisine", "Ẩm thực", "Am thuc"],
    "taste": ["Keyword Vị Giác (Ngọt/Mặn/Chua/Cay)", "Taste", "Khẩu vị", "Khau vi"],
    "opening": ["Opening Hours", "Giờ mở cửa", "Gio mo cua", "open_hours"],
    "address": ["Address", "Địa chỉ", "Dia chi", "address"],
}

BUDGET_MF = {
    "very_cheap": ("trap", [10000, 10000, 25000, 50000]),
    "cheap": ("tri", [30000, 75000, 130000]),
    "medium": ("tri", [90000, 180000, 320000]),
    "expensive": ("tri", [250000, 450000, 700000]),
    "very_expensive": ("trap", [600000, 800000, 1000000, 1000000]),
}
HUNGRY_MF = {
    "light": ("trap", [1, 1, 2.5, 4.0]),
    "hungry": ("tri", [3.0, 5.5, 8.0]),
    "starving": ("trap", [7.0, 8.5, 10, 10]),
}
TIME_MF = {
    "very_short": ("trap", [10, 10, 25, 40]),
    "short": ("tri", [30, 45, 65]),
    "medium": ("tri", [55, 75, 95]),
    "long": ("tri", [80, 100, 115]),
    "very_long": ("trap", [95, 110, 120, 120]),
}
HEALTH_MEMBERSHIP = {
    "diet": {"diet": 1.0, "normal": 0.1, "bulking": 0.0},
    "normal": {"diet": 0.25, "normal": 1.0, "bulking": 0.25},
    "bulking": {"diet": 0.0, "normal": 0.3, "bulking": 1.0},
}
WEATHER_MEMBERSHIP = {
    "khong_mua": {"no_rain": 1.0, "light_rain": 0.0, "rain": 0.0, "heavy_rain": 0.0},
    "mua_nho": {"no_rain": 0.2, "light_rain": 1.0, "rain": 0.3, "heavy_rain": 0.0},
    "mua_vua": {"no_rain": 0.0, "light_rain": 0.3, "rain": 1.0, "heavy_rain": 0.2},
    "mua_lon": {"no_rain": 0.0, "light_rain": 0.0, "rain": 0.3, "heavy_rain": 1.0},
}
RAIN_MULTIPLIER = {"khong_mua": 1.0, "mua_nho": 1.15, "mua_vua": 1.30, "mua_lon": 1.50}
PREP_TIME = {
    "Drinks": 7,
    "Snack / Street Food": 8,
    "Fast Food Meal": 12,
    "Noodles / Soup Meal": 13,
    "Healthy / Vegetarian Meal": 15,
    "Casual Dining": 20,
    "Hotpot / BBQ / Buffet": 28,
    "Seafood / Specialty Meal": 30,
}
TIME_DISTANCE_MAP = {"very_short": 2.0, "short": 3.5, "medium": 5.5, "long": 8.0, "very_long": 10.0}
SMART_GOAL_WEIGHTS = {
    # Smart mode: no explicit category/cuisine/taste filter. The app should
    # infer intent from fuzzy variables and from the selected health goal.
    "diet": {
        "goal_fit": 0.30,
        "budget_fit": 0.18,
        "delivery_time_fit": 0.16,
        "distance_fit": 0.10,
        "category_match": 0.14,
        "rating_score": 0.07,
        "opening_score": 0.05,
    },
    "normal": {
        "category_match": 0.24,
        "budget_fit": 0.20,
        "delivery_time_fit": 0.16,
        "distance_fit": 0.14,
        "goal_fit": 0.10,
        "rating_score": 0.09,
        "opening_score": 0.07,
    },
    "bulking": {
        "goal_fit": 0.28,
        "budget_fit": 0.18,
        "category_match": 0.18,
        "delivery_time_fit": 0.14,
        "distance_fit": 0.10,
        "rating_score": 0.07,
        "opening_score": 0.05,
    },
}
GUIDED_GOAL_WEIGHTS = {
    # Guided mode: user already picked category/cuisine/taste, so keep
    # user_choice_match strong while still letting Diet/Bulking matter.
    "diet": {
        "goal_fit": 0.30,
        "user_choice_match": 0.18,
        "budget_fit": 0.16,
        "delivery_time_fit": 0.14,
        "distance_fit": 0.08,
        "rating_score": 0.07,
        "opening_score": 0.05,
        "taste_match": 0.02,
    },
    "normal": {
        "user_choice_match": 0.30,
        "budget_fit": 0.18,
        "delivery_time_fit": 0.13,
        "distance_fit": 0.10,
        "goal_fit": 0.08,
        "rating_score": 0.09,
        "opening_score": 0.07,
        "taste_match": 0.05,
    },
    "bulking": {
        "goal_fit": 0.28,
        "user_choice_match": 0.22,
        "budget_fit": 0.16,
        "delivery_time_fit": 0.12,
        "distance_fit": 0.08,
        "rating_score": 0.07,
        "opening_score": 0.05,
        "taste_match": 0.02,
    },
}

# ============================================================
# 2) LOW-LEVEL UTILITIES
# ============================================================
def strip_accents(text: Any) -> str:
    text = "" if text is None else str(text)
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")


def norm_key(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", strip_accents(text).lower())


def clean_str(value: Any, default: str = "") -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    return str(value).strip()


def parse_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else default


def vnd_number(value: str) -> int:
    return int(re.sub(r"\D", "", value) or 0)


def parse_price_range(value: Any) -> Tuple[int, int, int]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 50000, 90000, 70000
    s = str(value)
    nums = re.findall(r"\d[\d\.]*", s)
    vals = [vnd_number(x) for x in nums if vnd_number(x) > 0]
    if not vals:
        return 50000, 90000, 70000
    if len(vals) == 1:
        v = vals[0]
        return v, v, v
    low, high = min(vals[0], vals[1]), max(vals[0], vals[1])
    return low, high, int(round((low + high) / 2))


def parse_coordinates(value: Any) -> Tuple[Optional[float], Optional[float]]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None, None
    nums = re.findall(r"-?\d+(?:\.\d+)?", str(value))
    if len(nums) < 2:
        return None, None
    lat, lng = float(nums[0]), float(nums[1])
    if -90 <= lat <= 90 and -180 <= lng <= 180:
        return lat, lng
    return None, None


def split_values(value: Any) -> List[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    parts = re.split(r"[,;/|]+", str(value))
    return [p.strip() for p in parts if p and p.strip()]


def canonical_health(value: Any) -> str:
    key = norm_key(value)
    if "unhealthy" in key or key in {"khonglanhmanh", "khonghealthy"}:
        return "Unhealthy"
    if "healthy" in key or "lanhmanh" in key:
        return "Healthy"
    return "Normal"


def canonical_calories(value: Any) -> str:
    key = norm_key(value)
    if key.startswith("low") or "thap" in key:
        return "Low"
    if key.startswith("high") or "cao" in key:
        return "High"
    return "Medium"


def canonical_diet_type(value: Any) -> str:
    key = norm_key(value)
    if any(token in key for token in ["chay", "vegetarian", "vegan", "plantbased"]):
        return "Chay"
    return "Mặn"


def canonical_diet_preference(value: Any) -> str:
    # UI/user preference for Diet mode. "Mặn" here means omnivore / no
    # vegetarian restriction, not "must contain meat".
    return "Chay" if canonical_diet_type(value) == "Chay" else "Mặn"


def canonical_protein(value: Any) -> str:
    key = norm_key(value)
    if key.startswith("high") or "cao" in key:
        return "High"
    if key.startswith("low") or "thap" in key:
        return "Low"
    return "Medium"


def canonical_portion(value: Any) -> str:
    key = norm_key(value)
    if key.startswith("large") or "lon" in key or "big" in key:
        return "Large"
    if key.startswith("small") or "nho" in key:
        return "Small"
    return "Medium"


def canonical_taste_list(value: Any) -> List[str]:
    allowed = {"cay": "Cay", "man": "Mặn", "ngot": "Ngọt", "chua": "Chua"}
    out = []
    for part in split_values(value):
        key = norm_key(part)
        if key in allowed and allowed[key] not in out:
            out.append(allowed[key])
    return out


def canonical_category(value: Any) -> Optional[str]:
    key = norm_key(value)
    aliases = {
        "monnuoc": "Noodles / Soup Meal",
        "noodlessoupmeal": "Noodles / Soup Meal",
        "annhanh": "Fast Food Meal",
        "doanhanh": "Fast Food Meal",
        "doannhanh": "Fast Food Meal",
        "fastfoodmeal": "Fast Food Meal",
        "launuong": "Hotpot / BBQ / Buffet",
        "laubuffet": "Hotpot / BBQ / Buffet",
        "hotpotbbqbuffet": "Hotpot / BBQ / Buffet",
        "commonchinh": "Casual Dining",
        "monchinh": "Casual Dining",
        "casualdining": "Casual Dining",
        "healthy": "Healthy / Vegetarian Meal",
        "monchay": "Healthy / Vegetarian Meal",
        "healthyvegetarianmeal": "Healthy / Vegetarian Meal",
        "haisan": "Seafood / Specialty Meal",
        "dacsan": "Seafood / Specialty Meal",
        "seafoodspecialtymeal": "Seafood / Specialty Meal",
        "douong": "Drinks",
        "nuocuong": "Drinks",
        "trasua": "Drinks",
        "drinks": "Drinks",
        "anvat": "Snack / Street Food",
        "anduongpho": "Snack / Street Food",
        "duongpho": "Snack / Street Food",
        "streetfood": "Snack / Street Food",
        "snackstreetfood": "Snack / Street Food",
    }
    if key in aliases:
        return aliases[key]
    exact = {norm_key(c): c for c in CATEGORIES}
    if key in exact:
        return exact[key]
    if any(k in key for k in ["noodle", "soup", "monnuoc", "pho", "bun", "hutieu", "banhcanh", "chao"]):
        return "Noodles / Soup Meal"
    if any(k in key for k in ["fast", "burger", "pizza", "garan", "fried", "chicken"]):
        return "Fast Food Meal"
    if any(k in key for k in ["hotpot", "bbq", "buffet", "lau", "nuong"]):
        return "Hotpot / BBQ / Buffet"
    if any(k in key for k in ["healthy", "vegetarian", "chay", "salad"]):
        return "Healthy / Vegetarian Meal"
    if any(k in key for k in ["seafood", "hai san", "haisan", "specialty", "dac san", "ocs"]):
        return "Seafood / Specialty Meal"
    if any(k in key for k in ["snack", "street", "anvat", "duongpho", "banh", "che", "kem", "dessert", "trangmieng", "traicay"]):
        return "Snack / Street Food"
    if any(k in key for k in ["drink", "coffee", "tea", "trasua", "cafe", "douong", "nuocuong", "nuocep", "sinhto"]):
        return "Drinks"
    if key:
        return "Casual Dining"
    return None


def parse_categories(value: Any) -> List[str]:
    cats = []
    for part in split_values(value):
        cat = canonical_category(part)
        if cat and cat not in cats:
            cats.append(cat)
    return cats or ["Casual Dining"]


def unique_categories(*groups: Iterable[str]) -> List[str]:
    """Return valid categories without duplicates, preserving priority order."""
    out: List[str] = []
    for group in groups:
        for cat in group:
            if cat in CATEGORIES and cat not in out:
                out.append(cat)
    return out or ["Casual Dining"]


def normalize_phrase_text(value: Any) -> str:
    """Accent-free lowercase text with spaces kept for safe phrase matching."""
    text = strip_accents(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " " + re.sub(r"\s+", " ", text).strip() + " "


def refine_categories_from_name(name: Any, parsed_categories: Sequence[str]) -> List[str]:
    """
    Correct noisy dataset labels using high-confidence dish-name rules.

    Important: this function uses phrase/word matching instead of compact
    substring matching. Otherwise names such as "Domino's" accidentally match
    "mì", "Coco" accidentally matches "ốc", or "Chú Chen" accidentally
    matches "chè".
    """
    cats = unique_categories(parsed_categories)
    text = normalize_phrase_text(name)

    def norm_phrase(word: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", strip_accents(word).lower())).strip()

    def has_any(phrases: Sequence[str]) -> bool:
        return any(f" {norm_phrase(p)} " in text for p in phrases)

    # Rice / rice-box / rice-plate concepts are casual dining, never noodles.
    rice_phrases = [
        "cơm", "cơm tấm", "cơm gà", "cơm niêu", "cơm thố", "rice",
        "home meal", "mẹ nấu", "tam kỳ",
    ]
    if has_any(rice_phrases):
        if has_any(["chay", "vegetarian", "vegan"]):
            return unique_categories(["Healthy / Vegetarian Meal", "Casual Dining"])
        return unique_categories(["Casual Dining"])

    # Strong healthy / vegetarian concepts.
    if has_any(["chay", "vegan", "vegetarian", "healthy", "salad", "gạo lứt"]):
        if has_any(["lẩu"]):
            return unique_categories(["Healthy / Vegetarian Meal", "Hotpot / BBQ / Buffet"])
        return unique_categories(["Healthy / Vegetarian Meal", "Casual Dining"])

    # Dessert / snack concepts should not become noodles just because the
    # original label is broad or the name contains words like "hủ tiếu" in a
    # street-food context.
    snack_phrases = [
        "bánh tráng", "bánh cuốn", "bánh ướt", "há cảo", "gỏi đu đủ",
        "ăn vặt", "xiên que", "chè", "kem", "trái cây", "tráng miệng",
        "phô mai que",
    ]
    if has_any(snack_phrases):
        return unique_categories(["Snack / Street Food"])

    # Beverages.
    drink_phrases = [
        "trà sữa", "cafe", "coffee", "cà phê", "nước ép", "sinh tố",
        "vitamins", "vitamin", "soda", "trà đào",
    ]
    if has_any(drink_phrases):
        return unique_categories(["Drinks"])

    # Hotpot / BBQ / buffet. Use this before seafood so seafood hotpot remains
    # a hotpot/buffet experience in the category bar.
    if has_any(["hotpot", "bbq", "buffet", "lẩu", "nướng", "gogi", "dookki", "top pot"]):
        if has_any(["hải sản", "ốc", "tôm", "cua", "ghẹ"]):
            return unique_categories(["Hotpot / BBQ / Buffet", "Seafood / Specialty Meal"])
        # Simple grilled chicken/beef restaurants are still full meals; large
        # named grill/buffet restaurants remain hotpot/BBQ.
        if has_any(["con gà nướng"]):
            return unique_categories(["Casual Dining"])
        return unique_categories(["Hotpot / BBQ / Buffet", "Casual Dining"])

    # Noodle / soup category. Rice keywords were handled first, so names like
    # "Cơm thố Osaka" will never fall into this branch.
    noodle_phrases = [
        "phở", "bún", "bún bò", "bún riêu", "bún chả", "bún cá",
        "hủ tiếu", "mì", "mì cay", "mì xào", "bánh canh", "súp",
        "súp cua", "cháo",
    ]
    fast_phrases = ["pizza", "burger", "gà rán", "fried chicken", "fast food", "wallace", "domino", "hallyu", "hancook", "tokbokki"]
    if has_any(noodle_phrases):
        extras = []
        if has_any(["hải sản", "ghẹ", "cua", "tôm", "cá lóc"]):
            extras.append("Seafood / Specialty Meal")
        if has_any(fast_phrases):
            extras.append("Fast Food Meal")
        return unique_categories(["Noodles / Soup Meal"], extras)

    # Fast food.
    if has_any(fast_phrases):
        return unique_categories(["Fast Food Meal", "Casual Dining"])

    # Seafood / specialty.
    if has_any(["sushi", "sashimi", "hải sản", "ốc", "tôm", "cua", "ghẹ", "seafood", "sao biển"]):
        return unique_categories(["Seafood / Specialty Meal", "Casual Dining"])

    # Dimsum and home-style restaurants are main-meal casual dining.
    if has_any(["dimsum", "quán", "restaurant", "nhà hàng", "bò tơ", "con gà"]):
        return unique_categories(["Casual Dining"])

    # Final safety cleanup: if the Excel label says Noodles but the restaurant
    # name has no noodle/soup signal, remove that noisy label. This prevents
    # cases like Som Tum or generic rice/main-meal places from appearing under
    # Món nước.
    if "Noodles / Soup Meal" in cats and not has_any(noodle_phrases):
        cats = [c for c in cats if c != "Noodles / Soup Meal"]

    return unique_categories(cats)


def infer_primary_category(name: Any, categories: Sequence[str]) -> str:
    cats = unique_categories(categories)
    return cats[0]


def normalize_goal(goal: Any) -> str:
    key = norm_key(goal)
    if key == "diet":
        return "diet"
    if key == "bulking":
        return "bulking"
    return "normal"


def parse_clock(value: Any, fallback: dtime = dtime(18, 15)) -> dtime:
    if isinstance(value, dtime):
        return value
    if value:
        nums = re.findall(r"\d+", str(value))
        if len(nums) >= 2:
            h, m = int(nums[0]) % 24, int(nums[1]) % 60
            return dtime(h, m)
    return fallback


def minutes_of_day(t: dtime) -> int:
    return t.hour * 60 + t.minute


def format_vnd(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", ".") + "đ"


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def choose_by_hash(options: Sequence[str], seed: str) -> str:
    if not options:
        return ""
    return options[abs(hash(seed)) % len(options)]

# ============================================================
# 3) DATA LOADER
# ============================================================
def find_dataset_path() -> Path:
    for p in DATASET_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        "Không tìm thấy file dataset. Hãy đặt file Excel tên 'restaurants.xlsx' cùng thư mục với app.py."
    )


def dataset_signature(path: Path) -> Tuple[str, int, int]:
    stat = path.stat()
    return str(path.resolve()), stat.st_mtime_ns, stat.st_size


def find_col(columns: Iterable[str], aliases: Sequence[str]) -> Optional[str]:
    lookup = {norm_key(c): c for c in columns}
    for alias in aliases:
        if norm_key(alias) in lookup:
            return lookup[norm_key(alias)]
    return None


def resolve_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    cols = list(df.columns)
    return {key: find_col(cols, aliases) for key, aliases in COLUMN_ALIASES.items()}


def category_image(category: str, seed: str) -> str:
    return choose_by_hash(CATEGORY_PHOTOS.get(category) or CATEGORY_PHOTOS["Casual Dining"], seed)


def build_menu_items(rest: Dict[str, Any]) -> List[Dict[str, Any]]:
    category = rest["primary_category"]
    names = MENU_TEMPLATES.get(category, MENU_TEMPLATES["Casual Dining"])
    base = max(15000, rest.get("price_avg", 70000))
    multipliers = [1.0, 0.82, 0.35]
    menu = []
    for idx, name in enumerate(names):
        price = int(round(base * multipliers[idx] / 1000) * 1000)
        menu.append({
            "id": f"{rest['id']}-M{idx + 1}",
            "name": name,
            "price": max(10000, price),
            "image": category_image(category, f"{rest['id']}-{idx}"),
        })
    return menu




def annotate_branch_labels(records: List[Dict[str, Any]]) -> None:
    """Keep duplicate restaurant names, but label branches clearly in the UI."""
    name_counts = Counter(norm_key(r.get("name", "")) for r in records)
    seen: Counter[str] = Counter()
    for rest in records:
        key = norm_key(rest.get("name", ""))
        total = name_counts.get(key, 0)
        if total > 1:
            seen[key] += 1
            idx = seen[key]
            rest["branch_index"] = idx
            rest["branch_total"] = total
            rest["branch_label"] = f"CN {idx}/{total}"
            rest["display_name"] = f"{rest['name']} · CN {idx}"
        else:
            rest["branch_index"] = 1
            rest["branch_total"] = 1
            rest["branch_label"] = ""
            rest["display_name"] = rest.get("name", "")


def load_restaurants() -> List[Dict[str, Any]]:
    path = find_dataset_path()
    signature = dataset_signature(path)
    if DATASET_CACHE["signature"] == signature:
        return deepcopy(DATASET_CACHE["records"])

    df = pd.read_excel(path)
    df = df.dropna(how="all", axis=1).dropna(how="all", axis=0)
    cols = resolve_columns(df)
    required = ["name", "category", "price"]
    missing = [k for k in required if not cols.get(k)]
    if not cols.get("coordinates") and not (cols.get("lat") and cols.get("lng")):
        missing.append("coordinates hoặc lat/lng")
    if missing:
        raise ValueError(
            "Dataset thiếu cột bắt buộc: " + ", ".join(missing) + ". Hãy kiểm tra COLUMN_ALIASES trong app.py."
        )

    records: List[Dict[str, Any]] = []
    for i, row in df.iterrows():
        rid = clean_str(row.get(cols.get("id")) if cols.get("id") else None, f"R{i + 1:03d}")
        name = clean_str(row.get(cols["name"]), f"Quán {i + 1}")
        if cols.get("coordinates"):
            lat, lng = parse_coordinates(row.get(cols["coordinates"]))
        else:
            lat = parse_float(row.get(cols["lat"]), None)
            lng = parse_float(row.get(cols["lng"]), None)
        price_min, price_max, price_avg = parse_price_range(row.get(cols["price"]))
        raw_category = clean_str(row.get(cols["category"]))
        parsed_cats = parse_categories(raw_category)
        cats = refine_categories_from_name(name, parsed_cats)
        primary_category = infer_primary_category(name, cats)
        cuisines = split_values(row.get(cols.get("cuisine"))) if cols.get("cuisine") else []
        tastes = canonical_taste_list(row.get(cols.get("taste"))) if cols.get("taste") else []
        rest = {
            "id": rid,
            "name": name,
            "address": clean_str(row.get(cols.get("address")) if cols.get("address") else None, f"TP.HCM · {lat:.5f}, {lng:.5f}" if lat and lng else "TP.HCM"),
            "lat": lat,
            "lng": lng,
            "rating": parse_float(row.get(cols.get("rating")) if cols.get("rating") else None, None),
            "price_min": price_min,
            "price_max": price_max,
            "price_avg": price_avg,
            "category_source": raw_category,
            "categories": cats,
            "primary_category": primary_category,
            "calories_level": canonical_calories(row.get(cols.get("calories"))) if cols.get("calories") else "Medium",
            "healthy_score": canonical_health(row.get(cols.get("healthy"))) if cols.get("healthy") else "Normal",
            "diet_type": canonical_diet_type(row.get(cols.get("diet_type"))) if cols.get("diet_type") else ("Chay" if primary_category == "Healthy / Vegetarian Meal" else "Mặn"),
            "protein_level": canonical_protein(row.get(cols.get("protein"))) if cols.get("protein") else "Medium",
            "portion_size": canonical_portion(row.get(cols.get("portion"))) if cols.get("portion") else "Medium",
            "cuisines": cuisines,
            "tastes": tastes,
            "opening_hours": clean_str(row.get(cols.get("opening")) if cols.get("opening") else None, ""),
            "image": category_image(primary_category, name),
            "icon": CATEGORY_ICONS.get(primary_category, "🍽️"),
        }
        rest["menu"] = build_menu_items(rest)
        records.append(rest)

    annotate_branch_labels(records)
    DATASET_CACHE["signature"] = signature
    DATASET_CACHE["records"] = records
    return deepcopy(records)


def get_restaurant_by_id(rid: str) -> Optional[Dict[str, Any]]:
    for rest in load_restaurants():
        if str(rest["id"]) == str(rid):
            return deepcopy(rest)
    return None

# ============================================================
# 4) FUZZY ENGINE
# ============================================================
def trimf(x: float, abc: Sequence[float]) -> float:
    a, b, c = abc
    if x == b:
        return 1.0
    if x <= a or x >= c:
        return 0.0
    if a < x < b:
        return (x - a) / (b - a) if b != a else 1.0
    if b < x < c:
        return (c - x) / (c - b) if c != b else 1.0
    return 0.0


def trapmf(x: float, abcd: Sequence[float]) -> float:
    a, b, c, d = abcd
    if x < a or x > d:
        return 0.0
    if a == b and x <= b:
        return 1.0
    if c == d and x >= c:
        return 1.0
    if a < x < b:
        return (x - a) / (b - a) if b != a else 1.0
    if b <= x <= c:
        return 1.0
    if c < x < d:
        return (d - x) / (d - c) if d != c else 1.0
    return 0.0


def eval_mfs(x: float, spec: Dict[str, Tuple[str, Sequence[float]]]) -> Dict[str, float]:
    out = {}
    for name, (kind, params) in spec.items():
        out[name] = clamp01(trapmf(x, params) if kind == "trap" else trimf(x, params))
    return out


def health_degree(goal: Any) -> Dict[str, float]:
    return HEALTH_MEMBERSHIP.get(normalize_goal(goal), HEALTH_MEMBERSHIP["normal"])


def weather_degree(rain_level: Any) -> Dict[str, float]:
    return WEATHER_MEMBERSHIP.get(str(rain_level or "khong_mua"), WEATHER_MEMBERSHIP["khong_mua"])


def weighted_max_distance(time_degree: Dict[str, float]) -> float:
    denom = sum(time_degree.values())
    if denom <= 0:
        return 5.0
    return sum(time_degree[k] * TIME_DISTANCE_MAP[k] for k in TIME_DISTANCE_MAP) / denom


def urgency_adjusted_time(hungry_level: float, requested_time: float) -> Dict[str, Any]:
    """Convert the user's requested wait time into the time used by ranking.

    The UI slider means "I can receive food within X minutes", but hunger is
    a stronger context signal. If someone is very hungry, a long wait is usually
    an inconsistent input rather than a true preference for slow food. Therefore
    high hunger caps the effective time used by fuzzy rules, distance radius,
    ETA fit, and candidate filtering.
    """
    hunger = max(1.0, min(10.0, float(hungry_level or 1.0)))
    requested = max(10.0, min(120.0, float(requested_time or 45.0)))

    if hunger >= 9.0:
        cap = 35.0
        urgency = "rất đói"
    elif hunger >= 8.0:
        cap = 42.0
        urgency = "đói cao"
    elif hunger >= 7.0:
        cap = 50.0
        urgency = "đói khá cao"
    elif hunger >= 5.0:
        cap = 65.0
        urgency = "đói vừa"
    elif hunger >= 3.0:
        cap = 85.0
        urgency = "hơi đói"
    else:
        cap = requested
        urgency = "đói nhẹ"

    effective = min(requested, cap)
    contradiction = max(0.0, requested - effective)
    return {
        "requested_time": requested,
        "effective_time": effective,
        "cap": cap,
        "contradiction_minutes": contradiction,
        "is_contradictory": contradiction >= 8.0,
        "urgency": urgency,
        "summary": (
            f"Bạn chọn mức {urgency} nhưng đặt thời gian {int(requested)} phút; "
            f"Yeppi xử lý như khoảng {int(effective)} phút để ưu tiên món giao nhanh hơn."
            if contradiction >= 8.0 else ""
        ),
    }


def eta_slack_for_hunger(hungry_level: float) -> float:
    """Allowed ETA overflow after urgency adjustment."""
    hunger = max(1.0, min(10.0, float(hungry_level or 1.0)))
    if hunger >= 9.0:
        return 8.0
    if hunger >= 8.0:
        return 10.0
    if hunger >= 7.0:
        return 12.0
    if hunger >= 5.0:
        return 16.0
    return 24.0


def fuzzy_mode_a(budget_per_person: float, hungry_level: float, time_available: float, health_goal: str, rain_level: str) -> Dict[str, Any]:
    b = eval_mfs(budget_per_person, BUDGET_MF)
    h = eval_mfs(hungry_level, HUNGRY_MF)
    t = eval_mfs(time_available, TIME_MF)
    g = health_degree(health_goal)
    w = weather_degree(rain_level)
    scores = {cat: 0.0 for cat in CATEGORIES}

    def add(strength: float, boosts: Sequence[Tuple[str, float]]) -> None:
        strength = clamp01(strength)
        for cat, weight in boosts:
            scores[cat] += strength * weight

    def sub(strength: float, penalties: Sequence[Tuple[str, float]]) -> None:
        strength = clamp01(strength)
        for cat, weight in penalties:
            scores[cat] -= strength * weight

    # 20 boost rules from prompt
    add(min(h["light"], t["very_short"]), [("Drinks", 1.0), ("Snack / Street Food", 0.8)])
    add(min(h["light"], t["short"]), [("Snack / Street Food", 0.9), ("Drinks", 0.7)])
    add(min(h["light"], max(t["medium"], t["long"], t["very_long"])), [("Casual Dining", 0.7), ("Healthy / Vegetarian Meal", 0.5), ("Drinks", 0.5)])
    add(min(h["hungry"], t["very_short"]), [("Fast Food Meal", 1.0), ("Noodles / Soup Meal", 0.8)])
    add(min(h["hungry"], t["short"]), [("Noodles / Soup Meal", 1.0), ("Fast Food Meal", 0.8), ("Casual Dining", 0.6)])
    add(min(h["hungry"], t["medium"]), [("Casual Dining", 1.0), ("Noodles / Soup Meal", 0.7)])
    add(min(h["hungry"], max(t["long"], t["very_long"])), [("Casual Dining", 0.8), ("Hotpot / BBQ / Buffet", 0.5)])
    add(min(h["starving"], t["very_short"]), [("Fast Food Meal", 1.0), ("Noodles / Soup Meal", 0.9)])
    add(min(h["starving"], t["short"]), [("Fast Food Meal", 1.0), ("Noodles / Soup Meal", 0.9), ("Casual Dining", 0.7)])
    add(min(h["starving"], t["medium"]), [("Casual Dining", 1.0), ("Noodles / Soup Meal", 0.7), ("Hotpot / BBQ / Buffet", 0.5)])
    add(min(h["starving"], max(t["long"], t["very_long"])), [("Hotpot / BBQ / Buffet", 1.0), ("Casual Dining", 0.8), ("Seafood / Specialty Meal", 0.6)])
    add(b["very_cheap"], [("Snack / Street Food", 0.8), ("Noodles / Soup Meal", 0.6)])
    add(min(max(b["very_cheap"], b["cheap"]), max(h["hungry"], h["starving"])), [("Noodles / Soup Meal", 0.9), ("Fast Food Meal", 0.7), ("Casual Dining", 0.6)])
    add(min(b["medium"], max(t["medium"], t["long"], t["very_long"])), [("Casual Dining", 0.9), ("Noodles / Soup Meal", 0.5)])
    add(min(max(b["expensive"], b["very_expensive"]), max(t["long"], t["very_long"]), max(h["hungry"], h["starving"])), [("Hotpot / BBQ / Buffet", 0.9), ("Seafood / Specialty Meal", 0.8)])

    # Premium intent correction:
    # A high per-person budget + enough waiting time should mean "occasion / premium meal"
    # rather than "any cheap option is okay". At 60-75 minutes, old rules still treated
    # time as only "medium", so Casual Dining could dominate and cheap rice places won.
    premium_budget_strength = max(b["expensive"], b["very_expensive"])
    patient_time_strength = max(t["medium"], t["long"], t["very_long"])
    meal_need_strength = max(h["hungry"], h["starving"], 0.55 * g["normal"], 0.70 * g["bulking"])
    premium_intent_strength = min(premium_budget_strength, patient_time_strength, meal_need_strength)
    add(premium_intent_strength, [("Hotpot / BBQ / Buffet", 2.4), ("Seafood / Specialty Meal", 2.0), ("Casual Dining", 0.15)])
    sub(premium_intent_strength, [("Drinks", 0.55), ("Snack / Street Food", 0.45), ("Fast Food Meal", 0.35), ("Noodles / Soup Meal", 0.25), ("Casual Dining", 0.25)])

    # Diet should mainly prefer healthy/vegetarian and light meal groups.
    # Do not over-boost all noodles: noodle/soup includes both light dishes
    # and non-diet dishes, so nutrition columns should decide the final rank.
    add(g["diet"], [("Healthy / Vegetarian Meal", 1.0), ("Noodles / Soup Meal", 0.25), ("Seafood / Specialty Meal", 0.25), ("Casual Dining", 0.15)])
    sub(g["diet"], [("Fast Food Meal", 0.55), ("Drinks", 0.45), ("Snack / Street Food", 0.35), ("Hotpot / BBQ / Buffet", 0.25)])
    # Normal health should not override a light/very-short hunger signal.
    # Apply this generic main-meal boost mainly when the user is actually hungry
    # or has enough time for a real meal.
    normal_meal_strength = min(g["normal"], max(h["hungry"], h["starving"], t["medium"], t["long"], t["very_long"]))
    add(normal_meal_strength, [("Casual Dining", 0.6), ("Noodles / Soup Meal", 0.5), ("Fast Food Meal", 0.3)])
    # Bulking means protein + portion, not automatically fast food.
    add(g["bulking"], [("Casual Dining", 0.8), ("Noodles / Soup Meal", 0.55), ("Hotpot / BBQ / Buffet", 0.55), ("Seafood / Specialty Meal", 0.45)])
    add(min(max(w["light_rain"], w["rain"], w["heavy_rain"]), max(h["hungry"], h["starving"])), [("Noodles / Soup Meal", 0.5), ("Hotpot / BBQ / Buffet", 0.3)])
    add(min(max(w["rain"], w["heavy_rain"]), max(t["very_short"], t["short"])), [("Fast Food Meal", 0.5), ("Noodles / Soup Meal", 0.5)])

    # 6 penalty rules from prompt
    sub(t["very_short"], [("Hotpot / BBQ / Buffet", 0.8), ("Seafood / Specialty Meal", 0.7)])
    sub(b["very_cheap"], [("Seafood / Specialty Meal", 0.9), ("Hotpot / BBQ / Buffet", 0.7)])
    sub(g["diet"], [("Fast Food Meal", 0.35), ("Hotpot / BBQ / Buffet", 0.15)])
    sub(h["light"], [("Hotpot / BBQ / Buffet", 0.4), ("Seafood / Specialty Meal", 0.3)])
    sub(min(max(b["expensive"], b["very_expensive"]), max(t["very_short"], t["short"])), [("Hotpot / BBQ / Buffet", 0.5), ("Seafood / Specialty Meal", 0.4)])
    sub(h["starving"], [("Drinks", 0.5), ("Snack / Street Food", 0.2)])

    scores = {cat: max(0.0, val) for cat, val in scores.items()}
    max_score = max(scores.values()) if scores else 0
    if max_score <= 0:
        normalized = {cat: 0.0 for cat in CATEGORIES}
        top_categories = ["Casual Dining", "Noodles / Soup Meal", "Fast Food Meal"]
    else:
        normalized = {cat: val / max_score for cat, val in scores.items()}
        top_categories = sorted(normalized, key=normalized.get, reverse=True)[:3]
    return {
        "budget_degree": b,
        "hungry_degree": h,
        "time_degree": t,
        "health_degree": g,
        "weather_degree": w,
        "category_scores": normalized,
        "top_categories": top_categories,
        "max_distance_km": weighted_max_distance(t),
    }

# ============================================================
# 5) OPENING HOURS + DELIVERY ESTIMATION
# ============================================================
def opening_windows(opening_raw: str) -> List[Tuple[int, int]]:
    raw = opening_raw or ""
    windows = []
    for h1, m1, h2, m2 in re.findall(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", raw):
        start = int(h1) * 60 + int(m1)
        end = int(h2) * 60 + int(m2)
        if start == end:
            windows.append((0, 24 * 60))
        elif end < start:
            windows.append((start, 24 * 60))
            windows.append((0, end))
        else:
            windows.append((start, end))
    return windows


def is_open_and_minutes_until_close(opening_raw: str, current_time: dtime) -> Tuple[bool, float]:
    windows = opening_windows(opening_raw)
    if not windows:
        return True, 360.0
    now = minutes_of_day(current_time)
    for start, end in windows:
        if start <= now <= end:
            return True, max(0.0, float(end - now))
    return False, 0.0


def is_between(t: dtime, start: Tuple[int, int], end: Tuple[int, int]) -> bool:
    m = minutes_of_day(t)
    return start[0] * 60 + start[1] <= m <= end[0] * 60 + end[1]


def speed_kmh(current_time: dtime) -> float:
    if is_between(current_time, (7, 0), (9, 30)):
        return 28.0
    if is_between(current_time, (11, 0), (13, 30)):
        return 25.0
    if is_between(current_time, (16, 30), (19, 0)):
        return 20.0
    return 38.0


def prep_time_minutes(category: str, current_time: dtime) -> float:
    prep = float(PREP_TIME.get(category, 20))
    if is_between(current_time, (11, 0), (13, 30)) or is_between(current_time, (17, 0), (19, 30)):
        prep *= 1.25
    return prep


def delivery_estimate_minutes(rest: Dict[str, Any], distance_km: float, current_time: dtime, rain_level: str) -> float:
    prep = prep_time_minutes(rest.get("primary_category", "Casual Dining"), current_time)
    travel = distance_km / max(1.0, speed_kmh(current_time)) * 60.0
    return prep + 5.0 + travel * RAIN_MULTIPLIER.get(rain_level, 1.0)


def delivery_range(estimate: float) -> Dict[str, Any]:
    lo = max(1, int(estimate * 0.85))
    hi = max(lo + 1, int(estimate * 1.20))
    return {"min": lo, "max": hi, "text": f"{lo}–{hi} phút"}

# ============================================================
# 6) ROUTING: TRUE ROAD DISTANCE VIA OSRM + FALLBACK
# ============================================================
def route_cache_key(user_lat: float, user_lng: float, restaurants: Sequence[Dict[str, Any]]) -> str:
    rest_parts = [
        f"{r['id']}@{round(float(r['lat']), 5)},{round(float(r['lng']), 5)}"
        for r in restaurants
        if r.get("lat") is not None and r.get("lng") is not None
    ]
    return f"{round(user_lat, 5)},{round(user_lng, 5)}|" + ",".join(rest_parts)


def fallback_route_metric(user_lat: float, user_lng: float, rest: Dict[str, Any]) -> Dict[str, Any]:
    bird = haversine_km(user_lat, user_lng, rest["lat"], rest["lng"])
    road = bird * 1.32
    return {
        "distance_km": round(road, 3),
        "osrm_duration_min": round(road / 28.0 * 60.0, 1),
        "route_source": "fallback_haversine_x1.32",
    }


def route_table(user_lat: float, user_lng: float, restaurants: List[Dict[str, Any]], batch_size: int = 45) -> Dict[str, Dict[str, Any]]:
    key = route_cache_key(user_lat, user_lng, restaurants)
    if key in ROUTE_TABLE_CACHE:
        return ROUTE_TABLE_CACHE[key]

    metrics = {str(r["id"]): fallback_route_metric(user_lat, user_lng, r) for r in restaurants}
    for start in range(0, len(restaurants), batch_size):
        batch = restaurants[start:start + batch_size]
        coords = [f"{user_lng},{user_lat}"] + [f"{r['lng']},{r['lat']}" for r in batch]
        destinations = ";".join(str(i) for i in range(1, len(coords)))
        url = f"{OSRM_BASE_URL.rstrip('/')}/table/v1/driving/" + ";".join(coords)
        try:
            resp = requests.get(url, params={"sources": "0", "destinations": destinations, "annotations": "distance,duration"}, timeout=OSRM_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == "Ok":
                dists = (data.get("distances") or [[]])[0]
                durs = (data.get("durations") or [[]])[0]
                for i, rest in enumerate(batch):
                    if i < len(dists) and dists[i] is not None:
                        metrics[str(rest["id"])] = {
                            "distance_km": round(float(dists[i]) / 1000.0, 3),
                            "osrm_duration_min": round(float(durs[i]) / 60.0, 1) if i < len(durs) and durs[i] is not None else None,
                            "route_source": "osrm_table",
                        }
        except Exception:
            # Keep fallback metrics. The app should not crash when OSRM is offline/rate-limited.
            continue
    ROUTE_TABLE_CACHE[key] = metrics
    return metrics


def get_route_geometry(rest: Dict[str, Any], user_lat: float = DEFAULT_USER_LAT, user_lng: float = DEFAULT_USER_LNG) -> Dict[str, Any]:
    key = f"{rest['id']}@{round(float(rest['lat']), 5)},{round(float(rest['lng']), 5)}|{round(user_lat, 5)},{round(user_lng, 5)}"
    if key in ROUTE_GEOMETRY_CACHE:
        return ROUTE_GEOMETRY_CACHE[key]
    coords = f"{rest['lng']},{rest['lat']};{user_lng},{user_lat}"
    url = f"{OSRM_BASE_URL.rstrip('/')}/route/v1/driving/{coords}"
    out = {
        "source": "fallback_straight_line",
        "distance_km": round(haversine_km(rest["lat"], rest["lng"], user_lat, user_lng) * 1.32, 3),
        "duration_min": None,
        "points": [[rest["lat"], rest["lng"]], [user_lat, user_lng]],
    }
    try:
        resp = requests.get(url, params={"overview": "full", "geometries": "geojson", "steps": "false"}, timeout=OSRM_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == "Ok" and data.get("routes"):
            route = data["routes"][0]
            points = [[latlng[1], latlng[0]] for latlng in route["geometry"]["coordinates"]]
            out = {
                "source": "osrm_route",
                "distance_km": round(float(route.get("distance", 0)) / 1000.0, 3),
                "duration_min": round(float(route.get("duration", 0)) / 60.0, 1),
                "points": points,
            }
    except Exception:
        pass
    ROUTE_GEOMETRY_CACHE[key] = out
    return out


def interpolate_route(points: List[List[float]], progress: float) -> List[float]:
    progress = clamp01(progress)
    if not points:
        return [DEFAULT_USER_LAT, DEFAULT_USER_LNG]
    if len(points) == 1 or progress <= 0:
        return points[0]
    if progress >= 1:
        return points[-1]
    seg_lengths = []
    total = 0.0
    for a, b in zip(points[:-1], points[1:]):
        length = haversine_km(a[0], a[1], b[0], b[1])
        seg_lengths.append(length)
        total += length
    target = total * progress
    acc = 0.0
    for i, length in enumerate(seg_lengths):
        if acc + length >= target:
            ratio = 0 if length == 0 else (target - acc) / length
            a, b = points[i], points[i + 1]
            return [a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio]
        acc += length
    return points[-1]

# ============================================================
# 7) SCORING FUNCTIONS
# ============================================================
def budget_fit(price_avg: float, budget_per_person: float) -> float:
    """Score price against the user's per-person budget.

    Previous logic returned 1.0 for every restaurant cheaper than the budget.
    That made a 35k rice shop look just as suitable as a 350k hotpot/seafood
    restaurant when the user entered 1,000,000đ/person. This version still
    respects the budget as a ceiling, but also aligns the suggestion with the
    spending tier implied by the user.
    """
    budget = max(1.0, float(budget_per_person or 1.0))
    price = max(0.0, float(price_avg or 0.0))
    ratio = price / budget

    # Too expensive for the declared budget remains a strong negative.
    if ratio > 1.70:
        return 0.0

    # High budget usually means the user expects a fuller / premium meal.
    # Extremely cheap places are allowed, but they should not top the ranking
    # only because they are close and under budget.
    if budget >= 600000:
        if ratio < 0.08:
            return 0.18
        if ratio < 0.15:
            return 0.35
        if ratio < 0.28:
            return 0.58
        if ratio < 0.45:
            return 0.78
        if ratio <= 1.05:
            return 1.0
        if ratio <= 1.25:
            return 0.78
        if ratio <= 1.45:
            return 0.48
        return 0.22

    if budget >= 300000:
        if ratio < 0.12:
            return 0.30
        if ratio < 0.25:
            return 0.55
        if ratio < 0.40:
            return 0.78
        if ratio <= 1.05:
            return 1.0
        if ratio <= 1.25:
            return 0.76
        if ratio <= 1.50:
            return 0.45
        return 0.20

    if budget >= 150000:
        if ratio < 0.18:
            return 0.48
        if ratio < 0.35:
            return 0.75
        if ratio <= 1.05:
            return 1.0
        if ratio <= 1.25:
            return 0.76
        if ratio <= 1.50:
            return 0.45
        return 0.20

    if budget >= 75000:
        if ratio < 0.25:
            return 0.68
        if ratio <= 1.05:
            return 1.0
        if ratio <= 1.25:
            return 0.76
        if ratio <= 1.50:
            return 0.45
        return 0.20

    # Student / very low budget mode: any affordable option is a good option.
    if ratio <= 1.0:
        return 1.0
    if ratio <= 1.2:
        return 0.8
    if ratio <= 1.5:
        return 0.5
    if ratio <= 1.7:
        return 0.25
    return 0.0


def delivery_time_fit(estimated: float, time_available: float) -> float:
    """Score ETA as a constraint, with a soft preference for fuller options when time is relaxed."""
    estimated = max(0.0, float(estimated or 0.0))
    time_available = max(1.0, float(time_available or 1.0))
    diff = estimated - time_available
    if diff > 20:
        return 0.0
    if diff > 10:
        return 0.25
    if diff > 0:
        return 0.6

    # If the user can wait a long time, a 15-minute ultra-fast option should not
    # get exactly the same time score as a more appropriate 35-55 minute meal.
    if time_available >= 90:
        if estimated < 25:
            return 0.62
        if estimated < 35:
            return 0.78
        return 1.0
    if time_available >= 65:
        if estimated < 18:
            return 0.72
        if estimated < 28:
            return 0.86
        return 1.0
    return 1.0


def distance_fit(distance_km: float, max_distance_km: float) -> float:
    return max(0.0, 1.0 - distance_km / max(0.1, max_distance_km))


def goal_fit(rest: Dict[str, Any], goal: str, diet_preference: str = "Mặn") -> float:
    """Fuzzy suitability for the selected health goal using MVP dataset fields."""
    goal_key = normalize_goal(goal)
    health = canonical_health(rest.get("healthy_score", "Normal"))
    cal = canonical_calories(rest.get("calories_level", "Medium"))
    diet_type = canonical_diet_type(rest.get("diet_type", "Mặn"))
    protein = canonical_protein(rest.get("protein_level", "Medium"))
    portion = canonical_portion(rest.get("portion_size", "Medium"))
    category = rest.get("primary_category", "")

    if goal_key == "diet":
        hmap = {"Healthy": 0.50, "Normal": 0.32, "Unhealthy": 0.08}
        cmap = {"Low": 0.35, "Medium": 0.22, "High": 0.03}
        score = hmap[health] + cmap[cal]

        # Vegetarian diet is hard-filtered elsewhere. This small boost only
        # orders vegetarian candidates among themselves. Omnivore Diet still
        # allows vegetarian places, because "Mặn" means no chay restriction.
        if normalize_goal(goal) == "diet" and canonical_diet_preference(diet_preference) == "Chay" and diet_type == "Chay":
            score += 0.12
        elif diet_type == "Chay" and health == "Healthy":
            score += 0.04

        # Safety caps for categories that are often sugary/fried/heavy when
        # the row is not marked as Healthy. Dataset labels still decide first.
        if cal == "High" and health == "Unhealthy":
            score = min(score, 0.18)
        if category in {"Fast Food Meal", "Snack / Street Food", "Drinks"} and health != "Healthy":
            score = min(score, 0.45)
        return clamp01(score)

    if goal_key == "bulking":
        pmap = {"High": 0.50, "Medium": 0.32, "Low": 0.08}
        smap = {"Large": 0.30, "Medium": 0.20, "Small": 0.05}
        cmap = {"High": 0.20, "Medium": 0.16, "Low": 0.06}
        score = pmap[protein] + smap[portion] + cmap[cal]
        # High-calorie drinks/snacks are not good bulking choices if protein is low.
        if category in {"Drinks", "Snack / Street Food"} and protein == "Low":
            score = min(score, 0.32)
        if protein == "Low" and portion == "Small":
            score = min(score, 0.28)
        return clamp01(score)

    # Normal mode is intentionally permissive: nutrition is a light preference,
    # not a strict filter.
    hmap = {"Healthy": 0.85, "Normal": 0.76, "Unhealthy": 0.55}
    cmap = {"Low": 0.76, "Medium": 0.80, "High": 0.62}
    return clamp01((hmap[health] + cmap[cal]) / 2.0)


def score_weights_for_context(context: Dict[str, Any]) -> Dict[str, float]:
    goal_key = normalize_goal(context.get("health_goal", "Normal"))
    if context.get("mode") == "guided":
        return GUIDED_GOAL_WEIGHTS.get(goal_key, GUIDED_GOAL_WEIGHTS["normal"])
    return SMART_GOAL_WEIGHTS.get(goal_key, SMART_GOAL_WEIGHTS["normal"])


def rating_score(rating: Optional[float]) -> float:
    if rating is None or rating != rating:
        return 0.5
    return clamp01((float(rating) - 1.0) / 4.0)


def opening_score(minutes_until_close: float, estimated_delivery: float) -> float:
    if minutes_until_close < estimated_delivery:
        return 0.0
    if minutes_until_close >= estimated_delivery + 30:
        return 1.0
    if minutes_until_close >= estimated_delivery + 15:
        return 0.6
    return 0.3


def taste_match(user_tastes: Sequence[str], restaurant_tastes: Sequence[str]) -> float:
    user = [t for t in user_tastes if t]
    if not user:
        return 0.5
    rest = set(restaurant_tastes or [])
    return len([t for t in user if t in rest]) / max(1, len(user))


def category_intersects(rest: Dict[str, Any], allowed: Sequence[str]) -> bool:
    # UI category chips are strict primary-category filters. Secondary tags are
    # displayed for context but should not make Bún bò appear under Cơm, etc.
    return rest.get("primary_category") in set(allowed)


def normalize_selected_categories(value: Any) -> List[str]:
    """Return a clean list of selected primary categories from UI/API payload.

    The UI can now send multiple categories. In guided mode this list is an
    immutable hard constraint: restaurants may match ANY selected category, but
    they may not fall outside the selected set.
    """
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = [] if value in {"", "all"} else [value]
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        raw_values = list(value)
    else:
        raw_values = [value]

    out: List[str] = []
    for raw in raw_values:
        if raw is None or str(raw).strip() in {"", "all"}:
            continue
        cat = search_category_hint(raw)
        if cat in CATEGORIES and cat not in out:
            out.append(cat)
    return out


def selected_category_label(selected_categories: Sequence[str]) -> str:
    if not selected_categories:
        return "all"
    if len(selected_categories) == 1:
        return selected_categories[0]
    return "multiple"


def user_choice_match(rest: Dict[str, Any], selected_categories: Sequence[str], selected_cuisine: str, selected_tastes: Sequence[str]) -> float:
    parts = []
    selected_set = set(selected_categories or [])
    if selected_set:
        parts.append(1.0 if rest.get("primary_category") in selected_set else 0.0)
    if selected_cuisine and selected_cuisine != "Tất cả":
        parts.append(1.0 if selected_cuisine in rest.get("cuisines", []) else 0.0)
    if selected_tastes:
        parts.append(taste_match(selected_tastes, rest.get("tastes", [])))
    return sum(parts) / len(parts) if parts else 0.6


def score_restaurant(rest: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    selected_categories = context["selected_categories"]
    selected_cuisine = context["selected_cuisine"]
    selected_tastes = context["selected_tastes"]
    category_scores = context["category_scores"]
    max_distance = context["effective_max_distance"]
    components = {
        "category_match": max(category_scores.get(cat, 0.0) for cat in rest.get("categories", ["Casual Dining"])),
        "user_choice_match": user_choice_match(rest, selected_categories, selected_cuisine, selected_tastes),
        "budget_fit": budget_fit(rest["price_avg"], context["budget_per_person"]),
        "delivery_time_fit": delivery_time_fit(rest["estimated_delivery_min"], context["time_available"]),
        "distance_fit": distance_fit(rest["distance_km"], max_distance),
        "goal_fit": goal_fit(rest, context["health_goal"], context.get("diet_preference", "Mặn")),
        "rating_score": rating_score(rest.get("rating")),
        "opening_score": opening_score(rest["minutes_until_close"], rest["estimated_delivery_min"]),
        "taste_match": taste_match(selected_tastes, rest.get("tastes", [])),
    }
    weights = score_weights_for_context(context)
    final = sum(components.get(k, 0.0) * w for k, w in weights.items())
    rest["components"] = {k: round(v, 3) for k, v in components.items()}
    rest["final_score"] = round(final, 4)
    rest["reasons"] = build_reasons(rest, context)
    return rest


def build_reasons(rest: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
    c = rest.get("components", {})
    reasons = []
    if context["mode"] == "guided" and c.get("user_choice_match", 0) >= 0.65:
        reasons.append("đúng nhóm món/cuisine bạn chọn")
    elif c.get("category_match", 0) >= 0.55:
        reasons.append("hợp nhóm món app đang ưu tiên")
    budget_per_person = max(1.0, float(context.get("budget_per_person", rest.get("price_avg", 1)) or 1))
    price_ratio = float(rest.get("price_avg", 0) or 0) / budget_per_person
    if c.get("budget_fit", 0) >= 0.8:
        reasons.append("hợp mức chi tiêu")
    elif c.get("budget_fit", 0) >= 0.5 and price_ratio > 1.0:
        reasons.append("giá chỉ vượt nhẹ")
    elif c.get("budget_fit", 0) >= 0.5:
        reasons.append("giá thấp hơn budget")
    if c.get("distance_fit", 0) >= 0.65:
        reasons.append("gần bạn")
    if c.get("delivery_time_fit", 0) >= 0.8:
        reasons.append("giao kịp thời gian")
    if c.get("goal_fit", 0) >= 0.75:
        goal_key = normalize_goal(context.get("health_goal", "Normal"))
        if goal_key == "diet":
            reasons.append("hợp mục tiêu diet")
        elif goal_key == "bulking":
            reasons.append("hợp mục tiêu bulking")
        else:
            reasons.append("hợp mục tiêu sức khỏe")
    if c.get("taste_match", 0) >= 0.8 and context.get("selected_tastes"):
        reasons.append("hợp khẩu vị " + ", ".join(context["selected_tastes"]))
    if c.get("rating_score", 0) >= 0.85:
        reasons.append("rating rất tốt")
    return reasons[:4] or ["cân bằng tốt giữa giá, khoảng cách và thời gian giao"]


def apply_diversity(scored: List[Dict[str, Any]], top_n: int = TOP_N_RESULTS) -> List[Dict[str, Any]]:
    sorted_items = sorted(scored, key=lambda r: r.get("final_score", 0), reverse=True)
    result, seen, count = [], set(), Counter()
    for rest in sorted_items:
        cat = rest.get("primary_category", "Casual Dining")
        if len(result) < min(5, top_n) and count[cat] < 2:
            result.append(rest)
            seen.add(rest["id"])
            count[cat] += 1
    for rest in sorted_items:
        if len(result) >= top_n:
            break
        if rest["id"] not in seen:
            result.append(rest)
            seen.add(rest["id"])
    return result[:top_n]


def apply_guided_category_balance(scored: List[Dict[str, Any]], selected_categories: Sequence[str], top_n: int = TOP_N_RESULTS) -> List[Dict[str, Any]]:
    """Balance the first results across multiple user-selected categories.

    This is only used when the user explicitly selects multiple categories.
    Category remains a hard constraint, but Yeppi avoids showing only one
    selected group at the top when there are good candidates from the others.
    """
    sorted_items = sorted(scored, key=lambda r: r.get("final_score", 0), reverse=True)
    selected = [c for c in selected_categories if c in CATEGORIES]
    if len(selected) <= 1:
        return apply_diversity(scored, top_n)

    by_cat: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in selected}
    for rest in sorted_items:
        cat = rest.get("primary_category")
        if cat in by_cat:
            by_cat[cat].append(rest)

    active_cats = [cat for cat in selected if by_cat.get(cat)]
    if len(active_cats) <= 1:
        return apply_diversity(scored, top_n)

    result: List[Dict[str, Any]] = []
    seen: set[str] = set()
    # Reserve the first screen for a fair comparison among selected categories.
    balanced_limit = min(top_n, max(len(active_cats), min(5, len(sorted_items))))
    while len(result) < balanced_limit:
        added = False
        for cat in active_cats:
            while by_cat[cat] and by_cat[cat][0]["id"] in seen:
                by_cat[cat].pop(0)
            if by_cat[cat] and len(result) < balanced_limit:
                item = by_cat[cat].pop(0)
                item["rank_note"] = "Cân bằng nhóm món đã chọn"
                result.append(item)
                seen.add(item["id"])
                added = True
        if not added:
            break

    # Fill the rest by absolute score.
    for rest in sorted_items:
        if len(result) >= top_n:
            break
        if rest["id"] not in seen:
            result.append(rest)
            seen.add(rest["id"])
    return result[:top_n]

# ============================================================
# 8) RECOMMENDATION PIPELINE: FUZZY -> FILTER -> SCORE -> DIVERSITY
# ============================================================
SEARCH_TYPE_LABELS = {
    "restaurant": "Tên quán",
    "menu": "Món trong menu",
    "category": "Nhóm món",
    "cuisine": "Cuisine",
    "taste": "Khẩu vị",
    "address": "Địa chỉ",
}

POPULAR_SEARCH_TERMS = [
    "bún bò", "phở", "cơm tấm", "cơm thố", "gà rán", "pizza",
    "lẩu", "sushi", "trà sữa", "healthy", "ăn vặt", "hải sản",
]

SEARCH_SYNONYMS = {
    "com": ["cơm", "rice", "cơm tấm", "cơm gà", "cơm thố", "cơm niêu"],
    "bun": ["bún", "bún bò", "bún riêu", "bún chả", "bún đậu"],
    "pho": ["phở", "pho"],
    "mi": ["mì", "mì cay", "mì xào", "noodle"],
    "lau": ["lẩu", "hotpot"],
    "nuong": ["nướng", "bbq", "grill"],
    "ga": ["gà", "gà rán", "chicken"],
    "tra": ["trà", "trà sữa", "tea"],
    "cafe": ["cafe", "cà phê", "coffee"],
    "healthy": ["healthy", "salad", "vegetarian", "gạo lứt"],
    "anvat": ["ăn vặt", "snack", "street food", "bánh tráng", "xiên que"],
}


def search_phrase(value: Any) -> str:
    """Accent-free text with spaces for safe search matching."""
    return normalize_phrase_text(value).strip()


def search_tokens(value: Any) -> List[str]:
    return [t for t in search_phrase(value).split() if len(t) >= 2]


def expanded_search_terms(query: Any) -> List[str]:
    terms = [search_phrase(query)]
    compact = norm_key(query)
    query_token_count = len(search_tokens(query))
    for key, vals in SEARCH_SYNONYMS.items():
        # Only expand broad one-word concepts. If the user entered a specific
        # dish phrase such as "bún bò" or "trà sữa", keep that intent precise.
        if compact == key and query_token_count <= 1:
            terms.extend(search_phrase(v) for v in vals)
        else:
            for v in vals:
                if norm_key(v) == compact:
                    terms.append(search_phrase(v))
    seen: set[str] = set()
    out: List[str] = []
    for term in terms:
        term = re.sub(r"\s+", " ", term).strip()
        if term and term not in seen:
            out.append(term)
            seen.add(term)
    return out




def search_category_hint(query: Any) -> Optional[str]:
    """Strict category hint for search. Unlike canonical_category(), this never
    falls back to Casual Dining for arbitrary text.
    """
    q = search_phrase(query)
    qc = norm_key(query)
    if not qc:
        return None
    candidates: List[Tuple[Sequence[str], str]] = [
        (["bun", "bún", "pho", "phở", "mi", "mì", "hu tieu", "hủ tiếu", "banh canh", "bánh canh", "chao", "cháo", "noodle", "soup"], "Noodles / Soup Meal"),
        (["pizza", "burger", "ga ran", "gà rán", "fried chicken", "fast food", "an nhanh", "ăn nhanh"], "Fast Food Meal"),
        (["lau", "lẩu", "nuong", "nướng", "bbq", "buffet", "hotpot"], "Hotpot / BBQ / Buffet"),
        (["com", "cơm", "rice", "com tam", "cơm tấm", "com tho", "cơm thố", "com ga", "cơm gà", "mon chinh", "món chính"], "Casual Dining"),
        (["healthy", "salad", "chay", "vegetarian", "vegan", "gao lut", "gạo lứt"], "Healthy / Vegetarian Meal"),
        (["hai san", "hải sản", "seafood", "sushi", "sashimi", "oc", "ốc", "tom", "tôm", "cua", "ghe", "ghẹ"], "Seafood / Specialty Meal"),
        (["do uong", "đồ uống", "drink", "tra sua", "trà sữa", "cafe", "cà phê", "coffee", "nuoc ep", "nước ép", "sinh to", "sinh tố"], "Drinks"),
        (["an vat", "ăn vặt", "snack", "street food", "banh trang", "bánh tráng", "xien que", "xiên que", "che", "chè", "kem"], "Snack / Street Food"),
    ]
    for phrases, cat in candidates:
        for phrase in phrases:
            p = search_phrase(phrase)
            pc = norm_key(phrase)
            if not pc:
                continue
            if f" {p} " in f" {q} " or qc == pc or (len(pc) >= 4 and pc in qc):
                return cat
    for cat, label in CATEGORY_LABELS.items():
        if cat == "all":
            continue
        if qc == norm_key(label) or qc == norm_key(cat):
            return cat
    return None



def is_broad_category_search(query: Any, cat_hint: Optional[str]) -> bool:
    if not cat_hint:
        return False
    q = search_phrase(query)
    qc = norm_key(query)
    broad_terms = {
        "Noodles / Soup Meal": ["mon nuoc", "món nước", "bun pho mi", "bún phở mì", "noodle", "soup"],
        "Fast Food Meal": ["an nhanh", "ăn nhanh", "fast food"],
        "Hotpot / BBQ / Buffet": ["lau nuong", "lẩu nướng", "hotpot", "bbq", "buffet"],
        "Casual Dining": ["com", "cơm", "mon chinh", "món chính", "rice meal"],
        "Healthy / Vegetarian Meal": ["healthy", "mon chay", "món chay", "vegetarian", "vegan"],
        "Seafood / Specialty Meal": ["hai san", "hải sản", "seafood", "dac san", "đặc sản"],
        "Drinks": ["do uong", "đồ uống", "nuoc uong", "nước uống", "drinks"],
        "Snack / Street Food": ["an vat", "ăn vặt", "street food", "snack"],
    }
    for term in broad_terms.get(cat_hint, []):
        if qc == norm_key(term) or q == search_phrase(term):
            return True
    return qc == norm_key(CATEGORY_LABELS.get(cat_hint, "")) or qc == norm_key(cat_hint)

def restaurant_search_fields(rest: Dict[str, Any]) -> Dict[str, str]:
    menu_names = " ".join(m.get("name", "") for m in rest.get("menu", []))
    primary = rest.get("primary_category", "")
    primary_label = CATEGORY_LABELS.get(primary, primary)
    return {
        "restaurant": " ".join([rest.get("name", ""), rest.get("display_name", "")]),
        "menu": menu_names,
        "category": " ".join([primary, primary_label]),
        "cuisine": " ".join(rest.get("cuisines", [])),
        "taste": " ".join(rest.get("tastes", [])),
        "address": rest.get("address", ""),
    }


def search_match_info(rest: Dict[str, Any], search_query: Any) -> Dict[str, Any]:
    """Robust accent-insensitive search for restaurants, menu and tags.

    Search is a user intent filter, but it must not override selected category
    hard-filters. This function only decides whether a restaurant matches the
    search text and how strongly it matches.
    """
    raw = clean_str(search_query)
    if not raw:
        return {"matched": True, "score": 0.0, "type": "", "label": "", "terms": []}

    query_terms = expanded_search_terms(raw)
    q_phrase = query_terms[0] if query_terms else search_phrase(raw)
    q_compact = norm_key(raw)
    q_tokens = search_tokens(raw)
    fields = restaurant_search_fields(rest)

    best_score = 0.0
    best_type = ""
    best_label = ""

    for field_type, text in fields.items():
        field_phrase = search_phrase(text)
        field_compact = norm_key(text)
        field_tokens = search_tokens(text)
        field_token_set = set(field_tokens)
        score = 0.0

        # Strong direct phrase/compact matching.
        for term in query_terms:
            compact_term = norm_key(term)
            if field_type == "menu" and compact_term == "chay":
                # Prevent "chay" search from matching the generic phrase "bán chạy".
                continue
            if term:
                if len(search_tokens(term)) == 1:
                    if f" {term} " in f" {field_phrase} ":
                        score = max(score, 1.0)
                elif term in field_phrase:
                    score = max(score, 1.0)
            if len(compact_term) >= 4 and compact_term in field_compact:
                score = max(score, 0.96)

        # Token coverage lets queries such as "bun bo" match noisy full names.
        if q_tokens:
            matched = 0.0
            for token in q_tokens:
                if token == "chay" and field_type == "menu":
                    # Avoid false positives from generic menu wording like "bán chạy".
                    continue
                if token in field_token_set:
                    matched += 1.0
                elif len(token) >= 4 and any(token in ft or ft in token for ft in field_tokens if len(ft) >= 4):
                    matched += 0.82
                elif len(token) >= 4:
                    best_fuzzy = max((SequenceMatcher(None, token, ft).ratio() for ft in field_tokens if len(ft) >= 4), default=0.0)
                    if best_fuzzy >= 0.86:
                        matched += 0.65
            coverage = matched / max(1, len(q_tokens))
            if coverage >= 0.65:
                score = max(score, min(0.92, coverage))

        # Fuzzy phrase fallback for short typos like "trasua" or "bunbo".
        if q_compact and len(q_compact) >= 4 and not (field_type == "menu" and q_compact == "chay"):
            field_parts = [norm_key(x) for x in re.split(r"\s+", field_phrase) if len(norm_key(x)) >= 3]
            chunks = field_parts + [norm_key(" ".join(field_parts[i:i + 2])) for i in range(max(0, len(field_parts) - 1))]
            fuzzy = max((SequenceMatcher(None, q_compact, c).ratio() for c in chunks), default=0.0)
            if fuzzy >= 0.86:
                score = max(score, 0.70)

        if score > best_score:
            best_score = score
            best_type = field_type
            best_label = SEARCH_TYPE_LABELS.get(field_type, field_type)

    # Category aliases should work even when the Excel category label is English.
    cat_hint = search_category_hint(raw)
    if cat_hint and rest.get("primary_category") == cat_hint and is_broad_category_search(raw, cat_hint):
        best_score = max(best_score, 0.88)
        best_type = "category"
        best_label = "Nhóm món"

    matched = best_score >= 0.52
    return {
        "matched": matched,
        "score": round(best_score, 3),
        "type": best_type if matched else "",
        "label": best_label if matched else "",
        "terms": query_terms,
        "category_hint": cat_hint if matched else None,
    }


def should_match_search(rest: Dict[str, Any], search_query: str) -> bool:
    return bool(search_match_info(rest, search_query).get("matched"))


def build_search_suggestions(query: Any, limit: int = 8) -> List[Dict[str, str]]:
    raw = clean_str(query)
    suggestions: List[Dict[str, str]] = []

    def add(label: str, kind: str, value: Optional[str] = None) -> None:
        label = clean_str(label)
        value = clean_str(value or label)
        if not label:
            return
        key = (norm_key(label), kind)
        if key not in {(norm_key(s["label"]), s["type"]) for s in suggestions}:
            suggestions.append({"label": label, "type": kind, "value": value})

    if not raw:
        for term in POPULAR_SEARCH_TERMS[:limit]:
            add(term, "popular")
        return suggestions[:limit]

    rows = load_restaurants()
    scored: List[Tuple[float, Dict[str, str]]] = []
    raw_compact = norm_key(raw)
    for rest in rows:
        label = rest.get("display_name") or rest.get("name") or ""
        if raw_compact and len(raw_compact) >= 2 and raw_compact in norm_key(label):
            scored.append((0.98, {"label": label, "type": "Tên quán", "value": label}))
        info = search_match_info(rest, raw)
        if info.get("matched"):
            if label:
                scored.append((float(info.get("score", 0)), {"label": label, "type": info.get("label") or "Tên quán", "value": label}))
            for menu in rest.get("menu", [])[:2]:
                mname = menu.get("name", "")
                if raw_compact and len(raw_compact) >= 2 and raw_compact in norm_key(mname):
                    scored.append((0.92, {"label": mname, "type": "Món", "value": mname}))
                minfo = search_match_info({**rest, "name": mname, "display_name": mname}, raw)
                if minfo.get("matched"):
                    scored.append((float(minfo.get("score", 0)) * 0.95, {"label": mname, "type": "Món", "value": mname}))
    cat = search_category_hint(raw)
    if cat and is_broad_category_search(raw, cat):
        scored.append((0.93, {"label": CATEGORY_LABELS.get(cat, cat), "type": "Nhóm món", "value": CATEGORY_LABELS.get(cat, cat)}))
    for term in POPULAR_SEARCH_TERMS:
        if norm_key(raw) in norm_key(term) or norm_key(term) in norm_key(raw):
            scored.append((0.80, {"label": term, "type": "Gợi ý", "value": term}))

    seen: set[Tuple[str, str]] = set()
    for _, item in sorted(scored, key=lambda x: x[0], reverse=True):
        key = (norm_key(item["label"]), item["type"])
        if key not in seen:
            suggestions.append(item)
            seen.add(key)
        if len(suggestions) >= limit:
            break
    return suggestions[:limit]


def serialize_result(rest: Dict[str, Any]) -> Dict[str, Any]:
    rating = rest.get("rating")
    return {
        "id": rest["id"],
        "name": rest["name"],
        "display_name": rest.get("display_name", rest["name"]),
        "branch_label": rest.get("branch_label", ""),
        "branch_index": rest.get("branch_index", 1),
        "branch_total": rest.get("branch_total", 1),
        "address": rest["address"],
        "lat": rest["lat"],
        "lng": rest["lng"],
        "rating": None if rating is None or rating != rating else round(float(rating), 1),
        "price_min": rest["price_min"],
        "price_max": rest["price_max"],
        "price_avg": rest["price_avg"],
        "price_text": f"{format_vnd(rest['price_min'])}–{format_vnd(rest['price_max'])}/người" if rest["price_min"] != rest["price_max"] else f"{format_vnd(rest['price_avg'])}/người",
        "category_source": rest.get("category_source", ""),
        "categories": rest.get("categories", []),
        "primary_category": rest.get("primary_category"),
        "primary_label": CATEGORY_LABELS.get(rest.get("primary_category"), rest.get("primary_category")),
        "icon": rest.get("icon", "🍽️"),
        "image": rest.get("image"),
        "cuisines": rest.get("cuisines", []),
        "tastes": rest.get("tastes", []),
        "calories_level": rest.get("calories_level"),
        "healthy_score": rest.get("healthy_score"),
        "diet_type": rest.get("diet_type", "Mặn"),
        "protein_level": rest.get("protein_level", "Medium"),
        "portion_size": rest.get("portion_size", "Medium"),
        "opening_hours": rest.get("opening_hours", ""),
        "distance_km": round(rest.get("distance_km", 0), 2),
        "route_source": rest.get("route_source", "unknown"),
        "estimated_delivery_min": round(rest.get("estimated_delivery_min", 0), 1),
        "delivery_range": delivery_range(rest.get("estimated_delivery_min", 0)),
        "score": rest.get("final_score", 0),
        "score_percent": int(round(rest.get("final_score", 0) * 100)),
        "display_rank": rest.get("display_rank"),
        "rank_note": rest.get("rank_note", ""),
        "components": rest.get("components", {}),
        "reasons": rest.get("reasons", []),
        "search_match_score": rest.get("search_match_score", 0),
        "search_match_label": rest.get("search_match_label", ""),
        "menu": rest.get("menu", []),
    }


def recommend(payload: Dict[str, Any]) -> Dict[str, Any]:
    total_budget = float(payload.get("total_budget", 180000) or 180000)
    group_size = int(float(payload.get("group_size", 2) or 2))
    group_size = max(1, min(group_size, 10))
    budget_per_person = total_budget / group_size
    hungry_level = max(1.0, min(10.0, float(payload.get("hungry_level", 6) or 6)))
    requested_time_available = max(10.0, min(120.0, float(payload.get("time_available", 45) or 45)))
    urgency_time = urgency_adjusted_time(hungry_level, requested_time_available)
    time_available = float(urgency_time["effective_time"])
    health_goal = payload.get("health_goal", "Normal")
    diet_preference = canonical_diet_preference(payload.get("diet_preference", "Mặn"))
    rain_level = payload.get("rain_level", "khong_mua")
    user_lat = float(payload.get("user_lat", DEFAULT_USER_LAT) or DEFAULT_USER_LAT)
    user_lng = float(payload.get("user_lng", DEFAULT_USER_LNG) or DEFAULT_USER_LNG)
    selected_categories = normalize_selected_categories(
        payload.get("selected_categories", payload.get("selected_category") or payload.get("selected_meal_type") or "all")
    )
    selected_category = selected_category_label(selected_categories)
    selected_cuisine = payload.get("selected_cuisine") or "Tất cả"
    selected_tastes = payload.get("selected_tastes") or payload.get("selected_taste") or []
    if isinstance(selected_tastes, str):
        selected_tastes = [selected_tastes] if selected_tastes else []
    current_time = parse_clock(payload.get("current_time"), vietnam_now_time())
    search_query = payload.get("search_query", "")

    fuzzy = fuzzy_mode_a(budget_per_person, hungry_level, time_available, health_goal, rain_level)
    max_distance = float(fuzzy["max_distance_km"])
    choice_mode = bool(selected_categories) or (selected_cuisine != "Tất cả") or bool(selected_tastes)
    mode = "guided" if choice_mode else "smart"

    restaurants = deepcopy(load_restaurants())
    search_active = bool(norm_key(search_query))
    base_candidates = []
    for rest in restaurants:
        if rest.get("lat") is None or rest.get("lng") is None:
            continue
        is_open, minutes_close = is_open_and_minutes_until_close(rest.get("opening_hours", ""), current_time)
        if not is_open:
            continue
        search_info = search_match_info(rest, search_query)
        if not search_info.get("matched"):
            continue
        rest["search_match_score"] = search_info.get("score", 0.0)
        rest["search_match_label"] = search_info.get("label", "")
        rest["minutes_until_close"] = minutes_close
        base_candidates.append(rest)

    route_metrics = route_table(user_lat, user_lng, base_candidates)
    for rest in base_candidates:
        rest.update(route_metrics.get(str(rest["id"]), fallback_route_metric(user_lat, user_lng, rest)))

    fallback_configs = [
        {"name": "exact", "distance_extra": 0.0, "budget_mult": 1.7, "ignore_cuisine": False},
        {"name": "Nới bán kính thêm 1.5 km", "distance_extra": 1.5, "budget_mult": 1.7, "ignore_cuisine": False},
        {"name": "Nới ngân sách thêm 20%", "distance_extra": 1.5, "budget_mult": 1.7 * 1.2, "ignore_cuisine": False},
        {"name": "Bỏ lọc cuisine nhưng vẫn giữ đúng loại món", "distance_extra": 1.5, "budget_mult": 1.7 * 1.2, "ignore_cuisine": True},
    ]

    selected_config = fallback_configs[0]
    scored: List[Dict[str, Any]] = []
    used_config_index = 0

    for idx, config in enumerate(fallback_configs):
        if config["ignore_cuisine"] and selected_cuisine == "Tất cả":
            continue
        effective_max_distance = max_distance + float(config["distance_extra"])
        if mode == "guided" and selected_categories:
            allowed_categories = list(selected_categories)
        elif mode == "smart" and search_active:
            # Search is an explicit user intent, so do not let fuzzy top-categories
            # hide restaurants that match the query (for example searching pizza).
            allowed_categories = []
        elif mode == "smart":
            allowed_categories = list(fuzzy["top_categories"])
        else:
            allowed_categories = []

        candidate_scores = []
        for rest in deepcopy(base_candidates):
            if rest["distance_km"] > effective_max_distance:
                continue
            rest["estimated_delivery_min"] = delivery_estimate_minutes(rest, rest["distance_km"], current_time, rain_level)
            if rest["estimated_delivery_min"] > rest.get("minutes_until_close", 0):
                continue
            # If hunger is high, do not let a manually long requested time make
            # slow restaurants look suitable. Keep a small slack so fallback
            # results can still appear when the dataset is sparse.
            if rest["estimated_delivery_min"] > time_available + eta_slack_for_hunger(hungry_level):
                continue
            # Diet + Chay is a hard dietary constraint. Fallback may widen
            # distance/budget but must never switch to non-vegetarian rows.
            if normalize_goal(health_goal) == "diet" and diet_preference == "Chay" and rest.get("diet_type") != "Chay":
                continue
            if rest["price_avg"] > budget_per_person * float(config["budget_mult"]):
                continue
            # In guided mode, selected categories are immutable hard constraints.
            # A restaurant may match ANY selected category, but never outside them.
            if mode == "guided" and selected_categories:
                if rest.get("primary_category") not in set(selected_categories):
                    continue
            if selected_cuisine != "Tất cả" and not config["ignore_cuisine"]:
                if selected_cuisine not in rest.get("cuisines", []):
                    continue
            if mode == "smart" and allowed_categories and not category_intersects(rest, allowed_categories):
                continue

            context = {
                "mode": mode,
                "selected_category": selected_category,
                "selected_categories": selected_categories,
                "selected_cuisine": selected_cuisine,
                "selected_tastes": selected_tastes,
                "category_scores": fuzzy["category_scores"],
                "effective_max_distance": effective_max_distance,
                "budget_per_person": budget_per_person,
                "time_available": time_available,
                "health_goal": health_goal,
                "diet_preference": diet_preference,
            }
            scored_rest = score_restaurant(rest, context)
            if search_active:
                search_score = float(scored_rest.get("search_match_score", 0) or 0)
                scored_rest["components"]["search_match"] = round(search_score, 3)
                scored_rest["final_score"] = round(min(1.0, scored_rest.get("final_score", 0) + 0.08 * search_score), 4)
                if search_score >= 0.52:
                    label = scored_rest.get("search_match_label") or "từ khóa"
                    reason = f"khớp tìm kiếm ({label})"
                    if reason not in scored_rest.get("reasons", []):
                        scored_rest["reasons"] = [reason] + scored_rest.get("reasons", [])[:3]
            candidate_scores.append(scored_rest)
        scored = candidate_scores
        selected_config = config
        used_config_index = idx
        if len(scored) >= 3:
            break

    category_balance_applied = mode == "guided" and len(selected_categories) > 1
    if category_balance_applied:
        ranked = apply_guided_category_balance(scored, selected_categories, TOP_N_RESULTS)
    else:
        ranked = apply_diversity(scored, TOP_N_RESULTS)
        # Final safety ranking: normal/single-category lists should show the most
        # suitable restaurants first. If scores tie, closer restaurants come first.
        ranked = sorted(
            ranked,
            key=lambda r: (float(r.get("final_score", 0) or 0), -float(r.get("distance_km", 999) or 999)),
            reverse=True,
        )

    for display_rank, rest in enumerate(ranked, start=1):
        rest["display_rank"] = display_rank
    fallback_steps = [
        cfg["name"]
        for cfg in fallback_configs[1:used_config_index + 1]
        if not cfg["ignore_cuisine"] or selected_cuisine != "Tất cả"
    ]
    cuisine_ignored = bool(selected_config.get("ignore_cuisine")) and selected_cuisine != "Tất cả"
    warning_parts: List[str] = []
    if urgency_time.get("is_contradictory"):
        warning_parts.append(str(urgency_time.get("summary", "")))
    if normalize_goal(health_goal) == "diet" and diet_preference == "Chay" and len(ranked) < 3:
        warning_parts.append("Bạn chọn Diet + Ăn chay nên Yeppi chỉ giữ quán chay; app chỉ nới khoảng cách/ngân sách, không chuyển sang quán mặn.")
    if cuisine_ignored:
        warning_parts.append("Không có đủ quán đúng cuisine đã chọn, nên Yeppi đã bỏ lọc cuisine nhưng vẫn giữ đúng nhóm món.")
    if mode == "guided" and selected_categories:
        if len(ranked) < 3:
            warning_parts.append("Không tìm thấy đủ quán đúng nhóm món bạn chọn. App đã nới khoảng cách/ngân sách nhưng vẫn giữ đúng các nhóm món đã chọn.")
    else:
        if not (used_config_index < len(fallback_configs) - 1 and len(ranked) >= 3):
            warning_parts.append("Không tìm thấy kết quả hoàn toàn phù hợp, đây là lựa chọn gần nhất.")
    if not ranked and not (mode == "guided" and selected_categories):
        warning_parts = ["Không tìm thấy quán đang mở phù hợp với điều kiện hiện tại. Hãy tăng thời gian, nới ngân sách hoặc đổi giờ đặt món."]
    warning = " ".join(warning_parts)

    summary = explain_summary(
        mode, fuzzy, budget_per_person, hungry_level, time_available, health_goal,
        selected_categories, selected_cuisine, selected_tastes,
        cuisine_ignored=cuisine_ignored, category_balance_applied=category_balance_applied,
        requested_time_available=requested_time_available, effective_time_available=time_available,
        urgency_summary=str(urgency_time.get("summary", "")),
        diet_preference=diet_preference,
    )
    return {
        "ok": True,
        "mode": mode,
        "current_time": current_time.strftime("%H:%M"),
        "budget_per_person": round(budget_per_person),
        "requested_time_available": round(requested_time_available),
        "effective_time_available": round(time_available),
        "urgency_time": urgency_time,
        "max_distance_km": round(max_distance, 2),
        "effective_max_distance_km": round(max_distance + selected_config.get("distance_extra", 0), 2),
        "selected_categories": selected_categories,
        "diet_preference": diet_preference,
        "search_query": clean_str(search_query),
        "search_active": search_active,
        "search_suggestions": build_search_suggestions(search_query, 6) if search_active else build_search_suggestions("", 6),
        "fuzzy": {
            "top_categories": fuzzy["top_categories"],
            "category_scores": {k: round(v, 3) for k, v in fuzzy["category_scores"].items()},
            "time_degree": {k: round(v, 3) for k, v in fuzzy["time_degree"].items()},
        },
        "fallback_steps": fallback_steps,
        "warning": warning,
        "summary": summary,
        "category_balance_applied": category_balance_applied,
        "cuisine_ignored": cuisine_ignored,
        "restaurants": [serialize_result(r) for r in ranked],
        "debug": {"base_candidates": len(base_candidates), "scored_candidates": len(scored), "selected_config": selected_config["name"]},
    }


def explain_summary(
    mode: str,
    fuzzy: Dict[str, Any],
    budget_per_person: float,
    hungry: float,
    time_available: float,
    health_goal: str,
    selected_categories: Sequence[str],
    selected_cuisine: str,
    selected_tastes: Sequence[str],
    cuisine_ignored: bool = False,
    category_balance_applied: bool = False,
    requested_time_available: Optional[float] = None,
    effective_time_available: Optional[float] = None,
    urgency_summary: str = "",
    diet_preference: str = "Mặn",
) -> str:
    budget_text = format_vnd(budget_per_person)
    requested_time = int(round(requested_time_available if requested_time_available is not None else time_available))
    effective_time = int(round(effective_time_available if effective_time_available is not None else time_available))
    time_text = f"{effective_time} phút"
    if requested_time != effective_time:
        time_text += f" (thay vì {requested_time} phút do mức đói cao)"
    diet_suffix = ""
    if normalize_goal(health_goal) == "diet":
        diet_suffix = f" Chế độ Diet đang dùng lựa chọn {'Ăn chay' if diet_preference == 'Chay' else 'Ăn mặn/không giới hạn chay'}."
    if mode == "guided":
        chosen = []
        if selected_categories:
            chosen.append("nhóm món " + ", ".join(CATEGORY_LABELS.get(c, c) for c in selected_categories))
        if selected_cuisine != "Tất cả" and not cuisine_ignored:
            chosen.append(selected_cuisine)
        if selected_tastes:
            chosen.append("khẩu vị " + ", ".join(selected_tastes))
        suffix = ""
        if cuisine_ignored:
            suffix += " Cuisine đã được nới vì không đủ quán, nhưng nhóm món vẫn được giữ cứng."
        if category_balance_applied:
            suffix += " Yeppi đang cân bằng kết quả giữa các nhóm món bạn chọn để bạn dễ so sánh."
        return f"Đang ưu tiên {' · '.join(chosen) or 'lựa chọn của bạn'}, ngân sách khoảng {budget_text}/người và thời gian logic {time_text}.{diet_suffix}{suffix}"
    cats = ", ".join(CATEGORY_LABELS.get(c, c) for c in fuzzy["top_categories"])
    if budget_per_person >= 300000 and effective_time >= 60:
        return f"Budget khoảng {budget_text}/người và thời gian logic {time_text} khá thoải mái, nên Yeppi ưu tiên trải nghiệm bữa ăn đầy đủ/premium trước: {cats}. Quán quá rẻ vẫn có thể xuất hiện nhưng sẽ không được đẩy lên đầu chỉ vì gần.{diet_suffix}"
    return f"Phù hợp với ngân sách khoảng {budget_text}/người, mức đói {hungry:.0f}/10 và thời gian logic {time_text}. Hôm nay nên thử: {cats}.{diet_suffix}"

# ============================================================
# 9) APP CORE HELPERS FOR UI LAYER
# ============================================================
def meta_payload() -> Dict[str, Any]:
    """Return data used by the UI to build filters and defaults."""
    rests = load_restaurants()
    cuisines = sorted({c for r in rests for c in r.get("cuisines", []) if c})
    return {
        "categories": [{"id": "all", "label": CATEGORY_LABELS["all"], "icon": CATEGORY_ICONS["all"]}] + [
            {"id": c, "label": CATEGORY_LABELS[c], "icon": CATEGORY_ICONS[c]} for c in CATEGORIES
        ],
        "cuisines": ["Tất cả"] + cuisines,
        "tastes": ["Cay", "Mặn", "Ngọt", "Chua"],
        "health_goals": ["Diet", "Normal", "Bulking"],
        "diet_preferences": ["Mặn", "Chay"],
        "rain_levels": [
            {"id": "khong_mua", "label": "Không mưa"},
            {"id": "mua_nho", "label": "Mưa nhỏ"},
            {"id": "mua_vua", "label": "Mưa vừa"},
            {"id": "mua_lon", "label": "Mưa lớn"},
        ],
        "default_user": {"lat": DEFAULT_USER_LAT, "lng": DEFAULT_USER_LNG, "label": DEFAULT_USER_LABEL},
        "server_time": vietnam_now_hhmm(),
        "server_timezone": APP_TIMEZONE,
        "tracking_acceleration": TRACKING_ACCELERATION,
    }


def create_order(payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], int]:
    """Create an order and return (ok, payload, http_status)."""
    rid = payload.get("restaurant_id")
    rest = get_restaurant_by_id(rid)
    if not rest:
        return False, {"error": "Không tìm thấy quán"}, 404
    user_lat = float(payload.get("user_lat", DEFAULT_USER_LAT))
    user_lng = float(payload.get("user_lng", DEFAULT_USER_LNG))
    route = get_route_geometry(rest, user_lat, user_lng)
    eta_min = max(10.0, float(payload.get("estimated_delivery_min") or route.get("duration_min") or 35.0))
    order_id = "OD" + uuid.uuid4().hex[:8].upper()
    ORDERS[order_id] = {
        "id": order_id,
        "created_at": time.time(),
        "restaurant": {
            "id": rest["id"],
            "name": rest.get("display_name", rest["name"]),
            "icon": rest["icon"],
            "lat": rest["lat"],
            "lng": rest["lng"],
        },
        "items": payload.get("items", []),
        "eta_min": eta_min,
        "route": route,
        "user": {"lat": user_lat, "lng": user_lng},
    }
    return True, {"order": order_status(order_id)}, 200


def order_status(order_id: str) -> Dict[str, Any]:
    order = ORDERS[order_id]
    total_seconds = max(60.0, float(order["eta_min"]) * 60.0)
    elapsed = (time.time() - order["created_at"]) * TRACKING_ACCELERATION
    progress = clamp01(elapsed / total_seconds)
    if progress < 0.18:
        stage = 0
    elif progress < 0.48:
        stage = 1
    elif progress < 0.92:
        stage = 2
    else:
        stage = 3
    eta_left_min = max(0.0, (total_seconds - elapsed) / 60.0)
    courier = interpolate_route(order["route"]["points"], progress)
    return {
        "id": order_id,
        "restaurant": order["restaurant"],
        "items": order["items"],
        "eta_min": order["eta_min"],
        "eta_left_min": round(eta_left_min, 1),
        "progress": round(progress, 4),
        "stage_index": stage,
        "stage_label": ["Quán xác nhận", "Đang chuẩn bị", "Tài xế đang giao", "Đã giao đến bạn"][stage],
        "route": order["route"],
        "courier": {"lat": courier[0], "lng": courier[1]},
        "tracking_acceleration": TRACKING_ACCELERATION,
    }


def get_order_status(order_id: str) -> Tuple[bool, Dict[str, Any], int]:
    """Return an order status tuple for the UI layer."""
    if order_id not in ORDERS:
        return False, {"error": "Không tìm thấy đơn hàng"}, 404
    return True, {"order": order_status(order_id)}, 200

# ============================================================
# 11) TESTS
# ============================================================
def run_fuzzy_tests() -> None:
    cases = [
        ("light + very_short", dict(budget_per_person=60000, hungry_level=2, time_available=20, health_goal="Normal", rain_level="khong_mua"), {"Drinks", "Snack / Street Food"}),
        ("starving + cheap + short", dict(budget_per_person=75000, hungry_level=9, time_available=45, health_goal="Normal", rain_level="khong_mua"), {"Noodles / Soup Meal", "Fast Food Meal", "Casual Dining"}),
        ("starving + expensive + long", dict(budget_per_person=450000, hungry_level=9, time_available=105, health_goal="Normal", rain_level="khong_mua"), {"Hotpot / BBQ / Buffet", "Seafood / Specialty Meal", "Casual Dining"}),
    ]
    for name, params, expected in cases:
        out = fuzzy_mode_a(**params)
        top = set(out["top_categories"])
        assert top & expected, f"{name}: expected one of {expected}, got {out['top_categories']}"
        print(f"[OK] {name}: {out['top_categories']}")
    premium_mid = fuzzy_mode_a(1000000, 6, 70, "Normal", "khong_mua")
    assert premium_mid["top_categories"][0] in {"Hotpot / BBQ / Buffet", "Seafood / Specialty Meal"}, f"Premium 1,000,000đ + 70 phút should prioritize premium meal groups, got {premium_mid['top_categories']}"
    assert budget_fit(45000, 1000000) < budget_fit(250000, 1000000), "Cheap rice should not have the same budget fit as premium meals under 1,000,000đ/person"
    print(f"[OK] premium intent: {premium_mid['top_categories']}")
    light_out = fuzzy_mode_a(60000, 2, 20, "Normal", "khong_mua")
    assert light_out["top_categories"][:2] == ["Drinks", "Snack / Street Food"], f"Light + very short should prioritize Drinks/Snack, got {light_out['top_categories']}"
    print("[OK] light hunger UX: Drinks/Snack are top 2")
    rows = load_restaurants()
    assert rows, "Dataset loaded but empty"
    print(f"[OK] dataset loaded: {len(rows)} restaurants")

    com_tho = next((r for r in rows if "com tho" in normalize_phrase_text(r["name"])), None)
    assert com_tho and com_tho["primary_category"] == "Casual Dining", "Cơm thố must be Casual Dining"
    assert "Noodles / Soup Meal" not in com_tho["categories"], "Cơm thố must not be labeled as Noodles"
    bun_bo_items = [r for r in rows if "bun bo" in normalize_phrase_text(r["name"])]
    assert bun_bo_items and all(r["primary_category"] == "Noodles / Soup Meal" for r in bun_bo_items), "Bún bò must stay in Noodles"
    print("[OK] category sanity: Cơm thố != Noodles, Bún bò = Noodles")

    duplicate_groups = Counter(norm_key(r["name"]) for r in rows)
    duplicate_rows = [r for r in rows if duplicate_groups[norm_key(r["name"])] > 1]
    assert all(r.get("branch_label") for r in duplicate_rows), "Duplicate restaurants must show branch labels"
    print(f"[OK] duplicate branch labels: {len(duplicate_rows)} branch rows labeled")

    original_route_table = globals()["route_table"]

    def offline_route_table(user_lat: float, user_lng: float, restaurants: List[Dict[str, Any]], batch_size: int = 45) -> Dict[str, Dict[str, Any]]:
        return {str(r["id"]): fallback_route_metric(user_lat, user_lng, r) for r in restaurants}

    def assert_scores_desc(data: Dict[str, Any], label: str) -> None:
        scores = [float(r.get("score", 0) or 0) for r in data.get("restaurants", [])]
        assert scores == sorted(scores, reverse=True), f"{label}: scores are not descending: {scores}"
        print(f"[OK] {label}: scores sorted descending")

    def assert_guided_category(payload: Dict[str, Any], expected_category: str, label: str) -> Dict[str, Any]:
        return assert_guided_categories(payload, [expected_category], label)

    def assert_guided_categories(payload: Dict[str, Any], expected_categories: Sequence[str], label: str, check_scores: bool = True) -> Dict[str, Any]:
        data = recommend(payload)
        assert data["ok"], f"{label}: recommend returned not ok"
        assert data["mode"] == "guided", f"{label}: expected guided mode, got {data['mode']}"
        expected_set = set(expected_categories)
        bad = [
            (r["name"], r.get("primary_category"), r.get("categories", []))
            for r in data["restaurants"]
            if r.get("primary_category") not in expected_set
        ]
        assert not bad, f"{label}: found restaurants outside {expected_categories}: {bad}"
        print(f"[OK] {label}: {len(data['restaurants'])} restaurants keep one of {list(expected_categories)}")
        if check_scores:
            assert_scores_desc(data, label)
        return data

    globals()["route_table"] = offline_route_table
    try:
        assert_guided_category(
            {
                "selected_category": "Noodles / Soup Meal",
                "selected_cuisine": "Tất cả",
                "selected_tastes": [],
                "time_available": 20,
                "total_budget": 50000,
                "group_size": 1,
            },
            "Noodles / Soup Meal",
            "guided noodles hard filter",
        )
        assert_guided_category(
            {"selected_category": "Fast Food Meal", "selected_cuisine": "Tất cả"},
            "Fast Food Meal",
            "guided fast food hard filter",
        )
        cuisine_fallback = assert_guided_category(
            {
                "selected_category": "Noodles / Soup Meal",
                "selected_cuisine": "Cuisine khó tìm",
                "time_available": 45,
                "total_budget": 180000,
                "group_size": 2,
            },
            "Noodles / Soup Meal",
            "guided noodles cuisine fallback keeps category",
        )
        assert "Bỏ lọc cuisine nhưng vẫn giữ đúng loại món" in cuisine_fallback["fallback_steps"], "Cuisine fallback step missing"
        assert cuisine_fallback.get("cuisine_ignored") is True, "Cuisine ignored flag missing"
        assert "bỏ lọc cuisine" in cuisine_fallback.get("warning", "").lower(), "Cuisine fallback warning missing"
        multi = assert_guided_categories(
            {
                "selected_categories": ["Noodles / Soup Meal", "Casual Dining"],
                "selected_cuisine": "Tất cả",
                "time_available": 45,
                "total_budget": 180000,
                "group_size": 2,
            },
            ["Noodles / Soup Meal", "Casual Dining"],
            "guided multiple category hard filter",
            check_scores=False,
        )
        assert set(multi.get("selected_categories", [])) == {"Noodles / Soup Meal", "Casual Dining"}, "Multiple selected categories missing from response"
        assert multi.get("category_balance_applied") is True, "Multi-category balance should be applied"
        top_cats = [r.get("primary_category") for r in multi["restaurants"][:2]]
        assert {"Noodles / Soup Meal", "Casual Dining"}.issubset(set(top_cats)), f"Top results should represent both selected groups, got {top_cats}"
        print("[OK] guided multiple category balance: top results represent both selected groups")
        smart = recommend({"selected_category": "all", "time_available": 45, "total_budget": 180000, "group_size": 2})
        assert smart["ok"] and smart["mode"] == "smart" and smart["restaurants"], "smart mode should still return fuzzy recommendations"
        assert_scores_desc(smart, "smart mode fuzzy recommendations")
        print(f"[OK] smart mode fuzzy recommendations: {len(smart['restaurants'])} restaurants")

        diet_chay = recommend({
            "health_goal": "Diet",
            "diet_preference": "Chay",
            "time_available": 45,
            "total_budget": 120000,
            "group_size": 1,
        })
        assert diet_chay["ok"], "Diet + Chay should return ok"
        assert all(r.get("diet_type") == "Chay" for r in diet_chay.get("restaurants", [])), "Diet + Chay must hard-filter non-vegetarian restaurants"
        print(f"[OK] Diet + Chay hard filter: {len(diet_chay.get('restaurants', []))} vegetarian results")

        bulking_rows = [r for r in rows if r.get("protein_level") == "High" and r.get("portion_size") == "Large"]
        assert bulking_rows, "Dataset should contain high-protein large-portion rows for Bulking"
        good = goal_fit({"protein_level": "High", "portion_size": "Large", "calories_level": "High", "primary_category": "Casual Dining"}, "Bulking")
        bad = goal_fit({"protein_level": "Low", "portion_size": "Small", "calories_level": "High", "primary_category": "Drinks"}, "Bulking")
        assert good > bad, "Bulking goal_fit must prefer high protein + large portion over low-protein high-calorie drinks"
        print("[OK] Bulking goal_fit: protein/portion beats empty calories")
    finally:
        globals()["route_table"] = original_route_table


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_fuzzy_tests()
    else:
        print("fuzzy_logic_core.py contains only the core logic. Run the app with: python app_ui.py")
