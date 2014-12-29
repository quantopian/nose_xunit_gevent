"""
Xunit for the nose_gevented_multiprocess plugin

The xunit plugin works by keeping ongoing stats on the test run as it
progresses, with hooks that are run before/after each test to update
the stats.

Unfortunately, when those hooks are called in subprocesses, it doesn't
work.

There's a nose_xunitmp plugin which claims to fix this (I haven't
verified that it does one way or the other), but it doesn't work with
the nose_gevented_multiprocess plugin, because it relies on
multiprocessing.Manager, but nose_gevented_multiprocess uses popen,
not multiprocessing, so that's no good.

This plugin fixes that by using temporary directories to collect stats
and error reports among the multiple test processes, before finally
aggregating them all at the end.

I doubt my implementation is particularly "pythonic," and maybe I
could have come up with a better scheme than temporary directories for
interprocess communication, but this works well enough for us.
"""

import codecs
import cPickle as pickle
import os
import tempfile
import uuid

from nose.plugins.base import Plugin
from nose.plugins.xunit import Xunit
from nose.pyversion import force_unicode


envvar_name = '_nose_xunit_gevent_dirs'
stat_names = ('errors', 'failures', 'passes', 'skipped')


class OnDiskCounter(object):
    """Creates a temporary directory in which to store updates to the
    counter. Supports addition and value retrieval."""

    def __init__(self, directory=None):
        self.do_cleanup = not directory
        self.directory = directory or tempfile.mkdtemp()

    def __iadd__(self, y):
        if not isinstance(y, (int, OnDiskCounter)):
            raise TypeError

        fn = '{0}/{1}'.format(self.directory, uuid.uuid1())
        pickle.dump(int(y), open(fn, "w"))
        return self

    def __add__(self, y):
        if not isinstance(y, (int, OnDiskCounter)):
            raise TypeError

        return int(self) + int(y)

    def __radd__(self, y):
        if not isinstance(y, (int, OnDiskCounter)):
            raise TypeError

        return int(self) + int(y)

    def __int__(self):
        val = 0
        for f in sorted(os.listdir(self.directory)):
            val += pickle.load(open('{0}/{1}'.format(self.directory, f)))
        return val

    def __str__(self):
        return str(int(self))

    def __repr__(self):
        return str(int(self))

    def __del__(self):
        if not self.do_cleanup:
            return
        for f in os.listdir(self.directory):
            os.remove('{0}/{1}'.format(self.directory, f))
        os.rmdir(self.directory)


class OnDiskList(object):
    """Creates a temporary directory in which to store updates to the
    list. Supports append and retrieval."""

    def __init__(self, directory=None):
        self.do_cleanup = not directory
        self.directory = directory or tempfile.mkdtemp()

    def append(self, item):
        fn = '{0}/{1}'.format(self.directory, uuid.uuid1())
        pickle.dump(item, open(fn, "w"))

    def __iter__(self):
        for f in sorted(os.listdir(self.directory)):
            yield pickle.load(open('{0}/{1}'.format(self.directory, f)))

    def __str__(self):
        return str([i for i in self])

    def __repr__(self):
        return repr([i for i in self])

    def __del__(self):
        if not self.do_cleanup:
            return
        for f in os.listdir(self.directory):
            os.remove('{0}/{1}'.format(self.directory, f))
        os.rmdir(self.directory)


class XunitGevent(Xunit):
    """Test results in XUnit XML format when nose_gevented_multiprocess
is in use."""

    name = 'xunit-gevent'
    score = 2000
    error_report_filename = None
    error_report_file = None

    def options(self, parser, env):
        """Sets additional command line options."""
        Plugin.options(self, parser, env)
        parser.add_option(
            '--xunit-gevent-file', action='store',
            dest='xunit_gevent_file', metavar="FILE",
            default=env.get('NOSE_XUNIT_GEVENT_FILE', 'nosetests.xml'),
            help=("Path to xml file to store the xunit report in. "
                  "Default is nosetests.xml in the working directory "
                  "[NOSE_XUNIT_GEVENT_FILE]"))

    def configure(self, options, config):
        """Configures the xunit plugin."""
        Plugin.configure(self, options, config)
        self.config = config
        if self.enabled:
            try:
                dirs = os.environ[envvar_name].split(',')
            except KeyError:
                dirs = [None for name in range(len(stat_names) + 1)]
            self.stats = {name: OnDiskCounter(dirs.pop(0))
                          for name in stat_names}
            self.errorlist = OnDiskList(directory=dirs.pop(0))
            os.environ[envvar_name] = ','.join(
                [self.stats[s].directory for s in stat_names] +
                [self.errorlist.directory])
            self.error_report_filename = options.xunit_gevent_file

    def report(self, stream):
        """Writes an Xunit-formatted XML file

        The file includes a report of test errors and failures.

        """
        self.error_report_file = codecs.open(self.error_report_filename, 'w',
                                             self.encoding, 'replace')
        self.stats['encoding'] = self.encoding
        self.stats['total'] = (self.stats['errors'] + self.stats['failures']
                               + self.stats['passes'] + self.stats['skipped'])
        self.error_report_file.write(
            u'<?xml version="1.0" encoding="%(encoding)s"?>'
            u'<testsuite name="nosetests" tests="%(total)d" '
            u'errors="%(errors)d" failures="%(failures)d" '
            u'skip="%(skipped)d">' % self.stats)
        self.error_report_file.write(u''.join([
            force_unicode(error)
            for error
            in self.errorlist
        ]))

        self.error_report_file.write(u'</testsuite>')
        self.error_report_file.close()
        if self.config.verbosity > 1:
            stream.writeln("-" * 70)
            stream.writeln("XML: %s" % self.error_report_file.name)
        # So that temporary directories are cleaned up
        del self.stats
        del self.errorlist
