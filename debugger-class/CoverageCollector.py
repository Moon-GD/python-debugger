import html
import inspect
import math
import sys
import traceback
from IPython.display import Markdown
from typing import Any, Optional, Callable, Dict, List, Type, TextIO, cast, Tuple, Set, TypeVar, Union
from types import FrameType, TracebackType, FunctionType
Coverage = Set[Tuple[Callable, int]]

# Coverage Collector
### A class to record covered locations during execution.

class CoverageCollector():
    _generated_function_cache: Dict[Tuple[str, int], Callable] = {}
        
    def __init__(self, *, file: TextIO = sys.stdout) -> None:
        self.original_trace_function: Optional[Callable] = None
        self.file = file
        self.last_vars: Dict[str, Any] = {}
        self._generated_function_cache = {}
        self._function: Optional[Callable] = None
        self._args: Optional[Dict[str, Any]] = None
        self._argstring: Optional[str] = None
        self._exception: Optional[Type] = None
        self.items_to_ignore: List[Union[Type, Callable]] = [self.__class__]
        self._coverage: Coverage = set()
        
    def _traceit(self, frame: FrameType, event: str, arg: Any) -> Optional[Callable]:
        """Internal tracing function."""
        if self.our_frame(frame):
            # Do not trace our own methods
            pass
        else:
            self.traceit(frame, event, arg)
        return self._traceit
    
    def __enter__(self) -> Any:
        """Called at begin of `with` block. Turn tracing on."""
        self.original_trace_function = sys.gettrace()
        sys.settrace(self._traceit)

        # This extra line also enables tracing for the current block
        # inspect.currentframe().f_back.f_trace = self._traceit
        return self
        
    def __exit__(self, exc_tp: Type, exc_value: BaseException,
                 exc_traceback: TracebackType) -> Optional[bool]:
        """Exit the `with` block."""
        sys.settrace(self.original_trace_function)
        if self.is_internal_error(exc_tp, exc_value, exc_traceback):
            ret = False
        else:
            ret = None

        if not self._function:
            if exc_tp:
                return False  # re-raise exception
            else:
                raise ValueError("No call collected")

        return ret
        
    def __repr__(self) -> str:
        """Return a string representation of the collector"""
        return self.id()   
    
    def add_items_to_ignore(self,
                            items_to_ignore: List[Union[Type, Callable]]) \
                            -> None:
        """
        Define additional classes and functions to ignore during collection
        """
        self.items_to_ignore += items_to_ignore
    
    def argstring(self) -> str:
        """
        Return the list of arguments from the first call,
        as a printable string
        """
        if not self._argstring:
            raise ValueError("No call collected")
        return self._argstring    

    def args(self) -> Dict[str, Any]:
        """Return a dict of argument names and values from the first call"""
        if not self._args:
            raise ValueError("No call collected")
        return self._args
    
    def caller_frame(self) -> FrameType:
        """Return the frame of the caller."""

        # Walk up the call tree until we leave the current class
        frame = cast(FrameType, inspect.currentframe())

        while self.our_frame(frame):
            frame = cast(FrameType, frame.f_back)

        return frame
    
    def caller_function(self) -> Callable:
        """Return the calling function"""
        frame = self.caller_frame()
        name = frame.f_code.co_name
        func = self.search_func(name)
        if func:
            return func

        if not name.startswith('<'):
            warnings.warn(f"Couldn't find {name} in caller")

        return self.create_function(frame)
    
    def create_function(self, frame: FrameType) -> Callable:
        name = frame.f_code.co_name
        cache_key = (name, frame.f_lineno)
        if cache_key in self._generated_function_cache:
            return self._generated_function_cache[cache_key]

        try:
            # Create new function from given code
            generated_function = cast(Callable,
                                      FunctionType(frame.f_code,
                                                   globals=frame.f_globals,
                                                   name=name))
        except TypeError:
            # Unsuitable code for creating a function
            # Last resort: Return some function
            generated_function = self.unknown

        except Exception as exc:
            # Any other exception
            warnings.warn(f"Couldn't create function for {name} "
                          f" ({type(exc).__name__}: {exc})")
            generated_function = self.unknown

        self._generated_function_cache[cache_key] = generated_function
        
        return generated_function
    
    def changed_vars(self, new_vars: Dict[str, Any]) -> Dict[str, Any]:
        """Track changed variables, based on `new_vars` observed."""
        changed = {}
        for var_name, var_value in new_vars.items():
            if (var_name not in self.last_vars or
                    self.last_vars[var_name] != var_value):
                changed[var_name] = var_value
        self.last_vars = new_vars.copy()
        
        return changed
    
    def collect(self, frame: FrameType, event: str, arg: Any) -> None:
        name = frame.f_code.co_name
        function = self.search_func(name, frame)

        if function is None:
            function = self.create_function(frame)

        location = (function, frame.f_lineno)
        self._coverage.add(location)
    
    def covered_functions(self) -> Set[Callable]:
        """Return a set with all functions covered."""
        return {func for func, lineno in self._coverage}

    def coverage(self) -> Coverage:
        """Return a set (function, lineno) with all locations covered."""
        return self._coverage
    
    def events(self) -> Set[Tuple[str, int]]:
        """
        Return the set of locations covered.
        Each location comes as a pair (`function_name`, `lineno`).
        """
        return {(func.__name__, lineno) for func, lineno in self._coverage}
    
    def exception(self) -> Optional[Type]:
        """Return the exception class from the first call,
        or None if no exception was raised."""
        return self._exception
    
    def function(self) -> Callable:
        """Return the function from the first call, as a function object"""
        if not self._function:
            raise ValueError("No call collected")
        return self._function
    
    def id(self) -> str:
        """Return an identifier for the collector, created from the first call"""
        """That is, return a printable representation of the call:"""
        
        return f"{self.function().__name__}({self.argstring()})"
    
    def is_internal_error(self, exc_tp: Type, 
                          exc_value: BaseException, 
                          exc_traceback: TracebackType) -> bool:
        """Return True if exception was raised from `StackInspector` or a subclass."""
        if not exc_tp:
            return False

        for frame, lineno in traceback.walk_tb(exc_traceback):
            if self.our_frame(frame):
                return True

        return False

    def log(self, *objects: Any, 
            sep: str = ' ', end: str = '\n', 
            flush: bool = True) -> None:
        """
        Like `print()`, but always sending to `file` given at initialization,
        and flushing by default.
        """
        print(*objects, sep=sep, end=end, file=self.file, flush=flush)
    
    def our_frame(self, frame: FrameType) -> bool:
        """Return true if `frame` is in the current (inspecting) class."""
        return isinstance(frame.f_locals.get('self'), self.__class__)
    
    def search_frame(self, name: str, frame: Optional[FrameType] = None) -> \
        Tuple[Optional[FrameType], Optional[Callable]]:
        """
        Return a pair (`frame`, `item`) 
        in which the function `name` is defined as `item`.
        """
        if frame is None:
            frame = self.caller_frame()

        while frame:
            item = None
            if name in frame.f_globals:
                item = frame.f_globals[name]
            if name in frame.f_locals:
                item = frame.f_locals[name]
            if item and callable(item):
                return frame, item

            frame = cast(FrameType, frame.f_back)

        return None, None
    
    def search_func(self, name: str, frame: Optional[FrameType] = None) -> \
        Optional[Callable]:
        """Search in callers for a definition of the function `name`"""
        frame, func = self.search_frame(name, frame)
        
        return func
        
    def print_debugger_status(self, frame: FrameType, event: str, arg: Any) -> None:
        """Show current source line and changed vars"""
        changes = self.changed_vars(frame.f_locals)
        changes_s = ", ".join([var + " = " + repr(changes[var])
                               for var in changes])

        if event == 'call':
            self.log("Calling " + frame.f_code.co_name + '(' + changes_s + ')')
        elif changes:
            self.log(' ' * 40, '#', changes_s)

        if event == 'line':
            try:
                module = inspect.getmodule(frame.f_code)
                if module is None:
                    source = inspect.getsource(frame.f_code)
                else:
                    source = inspect.getsource(module)
                current_line = source.split('\n')[frame.f_lineno - 1]

            except OSError as err:
                self.log(f"{err.__class__.__name__}: {err}")
                current_line = ""

            self.log(repr(frame.f_lineno) + ' ' + current_line)

        if event == 'return':
            self.log(frame.f_code.co_name + '()' + " returns " + repr(arg))
            self.last_vars = {}  # Delete 'last' variables
        
    def traceit(self, frame: FrameType, event: str, arg: Any) -> None:
        # 넘어가도 되는 코드인지 검사
        for item in self.items_to_ignore:
            # 무시하기로 했던 class인 경우
            if (isinstance(item, type) and 'self' in frame.f_locals and
                isinstance(frame.f_locals['self'], item)):
                return
            
            # 무시하기로 했던 함수인 경우
            if item.__name__ == frame.f_code.co_name:
                return

        # 추적 함수 초기화
        
        if self._function is None and event == 'call':
            self._function = self.create_function(frame)
            self._args = frame.f_locals.copy()
            self._argstring = ", ".join([f"{var}={repr(self._args[var])}" 
                                         for var in self._args])

        self.collect(frame, event, arg)
