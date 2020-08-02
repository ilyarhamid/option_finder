import yfinance as yf
import pandas as pd
from pandas.tseries.offsets import Week
from datetime import datetime
import numpy as np


def get_options(ticker, exp_date, typ):
    std_date = datetime(2020, 8, 14)
    std_sec = 1597363200
    dt = exp_date - std_date
    target_sec = std_sec + int(dt.total_seconds())
    url = f"finance.yahoo.com/quote/UAL/options?date={target_sec}&p={ticker}"
    ls = pd.read_html("https://" + url)
    if typ == "Call":
        df = ls[0][["Strike", "Ask"]]
        ret_df = df.copy()
        ret_df["Expiration Date"] = pd.Series([exp_date] * len(df), index=df.index)
        return ret_df
    elif typ == "Put":
        df = ls[1][["Strike", "Ask"]]
        ret_df = df.copy()
        ret_df["Expiration Date"] = pd.Series([exp_date] * len(df), index=df.index)
        return ret_df
    else:
        raise ValueError


def info_process(dic, contract_type):
    target_date = datetime.strptime(dic["Target Date"], "%Y-%m-%d")
    if target_date.isoweekday() != 5:
        target_date = target_date + Week(weekday=4)
    ls = []
    while True:
        if len(ls) == 3:
            break
        try:
            ls.append(get_options(dic["Ticker"], target_date, contract_type))
            target_date = target_date + Week(weekday=4)
        except:
            target_date = target_date + Week(weekday=4)
    df_options = pd.concat(ls)
    df_options.columns = ["Strike", "Price", "Expiration Date"]
    return df_options


def recommend(dic, contract_type):
    df = info_process(dic, contract_type)
    df["Number"] = np.floor(dic["Maximum Risk"] * 0.01 / df["Price"])
    df = df[df["Number"] != 0]
    df["Entry Cost"] = df["Number"] * df["Price"] * 100.0
    if contract_type == "Call":
        df = df[df["Strike"] < dic["Target Price"]]
        df["Estimated Return"] = 100.0 * (
                    df["Number"] * 100.0 * (dic["Target Price"] - df["Strike"]) - df["Entry Cost"]) / df["Entry Cost"]
    if contract_type == "Put":
        df = df[df["Strike"] > dic["Target Price"]]
        df["Estimated Return"] = 100.0 * (
                    df["Number"] * 100.0 * (df["Strike"] - dic["Target Price"]) - df["Entry Cost"]) / df["Entry Cost"]

    df = round(df, 2)
    df = df.sort_values(by="Estimated Return", ascending=False)
    return df[:dic["Contract Number"]]


def text_output(dic):
    current_price = yf.Ticker(dic["Ticker"]).history("1d")["Close"].iloc[-1]
    if dic["Target Price"] > current_price:
        contract_type = "Call"
    else:
        contract_type = "Put"
    df = recommend(dic, contract_type)
    for index, row in df.iterrows():
        print("Long %s: Buy %s x %s $%s %s @ $%s" % (contract_type,
                                                     row["Number"],
                                                     row["Expiration Date"],
                                                     row["Strike"],
                                                     contract_type,
                                                     row["Price"]))
        print("Entry cost: $%s (debit)" % row["Entry Cost"])
        print("Maximum risk: $%s" % row["Entry Cost"])
        print("Est. return at target price: $%s (%s%s)" % (round(row["Estimated Return"] * row["Entry Cost"] * 0.01, 1),
                                                           row["Estimated Return"],
                                                           "%"))
        print("=" * 100)
