# Code Smells

## 1. Overview

A **Code Smell** is a structural pattern that signals poor maintainability. The term was coined by Kent Beck and cataloged by Martin Fowler in *Refactoring* (1999), chapter 3, "Bad Smells in Code" — a smell is **not a provable defect**: it is a heuristic, "a surface indication that usually corresponds to a deeper problem in the system".

CodeInsight curates **10 smells**, each implemented as **one hand-written AST rule** (plus the standard `tokenize` module for the comment-based rule) with a documented definition, a threshold (where applicable) and a cited reference. The engine is CodeInsight's own — it is **not** delegated to any library, and pylint/Ruff/SonarQube serve as **references only**, never as runtime or test dependencies (ADR-0002).

Code Smells is an **independent metric**: each smell is computed from a single file's AST alone (except the cross-file reference set of Dead Function), so it is applicable at any scope and reports `completeness: full` on every parsed file (ADR-0001). Findings are counted per file and per smell with locations and the reason each rule fired, so the result is actionable rather than a bare number.

## 2. Code Smells vs Rule Violations

CodeInsight distinguishes two Code Health signals (vocabulary pinned in [CONTEXT.md](../CONTEXT.md)):

> **Rule Violation** — A finding from a lint or security tool (Ruff, Bandit). Distinct from a Code Smell.
>
> **Code Smell** — A structural pattern of poor maintainability detected by curated heuristics (long method, god class, …), each documented against Clean Code or an official reference. Distinct from a Rule Violation.

- **Provability:** a Rule Violation is objective relative to a tool's rule set (Ruff's E722 either fires or not); a Code Smell is a subjective heuristic — two competent engineers can disagree about whether a 40-line method smells, but not about whether a file fails E722.
- **Tooling:** Rule Violations come from external tools (Ruff/Bandit); Code Smells come from CodeInsight's own AST engine with CodeInsight's own thresholds. This mirrors SonarQube's issue taxonomy, where a Code Smell is a maintainability issue distinct from a Bug (correctness) and a Vulnerability (security).
- **Coexistence:** a file can have zero Rule Violations and still smell; it can have Rule Violations and no smells. The outputs are never merged.

## 3. The 10 Smells

Each smell lists its **Definition** (with the CodeInsight rule), **Why it hurts**, **Threshold in CodeInsight** (configurable constants, `code_smells.py:142-150`) and **Reference**. Detection is dispatched in `_analyze_file` (`code_smells.py:299-323`); every finding is built by `_smell` → `{type, lineno, endline, message, entity, entity_type, class_name}` (`code_smells.py:1109-1131`), with `entity_type` ∈ {function, method, class, variable, parameter, except, block} and `class_name` = the containing class for methods (`_function_entity`, `code_smells.py:333-348`).

### 3.1 Long Method

**Definition.** A function or method whose body exceeds `MAX_METHOD_LINES` lines. Body = the function's own statement span (docstring excluded): `statements[-1].end_lineno - statements[0].lineno + 1` (`code_smells.py:421-451`; helper `_body_statements` `:1016-1025`). Nested functions are separate candidates.

**Why it hurts.** Long methods hide multiple responsibilities and are the primary target of Fowler's Extract Method refactoring.

**Threshold.** `MAX_METHOD_LINES = 30` (fires when `lines > 30`).

**Reference.** Fowler, *Refactoring* ch. 3 (Long Method); *Clean Code*, 2008, ch. 3 ("Functions should hardly ever be 20 lines long"). Tool note: SonarQube S138 (line-based function size) is not implemented for Python; pylint's R0915 counts statements, not lines.

### 3.2 Large/God Class

**Definition.** A class whose body exceeds `MAX_CLASS_LINES` lines **or** which defines more than `MAX_CLASS_METHODS` methods — reasons joined with `"; "` (`code_smells.py:453-501`). "God class" is the extreme form (Riel's heuristic: a class that "monopolizes the data and/or behavior of the system").

**Why it hurts.** A class trying to do too much accumulates state and behavior, becoming impossible to test in isolation — Fowler's **Large Class**.

**Threshold.** `MAX_CLASS_LINES = 200` **or** `MAX_CLASS_METHODS = 15`.

**Reference.** Fowler, *Refactoring* ch. 3 (Large Class); Riel, *Object-Oriented Design Heuristics*, 1996 (god class). SonarQube has no direct class-size rule for Python (closest: S1200 coupling, S3776 cognitive complexity).

### 3.3 Deep Nesting

**Definition.** A function or method whose maximum nesting depth exceeds `MAX_NESTING_DEPTH`. Nesting counts control-flow and block constructs (`if`/`elif`/`else`, `for`, `while`, `try`/`except`/`finally`, `with`, `match`/`case`) as they nest — the function body is level 1, an `if` inside it level 2, etc. Walked via `_block_bodies` (`code_smells.py:33-74`); computation `code_smells.py:503-544`.

**Why it hurts.** Deeply nested code is hard to read and test; each level adds a precondition the reader must hold in mind ("arrow" anti-pattern).

**Threshold.** `MAX_NESTING_DEPTH = 4` — matches SonarQube S134's default exactly.

**Reference.** *Clean Code* ch. 3 (indentation "should not be greater than one or two"); SonarQube S134; pylint R1702 (`too-many-nested-blocks`, default 5).

### 3.4 Long Parameter List

**Definition.** A function or method with more than `MAX_PARAMETERS` parameters (posonly + args + kwonly; vararg/kwarg not counted; leading `self`/`cls` dropped) (`code_smells.py:546-579`).

**Why it hurts.** Long parameter lists are hard to read and easy to call with arguments in the wrong order; Fowler's fix is **Introduce Parameter Object**.

**Threshold.** `MAX_PARAMETERS = 5` (fires at more than 5) — matches pylint's `max-args=5` default exactly.

**Reference.** Fowler, *Refactoring* ch. 3 (Long Parameter List); *Clean Code* ch. 3 (0–2 ideal, avoid 3, justify > 3); pylint R0913.

### 3.5 Data Class

**Definition.** A class with at least `MIN_DATA_CLASS_FIELDS` fields and **no methods** (other than implicit dunder machinery). Fields = class-level data assignments (`Assign`/`AnnAssign`, `_collect_data_field` `code_smells.py:1086-1095`) **plus** `self.x` instance attributes assigned in `__init__` (`_collect_instance_field` `:1097-1107`; lambdas excluded) (`code_smells.py:581-661`).

**Why it hurts.** A data holder with no behavior is usually a sign that the behavior was placed elsewhere (the related **Feature Envy** smell) — "dumb data" other classes reach into.

**Threshold.** `MIN_DATA_CLASS_FIELDS = 3` (fires at ≥ 3 fields and no methods).

**Reference.** Fowler, *Refactoring* ch. 3 (Data Class). SonarQube has no data-class detector for Python.

### 3.6 Searchable Names

**Definition.** A local variable or function parameter whose name is a **single letter**, excluding the conventional set: loop counters (`i`/`j`/`k`), coordinates (`x`/`y`/`z`), the exception name (`e`), throwaway `_` (and `self`/`cls`/dunders, which are never single letters anyway). Per function: parameters plus local bindings (`_scope_bindings` = Store-`Name` + `ExceptHandler` names, minus nested scopes' bindings, `code_smells.py:776-799`); fires per offending name (`code_smells.py:688-774`). **No threshold** — binary per name.

**Why it hurts.** A single-letter name is nearly impossible to search for and carries no meaning — the reader must re-derive what the value *is* from its usage.

**Reference.** SonarQube S117 (single-letter names); pylint `invalid-name` C0103 with `good-names` exclusions (basis of the exclusion set). Exclusion set: `SINGLE_LETTER_EXCEPTIONS = {i, j, k, x, y, z, e, _}` (`code_smells.py:150`).

### 3.7 Commented-Out Code

**Definition.** A run of **consecutive comment lines** whose content, after removing the comment markers, **parses as valid Python** and carries a **code-like syntax signal** (structural prefixes or any of `= ( [ { @ ->`, `_looks_like_code` `code_smells.py:1066-1084`). Directives are never flagged: shebangs, coding declarations, `type: ignore`, and tool pragmas (`# noqa`, `# pylint:`, `# ruff:`, `# fmt:`, `# mypy:` — `_is_comment_directive` `:1040-1064`). Consecutive qualifying lines count as **one** finding. Detection via `tokenize.generate_tokens` runs grouped by consecutive line numbers (`code_smells.py:816-845`); dedented run must `compile()` cleanly (`code_smells.py:801-907`). **No threshold.**

**Why it hurts.** Commented-out code is dead weight that confuses the reader and silently rots out of date with the APIs it used.

**Reference.** SonarQube S125 ("Sections of code should not be commented out").

### 3.8 Dead Function

**Definition.** A function or method whose name is **never referenced anywhere in the analyzed file set**: not called, not passed as a callback, not used as a decorator, not reached through attribute access (`self.x()`, `ClassName.x()`) and not invoked from an `if __name__ == "__main__"` entry point. Recursion counts as usage. Dunder methods excluded. Fires when `node.name not in referenced_names`, where `referenced_names` = every `Name.id` + `Attribute.attr` in **all analyzed files** (`_collect_references`, `code_smells.py:239-267`; rule `code_smells.py:909-941`). **No threshold.**

**Scope note (ADR-0001).** The rule is whole-analyzed-file-set by nature. At `project` scope every uploaded file is analyzed, so the claim is reliable; at `single_file` scope a function may be used by files outside the analysis — reported with the input `scope`, never a claim about unanalyzed files.

**Why it hurts.** Dead functions promise behavior nothing exercises and hide the module's real surface area.

**Reference.** SonarQube S1144 ("Unused private methods should be removed") — CodeInsight deliberately diverges: S1144 covers *private* methods only, CodeInsight reports any unreferenced function in the analyzed set and documents the single-file limitation instead.

### 3.9 Bare Except

**Definition.** An `except:` clause with no exception type (and no type bound via `as`). Fires when `handler.type is None` (`code_smells.py:663-686`); `except ValueError:` never fires. **No threshold.**

**Why it hurts.** A bare `except:` catches *everything*, including `KeyboardInterrupt` and `SystemExit`, masking real programming errors and making a program impossible to interrupt cleanly.

**Reference.** Python official tutorial (Errors and Exceptions: "Use this with extreme caution, since it is easy to mask a real programming error!"); *Clean Code* ch. 7; pylint W0702 / Ruff E722.

### 3.10 Empty Block

**Definition.** A block — function, `if`/`elif`/`else`, loop, `try`/`except`/`finally`, `with`, `class` — whose body is empty, i.e. contains only placeholder statements (`pass` or `...`), optionally preceded by a docstring. Every body of FunctionDef/AsyncFunctionDef/ClassDef/If/For/AsyncFor/While/With/AsyncWith (+ `orelse`), Try (body/orelse/finalbody/handlers), Match (cases); `_is_empty` `code_smells.py:1027-1038`; `_is_placeholder` `:22-30` (`code_smells.py:943-1012`). **No threshold.**

**Why it hurts.** An empty block is unfinished or silently dropped behavior: an empty `except:` swallows errors, an empty branch hides a decision never implemented, an empty function body is a stub.

**Reference.** SonarQube S108 ("Nested blocks of code should not be left empty") — typed by SonarQube itself as a **Code Smell**. Related but inverse: Ruff PIE790 (`unnecessary-pass`) flags *redundant* placeholders; this rule flags *necessary-but-empty* ones.

## 4. Threshold Calibration

The thresholds are deliberate, documented values anchored to the references, and they are **configurable constants** in the engine (`code_smells.py:142-150`):

- **Long Method (30 lines)** — looser than Clean Code's ~20 because it counts the whole body span; project convention, no tool default for Python lines.
- **Large/God Class (200 lines / 15 methods)** — project convention; no tool default exists for Python class size.
- **Deep Nesting (4)** — matches SonarQube S134's default exactly (pylint/Ruff default to 5).
- **Long Parameter List (5)** — `> 5` matches pylint `max-args=5` exactly; Clean Code's 0–2 ideal is deliberately not enforced.
- **Data Class (3 fields)** — project convention; Fowler gives no numeric rule.
- **Searchable Names / Commented-Out Code / Dead Function / Bare Except / Empty Block** — no thresholds; the references define the condition without a size bound.

## 5. Implementation Basis: Manual (no library)

All 10 rules are **hand-implemented directly on the Python standard library** — `ast` for 9 rules, plus `tokenize` for Commented-Out Code; the only imports are `ast, io, textwrap, tokenize, Path` (`code_smells.py:1-5`).

There is **no maintained Python library that implements this curated set of 10 smells**:

- **`radon`** — no smell detection of any kind (raw metrics, cyclomatic complexity, Halstead, Maintainability Index only).
- **`pylint`** — overlaps partially (R0913, R0915, R1702, W0702, W0107, C0103) but they are lint findings with pylint's thresholds/semantics: no god-class, no data-class, no dead-function, no empty-block-as-placeholder rules.
- **`ruff`** — mirrors the pylint refactor messages and E722, PIE790, but the same limitation applies; per CONTEXT.md Ruff output belongs to the Rule Violations metric, not Code Smells.

Conclusion: **a custom AST engine is required** — keeping CodeInsight standalone and hermetic per ADR-0002.

## 6. Documented Divergences

- **Thresholds vs Clean Code.** `MAX_METHOD_LINES = 30` vs Clean Code's "hardly ever 20"; `MAX_PARAMETERS = 5` vs the 0–2 ideal — treated as project conventions, not enforced ideals.
- **Long Method is line-based; the tools are statement-based.** pylint R0915 counts statements (default 50); CodeInsight counts body lines — values not directly comparable.
- **No SonarQube size rule for classes.** God classes are addressed by SonarQube through coupling (S1200) and cognitive complexity (S3776), not size.
- **Magic Number removed by decision.** The original set included a Magic Number rule (Clean Code G25); per `.scratch/code-health/issues/08-revise-code-smells-catalog.md` it was **removed and replaced by three rules** (Searchable Names, Commented-Out Code, Dead Function — one-for-three, not pairwise). Bare literals are no longer a Code Smell finding (they remain visible as Ruff lint findings in Rule Violations).
- **Searchable Names scope.** Matches SonarQube S117 (local variables and parameters) and adopts pylint's `good-names` exclusion set; module-level/function/class names deliberately not covered.
- **Commented-Out Code is a heuristic.** Parse-based (the comment run must compile) plus a code-like signal, which keeps prose and directives out of the count; the trade-off is documented (fragments that do not parse on their own are missed; prose that happens to parse is flagged).
- **Dead Function scope vs S1144.** S1144 covers unused *private* methods only (safe at any scope); CodeInsight reports any unreferenced function/method in the analyzed set, so at `single_file` scope a function used by an unanalyzed file is reported dead — a documented false-positive direction, reported honestly via the input `scope` (ADR-0001).
- **Empty Block vs PIE790.** Ruff flags *redundant* `pass`; CodeInsight flags *necessary* placeholders that signal emptiness — near-complements; S108 is the matching reference.
- **Data Class definition.** Fowler's includes classes with getters/setters "and nothing else"; CodeInsight's rule is stricter (≥ 3 fields, no methods at all).

## 7. Unit Tests

`backend/analysis/test/test_code_smells.py` (1223 lines) — hand-computed fixtures, no external tools ever invoked (ADR-0002). Per-rule fires / near-threshold non-fires:

- **LongMethodTest** (`:50-102`): fires at 31-line body, not 30; nested function is a separate candidate.
- **LargeClassTest** (`:105-171`): fires at 201 lines / 16 methods; not at 200 / 15.
- **DeepNestingTest** (`:174-226`): fires at depth 5, not 4; `else` branch counts.
- **LongParameterListTest** (`:229-275`): fires at 6 params, not 5; `self` not counted; `self`+6 fires.
- **DataClassTest** (`:278-341`): 3 class-level fields fire; 2 don't; a method suppresses; 3 `self.x` fields in `__init__` fire.
- **BareExceptTest** (`:343-373`): bare fires; `except ValueError:` doesn't.
- **EmptyBlockTest** (`:376-432`): `pass`-only, docstring+`pass`, `...`, empty `if` branch fire; docstring+code and real code don't.
- **SearchableNamesTest** (`:435-583`): single-letter param/local fire with `entity`/`entity_type`/`lineno`; loop counter `i`, exception `e`, `self` excluded; nested-scope names not counted as outer locals.
- **CommentedOutCodeTest** (`:585-689`): commented assignment and `def` block fire; prose and URLs don't; all directives (shebang, coding, noqa, `type: ignore`) excluded; consecutive lines = 1 finding; entity resolves to enclosing function.
- **DeadFunctionTest** (`:692-835`): unused fires with entity/entity_type/class_name; called, recursion, `__main__` entry, `self.x()` usage and **cross-file usage** (two temp files, `:810-835`) don't; dunders excluded.
- **EntityFieldsTest** (`:838-1029`): pins `entity`/`entity_type`/`class_name` for every rule across function/method/class/module contexts.
- **CodeSmellsEngineTest** (`:1032-1197`): clean file → zero + `completeness: full` + scope echoed; aggregation `by_type`; unparsable file → `completeness: partial` with `reason`, no fabricated counts; `calculate([])` → 0; thresholds configurable via constructor; registered in `ENGINE_REGISTRY`.
- **CodeSmellsMetricSeedTest** (`:1200-1223`): `MetricDefinition` row seeded.

The cross-engine detail contract (`test_detail_contract.py:104-123, 220-268`) pins the record shape for every smell: `type/lineno/endline/message/entity/entity_type/class_name`; `class_name` required for methods, `None` otherwise; `endline >= lineno`.

## 8. References

- Robert C. Martin, *Clean Code*, Prentice Hall, 2008 — [publisher page](https://www.informit.com/store/clean-code-a-handbook-of-agile-software-craftsmanship-9780132350884)
- Martin Fowler, *Refactoring: Improving the Design of Existing Code*, Addison-Wesley, 1999, ch. 3 "Bad Smells in Code"
- Arthur J. Riel, *Object-Oriented Design Heuristics*, Addison-Wesley, 1996
- SonarQube rules: [S117](https://rules.sonarsource.com/python/RSPEC-117/), [S125](https://rules.sonarsource.com/python/RSPEC-125/), [S1144](https://rules.sonarsource.com/python/RSPEC-1144/), [S108](https://rules.sonarsource.com/python/rspec-108/), [S134](https://rules.sonarsource.com/cpp/RSPEC-134/), [S138](https://rules.sonarsource.com/javascript/RSPEC-138/)
- pylint: [R0913](https://pylint.pycqa.org/en/stable/user_guide/messages/refactor/too-many-arguments.html), [R0915](https://pylint.pycqa.org/en/stable/user_guide/messages/refactor/too-many-statements.html), [R1702](https://pylint.readthedocs.io/en/v4.0.4/user_guide/messages/refactor/too-many-nested-blocks.html), [W0702](https://pylint.readthedocs.io/en/v2.17.7/user_guide/messages/warning/bare-except.html), [C0103](https://pylint.readthedocs.io/en/stable/user_guide/messages/convention/invalid-name.html)
- Ruff: [rules index](https://docs.astral.sh/ruff/rules/), [E722](https://docs.astral.sh/ruff/rules/bare-except/), [PIE790](https://docs.astral.sh/ruff/rules/unnecessary-placeholder/)
- Python tutorial — Errors and Exceptions: [docs.python.org](https://docs.python.org/3/tutorial/errors.html)
- Radon — metric set (no smells): [radon.readthedocs.io](https://radon.readthedocs.io/en/stable/intro.html)
- CodeInsight — [CONTEXT.md](../CONTEXT.md); ADR-0001 [`docs/adr/0001-metric-scope-completeness-contract.md`](adr/0001-metric-scope-completeness-contract.md); ADR-0002 [`docs/adr/0002-standalone-analyzer-no-external-dependency.md`](adr/0002-standalone-analyzer-no-external-dependency.md); decision doc `.scratch/code-health/issues/08-revise-code-smells-catalog.md`
- Engine: `backend/analysis/engines/code_smells.py` · Tests: `backend/analysis/test/test_code_smells.py`
- Registration: `MetricDefinition` key `CODE_SMELLS`, display name "Code Smells", category "Code Health" (`backend/analysis/migrations/0007_seed_code_smells.py:11-26`)
