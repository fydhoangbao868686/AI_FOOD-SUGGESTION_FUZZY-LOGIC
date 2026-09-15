# Yeppi — Smart Food & Restaurant Recommendations

Yeppi is a Vietnamese web application that helps users choose food and restaurants based on their budget, hunger level, available time, dietary goals, weather conditions, and preferences. It combines a rule-based fuzzy recommendation engine with restaurant search, map routes, estimated delivery times, and a simulated ordering experience.

Built with **Python, Flask, pandas, and JavaScript**, the project demonstrates explainable food recommendations using an Excel restaurant dataset. No trained model weights or AI API key are required.

## Features

- **Context-aware recommendations:** use total budget, group size, hunger, waiting time, health goals, and rain conditions to rank restaurants.
- **Preference-based selection:** narrow recommendations by food categories, cuisine, and taste; search by restaurant or food-related keywords.
- **Explainable results:** display suitability scores, recommendation reasons, estimated delivery ranges, and fallback notices.
- **Dietary preferences:** incorporate calorie, protein, portion, and health labels; the Diet + Chay combination retains vegetarian restaurants.
- **Maps and routes:** display restaurants and delivery routes using Leaflet, OpenStreetMap, and OSRM.
- **Location selection:** start from UEH Campus B in Ho Chi Minh City or request the user's browser location.
- **Ordering demo:** browse generated menu items, use the cart and checkout interface, and follow simulated delivery progress.

## How recommendations work

1. Calculate the budget per person and interpret hunger, time, health, and rain inputs using fuzzy membership functions and rules.
2. Use smart mode for general recommendations, or guided mode when categories, cuisine, or tastes are selected.
3. Filter candidates using location, opening hours, search terms, distance, budget, delivery estimates, and applicable preferences.
4. Rank candidates using weighted suitability components and return up to eight results, with diversity or category balancing where applicable.
5. If too few candidates remain, expand distance and budget tolerance and, if needed, relax cuisine matching. Selected categories in guided mode remain constraints.

Budget is a ranking target with tolerance, not a strict spending ceiling. Weather is supplied by the user; the app does not fetch a live weather forecast. The engine uses explicit rules and scoring rather than a trained neural network.

## Source files

| File | Purpose |
|---|---|
| `app_ui.py` | Flask entry point, API routes, and embedded HTML/CSS/JavaScript interface. |
| `fuzzy_logic_core.py` | Dataset loading, fuzzy rules, ranking, routing, demo order state, and built-in checks. |
| `full_app.py` | Alternative combined implementation containing both core logic and web interface. |
| `data_restaurants.xlsx` | Restaurant dataset used by default. |
| `requirements.txt` | Python dependencies. |
| `static/yeppi-logo-icon.png` | Local Yeppi logo asset. |
| `README.md` | Project documentation. |

Use **`python app_ui.py`** to launch the modular version. This source package does not contain an `app.py` file. To run the combined version instead, use `python full_app.py`; run only one version on the same port at a time.

## Run locally

Use a Python installation with `pip` and virtual-environment support. The supplied package includes Python 3.13 cache files, but does not declare or verify a supported Python version range.

Extract the source package and open a terminal **inside `Yeppi_FoodsuggestionApp`**, where `app_ui.py` and `requirements.txt` are located.

### Windows — Command Prompt

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app_ui.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app_ui.py
```

Open [Yeppi on localhost](http://127.0.0.1:5000) in your browser. Keep the terminal running while using the app; press `Ctrl+C` to stop it.

The dependencies declared in the supplied file are Flask, pandas, openpyxl, requests, and tzdata. No separate database server is needed.

## Run in GitHub Codespaces

After opening the repository in Codespaces, first extract the source ZIP if the repository contains only archives. In the terminal, change into the directory containing `app_ui.py`, then run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app_ui.py
```

Open the **Ports** tab and open port **5000** in the browser. If it is absent, add port `5000` manually. Keep its visibility private for development. Use the forwarded browser URL rather than typing your own machine's localhost address. See [GitHub's port-forwarding guide](https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace).

The supplied source has no dev-container configuration, so dependency installation is manual. Yeppi is a browser-based Flask app and does not need a remote desktop or VNC.

## Using the app

1. Confirm your delivery location or allow browser geolocation.
2. Enter your budget, group size, hunger level, available time, health goal, and rain condition.
3. Optionally select categories, cuisine, tastes, or a search term.
4. Request recommendations and inspect the reasons, delivery estimates, and map.
5. Open a restaurant, add demo menu items to the cart, and proceed through the simulated order flow.
6. Watch the delivery marker and order status progress on the tracking view.

## Dataset

`data_restaurants.xlsx` contains **129 non-empty restaurant records** in the `Restaurants` worksheet. It provides identifiers, names, coordinates, ratings, prices, categories, cuisines, tastes, opening hours, and dietary/nutrition labels.

The loader removes fully empty rows and columns. Required fields are restaurant name, category, price, and either combined coordinates or separate latitude/longitude columns. Accepted column names are defined in `COLUMN_ALIASES` in `fuzzy_logic_core.py`.

Keep the workbook beside the Python files. The loader checks `data_restaurants.xlsx` first, followed by alternative dataset names defined in `DATASET_CANDIDATES`. Menu items and their prices are generated from category templates and restaurant price data; they are not verified live restaurant menus.

## Configuration

These optional environment variables are read directly by the application:

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `5000` | Web-server port. |
| `OSRM_BASE_URL` | `https://router.project-osrm.org` | Routing service endpoint. |
| `OSRM_TIMEOUT` | `7` | Routing request timeout in seconds. |
| `TRACKING_ACCELERATION` | `12` | Simulated delivery speed multiplier; minimum value is 1. |

For example, to run tracking at normal clock speed in Windows CMD:

```bat
set TRACKING_ACCELERATION=1
python app_ui.py
```

On macOS / Linux:

```bash
TRACKING_ACCELERATION=1 python app_ui.py
```

Changing this value changes simulation speed; it does not enable live driver tracking. The code does not automatically load a `.env` file.

## Built-in checks

From the source directory, run:

```bash
python fuzzy_logic_core.py --test
```

These checks cover fuzzy-rule scenarios, dataset loading, category handling, branch labels, ranking, and dietary behavior. Routing is replaced with local distance estimates for recommendation checks. The combined implementation also accepts `python full_app.py --test`.

## Limitations and troubleshooting

- **Demo ordering:** no real payment processing, restaurant dispatch, or driver GPS integration is implemented. Orders are held in process memory and disappear when the server restarts.
- **Development server:** direct launch enables Flask debug mode. Public production hosting needs a separate deployment configuration and review of authentication and request validation.
- **External resources:** maps, fonts, illustrative food photos, and road routing depend on network services. If OSRM requests fail, the backend estimates road distance using Haversine distance multiplied by 1.32; map tiles and other browser assets still require connectivity.
- **No recommendations:** check location, opening hours, time, budget, and filters. Results depend on the supplied dataset and the current Vietnam time unless an explicit time is passed to the recommendation API.
- **Dataset missing:** keep `data_restaurants.xlsx` in the same folder as the source files; do not follow older error messages referring to `app.py`.
- **Port occupied:** stop the other instance or change `PORT` before launching.
- **Evaluation:** the archives do not supply a measured recommendation-accuracy benchmark. Nutrition labels, generated menus, prices, and delivery times should be treated as demonstration data or estimates.

This README was checked against the supplied code, archive contents, and workbook. The application and its built-in test suite were not executed as part of this documentation update.
