# Futures Curve Analyser

A small Streamlit app that reads the crude oil futures curve, explains
what its shape is saying about the market, and tests two interesting
research findings from the finance literature against the data.


## What it does

When crude oil is bought for future delivery, there is not one single
price. There is one price for delivery next month, another for the month
after, and so on. Together they form a curve. The app does four things
with that curve:

1. **Today's curve.** Pulls the four nearest crude oil contracts from
  Yahoo Finance and draws them. Shows the current shape, the headline
  price, and the cost or gain from holding the position.
2. **How the shape has moved.** Plots the daily holding return over the
  chosen time window, and reports how often the curve switched between
  rising and falling.
3. **Price vs holding return.** Splits the cumulative return of a position
  into the part that came from the price moving and the part that came
  purely from rolling each month. Often the rolling part matters more
  than one would think.
4. **Two research ideas, tested on the data.** Each one shows a clear
  CONFIRMED or NOT CONFIRMED indicator above its chart:
   - Does the shape of the curve predict the return that follows?
     (Erb and Harvey, 2006)
   - Does low inventory pull the curve into a falling shape?
     (the theory of storage, studied by Fama and French in 1987 and by
     Gorton, Hayashi and Rouwenhorst in 2013)


## How to set up and run

**Easiest option, with nothing to install.** A fully running version of the app is
hosted on Streamlit Cloud at
**[futures-curve.streamlit.app](https://futures-curve.streamlit.app)**. Just open
the link in any web browser and use it there.

To run it on your own computer instead, follow the steps below.
You need [Python 3.9 or newer](https://www.python.org/downloads/) installed.
Open a terminal and run the four commands below, one after another. The first
two lines create a private space for the project's libraries so they do not
clash with anything else on your computer.

```bash
# 1. Download the project and enter its folder
git clone https://github.com/JAS9000/futures_curve.git
cd futures_curve

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate      # on Windows use: venv\Scripts\activate

# 3. Install the libraries the project needs
pip install -r requirements.txt

# 4. Start the app
streamlit run app.py
```

(If you downloaded the code as a ZIP from GitHub instead of cloning, skip
step 1, unzip it, and just `cd` into the unzipped folder.)

The first launch takes 30 to 60 seconds because the app downloads the
full history of crude oil contracts from Yahoo Finance. After that it
is cached. The app opens automatically in the browser at
http://localhost:8501.


### Picking a time frame

The sidebar has a date range picker. The user can choose any start and
end date in the available history, and all charts and both research
questions use that window. The default is the most recent 5 years.


## EIA API key

The main features (sections 1, 2, 3, and question 1) come from Yahoo
Finance and need no key. Only question 2 needs an EIA key, for the
weekly inventory data.

A working key is already included at `.streamlit/secrets.toml` so the app
runs fully out of the box. To use your own key, edit that file and paste
a key from https://www.eia.gov/opendata/register.php (free, takes about
a minute).


## What you can learn from it

- **How people actually invest in oil.** Almost no one stores barrels, so
  exposure comes through futures contracts that have to be rolled forward as
  they expire. The app explains both ideas in plain language.
- **Why the shape of the curve matters as much as the price.** A rising or
  falling curve signals whether supply is tight or comfortable, and it quietly
  adds to or subtracts from the return of holding a position.
- **The difference between the price and what you actually earn.** Even when
  the headline price barely moves, an oil position can still gain or lose money
  just from the shape of the curve.
- **Whether the curve can predict future returns.** Question 1 tests the
  finding of Erb and Harvey (2006) that a falling curve tends to be followed by
  stronger price returns than a rising one.
- **What drives the shape in the first place.** Question 2 tests the theory of
  storage (Gorton, Hayashi and Rouwenhorst, 2013), which says low inventories
  push the curve into a falling shape and plentiful inventories into a rising one.


## Project layout

```
futures_curve/
├── app.py                  # the Streamlit interface
├── config.py               # project constants
├── requirements.txt        # the libraries to install
├── README.md               # this file
├── .gitignore              # files Git should not track
├── .streamlit/
│   └── secrets.toml        # EIA key (free, included so it runs out of the box)
├── data/                   # parquet cache (created on first run)
└── modules/
    ├── curve.py            # maths for a single curve
    ├── analytics.py        # time-series maths and the two research questions
    ├── data_yf.py          # Yahoo Finance data client
    ├── data_eia.py         # EIA client for the inventory series
    └── charts.py           # all Plotly figures
```


## Data sources

- **Yahoo Finance.** Individual NYMEX monthly contract tickers (e.g.
 `CLN26.NYM` = July 2026 crude oil). No API key needed. Used for the
 curve history.
- **EIA Open Data API.** Weekly U.S. crude oil ending stocks (series
 `WCESTUS1`). Free API key. Used for question 2 only. The EIA used to
 publish the futures price data too, but stopped after April 2024. Its
 inventory data is still published every week.


## Notes

- Claude was used during development, to debug, correct, and refine the code.
- The "holding return" shown here is an annualised approximation from listed
 contract prices, not an exact trading result, and it ignores trading costs.
- A few HTTP 404 messages may appear in the terminal on first launch. They are
 harmless: just old contracts that Yahoo has delisted, which the app skips
 automatically.
