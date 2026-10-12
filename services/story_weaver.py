"""Universal Story-Weaver Engine synthesizing ai-playbooks, Script-Weaver, and HiAPIAI patterns.

Generates episodic, source-grounded documentary screenplay beats with:
1. HiAPIAI Truth Sheet grounding (authentic materials, sensory details, verified facts, negative anachronisms).
2. Script-Weaver 5-Phase Dramatic Flow (Arrival Hook, Context Immersion, Rising Investigation, Turning Point, Legacy & Verdict).
3. ai-playbooks 4-Part Presenter Hook Formula (Subject + Era + Human Context + Central Puzzle).
4. ai-playbooks Active Physical Labor Choreography (quarrying, hauling, chiseling, hoisting, tamping).
5. Four Visual Locks & Motion Contracts (Clothing, Movement, Equipment, Framing).

Strictly AST-clean: Zero network calls, zero provider imports. Operates 100% on in-memory objects.
"""

from __future__ import annotations

import re
from typing import Any

from services.character import CharacterProfile, get_active_character
from services.historical_research import HistoricalTruthSheet
from services.visual_locks import (
    apply_clothing_lock_v2,
    apply_equipment_lock_v2,
    apply_framing_lock_v2,
    apply_movement_lock_v2,
)


class StoryWeaver:
    """Dynamic episodic documentary story generator."""

    def __init__(
        self,
        truth_sheet: HistoricalTruthSheet,
        character: CharacterProfile | None = None,
        total_blocks: int = 8,
        lang: str = "en",
        style_variant: str = "cinematic_photoreal",
    ) -> None:
        self.sheet = truth_sheet
        self.character = character or get_active_character()
        self.total_blocks = max(4, total_blocks)
        self.lang = lang
        self.style_variant = style_variant
        self.era = getattr(truth_sheet, "era", "default")

    def weave(self) -> list[dict[str, Any]]:
        """Synthesize 5-phase episodic beats with Truth Sheet grounding and 4 visual locks."""
        # 1. Distribute total_blocks proportionally across the 5 Script-Weaver phases
        phase_dist = self._calculate_phase_distribution(self.total_blocks)

        # 2. Weave each phase using Truth Sheet facts and ai-playbooks formulas
        raw_beats: list[dict[str, Any]] = []
        raw_beats.extend(self._weave_arrival_hook(phase_dist["arrival_hook"]))
        raw_beats.extend(self._weave_context_immersion(phase_dist["context_immersion"]))
        raw_beats.extend(self._weave_rising_investigation(phase_dist["rising_investigation"]))
        raw_beats.extend(self._weave_turning_point(phase_dist["turning_point"]))
        raw_beats.extend(self._weave_legacy_verdict(phase_dist["legacy_verdict"]))

        # 3. Ensure exact count matches total_blocks
        if len(raw_beats) > self.total_blocks:
            raw_beats = raw_beats[:self.total_blocks]
        elif len(raw_beats) < self.total_blocks:
            # Pad with additional sensory investigation beats
            needed = self.total_blocks - len(raw_beats)
            for k in range(needed):
                raw_beats.insert(-1, self._create_investigation_beat(k + 10))

        # 4. Apply 4 Visual Locks and Motion Contracts across all generated beats
        locked_beats: list[dict[str, Any]] = []
        for i, beat in enumerate(raw_beats):
            beat["index"] = i + 1
            locked_beats.append(self._apply_all_locks(beat, i + 1, self.total_blocks))

        return locked_beats

    def _calculate_phase_distribution(self, total: int) -> dict[str, int]:
        """Distribute total blocks across 5 phases proportionally."""
        if total <= 6:
            return {
                "arrival_hook": 1,
                "context_immersion": 1,
                "rising_investigation": 2,
                "turning_point": 1,
                "legacy_verdict": 1,
            }

        # Weighting: Arrival Hook (15%), Context (22%), Rising (28%), Turning Point (22%), Legacy (13%)
        weights = [0.15, 0.22, 0.28, 0.22, 0.13]
        counts = [max(1, int(round(total * w))) for w in weights]
        diff = total - sum(counts)
        # Allocate discrepancy to rising_investigation (phase 3)
        counts[2] += diff
        return {
            "arrival_hook": counts[0],
            "context_immersion": counts[1],
            "rising_investigation": counts[2],
            "turning_point": counts[3],
            "legacy_verdict": counts[4],
        }

    def _weave_arrival_hook(self, count: int) -> list[dict[str, Any]]:
        """Phase 1: Arrival Hook / In Media Res (ai-playbooks 4-part formula)."""
        loc = self.sheet.location_name or self.sheet.topic
        period = self.sheet.time_period or "ancient antiquity"
        sensory = self.sheet.sensory_details[0] if self.sheet.sensory_details else "airborne mineral dust"
        mat = self.sheet.architecture_and_materials[0] if self.sheet.architecture_and_materials else "monolithic stone"

        # 4-Part Hook Formula: (1) Subject reveal, (2) Historical period, (3) Human context, (4) Central puzzle
        text = (
            f"I just arrived at {loc} during {period}. "
            f"Touching these weathered surfaces, {sensory.lower()}. "
            f"History claims ancient builders shaped this entire complex by hand, "
            f"but looking at {mat}, how did they engineer these tolerances without modern tools?"
        )
        scene = f"Cinematic establishing shot of {loc} under dramatic morning light, host {self.character.name} at threshold"
        action = f"Host {self.character.name} pauses at the perimeter of {loc}, examining {mat} with focused curiosity"
        proof = f"{self.character.name}'s brass temporal chronometer; authentic {mat} at {loc}"

        beats = [{
            "phase": "arrival_hook",
            "role": "host_nova",
            "text": text,
            "emphasis": [loc.split()[-1] if loc else "monument", "tolerances", "tools"],
            "scene": scene,
            "action": action,
            "proof": proof,
            "scale": "medium",
            "lighting": "sharp early morning directional sunlight with atmospheric haze",
            "character_reference": True,
            "is_a_roll": True,
        }]

        if count > 1:
            beats.append({
                "phase": "arrival_hook",
                "role": "narrator",
                "text": f"Across the entire horizon of {loc}, the scale of human ambition is staggering.",
                "emphasis": ["scale", "ambition"],
                "scene": f"Sweeping panoramic establishing view across {loc}",
                "action": f"Camera sweeps across {loc} revealing massive structural perimeter",
                "proof": f"monumental perimeter foundations of {loc}",
                "scale": "wide",
                "lighting": "vast open sky with atmospheric golden hour illumination",
                "character_reference": False,
                "is_a_roll": False,
            })
        return beats

    def _weave_context_immersion(self, count: int) -> list[dict[str, Any]]:
        """Phase 2: Context & Sensory Immersion (period materials, acoustics, weather, textures)."""
        beats: list[dict[str, Any]] = []
        materials = self.sheet.architecture_and_materials or ["monolithic dressed stone"]
        sensory = self.sheet.sensory_details or ["cool interior stone corridor acoustics"]

        for i in range(count):
            mat = materials[i % len(materials)]
            sen = sensory[i % len(sensory)]
            text = (
                f"Examining the outer perimeter, {mat} defines every line. "
                f"Here at ground level, {sen.lower()}, reflecting centuries of dedicated craftsmanship."
            )
            beats.append({
                "phase": "context_immersion",
                "role": "narrator",
                "text": text,
                "emphasis": [mat.split()[-1] if mat else "stone", "craftsmanship"],
                "scene": f"Ground-level architectural view of {self.sheet.location_name} featuring {mat}",
                "action": f"Camera tracks steadily beside {mat}, revealing fine surface textures and masonry seams",
                "proof": f"authentic {mat} showing period tool striations",
                "scale": "wide" if i % 2 == 0 else "medium",
                "lighting": "natural diffuse sunlight filtering through ancient colonnades",
                "character_reference": False,
                "is_a_roll": False,
            })
        return beats

    def _weave_rising_investigation(self, count: int) -> list[dict[str, Any]]:
        """Phase 3: Rising Investigation & Active Process Choreography (tools, labor, witness)."""
        beats: list[dict[str, Any]] = []
        facts = self.sheet.verified_facts or ["Ancient stonemasons quarried and dressed multi-ton blocks using percussion techniques."]
        witnesses = self.sheet.historical_figures or []
        materials = self.sheet.architecture_and_materials or ["dressed stone blocks"]

        for i in range(count):
            # Include an authentic eyewitness interview if available and at midpoint of phase
            if witnesses and i == count // 2:
                w = witnesses[0]
                text = (
                    f"{facts[0] if facts else 'We carved these monumental foundations to withstand the elements.'} "
                    "Every joint was measured with careful alignment."
                )
                beats.append({
                    "phase": "rising_investigation",
                    "role": f"witness:{w['name']} ({w.get('era_label', self.era)})",
                    "text": text,
                    "emphasis": ["monumental", "measured", "alignment"],
                    "scene": f"Documentary interview framing of historical witness {w['name']} holding period tools",
                    "action": f"{w['name']} addresses the camera with calm period gravitas, holding authentic period instrument",
                    "proof": f"{w['name']} in authentic {self.era} craftsman attire",
                    "scale": "medium",
                    "lighting": "period-accurate warm directional workshop or outdoor natural daylight",
                    "character_reference": False,
                    "is_witness": True,
                })
            else:
                mat = materials[(i + 1) % len(materials)]
                # Process-specific active labor choreography
                text = (
                    f"Notice the tight mortarless seams across {mat}. "
                    "Craftsmen hauled and chiseled each section using hand-forged tools and counterweighted wooden levers."
                )
                beats.append({
                    "phase": "rising_investigation",
                    "role": "narrator",
                    "text": text,
                    "emphasis": ["mortarless seams", "counterweighted", "levers"],
                    "scene": f"Detailed macro exploration of {mat} showing precision joints and tooling marks",
                    "action": f"Slow cinematic camera glide across {mat} revealing knapped percussion flake scars and chisel furrows",
                    "proof": f"precision tooling marks on {mat} without modern machine grooves",
                    "scale": "macro" if i % 2 == 1 else "close",
                    "lighting": "low-angle raking sunlight revealing microscopic surface tool relief",
                    "character_reference": False,
                    "is_a_roll": False,
                })
        return beats

    def _weave_turning_point(self, count: int) -> list[dict[str, Any]]:
        """Phase 4: Turning Point & Decisive Physical Proof (on-screen mechanical solution)."""
        beats: list[dict[str, Any]] = []
        facts = self.sheet.verified_facts or ["Archaeological surveys confirmed internal sliding stones engineered to seal chambers."]
        loc = self.sheet.location_name or self.sheet.topic

        for i in range(count):
            if i == 0:
                # Host Nova midpoint turning point moment
                text = (
                    f"Standing inside this central chamber at {loc}, the answer becomes undeniable: "
                    "ancient builders relied on pure geometry and counterweighted gravity."
                )
                beats.append({
                    "phase": "turning_point",
                    "role": "host_nova",
                    "text": text,
                    "emphasis": ["central chamber", "geometry", "counterweighted gravity"],
                    "scene": f"Host {self.character.name} inside the central chamber of {loc} observing internal architectural mechanics",
                    "action": f"{self.character.name} inspects the interlocking stone chamber seams with thoughtful expression",
                    "proof": f"{self.character.name}'s glowing temporal chronometer; interlocking central chamber stones",
                    "scale": "medium",
                    "lighting": "dramatic shafts of subterranean sunlight piercing overhead roof openings",
                    "character_reference": True,
                    "is_a_roll": True,
                })
            else:
                text = (
                    f"Physical evidence confirms {facts[-1] if facts else 'advanced engineering joints'}. "
                    "By distributing multi-ton loads across interlocking lintels, the structure achieved permanent equilibrium."
                )
                beats.append({
                    "phase": "turning_point",
                    "role": "narrator",
                    "text": text,
                    "emphasis": ["interlocking lintels", "permanent equilibrium"],
                    "scene": f"Cutaway perspective of load-bearing structural joints at {loc}",
                    "action": f"Camera tilts upward along the monumental load-bearing piers and massive lintel blocks",
                    "proof": f"interlocking structural lintel joint engineering at {loc}",
                    "scale": "medium",
                    "lighting": "high-contrast volumetric light illuminating architectural stress distribution points",
                    "character_reference": False,
                    "is_a_roll": False,
                })
        return beats

    def _weave_legacy_verdict(self, count: int) -> list[dict[str, Any]]:
        """Phase 5: Legacy & Modern Archaeological Verdict (GPR radar, temporal extraction)."""
        beats: list[dict[str, Any]] = []
        loc = self.sheet.location_name or self.sheet.topic

        if count > 1:
            beats.append({
                "phase": "legacy_verdict",
                "role": "narrator",
                "text": f"Modern ground-penetrating radar scans confirm subterranean foundations of {loc} still survive intact beneath the surface.",
                "emphasis": ["radar scans", "subterranean foundations", "survive intact"],
                "scene": f"Wide aerial perspective over the landscape of {loc} revealing buried geometric foundation lines",
                "action": f"Camera ascends into high-angle aerial glide over {loc} showing the enduring footprint against the landscape",
                "proof": f"enduring monumental architectural footprint of {loc}",
                "scale": "wide",
                "lighting": "serene late afternoon golden twilight with long cinematic shadows",
                "character_reference": False,
                "is_a_roll": False,
            })

        # Closing Host Nova sign-off and verdict
        text = (
            f"Before my temporal chronometer returns me to the present, one verdict is clear: "
            f"the master builders of {loc} created architecture that time itself cannot erase."
        )
        beats.append({
            "phase": "legacy_verdict",
            "role": "host_nova",
            "text": text,
            "emphasis": ["temporal chronometer", loc.split()[-1] if loc else "monument", "cannot erase"],
            "scene": f"Host {self.character.name} on the perimeter ridge of {loc} at dusk as her chronometer gyroscopes glow",
            "action": f"{self.character.name} faces the camera at sunset as the brass temporal chronometer on her wrist illuminates",
            "proof": f"{self.character.name}'s glowing gyroscopic chronometer against the dusk horizon of {loc}",
            "scale": "medium",
            "lighting": "dramatic crimson and amber sunset sky with warm rim lighting",
            "character_reference": True,
            "is_a_roll": True,
        })
        return beats

    def _create_investigation_beat(self, idx: int) -> dict[str, Any]:
        """Fallback helper to synthesize a filler investigation beat if padding is needed."""
        mat = self.sheet.architecture_and_materials[0] if self.sheet.architecture_and_materials else "monolithic stone"
        return {
            "phase": "rising_investigation",
            "role": "narrator",
            "text": f"Tracing each structural contour, {mat} exhibits deliberate acoustic and load-bearing alignments.",
            "emphasis": ["structural contour", "alignments"],
            "scene": f"Documentary view of masonry details at {self.sheet.location_name}",
            "action": f"Camera glides smoothly along {mat} highlighting precision craftsmanship",
            "proof": f"aligned precision masonry joints of {mat}",
            "scale": "close",
            "lighting": "natural atmospheric daylight",
            "character_reference": False,
            "is_a_roll": False,
        }

    def _apply_all_locks(self, beat: dict[str, Any], block_idx: int, total_blocks: int) -> dict[str, Any]:
        """Apply the 4 Visual Locks and motion contracts onto an authored beat."""
        is_character = beat.get("role") == "host_nova" or beat.get("is_witness", False)
        scene = beat.get("scene", "")
        action = beat.get("action", "")

        # 1. Clothing Lock V2
        scene = apply_clothing_lock_v2(scene, era=self.era, truth_sheet=self.sheet)

        # 2. Equipment Lock V2 (Era-gated, exempts WWI)
        scene = apply_equipment_lock_v2(scene, era=self.era, truth_sheet=self.sheet)

        # 3. Framing & Headroom Lock
        scene = apply_framing_lock_v2(scene, is_character_shot=is_character)

        # 4. Movement Lock V2
        has_people = is_character or bool(beat.get("character_reference", False)) or "laborers" in scene or "craftsmen" in scene or "builders" in scene
        action = apply_movement_lock_v2(action, has_people=has_people)

        beat["scene"] = scene
        beat["action"] = action
        return beat
