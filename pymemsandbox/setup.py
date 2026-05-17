from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='pymemsandbox',
    version='1.0.0',
    author='1234567740',
    author_email='3901306490@qq.com',
    description='Pure Python C-Level Memory Sandbox & JIT Execution Engine',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/YourName/pymemsandbox',
    py_modules=['pymemsandbox'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries",
        "Topic :: System :: Hardware",
    ],
    python_requires='>=3.6',
)