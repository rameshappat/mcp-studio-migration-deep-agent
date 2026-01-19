#!/usr/bin/env python3
"""Test improved file parsing regex with edge cases."""

import re

# Test sample with nested code blocks
sample_with_nested = """
### FILE: README.md
```markdown
# My Project

Example code block:
```python
print("hello")
```

More text here.
```

### FILE: src/app.py
```python
def main():
    code = '''
    Some multi-line
    string content
    '''
    return code
```

### FILE: requirements.txt
```text
fastapi==0.104.1
uvicorn==0.24.0
```
"""

# Improved regex
file_pattern = r'###\s*FILE:\s*([^\n]+)\s*\n```[^\n]*\n(.*?)(?=\n###\s*FILE:|\Z)'
files = re.findall(file_pattern, sample_with_nested, re.DOTALL)

# Clean up trailing ```
cleaned_files = []
for path, content in files:
    content = content.strip()
    if content.endswith('```'):
        content = content[:-3].strip()
    cleaned_files.append((path, content))

print(f"Found {len(cleaned_files)} files:\n")

for i, (path, content) in enumerate(cleaned_files, 1):
    print(f"{i}. {path}")
    print(f"   Length: {len(content)} chars")
    print(f"   Content:")
    print(f"   {repr(content[:150])}...")
    print()

# Validate
assert len(cleaned_files) == 3, f"Expected 3 files, got {len(cleaned_files)}"
assert cleaned_files[0][0].strip() == "README.md"
assert "```python" in cleaned_files[0][1], "README should contain nested code block"
assert "print(" in cleaned_files[0][1], "README should contain nested python code"
assert cleaned_files[1][0].strip() == "src/app.py"
assert "def main():" in cleaned_files[1][1]
assert cleaned_files[2][0].strip() == "requirements.txt"
assert "fastapi" in cleaned_files[2][1]

print("✅ All edge case tests passed!")
