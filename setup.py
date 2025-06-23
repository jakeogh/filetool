# -*- coding: utf-8 -*-

import fastentrypoints  # leave if still in use
from setuptools import find_packages, setup
from pathlib import Path

this_dir = Path(__file__).resolve().parent
readme_path = this_dir / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

setup(
    name="filetool",
    version="0.1",
    description="Common file operations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jakeogh/filetool",
    author="Justin Keogh",
    author_email="github.com@v6y.net",
    license="ISC",
    packages=find_packages(exclude=["tests"]),
    package_data={"filetool": ["py.typed"]},
    include_package_data=True,
    zip_safe=False,
    platforms="any",
    python_requires=">=3.8",
    install_requires=[
        "click",
    ],
    entry_points={
        "console_scripts": [
            "filetool=filetool.cli:cli",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: ISC License (ISCL)",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Development Status :: 4 - Beta",
    ],
)

