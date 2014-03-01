# coding=utf-8

from setuptools import setup, find_packages

setup(
    name="psdash",
    version="0.1.0",
    description="Linux system information web dashboard",
    long_description="psdash is a system information web dashboard for linux using data mainly served by psutil",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Operating System :: Linux",
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
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "Flask==0.10.1",
        "psutil==1.2.1"
    ],
    entry_points={
        "console_scripts": [
            "psdash = psdash.web:main"
        ]
    }
)