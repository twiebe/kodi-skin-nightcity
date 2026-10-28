import pathlib
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKIP_DIRS = {'.git', '.superpowers', '.venv', '.pytest_cache', '__pycache__'}
NON_WINDOW_FILES = {'Font.xml', 'Variables.xml'}

sys.path.insert(0, str(ROOT / 'tools'))


def parse(path):
    return ET.parse(path).getroot()


def all_xml_files():
    return [p for p in ROOT.rglob('*.xml') if not SKIP_DIRS & set(p.relative_to(ROOT).parts)]


def layout_files():
    return sorted((ROOT / '1080i').glob('*.xml'))


def window_files():
    return [p for p in layout_files()
            if not p.name.startswith('Includes') and p.name not in NON_WINDOW_FILES]


@pytest.fixture
def skin_root():
    return ROOT
