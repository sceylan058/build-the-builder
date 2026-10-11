"""Build a Freya phone agent from a brief. The only final entrypoint.

    python3 builder/build.py <brief_path> [<brief_path> ...] <tool_api_path> [--slot NAME] [--no-save] [--practice-test A|B]

A brief path may be a file, a directory (all files, sorted by name) or a .zip. The last positional argument is the tool API
file (OpenAPI). build.py orchestrates; the LLM only writes and repairs the config, in an isolated work folder.
Stages: 1 write config (LLM)  2 compile (gen.py)  3 check (check.py) + repair rounds  4 dry-run validation
        5 save + publish + verify  6 export to submission/<slot>.workflow.json  7 finalize trace.
"""
import argparse, asyncio, datetime, hashlib, json, os, pathlib, re, shutil, subprocess, sys, time, zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "builder"))
import check  # noqa: E402

MODEL = os.environ.get("BUILDER_MODEL", "claude-opus-5-5")

# The builder's own API key lives in a gitignored file and is loaded only into this process (never the user's shell).
KEY_FILE = ROOT / ".anthropic_key"
CREDENTIALS = "api_key (environment)" if os.environ.get("ANTHROPIC_API_KEY") else "claude_login"
if not os.environ.get("ANTHROPIC_API_KEY") and KEY_FILE.exists():
    _k = KEY_FILE.read_text().strip()
    if _k:
        os.environ["ANTHROPIC_API_KEY"] = _k
        CREDENTIALS = "api_key"
NO_NEW_ROUND_AFTER = 20 * 60
SAVE_BY = 25 * 60
MAX_REPAIR_ROUNDS = 3
BUNDLE_MAX_CHARS = 60_000   # larger text files are listed in the bundle, not pasted
TEXT_EXT = {".md", ".txt", ".csv", ".tsv", ".json", ".yaml", ".yml", ".eml", ".html", ".htm", ".xml", ".log", ""}


# --------------------------------------------------------------------------------------------------- trace

class Trace:
    def __init__(self, slot):
        (ROOT / "traces").mkdir(exist_ok=True)
        self.log_path = ROOT / "traces" / f"{slot}.log"
        self.jsonl_path = ROOT / "traces" / f"{slot}.jsonl"
        self.log = open(self.log_path, "w")
        self.jsonl = open(self.jsonl_path, "w")
        self.t0 = time.time()
        self.secrets = [v for v in (os.environ.get(k, "") for k in ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY", "ANTHROPIC_API_KEY")) if len(v) >= 6]

    def redact(self, s):
        s = str(s)
        for v in self.secrets:
            s = s.replace(v, "[REDACTED]")
        s = re.sub(r"fak_\S+", "fak_[REDACTED]", s)
        return re.sub(r"sk-ant-\S+", "sk-ant-[REDACTED]", s)

    def elapsed(self):
        return time.time() - self.t0

    def line(self, text):
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%SZ")
        out = self.redact(f"[{stamp} +{self.elapsed():6.1f}s] {text}")
        print(out, flush=True)
        self.log.write(out + "\n")
        self.log.flush()

    def raw(self, obj):
        self.jsonl.write(self.redact(json.dumps(obj, default=str)) + "\n")
        self.jsonl.flush()

    def close(self):
        self.log.close()
        self.jsonl.close()


# --------------------------------------------------------------------------------------------------- inputs

def sha256(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def collect_inputs(paths, dest, T):
    """Copy every brief input into dest, expanding directories and zips. Returns the files in order."""
    dest.mkdir(parents=True, exist_ok=True)
    files = []
    for i, p in enumerate(paths):
        p = pathlib.Path(p)
        if not p.exists():
            sys.exit(f"build.py: brief path not found: {p}")
        if p.is_dir():
            for f in sorted(x for x in p.rglob("*") if x.is_file()):
                t = dest / f"{i:02d}_{p.name}" / f.relative_to(p)
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, t)
                files.append(t)
        elif p.suffix.lower() == ".zip":
            t = dest / f"{i:02d}_{p.stem}"
            with zipfile.ZipFile(p) as z:
                for m in z.namelist():
                    target = (t / m).resolve()
                    if not str(target).startswith(str(t.resolve())):
                        sys.exit(f"build.py: unsafe path in zip: {m}")
                z.extractall(t)
            files += sorted(x for x in t.rglob("*") if x.is_file() and "__MACOSX" not in x.parts)
        else:
            t = dest / f"{i:02d}_{p.name}"
            shutil.copy2(p, t)
            files.append(t)
    for f in files:
        T.line(f"input {f.relative_to(dest)} sha256={sha256(f)[:16]} bytes={f.stat().st_size}")
    return files


def to_text(f):
    ext = f.suffix.lower()
    if ext in TEXT_EXT:
        return f.read_text(encoding="utf-8", errors="replace")
    if ext == ".pdf" and shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-layout", str(f), "-"], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
    if ext in (".docx", ".doc", ".rtf", ".odt") and shutil.which("textutil"):
        r = subprocess.run(["textutil", "-convert", "txt", "-stdout", str(f)], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
    if ext == ".docx":
        try:
            with zipfile.ZipFile(f) as z:
                xml = z.read("word/document.xml").decode("utf-8", "replace")
            return re.sub(r"<[^>]+>", " ", xml.replace("</w:p>", "\n"))
        except Exception:
            pass
    return None


def write_bundle(files, inputs_dir, out):
    parts = []
    for f in files:
        rel = f.relative_to(inputs_dir)
        txt = to_text(f)
        if txt is not None and len(txt) > BUNDLE_MAX_CHARS:
            parts.append(f"\n\n===== FILE: inputs/{rel} =====\n(large file, {len(txt)} characters, not pasted here; "
                         f"start with its first lines and search it with the Read tool: inputs/{rel})\n")
        elif txt is None:
            parts.append(f"\n\n===== FILE: inputs/{rel} =====\n(binary file not converted; open it with the Read tool: inputs/{rel})\n")
        else:
            parts.append(f"\n\n===== FILE: inputs/{rel} =====\n{txt}")
    out.write_text("".join(parts).lstrip())


# --------------------------------------------------------------------------------------------------- isolation guard

def make_guard(workdir, T):
    root = str(workdir.resolve())

    # the SDK spills large tool outputs of this very session to ~/.claude/projects/<key of the work folder>/.../tool-results/
    spill = str(pathlib.Path.home() / ".claude" / "projects") + os.sep + re.sub(r"[^A-Za-z0-9]", "-", root) + os.sep

    def inside(p):
        if not p:
            return True
        if str(p).startswith(spill) and "/tool-results/" in str(p):
            return True
        q = pathlib.Path(p)
        q = (workdir / q) if not q.is_absolute() else q
        r = str(q.resolve())
        return r == root or r.startswith(root + os.sep)

    async def guard(input_data, tool_use_id, context):
        name = input_data.get("tool_name", "")
        ti = input_data.get("tool_input", {}) or {}
        why = None
        if name in ("Read", "Write", "Edit", "NotebookEdit"):
            if not inside(ti.get("file_path") or ti.get("notebook_path")):
                why = f"{name} outside the work folder: {ti.get('file_path')}"
        elif name in ("Glob", "Grep"):
            if not inside(ti.get("path")) or ".." in str(ti.get("pattern", "")) or str(ti.get("pattern", "")).startswith("/"):
                why = f"{name} outside the work folder: {ti.get('path')} {ti.get('pattern')}"
        elif name == "Bash":
            cmd = str(ti.get("command", ""))
            abs_paths = [m for m in re.findall(r"(?<![\w.])(/[^\s'\";|&]+)", cmd)
                         if not (m == root or m.startswith(root + os.sep)) and m not in ("/dev/null",) and not (m.startswith(spill) and "/tool-results/" in m)]
            if ".." in cmd or "~" in cmd or abs_paths or re.search(r"\bcd\s+/", cmd) or "$HOME" in cmd:
                why = f"Bash command reaches outside the work folder: {cmd[:160]}"
        elif name not in ("TodoWrite",):
            why = f"tool {name} is not allowed"
        if why:
            T.line(f"GUARD denied: {why}")
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                           "permissionDecisionReason": "Only files inside the current work folder may be used. " + why}}
        return {}
    return guard


# --------------------------------------------------------------------------------------------------- LLM session

CRED_RE = re.compile(r"credit balance is too low|invalid api key|invalid x-api-key|authentication_error|permission_error|billing|insufficient credit|api key.*(revoked|disabled)", re.I)


def credential_error(text):
    """True when a model reply is a credential/billing failure (never a config problem)."""
    return bool(CRED_RE.search(str(text or "")))


class Writer:
    """One Claude session that writes and repairs config.json inside the work folder."""

    def __init__(self, workdir, T):
        self.workdir, self.T, self.client, self.fatal = workdir, T, None, None

    async def start(self):
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher
        opts = ClaudeAgentOptions(
            cwd=str(self.workdir), model=MODEL, tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
            allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"], permission_mode="bypassPermissions",
            setting_sources=[], max_turns=80,
            hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[make_guard(self.workdir, self.T)])]},
            system_prompt=("You write config.json for a phone-agent generator, inside the current folder only. "
                           "Follow skill/SKILL.md exactly. Never read or write outside the current folder."),
            env=dict({"BASH_DEFAULT_TIMEOUT_MS": "120000"}, **({"ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"]} if os.environ.get("ANTHROPIC_API_KEY") else {})))
        self.T.line("credentials: " + CREDENTIALS)
        self.client = ClaudeSDKClient(options=opts)
        await self.client.connect()

    async def ask(self, prompt, stage, budget_s):
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock
        t = time.time()
        await self.client.query(prompt)
        calls = 0

        async def consume():
            nonlocal calls
            async for m in self.client.receive_response():
                self.T.raw({"stage": stage, "type": type(m).__name__, "message": getattr(m, "__dict__", str(m))})
                if isinstance(m, AssistantMessage):
                    calls += 1
                    what = []
                    for b in m.content:
                        if isinstance(b, ToolUseBlock):
                            arg = b.input.get("file_path") or b.input.get("command") or b.input.get("pattern") or ""
                            what.append(f"{b.name} {str(arg)[:70]}")
                        elif isinstance(b, TextBlock) and b.text.strip():
                            what.append("says: " + b.text.strip().splitlines()[0][:70])
                    self.T.line(f"model call {calls} [{stage}] model={getattr(m, 'model', MODEL)}: {'; '.join(what) or 'thinking'}")
                    for b in m.content:
                        if isinstance(b, TextBlock) and credential_error(b.text):
                            self.fatal = b.text.strip()[:200]
                elif isinstance(m, ResultMessage):
                    u = m.usage or {}
                    self.T.line(f"model session [{stage}] done: turns={m.num_turns} duration={m.duration_ms / 1000:.0f}s "
                                f"cost=${(m.total_cost_usd or 0):.2f} tokens in={u.get('input_tokens')} out={u.get('output_tokens')} "
                                f"cache_read={u.get('cache_read_input_tokens')}")
        try:
            await asyncio.wait_for(consume(), timeout=max(30, budget_s))
        except asyncio.TimeoutError:
            self.T.line(f"[{stage}] model time budget ({budget_s:.0f}s) used up; interrupting")
            try:
                await self.client.interrupt()
            except Exception:
                pass
        self.T.line(f"[{stage}] model stage took {time.time() - t:.0f}s, {calls} model calls")

    async def stop(self):
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass


# --------------------------------------------------------------------------------------------------- compile + check

def compile_and_check(workdir, T, rnd):
    cfg_p, wf_p = workdir / "config.json", workdir / "workflow.json"
    if not cfg_p.exists():
        return None, ["config.json does not exist yet"]
    try:
        cfg = json.loads(cfg_p.read_text())
    except Exception as ex:
        return None, [f"config.json is not valid JSON: {ex}"]
    t = time.time()
    r = subprocess.run([sys.executable, str(ROOT / "builder" / "skill" / "gen.py"), "config.json", "workflow.json"],
                       cwd=workdir, capture_output=True, text=True, timeout=120)
    T.line(f"[compile round {rnd}] gen.py exit={r.returncode} ({time.time() - t:.1f}s) {(r.stdout + r.stderr).strip()[-300:]}")
    if r.returncode != 0:
        return None, [(r.stderr or r.stdout).strip()[-1500:]]
    wf = json.loads(wf_p.read_text())
    api = json.loads((workdir / "openapi.json").read_text())
    bundle = (workdir / "brief_bundle.md").read_text(errors="replace")
    t = time.time()
    errors = check.run_checks(wf, api, cfg, bundle)
    T.line(f"[check round {rnd}] check.py: {'OK' if not errors else str(len(errors)) + ' error(s)'} ({time.time() - t:.1f}s)")
    for e in errors[:30]:
        T.line(f"    {e}")
    return wf, errors


def check_workflow(workdir, T, rnd):
    """Workflow mode: validate the model-written workflow.json against the given or model-written openapi.json."""
    wf_p, api_p = workdir / "workflow.json", workdir / "openapi.json"
    if not wf_p.exists():
        return None, ["workflow.json does not exist yet"]
    if not api_p.exists():
        return None, ["openapi.json does not exist yet: write it from the brief's integration documents (skill/WORKFLOW_SKILL.md step 1)"]
    try:
        wf = json.loads(wf_p.read_text())
        wf = wf.get("workflow", wf)
        api = json.loads(api_p.read_text())
    except Exception as ex:
        return None, [f"workflow.json or openapi.json is not valid JSON: {ex}"]
    base = (workdir / "tool_base_url.txt").read_text().strip() if (workdir / "tool_base_url.txt").exists() else ""
    errors = []
    if base and (api.get("servers") or [{}])[0].get("url", "").rstrip("/") != base.rstrip("/"):
        errors.append(f"openapi.json servers[0].url must be the tool base URL {base}")
    t = time.time()
    try:
        errors += check.run_checks(wf, api, None, None)
    except Exception as ex:
        errors.append(f"check.py crashed on the workflow: {type(ex).__name__}: {ex}")
    T.line(f"[check round {rnd}] check.py (workflow mode): {'OK' if not errors else str(len(errors)) + ' error(s)'} ({time.time() - t:.1f}s)")
    for e in errors[:30]:
        T.line(f"    {e}")
    return wf, errors


def counts(wf):
    tools = sum(len(n.get("tools", []) or []) for n in wf["nodes"].values())
    pre = sum(len(n.get("pre_actions", []) or []) for n in wf["nodes"].values())
    return f"{len(wf['nodes'])} nodes, {tools} model tools, {pre} engine actions"


HARD_STOP = 29 * 60   # keep retrying Freya through outages until this point of the run


def transient(ex):
    """A platform outage, not a problem with our workflow: 5xx, 429, timeouts, connection errors."""
    s = str(ex)
    return bool(re.search(r"-> (5\d\d|429)\b", s)) or any(k in s for k in ("timed out", "Timeout", "Connection", "URLError", "reset by peer", "Temporary failure"))


def retry(fn, T, what, tries=8):
    """Retry Freya calls through outages with growing back-off, never past HARD_STOP. Non-transient errors raise at once."""
    for i in range(tries):
        try:
            return fn()
        except Exception as ex:
            T.line(f"{what} attempt {i + 1} failed: {str(ex)[:200]}")
            wait = min(15 * (2 ** i), 120)
            if not transient(ex) or i == tries - 1 or T.elapsed() + wait > HARD_STOP:
                raise
            time.sleep(wait)


# --------------------------------------------------------------------------------------------------- main

async def run(a):
    os.chdir(ROOT)
    def is_openapi(p):
        try:
            d = json.loads(pathlib.Path(p).read_text())
            return isinstance(d, dict) and isinstance(d.get("paths"), dict)
        except Exception:
            return False
    has_api = len(a.paths) >= 2 and is_openapi(a.paths[-1])
    if a.mode == "auto":
        a.mode = "config" if has_api else "workflow"
    if a.mode == "workflow" and not has_api:
        briefs, api_path, api = list(a.paths), None, None
        if not a.tool_base_url:
            f = ROOT / "mock" / "mock_url.txt"
            a.tool_base_url = f.read_text().split()[0] if f.exists() and f.read_text().split() else ""
        if not a.tool_base_url:
            sys.exit("build.py: no tool API file: give --tool-base-url (or TOOL_BASE_URL, or mock/mock_url.txt)")
    else:
        *briefs, api_path = a.paths
        if not briefs:
            sys.exit("build.py: give at least one brief path and then the tool API file")
        if not is_openapi(api_path):
            sys.exit(f"build.py: {api_path} is not an OpenAPI file with 'paths' (the tool API file must be the last argument)")
        api = json.loads(pathlib.Path(api_path).read_text())
    wf_mode = a.mode == "workflow"
    src_name = "workflow.json" if wf_mode else "config.json"
    check_fn = check_workflow if wf_mode else compile_and_check
    write_prompt = ("Write workflow.json now (and openapi.json first if it does not exist), following skill/WORKFLOW_SKILL.md. "
                    "Read brief_bundle.md, the docs/ files it names and any binary inputs it lists first. "
                    "When skill/check.py passes, reply 'workflow ready'.") if wf_mode else \
                   ("Write config.json now, following skill/SKILL.md. Read brief_bundle.md and openapi.json first. "
                    "When the self-checks in SKILL.md pass, reply 'config ready'.")
    slot = a.slot or pathlib.Path(briefs[-1]).stem
    T = Trace(slot)
    stage_t = {}
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip() or "none"
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    except Exception:
        commit, dirty = "none", ""
    T.line(f"START utc={datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')} slot={slot} commit={commit}{' (dirty)' if dirty else ''} builder_model={MODEL}")
    T.line(f"args: mode={a.mode} briefs={briefs} api={api_path} no_save={a.no_save} practice_test={a.practice_test}")

    # ---- prepare the isolated work folder
    s = time.time()
    workdir = ROOT / "work" / slot
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    files = collect_inputs(briefs, workdir / "inputs", T)
    if api_path:
        shutil.copy2(api_path, workdir / "openapi.json")
        T.line(f"tool API {api_path} sha256={sha256(api_path)[:16]} paths={sorted(p.strip('/') for p in api['paths'])} server={api.get('servers', [{}])[0].get('url')}")
    else:
        T.line(f"no tool API file: the model writes openapi.json from the brief's integration documents; tool base URL {a.tool_base_url}")
    (workdir / "tool_base_url.txt").write_text(a.tool_base_url or "")
    write_bundle(files, workdir / "inputs", workdir / "brief_bundle.md")
    shutil.copytree(ROOT / "builder" / "skill", workdir / "skill", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(ROOT / "builder" / "check.py", workdir / "skill" / "check.py")
    shutil.copytree(ROOT / "docs", workdir / "docs")
    stage_t["prepare"] = time.time() - s
    T.line(f"[prepare] work folder ready ({stage_t['prepare']:.1f}s): brief_bundle.md {len((workdir / 'brief_bundle.md').read_text())} chars")

    # ---- stage 1 + 2 + 3: write, compile, check, repair
    writer = Writer(workdir, T)
    best = None   # (ok, -errors, wf)
    rnd = 0
    s = time.time()
    try:
        if a.reuse_config:
            shutil.copy2(a.reuse_config, workdir / "config.json")
            T.line(f"--reuse-config: no model stage; recompiling {a.reuse_config} (sha256={sha256(a.reuse_config)[:16]}) with the current generator")
        else:
            await writer.start()
            await writer.ask(write_prompt, "write " + a.mode, SAVE_BY - 5 * 60 - T.elapsed())
        if writer.fatal and CREDENTIALS.startswith("api_key"):
            T.line(f"credentials: api_key -> claude_login ({writer.fatal[:80]})")
            await writer.stop()
            os.environ.pop("ANTHROPIC_API_KEY", None)
            globals()["CREDENTIALS"] = "claude_login (fallback)"
            writer = Writer(workdir, T)
            await writer.start()
            await writer.ask(write_prompt, "write " + a.mode + " (fallback)", SAVE_BY - 5 * 60 - T.elapsed())
        stage_t["write"] = time.time() - s
        while True:
            s2 = time.time()
            wf, errors = check_fn(workdir, T, rnd)
            stage_t[f"compile+check {rnd}"] = time.time() - s2
            if wf is not None:
                cand = (not errors, -len(errors), wf, json.loads((workdir / src_name).read_text()))
                if best is None or cand[:2] > best[:2]:
                    best = cand
            if not errors:
                break
            if a.reuse_config:
                T.line("--reuse-config: no repair rounds")
                break
            if writer.fatal:
                T.line(f"MODEL CREDENTIALS FAILED ({CREDENTIALS}): {writer.fatal} -- stopping (no repair rounds on a credential failure)")
                break
            if rnd >= MAX_REPAIR_ROUNDS or T.elapsed() > NO_NEW_ROUND_AFTER:
                T.line(f"no further repair round (round {rnd}, elapsed {T.elapsed():.0f}s)")
                break
            rnd += 1
            s3 = time.time()
            await writer.ask(f"The builder checked {src_name} and found these errors. Fix {src_name} for every one, "
                             "run the self-checks again, then reply 'ready'.\n\n" + "\n".join(errors[:60]),
                             f"repair {rnd}", max(60, SAVE_BY - 3 * 60 - T.elapsed()))
            stage_t[f"repair {rnd}"] = time.time() - s3
        # ---- stage 4: dry-run validation on Freya
        if best is not None:
            import freya
            s4 = time.time()
            try:
                r = retry(lambda: freya.validate_workflow(f"{slot}-dryrun", best[2]), T, "dry-run")
                T.line(f"[dry-run] Freya validation: {json.dumps(r)[:200]} ({time.time() - s4:.1f}s)")
            except Exception as ex:
                T.line(f"[dry-run] Freya validation FAILED: {str(ex)[:600]}")
                if transient(ex):
                    T.line("[dry-run] the validator is unavailable (platform outage), not a config problem: continuing without it")
                elif T.elapsed() < NO_NEW_ROUND_AFTER and not a.reuse_config:
                    rnd += 1
                    await writer.ask(f"Freya's validator rejected the workflow from {src_name}:\n" + str(ex)[:3000] +
                                     f"\nFix {src_name}, run the self-checks, reply 'ready'.", f"repair {rnd} (validator)",
                                     max(60, SAVE_BY - 3 * 60 - T.elapsed()))
                    wf, errors = check_fn(workdir, T, rnd)
                    if wf is not None and not errors:
                        best = (True, 0, wf, json.loads((workdir / src_name).read_text()))
            stage_t["dry-run"] = time.time() - s4
    finally:
        await writer.stop()

    if best is None:
        T.line("RESULT: no workflow could be compiled. Nothing saved.")
        finish(T, stage_t, slot)
        return 2
    ok, neg, wf, cfg = best
    (workdir / "final.workflow.json").write_text(json.dumps(wf, indent=1))
    (workdir / ("final.source.json" if wf_mode else "final.config.json")).write_text(json.dumps(cfg, indent=1))
    T.line(f"final workflow: {counts(wf)}; check {'OK' if ok else 'FAILED with ' + str(-neg) + ' error(s)'}; repair rounds used: {rnd}")
    if a.no_save:
        T.line("--no-save: stopping after the dry run")
        finish(T, stage_t, slot)
        return 0 if ok else 1

    # ---- stage 5: save + publish + verify
    import freya
    s5 = time.time()
    res = retry(lambda: freya.save_workflow(slot, wf), T, "save")
    wid, aid = res["workflow_id"], res["agent_id"]
    vs = retry(lambda: freya.api("GET", f"/api/v2/versions/workflow/{wid}", workspaceId=freya.workspace_id())["versions"], T, "versions")
    newest = max(vs, key=lambda v: v["versionNumber"])
    live = retry(lambda: freya.api("GET", f"/api/v2/workflow/{wid}", workspaceId=freya.workspace_id())["workflow"]["workflow"], T, "get workflow")
    llm = (live.get("agent_config") or {}).get("llmConfig") or {}
    model_ok = (llm.get("provider"), llm.get("model")) == (freya.AGENT_LLM["provider"], freya.AGENT_LLM["model"])
    T.line(f"[save] Freya workflow_id={wid} agent_id={aid} version={newest['versionNumber']} published={newest.get('isPublished')} "
           f"agent model={llm.get('provider')}/{llm.get('model')} matches AGENT_LLM={model_ok} ({time.time() - s5:.1f}s)")
    T.line(f"[save] live workflow: {counts(live)}")
    stage_t["save"] = time.time() - s5

    # ---- stage 6: export
    s6 = time.time()
    (ROOT / "submission").mkdir(exist_ok=True)
    out = ROOT / "submission" / f"{slot}.workflow.json"
    retry(lambda: freya.export_workflow(wid, str(out)), T, "export")
    T.line(f"[export] {out.relative_to(ROOT)} sha256={sha256(out)[:16]} ({time.time() - s6:.1f}s)")
    stage_t["export"] = time.time() - s6

    if a.practice_test:
        s7 = time.time()
        T.line(f"[practice-test] development only: tools/run_cases.py {aid} --brief {a.practice_test}")
        r = subprocess.run([sys.executable, "tools/run_cases.py", aid, "--brief", a.practice_test, "--out", f"results/{slot}-practice.json"],
                           capture_output=True, text=True, cwd=ROOT)
        for l in (r.stdout + r.stderr).strip().splitlines()[-25:]:
            T.line(f"    {l}")
        stage_t["practice-test"] = time.time() - s7
    finish(T, stage_t, slot)
    return 0


def finish(T, stage_t, slot):
    for k, v in stage_t.items():
        T.line(f"stage duration {k}: {v:.1f}s")
    T.line(f"END utc={datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')} total={T.elapsed():.0f}s")
    T.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="brief path(s), then the tool API file")
    ap.add_argument("--slot")
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--practice-test", choices=["A", "B"])
    ap.add_argument("--mode", choices=["auto", "config", "workflow"], default="auto",
                    help="config: model writes a config compiled by gen.py; workflow: model writes the workflow JSON directly; "
                         "auto: workflow when no tool API file is given (e.g. a case folder), else config")
    ap.add_argument("--tool-base-url", default=os.environ.get("TOOL_BASE_URL", ""),
                    help="workflow mode without a tool API file: servers[0].url of the openapi.json the model writes "
                         "(default: first line of mock/mock_url.txt)")
    ap.add_argument("--reuse-config", help="skip the model: recompile this previously written config.json with the current generator, then run every later stage")
    a = ap.parse_args()
    if len(a.paths) < 1 or (len(a.paths) < 2 and a.mode == "config"):
        ap.error("give the brief path(s) and, in config mode, the tool API file last")
    sys.exit(asyncio.run(run(a)))


if __name__ == "__main__":
    main()
