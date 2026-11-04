"""Skill-guided screenplay I/O with explicit offline simulation fixtures.

Live failures never fall back to engine-authored narrative. Creative direction
comes exclusively from the loaded skills and the authoring model.
"""
from __future__ import annotations
import asyncio
import copy
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from engine.services.text_sanitizer import sanitize_spoken_text

GENRE_CATASTROPHE = "catastrophe"
SIMULATION_FIXTURE = Path(__file__).resolve().parents[2] / "examples" / "fixtures" / "narrative_simulation.json"

@dataclass(frozen=True)
class GenreArchetype:
    slug: str
    display_name: str
    protagonist_role: str = ""
    tangible_metrics: str = ""
    diegetic_framing: str = ""
    beats_16_9: list = field(default_factory=list)
    beats_9_16: list = field(default_factory=list)

_ARCHETYPES = {slug: GenreArchetype(slug, name) for slug,name in {
    "catastrophe":"Procedural Catastrophe / Mega-Disaster", "sci_fi":"Sci-Fi / Deep Space", "cyberpunk":"Cyberpunk / Infiltration", "deep_sea":"Deep-Sea / Submarine", "survival_horror":"Survival Horror / Post-Apocalyptic", "medieval_siege":"Historical / Medieval Siege"}.items()}

def detect_genre_archetype(genre: str) -> GenreArchetype:
    normalized = (genre or "").lower().strip()
    aliases = {
        "catastrophe": ("catastrophe", "disaster", "volcano", "tsunami", "asteroid", "earthquake"),
        "sci_fi": ("space", "sci-fi", "sci_fi", "scifi", "alien", "cosmic"),
        "cyberpunk": ("cyber", "punk", "hack", "infiltrat"),
        "deep_sea": ("sea", "ocean", "submarine", "underwater"),
        "medieval_siege": ("medieval", "castle", "siege", "knight", "fantasy"),
    }
    slug = next((key for key, terms in aliases.items() if any(term in normalized for term in terms)), "survival_horror")
    return _ARCHETYPES[slug]

def snap_to_veo_duration(duration: float) -> float:
    from engine.providers.flow_contract import default_capabilities
    return min(default_capabilities().supported_native_durations, key=lambda value: abs(value - duration))

def standardize_catastrophe_title(title: str) -> str:
    """Normalize punctuation without inventing events, quantities or locations."""
    title = (title or "").strip()
    if not title:
        raise ValueError("A non-empty production title is required")
    return title.rstrip("?.!") + "?" if re.match(r"what\s+if\s", title, re.I) else title

def format_catastrophe_title(threat: str, number: int | str, location: str) -> str:
    if not str(threat).strip() or not str(location).strip():
        raise ValueError("Explicit threat, quantity and location are required")
    return f"What if {number} {threat} Hit {location}?"

def is_catastrophe_title(title: str) -> bool:
    return bool(re.match(r"what\s+if\s+.+", (title or "").strip(), re.I))

def build_llm_genre_system_prompt(title: str, genre: str, duration: int, aspect: str = "16:9") -> str:
    from engine.services.skill_loader import get_skill_loader
    return get_skill_loader().build_unified_system_prompt(title=title,genre=genre,duration=duration,aspect=aspect)

def build_llm_catastrophe_system_prompt(title: str, duration: int = 300, aspect: str = "16:9") -> str:
    return build_llm_genre_system_prompt(title, "catastrophe", duration, aspect)

def load_simulation_scenes(genre: str, duration: int, aspect: str) -> list[dict[str, Any]]:
    """Load external fixtures only after an explicit simulation request."""
    if duration <= 0:
        raise ValueError("duration must be positive")
    data = json.loads(SIMULATION_FIXTURE.read_text(encoding="utf-8"))
    fixture_genres = {"catastrophe":"catastrophe", "sci_fi":"Sci-Fi", "cyberpunk":"cyberpunk", "deep_sea":"deep sea", "survival_horror":"survival horror", "medieval_siege":"medieval siege"}
    key = f"{fixture_genres[detect_genre_archetype(genre).slug]}|{aspect}"
    scenes = copy.deepcopy(data["scenarios"][key])
    total = sum(float(scene["duration"]) for scene in scenes)
    for scene in scenes:
        scene["duration"] = float(scene["duration"]) * duration / total
        scene["simulation_only"] = True
    return scenes

def screenplay_schema(scene_count: int) -> dict[str, Any]:
    """Describe data interchange; visual values must be supplied by the author."""
    fields = {name: {"type":"string"} for name in ("id","narration","visual_prompt","motion_prompt","micro_math")}
    fields.update({"scene_number":{"type":"integer"}, "duration":{"type":"number","exclusiveMinimum":0},
        "is_data_broll":{"type":"boolean"}, "template_name":{"type":"string"},
        "data_payload":{"type":"object","additionalProperties":True}})
    return {"type":"object","properties":{"act_summary":{"type":"string"},"scenes":{"type":"array","minItems":scene_count,"maxItems":scene_count,"items":{"type":"object","properties":fields,"required":["id","narration","visual_prompt","motion_prompt","duration","micro_math"]}}},"required":["scenes"]}

async def _generate_script_async(title: str, genre: str, duration: int, aspect: str, llm_provider: Any, skill_loader: Any = None) -> list[dict[str,Any]]:
    system_prompt = skill_loader.build_unified_system_prompt(title=title,genre=genre,duration=duration,aspect=aspect) if skill_loader is not None else build_llm_genre_system_prompt(title,genre,duration,aspect)
    payload_schema_path = Path(__file__).resolve().parents[1] / "motion_graphics" / "payload_schema.json"
    payload_schema = json.loads(payload_schema_path.read_text(encoding="utf-8"))
    system_prompt += "\nB-roll data interchange schema (template_name and data_payload):\n" + json.dumps(payload_schema)

    scene_count = max(5, math.ceil(duration / 8))
    if genre.lower() == "catastrophe" and scene_count == 38:
        chunk_ranges = [(0, 6), (6, 16), (16, 27), (27, 34), (34, 38)]
        act_names = [f"Act {c + 1} of 5" for c in range(5)]
    else:
        chunks = min(5, scene_count)
        chunk_ranges = [(scene_count * c // chunks, scene_count * (c + 1) // chunks) for c in range(chunks)]
        act_names = [f"Act {c + 1} of {len(chunk_ranges)}" for c in range(len(chunk_ranges))]

    result: list[dict[str, Any]] = []
    for chunk, (start, end) in enumerate(chunk_ranges):
        topic = json.dumps({
            "title": title,
            "genre": genre,
            "aspect": aspect,
            "target_duration": duration,
            "act_number": chunk + 1,
            "act_description": act_names[chunk],
            "chunk": chunk + 1,
            "chunk_count": len(chunk_ranges),
            "scene_start": start + 1,
            "scene_end": end,
            "act_instructions": (
                "Maintain unbroken chronological continuity from preceding scenes. "
                "Use the loaded production rules and screenplay contract for POV, visual safety, materials, and CTA placement. "
                "Do not invent or infer a different act policy."
            ),
            "previous_scenes": result,
        }, ensure_ascii=False)
        data = await llm_provider.generate_script(topic=topic,system_prompt=system_prompt,schema=screenplay_schema(end-start))
        scenes = data.get("scenes", [])
        if len(scenes) != end-start:
            raise ValueError("Authoring model returned an incomplete screenplay chunk")
        for i, scene in enumerate(scenes,start+1):
            if not isinstance(scene, dict):
                raise ValueError(f"Scene {i}: scene must be an object")
            if any(not isinstance(scene.get(key), str) or not scene[key].strip()
                   for key in ("narration", "visual_prompt")):
                raise ValueError(f"Scene {i}: narration and visual_prompt are required")
            if any(not isinstance(scene.get(key), str) for key in ("motion_prompt", "micro_math")):
                raise ValueError(f"Scene {i}: motion_prompt and micro_math must be strings")
            value = scene.get("duration")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"Scene {i}: positive finite duration required")
            if "is_data_broll" in scene and not isinstance(scene["is_data_broll"], bool):
                raise ValueError(f"Scene {i}: is_data_broll must be a boolean")
            if "template_name" in scene and not isinstance(scene["template_name"], str):
                raise ValueError(f"Scene {i}: template_name must be a string")
            if "data_payload" in scene and not isinstance(scene["data_payload"], dict):
                raise ValueError(f"Scene {i}: data_payload must be an object")
            scene["id"] = f"scene_{i:02d}"
            scene["scene_number"] = i
            scene["narration"] = sanitize_spoken_text(scene["narration"])
            if not scene["narration"].strip():
                raise ValueError(f"Scene {i}: narration is empty after spoken-text sanitization")
            is_broll = scene.get("is_data_broll") or any("[DATA_BROLL]" in scene[key].upper()
                for key in ("visual_prompt", "motion_prompt"))
            if is_broll and (not scene.get("template_name") or not isinstance(scene.get("data_payload"), dict) or not scene["data_payload"]):
                raise ValueError(f"Scene {i}: B-roll requires template_name and non-empty data_payload")
            if is_broll:
                from engine.services.remotion_bridge import validate_broll_payload
                try:
                    scene["data_payload"] = validate_broll_payload(scene["template_name"], scene["data_payload"])
                except Exception as broll_err:
                    raise ValueError(f"Scene {i}: invalid B-roll payload") from broll_err

        result.extend(scenes)
    return result

def generate_5act_script(title: str, genre: str = "catastrophe", duration: int = 300, aspect: str = "16:9", llm_provider: Any = None, *, simulation: bool = False, skill_loader: Any = None) -> list[dict[str,Any]]:
    if simulation:
        return load_simulation_scenes(genre,duration,aspect)
    if llm_provider is None:
        raise RuntimeError("Live screenplay authoring requires an LLM provider; use explicit dry-run simulation for offline tests")
    if duration <= 0:
        raise ValueError("duration must be positive")
    return asyncio.run(_generate_script_async(title,genre,duration,aspect,llm_provider,skill_loader))

def generate_catastrophe_scenes(title: str, duration: int = 300, aspect: str = "16:9", *, llm_provider: Any = None, simulation: bool = False) -> list[dict[str,Any]]:
    return generate_5act_script(title,"catastrophe",duration,aspect,llm_provider,simulation=simulation)

def generate_universal_scenes(title: str, genre: str = "catastrophe", duration: int = 300, aspect: str = "16:9", *, llm_provider: Any = None, simulation: bool = False) -> list[dict[str,Any]]:
    return generate_5act_script(title,genre,duration,aspect,llm_provider,simulation=simulation)

class UniversalNarrativeEngine:
    def __init__(self, skill_loader: Any = None, llm_provider: Any = None) -> None:
        self.skill_loader = skill_loader
        self.llm_provider = llm_provider
    def generate_screenplay(self,title: str,genre: str = "catastrophe",duration: int = 300,aspect: str = "16:9",voice_provider: str = "deepgram",dry_run: bool = False,**kwargs: Any) -> list[dict[str,Any]]:
        return generate_5act_script(title,genre,duration,aspect,self.llm_provider,simulation=dry_run,skill_loader=self.skill_loader)

__all__ = ["GENRE_CATASTROPHE","GenreArchetype","UniversalNarrativeEngine","detect_genre_archetype","generate_catastrophe_scenes","generate_universal_scenes","generate_5act_script","build_llm_genre_system_prompt","build_llm_catastrophe_system_prompt","standardize_catastrophe_title","format_catastrophe_title","is_catastrophe_title","snap_to_veo_duration","load_simulation_scenes","screenplay_schema"]
