#  Copyright 2008-2015 Nokia Networks
#  Copyright 2016-     Robot Framework Foundation
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Module implementing result related model objects.

During test execution these objects are created internally by various runners.
At that time they can be inspected and modified by listeners__.

When results are parsed from XML output files after execution to be able to
create logs and reports, these objects are created by the
:func:`~.resultbuilder.ExecutionResult` factory method.
At that point they can be inspected and modified by `pre-Rebot modifiers`__.

The :func:`~.resultbuilder.ExecutionResult` factory method can also be used
by custom scripts and tools. In such usage it is often easiest to inspect and
modify these objects using the :mod:`visitor interface <robot.model.visitor>`.

If classes defined here are needed, for example, as type hints, they can
be imported via the :mod:`robot.running` module.

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#listener-interface
__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#programmatic-modification-of-results

"""

from collections import OrderedDict
from itertools import chain
import warnings

from robot import model
from robot.model import BodyItem, create_fixture, Keywords, Tags, TotalStatisticsBuilder
from robot.utils import get_elapsed_time, setter

from .configurer import SuiteConfigurer
from .messagefilter import MessageFilter
from .modeldeprecation import deprecated, DeprecatedAttributesMixin
from .keywordremover import KeywordRemover
from .suiteteardownfailed import SuiteTeardownFailed, SuiteTeardownFailureHandler


class Body(model.Body):
    __slots__ = []


class Branches(model.Branches):
    __slots__ = []


class Iterations(model.BaseBody):
    __slots__ = ['iteration_class']

    def __init__(self, iteration_class, parent=None, items=None):
        self.iteration_class = iteration_class
        super().__init__(parent, items)

    def create_iteration(self, *args, **kwargs):
        return self.append(self.iteration_class(*args, **kwargs))


@Body.register
@Branches.register
@Iterations.register
class Message(model.Message):
    __slots__ = []


class StatusMixin:
    __slots__ = []
    PASS = 'PASS'
    FAIL = 'FAIL'
    SKIP = 'SKIP'
    NOT_RUN = 'NOT RUN'
    NOT_SET = 'NOT SET'

    @property
    def elapsedtime(self):
        """Total execution time in milliseconds."""
        return get_elapsed_time(self.starttime, self.endtime)

    @property
    def passed(self):
        """``True`` when :attr:`status` is 'PASS', ``False`` otherwise."""
        return self.status == self.PASS

    @passed.setter
    def passed(self, passed):
        self.status = self.PASS if passed else self.FAIL

    @property
    def failed(self):
        """``True`` when :attr:`status` is 'FAIL', ``False`` otherwise."""
        return self.status == self.FAIL

    @failed.setter
    def failed(self, failed):
        self.status = self.FAIL if failed else self.PASS

    @property
    def skipped(self):
        """``True`` when :attr:`status` is 'SKIP', ``False`` otherwise.

        Setting to ``False`` value is ambiguous and raises an exception.
        """
        return self.status == self.SKIP

    @skipped.setter
    def skipped(self, skipped):
        if not skipped:
            raise ValueError("`skipped` value must be truthy, got '%s'." % skipped)
        self.status = self.SKIP

    @property
    def not_run(self):
        """``True`` when :attr:`status` is 'NOT RUN', ``False`` otherwise.

        Setting to ``False`` value is ambiguous and raises an exception.
        """
        return self.status == self.NOT_RUN

    @not_run.setter
    def not_run(self, not_run):
        if not not_run:
            raise ValueError("`not_run` value must be truthy, got '%s'." % not_run)
        self.status = self.NOT_RUN


class ForIteration(BodyItem, StatusMixin, DeprecatedAttributesMixin):
    """Represents one FOR loop iteration."""
    type = BodyItem.ITERATION
    body_class = Body
    repr_args = ('variables',)
    __slots__ = ['variables', 'status', 'starttime', 'endtime', 'doc']

    def __init__(self, variables=None, status='FAIL', starttime=None, endtime=None,
                 doc='', parent=None):
        self.variables = variables or OrderedDict()
        self.parent = parent
        self.status = status
        self.starttime = starttime
        self.endtime = endtime
        self.doc = doc
        self.body = None

    @setter
    def body(self, body):
        return self.body_class(self, body)

    def visit(self, visitor):
        visitor.visit_for_iteration(self)

    @property
    @deprecated
    def name(self):
        return ', '.join('%s = %s' % item for item in self.variables.items())


@Body.register
class For(model.For, StatusMixin, DeprecatedAttributesMixin):
    iterations_class = Iterations
    iteration_class = ForIteration
    __slots__ = ['status', 'starttime', 'endtime', 'doc']

    def __init__(self, variables=(),  flavor='IN', values=(), start=None, mode=None,
                 fill=None, status='FAIL', starttime=None, endtime=None, doc='',
                 parent=None):
        super().__init__(variables, flavor, values, start, mode, fill, parent)
        self.status = status
        self.starttime = starttime
        self.endtime = endtime
        self.doc = doc

    @setter
    def body(self, iterations):
        return self.iterations_class(self.iteration_class, self, iterations)

    @property
    @deprecated
    def name(self):
        variables = ' | '.join(self.variables)
        values = ' | '.join(self.values)
        for name, value in [('start', self.start),
                            ('mode', self.mode),
                            ('fill', self.fill)]:
            if value is not None:
                values += f' | {name}={value}'
        return f'{variables} {self.flavor} [ {values} ]'


class WhileIteration(BodyItem, StatusMixin, DeprecatedAttributesMixin):
    """Represents one WHILE loop iteration."""
    type = BodyItem.ITERATION
    body_class = Body
    __slots__ = ['status', 'starttime', 'endtime', 'doc']

    def __init__(self, status='FAIL', starttime=None, endtime=None,
                 doc='', parent=None):
        self.parent = parent
        self.status = status
        self.starttime = starttime
        self.endtime = endtime
        self.doc = doc
        self.body = None

    @setter
    def body(self, body):
        return self.body_class(self, body)

    def visit(self, visitor):
        visitor.visit_while_iteration(self)

    @property
    @deprecated
    def name(self):
        return ''


@Body.register
class While(model.While, StatusMixin, DeprecatedAttributesMixin):
    iterations_class = Iterations
    iteration_class = WhileIteration
    __slots__ = ['status', 'starttime', 'endtime', 'doc']

    def __init__(self, condition=None, limit=None, on_limit_message=None,
                 parent=None, status='FAIL', starttime=None,
                 endtime=None, doc=''):
        super().__init__(condition, limit, on_limit_message, parent)
        self.status = status
        self.starttime = starttime
        self.endtime = endtime
        self.doc = doc

    @setter
    def body(self, iterations):
        return self.iterations_class(self.iteration_class, self, iterations)

    @property
    @deprecated
    def name(self):
        parts = []
        if self.condition:
            parts.append(self.condition)
        if self.limit:
            parts.append(f'limit={self.limit}')
        if self.on_limit_message:
            parts.append(f'on_limit_message={self.on_limit_message}')
        return ' | '.join(parts)


class IfBranch(model.IfBranch, StatusMixin, DeprecatedAttributesMixin):
    body_class = Body
    __slots__ = ['status', 'starttime', 'endtime', 'doc']

    def __init__(self, type=BodyItem.IF, condition=None, status='FAIL',
                 starttime=None, endtime=None, doc='', parent=None):
        super().__init__(type, condition, parent)
        self.status = status
        self.starttime = starttime
        self.endtime = endtime
        self.doc = doc

    @property
    @deprecated
    def name(self):
        return self.condition


@Body.register
class If(model.If, StatusMixin, DeprecatedAttributesMixin):
    branch_class = IfBranch
    branches_class = Branches
    __slots__ = ['status', 'starttime', 'endtime', 'doc']

    def __init__(self, status='FAIL', starttime=None, endtime=None, doc='', parent=None):
        super().__init__(parent)
        self.status = status
        self.starttime = starttime
        self.endtime = endtime
        self.doc = doc


class TryBranch(model.TryBranch, StatusMixin, DeprecatedAttributesMixin):
    body_class = Body
    __slots__ = ['status', 'starttime', 'endtime', 'doc']

    def __init__(self, type=BodyItem.TRY, patterns=(), pattern_type=None, variable=None,
                 status='FAIL', starttime=None, endtime=None, doc='', parent=None):
        super().__init__(type, patterns, pattern_type, variable, parent)
        self.status = status
        self.starttime = starttime
        self.endtime = endtime
        self.doc = doc

    @property
    @deprecated
    def name(self):
        patterns = list(self.patterns)
        if self.pattern_type:
            patterns.append(f'type={self.pattern_type}')
        parts = []
        if patterns:
            parts.append(' | '.join(patterns))
        if self.variable:
            parts.append(f'AS {self.variable}')
        return ' '.join(parts)


@Body.register
class Try(model.Try, StatusMixin, DeprecatedAttributesMixin):
    branch_class = TryBranch
    branches_class = Branches
    __slots__ = ['status', 'starttime', 'endtime', 'doc']

    def __init__(self, status='FAIL', starttime=None, endtime=None, doc='', parent=None):
        super().__init__(parent)
        self.status = status
        self.starttime = starttime
        self.endtime = endtime
        self.doc = doc


@Body.register
class Return(model.Return, StatusMixin, DeprecatedAttributesMixin):
    __slots__ = ['status', 'starttime', 'endtime']
    body_class = Body

    def __init__(self, values=(), status='FAIL', starttime=None, endtime=None, parent=None):
        super().__init__(values, parent)
        self.status = status
        self.starttime = starttime
        self.endtime = endtime
        self.body = None

    @setter
    def body(self, body):
        """Child keywords and messages as a :class:`~.Body` object.

        Typically empty. Only contains something if running RETURN has failed
        due to a syntax error or listeners have logged messages or executed
        keywords.
        """
        return self.body_class(self, body)

    @property
    @deprecated
    def args(self):
        return self.values

    @property
    @deprecated
    def doc(self):
        return ''


@Body.register
class Continue(model.Continue, StatusMixin, DeprecatedAttributesMixin):
    __slots__ = ['status', 'starttime', 'endtime']
    body_class = Body

    def __init__(self, status='FAIL', starttime=None, endtime=None, parent=None):
        super().__init__(parent)
        self.status = status
        self.starttime = starttime
        self.endtime = endtime
        self.body = None

    @setter
    def body(self, body):
        """Child keywords and messages as a :class:`~.Body` object.

        Typically empty. Only contains something if running CONTINUE has failed
        due to a syntax error or listeners have logged messages or executed
        keywords.
        """
        return self.body_class(self, body)

    @property
    @deprecated
    def args(self):
        return ()

    @property
    @deprecated
    def doc(self):
        return ''


@Body.register
class Break(model.Break, StatusMixin, DeprecatedAttributesMixin):
    __slots__ = ['status', 'starttime', 'endtime']
    body_class = Body

    def __init__(self, status='FAIL', starttime=None, endtime=None, parent=None):
        super().__init__(parent)
        self.status = status
        self.starttime = starttime
        self.endtime = endtime
        self.body = None

    @setter
    def body(self, body):
        """Child keywords and messages as a :class:`~.Body` object.

        Typically empty. Only contains something if running BREAK has failed
        due to a syntax error or listeners have logged messages or executed
        keywords.
        """
        return self.body_class(self, body)

    @property
    @deprecated
    def args(self):
        return ()

    @property
    @deprecated
    def doc(self):
        return ''


@Body.register
class Error(model.Error, StatusMixin, DeprecatedAttributesMixin):
    __slots__ = ['status', 'starttime', 'endtime']
    body_class = Body

    def __init__(self, values=(), status='FAIL', starttime=None, endtime=None, parent=None):
        super().__init__(values, parent)
        self.status = status
        self.starttime = starttime
        self.endtime = endtime
        self.body = None

    @setter
    def body(self, body):
        """Messages as a :class:`~.Body` object.

        Typically contains the message that caused the error.
        """
        return self.body_class(self, body)

    @property
    @deprecated
    def kwname(self):
        return self.values[0]

    @property
    @deprecated
    def args(self):
        return self.values[1:]

    @property
    @deprecated
    def doc(self):
        return ''


@Body.register
@Branches.register
@Iterations.register
class Keyword(model.Keyword, StatusMixin):
    """Represents an executed library or user keyword."""
    body_class = Body
    __slots__ = ['kwname', 'libname', 'doc', 'timeout', 'status', '_teardown',
                 'starttime', 'endtime', 'message', 'sourcename']

    def __init__(self, kwname='', libname='', doc='', args=(), assign=(), tags=(),
                 timeout=None, type=BodyItem.KEYWORD, status='FAIL', starttime=None,
                 endtime=None, parent=None, sourcename=None):
        super().__init__(None, args, assign, type, parent)
        #: Name of the keyword without library or resource name.
        self.kwname = kwname
        #: Name of the library or resource containing this keyword.
        self.libname = libname
        self.doc = doc
        self.tags = tags
        self.timeout = timeout
        self.status = status
        self.starttime = starttime
        self.endtime = endtime
        #: Keyword status message. Used only if suite teardowns fails.
        self.message = ''
        #: Original name of keyword with embedded arguments.
        self.sourcename = sourcename
        self._teardown = None
        self.body = None

    @setter
    def body(self, body):
        """Possible keyword body as a :class:`~.Body` object.

        Body can consist of child keywords, messages, and control structures
        such as IF/ELSE. Library keywords typically have an empty body.
        """
        return self.body_class(self, body)

    @property
    def keywords(self):
        """Deprecated since Robot Framework 4.0.

        Use :attr:`body` or :attr:`teardown` instead.
        """
        keywords = self.body.filter(messages=False)
        if self.teardown:
            keywords.append(self.teardown)
        return Keywords(self, keywords)

    @keywords.setter
    def keywords(self, keywords):
        Keywords.raise_deprecation_error()

    @property
    def messages(self):
        """Keyword's messages.

        Starting from Robot Framework 4.0 this is a list generated from messages
        in :attr:`body`.
        """
        return self.body.filter(messages=True)

    @property
    def children(self):
        """List of child keywords and messages in creation order.

        Deprecated since Robot Framework 4.0. Use :attr:`body` instead.
        """
        warnings.warn("'Keyword.children' is deprecated. Use 'Keyword.body' instead.")
        return list(self.body)

    @property
    def name(self):
        """Keyword name in format ``libname.kwname``.

        Just ``kwname`` if :attr:`libname` is empty. In practice that is the
        case only with user keywords in the same file as the executed test case
        or test suite.

        Cannot be set directly. Set :attr:`libname` and :attr:`kwname`
        separately instead.
        """
        if not self.libname:
            return self.kwname
        return '%s.%s' % (self.libname, self.kwname)

    @name.setter
    def name(self, name):
        if name is not None:
            raise AttributeError("Cannot set 'name' attribute directly. "
                                 "Set 'kwname' and 'libname' separately instead.")
        self.kwname = None
        self.libname = None

    @property    # Cannot use @setter because it would create teardowns recursively.
    def teardown(self):
        """Keyword teardown as a :class:`Keyword` object.

        Teardown can be modified by setting attributes directly::

            keyword.teardown.name = 'Example'
            keyword.teardown.args = ('First', 'Second')

        Alternatively the :meth:`config` method can be used to set multiple
        attributes in one call::

            keyword.teardown.config(name='Example', args=('First', 'Second'))

        The easiest way to reset the whole teardown is setting it to ``None``.
        It will automatically recreate the underlying ``Keyword`` object::

            keyword.teardown = None

        This attribute is a ``Keyword`` object also when a keyword has no teardown
        but in that case its truth value is ``False``. If there is a need to just
        check does a keyword have a teardown, using the :attr:`has_teardown`
        attribute avoids creating the ``Keyword`` object and is thus more memory
        efficient.

        New in Robot Framework 4.0. Earlier teardown was accessed like
        ``keyword.keywords.teardown``. :attr:`has_teardown` is new in Robot
        Framework 4.1.2.
        """
        if self._teardown is None and self:
            self._teardown = create_fixture(None, self, self.TEARDOWN)
        return self._teardown

    @teardown.setter
    def teardown(self, teardown):
        self._teardown = create_fixture(teardown, self, self.TEARDOWN)

    @property
    def has_teardown(self):
        """Check does a keyword have a teardown without creating a teardown object.

        A difference between using ``if kw.has_teardown:`` and ``if kw.teardown:``
        is that accessing the :attr:`teardown` attribute creates a :class:`Keyword`
        object representing a teardown even when the keyword actually does not
        have one. This typically does not matter, but with bigger suite structures
        having lots of keywords it can have a considerable effect on memory usage.

        New in Robot Framework 4.1.2.
        """
        return bool(self._teardown)

    @setter
    def tags(self, tags):
        """Keyword tags as a :class:`~.model.tags.Tags` object."""
        return Tags(tags)


class TestCase(model.TestCase, StatusMixin):
    """Represents results of a single test case.

    See the base class for documentation of attributes not documented here.
    """
    __slots__ = ['status', 'message', 'starttime', 'endtime']
    body_class = Body
    fixture_class = Keyword

    def __init__(self, name='', doc='', tags=None, timeout=None, lineno=None,
                 status='FAIL', message='', starttime=None, endtime=None,
                 parent=None):
        super().__init__(name, doc, tags, timeout, lineno, parent)
        #: Status as a string ``PASS`` or ``FAIL``. See also :attr:`passed`.
        self.status = status
        #: Test message. Typically a failure message but can be set also when
        #: test passes.
        self.message = message
        #: Test case execution start time in format ``%Y%m%d %H:%M:%S.%f``.
        self.starttime = starttime
        #: Test case execution end time in format ``%Y%m%d %H:%M:%S.%f``.
        self.endtime = endtime

    @property
    def not_run(self):
        return False

    @property
    def critical(self):
        warnings.warn("'TestCase.critical' is deprecated and always returns 'True'.")
        return True


class TestSuite(model.TestSuite, StatusMixin):
    """Represents results of a single test suite.

    See the base class for documentation of attributes not documented here.
    """
    __slots__ = ['message', 'starttime', 'endtime']
    test_class = TestCase
    fixture_class = Keyword

    def __init__(self, name='', doc='', metadata=None, source=None, message='',
                 starttime=None, endtime=None, rpa=False, parent=None):
        super().__init__(name, doc, metadata, source, rpa, parent)
        #: Possible suite setup or teardown error message.
        self.message = message
        #: Suite execution start time in format ``%Y%m%d %H:%M:%S.%f``.
        self.starttime = starttime
        #: Suite execution end time in format ``%Y%m%d %H:%M:%S.%f``.
        self.endtime = endtime

    @property
    def passed(self):
        """``True`` if no test has failed but some have passed, ``False`` otherwise."""
        return self.status == self.PASS

    @property
    def failed(self):
        """``True`` if any test has failed, ``False`` otherwise."""
        return self.status == self.FAIL

    @property
    def skipped(self):
        """``True`` if there are no passed or failed tests, ``False`` otherwise."""
        return self.status == self.SKIP

    @property
    def not_run(self):
        return False

    @property
    def status(self):
        """'PASS', 'FAIL' or 'SKIP' depending on test statuses.

        - If any test has failed, status is 'FAIL'.
        - If no test has failed but at least some test has passed, status is 'PASS'.
        - If there are no failed or passed tests, status is 'SKIP'. This covers both
          the case when all tests have been skipped and when there are no tests.
        """
        stats = self.statistics  # Local variable avoids recreating stats.
        if stats.failed:
            return self.FAIL
        if stats.passed:
            return self.PASS
        return self.SKIP

    @property
    def statistics(self):
        """Suite statistics as a :class:`~robot.model.totalstatistics.TotalStatistics` object.

        Recreated every time this property is accessed, so saving the results
        to a variable and inspecting it is often a good idea::

            stats = suite.statistics
            print(stats.failed)
            print(stats.total)
            print(stats.message)
        """
        return TotalStatisticsBuilder(self, self.rpa).stats

    @property
    def full_message(self):
        """Combination of :attr:`message` and :attr:`stat_message`."""
        if not self.message:
            return self.stat_message
        return '%s\n\n%s' % (self.message, self.stat_message)

    @property
    def stat_message(self):
        """String representation of the :attr:`statistics`."""
        return self.statistics.message

    @property
    def elapsedtime(self):
        """Total execution time in milliseconds."""
        if self.starttime and self.endtime:
            return get_elapsed_time(self.starttime, self.endtime)
        return sum(child.elapsedtime for child in
                   chain(self.suites, self.tests, (self.setup, self.teardown)))

    def remove_keywords(self, how):
        """Remove keywords based on the given condition.

        :param how: What approach to use when removing keywords. Either
            ``ALL``, ``PASSED``, ``FOR``, ``WUKS``, or ``NAME:<pattern>``.

        For more information about the possible values see the documentation
        of the ``--removekeywords`` command line option.
        """
        self.visit(KeywordRemover(how))

    def filter_messages(self, log_level='TRACE'):
        """Remove log messages below the specified ``log_level``."""
        self.visit(MessageFilter(log_level))

    def configure(self, **options):
        """A shortcut to configure a suite using one method call.

        Can only be used with the root test suite.

        :param options: Passed to
            :class:`~robot.result.configurer.SuiteConfigurer` that will then
            set suite attributes, call :meth:`filter`, etc. as needed.

        Example::

            suite.configure(remove_keywords='PASSED',
                            doc='Smoke test results.')

        Not to be confused with :meth:`config` method that suites, tests,
        and keywords have to make it possible to set multiple attributes in
        one call.
        """
        model.TestSuite.configure(self)    # Parent validates call is allowed.
        self.visit(SuiteConfigurer(**options))

    def handle_suite_teardown_failures(self):
        """Internal usage only."""
        self.visit(SuiteTeardownFailureHandler())

    def suite_teardown_failed(self, error):
        """Internal usage only."""
        self.visit(SuiteTeardownFailed(error))

    def suite_teardown_skipped(self, message):
        """Internal usage only."""
        self.visit(SuiteTeardownFailed(message, skipped=True))
