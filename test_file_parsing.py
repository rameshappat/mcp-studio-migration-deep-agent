#!/usr/bin/env python3
"""Test file parsing regex to ensure it extracts code correctly."""

import re

# Test sample output that LLM might generate
sample_output = """Here's the implementation:

### FILE: README.md
```markdown
# My Project

This is a real project.
```

### FILE: src/main.py
```python
#!/usr/bin/env python3
import sys

def main():
    print("Hello World")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### FILE: requirements.txt
```text
fastapi==0.104.1
uvicorn==0.24.0
```

That's all the files!
"""

# Test the regex pattern
file_pattern = r'###\s*FILE:\s*([^\n]+)\s*\n```[^\n]*\n(.*?)\n```'
files = re.findall(file_pattern, sample_output, re.DOTALL | re.MULTILINE)

print(f"Found {len(files)} files:\n")

for i, (path, content) in enumerate(files, 1):
    print(f"{i}. {path}")
    print(f"   Length: {len(content)} chars")
    print(f"   Preview: {content[:80]}...")
    print()

# Validate
assert len(files) == 3, f"Expected 3 files, got {len(files)}"
assert files[0][0].strip() == "README.md"
assert files[1][0].strip() == "src/main.py"
assert files[2][0].strip() == "requirements.txt"
assert "Hello World" in files[1][1]
assert "fastapi" in files[2][1]

print("✅ All regex tests passed!")
