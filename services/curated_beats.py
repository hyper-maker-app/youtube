"""Curated documentary story arcs for authoritative historical benchmark productions.

Provides full-length 22-block (90s) and 15-block (60s) curated beats for:
1. 18 March 1915 Gallipoli / Çanakkale: Rumeli Mecidiye Bastion, Corporal Seyit (Seyit Onbaşı),
   and the battleship Bouvet artillery duel (benchmarking @zamanyolcusudefne 2:10 - 3:40).
2. 79 AD Pompeii: Eve of Mount Vesuvius eruption, Roman street life, Terentius Neo's pistrinum bakery,
   and the Plinian volcanic ash column (generalization target).

Enforces:
- Strict ADR-060: Host Nova appears exclusively in pivotal A-Roll (Opening Hook, Midpoint Turning Point, Closing Verdict).
- Period Accuracy: Ottoman khaki kabalak (Enveriye) hats (strictly NO red fez), authentic 28cm Krupp coastal gun.
- Generalization: Roman wool tunics, lava-stone mills, domed brick ovens (strictly NO medieval armor, NO sunglasses).
- Zero Text Shield: Proof targets describe physical evidence without date/title boxes or watermarks.
- Dual Language: Full Turkish ('tr') and English ('en') documentary narration.

Zero network/transport calls are made in this module (strictly AST-clean).
"""

from __future__ import annotations

from typing import Any


def get_gallipoli_curated_beats(total_blocks: int, lang: str = "en", topic: str = "") -> list[dict[str, Any]]:
    """Return curated beats for the 18 March 1915 Gallipoli naval battle and Mecidiye Bastion duel."""
    is_tr = (lang or "en").strip().casefold() == "tr"
    is_seyit_arc = any(term in (topic or "").casefold() for term in ("seyit", "onbasi", "onbaşı", "mecidiye", "215", "rumeli"))

    if total_blocks >= 20:
        # 22-block master sequence (90-second video: 22 x 4.0s = 88s + 1.5s tail = 89.5s)
        # Matches the exact 2:10 - 3:40 section of reference video https://www.youtube.com/watch?v=PXixPeATIQc
        return [
            {
                "text": "18 Mart 1915; Müttefik donanması Çanakkale Boğazı'na giriyor."
                if is_tr else "On 18 March 1915, Allied battleships enter the Dardanelles.",
                "role": "host_nova", "emphasis": ["18 March 1915", "Dardanelles"], "scale": "wide",
                "scene": "Nova arrives on the Gallipoli shore on 18 March 1915, Allied battleships advancing into the narrow Dardanelles; period wool coat and brass chronometer on her left wrist.",
                "proof": "Nova's brass temporal chronometer; Allied battleships entering the Dardanelles on 18 March 1915",
                "action": "Nova steps out of salt spray and turns toward the distant ships; her coat and hair move in the coastal wind, camera follows her gaze to the strait.",
                "lighting": "gray dawn beneath smoke-heavy coastal cloud",
                "location_id": "gallipoli_battery_story_hook",
                "character_reference": True,
            },
            {
                "text": "Ağır zırhlı topları kıyı tabyalarını aralıksız dövüyor."
                if is_tr else "Heavy battleship broadsides crash relentlessly around shore batteries.",
                "role": "narrator", "emphasis": ["broadsides crash", "shore fortifications"], "scale": "wide",
                "scene": "Allied battleship guns bombard Ottoman shore batteries on 18 March 1915; shell splashes rise beyond the stone fortifications and dark powder smoke crosses the channel.",
                "proof": "Allied battleship bombardment of Ottoman coastal battery during the 18 March attack",
                "action": "A distant shell strikes the hillside beyond the battery, throwing up dust as smoke drifts across the gun position; camera tracks from shaking sandbags toward the obscured water.",
                "lighting": "smoke-diffused cold daylight",
                "location_id": "dardanelles_battery_under_fire",
            },
            {
                "text": "Rumeli Mecidiye Tabyası sarsıcı bir doğrudan isabet alıyor."
                if is_tr else "Rumeli Mecidiye Bastion takes a catastrophic direct hit.",
                "role": "narrator", "emphasis": ["Mecidiye", "direct artillery hit"], "scale": "medium",
                "scene": "Ottoman coastal artillery battery at Mecidiye Bastion on 18 March 1915; heavy 28cm Krupp gun in sunken stone embrasure, sandbags, and powder smoke.",
                "proof": "Direct artillery shell strike on the stone fortifications of Mecidiye Bastion",
                "action": "Ottoman gunners and Corporal Seyit brace as a shell strikes the battery; gunners actively clear shattered stone from the position, powder smoke drifting across the sandbags.",
                "lighting": "warm firelight through powder smoke",
                "location_id": "dardanelles_mecidiye_strike",
            },
            {
                "text": "Patlama mermi vincini parçalıyor; çarklar yere savruluyor."
                if is_tr else "The blast shatters the shell crane and gears.",
                "role": "narrator", "emphasis": ["shatters", "mechanical shell crane"], "scale": "close",
                "scene": "Close documentary inspection of the destroyed shell hoist mechanism inside Mecidiye Bastion on 18 March 1915; twisted iron gears, snapped chains, and rubble.",
                "proof": "The broken mechanical shell crane and twisted iron chains inside the battery",
                "action": "Dust settles over the crushed mechanical crane and snapped chains on the battery floor; gunners assess the damage with urgent purposeful movement.",
                "lighting": "smoke-softened daylight with warm ember highlights",
                "location_id": "dardanelles_broken_crane",
            },
            {
                "text": "Duman dağılırken geriye yalnızca üç ağır mermi kalıyor."
                if is_tr else "When dust clears, only three heavy shells remain.",
                "role": "narrator", "emphasis": ["dust clears", "three intact heavy shells"], "scale": "medium",
                "scene": "Ottoman artillerymen and Corporal Seyit standing amidst powder smoke in the ruined Mecidiye Bastion; three massive 215kg steel artillery shells resting beside the shattered hoist.",
                "proof": "Three intact 215kg artillery shells resting beside the ruined ammunition hoist",
                "action": "Corporal Seyit and comrade Niğdeli Ali wipe dust from their eyes and inspect the remaining ammunition; gunners move with grim resolve.",
                "lighting": "chiaroscuro daylight through clearing smoke",
                "location_id": "dardanelles_ammunition_depot",
            },
            {
                "text": "Seyit Onbaşı 215 kiloluk dev Krupp mermisine bakıyor."
                if is_tr else "Corporal Seyit inspects the colossal Krupp shell.",
                "role": "narrator", "emphasis": ["Corporal Seyit", "two-hundred-fifteen kilogram"], "scale": "close",
                "scene": "Close-up of Corporal Seyit Onbaşı's weathered, soot-streaked Anatolian face, wearing authentic khaki cloth kabalak hat; determined eyes locked on the heavy artillery shell.",
                "proof": "Corporal Seyit inspecting the massive 215kg artillery shell",
                "action": "Seyit Onbaşı tightens his leather belt and takes a deep breath, preparing mentally and physically for the impossible lift.",
                "lighting": "dramatic directional sunlight through battle smoke",
                "location_id": "dardanelles_seyit_resolve",
            },
            {
                "text": "Seyit kollarını dev çelik merminin altına sarıyor."
                if is_tr else "Seyit locks his thick arms beneath the steel.",
                "role": "narrator", "emphasis": ["squats low", "locking arms"], "scale": "close",
                "scene": "Corporal Seyit Onbaşı bracing his boots against the crushed stone floor, arms wrapped tightly around the 215kg artillery shell.",
                "proof": "Corporal Seyit wrapping his arms around the 215kg artillery shell",
                "action": "Seyit braces his legs and drives his shoulders upward beneath the shell; leg muscles tighten and veins swell along his forearms.",
                "lighting": "low-angle dramatic side light",
                "location_id": "dardanelles_seyit_grip",
            },
            {
                "text": "İnsanüstü bir iradeyle 215 kiloluk yükü sırtına alıyor."
                if is_tr else "With superhuman willpower, he heaves the shell onto his back.",
                "role": "narrator", "emphasis": ["superhuman willpower", "heaves onto back"], "scale": "close",
                "scene": "Close-up of Corporal Seyit lifting the colossal 215kg shell onto his upper back; heavy wool uniform straining, facial muscles clenched in agony and resolve.",
                "proof": "Corporal Seyit lifting the heavy 215kg artillery shell onto his back",
                "action": "Seyit strains every tendon and raises the colossal weight onto his shoulders; his boots dig into the crushed limestone battery floor.",
                "lighting": "directional daylight through powder haze",
                "location_id": "dardanelles_seyit_lift",
            },
            {
                "text": "Seyit, ezici yükün altında taş mevzide ilerliyor."
                if is_tr else "Under the crushing burden, he marches across stone.",
                "role": "narrator", "emphasis": ["crushing burden", "marches across stone"], "scale": "medium",
                "scene": "Corporal Seyit carrying the massive artillery shell across the stone battery floor; comrades Niğdeli Ali and gunners clearing the path ahead.",
                "proof": "Seyit Onbaşı carrying the massive 215kg shell across the battery",
                "action": "Seyit moves forward with slow, powerful, measured footsteps under the heavy load; dust rises around his boots.",
                "lighting": "deep shadows and dusty daylight",
                "location_id": "dardanelles_seyit_walk",
            },
            {
                "text": "Canını dişine takarak taş basamakları adım adım tırmanıyor."
                if is_tr else "Step by agonizing step, he ascends the stone stairs.",
                "role": "narrator", "emphasis": ["step by agonizing step", "ascends stone stairs"], "scale": "medium",
                "scene": "Seyit Onbaşı ascending the massive stone steps toward the 28cm Krupp gun platform under the immense weight of the artillery shell.",
                "proof": "Seyit Onbaşı carrying the massive 215kg shell up the battery stone steps",
                "action": "Seyit climbs the stone steps one by one under the colossal weight, boots striking solid stone as he reaches the steel gun platform.",
                "lighting": "cool reflected daylight and deep gunmetal shadows",
                "location_id": "dardanelles_steps_climb",
            },
            {
                "text": "Mecidiye'deki bu eşsiz kahramanlık, tüm savaşın kaderini değiştiriyor."
                if is_tr else "This heroic stand at Mecidiye turns the entire battle.",
                "role": "host_nova", "emphasis": ["heroic stand", "entire naval battle"], "scale": "medium",
                "scene": "Nova on the Gallipoli peninsula at the midpoint turning point; drifting powder smoke behind her, glowing brass temporal chronometer on left wrist.",
                "proof": "Nova witnessing the pivotal turning point of the 18 March battle; glowing chronometer",
                "action": "Nova turns toward the camera as powder smoke thins behind her; observing the dramatic turn of the naval engagement with intense historical emotion.",
                "lighting": "dramatic chiaroscuro daylight through thinning smoke",
                "location_id": "gallipoli_midpoint_turning_point",
                "character_reference": True,
            },
            {
                "text": "Seyit platforma varıyor; Niğdeli Ali'yle mermiyi hizalıyor."
                if is_tr else "Seyit and Niğdeli Ali align the shell with the breech.",
                "role": "narrator", "emphasis": ["align the shell", "breech"], "scale": "close",
                "scene": "Seyit Onbaşı and Niğdeli Ali steadying the 215kg shell at the open steel breech of the massive 28cm Krupp coastal fortress gun.",
                "proof": "The heavy shell aligned with the open breech of the coastal gun",
                "action": "One gunner steadies the shell while a second aligns it with the open breech; hands guide the round forward in one careful motion.",
                "lighting": "cool reflected daylight and deep gunmetal shadows",
                "location_id": "dardanelles_breech_align",
            },
            {
                "text": "İki topçu dev mermiyi çelik namluya sürüyor."
                if is_tr else "Together they slide the colossal shell into the barrel.",
                "role": "narrator", "emphasis": ["slide the colossal shell", "rifled steel barrel"], "scale": "close",
                "scene": "The 215kg shell sliding into the rifled steel barrel of the 28cm Krupp coastal gun inside Mecidiye Bastion.",
                "proof": "The heavy shell sliding into the breech of the 28cm Krupp coastal gun",
                "action": "Seyit and Niğdeli Ali carefully push the shell into the open breech; hands guide the round forward in one coordinated movement.",
                "lighting": "gray daylight broken by powder smoke",
                "location_id": "dardanelles_breech_load",
            },
            {
                "text": "Topçular kamayı kapatıp çarkları hızla boğaza çeviriyor."
                if is_tr else "The crew locks the breech block and cranks seaward.",
                "role": "narrator", "emphasis": ["locks steel breech", "cranks seaward"], "scale": "medium",
                "scene": "Artillerymen closing the massive steel wedge breech block and vigorously turning traversing handwheels on the Krupp gun carriage.",
                "proof": "The loaded Ottoman coastal gun being aimed toward the strait",
                "action": "The crew secures the breech, then turns the gun toward the channel using the traversing wheels; camera tracks the barrel across the battery toward the fleet.",
                "lighting": "gray daylight broken by powder smoke",
                "location_id": "dardanelles_gun_traverse",
            },
            {
                "text": "Dev namlu Fransız zırhlısı Bouvet'nin su kesimine kilitleniyor."
                if is_tr else "The Krupp barrel locks onto battleship Bouvet.",
                "role": "narrator", "emphasis": ["locks onto", "Bouvet"], "scale": "medium",
                "scene": "The heavy 28cm Krupp coastal gun barrel aimed directly at the French pre-dreadnought battleship Bouvet in the Dardanelles.",
                "proof": "The 28cm Krupp gun traversed toward the Allied line in the strait",
                "action": "Gunners make fine elevation adjustments on the Krupp gun sights, locking the trajectory directly on the advancing enemy warship.",
                "lighting": "cold overcast daylight with distant ship silhouettes",
                "location_id": "dardanelles_aim_bouvet",
            },
            {
                "text": "Ateş! 28'lik dev top kulakları sağır eden gürlemeyle patlıyor."
                if is_tr else "Fire! The giant cannon discharges with thunderous blast.",
                "role": "narrator", "emphasis": ["Fire", "thunderous recoil blast"], "scale": "wide",
                "scene": "The 28cm Krupp coastal cannon firing toward the Allied fleet; massive orange muzzle flash, recoil along carriage, and thick powder smoke.",
                "proof": "A coastal gun firing with massive recoil from an Ottoman battery during the naval assault",
                "action": "The cannon fires once, recoiling along its carriage as the crew braces and dense powder smoke rolls over the stone position; camera jolts subtly with the blast.",
                "lighting": "brief hot muzzle flash in cold smoke",
                "location_id": "dardanelles_gun_firing",
            },
            {
                "text": "Ağır mermi Bouvet zırhlısının su kesimine tam isabet ediyor."
                if is_tr else "The heavy shell strikes Bouvet directly at the waterline.",
                "role": "narrator", "emphasis": ["strikes waterline", "battleship Bouvet"], "scale": "wide",
                "scene": "Artillery shell impact near the waterline of the French battleship Bouvet in the Dardanelles; colossal water and iron explosion.",
                "proof": "Direct artillery shell strike on the French battleship Bouvet",
                "action": "A massive water and steel explosion erupts along the waterline of the battleship Bouvet as the heavy shell impacts.",
                "lighting": "cold daylight with explosion flash",
                "location_id": "dardanelles_bouvet_impact",
            },
            {
                "text": "Bouvet'nin cephaneliği patlıyor; göğe dev kara dumanlar yükseliyor."
                if is_tr else "Bouvet's magazine detonates in a giant fiery explosion.",
                "role": "narrator", "emphasis": ["magazine detonates", "fiery explosion"], "scale": "wide",
                "scene": "The French battleship Bouvet suffering a massive internal explosion in the Dardanelles; billowing yellow-black smoke column rising over the water.",
                "proof": "Internal magazine explosion tearing through the French battleship Bouvet",
                "action": "A secondary magazine explosion tears through the deck of Bouvet; billowing black and yellow smoke rises into the overcast sky.",
                "lighting": "cold storm light with orange fire glow",
                "location_id": "dardanelles_bouvet_explosion",
            },
            {
                "text": "Fransız zırhlısı Bouvet hızla yan yatıp sulara gömülüyor."
                if is_tr else "The French battleship Bouvet capsizes and sinks into the strait.",
                "role": "narrator", "emphasis": ["Bouvet capsizes", "sinks"], "scale": "wide",
                "scene": "The French battleship Bouvet in the Dardanelles on 18 March 1915, listing sharply to starboard as waves pour over the deck and hull capsizes.",
                "proof": "French battleship Bouvet listing and capsizing into the Dardanelles",
                "action": "Bouvet rolls onto its side as cold sea water pours over the superstructure; the warship slips beneath the surface amid swirling foam.",
                "lighting": "cold daylight through smoke haze",
                "location_id": "dardanelles_bouvet_capsizes",
            },
            {
                "text": "Mayınlara çarpan diğer zırhlılarla donanmada panik başlıyor."
                if is_tr else "Panic spreads as battleships Ocean and Irresistible strike mines.",
                "role": "narrator", "emphasis": ["panic spreads", "strike mines"], "scale": "wide",
                "scene": "A distant historical tableau of Allied fleet losses on 18 March 1915: disabled battleships turning in disorder, drifting smoke and rescue vessels.",
                "proof": "Bouvet, Irresistible, and Ocean lost; Inflexible damaged in the 18 March attack",
                "action": "Rescue boats pull sailors from the water beside a disabled ship as another damaged battleship turns away through smoke; keep ships distinct and the action non-graphic.",
                "lighting": "late afternoon haze over rough water",
                "location_id": "dardanelles_fleet_losses",
            },
            {
                "text": "Mecidiye topçuları ve Seyit Onbaşı çekilen armadayı izliyor."
                if is_tr else "Mecidiye's gunners and Corporal Seyit watch the armada retreat.",
                "role": "narrator", "emphasis": ["Corporal Seyit", "armada retreats"], "scale": "medium",
                "scene": "Ottoman artillerymen and Corporal Seyit on the ramparts of Mecidiye Bastion watching the retreating Allied fleet through thinning battle smoke.",
                "proof": "The surviving Allied fleet turning away in retreat past drifting wreckage",
                "action": "Surviving Allied warships turn away toward open water as gunners and Corporal Seyit watch from the sandbagged parapet with weary pride.",
                "lighting": "late afternoon haze over rough water",
                "location_id": "dardanelles_fleet_retreat",
            },
            {
                "text": "Akşam donanma çekiliyor; Çanakkale'nin geçilemeyeceği tarihe mühürleniyor."
                if is_tr else "At dusk the fleet retreats; the Dardanelles remains impassable.",
                "role": "host_nova", "emphasis": ["fleet retreats", "impassable"], "scale": "wide",
                "scene": "Nova stands on the Gallipoli shore at dusk watching the surviving Allied fleet withdraw from the Dardanelles; wool-and-linen period camouflage and left-wrist brass chronometer.",
                "proof": "The Gallipoli shoreline at evening as the Allied fleet withdraws; Nova's brass chronometer",
                "action": "Nova lowers her field map and watches the ships turn toward open water; wind pulls at her coat as the camera moves from her shoulder to the receding horizon.",
                "lighting": "restrained dusk light with smoke fading into the horizon",
                "location_id": "gallipoli_1915_shore_evening",
                "character_reference": True,
            },
        ]

    if total_blocks >= 12:
        if is_seyit_arc:
            # 15-block Seyit Onbaşı sequence (60s video: 15 x 4.0s = 60s)
            return [
                {
                    "text": "18 Mart 1915; Müttefik armadası Çanakkale Boğazı'na giriyor."
                    if is_tr else "At dawn on 18 March 1915, Allied battleships enter the Dardanelles.",
                    "role": "host_nova", "emphasis": ["18 March 1915", "Dardanelles"], "scale": "wide",
                    "scene": "Nova arrives on the Gallipoli shore on 18 March 1915, Allied battleships advancing into the narrow Dardanelles; period wool coat and brass chronometer on her left wrist.",
                    "proof": "Nova's brass temporal chronometer; Allied battleships entering the Dardanelles on 18 March 1915",
                    "action": "Nova steps out of salt spray and turns toward the distant ships; her coat and hair move in the coastal wind, camera follows her gaze to the strait.",
                    "lighting": "gray dawn beneath smoke-heavy coastal cloud",
                    "location_id": "gallipoli_battery_story_hook",
                    "character_reference": True,
                },
                {
                    "text": "Zırhlıların ağır topları kıyı tabyasını aralıksız dövüyor."
                    if is_tr else "Their heavy broadsides crash around the coastal fortifications, smoke obscuring the channel.",
                    "role": "narrator", "emphasis": ["heavy broadsides", "coastal fortifications"], "scale": "wide",
                    "scene": "Allied battleship guns bombard an Ottoman shore battery on 18 March 1915; shell splashes rise beyond the stone position and dark powder smoke crosses the channel.",
                    "proof": "Allied battleship bombardment of Ottoman coastal battery during the 18 March attack",
                    "action": "A distant shell strikes the hillside beyond the battery, throwing up dust as smoke drifts across the gun position; camera tracks from shaking sandbags toward the obscured water.",
                    "lighting": "smoke-diffused cold daylight",
                    "location_id": "dardanelles_battery_under_fire",
                },
                {
                    "text": "Rumeli Mecidiye Tabyası sarsıcı bir doğrudan isabet alıyor."
                    if is_tr else "Rumeli Mecidiye Bastion takes a catastrophic direct hit, shattering stone ramparts.",
                    "role": "narrator", "emphasis": ["Mecidiye", "catastrophic hit"], "scale": "medium",
                    "scene": "Ottoman coastal artillery battery at Mecidiye Bastion on 18 March 1915; period heavy 28cm Krupp gun in sunken stone embrasure, sandbags, and powder smoke.",
                    "proof": "Direct artillery shell strike on the stone fortifications of Mecidiye Bastion",
                    "action": "Ottoman gunners and Corporal Seyit brace as a shell strikes the battery; gunners actively clear shattered stone from the position, powder smoke drifting across the sandbags.",
                    "lighting": "warm firelight through powder smoke",
                    "location_id": "dardanelles_mecidiye_strike",
                },
                {
                    "text": "Mermi vinci parçalanıyor, çelik çarklar yere savruluyor."
                    if is_tr else "The mechanical shell crane lies crushed; heavy iron hoist gears snap across the stone floor.",
                    "role": "narrator", "emphasis": ["shell crane", "iron hoist gears"], "scale": "close",
                    "scene": "Close documentary inspection of the destroyed shell hoist mechanism inside Mecidiye Bastion on 18 March 1915; twisted iron gears, snapped chains, and rubble.",
                    "proof": "The broken mechanical shell crane and twisted iron chains inside the battery",
                    "action": "Dust settles over the crushed mechanical crane and snapped chains on the battery floor; gunners assess the damage with urgent purposeful movement.",
                    "lighting": "smoke-softened daylight with warm ember highlights",
                    "location_id": "dardanelles_broken_crane",
                },
                {
                    "text": "Seyit Onbaşı 215 kiloluk dev Krupp mermisini sırtına alıyor."
                    if is_tr else "Corporal Seyit bends low, heaving a colossal two-hundred-fifteen kilogram shell onto his back.",
                    "role": "narrator", "emphasis": ["Corporal Seyit", "two-hundred-fifteen kilogram"], "scale": "close",
                    "scene": "Corporal Seyit Onbaşı bending down beside the ammunition depot inside Mecidiye Bastion, wrapping his arms around a massive 215kg artillery shell.",
                    "proof": "Corporal Seyit lifting the heavy 215kg artillery shell onto his back",
                    "action": "Corporal Seyit strains every tendon and lifts the massive heavy shell onto his shoulders, muscles corded under his khaki uniform as boots dig into crushed limestone.",
                    "lighting": "directional daylight through powder haze",
                    "location_id": "dardanelles_seyit_lift",
                },
                {
                    "text": "İnsanüstü bir gayretle topun taş basamaklarını tırmanıyor."
                    if is_tr else "Step by agonizing step under the immense weight, he ascends the stone battery stairs.",
                    "role": "narrator", "emphasis": ["agonizing step", "stone battery stairs"], "scale": "medium",
                    "scene": "Corporal Seyit Onbaşı carrying the colossal 215kg shell on his back up the massive stone steps leading to the gun platform at Mecidiye Bastion.",
                    "proof": "Seyit Onbaşı carrying the massive 215kg shell up the battery stone steps",
                    "action": "Seyit climbs the stone steps under the colossal weight of the shell; boots strike solid limestone as he advances toward the gun mount.",
                    "lighting": "cool reflected daylight and deep gunmetal shadows",
                    "location_id": "dardanelles_steps_climb",
                },
                {
                    "text": "Seyit ve Niğdeli Ali mermiyi 28'lik topun namlusuna sürüyor."
                    if is_tr else "Reaching the mount, Seyit and Niğdeli Ali slide the shell home into the Krupp cannon.",
                    "role": "narrator", "emphasis": ["slide the shell", "Krupp cannon"], "scale": "close",
                    "scene": "Seyit Onbaşı and comrade Niğdeli Ali hand-guiding the massive heavy shell into the open breech of the heavy 28cm Krupp coastal gun.",
                    "proof": "The heavy shell sliding into the breech of the 28cm Krupp coastal gun",
                    "action": "Seyit and Niğdeli Ali carefully guide the shell into the open breech; hands push the round forward in one coordinated movement.",
                    "lighting": "gray daylight broken by powder smoke",
                    "location_id": "dardanelles_breech_load",
                },
                {
                    "text": "Mecidiye'deki bu eşsiz kahramanlık, tüm boğaz savaşının kaderini değiştiriyor."
                    if is_tr else "Standing here in the smoke, this single heroic stand turns the entire naval battle.",
                    "role": "host_nova", "emphasis": ["heroic stand", "entire naval battle"], "scale": "medium",
                    "scene": "Nova on the Gallipoli peninsula at the midpoint turning point; drifting powder smoke behind her, glowing brass temporal chronometer on left wrist.",
                    "proof": "Nova witnessing the pivotal turning point of the 18 March battle; glowing chronometer",
                    "action": "Nova turns toward the camera as powder smoke thins behind her; observing the dramatic turn of the naval engagement with intense historical emotion.",
                    "lighting": "dramatic chiaroscuro daylight through thinning smoke",
                    "location_id": "gallipoli_midpoint_turning_point",
                    "character_reference": True,
                },
                {
                    "text": "Topçular çelik kamayı kapatıp namluyu Bouvet zırhlısına kilitliyor."
                    if is_tr else "Crewmen lock the steel breech and crank handwheels, aiming the gun directly at battleship Bouvet.",
                    "role": "narrator", "emphasis": ["lock steel breech", "aiming directly"], "scale": "medium",
                    "scene": "The 28cm Krupp coastal artillery piece being traversed toward the Allied fleet in the narrows; gunners turning heavy handwheels.",
                    "proof": "The 28cm Krupp gun traversed toward the Allied line in the strait",
                    "action": "Gunners turn the traversing wheels rapidly to aim the massive rifled steel barrel across the water toward the approaching warships.",
                    "lighting": "gray daylight broken by powder smoke",
                    "location_id": "dardanelles_gun_traverse",
                },
                {
                    "text": "Ateş! 28'lik dev top kulakları sağır eden gürlemeyle patlıyor."
                    if is_tr else "Fire! The giant Krupp cannon discharges with a thunderous recoil blast across the battery.",
                    "role": "narrator", "emphasis": ["Fire", "thunderous recoil blast"], "scale": "wide",
                    "scene": "The 28cm Krupp coastal cannon firing once toward the Allied fleet; massive orange muzzle flash, recoil jolt, and thick powder smoke.",
                    "proof": "A coastal gun firing with massive recoil from an Ottoman battery during the naval assault",
                    "action": "The cannon fires once, recoiling powerfully along its carriage as dense powder smoke rolls over the stone position and water shakes.",
                    "lighting": "brief hot muzzle flash in cold smoke",
                    "location_id": "dardanelles_gun_firing",
                },
                {
                    "text": "Ağır mermi Bouvet zırhlısının su kesimine tam isabet kaydediyor."
                    if is_tr else "The heavy shell screams across the channel, scoring a direct waterline impact on French battleship Bouvet.",
                    "role": "narrator", "emphasis": ["direct waterline impact", "battleship Bouvet"], "scale": "wide",
                    "scene": "Artillery shell impact near the waterline of the French battleship Bouvet in the Dardanelles; colossal water and iron explosion.",
                    "proof": "Direct artillery shell strike on the French battleship Bouvet",
                    "action": "A massive water and steel explosion erupts along the waterline of the battleship Bouvet as the heavy shell impacts.",
                    "lighting": "cold daylight with explosion flash",
                    "location_id": "dardanelles_bouvet_impact",
                },
                {
                    "text": "Bouvet'nin cephaneliği havaya uçuyor; göğe dev kara dumanlar yükseliyor."
                    if is_tr else "Internal magazines detonate aboard Bouvet, sending a colossal fire column through the warship's deck.",
                    "role": "narrator", "emphasis": ["magazines detonate", "colossal fire column"], "scale": "wide",
                    "scene": "The French battleship Bouvet suffering a massive internal explosion in the Dardanelles; billowing yellow-black smoke column rising over the water.",
                    "proof": "Internal magazine explosion tearing through the French battleship Bouvet",
                    "action": "A secondary magazine explosion tears through the deck of Bouvet; billowing black and yellow smoke rises into the overcast sky.",
                    "lighting": "cold storm light with orange fire glow",
                    "location_id": "dardanelles_bouvet_explosion",
                },
                {
                    "text": "Fransız zırhlısı Bouvet hızla yan yatıp boğazın sularına gömülüyor."
                    if is_tr else "The French battleship Bouvet lists violently and capsizes into the Dardanelles within two minutes.",
                    "role": "narrator", "emphasis": ["Bouvet lists", "capsizes into Dardanelles"], "scale": "wide",
                    "scene": "The French battleship Bouvet in the Dardanelles on 18 March 1915, listing sharply to starboard as waves pour over the deck and hull capsizes.",
                    "proof": "French battleship Bouvet listing and capsizing into the Dardanelles",
                    "action": "Bouvet rolls onto its side as cold sea water pours over the superstructure; the warship slips beneath the surface amid swirling foam.",
                    "lighting": "cold daylight through smoke haze",
                    "location_id": "dardanelles_bouvet_capsizes",
                },
                {
                    "text": "Mayınlara çarpan diğer zırhlılarla donanma panik içinde geri çekiliyor."
                    if is_tr else "Panic sweeps the fleet as striking mines disables further warships, forcing an immediate disordered retreat.",
                    "role": "narrator", "emphasis": ["panic sweeps fleet", "disordered retreat"], "scale": "medium",
                    "scene": "Ottoman artillerymen and Corporal Seyit on the ramparts of Mecidiye Bastion watching the retreating Allied fleet through thinning battle smoke.",
                    "proof": "The surviving Allied fleet turning away in retreat past drifting wreckage",
                    "action": "Surviving Allied warships turn away toward open water as gunners and Corporal Seyit watch from the sandbagged parapet with weary pride.",
                    "lighting": "late afternoon haze over rough water",
                    "location_id": "dardanelles_fleet_retreat",
                },
                {
                    "text": "Gün batarken donanma kaçıyor; Çanakkale'nin geçilemeyeceği tarihe mühürleniyor."
                    if is_tr else "By evening the armada retreats; the sea attack has failed and the Dardanelles remains forever impassable.",
                    "role": "host_nova", "emphasis": ["armada retreats", "forever impassable"], "scale": "wide",
                    "scene": "Nova stands on the Gallipoli shore at dusk watching the surviving Allied fleet withdraw from the Dardanelles; wool-and-linen camouflage, glowing temporal chronometer.",
                    "proof": "The Gallipoli shoreline at evening as the Allied fleet withdraws; Nova's brass chronometer",
                    "action": "Nova lowers her field map and watches the ships turn toward open water; wind pulls at her coat as the camera moves from her shoulder to the receding horizon.",
                    "lighting": "restrained dusk light with smoke fading into the horizon",
                    "location_id": "gallipoli_1915_shore_evening",
                    "character_reference": True,
                },
            ]

        # 15-block gunner crew sequence (tracks gunner story arc on continuous battery location)
        return [
            {
                "text": "18 Mart 1915 sabahı Çanakkale Boğazı'ndayım; devasa Müttefik armadası boğazın dar sularına giriyor."
                if is_tr else "I have stepped onto Gallipoli as warships enter the strait.",
                "role": "host_nova",
                "emphasis": ["stepped onto Gallipoli", "warships"],
                "scale": "wide",
                "scene": "Nova arrives on the Gallipoli shore on 18 March 1915, Allied battleships advancing into the narrow Dardanelles; period wool coat and brass chronometer on her left wrist.",
                "proof": "Nova's brass temporal chronometer; Allied battleships entering the Dardanelles on 18 March 1915",
                "action": "Nova steps out of salt spray and turns toward the distant ships; her coat and hair move in the coastal wind, camera follows her gaze to the strait.",
                "lighting": "gray dawn beneath smoke-heavy coastal cloud",
                "location_id": "gallipoli_battery_story_hook",
                "character_reference": True,
            },
            {
                "text": "Zırhlıların ağır topları kıyı tabyasını dövüyor; duman ve su sütunları boğazı kaplıyor."
                if is_tr else "Their shells crash around the battery; smoke hides the water.",
                "role": "narrator",
                "emphasis": ["shells crash", "smoke"],
                "scale": "wide",
                "scene": "Allied battleship guns bombard an Ottoman shore battery on 18 March 1915; shell splashes rise beyond the stone position and dark powder smoke crosses the channel.",
                "proof": "Allied battleship bombardment of Ottoman coastal battery during the 18 March attack",
                "action": "A distant shell strikes the hillside beyond the battery, throwing up dust as smoke drifts across the gun position; camera tracks from shaking sandbags toward the obscured water.",
                "lighting": "smoke-diffused cold daylight",
                "location_id": "dardanelles_battery_under_fire",
            },
            {
                "text": "Dumanların arasında tabyadaki Osmanlı topçularının yanına ulaşıyorum."
                if is_tr else "I meet an Ottoman gunner beside his artillery crew.",
                "role": "host_nova",
                "visual_role": "field_interview",
                "emphasis": ["Ottoman gunner", "crew"],
                "scale": "medium",
                "scene": "Nova, matching her established face and Ottoman-era wool-and-linen camouflage with brass chronometer, meets a tired Ottoman coastal gunner beside his 1915 artillery crew and heavy gun.",
                "proof": "A time-traveler host meeting an Ottoman coastal gun crew at its battery",
                "action": "Nova leans in to ask the gunner a question with a small hand gesture; he answers without speaking by pointing toward the next shell. Both keep neutral closed mouths; no audible dialogue or lip movement.",
                "lighting": "warm firelight through powder smoke",
                "location_id": "dardanelles_gunner_interview",
                "character_reference": True,
            },
            {
                "text": "Top çavuşu bir sonraki mermiyi işaret ediyor; erler derhal harekete geçiyor."
                if is_tr else "He nods toward the next round. The crew begins hauling.",
                "role": "narrator",
                "emphasis": ["next round", "hauling"],
                "scale": "medium",
                "scene": "At the same Dardanelles battery, an Ottoman gun crew prepares another artillery round while Nova watches from the side; period-correct wool uniforms and sandbagged gun position.",
                "proof": "The crew moving the next artillery round toward the gun",
                "action": "The gunner signals toward a shell and two crewmen step in, grip it together, and begin hauling it over the rough battery floor; Nova watches beside them.",
                "lighting": "smoke-softened daylight with warm ember highlights",
                "location_id": "dardanelles_gunner_interview",
                "character_reference": True,
            },
            {
                "text": "Topçular devasa çelik mermiyi birlikte kavrayıp yukarı kaldırıyor."
                if is_tr else "They grip the shell and lift it together.",
                "role": "narrator",
                "emphasis": ["grip the shell", "together"],
                "scale": "close",
                "scene": "Close documentary view of Ottoman artillerymen lifting a heavy period shell between them inside a Dardanelles shore battery, wool sleeves, leather gloves and gun carriage visible.",
                "proof": "Several artillerymen coordinating to lift one heavy shell",
                "action": "Three crewmen brace their boots and raise the shell in a coordinated lift; camera moves beside their hands and the round without losing the men performing the work.",
                "lighting": "directional daylight through powder haze",
                "location_id": "dardanelles_shell_lift",
            },
            {
                "text": "Biri mermiyi dengelerken diğeri topun açık kamasını hizalıyor."
                if is_tr else "One steadies it as another aligns the breech.",
                "role": "narrator",
                "emphasis": ["steadies", "breech"],
                "scale": "close",
                "scene": "Ottoman artillery crew hand-guiding a shell toward the breech of a heavy 1915 coastal gun, exact mechanical scale and period gun carriage.",
                "proof": "The shell aligned with the open breech of the coastal gun",
                "action": "One gunner steadies the shell while a second aligns it with the open breech; hands guide the round forward in one careful motion, camera pushes in at shoulder height.",
                "lighting": "cool reflected daylight and deep gunmetal shadows",
                "location_id": "dardanelles_breech_load",
            },
            {
                "text": "Mermiyi namluya sürüp kamayı kilitliyorlar, ardından topu boğaza çeviriyorlar."
                if is_tr else "They ram it home, then swing the gun seaward.",
                "role": "narrator",
                "emphasis": ["ram it home", "seaward"],
                "scale": "medium",
                "scene": "A period Ottoman coastal artillery piece traversing toward the Allied fleet, crew at the breech and hand wheels, smoke and stone revetment behind.",
                "proof": "The loaded Ottoman coastal gun being aimed toward the strait",
                "action": "The crew secures the breech, then turns the gun toward the channel using the traversing wheels; camera tracks the barrel across the battery toward the fleet.",
                "lighting": "gray daylight broken by powder smoke",
                "location_id": "dardanelles_gun_traverse",
            },
            {
                "text": "Top kulakları sağır eden bir gürlemeyle ateşleniyor; patlama taş mevziyi sarsıyor."
                if is_tr else "The cannon fires; the blast shakes the stone position.",
                "role": "narrator",
                "emphasis": ["cannon fires", "blast"],
                "scale": "wide",
                "scene": "Ottoman shore gun firing once toward the Allied fleet from its stone battery on 18 March 1915; visible crew, recoil, and powder smoke.",
                "proof": "A coastal gun firing from an Ottoman battery during the naval assault",
                "action": "The cannon fires once, recoiling along its carriage as the crew braces and dense powder smoke rolls over the stone position; camera jolts subtly with the blast.",
                "lighting": "brief hot muzzle flash in cold smoke",
                "location_id": "dardanelles_gun_firing",
            },
            {
                "text": "Aralıksız bombardıman altında bu ateşi ne kadar sürdürebileceklerini soruyorum."
                if is_tr else "I ask how long they can keep firing.",
                "role": "host_nova",
                "visual_role": "field_interview",
                "emphasis": ["keep firing"],
                "scale": "medium",
                "scene": "Nova and the same Ottoman gunner beside the same coastal gun, brief side-on field interview framed through drifting powder smoke; both in consistent period setting.",
                "proof": "The field interview returns to the same gunner and active battery",
                "action": "Nova gestures toward the gun and asks a question without speaking on camera; the gunner answers only with a determined nod and turns toward his crew, mouths neutral and closed.",
                "lighting": "soft amber light through a thinning veil of smoke",
                "location_id": "dardanelles_gunner_interview",
                "character_reference": True,
            },
            {
                "text": "Durmak yok: sonraki ağır mermi şimdiden namluya doğru taşınıyor."
                if is_tr else "No pause: the next shell is already moving forward.",
                "role": "narrator",
                "emphasis": ["no pause", "next shell"],
                "scale": "medium",
                "scene": "The same Ottoman gun crew immediately preparing a second shell while the first shot's smoke still hangs over the battery.",
                "proof": "The crew beginning the next loading cycle before the smoke clears",
                "action": "Crewmen carry another round from the ammunition stack toward the open breech as the gunner checks the position; keep the movement continuous and purposeful.",
                "lighting": "dusty daylight with residual powder haze",
                "location_id": "dardanelles_next_round",
            },
            {
                "text": "Tabyanın ötesinde, mayın tarama gemileri boğaz kanalını temizlemeye çalışıyor."
                if is_tr else "Beyond the battery, minesweepers probe the channel.",
                "role": "narrator",
                "emphasis": ["minesweepers", "channel"],
                "scale": "wide",
                "scene": "Small period minesweeping trawlers work ahead of the Allied battleships in the Dardanelles on 18 March 1915, under fire from shore batteries.",
                "proof": "Minesweeping vessels working ahead of the Allied fleet",
                "action": "A trawler pulls sweep gear through choppy water while nearby shells splash and crewmen haul taut lines; camera tracks low along the moving wake.",
                "lighting": "flat gray daylight and drifting gun smoke",
                "location_id": "dardanelles_minesweepers_under_fire",
            },
            {
                "text": "Kıyı bataryaları ateşi sürdürürken Müttefik zırhlıları boğaza doğru yükleniyor."
                if is_tr else "Ottoman shore guns fire as the fleet pushes on.",
                "role": "narrator",
                "emphasis": ["shore guns", "fleet pushes on"],
                "scale": "wide",
                "scene": "Allied battleships continue through the Dardanelles while Ottoman coastal guns fire from the rocky shore, 18 March 1915.",
                "proof": "The Allied fleet advancing under fire from shore batteries",
                "action": "Battleships move forward as a shore gun flashes and water bursts near a trawler; smoke streams with the wind while the camera pans from battery to fleet.",
                "lighting": "cold, smoke-filtered afternoon daylight",
                "location_id": "dardanelles_fleet_under_fire",
            },
            {
                "text": "Tam o sırada Fransız zırhlısı Bouvet gizli mayın hattına çarpıyor."
                if is_tr else "Then the French battleship Bouvet strikes a mine.",
                "role": "narrator",
                "emphasis": ["Bouvet", "strikes a mine"],
                "scale": "wide",
                "scene": "The French battleship Bouvet in the Dardanelles on 18 March 1915, period pre-dreadnought silhouette on rough gray water.",
                "proof": "Bouvet struck by a mine during the 18 March naval assault",
                "action": "A mine detonates beside Bouvet's hull; the ship shudders and begins to list as water surges across its deck, camera sweeps over the disturbed surface.",
                "lighting": "cold daylight through blast smoke",
                "location_id": "dardanelles_bouvet_strike",
            },
            {
                "text": "Bouvet sulara gömülüyor; diğer iki zırhlı terk ediliyor, biri ağır hasar alıyor."
                if is_tr else "It sinks; two other ships are abandoned, another damaged.",
                "role": "narrator",
                "emphasis": ["two other ships", "another damaged"],
                "scale": "wide",
                "scene": "A distant historical tableau of Allied fleet losses on 18 March 1915: one sinking ship, rescue boats beside an abandoned battleship, and another damaged vessel withdrawing.",
                "proof": "Bouvet, Irresistible, and Ocean lost; Inflexible damaged in the 18 March attack",
                "action": "Rescue boats pull sailors from the water beside a disabled ship as another damaged battleship turns away through smoke; keep ships distinct and the action non-graphic.",
                "lighting": "late afternoon haze over rough water",
                "location_id": "dardanelles_fleet_losses",
            },
            {
                "text": "Akşam inerken donanma geri çekiliyor; deniz saldırısı kesin olarak püskürtülüyor."
                if is_tr else "By evening the fleet retreats. The sea attack has failed.",
                "role": "host_nova",
                "emphasis": ["fleet retreats", "attack has failed"],
                "scale": "wide",
                "scene": "Nova stands on the Gallipoli shore at dusk watching the surviving Allied fleet withdraw from the Dardanelles; same face, wool-and-linen period camouflage and left-wrist brass chronometer.",
                "proof": "The Allied fleet withdrawing from the Dardanelles at evening",
                "action": "Nova lowers a field map and watches the ships turn toward open water; wind pulls at her coat as the camera moves from her shoulder to the receding formation.",
                "lighting": "restrained dusk light with smoke fading into the horizon",
                "location_id": "gallipoli_fleet_retreat",
                "character_reference": True,
            },
        ]

    # 6-block smoke outline
    return [
        {
            "text": "At dawn on 18 March 1915, I watch Allied battleships enter the Dardanelles, expecting gunfire to open the route toward Constantinople.",
            "role": "host_nova", "emphasis": ["18 March 1915", "Dardanelles"], "scale": "wide",
            "scene": "Nova arrives at the Gallipoli shore at dawn, 18 March 1915; period wool field coat and brass chronometer on her left wrist, Allied battleships entering the distant strait.",
            "proof": "Nova's brass temporal chronometer; Allied battleships entering the Dardanelles on 18 March 1915",
            "action": "Nova steps against the coastal wind and unfolds a field map as the fleet advances; her coat and hair move naturally, camera glides from her shoulder toward the strait.",
            "lighting": "golden dawn beneath heavy coastal cloud",
            "location_id": "gallipoli_1915_shore_dawn",
            "character_reference": True,
        },
        {
            "text": "The Ottoman minelayer Nusret laid twenty-six mines in Erenköy Bay on 8 March, hidden beneath a dark, choppy surface.",
            "role": "narrator", "emphasis": ["Nusret", "twenty-six mines"], "scale": "medium",
            "scene": "The Ottoman minelayer Nusret laying a line of twenty-six contact mines in Erenköy Bay on the night of 8 March 1915; authentic early twentieth-century vessel and naval crew.",
            "proof": "Nusret and its mine-laying operation in Erenköy Bay",
            "action": "Nusret moves through black water as sailors haul one contact mine over the rail and lower it with period rigging; rope strains, wake ripples, deck lamps flicker.",
            "lighting": "cold moonlight with warm deck lanterns",
            "location_id": "erenkoy_bay_1915_night",
        },
        {
            "text": "Ottoman coastal batteries answered with smoke and thunder as crews loaded shells, reset their guns, and fired across the strait.",
            "role": "narrator", "emphasis": ["coastal batteries", "fired"], "scale": "close",
            "scene": "Ottoman coastal artillery battery at the Dardanelles on 18 March 1915; period heavy 28cm Krupp gun, wool-uniformed artillery crew, sandbags and powder smoke.",
            "proof": "An Ottoman artillery crew loading and firing a period coastal gun",
            "action": "Crewmen haul a shell, load the breech, traverse the gun and fire once; recoil jolts the barrel as powder smoke rolls past.",
            "lighting": "chiaroscuro daylight filtered through powder smoke",
            "location_id": "dardanelles_battery_1915",
        },
        {
            "text": "The French battleship Bouvet struck a mine and capsized; Irresistible and Ocean were also lost during the retreat.",
            "role": "narrator", "emphasis": ["Bouvet", "mine"], "scale": "wide",
            "scene": "The French battleship Bouvet in the Dardanelles on 18 March 1915, historically grounded pre-dreadnought silhouette on rough gray water, non-graphic depiction.",
            "proof": "Bouvet listing and capsizing after striking a mine",
            "action": "Bouvet takes a mine blast along the hull, lists sharply and capsizes as waves surge over the deck; distant ships alter course.",
            "lighting": "cold storm light with brief orange blast illumination",
            "location_id": "dardanelles_bouvet_1915",
        },
        {
            "text": "The Allied fleet withdrew. The failed sea passage did not end the campaign; troops landed on Gallipoli on 25 April 1915.",
            "role": "narrator", "emphasis": ["withdrew", "25 April 1915"], "scale": "medium",
            "scene": "A damaged Allied warship withdrawing from the Dardanelles after the failed naval assault; smoke trails past the rocky peninsula.",
            "proof": "The fleet turning away from the Dardanelles after the failed passage",
            "action": "The damaged ship turns away under its own power as smaller period vessels maneuver through choppy water to assist; smoke drifts downwind.",
            "lighting": "muted late-afternoon light with smoke haze",
            "location_id": "dardanelles_retreat_1915",
        },
        {
            "text": "The struggle shifted from sea to shore and endured months, leaving a legacy remembered in Turkey, Australia, New Zealand, and Britain.",
            "role": "host_nova", "emphasis": ["sea to shore", "legacy"], "scale": "wide",
            "scene": "Nova walks the Gallipoli shoreline at evening, same face, chestnut hair, left-wrist brass chronometer and 1915 wool-and-linen camouflage; the Dardanelles opens behind her.",
            "proof": "The Gallipoli peninsula and the sea-to-land campaign shift",
            "action": "Nova folds her map and walks along the wind-beaten shore; waves cross the rocks and clouds move over the strait as the camera tracks backward.",
            "lighting": "soft overcast evening light, reflective and restrained",
            "location_id": "gallipoli_1915_shore_evening",
            "character_reference": True,
        },
    ]


def get_pompeii_curated_beats(total_blocks: int, lang: str = "en") -> list[dict[str, Any]]:
    """Return curated beats for the 79 AD Pompeii documentary (eve of Vesuvius eruption)."""
    is_tr = (lang or "en").strip().casefold() == "tr"

    return [
        {
            "text": "MS 79... Vezüv patlamadan bir gün önce Pompei'deyim."
            if is_tr else "On 23 August 79 AD, I enter Pompeii before Vesuvius erupts.",
            "role": "host_nova", "emphasis": ["Pompeii", "Vesuvius"], "scale": "wide",
            "scene": "Nova arrives on the polygonal basalt stone street of Pompeii in 79 AD; draped Roman wool mantle, left-wrist brass temporal chronometer; Mount Vesuvius looming on the horizon.",
            "proof": "Nova's brass temporal chronometer; Mount Vesuvius looming behind the ancient Roman city of Pompeii",
            "action": "Nova steps across the raised basalt pedestrian stepping stones as citizens pass; morning sunlight filters through colonnades as camera pans from her shoulder toward Vesuvius.",
            "lighting": "warm Mediterranean morning sunlight",
            "location_id": "pompeii_street_arrival_hook",
            "character_reference": True,
        },
        {
            "text": "Romalılar dükkanlardan taze sıcak sabah yemekleri alıyor."
            if is_tr else "Roman citizens gather at thermopolium snack counters for warm morning food.",
            "role": "narrator", "emphasis": ["Roman citizens", "thermopolium"], "scale": "medium",
            "scene": "A vibrant Roman thermopolium snack bar with embedded terracotta dolia jars in marble counters; Roman citizens in unbleached wool tunics buying food.",
            "proof": "Frescoed Roman thermopolium counter with embedded storage jars",
            "action": "A shopkeeper ladles warm pulses into terracotta bowls for customers while citizens converse with lively hand gestures; steam rises into the morning air.",
            "lighting": "dappled morning sunlight under terracotta awnings",
            "location_id": "pompeii_thermopolium_scene",
        },
        {
            "text": "Terentius Neo'nun pistrinum fırınında dev bazalt değirmentaşları dönüyor."
            if is_tr else "Inside Terentius Neo's pistrinum bakery, massive basalt mills grind grain.",
            "role": "narrator", "emphasis": ["pistrinum", "basalt mills"], "scale": "medium",
            "scene": "Inside an authentic 79 AD Roman pistrinum bakery; circular volcanic basalt lava-stone grain mills turned by wooden beams; sacks of grain on flagstone floor.",
            "proof": "Hourglass-shaped volcanic basalt lava stone grain mills inside the Roman bakery",
            "action": "Bakery workers push heavy wooden beams to rotate the upper catillus stone mill; golden grain feeds into the hopper as stone grinds rhythmically.",
            "lighting": "soft side light through high arched bakery windows with flour dust in the air",
            "location_id": "pompeii_pistrinum_mills",
        },
        {
            "text": "Fırıncılar hamuru sekiz dilimli Pompei ekmeklerine şekillendiriyor."
            if is_tr else "Bakers knead sourdough into eight-wedge circular panis quadratus loaves.",
            "role": "narrator", "emphasis": ["knead sourdough", "panis quadratus"], "scale": "close",
            "scene": "Roman bakers hand-kneading dough on heavy stone tables and tying linen strings around circular panis quadratus loaves with eight radial cuts.",
            "proof": "Circular Roman panis quadratus bread loaves with eight radial scores on a stone table",
            "action": "Bakers rhythmically knead dough, stamp the center seal, and tie linen string around the circumference with experienced deft motions.",
            "lighting": "warm directional morning light illuminating white flour dust",
            "location_id": "pompeii_dough_kneading",
        },
        {
            "text": "Somunlar uzun küreklerle kubbeli tuğla fırına sürülüyor."
            if is_tr else "With wooden peels, bakers slide loaves into brick domed ovens.",
            "role": "narrator", "emphasis": ["wooden peels", "brick domed oven"], "scale": "close",
            "scene": "The glowing interior of a Roman brick domed baking oven, glowing wood embers pushed to the side, freshly shaped loaves sliding onto the stone floor.",
            "proof": "Authentic Roman brick domed baking oven with glowing embers and bread loaves inside",
            "action": "A baker slides a wooden peel carrying four loaves into the arched oven mouth; orange firelight flickers across his flour-dusted face and tunic.",
            "lighting": "intense warm orange firelight glow contrasting with cool ambient stone",
            "location_id": "pompeii_oven_loading",
        },
        {
            "text": "Fırından çıkan altın rengi somunlar sepetlere diziliyor."
            if is_tr else "Golden-brown loaves emerge from the oven and cool in baskets.",
            "role": "narrator", "emphasis": ["fresh loaves", "wicker baskets"], "scale": "close",
            "scene": "Golden-brown baked Roman panis quadratus loaves cooling in woven reed baskets, bread steam rising into the air.",
            "proof": "Freshly baked authentic Roman panis quadratus bread cooling in reed baskets",
            "action": "Bakers pull the charred loaves from the oven floor with a flat wooden shovel and arrange them in cooling racks with purposeful care.",
            "lighting": "warm ambient bakery lighting with soft rising steam",
            "location_id": "pompeii_cooling_loaves",
        },
        {
            "text": "Aniden zemin sarsılıyor; tavandan ince tozlar dökülüyor."
            if is_tr else "Suddenly a subtle subterranean tremor ripples through the stone rafters.",
            "role": "narrator", "emphasis": ["subterranean tremor", "timber rafters"], "scale": "medium",
            "scene": "The bakery interior during a precursor earthquake; flour dust shaken loose from ceiling beams, terracotta cups rattling on stone shelves.",
            "proof": "Subtle seismic vibration causing dust to fall and terracotta vessels to rattle",
            "action": "Bakery workers pause in mid-stride as the stone floor vibrates beneath their leather sandals; exchanging uncertain glances as dust drifts down.",
            "lighting": "volumetric shafts of morning light through sudden airborne dust",
            "location_id": "pompeii_precursor_tremor",
        },
        {
            "text": "Bu sıradan bir sarsıntı değil; Vezüv uyanıyor."
            if is_tr else "This is no ordinary rumble; Mount Vesuvius is awakening.",
            "role": "host_nova", "emphasis": ["routine tremors", "Vesuvius awakening"], "scale": "medium",
            "scene": "Nova standing in a Pompeian peristyle courtyard near the bakery; looking anxiously toward Mount Vesuvius as the ground tremors under her sandals.",
            "proof": "Nova observing the precursor seismic signs; glowing temporal chronometer",
            "action": "Nova turns toward the camera, her hand resting against a fluted stone column that subtly vibrates; expressing deep historical foreboding.",
            "lighting": "dramatic Mediterranean midday light with faint haze",
            "location_id": "pompeii_midpoint_turning_point",
            "character_reference": True,
        },
        {
            "text": "Korkunç kükremeyle Vezüv patlıyor; göğe kül sütunu fışkırıyor."
            if is_tr else "With a deafening roar, Vesuvius erupts, blasting ash skyward.",
            "role": "narrator", "emphasis": ["Vesuvius erupts", "black column of ash"], "scale": "wide",
            "scene": "Cinematic wide vista of Mount Vesuvius exploding; monumental pine-tree shaped Plinian eruptive column of dark volcanic ash and tephra climbing into the blue sky.",
            "proof": "Plinian eruptive ash column rising from Mount Vesuvius above Pompeii",
            "action": "The towering eruptive cloud expands rapidly like an umbrella pine, casting a massive shadow across the Bay of Naples as shockwaves ripple outward.",
            "lighting": "harsh sunlight cut in half by towering black volcanic ash shadow",
            "location_id": "vesuvius_catastrophic_eruption",
        },
        {
            "text": "Dev kül bulutu güneşi karartıyor; şehir karanlığa bürünüyor."
            if is_tr else "The expanding ash umbrella blots out the midday sun in darkness.",
            "role": "narrator", "emphasis": ["blots out the sun", "unnatural darkness"], "scale": "wide",
            "scene": "Pompeii forum under the darkening sky; the midday sun obscured by dense volcanic fallout; eerie twilight settling over Roman temples and arches.",
            "proof": "Midday sky turning dark under the expanding volcanic ash cloud",
            "action": "Darkness spreads rapidly across the cityscape as daylight fades to an apocalyptic copper-brown gloom; wind howls through colonnades.",
            "lighting": "dim apocalyptic bronze-brown twilight beneath dense tephra canopy",
            "location_id": "pompeii_darkening_forum",
        },
        {
            "text": "Forumda panik başlıyor; çatılara ponza taşları yağıyor."
            if is_tr else "Panic sweeps the forum as gray pumice rains onto roofs.",
            "role": "narrator", "emphasis": ["panic sweeps", "pumice stones"], "scale": "medium",
            "scene": "The Pompeii forum as pumice stones (lapilli) rain down; Roman citizens clutching woolen cloaks over their heads as they seek shelter under porticos.",
            "proof": "Volcanic pumice stones accumulating across Roman paved streets and colonnades",
            "action": "Citizens hurry across the square covering their heads with folded togas and wooden pillows; pumice stones bounce and clatter on the stone floor.",
            "lighting": "dim ambient light punctured by distant volcanic flashes",
            "location_id": "pompeii_lapilli_rain",
        },
        {
            "text": "Fırıncı Neo, para kasasını mühürleyip ailesini topluyor."
            if is_tr else "Baker Neo seals his bronze chest and evacuates his family.",
            "role": "narrator", "emphasis": ["secures coin chest", "pumice piles up"], "scale": "close",
            "scene": "Inside the bakery, the baker hastily sealing an iron-bound money box with a bronze key as pumice stones cascade through the open doorway.",
            "proof": "Roman iron-bound wooden money chest and bronze keys inside the bakery",
            "action": "The baker secures the lock and scoops up his household wax tablets, motioning urgently for his family to move toward the street.",
            "lighting": "flickering oil lamp light in the dark interior",
            "location_id": "pompeii_baker_evacuation",
        },
        {
            "text": "Ponza tabakası yükseliyor; sokaklar volkanik taşlarla doluyor."
            if is_tr else "Pumice accumulates relentlessly, burying doorways under heavy volcanic fallout.",
            "role": "narrator", "emphasis": ["pumice and ash", "burying doorways"], "scale": "medium",
            "scene": "A residential street in Pompeii where deep gray pumice has accumulated half a meter high against house thresholds and stone walls.",
            "proof": "Deep accumulation of gray volcanic lapilli along Roman street walls and door thresholds",
            "action": "Falling tephra piles against wooden doors as heavy roof tiles creak under volcanic load; dust billows in the hot volcanic wind.",
            "lighting": "dark murky volcanic twilight with lightning flickers in distant cloud",
            "location_id": "pompeii_tephra_burial",
        },
        {
            "text": "Halk limana kaçıyor; koca medeniyet geride kalıyor."
            if is_tr else "Citizens flee toward the sea, leaving ancient Pompeii behind.",
            "role": "narrator", "emphasis": ["citizens flee", "frozen in time"], "scale": "wide",
            "scene": "Crowds of Roman citizens moving through the arched Marine Gate of Pompeii toward the sea; dark volcanic clouds swirling behind them.",
            "proof": "Roman citizens evacuating through the arched city gate under volcanic skies",
            "action": "Silhouettes of evacuating citizens move with urgent determination down the coastal road as ash drifts around their garments.",
            "lighting": "silhouette lighting against dark storm sky",
            "location_id": "pompeii_city_gate_evacuation",
        },
        {
            "text": "Pompei gömülüyor; Roma'nın bir günü sonsuzluğa mühürleniyor."
            if is_tr else "Ash blankets Pompeii; an entire Roman day is preserved forever.",
            "role": "host_nova", "emphasis": ["temporal window", "preserved forever"], "scale": "wide",
            "scene": "Nova standing near the ancient city walls at dusk as volcanic tephra falls gently around her; left-wrist brass chronometer glowing with amber temporal energy.",
            "proof": "Nova's glowing temporal chronometer against the timeless horizon of Pompeii under falling ash",
            "action": "Nova looks back toward the buried city with reverence and deep documentary emotion; her chronometer gyroscopes spin as she prepares for extraction.",
            "lighting": "soft amber glow from chronometer in the dark twilight",
            "location_id": "pompeii_closing_verdict",
            "character_reference": True,
        },
    ]
