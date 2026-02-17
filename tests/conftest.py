import pytest
from pathlib import Path
from lode.reader import Reader

@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def reader():
    return Reader()

@pytest.fixture
def tmp_path(tmp_path):
    """Pytest fornisce già tmp_path, ma lo rendiamo esplicito"""
    return tmp_path