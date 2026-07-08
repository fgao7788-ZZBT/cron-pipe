from setuptools import setup, find_packages

setup(
    name="cron-pipe",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "cron-pipe=cron_pipe.__main__:main",
        ],
    },
    python_requires=">=3.8",
    description="Turn dumb cron jobs into state-aware, conditional pipelines",
    long_description=open("README.md").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    license="MIT",
    url="https://github.com/eligao/cron-pipe",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: System :: Monitoring",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
