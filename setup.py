#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

if __name__ == "__main__":
    setup(
        name = "pysnole",
        version = "0.1",
        description="Terminal emulator widget backed by pyte",
        author="Ilya Petrov",
        author_email="henning.schroeder@gmail.com",
        url="https://github.com/muromec/pysnole",
        zip_safe=True,
        license="GPL2",
        keywords="pyqt pyqt4 console terminal shell vt100 widget",
        depends = ["pysnole"],
        packages = find_packages(),
    )
