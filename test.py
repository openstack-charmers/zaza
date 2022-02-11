import zaza
import zaza.model

zaza.get_or_create_libjuju_thread()
print(zaza.model.get_units('ubuntu'))
zaza.clean_up_libjuju_thread()
