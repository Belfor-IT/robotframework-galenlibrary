robotframework-galenlibrary
===========================

Layout, responsive-design and visual regression testing for **Robot Framework**, powered by
[Galen Framework](http://galenframework.com).

This repository is a fork of [galenframework/galen](https://github.com/galenframework/galen) with
two additions:

1. **GalenLibrary**, a Robot Framework library (`robotframework-galenframework`) that runs Galen
   checks on the page that is already open in **SeleniumLibrary**.
2. The **Galen engine moved to Selenium 4** and Java 11, so it works with current browsers and
   drivers.

```robotframework
*** Settings ***
Library    SeleniumLibrary
Library    GalenLibrary    baseline_dir=${CURDIR}/baselines

*** Test Cases ***
Save Button Looks Right
    Open Browser    https://example.com/components    headlesschrome
    Set Window Size    1280    900
    Element Height Should Be         css:[data-testid="save"]    40px
    Element Should Be Below          css:[data-testid="save"]    id:form
    Element Should Match Baseline    css:[data-testid="save"]    name=save-button
```

What we built
-------------

### GalenLibrary (`robotframework-galenframework/`)

A Python library that you import next to SeleniumLibrary. It does not open a browser of its own:
the Galen engine attaches to the existing WebDriver session, so login state, cookies, window size
and earlier test steps are kept.

| Approach | Keywords | Good for |
|---|---|---|
| **Layout keywords** | `Element Should Be Below`, `Element Should Be Inside`, `Element Width Should Be`, `Elements Should Be Aligned`, ... | Hard design rules (sizes, distances, alignment) without learning Galen |
| **Baseline comparison** | `Element Should Match Baseline`, `Page Should Match Baseline`, `Capture Baseline` | Visual regression tests per component, with a heatmap of the differences |
| **Galen spec files** | `Check Layout` | Complete pages on several screen sizes in one `.gspec` file |

Highlights:

- Failures show Galen's own message, for example `"logo" is 66px left instead of 16px`, with a
  link to the Galen report. Baseline failures show baseline, actual screenshot and heatmap side
  by side in `log.html`.
- **Baselines per environment**: screenshots are stored in a subfolder per browser, platform and
  window size (`baselines/chrome-linux-1280x900/`), so Windows and Linux, or desktop and mobile,
  never mix.
- **Approval workflow**: a failed comparison keeps the new screenshot in
  `${OUTPUT DIR}/galen-pending`. `python -m GalenLibrary.approve` (or `galen-approve`) copies the
  approved screenshots over the baselines. In CI, `GALEN_MISSING_BASELINE:fail` makes missing
  baselines a failure, and all of them are collected in one run.
- **Long pages**: elements below the first screen are scrolled into view automatically, also
  inside a scrolling container such as `div.content-body`, and the scroll positions are restored
  afterwards. `full_page=True` stitches the whole page when you need it, but it scrolls only the
  window, so it does not work when a container scrolls instead.

Full keyword documentation: [robotframework-galenframework/README.md](robotframework-galenframework/README.md)
and [docs/GalenLibrary.html](robotframework-galenframework/docs/GalenLibrary.html).

### Galen robot bridge (`galen-robot-bridge/`)

A new Maven module that builds `galen-robot-bridge.jar`, a shaded jar with the Galen engine. The
library starts it once per test run (`java -jar galen-robot-bridge.jar --server`) and talks to it
with JSON lines over stdin/stdout. The bridge attaches to the SeleniumLibrary session through
Selenium's supported API. The jar is bundled inside the Python wheel, so users only need Java.

### Galen core on Selenium 4

- Selenium 3.14 → **4.51**, Java 8 → **11**.
- PhantomJS support removed: Selenium 4 has no driver for it.
- `httpclient` added as an explicit dependency, because Selenium 4 no longer brings it along.

How it fits together
--------------------

```
Robot Framework test
  ├── SeleniumLibrary ──────────── WebDriver session (Chrome, Firefox, ...)
  └── GalenLibrary (Python)                 ▲
        └── galen-robot-bridge.jar (Java) ──┘ attaches to the same session
              └── Galen core: layout checks, screenshots, image comparison
```

What happens when a keyword runs:

1. GalenLibrary asks SeleniumLibrary for the current WebDriver session (session id and driver URL).
2. A layout keyword such as `Element Should Be Below` is turned into a small Galen spec. `Check
   Layout` uses your own `.gspec` file instead.
3. The spec, or the screenshot request for a baseline keyword, goes to the bridge as one JSON line.
4. The bridge attaches to the session, runs Galen and sends back the result.
5. GalenLibrary passes or fails the keyword and writes Galen's message, the report link and, for
   baselines, the images and heatmap to `log.html`.

The browser is never restarted, so whatever the test did before (logging in, filling in a form,
resizing the window) is what Galen checks.

Installation
------------

Requirements: Python 3.9+, Java 11+ (on `PATH` or via `JAVA_HOME`), a browser with its driver.
SeleniumLibrary is installed automatically.

The library is not on PyPI. Install the wheel from a
[GitHub release](https://github.com/Belfor-IT/robotframework-galenlibrary/releases), or build it
yourself (see below):

```bash
pip install robotframework_galenframework-0.3.1-py3-none-any.whl
```

The same wheel works on Windows, Linux and macOS.

Using it in Robot Framework, step by step
-----------------------------------------

**1. Import both libraries.** SeleniumLibrary opens the browser, GalenLibrary checks it.

```robotframework
*** Settings ***
Library    SeleniumLibrary
Library    GalenLibrary    baseline_dir=${CURDIR}/baselines
```

**2. Open the page with a fixed window size.** Layout and screenshots depend on the window size,
and the baseline folder name includes it (`chrome-linux-1280x900`).

```robotframework
*** Keywords ***
Open Page For Visual Test
    Open Browser    ${URL}    headlesschrome
    Set Window Size    1280    900
```

**3. Make the page stable.** Turn off animations, transitions and the blinking cursor, and wait
for fonts, otherwise screenshots differ from run to run.

```robotframework
Make Page Stable
    Execute Javascript
    ...    var s = document.createElement('style');
    ...    s.textContent = '*, *::before, *::after { transition: none !important; animation: none !important; caret-color: transparent !important; }';
    ...    document.head.appendChild(s);
    Wait For Condition    return document.fonts.status === 'loaded'
```

**4. Check hard design rules with layout keywords.**

```robotframework
*** Test Cases ***
Buttons Have The Right Size And Position
    Element Height Should Be      css:[data-testid="save"]    40px
    Element Should Be Left Of     css:[data-testid="save"]    css:[data-testid="cancel"]    12px
    Elements Should Be Aligned    css:.button    direction=horizontally    edge=top
```

**5. Compare components with baselines.** Use one baseline per component and per state (hover,
focus, error). The first run creates the baseline; later runs compare with it.

```robotframework
Save Button
    Element Should Match Baseline    css:[data-testid="save"]    name=save-button
    Mouse Over                       css:[data-testid="save"]
    Element Should Match Baseline    css:[data-testid="save"]    name=save-button-hover
```

Wrap the comparison in `Run Keyword And Continue On Failure` to see all differences of a test in
one run. Use `ignore=` for parts that change by themselves, such as dates.

**6. Look at the result.** On a difference, `log.html` shows baseline, actual screenshot and
heatmap. The new screenshot is kept in `results/galen-pending/`.

**7. Approve intended changes.**

```bash
python -m GalenLibrary.approve results                    # approve everything
python -m GalenLibrary.approve results "*/save-button*"   # only matching baselines
python -m GalenLibrary.approve results --list             # only show what is pending
```

**8. Run in CI.** Make and compare baselines on the CI runner (or an identical machine), and run
with `--variable GALEN_MISSING_BASELINE:fail` so a missing baseline fails the pipeline instead of
being created silently. Approved baselines go back into git through a merge request.

```bash
robot --outputdir results --variable GALEN_MISSING_BASELINE:fail tests
```

Keywords
--------

| Keyword | Arguments | What it checks or does |
|---|---|---|
| **Position** | | |
| `Element Should Be Above` | `locator, reference, distance=None` | `locator` is above `reference`, optionally at a distance |
| `Element Should Be Below` | `locator, reference, distance=None` | `locator` is below `reference` |
| `Element Should Be Left Of` | `locator, reference, distance=None` | `locator` is left of `reference` |
| `Element Should Be Right Of` | `locator, reference, distance=None` | `locator` is right of `reference` |
| `Element Should Be Inside` | `locator, container, offsets=None, partly=False` | `locator` lies inside `container`, optionally with distances to its edges |
| `Element Should Be Near` | `locator, reference, offsets` | `locator` is close to `reference` at the given sides |
| `Element Should Be Centered` | `locator, container, direction=all, tolerance=None` | Centered in `container` (`all`, `horizontally`, `vertically`) |
| `Elements Should Be Aligned` | `*locators, direction=horizontally, edge=all, tolerance=0` | Elements are in one row or column |
| **Size and style** | | |
| `Element Width Should Be` | `locator, expected` | Width, e.g. `200px`, `190 to 210px`, `50% of viewport/width` |
| `Element Height Should Be` | `locator, expected` | Height, same notation |
| `Element Css Property Should Be` | `locator, property, expected, match=is` | Computed CSS value (`is`, `contains`, `starts`, `ends`, `matches`) |
| `Element Color Scheme Should Be` | `locator, scheme` | Colours in a screenshot, e.g. `> 70% #1f3a5f` |
| `Element Should Satisfy Spec` | `locator, *specs, **references` | Raw Galen spec lines, for anything else |
| **Spec files** | | |
| `Check Layout` | `spec, tags=None, exclude_tags=None, properties=None, variables=None, title=None, fail_on_error=True, full_page=False` | Runs a complete `.gspec` file, optionally for some tags only |
| **Baselines** | | |
| `Element Should Match Baseline` | `locator, name=None, max_difference=0%, tolerance=None, ignore=None, analyze_offset=0, full_page=False` | Compares an element with its baseline screenshot |
| `Page Should Match Baseline` | `name=None, max_difference=0%, tolerance=None, ignore=None, analyze_offset=0, full_page=False` | Compares the visible page (or the whole page) with its baseline |
| `Capture Baseline` | `locator=viewport, name=None, full_page=False` | Stores a screenshot as baseline without comparing |
| **Settings** | | |
| `Set Baseline Directory` | `path` | Changes the baseline folder; returns the previous one |
| `Set Galen Report Directory` | `path` | Changes the folder for Galen reports and comparison images |

Locators are written as in SeleniumLibrary (`id:`, `css:`, `xpath:`, `class:`, `name:`, `tag:`,
`link:`, `partial link:`). `screen` and `viewport` can be used as containers.

`max_difference` is a percentage (`0.5%`) or a number of pixels (`200px`). `tolerance` is the
colour difference per pixel that still counts as equal (default 25).

### Import arguments

| Argument | Default | Meaning |
|---|---|---|
| `baseline_dir` | `${EXECDIR}/baselines` | Folder with the baseline screenshots |
| `baseline_subfolder` | `{browser}-{platform}-{width}x{height}` | Subfolder per environment; `NONE` for none |
| `missing_baseline` | `create` | `create` stores a missing baseline, `fail` fails the keyword (also `GALEN_MISSING_BASELINE`) |
| `update_baselines` | `False` | Replace baselines instead of comparing (also `GALEN_UPDATE_BASELINES`) |
| `tolerance` | `25` | Default per-pixel colour tolerance |
| `report_dir` | `${OUTPUT DIR}/galen-reports` | Folder for Galen reports and images |
| `java_path` / `jar_path` | from `JAVA_HOME` / bundled jar | Other Java or bridge jar |
| `timeout` | `300` | Seconds to wait for the Galen engine |
| `selenium_library` | `SeleniumLibrary` | Name of the SeleniumLibrary import, if it has an alias |

Building
--------

The wheel needs the Java engine inside it. `build_jar.py` builds the jar with Maven and copies it
into the package, then `python -m build` makes the wheel. You need a JDK 11+ and Maven 3.

```bash
cd robotframework-galenframework
python build_jar.py            # or: python build_jar.py --mvn /path/to/mvn
python -m build                # wheel and sdist in dist/
```

The jar is not committed to git, so `pip install git+https://...` does not work. Always install
from a built wheel.

Testing
-------

```bash
cd robotframework-galenframework
pip install -e .[dev]
python build_jar.py
pytest utest                   # unit tests, no Java or browser needed
robot --outputdir results atest   # acceptance tests with headless Chrome
```

Galen core unit tests (`mvn test` from the repository root) also run on Java 21 with:

```bash
mvn test -Djacoco.skip=true "-DsurefireArgLine=--add-opens=java.base/java.lang=ALL-UNNAMED"
```

JaCoCo 0.7.4 and Mockito 1.9.5 in the original build are too old for Java 21 without these flags.

Repository layout
-----------------

| Folder | Contents |
|---|---|
| `robotframework-galenframework/` | GalenLibrary: Python source, unit tests (`utest`), acceptance tests (`atest`), keyword docs |
| `galen-robot-bridge/` | Java bridge between GalenLibrary and the Galen engine (new) |
| `galen-core/`, `galen-rainbow4j/`, `galen-java-support/` | Galen engine, image comparison and Java API (upstream, moved to Selenium 4) |
| `galen-integration-tests/`, `galen-distribution/` | Upstream integration tests and the Galen command-line distribution |

Limitations
-----------

- Only SeleniumLibrary is supported, not Browser library (Playwright).
- Screenshots are not corrected for `devicePixelRatio` > 1. Headless browsers and CI normally
  use 1.
- Screenshots differ per machine (browser version, fonts, display scaling). Make and compare
  baselines on the same kind of machine, for example the CI runner.

About Galen Framework
---------------------

Galen is an open-source tool for testing the layout and responsive design of web applications.
It describes a page in a spec language and checks the position and size of elements relative to
each other, for each screen size:

```
@objects
    header      id  header
    menu        css #menu
    content     id  content

= Main section =
    @on *
        header:
            inside screen 0px top, 0px left, 0px right
        menu:
            below header 0px

    @on mobile
        content:
            width 100% of screen/width
```

GalenLibrary runs such spec files with `Check Layout`, and generates small specs like this one for
every layout keyword. See the [Galen documentation](http://galenframework.com/docs/all/) for the
full spec language.

The original Galen command-line tool can still be built from this repository with `./makeDist.sh`.

License
-------

Licensed under the [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0), like
Galen Framework itself. Galen Framework was created by Ivan Shubin and contributors.
