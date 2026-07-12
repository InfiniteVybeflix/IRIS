from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="iris-v9",
    version="9.0.0",
    author="Infinite Vybeflix",
    author_email="aevibron@gmail.com",
    description="IRIS v9 — Infinite Reactive Intelligence System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/luckyfelistine-bot/IRIS",
    packages=find_packages(exclude=["tests", "tests.*", "scripts", "scripts.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={"console_scripts": ["iris=app:main"]},
    include_package_data=True,
    zip_safe=False,
)
