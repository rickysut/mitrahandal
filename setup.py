from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="mitrahandal",
    version="0.0.1",
    packages=find_packages(),
    install_requires=install_requires,
)