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
- **Long pages**: elements below the first screen are scrolled into view automatically;
  `full_page=True` stitches the whole page when you need it.

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

Installation
------------

Requirements: Python 3.9+, Java 11+ (on `PATH` or via `JAVA_HOME`), a browser with its driver.
SeleniumLibrary is installed automatically.

The library is not on PyPI. Install the wheel from a
[GitHub release](https://github.com/Belfor-IT/robotframework-galenlibrary/releases), or build it
yourself (see below):

```bash
pip install robotframework_galenframework-0.3.0-py3-none-any.whl
```

The same wheel works on Windows, Linux and macOS.

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
