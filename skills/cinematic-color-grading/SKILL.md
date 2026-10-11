---
name: cinematic-color-grading
description: Audit and optimize 3D Cycles cinematic color grading, studio void lighting, vignette, and grain unsharp polish for Zack D. Films vertical animations.
---

# Cinematic Color Grading

Use this skill when evaluating visual aesthetics, render polish, and lighting contrast for 9:16 vertical shorts.

## Visual DNA & Lighting Rules (ADR-011, ADR-015, ADR-021)
1. **Studio Void Aesthetic**: Minimalist dark neutral 3D studio void background (R:15, G:18, B:24) with deep readable contact shadows.
2. **Key & Rim Light Matrix**:
   - 45-degree warm golden key light (5600K)
   - Sharp cyan edge/rim light (8000K) separating subject from void or background
   - Transillumination and Subsurface Scattering (SSS) on translucent organic tissue (SSS radius 1.2, deep amber-red scattering)
3. **PBR Domain Shaders**:
   - Mineralized cortical bone: ivory enamel micro-structure, high specular hardness, subtle amber glow
   - Viscous fluids: refractive index 1.33, ray-traced surface tension, suspended micro-particulates
   - Metals & mechanisms: brushed anisotropic metallic sheen, photoelastic stress concentration fringes
4. **Final Polish Filter Chain (FFmpeg)**:
   - Unsharp: unsharp=5:5:0.7 (restores crisp edges after 9:16 scaling)
   - Filmic Grain: 
oise=alls=6:allf=t+u (eliminates digital banding, adds cinematic texture)
   - Contrast & Saturation: eq=contrast=1.06:saturation=1.05 (punches up 3D depth)
   - Vignette: ignette=PI/5 (draws viewer focus to center-third action)
5. **Zero Text & Clipart Arrows**: Strictly pure visual geometry; visual proof markers must be rendered as volumetric glowing 3D energy streams (ADR-028).
