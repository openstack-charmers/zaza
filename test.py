import zaza
import zaza.model

try:
    print(zaza.model.get_units('ubuntu'))
finally:
    zaza.clean_up_libjuju_thread()
