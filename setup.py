import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

short_desc = "Python library package with a collection of utility modules, from simple general"
short_desc += " utility functions to more complex IMGUI (imgui-bundle) utility classes."

setuptools.setup(
    name='libasvat',
    version='1.0',
    py_modules=["libasvat"],
    entry_points={},
    author="Fernando Omar Aluani",
    author_email="rewasvat@gmail.com",
    description=short_desc,
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Rewasvat/libasvat",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
        "Development Status :: 5 - Production/Stable",
    ],
    install_requires=["Click>=8.1.0", "Colorama", "keyring", "imgui-bundle", "debugpy"]
)
