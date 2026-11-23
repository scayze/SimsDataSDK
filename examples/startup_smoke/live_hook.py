"""Test-only game callback. Loaded from the disposable Sims 4 profile."""

from functools import wraps
from traceback import format_exc

import services
from server_commands.persistence_commands import save_to_new_slot
from zone import Zone


def log(message):
    with open(LOG_PATH, "a", encoding="utf-8") as output:
        print(message, file=output)


original = Zone.on_loading_screen_animation_finished
saved = False


@wraps(original)
def loading_finished(self, *args, **kwargs):
    global saved
    result = original(self, *args, **kwargs)
    household = services.active_household()
    if not saved and household is not None and household.home_zone_id == self.id:
        try:
            save_to_new_slot(127, "SDK Startup Smoke", 0, False)
            saved = True
            log("Live Mode save requested.")
        except Exception:
            log(format_exc())
            raise
    return result


Zone.on_loading_screen_animation_finished = loading_finished
log("Live Mode hook loaded.")
