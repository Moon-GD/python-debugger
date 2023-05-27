def rich_output() -> bool:
    try:
        get_ipython()  # type: ignore
        rich = True
    except NameError:
        rich = False

    return rich

def getsourcelines(function: Any) -> Tuple[List[str], int]:
    """A replacement for inspect.getsourcelines(), but with syntax highlighting"""
    import inspect
    
    source_lines, starting_line_number = \
       inspect.getsourcelines(function)
       
    if not rich_output():
        return source_lines, starting_line_number
        
    from pygments import highlight, lexers, formatters
    from pygments.lexers import get_lexer_for_filename
    
    lexer = get_lexer_for_filename('.py')
    colorful_content = highlight(
        "".join(source_lines), lexer,
        formatters.TerminalFormatter())
    content = colorful_content.strip()
    return [line + '\n' for line in content.split('\n')], starting_line_number

def code_with_coverage(function: Callable, coverage: Coverage) -> None:
    source_lines, starting_line_number = \
       getsourcelines(function)

    line_number = starting_line_number
    for line in source_lines:
        marker = '*' if (function, line_number) in coverage else ' '
        print(f"{line_number:4} {marker} {line}", end='')
        line_number += 1
