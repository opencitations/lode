# Lode

[![Run tests](https://github.com/opencitations/lode/actions/workflows/tests.yml/badge.svg)](https://github.com/opencitations/lode/actions/workflows/tests.yml)
[![Coverage](https://opencitations.github.io/lode/coverage/coverage-badge.svg)](https://opencitations.github.io/lode/coverage/)
[![License: ISC](https://img.shields.io/badge/License-ISC-blue.svg)](https://opensource.org/licenses/ISC)

New reengineered version of LODE, maintained by OpenCitations.

## Installation

```bash
pip install lode
```

## Usage

```python
from lode import example_function

result = example_function()
print(result)
```

## Documentation

Full documentation is available at: https://username.github.io/lode/

## Development

This project uses [UV](https://docs.astral.sh/uv/) for dependency management.

### Setup

```bash
# Clone the repository
git clone https://github.com/username/lode.git
cd lode

# Install dependencies
uv sync --all-extras --dev
```

### Running tests

```bash
uv run pytest tests/
```

### Building documentation locally

```bash
cd docs
npm install
npm run dev
```

## License

This project is licensed under the ISC License - see the [LICENSE.md](LICENSE.md) file for details.
