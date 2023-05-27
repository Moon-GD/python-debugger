# ContinuousSpectrumDebugger

import html
import inspect
import math
import sys
import traceback
from IPython.display import Markdown
from typing import Any, Optional, Callable, Dict, List, Type, TextIO, cast, Tuple, Set, TypeVar, Union
from types import FrameType, TracebackType, FunctionType
Coverage = Set[Tuple[Callable, int]]

class ContinuousSpectrumDebugger():
    PASS = 'PASS'
    FAIL = 'FAIL'

    def __init__(self, collector_class: Type = CoverageCollector, log: bool = False):
        """Constructor. Use instances of `collector_class` to collect events."""
        self.collector_class = collector_class
        self.collectors: Dict[str, List[Collector]] = {}
        self.log = log
        
    def __enter__(self) -> Any:
        """Enter a `with` block. Collect coverage and outcome;
        classify as FAIL if the block raises an exception,
        and PASS if it does not.
        """
        self.collector = self.collector_class()
        self.collector.add_items_to_ignore([self.__class__])
        self.collector.__enter__()
        return self

    def __exit__(self, exc_tp: Type, exc_value: BaseException,
                 exc_traceback: TracebackType) -> Optional[bool]:
        """Exit the `with` block."""
        status = self.collector.__exit__(exc_tp, exc_value, exc_traceback)

        if status is None:
            pass
        else:
            return False  # Internal error; re-raise exception

        if exc_tp is None:
            outcome = self.PASS
        else:
            outcome = self.FAIL

        self.add_collector(outcome, self.collector)
        return True  # Ignore exception, if any

    def __repr__(self) -> str:
        """Show code as string"""
        return self.code(color=False, suspiciousness=True)
    
    def __str__(self) -> str:
        """Show code as string"""
        return self.code(color=False, suspiciousness=True)

    def _repr_html_(self) -> str:
        """When output in Jupyter, visualize as HTML"""
        return self.code(color=True)
    
    def _repr_markdown_(self) -> str:
        return self.event_table_text(args=True, color=True)
        
    def all_fail_events(self) -> Set[Any]:
        """Return all events observed in failing runs."""
        return self.all_events(self.FAIL)

    def all_pass_events(self) -> Set[Any]:
        """Return all events observed in passing runs."""
        return self.all_events(self.PASS)    

    def add_collector(self, outcome: str, collector: Collector) -> Collector:
        if outcome not in self.collectors:
            self.collectors[outcome] = []
        self.collectors[outcome].append(collector)
        return collector
    
    def all_events(self, outcome: Optional[str] = None) -> Set[Any]:
        """Return a set of all events observed."""
        all_events = set()

        if outcome:
            if outcome in self.collectors:
                for collector in self.collectors[outcome]:
                    all_events.update(collector.events())
        else:
            for outcome in self.collectors:
                for collector in self.collectors[outcome]:
                    all_events.update(collector.events())

        return all_events
    
    def brightness(self, event: Any) -> float:
        return max(self.passed_fraction(event), self.failed_fraction(event))
    
    def collect(self, outcome: str, *args: Any, **kwargs: Any) -> Collector:
        """Return a collector for the given outcome. 
        Additional args are passed to the collector."""
        collector = self.collector_class(*args, **kwargs)
        collector.add_items_to_ignore([self.__class__])
        return self.add_collector(outcome, collector)
    
    def collect_pass(self, *args: Any, **kwargs: Any) -> Collector:
        """Return a collector for passing runs."""
        return self.collect(self.PASS, *args, **kwargs)

    def collect_fail(self, *args: Any, **kwargs: Any) -> Collector:
        """Return a collector for failing runs."""
        return self.collect(self.FAIL, *args, **kwargs)
    
    def covered_functions(self) -> Set[Callable]:
        """Return a set of all functions observed."""
        functions = set()
        for outcome in self.collectors:
            for collector in self.collectors[outcome]:
                functions |= collector.covered_functions()
        return functions

    def collectors_with_event(self, event: Any, category: str) -> Set[Collector]:
        """
        Return all collectors in a category
        that observed the given event.
        """
        all_runs = self.collectors[category]
        collectors_with_event = set(collector for collector in all_runs 
                                    if event in collector.events())
        return collectors_with_event
    
    def collectors_without_event(self, event: Any, category: str) -> Set[Collector]:
        """
        Return all collectors in a category
        that did not observe the given event.
        """
        all_runs = self.collectors[category]
        collectors_without_event = set(collector for collector in all_runs 
                              if event not in collector.events())
        return collectors_without_event
    
    def coverage(self) -> Coverage:
        """Return a set of all (functions, line_numbers) observed"""
        coverage = set()
        for outcome in self.collectors:
            for collector in self.collectors[outcome]:
                coverage |= collector.coverage()
        return coverage

    def color(self, event: Any) -> Optional[str]:
        hue = self.hue(event)
        if hue is None:
            return None
        saturation = self.brightness(event)

        # HSL color values are specified with: 
        # hsl(hue, saturation, lightness).
        return f"hsl({hue * 120}, {saturation * 100}%, 80%)"
    
    def code(self, functions: Optional[Set[Callable]] = None, *, 
             color: bool = False, suspiciousness: bool = False,
             line_numbers: bool = True) -> str:
        """
        Return a listing of `functions` (default: covered functions).
        If `color` is True, render as HTML, using suspiciousness colors.
        If `suspiciousness` is True, include suspiciousness values.
        If `line_numbers` is True (default), include line numbers.
        """

        if not functions:
            functions = self.covered_functions()

        out = ""
        seen = set()
        for function in functions:
            source_lines, starting_line_number = \
               inspect.getsourcelines(function)

            if (function.__name__, starting_line_number) in seen:
                continue
            seen.add((function.__name__, starting_line_number))

            if out:
                out += '\n'
                if color:
                    out += '<p/>'

            line_number = starting_line_number
            for line in source_lines:
                if color:
                    line = html.escape(line)
                    if line.strip() == '':
                        line = '&nbsp;'

                location = (function.__name__, line_number)
                location_suspiciousness = self.suspiciousness(location)
                if location_suspiciousness is not None:
                    tooltip = f"Line {line_number}: {self.tooltip(location)}"
                else:
                    tooltip = f"Line {line_number}: not executed"

                if suspiciousness:
                    line = self.percentage(location) + ' ' + line

                if line_numbers:
                    line = str(line_number).rjust(4) + ' ' + line

                line_color = self.color(location)

                if color and line_color:
                    line = f'''<pre style="background-color:{line_color}"
                    title="{tooltip}">{line.rstrip()}</pre>'''
                elif color:
                    line = f'<pre title="{tooltip}">{line}</pre>'
                else:
                    line = line.rstrip()

                out += line + '\n'
                line_number += 1

        return out
    
    def event_fraction(self, event: Any, category: str) -> float:
        if category not in self.collectors:
            return 0.0

        all_collectors = self.collectors[category]
        collectors_with_event = self.collectors_with_event(event, category)
        fraction = len(collectors_with_event) / len(all_collectors)
        # print(f"%{category}({event}) = {fraction}")
        return fraction
    
    def event_str(self, event: Any) -> str:
        """Format the given event. To be overloaded in subclasses."""
        if isinstance(event, str):
            return event
        if isinstance(event, tuple):
            return ":".join(self.event_str(elem) for elem in event)
        return str(event)

    def event_table_text(self, *, args: bool = False, color: bool = False) -> str:
        """
        Print out a table of events observed.
        If `args` is True, use arguments as headers.
        If `color` is True, use colors.
        """
        sep = ' | '
        all_events = self.all_events()
        longest_event = max(len(f"{self.event_str(event)}") 
                            for event in all_events)
        out = ""

        # Header
        if args:
            out += '| '
            func = self.function()
            if func:
                out += '`' + func.__name__ + '`'
            out += sep
            for name in self.collectors:
                for collector in self.collectors[name]:
                    out += '`' + collector.argstring() + '`' + sep
            out += '\n'
        else:
            out += '| ' + ' ' * longest_event + sep
            for name in self.collectors:
                for i in range(len(self.collectors[name])):
                    out += name + sep
            out += '\n'

        out += '| ' + '-' * longest_event + sep
        for name in self.collectors:
            for i in range(len(self.collectors[name])):
                out += '-' * len(name) + sep
        out += '\n'

        # Data
        for event in sorted(all_events):
            event_name = self.event_str(event).rjust(longest_event)

            tooltip = self.tooltip(event)
            if tooltip:
                title = f' title="{tooltip}"'
            else:
                title = ''

            if color:
                color_name = self.color(event)
                if color_name:
                    event_name = \
                        f'<samp style="background-color: {color_name}"{title}>' \
                        f'{html.escape(event_name)}' \
                        f'</samp>'

            out += f"| {event_name}" + sep
            for name in self.collectors:
                for collector in self.collectors[name]:
                    out += ' ' * (len(name) - 1)
                    if event in collector.events():
                        out += "X"
                    else:
                        out += "-"
                    out += sep
            out += '\n'

        return out

    def event_table(self, **_args: Any) -> Any:
        """Print out event table in Markdown format."""
        return Markdown(self.event_table_text(**_args))
    
    def fail_collectors(self) -> List[Collector]:
        return self.collectors[self.FAIL]
    
    def failed_fraction(self, event: Any) -> float:
        return self.event_fraction(event, self.FAIL)
    
    def function(self) -> Optional[Callable]:
        """
        Return the entry function from the events observed,
        or None if ambiguous.
        """
        names_seen = set()
        functions = []
        for outcome in self.collectors:
            for collector in self.collectors[outcome]:
                # We may have multiple copies of the function,
                # but sharing the same name
                func = collector.function()
                if func.__name__ not in names_seen:
                    functions.append(func)
                    names_seen.add(func.__name__)

        if len(functions) != 1:
            return None  # ambiguous
        return functions[0]

    def hue(self, event: Any) -> Optional[float]:
        """Return a color hue from 0.0 (red) to 1.0 (green)."""
        passed = self.passed_fraction(event)
        failed = self.failed_fraction(event)
        if passed + failed > 0:
            return passed / (passed + failed)
        else:
            return None
    
    def only_fail_events(self) -> Set[Any]:
        """Return all events observed only in failing runs."""
        return self.all_fail_events() - self.all_pass_events()

    def only_pass_events(self) -> Set[Any]:
        """Return all events observed only in passing runs."""
        return self.all_pass_events() - self.all_fail_events()
    
    def passed_fraction(self, event: Any) -> float:
        return self.event_fraction(event, self.PASS)
    
    def pass_collectors(self) -> List[Collector]:
        return self.collectors[self.PASS]
    
    def percentage(self, event: Any) -> str:
        """
        Return the suspiciousness for the given event as percentage string.
        """
        suspiciousness = self.suspiciousness(event)
        
        if suspiciousness is not None:
            return str(int(suspiciousness * 100)).rjust(3) + '%'
        else:
            return ' ' * len('100%')
    
    def suspiciousness(self, event: Any) -> Optional[float]:
        hue = self.hue(event)
        if hue is None:
            return None
        return 1 - hue
    
    def tooltip(self, event: Any) -> str:
        return self.percentage(event)
