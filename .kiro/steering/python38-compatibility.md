---
description: Python 3.8 compatibility — forbidden constructs, type hints, vendor libraries
inclusion: auto
fileMatchPattern: "**/*.py"
---

# Python 3.8 Compatibility Guidelines

## Critically Important

The addon must be compatible with Python 3.8 (Kodi 19.4+)

## Forbidden Constructs

### 1. Modern type syntax (PEP 585)

❌ **DO NOT use:**
```python
def get_items() -> list[str]:
    items: dict[str, int] = {}
    return list(items.keys())
```

✅ **Use instead:**
```python
from typing import List, Dict

def get_items() -> List[str]:
    items: Dict[str, int] = {}
    return list(items.keys())
```

### 2. Union operator for types (PEP 604)

❌ **DO NOT use:**
```python
def process(value: str | None) -> int | str:
    pass
```

✅ **Use instead:**
```python
from typing import Optional, Union

def process(value: Optional[str]) -> Union[int, str]:
    pass
```

### 3. Walrus operator in comprehensions

❌ **Be careful with:**
```python
# Works in 3.8, but can be problematic
[y := x + 1 for x in range(10)]
```

✅ **Safer approach:**
```python
result = []
for x in range(10):
    y = x + 1
    result.append(y)
```

## Vendor Libraries

### Compatibility Check

When adding/updating libraries in `resources/lib/vendor/`:

1. Check the minimum Python version in the documentation
2. Ensure the library supports Python 3.8
3. Avoid versions that use PEP 585 syntax

### urllib3 — special case

- ✅ Use: `urllib3 < 2.0` (e.g. 1.26.20)
- ❌ Avoid: `urllib3 >= 2.0` (incompatible with Python 3.8)

### requests

- ✅ Use: `requests >= 2.25.0, < 3.0`
- Will automatically pull the correct urllib3 version

## Testing

### Creating a Python 3.8 venv (optional)

For compatibility checking during development:

```bash
# If Python 3.8 is available
python3.8 -m venv venv38
source venv38/bin/activate
pip install -r requirements.txt

# Run tests
python3 test_urllib3_import.py
python3 test_new_api_client.py
```

### Required Tests

Before committing, always run:
```bash
source .venv/bin/activate
python3 -m pytest tests/ --tb=short
```

## Common Errors

### TypeError: 'type' object is not subscriptable

**Cause:** Using `list[str]` instead of `List[str]`

**Solution:** Import types from `typing`:
```python
from typing import List, Dict, Optional, Union, Tuple
```

### ImportError: cannot import name 'Literal'

**Cause:** `Literal` was added in Python 3.8, but may be missing in older typing versions

**Solution:** Use `typing_extensions` or avoid `Literal`

## Code Review Checklist

When reviewing code, check:
- [ ] No usage of `list[str]`, `dict[str, int]`, etc.
- [ ] No usage of `str | None`, `int | str`, etc.
- [ ] All types imported from `typing`
- [ ] Vendor libraries are compatible with Python 3.8

## References

- [PEP 585 - Type Hinting Generics In Standard Collections](https://peps.python.org/pep-0585/) — available from Python 3.9+
- [PEP 604 - Allow writing union types as X | Y](https://peps.python.org/pep-0604/) — available from Python 3.10+
- [typing module documentation](https://docs.python.org/3.8/library/typing.html) — for Python 3.8
