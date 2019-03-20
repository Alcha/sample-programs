import os
import tempfile
import shutil

import pytest
import docker
import yaml

from docker import errors

from test.project import ProjectType

from test import testinfo


class Source:
    def __init__(self, name, path, test_info_string):
        self._name = name
        self._path = path

        self.test_info = testinfo.TestInfo.from_string(test_info_string, self)

    @property
    def full_path(self):
        return os.path.join(self._path, self._name)

    @property
    def path(self):
        return self._path

    @property
    def name(self):
        return os.path.splitext(self._name)[0]

    @property
    def extension(self):
        return os.path.splitext(self._name)[1]

    def run(self, client, params='', expect_error=False):
        tmp_dir = tempfile.mkdtemp()
        shutil.copy(self.full_path, tmp_dir)

        image = _get_image(
            client=client,
            container_info=self.test_info.container_info
        )
        volume_info = {tmp_dir: {'bind': '/src', 'mode': 'rw'}}
        result = _run_container(
            client=client,
            image=image,
            container_info=self.test_info.container_info,
            volume_info=volume_info,
            params=params,
            expect_error=expect_error
        )
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return result.decode('utf-8')


def _get_image(client, container_info):
        return client.images.pull(container_info.image, tag=str(container_info.tag))


def _run_container(client, image, container_info, volume_info, params, expect_error):
    container = client.containers.run(image=image,
                                      command=f'{container_info.cmd} {params}',
                                      working_dir='/src',
                                      remove=not expect_error,
                                      detach=expect_error,
                                      volumes=volume_info)
    if not expect_error:
        return container

    out = b''.join([line for line in container.logs(stdout=True, stderr=True, stream=True, follow=True)])
    container.remove()
    return out



def get_sources(path):
    sources = {k: [] for k in ProjectType}
    for root, dirs, files in os.walk(path):
        path = os.path.abspath(root)
        if "testinfo.yml" in files:
            with open(os.path.join(path, 'testinfo.yml'), 'r') as file:
                test_info_string = file.read()
            folder_info = testinfo.FolderInfo.from_dict(yaml.safe_load(test_info_string)['folder'])
            folder_project_names = folder_info.get_project_mappings(include_extension=True)
            for project_type, project_name in folder_project_names.items():
                if project_name in files:
                    source = Source(project_name, path, test_info_string)
                    sources[project_type].append(source)
    return sources


@pytest.fixture
def docker_client():
    return docker.from_env()
