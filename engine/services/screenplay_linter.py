"""Report screenplay contract violations without inventing narrative or visual content.

Creative repair belongs to the skill-guided authoring model. The compatibility
helpers preserve input and report defects; they never substitute prose.
"""
from __future__ import annotations
import copy
import logging
import re
from typing import Any
logger = logging.getLogger(__name__)

_VEO_BANNED = re.compile(
    r"\b("
    r"mirror\s+(?:reflection|reflecting|face)|face\s+in\s+(?:the\s+)?(?:cracked\s+)?mirror"
    r"|rearview\s+mirror\s+face|reflects?\s+(?:your\s+)?(?:terrified\s+)?face"
    r"|reflection\s+of\s+(?:your\s+)?face"
    r"|(?:smart)?phone\s+screen\s+(?:showing|displaying|reading)"
    r"|digital\s+(?:readout|display|clock|thermometer|gauge|screen)\s*(?:showing|reading|with)?"
    r"|readable\s+(?:numbers|digits)|numeric\s+readout|clock\s+face\s+(?:showing|with\s+numbers?)"
    r"|screen\s+reads\s+[\"']?\d+"
    r"|crowd\s+of\s+people|large\s+crowd|people\s+(?:running|fleeing|screaming)\s+in\s+(?:the\s+)?foreground"
    r"|baked.?in\s+(?:text|subtitle|title|watermark|logo)"
    r"|text\s+(?:overlay|reading|graphic)|subtitles\s+reading|sign\s+that\s+reads|words\s+reading"
    r"|logo\s+on\s+screen|watermark"
    r"|warning\s+sign\s+(?:that\s+)?(?:reads?|says?)|written\s+text\s+(?:on|in)\s+frame"
    r"|(?:analog\s+)?(?:pressure\s+)?gauge(?:s)?(?:\s+(?:with\s+needles?|needle\s+thrashing|in\s+emergency\s+lighting))?"
    r"|(?:analog\s+)?dial(?:s)?(?:\s+on\s+(?:the\s+)?(?:elevator\s+)?wall)?"
    r"|(?:mercury|pressure|liquid|manometer|barometer)\s+column(?:s)?|column(?:s)?\s+visibly\s+climbing"
    r"|needle(?:s)?\s+(?:thrashing|pointing|twitching|in\s+red\s+emergency\s+lighting)"
    r"|temperature\s+strip(?:s)?(?:\s+changing\s+color(?:\s+from\s+bottom\s+to\s+top)?)?"
    r"|manometer(?:s)?"
    r"|scale\s+marking(?:s)?"
    r"|telemetry\s+(?:visuals|screen|display)|instrument\s+panels?|cockpit\s+instruments?|dashboard\s+instruments?"
    r")\b",
    re.IGNORECASE,
)

_HUMAN_FEATURE_BANNED = re.compile(
    r"\b("
    r"character\s+face|portrait(?:s)?|smiling|smiles?|teeth|eyes?|lips?|mouth|pupil(?:s)?"
    r"|(?:close-?up\s+(?:of\s+)?)?face(?:s)?"
    r"|facial\s+(?:expression|features?)|staring\s+eyes|human\s+face"
    r"|person(?:'s)?\s+face|terrified\s+face|human(?:s)?|person(?:s)?|hands?|limbs?|crowd(?:s)?"
    r")\b",
    re.IGNORECASE,
)

_CTA_PATTERN = re.compile(
    r"\b(subscribe|turn\s+on\s+notifications|comment\s+below"
    r"|follow\s+(?:our|the)\s+channel|like\s+and\s+subscribe"
    r"|join\s+our\s+(?:expedition|channel)|smash\s+(?:the\s+)?like)\b",
    re.IGNORECASE,
)


_VALID_POV_STARTERS = ("You ", "Your ", "You're ", "You've ", "You'd ", "You'll ", "You,")

def _fix_pov(narration: str, scene_index: int) -> tuple[str, str | None]:
    if not narration.strip():
        return narration, f"Scene {scene_index + 1}: ERROR -- narration is empty; model-authored repair required."
    if not narration.startswith(_VALID_POV_STARTERS):
        return narration, f"Scene {scene_index + 1}: ERROR -- narration violates second-person POV; model-authored repair required."
    return narration, None

def _strip_premature_cta(narration: str, scene_index: int, total_scenes: int) -> tuple[str, str | None]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", narration) if s.strip()]
    forbidden = sentences[:-1] if scene_index == total_scenes - 1 else sentences
    if any(_CTA_PATTERN.search(s) for s in forbidden):
        return narration, f"Scene {scene_index + 1}: ERROR -- premature CTA; model-authored repair required."
    return narration, None

def _strip_veo_violations(prompt: str, scene_index: int) -> tuple[str, str | None]:
    if not prompt.strip():
        return prompt, f"Scene {scene_index + 1}: ERROR -- visual_prompt is empty."
    if "[DATA_BROLL]" in prompt.upper():
        return prompt, None
    positive = prompt.partition("--no")[0]
    # Only suppress a directly negated match. Ambiguous conjunctions remain
    # violations so a positive request cannot hide behind an earlier negation.
    def has_positive_match(pattern: re.Pattern[str]) -> bool:
        for match in pattern.finditer(positive):
            prefix = positive[max(0, match.start() - 24):match.start()]
            if not re.search(r"\b(?:no|without|zero|gloved|protective|hazmat)\s+$", prefix, re.IGNORECASE):
                return True
        return False

    if has_positive_match(_VEO_BANNED) or has_positive_match(_HUMAN_FEATURE_BANNED):
        return prompt, f"Scene {scene_index + 1}: ERROR -- Veo visual guardrail violation; model-authored repair required."
    return prompt, None

def sanitize_prompt(prompt: str) -> str:
    """Normalize surrounding whitespace only; preserve the author's visual instructions."""
    return prompt.strip()

def _warn_missing_micro_math(scene: dict[str, Any], scene_index: int) -> str | None:
    if not str(scene.get("micro_math", "")).strip():
        return f"Scene {scene_index + 1}: WARNING -- micro_math is empty; model-authored metric required."
    return None

def lint_scenes(scenes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Return an unchanged deep copy and actionable diagnostics, never fabricated repairs."""
    result = copy.deepcopy(scenes)
    diagnostics: list[str] = []
    for i, scene in enumerate(result):
        narration = str(scene.get("narration", ""))
        for diagnostic in (
            _fix_pov(narration, i)[1],
            _strip_premature_cta(narration, i, len(result))[1],
            _strip_veo_violations(str(scene.get("visual_prompt", "")), i)[1],
            _warn_missing_micro_math(scene, i),
        ):
            if diagnostic:
                diagnostics.append(diagnostic)
        if i:
            current = set(re.findall(r"\w+", narration.lower()))
            previous = set(re.findall(r"\w+", str(result[i-1].get("narration", "")).lower()))
            if current and previous and len(current & previous) / max(len(current), len(previous)) > .8:
                diagnostics.append(f"Scene {i + 1}: WARNING -- repetitive narration; model-authored revision required.")
    return result, diagnostics
