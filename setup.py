from setuptools import setup, find_packages

setup(
    name='RaceResults',
    version='0.3.7',
    author='John Evans',
    author_email='john.g.evans.ne@gmail.com',
    url='http://pypi.python.org/pypi/RaceResults',
    packages=find_packages(),
    package_data={'rr': ['test/testdata/*.HTM',
        'test/testdata/*.shtml',
        'test/testdata/*.htm']},
    entry_points={
        'console_scripts': [
            'brrr = rr.command_line:run_bestrace',
            'crrr = rr.command_line:run_coolrunning',
            'csrr = rr.command_line:run_compuscore',
            'nyrr = rr.command_line:run_nyrr',
                            ]},
    license='LICENSE.txt',
    description='Race results parsing',
    install_requires=['lxml>=2.3.4', 'requests>=2.2.0'],
    classifiers=["Programming Language :: Python",
                 "Programming Language :: Python :: 3.4",
                 "Programming Language :: Python :: Implementation :: CPython",
                 "License :: OSI Approved :: MIT License",
                 "Development Status :: 4 - Beta",
                 "Operating System :: MacOS",
                 "Operating System :: POSIX :: Linux",
                 "Intended Audience :: Developers",
                 "Topic :: Internet :: WWW/HTTP",
                 "Topic :: Text Processing :: Markup :: HTML",
                 ]
)
