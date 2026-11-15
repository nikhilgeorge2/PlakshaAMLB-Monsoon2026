# HW4: Who Should Be in the Room

## 1. The business

When a company goes public, an investment bank helps it find institutional investors who might buy its shares. The bank cannot approach everyone, so it must decide which investors to contact. The same judgment serves two more jobs, advising listed companies that want new long-term shareholders and telling investors which companies fit their portfolios; all three ask how well a company suits an investor.

**The data.** Institutional investment managers with at least $100 million in reportable securities file Form 13F with the SEC within 45 days of each quarter-end, listing the stocks they hold. It is public, and these holdings provide evidence of investors' preferences: investors who hold the same stocks tend to want similar companies, though a 13F shows only what an investor holds, not everything it would like to own.

**The gap.** A 13F records stocks that already trade. A newly listed stock has no 13F holdings history; the bank has its prospectus (the S-1 or F-1 filed with the SEC) and its industry code (SIC), and nothing about who might buy it. That is the cold-start problem.

## 2. What you have to do

**Build one shared embedding space for stocks and investors.** Give every stock and every investor a vector of 16 numbers. The bank scores an investor–stock pair by the cosine similarity of their two vectors, and by nothing else; a high score means "this stock suits this investor". It uses your two tables unchanged for all three jobs: whom to call for a new listing, who might newly buy an established stock, and which companies fit an investor. How you build the vectors is your choice: collaborative filtering, matrix factorisation, pretrained language models from the approved list, or any other method the rules below permit.

**What you are given.** Data on the 200 investors and the 197 stocks, the two sets used throughout. The 200 investors (`manager_info.csv`) are the largest active stock-picking 13F filers at 31 December 2025. The 197 stocks (`companies.csv`) are the 100 stocks they held most widely plus the companies that listed in two windows:
- 100 established stocks (Microsoft, Alphabet, Meta);
- 53 companies that listed in the second half of 2025 (Figma, Klarna);
- 44 that listed between 2 March and 30 June 2026 (MiniMed, PayPay, Fervo Energy).

Nothing else is provided: no business descriptions, no industry codes, no embeddings.

**The data files.** Four comma-separated files in `data/`; a manager is an investor, and every date is YYYY-MM-DD.

`holdings.csv`, 24,126 rows; the positions the 200 investors reported in the 197 stocks, one row per investor, stock and quarter-end. A missing row means no reported position; the 2026 listings never appear.
- `quarter_end`: the date the report covers (2025-03-31, 2025-06-30, 2025-09-30, 2025-12-31)
- `manager_id`, `stock_id`: investor ids (M001, M002, …) and stock ids (S001, S002, …)
- `value_usd`: market value of the position at `quarter_end`, in US dollars; `shares`: number of shares held
- `filing_date`: the date the report became public, always later than `quarter_end` (usually within 45 days)

Example: `2025-03-31,M001,S001,260277441,693352,2025-05-15`

`filings.csv`, 798 rows; one row per report an investor filed for a 2025 quarter-end, including reports with none of the 197 stocks; no row means the investor did not file for that quarter.
- `manager_id`, `quarter_end`, `filing_date`: as in `holdings.csv`

Example: `M001,2025-03-31,2025-05-15`

`manager_info.csv`, 200 rows; one row per investor.
- `manager_id`; `sec_cik`: the SEC's filer identifier, used on EDGAR; `name`
- `total_value_usd_dec2025`, `total_positions_dec2025`: US-dollar value and number of positions of the whole 31 December 2025 report, all securities
- `positions_in_197_stocks_dec2025`: positions in the 197 stocks in that report

Example: `M001,10742,BECK MACK & OLIVER LLC,5506180680,194,50`

`companies.csv`, 197 rows; one row per stock.
- `stock_id`; `ticker`; `company_name`; `sec_cik`: the SEC's company identifier, used on EDGAR
- `status`: `established` (the 100 most widely held), `ipo_2025H2` (53 listed 1 July–31 December 2025), `ipo_2026` (44 listed 2 March–30 June 2026)
- `listing_date`: the IPO date; empty for established stocks

Example: `S110,FIG,"Figma, Inc.",1579878,ipo_2025H2,2025-07-31`

**What you have to find.** Anything beyond holdings comes from public sources you locate yourself: a company's 10-K or prospectus on EDGAR, an industry code, other data you can date and cite.

**The cutoff.** Use only holdings that were public by 2 March 2026. For a 2026 listing you may also use information about that company published before its IPO. Nothing published after the relevant date is permitted.

**What you may use.** AI assistants for code and writing: freely. Pretrained language models: only these six, loaded at the revision shown and run locally; anything else is not allowed.

| Model | Hugging Face repo | Revision (commit) |
|---|---|---|
| e5-large-v2 | `intfloat/e5-large-v2` | `b322e09026e4ea05f42beadf4d661fb4e101d311` |
| bge-base-en-v1.5 | `BAAI/bge-base-en-v1.5` | `70e8c52057794ed37381f7da00a03097927500a7` |
| all-mpnet-base-v2 | `sentence-transformers/all-mpnet-base-v2` | `5681fe04da6e48e851d5dd1af673670cdb299753` |
| all-MiniLM-L6-v2 | `sentence-transformers/all-MiniLM-L6-v2` | `7dbbc90392e2f80f3d3c277d6e90027e55de9125` |
| gte-base | `thenlper/gte-base` | `7cb59c7765dcf58720e0e63bdbbf8c10cbba8668` |
| FinBERT | `ProsusAI/finbert` | `4556d13015211d73dccd3fdd39d39232506f3e43` |

Never ask a model what it knows about a named company. SEC asks every automated request to carry a User-Agent with your own name and email address, and to stay below 10 requests per second.

**How you test.** Use the 2025 holdings and listings to test your choices before submitting. You will not receive a score before the deadline, so you must judge the evidence yourself; design your own experiments, with no extra deliverable. A historical test must use only information public at its simulated decision date, including when fitting any model or transformation.

**What you hand in.** See `SUBMISSION.md`.

## 3. How your embeddings will be evaluated

Your two tables are used unchanged. The evaluation uses holdings reported for the March and June 2026 quarter-ends; for each 2026 listing, ownership is measured at the first quarter-end on or after its listing date. Each test measures a different use of the same vectors. AUC is the chance that a randomly chosen positive outranks a randomly chosen negative, ties counting one half; 0.5 is chance.

**Test 1, finding investors for new listings.** For each of the 44 companies that listed between 2 March and 30 June 2026, rank all 200 investors by cosine; the outcome is whether each investor held that stock; the score is the mean AUC over listings with both holders and non-holders.

**Test 2, matching investors to companies.** Take two new listings, A and B, and two investors, i and j, where i held only A and j held only B; the comparison is correct when the actual matches have a higher combined cosine than the crossed ones, cos(i,A) + cos(j,B) > cos(i,B) + cos(j,A). A correct comparison earns 1, a tie 0.5, an incorrect one 0; the score is the mean over eligible comparisons.

**Test 3, finding new holdings for existing investors.** For each investor, rank the established stocks it did not hold in December 2025; the outcome is whether it held each in June 2026. AUC is computed within four groups of the 100 established stocks formed by December 2025 popularity, measured by the number of investors holding each stock; the score is the mean over groups, then over investors.

Marks: [to be set before release].

## 4. Six questions to answer

Answer each in at most 100 words, drawing on your own model and results where relevant; no additional experiments are required.

1. Test 1 uses AUC. Why does AUC depend only on the ranking and not on the values of the cosine? Suggest one statistic that is not based on ranks, say what it would tell you that AUC does not, and when it might mislead.
2. What objective did you minimise to construct your embeddings? Write it as an expression, or describe your construction rule precisely if you did not optimise one. How does your method treat a missing holding, and what might 16 dimensions lose?
3. Suppose every stock receives the same vector while investors have different vectors. Could this still do well on Test 1? What would it score on Test 2, and why? What does that say about interpreting a high Test 1 score?
4. Name two other business decisions for which your embeddings might be useful. For each, say why the representation could help and what further evidence you would want before trusting it; you need not test either.
5. The tests use reported holdings to judge predictions. Give two reasons a reported position may not reflect an investor's interest in a company, and propose one additional test or source of evidence that would help.
6. Suppose every investment bank starts using tools like yours to pick investors. Would the tools still give an advantage? How might widespread adoption change the decisions of banks, companies and investors?
