from distutils.core import setup

setup(
    name='RaceResults',
    version='0.3.3',
    author='John Evans',
    author_email='john.g.evans.ne@gmail.com',
    url='http://pypi.python.org/pypi/RaceResults',
    packages=['rr', 'rr.test'],
    package_data={'rr': ['test/testdata/*.HTM',
        'test/testdata/*.shtml',
        'test/testdata/*.htm']},
    scripts=['bin/brrr', 'bin/crrr', 'bin/csrr', 'bin/nyrr', 'bin/lmsports'],
    license='LICENSE.txt',
    description='Race results parsing',
    install_requires=['lxml>=2.3.4'],
    classifiers=["Programming Language :: Python",
                 "Programming Language :: Python :: 3.3",
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
