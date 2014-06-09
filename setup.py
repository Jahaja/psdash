# coding=utf-8
from psdash import __version__
from setuptools import setup, find_packages

setup(
    name="psdash",
    version=__version__,
    description="Linux system information web dashboard",
    long_description="psdash is a system information web dashboard for linux using data mainly served by psutil",
    classifiers=[
        "Topic :: System :: Monitoring",
        "Topic :: System :: Logging",
        "Topic :: System :: Networking :: Monitoring",
        "Development Status :: 4 - Beta",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "License :: Public Domain",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators"
    ],
    keywords="linux web dashboard",
    author="Joakim Hamrén",
    author_email="joakim.hamren@gmail.com",
    url="https://github.com/Jahaja/psdash",
    license="CC0",
    packages=find_packages(exclude=["tests"]),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "Flask==0.10.1",
        "psutil==2.1.1",
        "argparse==1.2.1",
        "glob2==0.4.1"
    ],
    test_suite="tests",
    entry_points={
        "console_scripts": [
            "psdash = psdash.web:main"
        ]
    }
)