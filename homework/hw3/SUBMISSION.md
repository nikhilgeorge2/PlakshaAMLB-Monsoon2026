# HW 3 Structured Project: submission

**Files you have:** `HW3_handout.md`, `historical_log.csv`, `bidder_template.py`, `check_submission.py`, `requirements.txt`.

**Environment.** Python 3.11-3.13. `pip install -r requirements.txt` builds the grader's stack (numpy 2.3.5, pandas 2.3.3, scipy 1.16.3, scikit-learn 1.8.0); run the check inside it. The usual causes of "works locally, fails in grading" are arguments removed from newer libraries (for example `OneHotEncoder(sparse=...)` is now `sparse_output=...`) and pandas chained assignment (use `df.loc[mask, col] = v`).

**Check.** `python check_submission.py 2301001_2301007.py` (run it from the folder that holds `historical_log.csv`, or give its path as the last argument). It replays a sample of the log through your bidder to test that it runs, and must print `OK`; a `WARN` line means your bidder is over a limit on your machine: it may be cut off in grading, so make it lighter; only `FAIL` blocks submission. It reports no profit, and the outcomes it feeds your bidder are random, so it tells you the bidder runs within the limits, not whether it is good. It does not look at your write-up.

**First:** register your team (or that you work alone) on the course sheet by Friday 16 October.

**File names:** the roll numbers of everyone in the team joined by underscores, in any order, at most three, the same for both files: `2301001_2301007.py` and `2301001_2301007.md` (alone: `2301001.py`, `2301001.md`). Write the roll numbers and names in a comment at the top of the .py and the first line of the .md.

**Hand in, per submission** (individual or team of 2-3)
- the `.py`: one file, at most 1 MB, imports limited to numpy, pandas, scipy, scikit-learn and the standard-library modules listed in the handout, no file or network access, deterministic (seed anything random). All names in a comment at the top.
- the `.md`: at most 800 words (whitespace-separated words, code included), a blog post for a broad audience (engineers, leadership, people outside the firm) explaining the key aspects of your bidder's design and the thoughtfulness behind it.

**Hand in, per student (everyone, including students working alone)**
- `<rollno>_contribution.md` (your own roll number): two lines on what each person did, and your judgment of each person's overall contribution as a percentage, adding to 100, for example "Emily 55, Greg 45" (alone: say so in one line).
