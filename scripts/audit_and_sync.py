"""Zero-cost architecture audit for the provider-native Shorts pipeline.

Run from the repository root with ``python scripts/audit_and_sync.py``.  The
audit intentionally makes no selected-provider request and never reads `.env`.
It validates contracts, `.env.example`, sanitizer behavior, FFmpeg parsing, and
the service-layer network boundary.
"""

from __future__ import annotations

import ast
import inspect
import os
import pkgutil
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, get_origin, get_type_hints


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class Color:
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    RESET = "\033[0m"


@dataclass
class AuditReport:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def section(self, title: str) -> None:
        print(f"\n{Color.CYAN}== {title} =={Color.RESET}")

    def passed(self, message: str) -> None:
        print(f"{Color.GREEN}PASS{Color.RESET} {message}")

    def failed(self, message: str) -> None:
        self.failures.append(message)
        print(f"{Color.RED}FAIL{Color.RESET} {message}")

    def warning(self, message: str) -> None:
        self.warnings.append(message)
        print(f"{Color.YELLOW}WARN{Color.RESET} {message}")


def _modules_under_providers() -> list[ModuleType]:
    import providers

    modules: list[ModuleType] = []
    for info in pkgutil.walk_packages(providers.__path__, providers.__name__ + "."):
        try:
            modules.append(__import__(info.name, fromlist=["*"]))
        except Exception as exc:  # imports must be safe and must not create remote clients
            raise RuntimeError(f"could not import {info.name}: {type(exc).__name__}: {exc}") from exc
    return modules


def _compatible_annotation(expected: Any, actual: Any) -> bool:
    """Accept the same runtime type origin (e.g. list[Any] and list)."""
    if expected is inspect.Signature.empty or actual is inspect.Signature.empty:
        return False
    if expected is Any:
        return True
    return (get_origin(expected) or expected) == (get_origin(actual) or actual)


def audit_provider_contracts(report: AuditReport) -> None:
    from providers.base import BaseImageProvider, BaseLLMProvider, BaseSfxProvider, BaseVideoProvider, BaseVoiceProvider

    report.section("1/5 Provider contract signatures")
    bases = (BaseLLMProvider, BaseImageProvider, BaseVideoProvider, BaseVoiceProvider, BaseSfxProvider)
    discovered: list[type[Any]] = []
    for module in _modules_under_providers():
        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if candidate.__module__ != module.__name__ or candidate in bases:
                continue
            if any(issubclass(candidate, base) for base in bases):
                discovered.append(candidate)

    if not discovered:
        report.failed("No concrete provider adapters were discovered.")
        return
    for provider in sorted(set(discovered), key=lambda item: item.__name__):
        matching_base = next(base for base in bases if issubclass(provider, base))
        if inspect.isabstract(provider):
            report.failed(f"{provider.__name__} is abstract and leaves {matching_base.__name__} unimplemented")
            continue
        method_name = next(iter(matching_base.__abstractmethods__))
        method = getattr(provider, method_name, None)
        base_method = getattr(matching_base, method_name)
        if method is None or not inspect.iscoroutinefunction(method):
            report.failed(f"{provider.__name__}.{method_name} must be an async method")
            continue
        expected = list(inspect.signature(base_method).parameters.values())[1:]
        actual = list(inspect.signature(method).parameters.values())[1:]
        if [(p.name, p.kind) for p in actual] != [(p.name, p.kind) for p in expected]:
            report.failed(f"{provider.__name__}.{method_name} parameters do not match {matching_base.__name__}")
            continue
        try:
            base_hints = get_type_hints(base_method)
            method_hints = get_type_hints(method)
        except Exception as exc:
            report.failed(f"{provider.__name__}.{method_name} annotations could not be resolved: {exc}")
            continue
        mismatches = [
            name for name in [p.name for p in expected] + ["return"]
            if not _compatible_annotation(base_hints.get(name, inspect.Signature.empty), method_hints.get(name, inspect.Signature.empty))
        ]
        if mismatches:
            report.failed(f"{provider.__name__}.{method_name} incompatible annotations: {', '.join(mismatches)}")
        else:
            report.passed(f"{provider.__name__}.{method_name} matches {matching_base.__name__}")


def _env_example_keys() -> set[str]:
    example = ROOT / ".env.example"
    if not example.is_file():
        raise RuntimeError(".env.example is missing")
    return {
        match.group(1)
        for line in example.read_text(encoding="utf-8").splitlines()
        if (match := re.match(r"\s*([A-Z][A-Z0-9_]*)\s*=", line))
    }


class _EnvLookupVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.keys: set[str] = set()

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            func = node.func
            direct_getenv = (
                isinstance(func, ast.Attribute) and func.attr == "getenv"
                and isinstance(func.value, ast.Name) and func.value.id == "os"
            )
            environ_get = (
                isinstance(func, ast.Attribute) and func.attr == "get"
                and isinstance(func.value, ast.Attribute) and func.value.attr == "environ"
                and isinstance(func.value.value, ast.Name) and func.value.value.id == "os"
            )
            if direct_getenv or environ_get:
                self.keys.add(node.args[0].value)
        self.generic_visit(node)


def audit_env_sync(report: AuditReport) -> None:
    report.section("2/5 Environment and example synchronization")
    visitor = _EnvLookupVisitor()
    for source in ROOT.rglob("*.py"):
        if any(part in {".venv", "__pycache__", "out"} for part in source.parts):
            continue
        visitor.visit(ast.parse(source.read_text(encoding="utf-8"), filename=str(source)))
    system_keys = {"LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"}
    missing = sorted(visitor.keys - system_keys - _env_example_keys())
    if missing:
        report.failed(".env.example is missing direct os.getenv/os.environ.get keys: " + ", ".join(missing))
    else:
        report.passed(f"{len(visitor.keys - system_keys)} direct environment lookups are documented in .env.example")


def _fixture(command: list[str], label: str) -> None:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if proc.returncode:
        raise RuntimeError(f"{label} failed: {proc.stderr[-1600:]}")


def audit_filtergraph(report: AuditReport) -> None:
    import config
    import editor

    report.section("3/5 FFmpeg filtergraph mathematical safety")
    try:
        with tempfile.TemporaryDirectory(prefix="youtube-audit-") as directory:
            work = Path(directory)
            video, voice = work / "block.mp4", work / "voice.wav"
            ffmpeg = config.resolve_ffmpeg()
            _fixture([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=360x640:r=30", "-t", "4", "-pix_fmt", "yuv420p", str(video)], "video fixture")
            _fixture([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=44100", "-t", "52", str(voice)], "audio fixture")
            for n_blocks in (6, 9, 12):
                content = n_blocks * 4.0 - config.TAIL_HOLD
                durations = [4.0] * (n_blocks - 1) + [4.0 - config.TAIL_HOLD]
                boundaries = [round(sum(durations[:index]), 3) for index in range(1, n_blocks)]
                coverage = [[
                    {"duration": 1.333, "quadrant": "top_left"},
                    {"duration": 1.334, "quadrant": "center"},
                    {"duration": 1.333, "quadrant": "bottom_right"},
                ] for _ in range(n_blocks)]
                graph = editor.build_filtergraph(
                    n_blocks, [], False, boundaries=boundaries, block_durations=durations,
                    target_duration=content, quadrants=["top_left"] * n_blocks,
                    transitions_enabled=False, coverage=coverage,
                )
                required = ("gte(time,", "*lt(time,", "clip(iw*", "clip(ih*", "iw-(iw/zoom)", "ih-(ih/zoom)")
                absent = [item for item in required if item not in graph]
                if absent or "xfade=" in graph:
                    raise RuntimeError(f"{n_blocks}-block graph lost guards or reintroduced crossfade: " + ", ".join(absent))
                graph_path = work / f"filtergraph-{n_blocks}.txt"
                graph_path.write_text(graph, encoding="utf-8")
                command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
                for _ in range(n_blocks):
                    command.extend(["-i", str(video)])
                command.extend(["-i", str(voice), "-/filter_complex", str(graph_path), "-map", "[vout]", "-map", "[aout]", "-t", "0.25", "-f", "null", "-"])
                _fixture(command, f"{n_blocks}-block FFmpeg filtergraph parse")
        report.passed("6/9/12-block graphs retain hard cuts, half-open windows, live clamps, and parse with -f null")
    except Exception as exc:
        report.failed(f"FFmpeg graph failed: {type(exc).__name__}: {exc}")


def audit_veo_sanitizer(report: AuditReport) -> None:
    from providers.video.vertex_veo import MAX_PROMPT_LENGTH, VertexVeoProvider

    report.section("4/5 Veo RAI sanitizer")
    risky = "Cancer blood NEEDLE puncture wound cut " + ("unrelated detail " * 100)
    clean = VertexVeoProvider.sanitize_prompt(risky)
    forbidden = [term for term in ("cancer", "blood", "needle", "puncture", "wound", "cut") if re.search(rf"\b{term}\b", clean, re.IGNORECASE)]
    if forbidden or len(clean) > MAX_PROMPT_LENGTH:
        report.failed(f"sanitizer left {forbidden or 'an overlength prompt'} (length={len(clean)})")
    else:
        report.passed(f"risk terms replaced and sanitized prompt is {len(clean)}/{MAX_PROMPT_LENGTH} characters")


def _attribute_path(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def audit_service_boundary(report: AuditReport) -> None:
    report.section("5/5 Service and generator AST network boundary")
    targets = [ROOT / "generator.py", ROOT / "services"]
    violations: list[str] = []
    forbidden = {"httpx.post", "httpx.get", "requests.get", "requests.post", "aiplatform", "fal.run", "urllib.request.urlopen"}
    for target in targets:
        files = [target] if target.is_file() else list(target.rglob("*.py"))
        for source in files:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [alias.name.split(".")[0] for alias in node.names]
                    if any(name in {"httpx", "requests", "google", "openai", "anthropic", "fal"} for name in names):
                        violations.append(f"{source.relative_to(ROOT)}:{getattr(node, 'lineno', '?')} (provider/network import)")
            for node in ast.walk(tree):
                path = _attribute_path(node.func) if isinstance(node, ast.Call) else ""
                if path in forbidden or path.startswith("aiplatform."):
                    violations.append(f"{source.relative_to(ROOT)}:{getattr(node, 'lineno', '?')} ({path})")
    if violations:
        report.failed("Unauthorized direct provider call(s): " + ", ".join(violations))
    else:
        report.passed("services/ and generator.py contain no provider/network import or direct transport call")


def audit_anchor_and_sfx_contract(report: AuditReport) -> None:
    """Exercise the persisted terminal frame plan and licence fail-closed rule."""
    from pipeline import build_editorial_plan, build_frame_plan
    from services.script_engine import Beat, Script, Shot
    from services.sfx import SfxValidationError, validate_cue_sheet
    from timeline import TimelinePlan
    report.section("6/6 Anchor payoff and licensed SFX contracts")
    timeline = TimelinePlan.for_profile("providers_4s", 24.0)
    shots = [Shot(block=i, beat_index=[1, 1, 2, 3, 4, 5][i - 1], t_start=(i - 1) * 4, t_end=i * 4,
                  subject_id="bridge", start_image_prompt="state", end_image_prompt="state next", motion_prompt="load settles",
                  entry_state="latent", exit_state="peak", dominant_event="cable tension stabilizes", proof_on_screen="cable holds",
                  presentation_mode="contextual_opening_anchor" if i == 1 else ("return_to_contextual_anchor_payoff" if i == 6 else "mechanism"),
                  contextual_anchor_id="ctx_bridge", contextual_anchor_subject_id="bridge", contextual_anchor_kind="structure",
                  mechanism_anchor_id="mech_cable", contextual_anchor_appearance_contract="same bridge identity and cable layout",
                  contextual_anchor_roster_ids=["environment_void", "bridge"], contextual_anchor_sheet_ids=["environment_void", "bridge"],
                  payoff_reason="The stable bridge resolves the final load claim." if i == 6 else "") for i in range(1, 7)]
    script = Script("bridge", [Beat(i, "words") for i in range(1, 6)], shots, timeline=timeline)
    plan = build_frame_plan(script)
    editor = build_editorial_plan(script)
    terminal = plan[-1]
    if terminal["end_frame_id"] is not None or terminal["reference_policy"] != "contextual_anchor_roster_only" or editor["boundaries"][-1]["impact_level"] != "none":
        report.failed("terminal anchor payoff is not roster-only, first-frame-only, calm hard-cut")
    else:
        report.passed("terminal anchor payoff is roster-only, first-frame-only, and calm")
    try:
        validate_cue_sheet([{"cue_id": "bad", "block": 1, "start": 0.1, "end": 0.3, "reason": "visible cable tension", "asset_id": "unknown", "gain_db": -18, "fade_in": .03, "fade_out": .1}], [])
    except SfxValidationError:
        report.passed("SFX cue rejects missing provenance")
    else:
        report.failed("SFX cue accepted an unverified asset")


def audit_decisions_and_llm_sync(report: AuditReport) -> None:
    """Validate ADR memory integrity, LLM instruction synchronization, and MCP configs."""
    report.section("7/7 Decision memory and Multi-LLM rule synchronization")
    from scripts import decision, sync_mcp_configs

    # 1. Decisions
    decisions = decision.parse_decisions()
    if not decisions:
        report.failed("DECISIONS.md is missing or contains no ADR entries.")
    else:
        report.passed(f"DECISIONS.md contains {len(decisions)} parsed architecture decision records")

    # 2. Multi-LLM Instruction Files
    rule_files = ["CLAUDE.md", ".cursorrules", "GEMINI.md", "AGENTS.md", "PROJECT_CONTEXT.md"]
    missing_rules = [rf for rf in rule_files if not (ROOT / rf).is_file()]
    if missing_rules:
        report.failed(f"Missing LLM instruction files: {missing_rules}")
    else:
        report.passed(f"All {len(rule_files)} LLM instruction files are present")

    # Verify no file has obsolete 8x4.0s contract
    obsolete_files = []
    for rf in ["CLAUDE.md", ".cursorrules", "GEMINI.md", "AGENTS.md"]:
        text = (ROOT / rf).read_text(encoding="utf-8")
        if "8 x 4.0-second video blocks" in text or "8 x\n4.0-second" in text:
            obsolete_files.append(rf)
    if obsolete_files:
        report.failed(f"Obsolete fixed-timeline clauses found in: {obsolete_files}")
    else:
        report.passed("All LLM rules agree on dynamic 6–13 block provider-native contract")

    # Verify mandatory git commit and push clause exists in all 5 rule files
    missing_git_push = []
    for rf in rule_files:
        text = (ROOT / rf).read_text(encoding="utf-8")
        if "git push" not in text.lower():
            missing_git_push.append(rf)
    if missing_git_push:
        report.failed(f"Missing mandatory git push clause in rule files: {missing_git_push}")
    else:
        report.passed("All 5 LLM instruction files enforce mandatory git commit & push after modifications")

    # 3. Automatic MCP Sync Check
    try:
        sync_mcp_configs.sync_all()
        report.passed("MCP server configs automatically synced across Antigravity, Codex, Cursor, and Claude")
    except Exception as exc:
        report.failed(f"MCP sync failed: {exc}")


def audit_upload_metadata(report: AuditReport) -> None:
    """Validate YouTube upload metadata pipeline contract and paste-ready format."""
    report.section("8/8 YouTube upload metadata contract")
    import metadata
    from services.script_engine import Script, Beat
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir)
        script = Script(
            topic="Audit Topic",
            beats=[Beat(1, "Beat")],
            shots=[],
            youtube={
                "titles": ["Title A", "Title B", "Title C"],
                "description": "Desc with #shorts",
                "tags": ["tag1", "tag2"],
            },
        )
        txt = metadata.write_metadata(script, out)
        if not txt.is_file() or not (out / "metadata.json").is_file():
            report.failed("metadata.write_metadata did not produce metadata.txt and metadata.json")
            return
        content = txt.read_text(encoding="utf-8")
        if "BASLIK SECENEKLERI" in content and "ETIKETLER" in content:
            report.passed("metadata.txt formats valid paste-ready upload contract")
        else:
            report.failed("metadata.txt missing required upload sections")


def main() -> int:
    os.chdir(ROOT)
    report = AuditReport()
    print(f"{Color.CYAN}YouTube provider architecture audit{Color.RESET}\nroot: {ROOT}")
    checks = (
        audit_provider_contracts,
        audit_env_sync,
        audit_filtergraph,
        audit_veo_sanitizer,
        audit_service_boundary,
        audit_anchor_and_sfx_contract,
        audit_decisions_and_llm_sync,
        audit_upload_metadata,
    )
    for check in checks:
        try:
            check(report)
        except Exception as exc:
            report.failed(f"{check.__name__} crashed: {type(exc).__name__}: {exc}")
    print("\n" + (f"{Color.GREEN}AUDIT PASSED{Color.RESET}" if not report.failures else f"{Color.RED}AUDIT FAILED{Color.RESET}"))
    print(f"checks failed: {len(report.failures)}; warnings: {len(report.warnings)}")
    return 0 if not report.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

