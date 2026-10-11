"""Long-form narrative script engine."""

import json
from dataclasses import replace
from typing import Any
import config
from services.script_engine import Beat, Script, Shot, TRANSITION_KINDS, JOURNEY_PHASES, MARKER_TYPES, PRESENTATION_MODES, CONTEXTUAL_ANCHOR_KINDS, SCALES, _DOMAIN_SCALES
from providers.base import BaseLLMProvider, ProviderError

class LongformEngine:
    """Handles episodic scripting (e.g., 4-6 episodes / 25+ beats)."""
    
    def __init__(self, llm: BaseLLMProvider, lang: str = "en", timeline=None, mode=None):
        self.llm = llm
        self.lang = lang
        self.timeline = timeline
        self.mode = mode

    @property
    def target_count(self) -> int:
        if self.timeline and getattr(self.timeline, "block_count", 0) >= 4:
            return int(self.timeline.block_count)
        return 28

    @property
    def schema(self) -> dict[str, Any]:
        count = self.target_count
        beat = {
            "type": "object",
            "properties": {
                "index": {"type": "integer"}, "text": {"type": "string", "minLength": 1},
                "role": {"type": "string"}, "emphasis": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["index", "text"], "additionalProperties": True,
        }
        shot = {
            "type": "object",
            "properties": {
                "beat_index": {"type": "integer", "minimum": 1, "maximum": count}, 
                "subject_id": {"type": "string", "minLength": 1}, 
                "subject_description": {"type": "string", "minLength": 1},
                "start_image_prompt": {"type": "string", "minLength": 1}, 
                "end_image_prompt": {"type": "string", "minLength": 1},
                "motion_prompt": {"type": "string", "minLength": 1}, 
                "target_quadrant": {"type": "string"}, 
                "end_target_quadrant": {"type": "string"},
                "visual_domain": {"type": "string", "enum": sorted(_DOMAIN_SCALES)}, 
                "scale": {"type": "string", "enum": list(SCALES)},
                "journey_phase": {"type": "string", "enum": list(JOURNEY_PHASES)}, 
                "transition_kind": {"type": "string", "enum": list(TRANSITION_KINDS)},
                "camera_angle": {"type": "string"}, "camera_vector": {"type": "string"}, 
                "detail_target": {"type": "string"},
                "continuity_anchor": {"type": "string", "minLength": 1}, 
                "entry_state": {"type": "string", "minLength": 1},
                "exit_state": {"type": "string", "minLength": 1}, 
                "dominant_event": {"type": "string", "minLength": 1}, 
                "proof_on_screen": {"type": "string", "minLength": 1}, 
                "location_id": {"type": "string", "minLength": 1},
                "marker_type": {"type": "string", "enum": list(MARKER_TYPES)}, 
                "endpoint_mode": {"type": "string", "enum": ["first_last", "first_only"]}, 
                "presentation_mode": {"type": "string", "enum": list(PRESENTATION_MODES)},
                "impact_offset_seconds": {"type": "number", "minimum": 0.2, "maximum": 3.8}
            },
            "required": ["beat_index", "subject_id", "subject_description", "start_image_prompt", "end_image_prompt", "motion_prompt", "target_quadrant", "visual_domain", "scale", "journey_phase", "transition_kind", "camera_angle", "detail_target", "continuity_anchor", "entry_state", "exit_state", "dominant_event", "proof_on_screen", "location_id", "marker_type", "endpoint_mode", "presentation_mode", "impact_offset_seconds"],
            "additionalProperties": True,
        }
        youtube = {
            "type": "object",
            "properties": {
                "titles": {"type": "array", "minItems": 3, "maxItems": 5, "items": {"type": "string"}},
                "description": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["titles", "description", "tags"],
            "additionalProperties": True,
        }
        return {
            "type": "object",
            "properties": {
                "beats": {"type": "array", "minItems": count, "maxItems": count, "items": beat},
                "shots": {"type": "array", "minItems": count, "maxItems": max(count, 40), "items": shot},
                "youtube": youtube,
            },
            "required": ["beats", "shots"],
            "additionalProperties": False,
        }

    def system_prompt(self, topic: str | None = None) -> str:
        count = self.target_count
        if (self.mode and self.mode.name == "explorer") or getattr(config, "IS_EXPLORER_FORMAT", False) or getattr(config, "LONGFORM_MODE", False):
            from services.character import get_active_character
            char = get_active_character()
            w1_shot = max(3, (count * 2) // 7)
            w2_shot = min(count - 2, (count * 5) // 7)
            mid_shot = max(2, (count // 2) + 1)
            truth_section = ""
            if topic:
                try:
                    from services.historical_research import get_historical_truth_sheet
                    sheet = get_historical_truth_sheet(topic)
                    truth_section = f"\n\n{sheet.summary_for_prompt()}"
                except Exception:
                    pass
            return (
                f"Write an English 16:9 widescreen long-form investigative explorer documentary "
                f"({count} beats total, exactly {count} shots) hosted by {char.name}, an adventurous female chronological time-traveler and field explorer. "
                "Structure the story in five chronological dramatic phases: (1) Hook/Cold Open, 0-10 seconds, open on a striking anomaly or urgent question; "
                "(2) Context & Sensory Immersion, 10-30 seconds, ground the viewer in period-specific place, weather, sounds, materials, and labor; "
                "(3) Rising Investigation, 30-60 seconds, reveal evidence and competing explanations; "
                "(4) Turning Point/Core Discovery, 60-90 seconds, deliver the decisive evidence; "
                "(5) Legacy & Reflection, 90-120 seconds, connect the supported historical conclusion to the present. "
                "Scale these beats proportionally for shorter timelines, keep chronology and evidence accurate, and give every shot a distinct character state, "
                "time-of-day/light cue, and dramatic tempo. The opening narration must begin with a direct viewer-facing question or anomaly. "
                f"Tone is immersive, first-person ('I arrived at...', 'Look at this clue...', 'Notice these ancient tool marks...'), engaging, and cinematic. "
                f"She wears her signature temporal chronometer wrist device and era-appropriate camouflage wardrobe. "
                f"CRITICAL HYBRID FORMAT — INCLUDE BOTH SOLO HOST SEGMENTS AND HISTORICAL EYEWITNESS INTERVIEWS, CLEARLY DISTINGUISHED: "
                f"1) Solo Time-Traveler Host Beats (role='host_nova'): {char.name} investigates the ancient monument first-hand; she appears on-camera (A-Roll) in Shot 1 (opening arrival), Shot {mid_shot} (midpoint turning point), and Shot {count} (closing verdict) with natural speech articulation and full headroom. "
                f"2) Historical Eyewitness Field Interviews (role='witness:<Historical Name & Era>'): At Shot {w1_shot} and Shot {w2_shot}, {char.name} interviews an authentic historical figure from that era (e.g. a royal architect, master stonemason, or classical historian like Herodotus) who speaks in first person with a distinct voice and period-accurate attire. Preceding question beats use role='host_question'. "
                f"3) Cinematic B-roll (all other shots): historically grounded environments, artifacts, and purposeful period labor when called for by the evidence; keep Nova out of these shots unless the shot explicitly identifies her. "
                "Use National Geographic / BBC Earth 35mm photorealism for period environments and archaeological details. "
                "Never use vague 'ancient clothing': specify fabric, period cut, stitching, fastenings, and footwear. Avoid passive posing; show meaningful physical action or visible atmospheric motion. "
                "For pre-industrial scenes, use only documented period tools and human/animal power; never introduce modern cranes, bolts, machinery, or synthetic rope. "
                f"Each beat should be punchy and concise (around 10-12 words) so each beat fits naturally within its 4-second shot window. "
                f"Total narration across all {count} beats should be around {int(count * 11)} words (approx {int(count * 4)} seconds total speech). "
                f"Provide exactly {count} distinct visual shots (one per beat). "
                "Include a youtube object with titles, description, and tags."
                f"{truth_section}"
            )
        return (
            f"Write a {self.lang} vertical Zack D. Films-style longform episodic documentary ({count} beats total). "
            f"Each beat should be punchy and around 15-20 words. "
            f"Provide exactly {count} visual shots (one for each beat). "
            f"Each shot must vividly describe the scene, matching the provided schema. "
            f"Ensure characters have closed/neutral mouths and there is no text/dialogue. "
            f"Include a youtube object with titles, description, and tags."
        )

    async def generate(self, topic: str) -> Script:
        if self.llm.__class__.__module__.endswith(".vertex_gemini"):
            print("  [LLM] Vertex AI disabled for this production; using the local evidence-bound Explorer screenplay engine.")
            return self._fallback_script(topic)
        feedback = ""
        attempts = 3
        count = self.target_count
        for attempt_idx in range(attempts):
            try:
                payload = await self.llm.generate_script(topic, self.system_prompt(topic) + feedback, self.schema)
                script = self._assemble(topic, payload)
                
                # Simplified validation for longform to avoid rigid Shorts constraints
                problems = []
                if len(script.beats) != count:
                    problems.append(f"Expected exactly {count} beats, got {len(script.beats)}")
                if len(script.shots) < count:
                    problems.append(f"Expected at least {count} shots, got {len(script.shots)}")
                    
                if not problems:
                    return script
                    
                feedback = f"\nReturn the corrected JSON object. Repair these violations: {'; '.join(problems)}"
            except Exception as exc:
                print(f"  [LLM] Notice: remote script provider error ({exc}); using authoritative Explorer narrative engine.")
                return self._fallback_script(topic)
            
        return self._fallback_script(topic)

    def _fallback_script(self, topic: str) -> Script:
        count = self.target_count
        try:
            from services.screenplay import generate_dynamic_screenplay
            return generate_dynamic_screenplay(topic, self.timeline, lang=self.lang, target_blocks=count)
        except Exception:
            from services.explorer_engine import build_explorer_script
            return build_explorer_script(topic, self.timeline, self.lang)

    def _assemble(self, topic: str, payload: dict[str, Any]) -> Script:
        beats = [Beat(int(item.get("index", i + 1)), str(item.get("text") or ""), str(item.get("role") or "host_nova"), list(item.get("emphasis") or [])) for i, item in enumerate(payload.get("beats") or [])]
        is_explorer = (self.mode and self.mode.name == "explorer") or getattr(config, "IS_EXPLORER_FORMAT", False) or getattr(config, "LONGFORM_MODE", False)
        if is_explorer:
            from services.character import detect_era
            from services.prompt_compiler import apply_ancient_equipment_rule, apply_clothing_lock, apply_movement_lock
            era = detect_era(topic)
        shots = []
        for index, item in enumerate(payload.get("shots") or [], start=1):
            merged = dict(item)
            # Assign artificial block indices and timestamps
            merged.update({"block": index, "t_start": (index - 1) * 4.0, "t_end": index * 4.0})
            merged["visual_domain"] = merged.get("visual_domain") or ("archaeology" if is_explorer else "mechanical")
            if is_explorer:
                merged["endpoint_mode"] = "first_only"
                for field in ("start_image_prompt", "end_image_prompt"):
                    if merged.get(field):
                        prompt = str(merged[field])
                        if any(token in prompt.casefold() for token in ("nova", "host", "person", "woman", "man", "crew", "sailor", "soldier", "worker")):
                            prompt = apply_clothing_lock(prompt, era=era)
                        merged[field] = apply_ancient_equipment_rule(prompt)
                if merged.get("motion_prompt"):
                    motion = apply_ancient_equipment_rule(str(merged["motion_prompt"]))
                    merged["motion_prompt"] = apply_movement_lock(motion)
            shots.append(Shot.from_dict(merged))
            
        timeline = self.timeline
        if timeline:
            footage = len(shots) * 4.0
            timeline = replace(
                timeline,
                block_count=len(shots),
                keyframe_count=len(shots) + 1,
                shot_durations=tuple(4.0 for _ in range(len(shots))),
                total_duration=footage,
                minimum_duration=footage,
                target_duration=footage,
                content_duration=max(0.0, footage - 1.5),
            )
            
        youtube = payload.get("youtube") if isinstance(payload.get("youtube"), dict) else None
        resolved_mode = self.mode.name if self.mode else ("explorer" if is_explorer else "anatomical")
        return Script(topic, beats, shots, self.lang, timeline, mode=resolved_mode, youtube=youtube)

