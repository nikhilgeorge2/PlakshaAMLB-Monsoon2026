"""check_tables.py: format check for your two vector tables. It checks format only, not quality.

Usage (from the folder that holds data/):  python check_tables.py stocks.csv managers.csv
Prints OK, or the first problems found. Needs numpy and pandas.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
K = 16


def check(path, id_col, ids, label):
    problems = []
    if not os.path.exists(path):
        return [f"{label}: file not found: {path}"]
    try:
        df = pd.read_csv(path, dtype={id_col: str}, encoding="utf-8")
    except Exception as e:  # unreadable file
        return [f"{label}: cannot read as CSV ({e})"]
    want = [id_col] + [f"d{j}" for j in range(1, K + 1)]
    if list(df.columns) != want:
        return [f"{label}: header must be exactly {','.join(want)}; found {','.join(map(str, df.columns))}"]
    ids_in = df[id_col].tolist()
    dup = sorted({i for i in ids_in if ids_in.count(i) > 1})
    if dup:
        problems.append(f"{label}: repeated ids: {dup[:5]}")
    missing = sorted(set(ids) - set(ids_in))
    extra = sorted(set(ids_in) - set(ids))
    if missing:
        problems.append(f"{label}: {len(missing)} ids missing, e.g. {missing[:5]}")
    if extra:
        problems.append(f"{label}: {len(extra)} unknown ids, e.g. {extra[:5]}")
    vals = df[want[1:]].apply(pd.to_numeric, errors="coerce")
    bad = ~np.isfinite(vals.to_numpy(dtype=float))
    if bad.any():
        rows = df[id_col][bad.any(axis=1)].tolist()
        problems.append(f"{label}: blank, non-numeric or non-finite values in {len(rows)} rows, e.g. {rows[:5]}")
    else:
        zero = df[id_col][(np.abs(vals.to_numpy(dtype=float)).sum(axis=1) == 0)].tolist()
        if zero:
            problems.append(f"{label}: all-zero rows (cosine is undefined), e.g. {zero[:5]}")
    return problems


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    stocks = pd.read_csv(os.path.join(HERE, "data", "companies.csv"), dtype=str)["stock_id"].tolist()
    investors = pd.read_csv(os.path.join(HERE, "data", "manager_info.csv"), dtype=str)["manager_id"].tolist()
    problems = check(sys.argv[1], "stock_id", stocks, "stocks.csv") + check(sys.argv[2], "manager_id", investors, "managers.csv")
    if problems:
        print("PROBLEMS:")
        for p in problems[:10]:
            print(" -", p)
        sys.exit(1)
    print(f"OK: {len(stocks)} stocks and {len(investors)} investors, {K} numbers each.")


if __name__ == "__main__":
    main()
