#!/usr/bin/env python

"""
Extract messages which share extreme tokens with message(s) on cmd line

usage %(prog)s [ -h ] -d mapfile [ -f feature [ -S file ] [ -H file ] file ...

If no features are given on the command line, one or more files containing
messages with X-Spambayes-Evidence headers must be present.

-d mapfile - specify file which holds feature mapping information

-S file - output spam message file

-H file - output spam message file

-f feature - specify feature to locate (may be given more than once)

-h - print this documentation and exit
"""

import sys
import getopt
import re
import cPickle as pickle

from spambayes.mboxutils import getmbox
from spambayes.tokenizer import tokenize

prog = sys.argv[0]

def usage(msg=None):
    if msg is not None:
        print >> sys.stderr, msg
    print >> sys.stderr, __doc__.strip() % globals()

def extractmessages(mapdb, hamfile, spamfile, features):
    """tokenize messages in f and extract messages with tokens to match"""
    i = 0
    hamids = {}
    spamids = {}

    for feature in features:
        ham, spam = mapdb.get(feature, ([], []))
        if hamfile is not None:
            for mbox in ham:
                msgids = hamids.get(mbox, set())
                msgids.update(ham.get(mbox, set()))
                hamids[mbox] = msgids
        if spamfile is not None:
            for mbox in spam:
                msgids = spamids.get(mbox, set())
                msgids.update(spam.get(mbox, set()))
                spamids[mbox] = msgids

    # now run through each mailbox in hamids and spamids and print
    # matching messages to relevant ham or spam files
    i = 0
    for mailfile in hamids:
        msgids = hamids[mailfile]
        for msg in getmbox(mailfile):
            if msg.get("message-id") in msgids:
                i += 1
                sys.stdout.write('\r%s: %5d' % (mailfile, i))
                sys.stdout.flush()
                print >> hamfile, msg
    print

    for mailfile in spamids:
        msgids = spamids[mailfile]
        for msg in getmbox(mailfile):
            if msg.get("message-id") in msgids:
                i += 1
                sys.stdout.write('\r%s: %5d' % (mailfile, i))
                sys.stdout.flush()
                print >> spamfile, msg
    print

def main(args):
    try:
        opts, args = getopt.getopt(args, "hd:S:H:f:",
                                   ["help", "database=", "spamfile=",
                                    "hamfile=", "feature="])
    except getopt.GetoptError, msg:
        usage(msg)
        return 1

    mapfile = spamfile = hamfile = None
    features = []
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            return 0
        elif opt in ("-d", "--database"):
            mapfile = arg
        elif opt in ("-H", "--hamfile"):
            hamfile = arg
        elif opt in ("-S", "--spamfile"):
            spamfile = arg
        elif opt in ("-f", "--feature"):
            features.append(arg)

    if hamfile is None and spamfile is None:
        usage("At least one of -S or -H are required")
        return 1

    if mapfile is None:
        usage("'-d mapfile' is required")
        return 1

    try:
        mapd = pickle.load(file(mapfile))
    except IOError:
        usage("Mapfile %s does not exist" % mapfile)
        return 1

    if not features and not args:
        usage("Require at least one feature (-f) arg or one message file")
        return 1

    if not features:
        # extract significant tokens from each message and identify
        # where they came from
        for f in args:
            for msg in getmbox(f):
                evidence = msg.get("X-Spambayes-Evidence", "")
                evidence = re.sub(r"\s+", " ", evidence)
                features = [e.rsplit(": ", 1)[0]
                              for e in evidence.split("; ")[2:]]
                features = [eval(f) for f in features]
        if not features:
            usage("No X-Spambayes-Evidence headers found")
            return 1

    if spamfile is not None:
        spamfile = file(spamfile, "w")
    if hamfile is not None:
        hamfile = file(hamfile, "w")

    extractmessages(mapd, hamfile, spamfile, features)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))