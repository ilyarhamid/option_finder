"""
Scrape options information from Yahoo Finance
and recommend option contracts according to the inputs
"""

import yfinance as yf
import pandas as pd
from pandas.tseries.offsets import Week
from datetime import datetime
import numpy as np
import mibian


input_dict = {
    "Ticker": "WMT",  # Ticker of underlying asset;
    "Target Price": 135.0,  # Estimated future price
    "Target Date": "2020-08-21",  # Estimated time when the price hit target price
    "Maximum Risk": 5000.0,
    "Contract Number": 5,  # Number of different options contracts to be recommended
    "Interest Rate": 1.0,  # interest rate used for delta calculation
    "Rank": "Delta",  # 'Return' or 'Delta'
    "Delta Range": (0.4, 0.5)
}


def get_options(ticker, exp_date, typ):
    """ Scrape options information from Yahoo Finance."""
    std_date = datetime(2020, 8, 14)
    std_sec = 1597363200
    dt = exp_date - std_date
    target_sec = std_sec + int(dt.total_seconds())
    # An URL for specific asset at a expiration date is created.
    url = f"finance.yahoo.com/quote/{ticker}/options?date={target_sec}&p={ticker}"
    # Tables on the page is read in to a list. The first on is call options and the second one is put options.
    ls = pd.read_html("https://" + url)
    if typ == "Call":
        df = ls[0][["Strike", "Ask", "Implied Volatility"]]  # Take Strike price and ask price.
        ret_df = df.copy()
        # Expiration date column is added
        ret_df["Expiration Date"] = pd.Series([exp_date] * len(df), index=df.index)
        return ret_df
    elif typ == "Put":
        df = ls[1][["Strike", "Ask", "Implied Volatility"]]  # Take Strike price and ask price.
        ret_df = df.copy()
        # Expiration date column is added
        ret_df["Expiration Date"] = pd.Series([exp_date] * len(df), index=df.index)
        return ret_df
    else:
        raise ValueError


def info_process(dic, contract_type):
    """Get options according to the inputs."""
    target_date = datetime.strptime(dic["Target Date"], "%Y-%m-%d")  # Target date to datetime object
    if target_date.isoweekday() != 5:  # The target date is moved to next Friday if it's not.
        target_date = target_date + Week(weekday=4)
    ls = []
    while True:  # Use a loop to store options on different target dates to a list.
        if len(ls) == 3:  # Look into 3 available target dates in the future.
            break
        try:
            # If options available on a target date, append the dataframe to the list
            # then move the target date to next Friday
            ls.append(get_options(dic["Ticker"], target_date, contract_type))
            target_date = target_date + Week(weekday=4)
        except:
            # If there is no options available, directly move to next Friday.
            target_date = target_date + Week(weekday=4)
    df_options = pd.concat(ls)  # Concatenate the dataframe into one.
    df_options.columns = ["Strike", "Price", "Volatility", "Expiration Date"]  # Change column names
    return df_options


def calculate_delta(dic, df, contract_type, curr_price):
    df["Remaining Days"] = df["Expiration Date"] - datetime.now()
    if contract_type == "Call":
        delta_ls = [
            mibian.BS(
                [curr_price, row["Strike"], dic["Interest Rate"], row["Remaining Days"].days],
                row["Volatility"][:-1]
            ) .callDelta
            for index, row in df.iterrows()
        ]
    elif contract_type == "Put":
        delta_ls = [
            mibian.BS(
                [curr_price, row["Strike"], dic["Interest Rate"], row["Remaining Days"].days],
                row["Volatility"][:-1]
            ).putDelta
            for index, row in df.iterrows()
        ]
    else:
        raise ValueError
    df["Delta"] = pd.Series(delta_ls, index=df.index)
    return df


def recommend(dic, contract_type, curr_price):
    """Calculate further information and recommend options."""
    df = info_process(dic, contract_type)
    if dic["Rank"] == "Delta":
        df = calculate_delta(dic, df, contract_type, curr_price)
    # Calculate maximum number can be bought for each contract.
    df["Number"] = np.floor(dic["Maximum Risk"] * 0.01 / df["Price"])
    df = df[df["Number"] != 0]  # Remove the contracts can not be bought.
    df["Entry Cost"] = df["Number"] * df["Price"] * 100.0  # Calculate the entry cost.
    if contract_type == "Call":
        df = df[df["Strike"] < dic["Target Price"]]  # Remove "useless" options
        # Calculate estimated return as percentage
        df["Estimated Return"] = 100.0 * (
                    df["Number"] * 100.0 * (dic["Target Price"] - df["Strike"]) - df["Entry Cost"]) / df["Entry Cost"]
    if contract_type == "Put":
        df = df[df["Strike"] > dic["Target Price"]]  # Remove "useless" options
        # Calculate estimated return as percentage
        df["Estimated Return"] = 100.0 * (
                    df["Number"] * 100.0 * (df["Strike"] - dic["Target Price"]) - df["Entry Cost"]) / df["Entry Cost"]

    df = round(df, 2)  # Round up the numbers
    if dic["Rank"] == "Return":
        # Sort the dataframe according to the estimated return.
        df = df.sort_values(by="Estimated Return", ascending=False)
    elif dic["Rank"] == "Delta":
        df = df[df["Delta"] >= dic["Delta Range"][0]]
        df = df[df["Delta"] <= dic["Delta Range"][1]]
        if len(df) == 0:
            return pd.DataFrame()
        if contract_type == "Call":
            df = df.sort_values(by="Delta", ascending=False)
        if contract_type == "Put":
            df = df.sort_values(by="Delta")
    return df[:dic["Contract Number"]]  # Return the top options


def main(dic):
    current_price = yf.Ticker(dic["Ticker"]).history("1d")["Close"].iloc[-1]  # Get current price from Yahoo Finance.
    if dic["Target Price"] > current_price:  # Decide the contract type according to the target and current price.
        contract_type = "Call"
    else:
        contract_type = "Put"
    df = recommend(dic, contract_type, current_price)  # Get recommended options.
    if len(df) == 0:
        print("No option found!")
    # Text output
    for index, row in df.iterrows():
        print("Long %s: Buy %s x %s $%s %s @ $%s" % (contract_type,
                                                     row["Number"],
                                                     row["Expiration Date"].strftime("%d %b"),
                                                     row["Strike"],
                                                     contract_type,
                                                     row["Price"]))
        if dic["Rank"] == "Delta":
            print("Delta: %s" % row["Delta"])
        print("Entry cost: $%s" % row["Entry Cost"])
        print("Maximum risk: $%s" % row["Entry Cost"])
        print("Est. return at target price: $%s (%s%s)" % (round(row["Estimated Return"] * row["Entry Cost"] * 0.01, 1),
                                                           row["Estimated Return"],
                                                           "%"))
        print("=" * 100)


if __name__ == '__main__':
    main(input_dict)
