import html
import inspect
import math
import sys
import traceback
from IPython.display import Markdown
from typing import Any, Optional, Callable, Dict, List, Type, TextIO, cast, Tuple, Set, TypeVar, Union
from types import FrameType, TracebackType, FunctionType
Coverage = Set[Tuple[Callable, int]]

# Collector
class Collector():
    _generated_function_cache: Dict[Tuple[str, int], Callable] = {}
        
    def __init__(self, *, file: TextIO = sys.stdout) -> None:
        self._args: Optional[Dict[str, Any]] = None  # 추적 함수의 인자 정보 저장
        self._argstring: Optional[str] = None  # 추적 함수의 인자 정보를 가독성 있게 표현
        self._exception: Optional[Type] = None
        self._function: Optional[Callable] = None  # 추적 함수
        self._generated_function_cache = {}
        self.file = file
        self.items_to_ignore: List[Union[Type, Callable]] = [self.__class__]  # 추적을 무시하고자 하는 Class, function
        self.last_vars: Dict[str, Any] = {}
        self.original_trace_function: Optional[Callable] = None  # 추적하고자 하는 함수의 원본 정보
        
    def _traceit(self, frame: FrameType, event: str, arg: Any) -> Optional[Callable]:
        if self.our_frame(frame):
            pass
        else:
            self.traceit(frame, event, arg)
            
        return self._traceit
    
    def __enter__(self) -> Any:
        self.original_trace_function = sys.gettrace()
        sys.settrace(self._traceit)

        return self
        
    def __exit__(self, exc_tp: Type, exc_value: BaseException,
                 exc_traceback: TracebackType) -> Optional[bool]:
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
        
    # 가독성 있게 Colletor 정보 반환
    def __repr__(self) -> str:
        return self.id()   
    
    # 추적을 무시할 Class, function 추가
    def add_items_to_ignore(self,
                            items_to_ignore: List[Union[Type, Callable]]) \
                            -> None:
        self.items_to_ignore += items_to_ignore
    
    # self._argstring 반환
    def argstring(self) -> str:
        if not self._argstring:
            raise ValueError("No call collected")
        return self._argstring    

    # self._arg 반환
    def args(self) -> Dict[str, Any]:
        if not self._args:
            raise ValueError("No call collected")
        return self._args
    
    # 현재 frame의 호출자를 반환
    def caller_frame(self) -> FrameType:
        """Return the frame of the caller."""

        # Walk up the call tree until we leave the current class
        frame = cast(FrameType, inspect.currentframe())

        while self.our_frame(frame):
            frame = cast(FrameType, frame.f_back)

        return frame
    
    # 호출했던 함수를 찾아 반환
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
    
    # 주어진 frame을 기반으로 함수 객체를 생성하여 반환
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
        """Collector function. To be overloaded in subclasses."""
        pass

    # cover 되었던 함수 set 반환
    def covered_functions(self) -> Set[Callable]:
        return set()

    # cover되었던 (function, line number) 반환
    def coverage(self) -> Coverage:
        return set()
    
    # event set 반환
    def events(self) -> Set:
        return set()
    
    def exception(self) -> Optional[Type]:
        """Return the exception class from the first call,
        or None if no exception was raised."""
        return self._exception
    
    # 추적 중인 함수 객체를 반환
    def function(self) -> Callable:
        """Return the function from the first call, as a function object"""
        if not self._function:
            raise ValueError("No call collected")
        return self._function
    
    # 가독성 있는 함수 정보를 반환
    def id(self) -> str:
        return f"{self.function().__name__}({self.argstring()})"
    
    # 추적 과정에서 내부에 에러가 발생했었는지 여부를 반환
    def is_internal_error(self, exc_tp: Type, 
                          exc_value: BaseException, 
                          exc_traceback: TracebackType) -> bool:
        if not exc_tp:
            return False

        for frame, lineno in traceback.walk_tb(exc_traceback):
            if self.our_frame(frame):
                return True

        return False

    # 디버깅 정보를 출력하기 위한 함수 (flush가 항상 되도록 설정된 것이 특징!)
    def log(self, *objects: Any, 
            sep: str = ' ', end: str = '\n', 
            flush: bool = True) -> None:
        print(*objects, sep=sep, end=end, file=self.file, flush=flush)
    
    # frame이 현재 클래스 내부에 존재하는 지 여부를 반환
    def our_frame(self, frame: FrameType) -> bool:
        return isinstance(frame.f_locals.get('self'), self.__class__)
    
    # 이름을 기반으로 대응되는 프레임을 검색
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
        
    # 디버거의 현재 상태 (source line, 바뀐 변수 등) 출력을 위한 메소드
    def print_debugger_status(self, frame: FrameType, event: str, arg: Any) -> None:
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
        for item in self.items_to_ignore:
            if (isinstance(item, type) and 'self' in frame.f_locals and
                isinstance(frame.f_locals['self'], item)):
                return
            
            if item.__name__ == frame.f_code.co_name:
                return

        # 추적 함수 초기화
        if self._function is None and event == 'call':
            self._function = self.create_function(frame)
            self._args = frame.f_locals.copy()
            self._argstring = ", ".join([f"{var}={repr(self._args[var])}" 
                                         for var in self._args])

        self.collect(frame, event, arg)
        
    def unknown(self) -> None:  # Placeholder for unknown functions
        pass
    
# Coverage Collector
class CoverageCollector():
    _generated_function_cache: Dict[Tuple[str, int], Callable] = {}
        
    def __init__(self, *, file: TextIO = sys.stdout) -> None:
        self._args: Optional[Dict[str, Any]] = None  # 추적 함수의 인자 정보 저장
        self._argstring: Optional[str] = None  # 추적 함수의 인자 정보를 가독성 있게 표현
        self._coverage: Coverage = set()  # coverage information이 담기는 set
        self._exception: Optional[Type] = None
        self._function: Optional[Callable] = None  # 추적 함수
        self._generated_function_cache = {}
        self.file = file
        self.items_to_ignore: List[Union[Type, Callable]] = [self.__class__]  # 추적을 무시하고자 하는 Class, function
        self.last_vars: Dict[str, Any] = {}
        self.original_trace_function: Optional[Callable] = None  # 추적하고자 하는 함수의 원본 정보
        
    def _traceit(self, frame: FrameType, event: str, arg: Any) -> Optional[Callable]:
        if self.our_frame(frame):
            pass
        else:
            self.traceit(frame, event, arg)
            
        return self._traceit
    
    def __enter__(self) -> Any:
        self.original_trace_function = sys.gettrace()
        sys.settrace(self._traceit)

        return self
        
    def __exit__(self, exc_tp: Type, exc_value: BaseException,
                 exc_traceback: TracebackType) -> Optional[bool]:
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
        
    # 가독성 있게 Colletor 정보 반환
    def __repr__(self) -> str:
        return self.id()   
    
    # 추적을 무시할 Class, function 추가
    def add_items_to_ignore(self,
                            items_to_ignore: List[Union[Type, Callable]]) \
                            -> None:
        self.items_to_ignore += items_to_ignore
    
    # self._argstring 반환
    def argstring(self) -> str:
        if not self._argstring:
            raise ValueError("No call collected")
        return self._argstring    

    # self._arg 반환
    def args(self) -> Dict[str, Any]:
        if not self._args:
            raise ValueError("No call collected")
        return self._args
    
    # 현재 frame의 호출자를 반환
    def caller_frame(self) -> FrameType:
        frame = cast(FrameType, inspect.currentframe())

        while self.our_frame(frame):
            frame = cast(FrameType, frame.f_back)

        return frame
    
    # 호출했던 함수를 찾아 반환
    def caller_function(self) -> Callable:
        frame = self.caller_frame()
        name = frame.f_code.co_name
        func = self.search_func(name)
        if func:
            return func

        if not name.startswith('<'):
            warnings.warn(f"Couldn't find {name} in caller")

        return self.create_function(frame)
    
    # 주어진 frame을 기반으로 함수 객체를 생성하여 반환
    def create_function(self, frame: FrameType) -> Callable:
        """Create function for given frame"""
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
        changed = {}
        for var_name, var_value in new_vars.items():
            if (var_name not in self.last_vars or
                    self.last_vars[var_name] != var_value):
                changed[var_name] = var_value
        self.last_vars = new_vars.copy()
        
        return changed
    
    # 호출된 함수와 line number를 튜플로 만들어서 저장하는 함수
    # (function name, line number)
    def collect(self, frame: FrameType, event: str, arg: Any) -> None:
        name = frame.f_code.co_name
        function = self.search_func(name, frame)

        if function is None:
            function = self.create_function(frame)

        location = (function, frame.f_lineno)
        self._coverage.add(location)

    # cover 되었던 함수 set 반환
    def covered_functions(self) -> Set[Callable]:
        return {func for func, lineno in self._coverage}

    # self._coverage 반환
    def coverage(self) -> Coverage:
        return self._coverage
    
    # cover 되었던 (function, line number)의 집합 반환
    def events(self) -> Set[Tuple[str, int]]:
        return {(func.__name__, lineno) for func, lineno in self._coverage}
    
    def exception(self) -> Optional[Type]:
        """Return the exception class from the first call,
        or None if no exception was raised."""
        return self._exception
    
    # 추적 중인 함수 객체를 반환
    def function(self) -> Callable:
        if not self._function:
            raise ValueError("No call collected")
        return self._function
    
    # 가독성 있는 함수 정보를 반환
    def id(self) -> str:
        return f"{self.function().__name__}({self.argstring()})"
    
    # 추적 과정에서 내부에 에러가 발생했었는지 여부를 반환
    def is_internal_error(self, exc_tp: Type, 
                          exc_value: BaseException, 
                          exc_traceback: TracebackType) -> bool:
        if not exc_tp:
            return False

        for frame, lineno in traceback.walk_tb(exc_traceback):
            if self.our_frame(frame):
                return True

        return False

    # 디버깅 정보를 출력하기 위한 함수 (flush가 항상 되도록 설정된 것이 특징!)
    def log(self, *objects: Any, 
            sep: str = ' ', end: str = '\n', 
            flush: bool = True) -> None:
        print(*objects, sep=sep, end=end, file=self.file, flush=flush)
    
    # frame이 현재 클래스 내부에 존재하는 지 여부를 반환
    def our_frame(self, frame: FrameType) -> bool:
        return isinstance(frame.f_locals.get('self'), self.__class__)
    
    # 이름을 기반으로 대응되는 프레임을 검색
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
        
    # 디버거의 현재 상태 (source line, 바뀐 변수 등) 출력을 위한 메소드
    def print_debugger_status(self, frame: FrameType, event: str, arg: Any) -> None:
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
        for item in self.items_to_ignore:
            if (isinstance(item, type) and 'self' in frame.f_locals and
                isinstance(frame.f_locals['self'], item)):
                return
            
            if item.__name__ == frame.f_code.co_name:
                return

        # 추적 함수 초기화
        if self._function is None and event == 'call':
            self._function = self.create_function(frame)
            self._args = frame.f_locals.copy()
            self._argstring = ", ".join([f"{var}={repr(self._args[var])}" 
                                         for var in self._args])

        self.collect(frame, event, arg)
        
    def unknown(self) -> None:  # Placeholder for unknown functions
        pass
    
# Tarantula Debugger
class TarantulaDebugger():
    PASS = 'PASS'
    FAIL = 'FAIL'

    def __init__(self, collector_class: Type = CoverageCollector, log: bool = False):
        self.collector_class = collector_class  # Coverage Collector class를 내부에 정보로 가지고 있음
        self.collectors: Dict[str, List[Collector]] = {}  # Coverage Collector 집합 생성
        self.log = log 
        
    # 멤버 변수 Coverage Collector 객체의 초기화    
    def __enter__(self) -> Any:
        self.collector = self.collector_class()
        self.collector.add_items_to_ignore([self.__class__])  # Tarantual Debugger 객체는 추적하지 않도록 초기화
        self.collector.__enter__()  # (function name, line number)를 저장할 수 있도록 Coverage Collector 추적도 시작
        
        return self

    # 오류 여부 확인
    def __exit__(self, exc_tp: Type, exc_value: BaseException,
                 exc_traceback: TracebackType) -> Optional[bool]:
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

    # 가독성 있게 Tarantula Debugger로 추적한 rank 정보 출력
    def __repr__(self) -> str:
        return repr(self.rank())
    
    # cover되었던 함수의 suspiciousness 정보를 포함하여 반환
    def __str__(self) -> str:
        return self.code(color=False, suspiciousness=True)

    # cover되었던 함수 정보를 색깔과 HTML로 표현
    def _repr_html_(self) -> str:
        return self.code(color=True)
    
    # 관측되었던 event 정보를 테이블 형식으로 표현
    def _repr_markdown_(self) -> str:
        return self.event_table_text(args=True, color=True)
        
    # 실패했던 모든 이벤트들을 집합 형태로 반환
    def all_fail_events(self) -> Set[Any]:
        return self.all_events(self.FAIL)

    # 성공했던 모든 이벤트들을 집합 형태로 반환
    def all_pass_events(self) -> Set[Any]:
        return self.all_events(self.PASS)    

    # 새로운 key를 기반으로 한 collector 추가 메소드
    def add_collector(self, outcome: str, collector: Collector) -> Collector:
        if outcome not in self.collectors:
            self.collectors[outcome] = []
            
        self.collectors[outcome].append(collector)
        return collector
    
    # 멤버 변수 self.collectors에서 수집된 모든 (function name, line number) 정보를 집합으로 만들어 반환
    def all_events(self, outcome: Optional[str] = None) -> Set[Any]:
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
    
    # 채도 값을 반환 (0에 가까울 수록 회색, 1에 가까울 수록 원래의 채색)
    # 얼마나 해당 line이 자주 활용되었는지를 상징
    # 즉, 밝을 수록해당 line이 success, fail 과의 연관성이 높아짐을 의미
    def brightness(self, event: Any) -> float:
        return max(self.passed_fraction(event), self.failed_fraction(event))
    
    # outcome 정보에 알맞은 Coverage Collector 정보를 추가
    def collect(self, outcome: str, *args: Any, **kwargs: Any) -> Collector:
        collector = self.collector_class(*args, **kwargs)
        collector.add_items_to_ignore([self.__class__])
        return self.add_collector(outcome, collector)
    
    # pass 관련 event를 추적하는 Coverage Collector 객체를 추가
    def collect_pass(self, *args: Any, **kwargs: Any) -> Collector:
        return self.collect(self.PASS, *args, **kwargs)

    # fail 관련 event를 추적하는 Coverage Collector 객체를 추가
    def collect_fail(self, *args: Any, **kwargs: Any) -> Collector:        
        return self.collect(self.FAIL, *args, **kwargs)
    
    # cover 되었던 함수들의 집합을 반환
    def covered_functions(self) -> Set[Callable]:
        functions = set()
        for outcome in self.collectors:
            for collector in self.collectors[outcome]:
                functions |= collector.covered_functions()
        return functions

    # 특정된 event 값을 가지고 있는 category의 Collector 객체의 집합 반환
    def collectors_with_event(self, event: Any, category: str) -> Set[Collector]:
        all_runs = self.collectors[category]
        collectors_with_event = set(collector for collector in all_runs 
                                    if event in collector.events())
        return collectors_with_event
    
    # 특정된 event 값을 가지고 있지 않는 category의 Collector 객체의 집합 반환
    def collectors_without_event(self, event: Any, category: str) -> Set[Collector]:
        all_runs = self.collectors[category]
        collectors_without_event = set(collector for collector in all_runs 
                              if event not in collector.events())
        return collectors_without_event
    
    # 멤버 변수인 collector 객체들로 수집되었던 (function name, line number)의 모든 정보를 집합으로 반환
    def coverage(self) -> Coverage:
        coverage = set()
        for outcome in self.collectors:
            for collector in self.collectors[outcome]:
                coverage |= collector.coverage()
                
        return coverage

    # hsl(색상, 채도, 명도) 정보를 문자열로 반환
    def color(self, event: Any) -> Optional[str]:
        hue = self.hue(event) # Red = 0, Green = 120, Blue = 240
        if hue is None:
            return None
        saturation = self.brightness(event)

        return f"hsl({hue * 120}, {saturation * 100}%, 80%)"
    
    # cover되었던 함수들을 반환
    # color = True : HTML 형식으로 반환 (의심 색깔 포함하여)
    # suspiciousness = True : suspiciousness 값을 포함
    # line numbers = True : line number 포함
    def code(self, functions: Optional[Set[Callable]] = None, *, 
             color: bool = False, suspiciousness: bool = False,
             line_numbers: bool = True) -> str:

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
    
    # category에 맞는 collector 객체의 비율을 반환
    def event_fraction(self, event: Any, category: str) -> float:
        if category not in self.collectors:
            return 0.0

        all_collectors = self.collectors[category]
        collectors_with_event = self.collectors_with_event(event, category)
        fraction = len(collectors_with_event) / len(all_collectors)
        
        return fraction
    
    # 주어진 이벤트를 문자열로 표현
    def event_str(self, event: Any) -> str:
        if isinstance(event, str):
            return event
        if isinstance(event, tuple):
            return ":".join(self.event_str(elem) for elem in event)
        return str(event)

    # 관측되었던 event 정보를 표로 표현
    # args = True : arguments를 headers로 표현
    # color = True : 색깔 사용
    def event_table_text(self, *, args: bool = False, color: bool = False) -> str:
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

    # event table을 Markdown 형태로 반환
    def event_table(self, **_args: Any) -> Any:
        return Markdown(self.event_table_text(**_args))
    
    # FAIL과 관련된 Collector 객체들을 리스트로 반환
    def fail_collectors(self) -> List[Collector]:
        return self.collectors[self.FAIL]
    
    # 해당 event로 실패했던 event의 value를 반환
    def failed_fraction(self, event: Any) -> float:
        return self.event_fraction(event, self.FAIL)
    
    # entry function을 반환하는 메소드
    def function(self) -> Optional[Callable]:
        names_seen = set()
        functions = []
        for outcome in self.collectors:
            for collector in self.collectors[outcome]:
                func = collector.function()
                if func.__name__ not in names_seen:
                    functions.append(func)
                    names_seen.add(func.__name__)

        if len(functions) != 1:
            return None  # ambiguous
        return functions[0]

    # 색상 정보를 실수 형태로 반환 (0 : red, 1 : green)
    def hue(self, event: Any) -> Optional[float]:
        passed = self.passed_fraction(event)
        failed = self.failed_fraction(event)
        if passed + failed > 0:
            return passed / (passed + failed)
        else:
            return None
    
    # 실패한 events의 집합만을 반환
    def only_fail_events(self) -> Set[Any]:        
        return self.all_fail_events() - self.all_pass_events()

    # 성공한 events의 집합만을 반환
    def only_pass_events(self) -> Set[Any]:
        return self.all_pass_events() - self.all_fail_events()
    
    # 해당 event로 성공했던 event의 value를 반환
    def passed_fraction(self, event: Any) -> float:
        return self.event_fraction(event, self.PASS)
    
    # 성공과 관련된 Collector 객체의 리스트를 반환
    def pass_collectors(self) -> List[Collector]:
        return self.collectors[self.PASS]
    
    # 의심도를 % 형태로 변환하여 반환
    def percentage(self, event: Any) -> str:
        suspiciousness = self.suspiciousness(event)
        
        if suspiciousness is not None:
            return str(int(suspiciousness * 100)).rjust(3) + '%'
        else:
            return ' ' * len('100%')
    
    # (function name, line number)의 리스트를 의심도를 기준으로 내림차 순 정렬 후, 반환
    def rank(self) -> List[Any]:
        def susp(event: Any) -> float:
            suspiciousness = self.suspiciousness(event)
            assert suspiciousness is not None
            return suspiciousness

        events = list(self.all_events())
        events.sort(key=susp, reverse=True)  # hue 정보를 기준으로 내림차순 정렬
        
        return events
    
    # 대응되는 event의 의심 정보를 0 ~ 1 사이로 반환 (human readable)
    def suspiciousness(self, event: Any) -> Optional[float]:
        hue = self.hue(event)
        if hue is None:
            return None
        return 1 - hue
    
    # 대응되는 event의 의심 정도를 %로 반환 (human readable)
    def tooltip(self, event: Any) -> str:
        return self.percentage(event)
