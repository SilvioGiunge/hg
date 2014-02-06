#!/usr/bin/env python
#
# Copyright (c) 2013, Neriberto C.Prado
#
# This file is part of HG - https://github.com/neriberto/hg
# See the file 'docs/LICENSE' for copying permission.

# -*- coding: utf-8 -*-

import ConfigParser
import datetime
import fnmatch
import hashlib
import json
import os.path
import requests
import sys

def getConfig():
    '''
    Read config file and return VxCage URL
    '''
    fconf = "conf/hg.conf"
    if os.path.exists(fconf):
        cfg = ConfigParser.ConfigParser()
        cfg.read(fconf)
        VX = {}
        VX["Enabled"]= cfg.get('vxcage', 'enabled')
        VX["connection"] = cfg.get('vxcage', 'connection');

        Cuckoo = {}
        Cuckoo["Enabled"]= cfg.get('cuckoo', 'enabled')
        Cuckoo["connection"] = cfg.get('cuckoo', 'connection');

        Mongo = {}
        Mongo["Enabled"]= cfg.get('mongodb', 'enabled')
        Mongo["host"] = cfg.get('mongodb', 'host');
        Mongo["port"] = cfg.get('mongodb', 'port');

        Config = {}
        Config["VxCage"] = VX
	Config["Cuckoo"] = Cuckoo
	Config["Mongo"] = Mongo

        return Config
    else:
        sys.stderr.write("Cannot found config file %s\n" % fconf)
        return None

def getModules():
    '''
    Loads all modules of Malware Repository
    '''
    Modules = []
    for arg, dirname, names in os.walk('modules'):
        for name in fnmatch.filter(names, "*.py"):
            if name != "__init__.py":
                name = "modules.%s" % name.split(".py")[0]
                module = __import__(name, globals(), locals(), [''])
                components = name.split('.')
                for comp in components[1:]:
                    class_ = getattr(module, comp)
                    Modules.append(class_())
    return Modules

def getSample(URL):
    '''
    Download file from a URL
    '''
    try:
        re = requests.get(URL, allow_redirects=True, timeout=100)
        if re.status_code == 200:
            if re.headers['Content-Disposition'] == None:
                filename = URL.split('/')[-1].split('#')[0].split('?')[0]
                if filename == None:
                    filename = URL.split('/')
            else:
                Disposition = re.headers['Content-Disposition']
                try:
                    filename = Disposition.split('=')[1].split('"')[1]
                except Exception:
                    filename = Disposition.split('=')[1].split('"')[0]
            return dict({"filename":filename,
                         "content": re.content,
                         "status_code": re.status_code})
        else:
            return dict({"filename": None,
                         "content": None,
                         "status_code": re.status_code})
    except Exception:
        return dict({"filename": None,
                     "content": None,
                     "status_code": "0"}) # 0 for timeout

def addVxCage(URL, fullpath):
    '''
    Send the sample in fullpath to VxCage
    '''
    # TODO: Execute file scanners to verify is the Zip File is a JAR or APK
    # and sends the real file type as a TAG to VxCage
    Uploaded = False
    Count = 0
    # TODO: Check first if the file is not empty
    if (os.path.getsize(fullpath) > 0):
        Files = {'file': (os.path.basename(fullpath), open(fullpath, 'rb'))}
        # Try 3 times if receive upload error
        while (not Uploaded) or (Count == 3):
            r = requests.post("%smalware/add" % URL, files=Files)
            # Returns 200 upload sucessfull, so remove
            if r.status_code == 200:
                #os.remove(fullpath)
                Uploaded = True
            else:
                Count += 1
        if Count == 3:
            print "Failure in send to VxCage in %s" % URL
            sys.exit(-1)

def findVxCage(MD5, URL):
    Data = {'md5': MD5}
    try :
        r = requests.post("%smalware/find" % URL, data=Data)
        return r.status_code
    except:
        return -1

def saveFile(data):
    fullpath = os.path.join('/tmp/', data['filename'])
    fp = open(fullpath, "wb")
    fp.write(data['content'])
    fp.close()
    return fullpath

def getURLS(URL, URLS):
    '''
    Works on a list of URLs
    '''
    print "URLs Encontradas: %s" % len(URLS)

    count = 0
    for url in URLS:
        count += 1
        data = getSample(url)
        print "%04d - [%s] - Status Code:%s\t%s" %  (
            count,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data['status_code'],
            url[0:50])
        try:
            data = getSample(url)
            if data['content'] != None:
                fullpath = saveFile(data)
                md5 = hashlib.md5(data['content']).hexdigest()
                # Returns 404 file don't exist in VxCage
                if findVxCage(md5, URL) == 404:
                    # Send to VxCage Server
                    addVxCage(URL, fullpath)
                os.remove(fullpath)
            # clean memory
            data = None
        except Exception:
            # Failure to download, go to next 
            pass

def main():
    '''
    Main Procedure
    '''
    URLS = []
    REPORT = []
    Config = getConfig()
    mods = getModules()
    for mod in mods:
        lista = mod.run()
        if lista != None:
            URLS += lista
        REPORT.append({"Source":mod.Name,"URL":mod.URL,"URLS":lista})

    print Config["VxCage"]

    if Config["VxCage"]["Enabled"]== "yes":
        getURLS(Config["VxCage"]["connection"], URLS)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit()
    except SystemExit:
        pass
