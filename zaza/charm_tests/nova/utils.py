"""Data for nova tests."""

FLAVORS = {
    'm1.tiny': {
        'flavorid': 1,
        'ram': 512,
        'disk': 1,
        'vcpus': 1},
    'm1.small': {
        'flavorid': 2,
        'ram': 2048,
        'disk': 20,
        'vcpus': 1},
    'm1.medium': {
        'flavorid': 3,
        'ram': 4096,
        'disk': 40,
        'vcpus': 2},
    'm1.large': {
        'flavorid': 4,
        'ram': 8192,
        'disk': 40,
        'vcpus': 4},
}
KEYPAIR_NAME = 'zaza'
