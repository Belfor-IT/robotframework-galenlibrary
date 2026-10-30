# robotframework-galenframework

Robot Framework library for layout, responsive-design and visual regression testing, powered by
[Galen Framework](http://galenframework.com).

GalenLibrary checks the page that is **already open in SeleniumLibrary**. The Galen engine (Java)
attaches to the same WebDriver session, so it sees your logged-in state, cookies, the current
window size and any changes made earlier in the test.

Three ways to test, freely combined:

| Approach | Keywords | Good for |
|---|---|---|
| **Layout keywords** | `Element Should Be Below`, `Element Should Be Inside`, `Element Width Should Be`, ... | Targeted checks without learning Galen |
| **Baseline comparison** | `Element Should Match Baseline`, `Page Should Match Baseline` | Quick visual regression tests with a heatmap of differences |
| **Galen spec files** | `Check Layout` | Complete pages on several screen sizes in one `.gspec` file |

## Installation

```bash
pip install robotframework_galenframework-0.3.1-py3-none-any.whl
```

Requirements: Python 3.9+, Java 11+ (on `PATH` or via `JAVA_HOME`). SeleniumLibrary is installed
automatically. The Galen engine is bundled in the wheel.

The library is not on PyPI. Take the wheel from a
[GitHub release](https://github.com/Belfor-IT/robotframework-galenlibrary/releases) or build it
yourself (see [Development](#development)).

## Layout keywords

```robotframework
*** Settings ***
Library    SeleniumLibrary
Library    GalenLibrary

*** Test Cases ***
Header On Desktop
    Open Browser    https://example.com    chrome
    Set Window Size    1280    800
    Element Height Should Be        id:header    70px
    Element Should Be Inside        id:logo      id:header    16px left
    Element Should Be Centered      id:logo      id:header    vertically
    Element Should Be Below         id:hero      id:header    0px
    Elements Should Be Aligned      css:.card
    Element Css Property Should Be  id:title     font-size    32px
```

Locators are written as in SeleniumLibrary (`id:`, `css:`, `xpath:`, `class:`, `name:`, `tag:`,
`link:`, `partial link:`); `screen` and `viewport` are special containers. Distances and sizes
use Galen notation: `16px` (or `16`), `10 to 20px`, `~ 16px`, `> 10px`, `50% of viewport/width`.

| Keyword | Checks |
|---|---|
| `Element Should Be Above` / `Below` / `Left Of` / `Right Of` | Position relative to another element, optional distance |
| `Element Should Be Inside` | Inside a container, optional distances to its edges, `partly=True` |
| `Element Should Be Near` | Distance to another element at given sides |
| `Element Should Be Centered` | Centered in a container (`all`, `horizontally`, `vertically`) |
| `Elements Should Be Aligned` | Elements in one row/column, by edge, with tolerance |
| `Element Width Should Be` / `Element Height Should Be` | Size, exact, range or relative |
| `Element Css Property Should Be` | Computed CSS value (`is`, `contains`, `starts`, `ends`, `matches`) |
| `Element Color Scheme Should Be` | Colour percentages, e.g. `> 70% #1f3a5f` |
| `Element Should Satisfy Spec` | Raw Galen spec lines, for anything else |

A failing keyword reports Galen's own message, e.g. `"logo" is 66px left instead of 16px`, and
links a Galen HTML report with a screenshot in the log.

## Baseline comparison (visual regression)

```robotframework
*** Settings ***
Library    SeleniumLibrary
Library    GalenLibrary    baseline_dir=${CURDIR}/baselines

*** Test Cases ***
Products Look The Same
    Element Should Match Baseline    id:products    name=products-desktop    max_difference=1%

Whole Page Without The Banner
    Page Should Match Baseline    home-desktop    ignore=id:banner    max_difference=0.5%
```

- **First run**: the baseline does not exist yet. It is saved and the test passes with a warning.
  (`missing_baseline=fail` on import or `--variable GALEN_MISSING_BASELINE:fail` makes it fail
  instead, e.g. in CI.)
- **Where**: in a subfolder per browser, platform and window size, e.g.
  `baselines/chrome-linux-1280x800/products-desktop.png`, so desktop and mobile, or Windows and
  Linux, never mix (import argument `baseline_subfolder`).
- **Next runs**: the element is compared with the baseline.
  - `max_difference`: how much may differ, a percentage (`1%`) or a number of pixels (`50px`).
  - `tolerance`: how different one pixel may be before it counts (sum of R+G+B differences,
    0-765, default 25). Raise it for anti-aliased text that differs per machine.
  - `ignore`: parts that are always different (clock, carousel).
  - `analyze_offset`: accept the image when it is shifted by a few pixels.
  - `full_page=True`: only for elements higher or wider than the window, or for the whole page
    with `Page Should Match Baseline`. It scrolls and stitches screenshots, so sticky and fixed
    elements (a sticky header) appear several times. It scrolls only the window, so it does not
    work when a container such as `div.content-body` scrolls instead.
- **Long pages**: an element far down the page, also inside a scrolling container, is scrolled
  into view automatically (and the scroll positions restored), so on a long page, such as a
  page with all components, compare per element rather than the whole page.
- **Intended change**: approve the new screenshots of the failed comparisons (below), run once
  with `--variable GALEN_UPDATE_BASELINES:True` to replace all baselines, or use
  `Capture Baseline`.

The log shows **baseline | actual | heatmap** side by side. In the heatmap the actual image is
greyed out and differences are coloured green (small), yellow (medium) or red (large), ignored
regions blue, with a red frame around the changed area.

### Approving new baselines

When a comparison fails (difference too large, other size, or a missing baseline in `fail`
mode), the new screenshot is kept in `${OUTPUT DIR}/galen-pending`, with the same folder layout
as the baselines and a `pending.json` manifest. Screenshots of tests that pass after all (e.g.
with `Run Keyword And Expect Error`) are removed again, and when several tests fail on the same
baseline the screenshot of the first one is kept. After checking the heatmaps:

```bash
python -m GalenLibrary.approve results                  # all (also: galen-approve results)
python -m GalenLibrary.approve results "*/header-*"     # only matching baselines
python -m GalenLibrary.approve results --list           # only show
python -m GalenLibrary.approve ci-results --baselines baselines   # results from a CI artifact
```

### Baselines in CI

Baselines only match when they are made under the same conditions: same browser version,
operating system (font rendering) and window size. Recommended setup:

1. Run the tests locally and in CI in **one Docker image** with a pinned browser version, e.g.
   `selenium/standalone-chrome:<version>` (contains Chrome, chromedriver, Java and Python).
   In a container Chrome needs `--no-sandbox` and `--disable-dev-shm-usage`.
2. Keep the baselines **in git**, next to the tests.
3. Normal pipeline runs compare with `GALEN_MISSING_BASELINE:fail`.
4. A **manual pipeline job** runs the tests, approves the pending screenshots and opens a merge
   request with the new baselines, so every baseline change is reviewed.

The demo project `galen-robot-demo` contains a working GitLab pipeline (`.gitlab-ci.yml`) and
`run-docker.ps1` for the same image locally.

## Galen spec files

```robotframework
Check Layout    ${CURDIR}/specs/homepage.gspec    desktop
${result} =     Check Layout    homepage.gspec    mobile    fail_on_error=False
```

See the [Galen spec language](http://galenframework.com/docs/reference-galen-spec-language-guide/).

## Keyword documentation and import arguments

Full documentation: [docs/GalenLibrary.html](docs/GalenLibrary.html)
(regenerate with `python -m robot.libdoc GalenLibrary docs/GalenLibrary.html`).

| Import argument | Default | Description |
|---|---|---|
| `report_dir` | `${OUTPUT DIR}/galen-reports` | Galen reports and comparison images (default folder is emptied per run) |
| `baseline_dir` | `${EXECDIR}/baselines` | Baseline images |
| `baseline_subfolder` | `{browser}-{platform}-{width}x{height}` | Subfolder per environment; `NONE` for none |
| `update_baselines` | `False` | Replace baselines instead of comparing (also `${GALEN_UPDATE_BASELINES}`) |
| `missing_baseline` | `create` | `create` or `fail` when a baseline is missing (also `${GALEN_MISSING_BASELINE}`) |
| `tolerance` | `25` | Default per-pixel colour tolerance |
| `java_path` | `JAVA_HOME` / `PATH` | Java executable |
| `jar_path` | bundled jar | Alternative Galen bridge jar (also env `GALEN_BRIDGE_JAR`) |
| `timeout` | `300` | Max seconds for one check |
| `selenium_library` | `SeleniumLibrary` | Name of the SeleniumLibrary import, if imported `AS` another name |

## How it works

```
Robot test ── SeleniumLibrary ── WebDriver session (chromedriver / geckodriver / Grid)
     │                                   ▲
     └── GalenLibrary ── java -jar galen-robot-bridge.jar --server ──┘  (same session id)
```

One Java process is started per library instance and kept running; requests are JSON lines over
stdin/stdout. Layout keywords generate a small Galen spec per call. Baseline keywords use Galen's
screenshot and element-area logic and Rainbow4J for the comparison.

`galen-robot-bridge` is a Maven module in this repository (`../galen-robot-bridge`) that builds a
single shaded jar with Galen and its dependencies.

## Development

```powershell
cd robotframework-galenframework
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]

python build_jar.py        # build the Java engine (Maven + JDK) and copy it into the package
pytest                     # unit tests, no Java or browser needed
robot --outputdir results atest   # acceptance tests (Java + Chrome)
python -m build            # wheel + sdist in dist/
```

If Robot fails with `LookupError: unknown encoding: utf-8:surrogateescape`, your shell has
`PYTHONIOENCODING=utf-8:surrogateescape`; set it to `utf-8` for the run.

## Limitations

- Only SeleniumLibrary is supported (not Browser library / Playwright).
- Screenshots are not corrected for high-DPI scaling (`devicePixelRatio` > 1); headless browsers
  and CI agents normally use 1.
