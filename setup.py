# coding=utf-8
"""Python Foscam setup script."""
from setuptools import setup, find_packages


def readme():
    with open('README.md', encoding='utf-8') as desc:
        return desc.read()


setup(
    name='pyfoscam',
    version='0.1.0-alpha.3',
    packages=find_packages(exclude=['tests', 'tests.*']),
    package_data={'foscam': ['py.typed']},
    python_requires='>=3.10',
    install_requires=[
        'aiohttp>=3.9.0',
        'ftpretty>=0.4.0',
        'click>=8.0.0',
        'platformdirs>=3.0.0',
    ],
    extras_require={
        'test': ['pytest>=7.0', 'pytest-asyncio>=0.20', 'aioresponses>=0.7.0'],
    },
    author='Steve Herrell',
    author_email='steve.herrell@gmail.com',
    description='A library and CLI for Foscam IP cameras and media recording management.',
    long_description=readme(),
    long_description_content_type='text/markdown',
    license='LGPLv3+',
    keywords=['foscam', 'camera', 'ipcam', 'home automation'],
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
    ],
    entry_points={
        'console_scripts': [
            'pyfoscam = foscam.cli.main:main',
            'foscam = foscam.cli.main:main',
        ],
    },
    test_suite='tests',
)
