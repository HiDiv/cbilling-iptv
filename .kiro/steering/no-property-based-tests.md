# No Property-Based Testing

## Rule

**DO NOT plan or include property-based tests (PBT) in specs related to testing.**

When creating or updating spec documents (requirements, design, tasks) that involve testing:
- Do not add Hypothesis, QuickCheck, or any PBT library as a dependency
- Do not create `Correctness Properties` sections that imply PBT implementation
- Do not plan `test_*_props.py` files
- Use standard pytest tests with positive, negative, and boundary scenarios instead

## Testing Approach

This project uses **example-based testing** with pytest:
- Positive scenarios (happy path)
- Negative scenarios (error conditions, invalid input)
- Boundary scenarios (edge cases, empty values, max lengths)

This provides sufficient coverage without the complexity of PBT.

## Exception

Property-based testing MAY be considered ONLY if:
- The code implements a complex algorithm with mathematical invariants (e.g., serialization/deserialization roundtrip, sorting, encoding)
- Manual enumeration of edge cases is demonstrably insufficient (hundreds of possible input combinations)
- The user explicitly requests PBT

In such cases, **ask the user first** before adding PBT to the spec.
