"""Generate up to 20 reference visuals and character sheet manifest for the Time-Traveler Persona (Nova).

Anchors Nova's immutable facial traits, hazel eyes, freckles, bone structure, and signature
temporal chronometer artifact across various historical eras and camera angles.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from services.character import (
    DEFAULT_CHARACTER,
    CharacterProfile,
    CharacterSheetSpec,
    get_active_character,
)


def compile_20_reference_prompts(char: CharacterProfile) -> list[dict[str, str]]:
    """Compile 20 authoritative character reference prompts across angles and historical eras."""
    spec = CharacterSheetSpec(char, aspect_ratio="16:9")
    base_anchor = char.anchor_description("default")

    prompts = [
        # --- Core Physical Identity Locks (Angles & Micro-Details) ---
        {
            "id": "sheet_01_frontal_studio",
            "category": "core_identity",
            "title": "Frontal Master Portrait",
            "prompt": (
                f"MASTER CHARACTER ANCHOR [FRONTAL VIEW]: {base_anchor}. "
                "Front-facing portrait, eye-level camera, direct gaze at viewer, neutral closed mouth, "
                "subtle confident smile. Professional documentary studio lighting, soft neutral fill light, "
                "sharp focus on facial micro-features, visible natural skin pores, fine freckles across nose bridge, "
                "8k resolution, National Geographic cinema photography, 16:9 composition. ZERO text, ZERO watermarks."
            ),
        },
        {
            "id": "sheet_02_three_quarter_right",
            "category": "core_identity",
            "title": "Three-Quarter Right Angle",
            "prompt": (
                f"CHARACTER REFERENCE [THREE-QUARTER RIGHT]: {base_anchor}. "
                "Looking 45 degrees toward the right, curious inquisitive gaze, sharp amber eye catchlights, "
                "defined cheekbones, textured chestnut hair strands with natural flyaways. Soft cinematic rim light, "
                "photorealistic 8k documentary cinema, 16:9 horizontal composition. ZERO text, ZERO watermarks."
            ),
        },
        {
            "id": "sheet_03_three_quarter_left",
            "category": "core_identity",
            "title": "Three-Quarter Left Angle",
            "prompt": (
                f"CHARACTER REFERENCE [THREE-QUARTER LEFT]: {base_anchor}. "
                "Looking 45 degrees toward the left, thoughtful focused analytical expression, natural skin texture, "
                "soft diffused natural daylight, documentary photography depth of field, 16:9 composition. "
                "ZERO text, ZERO watermarks."
            ),
        },
        {
            "id": "sheet_04_macro_facial_detail",
            "category": "core_identity",
            "title": "Macro Facial Feature Lock",
            "prompt": (
                f"FACIAL FEATURE DETAIL LOCK: Extreme close-up portrait of {char.name}. "
                f"{char.face_traits}. Striking hazel eyes with rich amber-gold flecks, sharp iris detail, "
                "authentic natural unretouched skin texture with realistic fine pores, delicate faint freckles across nose bridge, "
                "natural soft lip texture with neutral closed mouth. Shallow depth of field, 8k cinematic macro documentary, 16:9 composition. "
                "ZERO CGI plastic sheen, ZERO cartoon smoothing, ZERO text."
            ),
        },
        {
            "id": "sheet_05_temporal_device_macro",
            "category": "signature_artifact",
            "title": "Temporal Chronometer Wrist Device",
            "prompt": (
                spec.artifact_macro_prompt()
            ),
        },
        # --- Modern Expedition & Field Vlog Actions ---
        {
            "id": "sheet_06_field_vlog_arrival",
            "category": "field_action",
            "title": "Arrival Field Vlog Hook",
            "prompt": (
                f"DOCUMENTARY ARRIVAL HOOK [A-ROLL]: {base_anchor}. "
                "Mid-shot holding field camera at arm's length in selfie vlog style, speaking naturally to audience "
                "with engaged adventurous smile, standing outside a remote archaeological dig site at sunrise. "
                "Authentic fabric folds on olive utility jacket, morning golden hour lighting, cinematic background blur, "
                "16:9 widescreen documentary. ZERO text, ZERO watermarks."
            ),
        },
        {
            "id": "sheet_07_field_inscription_inspect",
            "category": "field_action",
            "title": "Inspecting Ancient Inscriptions",
            "prompt": (
                f"FIELD INVESTIGATION ACTION: {base_anchor}. "
                "Medium shot, {char.name} carefully examining weathered ancient stone hieroglyphs with a handheld warm LED inspection light. "
                "Subtle glowing temporal chronometer wrist device visible on her left forearm. "
                "Dust motes drifting through warm beam of light, ancient subterranean stone chamber, 8k cinematic photorealism, 16:9 composition. "
                "ZERO text, ZERO watermarks."
            ),
        },
        {
            "id": "sheet_08_torchlight_tunnel",
            "category": "field_action",
            "title": "Torchlight Subterranean Exploration",
            "prompt": (
                f"SUBTERRANEAN EXPLORATION: {base_anchor}. "
                "Low-angle cinematic shot of {char.name} descending narrow damp limestone passageway holding a warm flame torch, "
                "shadows dancing on ancient carved limestone blocks, intense focused expression of discovery. "
                "High dynamic range, deep atmospheric perspective, 16:9 widescreen cinema. ZERO text, ZERO watermarks."
            ),
        },
        # --- Era Camouflage 1: Neolithic / Prehistoric ---
        {
            "id": "sheet_09_neolithic_gobeklitepe",
            "category": "era_camouflage",
            "title": "Neolithic Camouflage - Göbeklitepe",
            "prompt": (
                f"TIME-TRAVELER ERA CAMOUFLAGE [NEOLITHIC 9600 BC]: {char.anchor_description('neolithic')}. "
                "Standing among colossal carved T-shaped limestone pillars at Göbeklitepe during ceremonial twilight. "
                "Historically authentic stitched deerskin tunic and flax mantle, while her subtle glowing brass temporal chronometer "
                "is strapped to her left wrist beneath the deerskin cuff. Volumetric bonfire smoke, starry ancient night sky, 16:9 cinema. "
                "ZERO text, ZERO watermarks."
            ),
        },
        # --- Era Camouflage 2: Ancient Egypt / Nile ---
        {
            "id": "sheet_10_egyptian_hawara_labyrinth",
            "category": "era_camouflage",
            "title": "Egyptian Camouflage - Hawara Labyrinth",
            "prompt": (
                f"TIME-TRAVELER ERA CAMOUFLAGE [ANCIENT EGYPT 1800 BC]: {char.anchor_description('egyptian')}. "
                "Walking through the grand colonnaded courtyard of the Lost Labyrinth of Hawara near the Fayum oasis. "
                "Wearing fine pleated unbleached linen kalasiris tunic with braided sash; her celestial brass temporal chronometer "
                "glowing faintly on her sun-kissed left wrist. Radiant desert sun, towering white limestone monoliths, 16:9 cinema. "
                "ZERO text, ZERO watermarks."
            ),
        },
        {
            "id": "sheet_11_egyptian_giza_plateau",
            "category": "era_camouflage",
            "title": "Egyptian Camouflage - Giza Horizon",
            "prompt": (
                f"TIME-TRAVELER IN EGYPT: {char.anchor_description('egyptian')}. "
                "Three-quarter profile standing on desert sand ridge overlooking newly cased gleaming white limestone pyramids under construction. "
                "Warm amber sunset breeze moving through her chestnut hair, looking into the distance with contemplative awe, "
                "temporal chronometer resting on her arm. 8k documentary cinema, 16:9 horizontal composition. ZERO text."
            ),
        },
        # --- Era Camouflage 3: Classical Greco-Roman ---
        {
            "id": "sheet_12_greco_roman_forum",
            "category": "era_camouflage",
            "title": "Greco-Roman Camouflage - Forum",
            "prompt": (
                f"TIME-TRAVELER ERA CAMOUFLAGE [ROMAN EMPIRE 100 AD]: {char.anchor_description('greco_roman')}. "
                "Walking through marble portico of the Roman Forum among bustling citizens in togas. "
                "Wearing draped terracotta wool chiton with bronze fibula clasps, disguised as an itinerant Greek naturalist, "
                "her intricate temporal chronometer gleaming discreetly on her left wrist. Mediterranean morning light, 16:9 cinema. ZERO text."
            ),
        },
        {
            "id": "sheet_13_greco_roman_celsus_library",
            "category": "era_camouflage",
            "title": "Classical Camouflage - Library of Celsus",
            "prompt": (
                f"CLASSICAL ERA INVESTIGATION: {char.anchor_description('greco_roman')}. "
                "Inspecting papyrus scroll scrolls inside the grand two-story library at Ephesus by flickering oil lamp. "
                "Intense intellectual curiosity, hazel eyes reflecting warm flame, marble statues in background alcoves, "
                "16:9 widescreen documentary. ZERO text, ZERO watermarks."
            ),
        },
        # --- Era Camouflage 4: Ottoman Empire ---
        {
            "id": "sheet_14_ottoman_grand_bazaar",
            "category": "era_camouflage",
            "title": "Ottoman Camouflage - Historical Istanbul",
            "prompt": (
                f"TIME-TRAVELER ERA CAMOUFLAGE [OTTOMAN EMPIRE 1550 AD]: {char.anchor_description('ottoman')}. "
                "Navigating the vaulted stone corridors of the Grand Bazaar under shafts of golden sunlight. "
                "Wearing tailored silk-and-wool entari robe and traveler kaftan, blending seamlessly with merchants, "
                "her glowing temporal astrolabe dial peeking from beneath her tailored sleeve. Rich spice colors, 16:9 cinema. ZERO text."
            ),
        },
        {
            "id": "sheet_15_ottoman_bosphorus_overlook",
            "category": "era_camouflage",
            "title": "Ottoman Camouflage - Bosphorus Sunset",
            "prompt": (
                f"OTTOMAN TIMELINE OVERLOOK: {char.anchor_description('ottoman')}. "
                "Overlooking the historical peninsula of Constantinople from the hills of Galata at sunset, "
                "domes and minarets silhouetted against crimson sky, holding her temporal chronometer in palm to calibrate chronological coordinates. "
                "8k photorealistic cinema, 16:9 composition. ZERO text."
            ),
        },
        # --- Era Camouflage 5: Medieval Europe ---
        {
            "id": "sheet_16_medieval_cloister",
            "category": "era_camouflage",
            "title": "Medieval Camouflage - Cloister Passage",
            "prompt": (
                f"TIME-TRAVELER ERA CAMOUFLAGE [MEDIEVAL EUROPE 1250 AD]: {char.anchor_description('medieval')}. "
                "Walking through arched gothic stone monastery cloister on an overcast autumn morning. "
                "Wearing moss-green wool cotehardie dress and traveler cloak, temporal wrist chronometer concealed at wrist, "
                "mist rising from damp courtyard grass, 8k photorealistic documentary, 16:9 composition. ZERO text."
            ),
        },
        # --- Era Camouflage 6: Ancient Mesopotamia ---
        {
            "id": "sheet_17_mesopotamian_ur",
            "category": "era_camouflage",
            "title": "Mesopotamian Camouflage - Ziggurat of Ur",
            "prompt": (
                f"TIME-TRAVELER ERA CAMOUFLAGE [SUMERIAN MESOPOTAMIA 2100 BC]: {char.anchor_description('mesopotamian')}. "
                "Ascending monumental mudbrick staircases of the Great Ziggurat of Ur. "
                "Wearing traditional fringed woolen kaunakes wrap and linen tunic, temporal chronometer glinting on forearm, "
                "stark desert horizon and braided Euphrates canals below, 16:9 cinema. ZERO text."
            ),
        },
        # --- Era Camouflage 7: Victorian 19th Century ---
        {
            "id": "sheet_18_victorian_antiquities_hall",
            "category": "era_camouflage",
            "title": "Victorian Camouflage - Antiquities Hall",
            "prompt": (
                f"TIME-TRAVELER ERA CAMOUFLAGE [VICTORIAN 1888 AD]: {char.anchor_description('victorian')}. "
                "Standing beside tall glass museum vitrines containing newly unearthed Egyptian artifacts in gaslit museum hall. "
                "Wearing tailored tweed riding jacket and high-collar blouse, looking directly at the camera with knowing intrigue, "
                "temporal chronometer worn beneath lace cuff, 16:9 documentary cinema. ZERO text."
            ),
        },
        # --- Story Climax & Verdict Moments ---
        {
            "id": "sheet_19_turning_point_discovery",
            "category": "story_climax",
            "title": "Turning Point Shock Reaction",
            "prompt": (
                f"CLIMACTIC TURNING POINT REVEAL [A-ROLL]: {base_anchor}. "
                "Over-the-shoulder shot, {char.name} turning sharply toward camera with wide amazed hazel eyes and parted lips, "
                "pointing toward an impossible technological artifact embedded deep inside ancient megalithic granite bedrock. "
                "Spontaneous authentic shock reaction, dynamic cinematic lighting, 16:9 widescreen documentary. ZERO text."
            ),
        },
        {
            "id": "sheet_20_closing_signoff",
            "category": "story_climax",
            "title": "Closing Sign-Off & Verdict",
            "prompt": (
                f"DOCUMENTARY CLOSING VERDICT [A-ROLL]: {base_anchor}. "
                "Warm engaging medium shot, {char.name} looking directly into lens delivering final reflective verdict to viewer, "
                "subtle warm sunset breeze moving through chestnut hair, ancient ruins fading softly into atmospheric bokeh behind her. "
                "Subtle glow from temporal chronometer at wrist, 8k photorealistic cinema, 16:9 widescreen composition. ZERO text."
            ),
        },
    ]
    return prompts


def save_manifest(prompts: list[dict[str, str]], out_dir: Path) -> Path:
    """Save structured reference sheets manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "character_sheets_manifest.json"
    manifest_data = {
        "character": DEFAULT_CHARACTER.name,
        "archetype": DEFAULT_CHARACTER.archetype,
        "age_range": DEFAULT_CHARACTER.age_range,
        "face_traits": DEFAULT_CHARACTER.face_traits,
        "signature_artifact": DEFAULT_CHARACTER.time_device,
        "total_sheets": len(prompts),
        "sheets": prompts,
    }
    manifest_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


async def run_generation(prompts: list[dict[str, str]], out_dir: Path, provider_name: str | None = None) -> None:
    """Generate images using the configured image provider."""
    from providers.factory import get_image_provider

    provider = get_image_provider(provider_name)
    print(f"Generating {len(prompts)} character reference visuals via {provider.__class__.__name__}...")

    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, item in enumerate(prompts, start=1):
        target_file = out_dir / f"{item['id']}.png"
        if target_file.exists() and target_file.stat().st_size > 0:
            print(f"  [{idx:02d}/20] [CACHED] {item['title']} -> {target_file.name}")
            continue

        print(f"  [{idx:02d}/20] Generating {item['title']}...", end="", flush=True)
        try:
            await provider.generate_keyframe(item["prompt"], target_file, seed=42 + idx, aspect_ratio="16:9")
            print(f" DONE ({target_file.stat().st_size // 1024} KB)")
        except Exception as exc:
            print(f" FAILED: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Time-Traveler Nova Character Sheet Generator")
    parser.add_argument("--generate", action="store_true", help="Submit prompts to active image provider")
    parser.add_argument("--provider", default=None, help="Image provider override (e.g. playwright_flow, flow_agent, vertex)")
    parser.add_argument("--out-dir", default="_character_sheets", help="Output directory for manifests and images")
    args = parser.parse_args()

    char = get_active_character()
    out_dir = ROOT / args.out_dir
    prompts = compile_20_reference_prompts(char)

    manifest_file = save_manifest(prompts, out_dir)
    print(f"[OK] Saved 20 time-traveler character sheet prompts to: {manifest_file}")

    if args.generate:
        asyncio.run(run_generation(prompts, out_dir, args.provider))
    else:
        print("Note: Run with '--generate' to render all 20 images using active image provider.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
