import os
from setuptools import setup

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "ritremixerator",
    version = "0.3",
    author = "Eitan Romanoff",
    author_email = "ear7631@rit.edu",
    description = ("A fork of the Dorrie project to create Spins and Remixes of Fedora."),
    license = "AGPL3",
    install_requires = [
        'pytz',
        'django',
        'pykickstart'],
    dependency_links = [
        'http://git.fedorahosted.org/git/?p=pykickstart.git;a=snapshot;h=HEAD;sf=tgz'
    ],
    include_package_data = True,
    keywords = "fedora kickstart python dorrie django redhat",
    url = "https://github.com/ear7631/RITRemixerator",
    packages=['dorrie', 'tests'],
    long_description=read('README'),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: AGPL",
    ],
)
