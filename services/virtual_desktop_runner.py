from __future__ import annotations
import logging
import ctypes

logger = logging.getLogger(__name__)

try:
    from pyvda import AppView, VirtualDesktop, get_virtual_desktops
    PYVDA_AVAILABLE = True
except ImportError:
    PYVDA_AVAILABLE = False
    logger.warning("pyvda not installed. VirtualDesktopRunner will run directly on current desktop.")

def _get_chrome_hwnds():
    hwnds = []
    user32 = ctypes.windll.user32
    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                if "Google Flow" in buff.value and "Chrome" in buff.value:
                    hwnds.append(hwnd)
        return 1
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    return hwnds

class VirtualDesktopRunner:
    @staticmethod
    def run_isolated(func, *args, **kwargs):
        if not PYVDA_AVAILABLE:
            logger.warning("Falling back to direct execution due to missing pyvda.")
            return func(*args, **kwargs)
        
        try:
            desktops = get_virtual_desktops()
            current_desktop = VirtualDesktop.current()
            
            if len(desktops) < 2:
                logger.info("Creating a new virtual desktop for isolation.")
                target_desktop = VirtualDesktop.create()
            else:
                target_desktop = next((d for d in desktops if d.number != current_desktop.number), desktops[1])
            
            # Move Chrome window(s) to the new desktop  
            for hwnd in _get_chrome_hwnds():
                try:
                    AppView(hwnd=hwnd).move(target_desktop)
                except Exception as e:
                    logger.warning(f"Failed to move chrome hwnd {hwnd}: {e}")
            
            # Switch to the new desktop
            target_desktop.go()
            
            # Execute the function
            logger.info(f"Executing function isolated on desktop {target_desktop.number}")
            result = func(*args, **kwargs)
            
            return result
        except Exception as e:
            logger.error(f"Error during isolated execution: {e}")
            raise
        finally:
            if PYVDA_AVAILABLE:
                try:
                    current_desktop.go()
                except Exception as e:
                    logger.error(f"Failed to return to original desktop: {e}")

