from setuptools import setup, find_packages

setup(
    name="flashdb",
    version="1.0.0",
    author="Flash Team",
    description="A unified, trigger-aware database interface for MySQL, PostgreSQL, and MongoDB.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[],
    extras_require={
        "mysql": ["mysql-connector-python>=8.0"],
        "postgres": ["psycopg2-binary>=2.9"],
        "mongodb": ["pymongo>=4.0"],
        "all": [
            "mysql-connector-python>=8.0",
            "psycopg2-binary>=2.9",
            "pymongo>=4.0",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Database",
        "Intended Audience :: Developers",
    ],
    keywords="database mysql postgresql mongodb orm crud flash unified",
)