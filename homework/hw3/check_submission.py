"""
Checks that your bidder file follows the interface and the technical limits. It reports NO profit.
It runs your bidder in the same child-process protocol the grader uses, so passing here means it runs in grading.

It replays a sample of 1,000 auctions drawn from historical_log.csv through your bidder: one campaign with a middle
budget, one with a budget that runs out, and a repeat of the first. The prices it uses for lost auctions are stand-ins
and the outcomes it sends to update() are random, so the replay only tests that your bidder runs, not how well it does.

Usage:  python check_submission.py bidder.py [writeup.md] [historical_log.csv]
"""
import sys
if sys.version_info < (3, 9):
    sys.exit('HW3 check needs Python 3.9 or newer (3.11-3.13 recommended): see requirements.txt')
try:
    import numpy, pandas, scipy, sklearn
except ImportError as e:
    sys.exit('Missing package %r. Install the course environment first: pip install -r requirements.txt' % (e.name,))
import ast
import builtins
import copy
import importlib.util
import json
import os
import queue
import random
import shutil
import subprocess
import sys
import threading
import time

import numpy as np
import pandas as pd

# ====================================================================================== harness


CONTRACT = dict(
    fit_cpu_s=60.0,          # fit(): CPU seconds, single thread
    fit_wall_s=120.0,        # parent kills the child if fit takes longer in wall time
    deadline_s=0.05,         # per bid()+update(): wall-clock; a miss loses the auction
    p99_cpu_ms=5.0,          # per bid()+update(): 99th percentile CPU ms
    mean_cpu_ms=2.5,         # mean CPU ms per impression; total cap = mean_cpu_ms * n_impressions
    rss_mb=1024,             # peak resident memory of the child
    err_frac=0.01,           # more than 1% bid/update errors aborts the campaign
    miss_frac=0.05,          # more than 5% deadline misses aborts the campaign
    max_file_mb=1.0,         # size of bidder.py
)
ALLOWED = {'numpy', 'pandas', 'scipy', 'sklearn',
           '__future__', 'math', 'random', 'collections', 'itertools', 'functools', 'typing',
           'dataclasses', 'time', 'copy', 'heapq', 'bisect', 'statistics', 'warnings'}
THREAD_ENV = {k: '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                               'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS')}
THREAD_ENV['PYTHONHASHSEED'] = '0'
THREAD_ENV['PYTHONDONTWRITEBYTECODE'] = '1'
PRODUCT = {'name': 'RunWell Pro', 'category': 'athletic_footwear', 'value': 1400}
CHILD = os.path.abspath(__file__)          # this file doubles as the child process (run with --child)


class HarnessAbort(BaseException):
    """Campaign aborted (memory, too many errors, hang, crash). BaseException so a
    simulator's `except Exception` cannot swallow it."""


def sandbox_available():
    return sys.platform == 'darwin' and shutil.which('sandbox-exec') is not None


def sandbox_profile(student_path, log_path, deny_roots=()):
    """macOS sandbox profile (SBPL; the last matching rule wins): no network, no writes, no reads of the home directory or of
    `deny_roots` except the files and the Python environment the bidder needs."""
    def q(p):
        return '"' + os.path.abspath(p).replace('\\', '\\\\').replace('"', '\\"') + '"'
    home = os.path.expanduser('~')
    prefixes = {os.path.realpath(p) for p in (sys.prefix, sys.base_prefix, sys.exec_prefix)}
    # the interpreter's own tree only: never the parent's sys.path entries (they include the instructor directory)
    allow_dirs = prefixes
    allow_files = {student_path, log_path, CHILD}
    rules = ['(version 1)', '(allow default)', '(deny network*)', '(deny file-write*)',
             '(allow file-write* (literal "/dev/null"))',
             f'(deny file-read* (subpath {q(home)}))']
    rules += [f'(deny file-read* (subpath {q(r)}))' for r in deny_roots]
    rules += [f'(allow file-read* (subpath {q(d)}))' for d in sorted(allow_dirs)]
    rules += [f'(allow file-read* (literal {q(f)}))' for f in sorted(allow_files)]
    return '\n'.join(rules)


class PipeConn:
    """Newline-delimited JSON over a subprocess's stdin/stdout with poll(timeout). A reader thread feeds a queue, so it works on
    Windows as well as macOS/Linux."""

    def __init__(self, proc):
        self.proc, self.q, self.item, self.eof = proc, queue.Queue(), None, False
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            for line in iter(self.proc.stdout.readline, b''):
                self.q.put(line)
        except Exception:
            pass
        finally:
            self.q.put(None)

    def send(self, obj):
        try:
            self.proc.stdin.write((json.dumps(obj, allow_nan=False) + '\n').encode())
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            raise EOFError

    def poll(self, timeout):
        if self.item is not None or self.eof:
            return True
        try:
            self.item = self.q.get(timeout=max(timeout, 0))
        except queue.Empty:
            return False
        if self.item is None:
            self.eof, self.item = True, None
        return True

    def recv(self):
        if self.item is None and not self.eof:
            self.item = self.q.get()
            if self.item is None:
                self.eof = True
        line, self.item = self.item, None
        if line is None:
            raise EOFError
        try:
            return json.loads(line)
        except ValueError:
            raise EOFError


def _rss_mb(pid):
    if os.name == 'nt':
        return 0.0                                   # memory is only enforced on macOS/Linux
    try:
        out = subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True)
        return int(out.stdout.strip() or 0) / 1024.0
    except Exception:
        return 0.0


class RemoteBidder:
    """Same methods as a Bidder; every call is forwarded to the child process."""

    def __init__(self, path, log_path, product=PRODUCT, contract=CONTRACT, sandbox=False, deny_roots=()):
        self.c = dict(contract)
        self.path, self.log_path, self.product = os.path.abspath(path), os.path.abspath(log_path), product
        env = dict(os.environ)
        env.update(THREAD_ENV)
        cmd = [sys.executable, '-B', CHILD, '--child', self.path, self.log_path, ','.join(sorted(ALLOWED))]
        self.sandboxed = False
        if sandbox:
            if not sandbox_available():
                raise HarnessAbort("sandbox requested but sandbox-exec is not available on this machine")
            cmd = ['sandbox-exec', '-p', sandbox_profile(self.path, self.log_path, deny_roots)] + cmd
            self.sandboxed = True
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     env=env, cwd=os.path.abspath(os.sep), close_fds=True)
        self.conn = PipeConn(self.proc)
        self.fit_cpu = self.fit_rss = 0.0
        self._reset_campaign_stats()
        self._call(['load', product], timeout=60)

    # --- plumbing
    def _call(self, msg, timeout):
        try:
            self.conn.send(msg)
        except EOFError:
            self.close()
            raise HarnessAbort(f"child process died before '{msg[0]}'")
        if not self.conn.poll(timeout):
            self.close()
            raise HarnessAbort(f"no reply to '{msg[0]}' within {timeout:.0f}s (hang or crash)")
        try:
            r = self.conn.recv()
        except EOFError:
            self.close()
            raise HarnessAbort(f"child process died during '{msg[0]}'")
        if r[0] == 'err':
            self.close()
            raise HarnessAbort(f"{msg[0]} raised {r[1]}: {r[2]}")
        return r

    def _reset_campaign_stats(self):
        self.cpu_ms, self.misses, self.errors, self.steps = [], 0, 0, 0
        self.total_cpu_s, self.dead, self.peak_rss = 0.0, False, 0.0
        self._pending, self.last_error = None, None

    # --- Bidder interface
    def fit(self, log_df=None):
        r = self._call(['fit'], timeout=self.c['fit_wall_s'])
        self.fit_cpu, self.fit_rss = r[1], r[2]
        if self.fit_cpu > self.c['fit_cpu_s']:
            self.close()
            raise HarnessAbort(f"fit used {self.fit_cpu:.1f}s CPU (limit {self.c['fit_cpu_s']:.0f}s)")
        if self.fit_rss > self.c['rss_mb']:
            self.close()
            raise HarnessAbort(f"memory {self.fit_rss:.0f} MB after fit (limit {self.c['rss_mb']} MB)")

    def start_campaign(self, budget, n_impressions):
        self._reset_campaign_stats()
        self.n = int(n_impressions)
        self.cpu_cap_s = self.c['mean_cpu_ms'] / 1000.0 * self.n
        self._call(['start', float(budget), self.n], timeout=60)

    @staticmethod
    def _plain(x):
        return x.item() if isinstance(x, np.generic) else x

    def bid(self, context):
        if self.dead:
            return 0.0, 'A'
        self.steps += 1
        pending, self._pending = self._pending, None
        try:
            self.conn.send(['step', pending, {k: self._plain(v) for k, v in context.items()}])
        except EOFError:
            self.close()
            raise HarnessAbort("child process died")
        if not self.conn.poll(self.c['deadline_s']):
            self.misses += 1                       # lost auction; drain the late reply
            if not self.conn.poll(1.0):
                self.close()
                raise HarnessAbort("a bid() call hung for over 1 s")
            try:
                self.conn.recv()
            except EOFError:
                self.close()
                raise HarnessAbort("child process died")
            if self.steps >= 100 and self.misses / self.steps > self.c['miss_frac']:
                self.close()
                raise HarnessAbort(f"deadline missed on {self.misses}/{self.steps} requests (limit {self.c['miss_frac']:.0%})")
            return 0.0, 'A'
        try:
            r = self.conn.recv()
        except EOFError:
            self.close()
            raise HarnessAbort("child process died")
        if r[0] == 'err':
            return self._error(f"{r[1]}: {r[2]}")
        _, ret, ms, bad = r
        self.cpu_ms.append(ms)
        self.total_cpu_s += ms / 1000.0
        if self.total_cpu_s > self.cpu_cap_s:
            self.dead = True                       # campaign ends; spend so far still counts
        if self.steps % 2000 == 0:
            self.peak_rss = max(self.peak_rss, _rss_mb(self.proc.pid))
            if self.peak_rss > self.c['rss_mb']:
                self.close()
                raise HarnessAbort(f"memory {self.peak_rss:.0f} MB (limit {self.c['rss_mb']} MB)")
        if ret is not None and ret[1] in ('A', 'B', 'C') and ret[0] >= 0.0:
            return float(ret[0]), ret[1]
        return self._error(f"invalid return {bad if bad else ret!r}")

    def _error(self, text):
        self.errors += 1
        self.last_error = text
        if self.steps >= 100 and self.errors / self.steps > self.c['err_frac']:
            self.close()
            raise HarnessAbort(f"error rate above {self.c['err_frac']:.0%}; last: {text}")
        return 0.0, 'A'

    def update(self, outcome):
        self._pending = {k: self._plain(v) for k, v in outcome.items()}

    def finish(self):
        if not self.dead and self.proc.poll() is None:
            r = self._call(['flush', self._pending], timeout=10)
            self._pending = None
            self.peak_rss = max(self.peak_rss, r[1], _rss_mb(self.proc.pid))

    # --- reporting / cleanup
    def stats(self):
        a = np.array(self.cpu_ms) if self.cpu_ms else np.zeros(1)
        return dict(steps=self.steps, errors=self.errors, misses=self.misses,
                    p50_cpu_ms=float(np.percentile(a, 50)), p99_cpu_ms=float(np.percentile(a, 99)),
                    max_cpu_ms=float(a.max()), mean_cpu_ms=float(a.mean()),
                    total_cpu_s=self.total_cpu_s, cpu_cap_hit=self.dead,
                    peak_rss_mb=max(self.peak_rss, self.fit_rss), fit_cpu_s=self.fit_cpu,
                    last_error=self.last_error)

    def close(self):
        try:
            if self.proc.poll() is None:
                self.proc.kill()
                self.proc.wait(2)
        except Exception:
            pass


# ====================================================================================== bidder process


def _child_main():
    student_path, log_path, allowed = sys.argv[1], sys.argv[2], set(sys.argv[3].split(','))
    inp = os.fdopen(os.dup(0), 'rb')
    out = os.fdopen(os.dup(1), 'wb', buffering=0)
    sys.stdout = open(os.devnull, 'w')             # student print() cannot corrupt the protocol
    sys.stderr = open(os.devnull, 'w')

    def send(obj):
        out.write((json.dumps(obj, allow_nan=False) + '\n').encode())

    def rss_mb():
        try:
            import resource                          # not available on Windows
        except ImportError:
            return 0.0
        r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return r / (1024 ** 2) if sys.platform == 'darwin' else r / 1024

    np.random.seed(0)
    random.seed(0)
    real_import = builtins.__import__

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        g = globals if globals is not None else sys._getframe(1).f_globals
        if g.get('__name__') == 'student_bidder' and level == 0 and name.split('.')[0] not in allowed:
            raise ImportError(f"import of '{name}' is not allowed")
        return real_import(name, globals, locals, fromlist, level)

    import pandas as pd                              # imported before the guard is installed
    bidder = active = None
    while True:
        line = inp.readline()
        if not line:
            break
        msg = json.loads(line)
        op = msg[0]
        try:
            if op == 'load':
                builtins.__import__ = guarded
                spec = importlib.util.spec_from_file_location('student_bidder', student_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                bidder = mod.Bidder(msg[1])
                send(['ok'])
            elif op == 'fit':
                log = pd.read_csv(log_path)
                t = time.process_time()
                bidder.fit(log)
                send(['ok', time.process_time() - t, rss_mb()])
                del log
            elif op == 'start':
                active = copy.deepcopy(bidder)
                active.start_campaign(msg[1], msg[2])
                np.random.seed(0)
                random.seed(0)
                send(['ok'])
            elif op == 'step':
                t = time.process_time()
                if msg[1] is not None:
                    active.update(msg[1])
                res = active.bid(msg[2])
                ms = (time.process_time() - t) * 1000.0
                try:
                    b, cr = res
                    b = float(b)
                    ret = [b, str(cr)] if b == b and abs(b) != float('inf') else None
                except Exception:
                    ret = None
                send(['bid', ret, ms, None if ret is not None else repr(res)[:80]])
            elif op == 'flush':
                if msg[1] is not None:
                    active.update(msg[1])
                send(['ok', rss_mb()])
            elif op == 'stop':
                break
        except BaseException as e:                  # report, keep the child alive
            send(['err', type(e).__name__, str(e)[:200]])



# ====================================================================================== checker



FEATURES = ['interest', 'revisit', 'device', 'os', 'age_bracket', 'city_tier', 'hour', 'referral',
            'session_depth', 'day_of_week']
N_SAMPLE = 1000                               # auctions per practice campaign
PRACTICE = [(N_SAMPLE, 5.5), (N_SAMPLE, 0.5)]  # (auctions, budget per auction in Rs): a middle level, and one that runs out
WRITEUP_MAX_WORDS = 800
LENIENT = 2.0                                 # the check fails only at twice the CPU limits: your machine may be slower than the grader's


def disallowed_imports(path):
    tree = ast.parse(open(path, encoding='utf-8', errors='replace').read())
    bad = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or '']
        else:
            continue
        bad |= {n.split('.')[0] for n in names} - ALLOWED
    return sorted(bad)


def public_campaign(rb, records, n, budget, seed=0):
    """Second-price replay of public auctions with random, meaningless outcomes. Returns bids and a summary."""
    rng = np.random.default_rng(seed)
    rb.start_campaign(budget, n)
    left, spend, wins, bids, empty_at = budget, 0.0, 0, [], None
    for i in range(n):
        rec = records[i % len(records)]
        ctx = {f: rec[f] for f in FEATURES}
        ctx.update(budget_remaining=float(left), impressions_remaining=n - i)
        b, c = rb.bid(ctx)
        bids.append((round(b, 9), c))
        price = float(rec['market_price'])
        if b >= price and left >= price:
            left -= price; spend += price; wins += 1
            rb.update({'won': True, 'price': price, 'clicked': bool(rng.random() < 0.1),
                       'converted': bool(rng.random() < 0.03)})
        else:
            rb.update({'won': False})
        if empty_at is None and left < 2.0:                 # no competing price is below Rs 2
            empty_at = i
    rb.finish()
    return bids, dict(n=n, budget=budget, spent=spend / budget, wins=wins, win_rate=wins / n, empty_at=empty_at)


GRADING_STACK = dict(python='3.12', numpy='2.3.5', pandas='2.3.3', scipy='1.16.3', sklearn='1.8.0')
TESTED_MIN = dict(numpy=(1, 26), pandas=(2, 0), scipy=(1, 12), sklearn=(1, 5))


def _v(text):
    out = []
    for part in text.split('.')[:2]:
        digits = ''.join(ch for ch in part if ch.isdigit())
        out.append(int(digits or 0))
    return tuple(out)


def environment_lines():
    """What this machine runs, against the stack the grader uses and the range we tested."""
    import scipy
    import sklearn
    have = dict(numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__, sklearn=sklearn.__version__)
    lines = [f"you:      Python {sys.version.split()[0]}, numpy {have['numpy']}, pandas {have['pandas']}, scipy {have['scipy']}, scikit-learn {have['sklearn']}",
             f"grading:  Python {GRADING_STACK['python']}, numpy {GRADING_STACK['numpy']}, pandas {GRADING_STACK['pandas']}, scipy {GRADING_STACK['scipy']}, scikit-learn {GRADING_STACK['sklearn']}"]
    warn = []
    if not ((3, 9) <= sys.version_info[:2] <= (3, 13)):
        warn.append("Python outside the tested range 3.9-3.13")
    for k, lo in TESTED_MIN.items():
        if _v(have[k]) < lo:
            warn.append(f"{k} {have[k]} is older than the tested minimum {'.'.join(map(str, lo))}: numbers can differ slightly")
    if have != {k: v for k, v in GRADING_STACK.items() if k != 'python'}:
        warn.append("your versions differ from the grader's: code that relies on version-specific behaviour (for example a removed scikit-learn argument, or pandas chained assignment) can behave differently in grading. `pip install -r requirements.txt` builds the grader's environment")
    return lines, warn


def name_advice(bidder, writeup):
    """File names must be the roll numbers of the team joined by underscores (1-3 of them), the same for the .py and the .md."""
    import re
    adv = []
    stem = os.path.splitext(os.path.basename(bidder))[0]
    parts = stem.split('_')
    if not (1 <= len(parts) <= 3 and all(re.fullmatch(r'[A-Za-z0-9]+', x) for x in parts) and len({x.lower() for x in parts}) == len(parts)) or stem.lower() in ('bidder', 'template', 'bidder_template'):
        adv.append(f"rename '{os.path.basename(bidder)}': the file name must be the roll numbers of everyone in the team joined by underscores (1 to 3), e.g. 2301001_2301007.py")
    if writeup and os.path.splitext(os.path.basename(writeup))[0] != stem:
        adv.append(f"the write-up should have the same name as the bidder: {stem}.md")
    if not writeup:
        adv.append(f"also submit the write-up: {stem}.md (at most 800 words)")
    return adv


def check(path, log_path='historical_log.csv', writeup=None):
    rows, fails, notes = [], [], []

    def rule(name, ok, detail):
        """ok is True (PASS), False (FAIL) or 'warn' (WARN: allowed here, but close to or over the stated limit)."""
        rows.append((name, ok, detail))
        if ok is False:
            fails.append(name)

    size_mb = os.path.getsize(path) / 1e6
    rule('file size', size_mb <= CONTRACT['max_file_mb'], f"{size_mb:.2f} MB (limit {CONTRACT['max_file_mb']} MB)")
    if writeup:
        try:
            words = len(open(writeup, encoding='utf-8', errors='replace').read().split())
            rule('write-up', 0 < words <= WRITEUP_MAX_WORDS, f"{words} words (limit {WRITEUP_MAX_WORDS})")
        except OSError as e:
            rule('write-up', False, f"cannot read {writeup}: {e}")
    try:
        bad = disallowed_imports(path)
    except SyntaxError as e:
        return [('syntax', False, str(e))], ['syntax'], notes
    rule('imports', not bad, 'ok' if not bad else f"not allowed: {', '.join(bad)}")
    if bad:
        return rows, fails, notes          # never execute code that imports unlisted packages

    try:
        sample = pd.read_csv(log_path, usecols=FEATURES + ['market_price', 'prior_bid'], encoding='utf-8')
        # the log has no price for lost auctions: the practice replay uses 1.25 x prior_bid there (a stand-in; it only has to be a plausible price)
        sample['market_price'] = sample['market_price'].fillna(sample['prior_bid'] * 1.25)
    except (OSError, ValueError) as e:
        rule('historical log', False, f"cannot read {log_path}: {e}")
        return rows, fails, notes
    records = sample.sample(n=min(len(sample), N_SAMPLE), random_state=0).to_dict('records')
    lenient = dict(CONTRACT, fit_cpu_s=CONTRACT['fit_cpu_s'] * LENIENT, fit_wall_s=CONTRACT['fit_wall_s'] * LENIENT,
                   mean_cpu_ms=CONTRACT['mean_cpu_ms'] * LENIENT, p99_cpu_ms=CONTRACT['p99_cpu_ms'] * LENIENT)
    rb = None
    try:
        rb = RemoteBidder(path, log_path, contract=lenient)
        rb.fit()
        fit_ok = rb.fit_cpu <= CONTRACT['fit_cpu_s']
        rule('fit cpu', True if fit_ok else 'warn',
             f"{rb.fit_cpu:.1f} s (limit {CONTRACT['fit_cpu_s']:.0f} s)" + ('' if fit_ok else ': over the limit; make fit lighter, it may fail in grading'))
        results, first_bids = [], None
        for j, (n, per) in enumerate(PRACTICE):
            bids, summ = public_campaign(rb, records, n, per * n)
            results.append((summ, rb.stats()))
            if j == 0:
                first_bids = bids
        again, _ = public_campaign(rb, records, PRACTICE[0][0], PRACTICE[0][1] * PRACTICE[0][0])   # fresh campaign, fresh state
        errors = sum(r[1]['errors'] for r in results)
        misses = sum(r[1]['misses'] for r in results)
        last = next((r[1]['last_error'] for r in results if r[1]['errors']), None)
        rule('valid returns / no errors', errors == 0, f"{errors} errors" + (f" (last: {last})" if errors else ''))
        rule('deadline (50 ms)', misses == 0, f"{misses} misses")
        mean = max(r[1]['mean_cpu_ms'] for r in results)
        capped = any(r[1]['cpu_cap_hit'] for r in results)
        if capped or mean > CONTRACT['mean_cpu_ms'] * LENIENT:
            rule('CPU per auction', False, f"mean {mean:.2f} ms, far over the {CONTRACT['mean_cpu_ms']} ms limit")
        elif mean > CONTRACT['mean_cpu_ms']:
            rule('CPU per auction', 'warn', f"mean {mean:.2f} ms on your machine, over the {CONTRACT['mean_cpu_ms']} ms limit: it may be capped in grading, so make bid() lighter")
        else:
            rule('CPU per auction', True, f"mean {mean:.2f} ms (limit {CONTRACT['mean_cpu_ms']} ms; aim well below it)")
        rss = max(r[1]['peak_rss_mb'] for r in results)
        if rss > 0:
            rule('memory', rss <= CONTRACT['rss_mb'], f"{rss:.0f} MB (limit {CONTRACT['rss_mb']} MB)")
        else:
            rule('memory', True, 'not measured on this system')
        if not capped:             # a campaign cut short by the CPU cap differs between runs for that reason alone
            rule('deterministic', first_bids == again, 'same bids on a repeat run' if first_bids == again
                 else 'bids differ between two identical runs: fix your random seeds')
        if any(summ['wins'] == 0 for summ, _ in results):
            rule('wins something', 'warn', "your bidder won no auction on the sample: check how it treats the blank prices in the log and that its bids are above zero")
    except HarnessAbort as e:
        rule('runs', False, str(e))
    finally:
        if rb is not None:
            rb.close()
    return rows, fails, notes


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--child':      # the harness starts this same file as the bidder's process
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        _child_main()
        sys.exit(0)
    a = sys.argv
    md = [x for x in a[1:] if x.lower().endswith('.md')]
    pos = [x for x in a[1:] if not x.lower().endswith('.md')]
    if not pos:
        sys.exit('usage: python check_submission.py bidder.py [writeup.md] [historical_log.csv]')
    log_p = pos[1] if len(pos) > 1 else check.__defaults__[0]
    for what, f in (('bidder file', pos[0]), ('write-up', md[0] if md else None), ('historical log', log_p)):
        if f and not os.path.isfile(f):
            sys.exit(f"cannot find the {what}: {f}" + ("  (run the check from the folder that holds historical_log.csv, or pass its path after the bidder)" if 'log' in what else ''))
    rows, fails, notes = check(pos[0], log_p, writeup=md[0] if md else None)
    if not md:
        notes.append('write-up not checked: run  python check_submission.py bidder.py writeup.md')
    for name, ok, detail in rows:
        print(f"{'PASS' if ok is True else 'WARN' if ok == 'warn' else 'FAIL'}  {name:28s} {detail}")
    if notes:
        print("\nNotes:")
        for line in notes:
            print("  " + line)
    adv = name_advice(pos[0], md[0] if md else None)
    if adv:
        print("\nBefore you submit:")
        for line in adv:
            print("  " + line)
    lines, warn = environment_lines()
    print("\nEnvironment:")
    for line in lines:
        print("  " + line)
    for w in warn:
        print("  WARNING: " + w)
    print("\nOK: interface and limits satisfied (no score is reported)" if not fails else f"\nFAIL: {', '.join(fails)}")
    sys.exit(1 if fails else 0)
