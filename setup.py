from setuptools import setup, find_packages
from os import path, listdir
from functools import partial
from itertools import imap, ifilter
from ast import parse
from distutils.sysconfig import get_python_lib

if __name__ == '__main__':
    package_name = 'offswitch'

    with open(path.join(package_name, '__init__.py')) as f:
        __author__, __version__ = imap(
            lambda buf: next(imap(lambda e: e.value.s, parse(buf).body)),
            ifilter(lambda line: line.startswith('__version__') or line.startswith('__author__'), f)
        )

    to_funcs = lambda *paths: (partial(path.join, path.dirname(__file__), package_name, *paths),
                               partial(path.join, get_python_lib(prefix=''), package_name, *paths))

    _data_join, _data_install_dir = to_funcs('_data')
    config_join, config_install_dir = to_funcs('config')

    setup(
        name=package_name,
        author=__author__,
        version=__version__,
        description='Configuration based deprovisioning tool with Apache Libcloud',
        classifiers=[
            'Development Status :: 7 - Inactive',
            'Intended Audience :: Developers',
            'Topic :: Software Development',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'License :: OSI Approved :: MIT License',
            'License :: OSI Approved :: Apache Software License',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 2 :: Only'
        ],
        test_suite=package_name + '.tests',
        packages=find_packages(),
        package_dir={package_name: package_name},
        install_requires=['apache-libcloud', 'python-etcd'],
        data_files=[
            (config_install_dir(), map(config_join, listdir(config_join()))),
            (_data_install_dir(), map(_data_join, listdir(_data_join())))
        ]
    )
