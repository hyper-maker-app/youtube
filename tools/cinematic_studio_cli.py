#!/usr/bin/env python3
"""Grok Imagine Cinematic Studio CLI — Primary Engine: Google Flow CDP + Remotion + Deepgram + FFmpeg."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(_TOOLS))
sys.path.insert(0, str(_TOOLS.parent))
_ARCHIVE_TOOLS = _TOOLS.parent / "archive" / "legacy_tools"
if _ARCHIVE_TOOLS.is_dir() and str(_ARCHIVE_TOOLS) not in sys.path:
    sys.path.append(str(_ARCHIVE_TOOLS))

from cli.animatic_commands import register as register_animatic_commands  # noqa: E402
from cli.api_commands import register as register_api_commands  # noqa: E402
from cli.bible_commands import register as register_bible_commands  # noqa: E402
from cli.dna_commands import register as register_dna_commands  # noqa: E402
from cli.files_commands import register as register_files_commands  # noqa: E402
from cli.flow_account_commands import register as register_flow_commands  # noqa: E402
from cli.generation_commands import register as register_generation_commands  # noqa: E402
from cli.ghost_aliases import register_ghost_aliases  # noqa: E402
from cli.grok_cli_commands import register as register_grok_cli_commands  # noqa: E402
from cli.handoff_commands import register as register_handoff_commands  # noqa: E402
from cli.help_ia import ROOT_EPILOG, ROOT_HELP, StudioGroup, apply_help_ia  # noqa: E402
from cli.imagine_commands import register as register_imagine_commands  # noqa: E402
from cli.models_commands import models_app  # noqa: E402
from cli.motion_commands import register as register_motion_commands  # noqa: E402
from cli.nsfw_commands import register as register_nsfw_commands  # noqa: E402
from cli.plugin_commands import register as register_plugin_commands  # noqa: E402
from cli.produce_commands import register as register_produce_commands  # noqa: E402
from cli.quota_commands import register as register_quota_commands  # noqa: E402
from cli.report_commands import register as register_report_commands  # noqa: E402
from cli.sequence_commands import register as register_sequence_commands  # noqa: E402
from cli.sfw_commands import register as register_sfw_commands  # noqa: E402
from cli.studio_commands import register as register_studio_commands  # noqa: E402
from cli.tui_commands import register as register_tui_commands  # noqa: E402
from cli.wave_a_commands import register as register_wave_a_commands  # noqa: E402
from cli.web_commands import register as register_web_commands  # noqa: E402
from cli.web_react_commands import register as register_web_react_commands  # noqa: E402

app = typer.Typer(
    name="cinematic-studio", help=ROOT_HELP, epilog=ROOT_EPILOG, cls=StudioGroup,
    add_completion=False, rich_markup_mode="rich", no_args_is_help=True,
)

dna_app = typer.Typer(help="Character DNA, Identity Lock handoff, prompt injection")
seq_app = typer.Typer(help="Long-form extend/stitch, chain QA, health (1.0 cost · 1.5 audio)")
quota_app = typer.Typer(help="Quota estimation, budgeting, optimization")
nsfw_app = typer.Typer(help="[Legacy Grok Imagine] NSFW batch planning, extension, daily reports")
extend_app = typer.Typer(help="[Legacy Grok Imagine] Sensual sequence extension 30–120s+")
sfw_app = typer.Typer(help="[Legacy Grok Imagine] SFW hero-first batches + Reference Curator routing")
imagine_app = typer.Typer(help="[Legacy Grok Imagine] xAI Imagine jobs, bridge, agent-handoff")
files_app = typer.Typer(help="[Legacy Grok Imagine] xAI Files API — upload plates, list, get, delete")
handoff_app = typer.Typer(help="Handoff packet validate (identity / sequence / agent-mode)")
animatic_app = typer.Typer(help="Animatic pre-vis and hero promotion")
motion_app = typer.Typer(help="[Primary Engine] Remotion parametric motion graphics B-Roll render commands (60 FPS)")
flow_app = typer.Typer(help="[Primary Engine] Google Flow CDP physical factory & multi-account control")
flow_accounts_app = typer.Typer(help="[Primary Engine] Multi-account pool management and rotation (4 accounts)")

for sub, name in (
    (dna_app, "dna"), (seq_app, "sequence"), (quota_app, "quota"), (models_app, "models"),
    (nsfw_app, "nsfw"), (sfw_app, "sfw"), (imagine_app, "imagine"), (files_app, "files"),
    (handoff_app, "handoff"), (animatic_app, "animatic"), (motion_app, "motion-graphics"),
    (flow_app, "flow"),
):
    app.add_typer(sub, name=name)
nsfw_app.add_typer(extend_app, name="extend")
flow_app.add_typer(flow_accounts_app, name="accounts")

for fn in (
    register_studio_commands, register_bible_commands, register_report_commands,
    register_plugin_commands, register_tui_commands, register_web_commands,
    register_web_react_commands, register_api_commands, register_produce_commands,
    register_generation_commands, register_wave_a_commands, register_grok_cli_commands,
    register_ghost_aliases,
):
    fn(app)
register_dna_commands(dna_app)
register_sequence_commands(seq_app)
register_quota_commands(quota_app)
register_nsfw_commands(nsfw_app, extend_app)
register_sfw_commands(sfw_app)
register_imagine_commands(imagine_app)
register_files_commands(files_app)
register_handoff_commands(handoff_app)
register_animatic_commands(animatic_app)
register_motion_commands(motion_app)
register_flow_commands(flow_accounts_app, flow_app)
apply_help_ia(app)

if __name__ == "__main__":
    app()
