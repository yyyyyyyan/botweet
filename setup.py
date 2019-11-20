from setuptools import setup

with open('README.rst') as file:
    long_description = file.read()

setup(
    name = 'botweet',
    version = '0.1.0',
    author = 'yyyyyyyan',
    author_email = 'yanorestes@hotmail.com',
    packages = ['botweet'],
    description = 'A package that simplifies the creation of Twitter bots with Python',
    long_description = long_description,
    url = 'https://github.com/yyyyyyyyyyan/botweet',
    download_url = 'https://github.com/yyyyyyyyyyan/botweet/archive/0.1.0.zip',
    project_urls = {
        'Source code': 'https://github.com/yyyyyyyyyyan/botweet',
        'Download': 'https://github.com/yyyyyyyyyyan/botweet/archive/0.1.0.zip',
    },
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Topic :: Communications',
        'Topic :: Utilities',
    ]
)