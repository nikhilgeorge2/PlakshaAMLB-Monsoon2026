# HW 3: Structured Project

*Applied ML for Business · running an ad campaign · individually or in a team of 2 or 3*

## The setting
A sports-retail marketplace sells one sponsored slot on each page view, through a **second-price auction**. You run the advertising for **RunWell Pro** running shoes. Each purchase of RunWell Pro is worth **₹1,400** to the firm.

Page views arrive one at a time, in order, and you never see the ones still to come. For each page view your bidder sees the user and context and chooses a **bid** and one of three **creatives** (A, B or C) to show if it wins. If your bid is at least the highest competing bid, you win the slot, the creative is shown, and you pay the **competing bid, not your own**; otherwise you pay nothing. A bid of 0 is allowed. You have a fixed **budget** for each campaign and cannot win an auction whose price exceeds your remaining budget.

**Your objective is the firm's final expected profit from the campaign: its contribution from purchases of RunWell Pro, less what you spend on advertising.**

## The data
`historical_log.csv` records 150,000 auctions of the previous campaign, one row per auction, in the order they happened.

| columns | meaning |
|---|---|
| `interest, revisit, device, os, age_bracket, city_tier, hour, referral, session_depth, day_of_week` | what is known about the user and context when the auction opens |
| `prior_bid` | what the previous campaign bid (every auction) |
| `market_price` | the price paid: the highest competing bid, recorded **only for auctions the previous campaign won**; blank for lost auctions |
| `won` | 1 if `prior_bid >= market_price` |
| `creative` | won auctions only: `psa`, `A`, `B` or `C` |
| `clicked`, `converted` | won auctions only; `converted` is whether the user bought RunWell Pro |

The previous campaign set its bids from the recorded user and context features plus random variation. **Among the auctions the previous campaign won, PSA, A, B, and C were assigned uniformly at random, independently of the recorded user and context features.** `psa` is a neutral public-service announcement, unrelated to RunWell Pro; the previous campaign paid for those impressions like any other. PSA works as a control group: its conversion rate is what users do without your ad. For a lost auction neither the price nor the outcome was observed: you know only that the price exceeded `prior_bid`. The blanks are deliberate, and your bidder must handle them. Your bidder will bid differently from the previous campaign, so it will win different auctions, and the mix of users in the hidden campaigns may differ modestly from the log.

## What you submit
Two team files and one individual file:

1. **`<rollnos>.py`** (team bidder), with a `Bidder` class (see `bidder_template.py`), described below.
2. **`<rollnos>.md`** (team write-up): you built this ad bidder; write a blog post of **at most 800 words** explaining the key aspects of its design to a broad audience: engineers, leadership, people outside the firm. It should convey the thoughtfulness behind the design.
3. **`<rollno>_contribution.md`** (individual: every student submits their own, including students working alone): two lines on what each person did, and your judgment of each person's overall contribution as a percentage, adding to 100. For example: "Emily built the value model and the validation. Greg built the budget rule and wrote the post. Contribution: Emily 55, Greg 45." If you worked alone, say so in one line.

Name the two team files with the roll numbers of everyone in the team, joined by underscores: `2301001_2301007.py` and `2301001_2301007.md` (alone: your own roll number). Register your team (or that you are working alone) on the course sheet by **Friday 16 October**; how to register will be announced. Submit one set of team files per team. There is one submission and no resubmission. The bidder deadline and how to submit will be announced.

The bidder:

- `fit(log)` is called once with the log.
- `start_campaign(budget, n_impressions)` is called at the start of each campaign and tells you its total budget (₹) and the number of auctions (impressions) that will arrive.
- `bid(context)` returns `(bid, creative)`. `context` holds the ten features plus `budget_remaining` and `impressions_remaining`; the competing price is not given.
- `update(outcome)` follows every auction: `{'won': True, 'price', 'clicked', 'converted'}` or `{'won': False}`. Prices and budgets are in ₹.

Your bidder will be run on hidden campaigns of three sizes: roughly 2,000, 5,000 and 10,000 auctions, on traffic you have not seen. At the start of each campaign it is told how many auctions to expect and how much money it has: sometimes only a fraction of what it would cost to buy every worthwhile auction, sometimes more than enough. At every auction it is told what is left.

The budget is one pot of money. You can bid any amount on any auction, and once the pot is empty you win nothing more. Money left over is neither rewarded nor penalised.

So build a bidder that copes with any size and any budget, not one tuned to a single setting. The world it faces is much like the world in the log, apart from the differences mentioned above.

Every campaign starts from a fresh copy of your bidder exactly as `fit` left it, so whatever it learns during one campaign is thrown away before the next. Your score is the expected profit per 1,000 auctions, averaged over the hidden campaigns. It is computed from the true purchase probabilities of the simulated users, so luck in individual outcomes does not decide it.

**Marks.** The assignment is marked out of 100: 80% for the bidder and 20% for the write-up. The bidder is graded on the lift it earns on the hidden campaigns: the profit it adds over not advertising.

**Teams.** You may work alone or in a team of 2 or 3, and the standard is the same for everyone. The mark out of 100 is then multiplied by a team-size factor: 3 students ×1.00, 2 students ×1.10, 1 student ×1.20 (a mark of 85 becomes 85, 93.5 or 102). Marks above 100 count.

**Limits.** `fit`: 60 s of CPU. `bid` + `update`: 2.5 ms of CPU per auction on average, 50 ms hard deadline. 1 GB of memory. Python with numpy, pandas, scipy and scikit-learn, plus these standard-library modules: `math`, `random`, `collections`, `itertools`, `functools`, `typing`, `dataclasses`, `time`, `copy`, `heapq`, `bisect`, `statistics`, `warnings`; any other import is rejected. No network and no data beyond the log. Fix your random seeds. The limits are measured on the grading machine, which may be faster or slower than yours: leave a margin. A campaign in which your bidder breaks a limit or errors repeatedly scores 0 for that campaign.

**Environment.** `requirements.txt` pins the exact package versions the grader uses. Install them (`pip install -r requirements.txt`) and develop and check your bidder in that environment, so that what runs for you also runs in grading.

`python check_submission.py <rollnos>.py <rollnos>.md` confirms that your file runs within these limits. It does not report a score and says nothing about how good the bidder is.
