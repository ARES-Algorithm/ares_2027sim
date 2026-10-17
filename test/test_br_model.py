"""Check the CAD-to-simulation boundary and runnable model conversion."""

import importlib.util
from pathlib import Path
import shutil
import subprocess
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'ares_br_urdf' / 'br.urdf'
spec = importlib.util.spec_from_file_location('prepare_br', ROOT / 'scripts' / 'prepare_br.py')
prepare_br = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare_br)


def test_source_has_one_connected_acyclic_tree():
    robot = ET.parse(SOURCE).getroot()
    links = {link.attrib['name'] for link in robot.findall('link')}
    children = [joint.find('child').attrib['link'] for joint in robot.findall('joint')]
    assert len(children) == len(set(children))
    assert links - set(children) == {'base'}
    reached = {'base'}
    while True:
        following = reached | {
            joint.find('child').attrib['link'] for joint in robot.findall('joint')
            if joint.find('parent').attrib['link'] in reached
        }
        if following == reached:
            break
        reached = following
    assert reached == links
    assert len(children) == len(links) - 1


def test_simulation_resources_and_wheel_geometry_preserve_source():
    original = SOURCE.read_bytes()
    robot = ET.fromstring(prepare_br.prepare_robot(SOURCE))
    assert SOURCE.read_bytes() == original
    for mesh in robot.findall('link/visual/geometry/mesh'):
        uri = urlparse(mesh.attrib['filename'])
        assert uri.scheme == 'file'
        assert Path(unquote(uri.path)).is_file()
    assert not robot.findall('link/collision/geometry/mesh')
    for index in range(9, 13):
        joint = robot.find(f"joint[@name='joint{index}']")
        assert joint.attrib['type'] == 'continuous'
        assert 'upper' not in joint.find('limit').attrib
        cylinder = robot.find(f"link[@name='link{index}']/collision/geometry/cylinder")
        # CAD tessellation varies slightly between otherwise identical wheels.
        assert float(cylinder.attrib['radius']) == pytest.approx(0.0325, abs=1e-4)


@pytest.mark.skipif(not shutil.which('ign'), reason='Gazebo Fortress is not installed')
def test_gazebo_conversion_keeps_all_moving_joints_and_controllers(tmp_path):
    urdf = tmp_path / 'br.urdf'
    urdf.write_text(prepare_br.prepare_robot(SOURCE))
    result = subprocess.run(['ign', 'sdf', '-p', str(urdf)], capture_output=True,
                            text=True, check=True, timeout=20)
    model = ET.fromstring(result.stdout).find('model')
    assert {joint.attrib['name'] for joint in model.findall('joint')} == {
        f'joint{index}' for index in range(1, 33)
    }
    assert len(model.findall('plugin')) == 33
    assert not model.findall('link/collision/geometry/mesh')
