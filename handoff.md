
## Flow Agent image: test_flow.png

The automated request stopped before `C:\Users\bekir\OneDrive\Masaüstü\Yeni klasör (2)\YOUTUBE\test_flow.png` was written. The Flow session, cookie, extension bridge, or CLI needs attention; no alternate provider was selected.

1. Open Google Flow, confirm the Flow Agent extension/bridge is ready, then run:

```powershell
flow image 'test photorealistic ancient pyramid at sunset, 16:9 widescreen, 8k documentary cinema' --model beluga --aspect landscape --count 1 --idempotency-key youtube-image-23fe1c9f7ee2b2a18551cc0aeae41f79 --output test_flow.png
```

2. Confirm the output exists at `C:\Users\bekir\OneDrive\Masaüstü\Yeni klasör (2)\YOUTUBE\test_flow.png` and resume this pipeline run.

Recorded failure: `RuntimeError`.
