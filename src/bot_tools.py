"""
Tools for the agents to use.

DO NOT PUT ANYTHING HERE THAT IS NOT SAFE FOR THE AGENT TO USE.
ALSO CAN'T HAVE CALLABLE MODULES.
"""

import os
import sys

src_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.dirname(src_dir)

token_threshold = 100_000


def get_local_repo_path(repo_name: str) -> str:
    """
    Get the path to the local repository

    Args:
        - repo_name : Name of repository (owner/repo)
            - Example: "openai/autogen"

    Returns:
        - Path to the local repository
    """
    repo_name_split = repo_name.split('/')
    repo_path = os.path.join(base_dir, 'repos', repo_name_split[0], repo_name_split[1])  # Use base_dir
    if os.path.exists(repo_path):
        return repo_path
    else:
        return f"Repository {repo_name} not found @ {repo_path}"


def search_for_pattern(
        search_dir: str,
        pattern: str,
) -> str:
    """
    Search for a pattern in a directory.
    Can only search for python files.

    Inputs:
        - search_dir : Directory to search
        - pattern : Pattern to search for

    Returns:
        - Path to files with pattern
    """
    run_str = f"grep -irl {pattern} {search_dir} --include='*.py'"
    print(run_str)
    # out = os.system(run_str)
    out = os.popen(run_str).read()
    return out


def search_for_file(
        directory: str,
        filename: str,
) -> str:
    """Search for a file in a directory
    Inputs:
        - Directory : Path to directory
        - Filename : Name of file

    Returns:
        - Path to file
    """
    run_str = f"find {directory} -iname '*{filename}*'"
    print(run_str)
    # out = os.system(run_str)
    out = os.popen(run_str).read()
    if out:
        return out
    else:
        return "File not found"


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in text by splitting on whitespace

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    return len(text.split())


def readfile(
        filepath: str,
) -> str:
    """Read a file and return its contents with line numbers.
    Will return partial content if token threshold is exceeded.

    Args:
        filepath: Path to file to read

    Returns:
        Tuple of:
        - File contents with line numbers (may be truncated if exceeds threshold)
        - Warning message if content was truncated, None otherwise

    Example:
        content, warning = readfile("myfile.py")
        if warning:
            print(warning)  # Shows truncation message
        print(content)  # Shows numbered lines
    """
    try:
        with open(filepath, 'r') as file:
            data = file.readlines()
    except FileNotFoundError:
        return f"File not found: {filepath}"
    except Exception as e:
        return f"Error reading file {filepath}: {str(e)}"

    # Add line numbers
    numbered_lines = [f"{i:04}: {line}" for i, line in enumerate(data)]

    # Check total tokens
    full_content = "".join(numbered_lines)
    total_tokens = estimate_tokens(full_content)

    if total_tokens <= token_threshold:
        return full_content

    # If over threshold, include as many lines as possible
    current_tokens = 0
    included_lines = []

    for line in numbered_lines:
        line_tokens = estimate_tokens(line)
        if current_tokens + line_tokens > token_threshold:
            break
        included_lines.append(line)
        current_tokens += line_tokens

    warning = (f"File exceeds token threshold of {token_threshold}. "
               f"Showing {len(included_lines)} of {len(data)} lines "
               f"({current_tokens}/{total_tokens} tokens). "
               f"Use readlines({filepath}, start_line, end_line) "
               f"to read specific ranges.")

    data = "".join(included_lines)
    data += f"\n\n{warning}"

    return data


def readlines(
        file_path: str,
        start_line: int,
        end_line: int,
) -> str:
    """
    Read lines from a file

    Inputs:
        - file_path : Path to file
        - start_line : Start line
        - end_line : End line

    Returns:
        - Lines from file
    """
    with open(file_path, 'r') as file:
        lines = file.readlines()

    lines = lines[start_line:end_line]

    # Add line numbers
    numbered_lines = [f"{i+start_line:04}: {line}" for i,
                      line in enumerate(lines)]

    # Check total tokens
    full_content = "".join(numbered_lines)
    total_tokens = estimate_tokens(full_content)

    if total_tokens <= token_threshold:
        return full_content

    # If over threshold, include as many lines as possible
    current_tokens = 0
    included_lines = []

    for line in numbered_lines:
        line_tokens = estimate_tokens(line)
        if current_tokens + line_tokens > token_threshold:
            break
        included_lines.append(line)
        current_tokens += line_tokens

    n_included = len(included_lines)

    warning = (f"Selected lines exceed token threshold of {token_threshold}. "
               f"Showing lines {start_line} to {start_line + n_included} "
               f"({current_tokens}/{total_tokens} tokens). "
               f"Use readlines({file_path}, start_line, end_line) "
               f"to read specific ranges.")

    data = "".join(included_lines)
    data += f"\n\n{warning}"

    return data


def get_func_code(
        module_path: str,
        func_name: str,
) -> str:
    """Use simple search to get the code for a function

    Inputs:
        - module_path : Path to module
        - func_name : Name of function

    Returns:
        - Code for function
    """

    with open(module_path, 'r') as file:
        lines = file.readlines()

    # Find all function definitions
    import re
    match_pattern = re.compile(r'def\s+.*\(')
    func_defs = re.findall(match_pattern, "\n".join(lines))
    # Get line numbers for each function definition
    func_def_lines = [i for i, line in enumerate(
        lines) if match_pattern.findall(line)]
    func_def_line_map = {func_def_lines[i]: func_defs[i]
                         for i in range(len(func_defs))}

    # Find range of lines for wanted function
    for i, this_num in enumerate(func_def_lines):
        if func_name in func_def_line_map[this_num]:
            start_line = this_num
            try:
                end_line = func_def_lines[i+1] - 1
            except IndexError:
                end_line = len(lines)
            break

    # Get code for function
    code = "".join(lines[start_line:end_line])
    return code


def search_github(query: str) -> str:
    """
    Search GitHub for a given query and return code snippets.

    Args:
        query: The search query string.

    Returns:
        A string containing search results with code snippets.
    """
    # Import here to avoid circular imports
    sys.path.append(src_dir)
    from git_utils import perform_github_search

    return perform_github_search(query)
