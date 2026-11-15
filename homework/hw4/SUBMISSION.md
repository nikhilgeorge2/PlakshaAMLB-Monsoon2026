# HW 4 submission

**Files you have:** `HW4_handout.md` and the four files in `data/`.

- Moodle: `stocks.csv`, `managers.csv`, `design.md` and `answers.md`, with the GitHub link and commit hash in the text box.
- GitHub: `make_vectors.py`, which must reproduce your two tables offline from the supplied files and `external.parquet`, with numerical differences no greater than 1e-5 (fix every random seed), and `external.parquet`, the one extra data file, a parquet file below 100 MB holding whatever you brought in from outside (text, industry codes, model outputs, other features). It is the only data file allowed in the repository besides your two tables; omit it if you bring nothing.
- `design.md`: at most 800 words on the logic of your design, from data and cutoffs to how listings and investors get their vectors and how you reached 16 dimensions.
- `answers.md`: your answers to the six questions in `HW4_handout.md`, at most 100 words each.

**Format of the two tables.** Comma-separated UTF-8 with a header row.
- `stocks.csv`: `stock_id,d1,d2,...,d16`, one row for each of the 197 stocks in `companies.csv`.
- `managers.csv`: `manager_id,d1,d2,...,d16`, one row for each of the 200 investors in `manager_info.csv`.
- Each id appears exactly once; row order does not matter; every value is a finite number with no blanks; no row is all zeros (cosine is undefined for a zero vector).

The header of `stocks.csv` is literally

```
stock_id,d1,d2,d3,d4,d5,d6,d7,d8,d9,d10,d11,d12,d13,d14,d15,d16
```

and that of `managers.csv` is the same with `manager_id` first; each row then holds the id and sixteen numbers.

The tables you upload to Moodle are the ones scored; the repository only has to reproduce them.
