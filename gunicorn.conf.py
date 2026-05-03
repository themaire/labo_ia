# Gunicorn production configuration
# https://docs.gunicorn.org/en/stable/configure.html

import multiprocessing

# ── Binding ──────────────────────────────────────────────────────────────────
bind = "0.0.0.0:5000"

# ── Workers ──────────────────────────────────────────────────────────────────
# Respect container cgroup CPU quota when available; fall back to host count.
# Override via the GUNICORN_WORKERS environment variable.
import os as _os

def _default_workers():
    try:
        # Docker / cgroups v2 exposes quota & period files
        quota  = int(open("/sys/fs/cgroup/cpu.max").read().split()[0])
        period = int(open("/sys/fs/cgroup/cpu.max").read().split()[1])
        if quota > 0:
            return max(2, int(quota / period) * 2 + 1)
    except Exception:
        pass
    return multiprocessing.cpu_count() * 2 + 1

workers = int(_os.environ.get("GUNICORN_WORKERS", _default_workers()))
worker_class = "sync"          # default; switch to "gevent" for async I/O apps
threads = 2                    # threads per worker
timeout = 120                  # seconds before a worker is killed & restarted

# ── Logging ──────────────────────────────────────────────────────────────────
accesslog = "-"   # stdout
errorlog  = "-"   # stderr
loglevel  = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# ── Process naming ────────────────────────────────────────────────────────────
proc_name = "labo_ia"

# ── Security / performance tweaks ────────────────────────────────────────────
max_requests = 1000           # recycle workers after N requests (memory leak guard)
max_requests_jitter = 100     # randomise recycling to avoid thundering herd
keepalive = 5                 # seconds to keep idle connections open
