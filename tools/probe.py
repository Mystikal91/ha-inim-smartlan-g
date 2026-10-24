#!/usr/bin/env python3
"""Read-only diagnostic for INIM SmartLAN/G panels (stdlib only, Windows friendly).

Logs in, runs every READ-ONLY query and saves the raw replies to a JSON file you
can attach to a GitHub issue. Nothing starting with "do_" is ever sent.
The token and your credentials are NOT written to the output file.

    python tools/probe.py --host 192.168.1.50 --port 80 --user USER
(password and code are asked interactively if not given)
"""

import argparse
import getpass
import json
import re
import time
import urllib.parse
import urllib.request

ALL_ONES = ",".join(["ffffffff"] + ["00000000"] * 6)


def post(base, body, timeout):
    req = urllib.request.Request(
        base + "/cgi-bin/web.cgi", data=urllib.parse.urlencode(body).encode()
    )
    t = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace"), round(time.time() - t, 2)


def get(base, path, timeout):
    t = time.time()
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace"), round(time.time() - t, 2)


MOD_RE = re.compile(r"""\bmod\b['"]?\s*[:=]\s*['"]([A-Za-z_]\w*)['"]""")
JS_REF_RE = re.compile(r"""["']([\w./-]+\.js)["']""")
SRC_RE = re.compile(r"""<script[^>]+src=['"]([^'"]+)['"]""", re.I)


def scan_web_ui(base, timeout):
    """Fetch the index page and its scripts; list mod names and the code around them."""
    res = {"pages": {}, "mods": {}}
    try:
        _, index, _ = get(base, "/", timeout)
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)}
    pages = {"/": index}
    queue = [urllib.parse.urljoin("/", s) for s in SRC_RE.findall(index)]
    queue.append("/web.html")
    try:  # the appcache manifest lists every file of the real UI
        manifest = get(base, "/cgi-bin/smartlang.appcache", timeout)[1]
        pages["/cgi-bin/smartlang.appcache"] = manifest
        for line in manifest.splitlines():
            line = line.strip()
            if line.endswith((".js", ".html")) and not line.startswith(("#", "http")):
                queue.append(urllib.parse.urljoin("/", line))
    except Exception as e:  # noqa: BLE001
        res["pages"]["appcache"] = {"error": repr(e)}
    while queue:
        path = queue.pop(0)
        if path in pages or urllib.parse.urlparse(path).netloc:
            continue
        try:
            pages[path] = get(base, path, timeout)[1]
        except Exception as e:  # noqa: BLE001
            res["pages"][path] = {"error": repr(e)}
            continue
        # follow script files named inside non-vendor scripts (one UI, a few small files)
        if "vendor" not in path and "jquery" not in path and path.endswith(".js"):
            for ref in JS_REF_RE.findall(pages[path]):
                queue.append(urllib.parse.urljoin("/", ref.lstrip("/")))
    for path, text in pages.items():
        res["pages"][path] = {"length": len(text)}
        if "vendor" not in path and "jquery" not in path and len(text) < 60000:
            res["pages"][path]["body"] = text
        for m in MOD_RE.finditer(text):
            snippet = text[max(0, m.start() - 80) : m.end() + 120].replace("\n", " ")
            res["mods"].setdefault(m.group(1), []).append({"file": path, "context": snippet})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=80)
    ap.add_argument("--user", required=True)
    ap.add_argument("--password")
    ap.add_argument("--code")
    ap.add_argument("--timeout", type=float, default=60)
    ap.add_argument("--out", default="probe_output.json")
    a = ap.parse_args()
    pw = a.password or getpass.getpass("Password: ")
    code = a.code or getpass.getpass("Code: ")
    base = f"http://{a.host}:{a.port}"
    out = {}

    for path in ("/sw_str_panel", "/version.html"):
        try:
            s, b, t = get(base, path, a.timeout)
            out[path] = {"status": s, "seconds": t, "body": b}
        except Exception as e:  # noqa: BLE001
            out[path] = {"error": repr(e)}

    s, html, t = post(base, {"user": a.user, "pass": pw, "mod": "auth", "code": code}, a.timeout)
    m = re.search(r"tk\s*=\s*['\"]([^'\"]+)", html)
    q = re.search(r"qindex\s*=\s*['\"]([^'\"]*)", html)
    ok = "ACK" in html and m
    out["login"] = {
        "status": s,
        "seconds": t,
        "ack": bool(ok),
        "qindex": q.group(1) if q else None,
        "token_length": len(m.group(1)) if m else None,
    }
    if not ok:
        out["login"]["body_without_token"] = re.sub(r"tk\s*=\s*['\"][^'\"]*['\"]", "tk='***'", html)
        json.dump(out, open(a.out, "w"), indent=2, ensure_ascii=False)
        raise SystemExit("Login failed, see " + a.out)
    tk, qi = m.group(1), (q.group(1) if q else "0")

    # Discover which "mod" names the panel's own web UI uses (static GETs only).
    out["web_ui"] = scan_web_ui(base, a.timeout)

    probes = [
        ("sce", {"mod": "sce"}),
        ("sce_now", {"mod": "sce", "par": "now"}),
        ("part", {"mod": "part"}),
        ("zone", {"mod": "zone"}),
        ("cmd", {"mod": "cmd"}),
        ("cmd_mask_all", {"mod": "cmd", "par": ALL_ONES}),
        ("tmr", {"mod": "tmr"}),
        ("fau", {"mod": "fau"}),
        ("gsm", {"mod": "gsm"}),
        ("log10", {"mod": "log", "par": "10"}),
    ]
    for name, extra in probes:
        body = {"tk": tk, "qindex": qi, **extra}
        try:
            s, b, t = post(base, body, a.timeout)
            try:
                parsed = json.loads(b.strip())
            except ValueError:
                parsed = None
            out[name] = {
                "request": extra,
                "status": s,
                "seconds": t,
                "json": parsed,
                "raw": None if parsed is not None else b,
            }
        except Exception as e:  # noqa: BLE001
            out[name] = {"request": extra, "error": repr(e)}
        print(name, "->", out[name].get("seconds", out[name].get("error")))
    json.dump(out, open(a.out, "w"), indent=2, ensure_ascii=False)
    print("Saved", a.out, "- check it for private data (names of people/rooms) before sharing.")


if __name__ == "__main__":
    main()
