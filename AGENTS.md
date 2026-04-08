# AGENTS.md

## Project Overview
Zaza is a Python 3-only functional test framework for OpenStack Charms,
developed by Canonical's OpenStack Charmers. It automates the full lifecycle of
deploying and testing Juju charms.

## Tech Stack
- **Language:** Python 3.10+
- **Automation:** tox
- **Testing:** `tox -e py3`
- **Linting:** `tox -e pep8`
- **Python interpreter** `.tox/py3/bin/python`

## Environment Rules
- **DO NOT** use `pip install` directly to modify the local environment.
- **ALWAYS** use `tox` to run tests and linters to ensure isolation.
- If new dependencies are needed, update `setup.py` and `requirements.txt`, then
  run `tox` to update environments.

## Available Tox Commands
- **Run all tests:** `tox`
- **Run specific environment:** `tox -e py3`
- **Run linting:** `tox -e pep8`
- **Run linting for one or more files** `tox -e pep8 -- <FILES>`
- **Build docs:** `tox -e docs`
- **Recreate environments:** `tox --recreate`

## Downstream consumers

- **zaza-openstack-tests** https://github.com/openstack-charmers/zaza-openstack-tests/

## Project Structure
- `zaza/`: Source code
- `unit_tests/`: Unit Test suite
- `tox.ini`: Tox configuration
- `requirements.txt`: Dependencies
- `setup.py`: Package definition

## Testing
- Run all tests: `tox -e py3`
- All new features must include unit tests in the `unit_tests/` directory.
- Use `tox -e func-target -- $bundle_name` to run integration tests, where
  `$bundle_name` can be one of the bundle files available in `tests/bundles/`
  directory (without the `.yaml` extension).

## Boundaries
- DO NOT commit `.env` files or secrets.