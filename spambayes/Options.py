# Options.options is a globally shared options object.

# XXX As this code is, option names must be unique across ini sections,
# XXX and must not conflict with OptionsClass method names.

import sys
import StringIO
import ConfigParser
from sets import Set

__all__ = ['options']

defaults = """
[Tokenizer]
# If false, tokenizer.Tokenizer.tokenize_body() strips HTML tags
# from pure text/html messages.  Set true to retain HTML tags in this
# case.  On the c.l.py corpus, it helps to set this true because any
# sign of HTML is so despised on tech lists; however, the advantage
# of setting it true eventually vanishes even there given enough
# training data.  If you set this true, you should almost certainly set
# ignore_redundant_html true too.
retain_pure_html_tags: False

# If true, when a multipart/alternative has both text/plain and text/html
# sections, the text/html section is ignored.  That's likely a dubious
# idea in general, so false is likely a better idea here.  In the c.l.py
# tests, it helped a lot when retain_pure_html_tags was true (in that case,
# keeping the HTML tags in the "redundant" HTML was almost certain to score
# the multipart/alternative as spam, regardless of content).
ignore_redundant_html: False

# Generate tokens just counting the number of instances of each kind of
# header line, in a case-sensitive way.
#
# Depending on data collection, some headers aren't safe to count.
# For example, if ham is collected from a mailing list but spam from your
# regular inbox traffic, the presence of a header like List-Info will be a
# very strong ham clue, but a bogus one.  In that case, set
# count_all_header_lines to False, and adjust safe_headers instead.

count_all_header_lines: False

# Like count_all_header_lines, but restricted to headers in this list.
# safe_headers is ignored when count_all_header_lines is true.

safe_headers: abuse-reports-to
    date
    errors-to
    from
    importance
    in-reply-to
    message-id
    mime-version
    organization
    received
    reply-to
    return-path
    subject
    to
    user-agent
    x-abuse-info
    x-complaints-to
    x-face

# A lot of clues can be gotten from IP addresses and names in Received:
# headers.  Again this can give spectacular results for bogus reasons
# if your test corpora are from different sources.  Else set this to true.
mine_received_headers: False

[MboxTest]
# If tokenize_header_words is true, then the header values are
# tokenized using the default text tokenize.  The words are tagged
# with "header:" where header is the name of the header.
tokenize_header_words: False
# If tokenize_header_default is True, use the base header tokenization
# logic described in the Tokenizer section.
tokenize_header_default: True

# skip_headers is a set of regular expressions describing headers that
# should not be tokenized if tokenize_header is True.
skip_headers: received
    date
    x-.*

[TestDriver]
# These control various displays in class TestDriver.Driver.

# Number of buckets in histograms.
nbuckets: 40
show_histograms: True

# Display spam when
#     show_spam_lo <= spamprob <= show_spam_hi
# and likewise for ham.  The defaults here don't show anything.
show_spam_lo: 1.0
show_spam_hi: 0.0
show_ham_lo: 1.0
show_ham_hi: 0.0

show_false_positives: True
show_false_negatives: False

# Near the end of Driver.test(), you can get a listing of the "best
# discriminators" in the words from the training sets.  These are the
# words whose WordInfo.killcount values are highest, meaning they most
# often were among the most extreme clues spamprob() found.  The number
# of best discriminators to show is given by show_best_discriminators;
# set this <= 0 to suppress showing any of the best discriminators.
show_best_discriminators: 30

# The maximum # of characters to display for a msg displayed due to the
# show_xyz options above.
show_charlimit: 3000

# If save_trained_pickles is true, Driver.train() saves a binary pickle
# of the classifier after training.  The file basename is given by
# pickle_basename, the extension is .pik, and increasing integers are
# appended to pickle_basename.  By default (if save_trained_pickles is
# true), the filenames are class1.pik, class2.pik, ...  If a file of that
# name already exists, it's overwritten.  pickle_basename is ignored when
# save_trained_pickles is false.

save_trained_pickles: False
pickle_basename: class

[Classifier]
# Fiddling these can have extreme effects.  See classifier.py for comments.
hambias: 2.0
spambias: 1.0

min_spamprob: 0.01
max_spamprob: 0.99
unknown_spamprob: 0.5

max_discriminators: 16

# Speculative change to allow giving probabilities more weight the more
# messages went into computing them.
adjust_probs_by_evidence_mass: False
"""

int_cracker = ('getint', None)
float_cracker = ('getfloat', None)
boolean_cracker = ('getboolean', bool)
string_cracker = ('get', None)

all_options = {
    'Tokenizer': {'retain_pure_html_tags': boolean_cracker,
                  'ignore_redundant_html': boolean_cracker,
                  'safe_headers': ('get', lambda s: Set(s.split())),
                  'count_all_header_lines': boolean_cracker,
                  'mine_received_headers': boolean_cracker,
                 },
    'TestDriver': {'nbuckets': int_cracker,
                   'show_ham_lo': float_cracker,
                   'show_ham_hi': float_cracker,
                   'show_spam_lo': float_cracker,
                   'show_spam_hi': float_cracker,
                   'show_false_positives': boolean_cracker,
                   'show_false_negatives': boolean_cracker,
                   'show_histograms': boolean_cracker,
                   'show_best_discriminators': int_cracker,
                   'save_trained_pickles': boolean_cracker,
                   'pickle_basename': string_cracker,
                   'show_charlimit': int_cracker,
                  },
    'Classifier': {'hambias': float_cracker,
                   'spambias': float_cracker,
                   'min_spamprob': float_cracker,
                   'max_spamprob': float_cracker,
                   'unknown_spamprob': float_cracker,
                   'max_discriminators': int_cracker,
                   'adjust_probs_by_evidence_mass': boolean_cracker,
                   },
    'MboxTest': {'tokenize_header_words': boolean_cracker,
                 'tokenize_header_default': boolean_cracker,
                 'skip_headers': ('get', lambda s: Set(s.split())),
                 },
}

def _warn(msg):
    print >> sys.stderr, msg

class OptionsClass(object):
    def __init__(self):
        self._config = ConfigParser.ConfigParser()

    def mergefiles(self, fnamelist):
        self._config.read(fnamelist)
        self._update()

    def mergefilelike(self, filelike):
        self._config.readfp(filelike)
        self._update()

    def _update(self):
        nerrors = 0
        c = self._config
        for section in c.sections():
            if section not in all_options:
                _warn("config file has unknown section %r" % section)
                nerrors += 1
                continue
            goodopts = all_options[section]
            for option in c.options(section):
                if option not in goodopts:
                    _warn("config file has unknown option %r in "
                         "section %r" % (option, section))
                    nerrors += 1
                    continue
                fetcher, converter = goodopts[option]
                value = getattr(c, fetcher)(section, option)
                if converter is not None:
                    value = converter(value)
                setattr(options, option, value)
        if nerrors:
            raise ValueError("errors while parsing .ini file")

    def display(self):
        output = StringIO.StringIO()
        self._config.write(output)
        return output.getvalue()


options = OptionsClass()

d = StringIO.StringIO(defaults)
options.mergefilelike(d)
del d

options.mergefiles(['bayescustomize.ini'])
