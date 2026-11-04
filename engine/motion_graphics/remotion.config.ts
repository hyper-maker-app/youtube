/**
 * Remotion configuration file
 * Broadcast standard: 1920x1080 @ 60 FPS
 * Optimized for headless Chromium and hardware-accelerated rendering.
 */
import { Config } from '@remotion/cli/config';

// Render encoding settings
Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(95);
Config.setPixelFormat('yuv420p');
Config.setCodec('h264');
Config.setCrf(18);

// Chromium headless & acceleration optimizations
Config.setChromiumOpenGlRenderer('angle');
Config.setChromiumHeadlessMode(true);
Config.setChromiumDisableWebSecurity(true);
Config.setChromiumIgnoreCertificateErrors(true);
Config.setOverwriteOutput(true);
