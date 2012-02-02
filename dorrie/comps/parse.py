# Dorrie - Web interface for building Fedora Spins/Remixes. 
# Copyright (C) 2009 Red Hat Inc.
# Author: Shreyank Gupta <sgupta@redhat.com>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os, pytz, urllib
import json

from subprocess import Popen

#FIXME: Import only what's needed or just 'from pykickstart import parser'
from pykickstart.parser import *
from pykickstart import constants
from pykickstart.version import makeVersion

from django.conf import settings

from comps import Comps
from helper import get_spin
from hardwareLists import langDict
#import rhpl.keyboard as keyboard


def get_comps():
    """
    parse and return comps object
    """
    # Eitan self-note:
    # Grabs the xml file from comps repository. Check settings for location.
    fd = urllib.urlopen(settings.COMPS_URL)
    c = Comps()
    c.add(fd)
    return c
    

def walk_ks_dir(directory):
    """
    Walks the defined KS_DIRS looking for only .ks files.
    """
 
    kickstart_files = []
   
    # Get the current directory, its internal directories, and files
    for (path, dirs, files) in os.walk(directory): 
        for file_name in filter(lambda x:(x.split('.')[-1] == "ks"), files):
            kickstart_files.append((os.path.abspath(os.path.join(path, file_name)), 
                                    file_name))

    return kickstart_files

def ls_ks():
    """
    List files in settings.KS_DIRS
    """
    # If the KS_DIRS is not a list, vomit
    if not isinstance(settings.KS_DIRS, list):
        raise ValueError, """Please set KS_DIRS in settings.py as a list
 of directories containing your kickstart files."""

    ks_files = []
    choicelist = []

    for ks_dir in settings.KS_DIRS:
        ks_files.extend(walk_ks_dir(ks_dir))

    for file_path, file_name in ks_files:
        #if kst.find('_') == -1:
        ks_tuple = (file_path, file_name.split('.')[0])
        choicelist.append(ks_tuple)
    return tuple(choicelist)

def languages():
    """
    Return list of languages
    """
    choicelist = []
    for text, code in langDict.iteritems():
        choicelist.append((code, text))
    return tuple(choicelist)
    

def timezones():
    """
    Return list of timezones
    """
    choicelist = []
    for each in pytz.common_timezones:
        choicelist.append((each, each))
    return tuple(choicelist)


def kickstart(ks, uploaded, path=settings.KS_DIR):
    """
    return parsed pykickstart object
    """
    if not uploaded:
        ks = "%s%s" % (path, ks)
    ksparser = DecoratedKickstartParser(makeVersion())
    ksparser.readKickstart(ks)
    
    # add the RIT stuff
    ritPostContents = get_rit_post()
    ksparser.addScript(ritPostContents, constants.KS_SCRIPT_POST)
    return ksparser


def get_lang_tz(ks):
    """
    return default language and timezole from base kickstart
    """
    ksparser = kickstart(ks)
    dict = {}
    dict['select_language'] = ksparser.handler.lang.lang.split('.')[0]
    dict['select_timezone'] = ksparser.handler.timezone.timezone
    return dict


def default_selected(ks, uploaded):
    """
    Return default groups from baseks
    """
    ksparser = kickstart(ks, uploaded)
    groups = [group.name for group in ksparser.handler.packages.groupList]
    plus = ksparser.handler.packages.packageList
    minus = ksparser.handler.packages.excludedList
    return groups, plus, minus


def package_listing(c):
    """
    Return a nicely parsed package-group listing 
    """
    result = {}
    for group, object in c._groups.iteritems():
        mandatory = object.mandatory_packages.keys()
        default = object.default_packages.keys()
        optional = object.optional_packages.keys()
        result[group] = [mandatory, default, optional]
    return result


def kpgrp_list(object):
    """
    return ksparser.group list from db object
    """
    list = []
    for each in object.all():
        list.append(Group(name=each.name))
    return list


def make_repo(object, name='', baseurl=''):
    """
    Build and return repo object
    """
    object.name = name
    object.baseurl = baseurl
    return object


def build_ks(id):
    """
    Build Modified KS file
    """
    spin = get_spin(id)
    folder = "%s%s_%s/" % (settings.CACHE, spin.id, spin.name)
    
    link = "%s/cache" % settings.MEDIA_ROOT
   
    #build paths
    if not os.path.exists(folder):
        os.makedirs(folder)

    if not os.path.exists(link):
        os.symlink(settings.CACHE, link)

    # get back a pykickstart object of a parsed spin.baseks kickstart file
    ksparser = kickstart(spin.baseks, spin.uploaded)
   
    #change lang, tz
    ksparser.handler.lang.lang = spin.language
    ksparser.handler.timezone.timezone = spin.timezone

    #Packages and Groups
    
    #Analyze which packages and groups were selected or deselected.
    gplus = kpgrp_list(spin.gplus)
    gminus = kpgrp_list(spin.gminus)
    pplus = [p.name for p in spin.pplus.all()]
    pminus = [p.name for p in spin.pminus.all()]

    # Remove each group and package in the minus category 
    for each in gminus:
        try:
            ksparser.handler.packages.groupList.remove(each)
        except:
            pass
    for each in gplus:
        ksparser.handler.packages.groupList.append(each)

    ksparser.handler.packages.packageList.extend(pplus)
    ksparser.handler.packages.excludedList.extend(pminus)

    
    if settings.REPO:
        #Change mirrorlist repo to the local one
        repolist = ksparser.handler.repo.repoList
        released = os.path.join(settings.REPO, 'fedora/Packages/')
        updates = os.path.join(settings.REPO, 'updates/')
        for repo in repolist:
            if repo.name == 'released':
                repo.baseurl = 'file://%s' % released
            elif repo.name == 'updates':
                repo.baseurl = 'file://%s' % updates

    #write new ks file
    filename = "%s%s.ks" % (folder, spin.name)
    fd = open(filename, 'w')
    lines = ksparser.handler.__str__().splitlines(True)
    for line in lines:
        if line.startswith('%include'): #include baseks hack
            continue
        if line.startswith('part / ') and \
            lines[lines.index(line)+1].startswith('part / '): #partition hack
                continue
        fd.write(line)
    fd.close()

    linkname = "/static/cache/%s_%s/%s.ks" % \
        (spin.id, spin.name, spin.name)

    #if the cache link is broken unlink and create a new symlink :-P
    if not os.path.exists(linkname):
        os.unlink(link)
        os.symlink(settings.CACHE, link)
    
    return linkname


def livecd_command(spin):
    """
    Build livecd-creator command
    """
    if settings.TESTING:
        return 'while read ln; do echo $ln; sleep .05; done < ../test-data/test.log'
    ks_path = "%s%s_%s/%s.ks" % (settings.CACHE, spin.id, spin.name, spin.name)
    fs_label = spin.name
    folder = "%s%s_%s" % (settings.CACHE, spin.id, spin.name)
    cache_path = os.path.join(settings.CACHE, 'cache/')
    tmp_path = os.path.join(settings.CACHE, 'tmp/')
    if not os.path.exists(tmp_path):
        os.makedirs(tmp_path)    
    cmd = "cd %s;livecd-creator -c %s --cache='%s' -t '%s' -f %s" \
        % (folder, ks_path, cache_path, tmp_path, fs_label)
    return cmd


def livecd_create(id):
    """
    Build livecd + give progress
    """
    spin = get_spin(id)
    cmd = livecd_command(spin)
    fd = get_log(spin, 'w')
    process = Popen(cmd, shell=True, stdout=fd, stderr=fd)
    spin.pid = process.pid
    spin.save()
    return process.pid


def get_log(spin, mode):
    """
    Returns FD of logfile, of given mode
    """
    log_file = "%s%s_%s/%s.log" % \
        (settings.CACHE, spin.id, spin.name, spin.name)
    return open(log_file, mode)

 
def get_tail(id):
    """
    return tail or log file
    """
    dump = {
        'link' : None,
        'string' : None,
        'percent' : None
    }
    spin = get_spin(id)
    spin_path = "%s%s_%s/%s.iso" % (settings.CACHE, spin.id, spin.name, 
        spin.name)
    if os.path.exists(spin_path):
        linkname = "/static/cache/%s_%s/%s.iso" % \
            (spin.id, spin.name, spin.name)
        dump['link'] = "<a href='%s'>Download Spin</a>" % linkname
    else:
        dump['string'], dump['percent'] = analyze_log(spin)
    if dump['percent'] is 100 and settings.TESTING:
        dump['link'] = "<a href='#'>Download Spin</a>"
    return json.dumps(dump)


def analyze_log(spin):
    """
    Returns string and percent completed from log
    """
    fd = get_log(spin, 'r')
    for line in reversed(fd.readlines()):
        if line.find('Setting supported flag to') is not -1:
            return 'Building image complete', 100
        elif line.find('done, estimate finish') is not -1:
            try:
                estimate = int(float(line[:line.find('%')]))/10
            except:
                return None, None
            return 'Building ISO image', 90 + estimate
        elif line.find('Parallel mksquashfs') is not -1:
            return 'Create Squash filesystem', 80 
        elif (line.find('e2fsck') is not -1 or line.find('resize2fs') is not
            -1 or line.find('e2image') is not -1):
                return 'Check and resize filesystem', 70
        elif line.find('password') is not -1:
            return 'Changing root password', 65
        elif line.find('Installing:') is not -1:
            try:
                estimate = int(float(line[line.find('[') + 1: line.find('/')]) / 
                    float(line[line.find('/') + 1: line.find(']')]) * 50)
            except:
                return None, None
            return 'Installing packages%s' % ('.'*(estimate/10)), 15 + estimate
        elif line.find('Retrieving') is not -1:
            return 'Retrieving repodata', 10
        elif line.find('mke2fs') is not -1:
            return 'Making new filesystem', 5
    return None, None

# Subclass the parser so we can add scripts easily to the kickstart
class DecoratedKickstartParser(KickstartParser):
    def addScript(self, script, scriptType):
        # Make a script object
        # add script object to self.handler.scripts
        scriptObj = Script(script, type=scriptType)
        self.handler.scripts.append(scriptObj)

# add the rit post script for the rit remix into the scripts list

def get_rit_post():
    cwd = os.getcwd()
    ritpostpath = cwd + "/ritpost.txt"
    rfile = open(ritpostpath)
    contents = rfile.read()
    rfile.close()
    return contents
