# BioStatViz v0.1 Design

## 1. Goal

Build an independent, open-source scientific statistics and visualization toolkit for AI agents. BioStatViz should execute reproducible analyses through validated Python functions rather than relying on an LLM to invent statistical code or calculate results directly.

The v0.1 milestone focuses on small tabular biological datasets and a narrow but reliable workflow:

1. Read CSV/XLSX data.
2. Inspect structure and data quality.
3. Identify experimental design metadata needed for analysis.
4. Perform basic two-group statistical analysis.
5. Generate a publication-oriented scientific figure.
6. Expose validated operations through MCP stdio.
7. Provide Agent Skills that instruct a harness how and when to use the tools.
8. Verify behavior with unit tests, simulated data, and end-to-end agent tests.

## 2. Target environment

- OS: Windows as the primary local development environment
- Python: 3.11
- Package/environment manager: uv
- Testing: pytest
- Version control: Git
- Editor/agent environment: VS Code and/or Codex-compatible workflow
- MCP transport for v0.1: stdio
- License: MIT

## 3. Architecture

```text
BioStatViz
├── src/
│   └── biostatviz/
│       ├── __init__.py
│       ├── io/
│       ├── profiling/
│       ├── design/
│       ├── statistics/
│       ├── visualization/
│       └── mcp/
├── skills/
│   ├── experimental-design/
│   ├── statistical-analysis/
│   └── scientific-visualization/
├── tests/
│   ├── unit/
│   └── validation/
├── examples/
├── docs/
├── pyproject.toml
├── README.md
├── LICENSE
└── .gitignore
```

### 3.1 Layer boundaries

#### Core Python layer

Contains all deterministic analysis logic. It must be callable without MCP or any LLM.

#### MCP layer

Thin adapter layer. It validates tool arguments, calls core Python functions, and serializes results. It must not contain statistical decision logic that belongs in the core layer.

#### Skill layer

Contains agent-facing instructions about workflow and statistical reasoning. Skills do not calculate statistics. They tell the agent when to call tools and what information must be confirmed before analysis.

#### Validation layer

Contains unit tests and statistical validation datasets. Validation must test both software correctness and statistical behavior.

## 4. Module design

### Module 01: `io`

Responsibilities:

- Read `.csv` and `.xlsx` files.
- Validate path and supported extension.
- Return a pandas DataFrame plus minimal source metadata.
- Never silently modify user data during load.

Initial public interface:

```python
load_table(path: str, sheet_name: str | int | None = None) -> LoadedTable
```

Expected errors:

- file does not exist
- unsupported format
- unreadable/corrupt file
- requested Excel sheet does not exist

### Module 02: `profiling`

Responsibilities:

- Row/column counts
- Column names and dtypes
- Missing-value counts
- Unique-value counts
- Numeric summaries
- Candidate ID/group/numeric columns
- Basic warnings such as empty columns or duplicated row identifiers

Initial public interface:

```python
profile_dataset(df: pd.DataFrame) -> DatasetProfile
```

Profiling may suggest candidate roles but must not claim to know the experimental design with certainty.

### Module 03: `design`

Responsibilities:

Represent and validate the experimental design needed by downstream statistics.

v0.1 should model:

- response variable
- grouping variable
- experimental unit identifier, when available
- independent vs paired comparison
- biological vs technical replicate warning flags

Initial contract:

```python
ExperimentalDesign(
    response=...,
    group=...,
    paired=False,
    subject_id=None,
    replicate_type=None,
)
```

The module may validate a user/agent-supplied design, but v0.1 should not pretend that replicate type can always be inferred automatically from column names alone.

### Module 04: `statistics`

v0.1 scope:

- Two independent groups
- Two paired groups
- Descriptive group summaries
- Mean/median difference
- Confidence interval where appropriate
- Effect size
- P-value
- Assumption diagnostics needed for the selected method

Initial functions should be explicit rather than one opaque `auto_stats()` function.

Candidate interfaces:

```python
summarize_groups(...)
compare_two_groups(...)
```

Important design rule:

BioStatViz should not use the simplistic rule "Shapiro p > 0.05 means t-test, otherwise Mann-Whitney" as its sole decision procedure. Test choice must consider design first, then distributional/robustness considerations.

### Module 05: `visualization`

v0.1 scope:

- Two-group scientific comparison figure
- Raw observations visible
- Clearly defined summary overlay
- Export PNG and SVG
- Axis labels and group labels preserved
- No silent statistical annotations unless their source result is provided

Initial interface:

```python
plot_two_group_comparison(...)
```

Matplotlib is the primary backend for v0.1.

### Module 06: `mcp`

Transport: stdio.

Initial MCP tools:

1. `inspect_dataset`
2. `summarize_groups`
3. `compare_two_groups`
4. `create_two_group_plot`

`compare_multiple_groups` and `correlation_analysis` are deferred until the two-group path is validated end-to-end. This keeps the first release smaller than the earlier conceptual six-tool sketch.

MCP tools return structured JSON-compatible data. Plot tools return both file metadata and a local output path/resource reference appropriate to the host.

### Skill layer

#### `experimental-design`

Must require identification of:

- response variable
- group variable
- experimental unit
- independent vs paired design
- whether cell/field/technical measurements are nested under a smaller number of biological replicates

#### `statistical-analysis`

Must instruct the agent to:

- inspect data before testing
- respect experimental unit
- avoid pseudoreplication
- report sample sizes
- report effect size and confidence interval when available
- report test name, statistic, and p-value
- distinguish exploratory from confirmatory interpretation

#### `scientific-visualization`

Must instruct the agent to:

- show raw data when practical
- state what error bars represent
- avoid misleading axes
- use plot types compatible with the design
- preserve publication-quality export

## 5. Data flow

```text
User dataset
   ↓
IO load
   ↓
Dataset profile
   ↓
Experimental design specification/validation
   ↓
Statistical function
   ↓
Structured result
   ├── JSON-compatible analysis output
   └── visualization input
           ↓
        PNG/SVG
```

When used through an agent:

```text
User
 ↓
Harness / LLM
 ↓
Skill reasoning
 ↓
MCP tool call
 ↓
BioStatViz core
 ↓
Structured result
 ↓
Agent explanation
```

The LLM is responsible for orchestration and interpretation, not numerical computation.

## 6. Result schema principles

Statistical result objects should be machine-readable and stable. A two-group result should eventually include fields such as:

- analysis type
- test name
- group labels
- n per group
- descriptive summaries
- estimate/effect size
- confidence interval
- test statistic
- p-value
- assumptions/diagnostics
- warnings
- software/version metadata where useful

Exact field names will be finalized during Module 04 design before implementation.

## 7. Error handling

Errors should be explicit and typed where practical.

Examples:

- unsupported file format
- missing requested column
- non-numeric response
- fewer observations than required
- paired data without a valid pairing key
- ambiguous or unsafe experimental design

Statistical warnings must not be hidden. A result can be valid while carrying warnings.

## 8. Testing strategy

Every module is accepted only after passing three layers of testing where applicable.

### 8.1 Unit tests

Examples:

- valid CSV/XLSX load
- missing file
- invalid sheet
- missing values
- wrong dtype
- missing columns
- invalid paired design

### 8.2 Statistical validation tests

Use simulated datasets with known properties.

Examples:

- H0 data to estimate false-positive behavior
- known location shift to check power/effect direction
- unequal variance data
- non-normal data
- outliers
- missing observations

Validation tests are not expected to prove statistical optimality, but they must catch obviously wrong behavior.

### 8.3 End-to-end agent tests

For a small biological table, verify that the agent:

1. inspects the dataset first
2. identifies or asks for required design metadata
3. does not treat technical observations as independent biological replicates without justification
4. calls the validated statistical tool
5. does not fabricate numerical results
6. produces a figure consistent with the analyzed data

## 9. v0.1 acceptance scenario

Input example:

```csv
sample,group,gfp
WT1,WT,101
WT2,WT,98
WT3,WT,105
KO1,KO,142
KO2,KO,149
KO3,KO,145
```

BioStatViz v0.1 is successful when an agent can:

1. read the dataset
2. report its structure and quality
3. identify `group` as the grouping variable and `gfp` as a numeric response candidate
4. establish an independent two-group design for this example
5. execute an appropriate validated comparison
6. report n, effect estimate/effect size, confidence interval when supported, test statistic, and p-value
7. generate a scientific comparison plot containing the raw observations
8. save structured output without fabricating any statistics

## 10. Development sequence

1. Repository/package skeleton
2. Module 01: IO
3. Module 02: Profiling
4. Module 03: Experimental design
5. Module 04: Two-group statistics
6. Module 05: Scientific visualization
7. Module 06: MCP stdio adapter
8. Agent Skills
9. End-to-end DeepSeek/harness test
10. GitHub CI, README, release preparation

Each module is implemented, tested, reviewed, and committed before moving to the next.

## 11. Licensing and attribution

BioStatViz will use the MIT License.

External projects may be studied for architectural ideas, but code will not be copied unless license compatibility and attribution requirements are explicitly reviewed. BioStatViz should maintain its own implementation and documentation.

## 12. Key design decisions

- Independent repository, not a fork.
- Core logic is independent of any particular LLM or harness.
- MCP is an adapter, not the business/statistics logic layer.
- No unrestricted arbitrary Python execution in v0.1.
- Experimental design takes precedence over automated normality-test-driven method selection.
- Raw observations should be visible in the default two-group scientific figure.
- v0.1 deliberately validates the two-group path before expanding to multi-group and correlation analysis.
