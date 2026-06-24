from setuptools import setup, find_packages

setup(
    name="webcrawl",
    version="0.1.0",
    description="Python SDK for the Webcrawl API — LLM-ready web scraping",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "httpx>=0.27.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
)
