*** Settings ***
Documentation       Acceptance tests for baseline comparisons of long pages (full_page=True).
...                 The page has a sticky header, 30 sections of 200px and a footer at the bottom.

Library             SeleniumLibrary
Library             OperatingSystem
Library             GalenLibrary    baseline_dir=${BASELINES}

Suite Setup         Prepare
Suite Teardown      Close All Browsers
Test Setup          Reload Page


*** Variables ***
${PAGE}         file:///${CURDIR}/resources/long.html
${BROWSER}      headlesschrome
# In Docker: add_argument("--no-sandbox");add_argument("--disable-dev-shm-usage")
${BROWSER_OPTIONS}    ${NONE}
${BASELINES}    ${OUTPUT DIR}/baselines-full-page


*** Test Cases ***
Element Below The Fold Is Scrolled Into View
    ${result} =    Element Should Match Baseline    id:footer-box    name=footer-box
    Should Be True    ${result}[created]
    Should Be Equal    ${{ image_size($result['baseline']) }}    ${{ (200, 60) }}
    ${result} =    Element Should Match Baseline    id:footer-box    name=footer-box
    Should Be Equal As Integers    ${result}[pixels]    0
    ${scroll} =    Execute Javascript    return window.pageYOffset
    Should Be Equal As Integers    ${scroll}    0    msg=The scroll position is restored

Element With Full Page Gives The Same Image
    ${result} =    Element Should Match Baseline    id:footer-box    name=footer-box    full_page=True
    Should Be Equal As Integers    ${result}[pixels]    0

Element Taller Than The Window Uses Full Page
    Run Keyword And Expect Error    *outside of the screenshot*use full_page=True*
    ...    Element Should Match Baseline    id:sections    name=sections
    ${result} =    Element Should Match Baseline    id:sections    name=sections    full_page=True
    Should Be Equal    ${{ image_size($result['baseline'])[1] }}    ${6000}

Full Page Has The Whole Document
    ${result} =    Page Should Match Baseline    long-page    full_page=True
    ${height} =    Execute Javascript    return document.documentElement.scrollHeight
    ${width} =    Execute Javascript    return document.documentElement.clientWidth
    Should Be Equal    ${{ image_size($result['baseline']) }}    ${{ (${width}, ${height}) }}

Full Page Does Not Depend On Scroll Position
    Page Should Match Baseline    long-page    full_page=True
    Execute Javascript    window.scrollTo(0, 2500)
    ${result} =    Page Should Match Baseline    long-page    full_page=True
    Should Be Equal As Integers    ${result}[pixels]    0
    Execute Javascript    window.scrollTo(0, document.body.scrollHeight)
    ${result} =    Page Should Match Baseline    long-page    full_page=True
    Should Be Equal As Integers    ${result}[pixels]    0

Sticky Header Is Not Repeated
    [Documentation]    A section in the middle must look the same in a full page screenshot
    ...    as when it is visible in the window: no copy of the sticky header painted over it.
    Execute Javascript    document.getElementById('section-15').scrollIntoView({block: 'center'})
    Capture Baseline    id:section-15    name=section-15
    Execute Javascript    window.scrollTo(0, 0)
    ${result} =    Element Should Match Baseline    id:section-15    name=section-15    full_page=True
    Should Be Equal As Integers    ${result}[pixels]    0

Scrolled Element In Window
    [Documentation]    Without full_page an element that is scrolled into view is compared too.
    Execute Javascript    document.getElementById('section-20').scrollIntoView({block: 'center'})
    Capture Baseline    id:section-20    name=section-20
    Execute Javascript    document.getElementById('section-20').scrollIntoView({block: 'end'})
    ${result} =    Element Should Match Baseline    id:section-20    name=section-20
    Should Be Equal As Integers    ${result}[pixels]    0

Change At The Bottom Is Found
    Page Should Match Baseline    long-page    full_page=True
    Execute Javascript    document.getElementById('footer-box').style.background = '#00f'
    Run Keyword And Expect Error    *differs from baseline 'long-page.png'*
    ...    Page Should Match Baseline    long-page    full_page=True


*** Keywords ***
Prepare
    Remove Directory    ${BASELINES}    recursive=True
    Open Browser    ${PAGE}    ${BROWSER}    options=${BROWSER_OPTIONS}
    Set Window Size    1280    900
    Evaluate    __import__('builtins').__dict__.setdefault('image_size', lambda p: __import__('struct').unpack('>II', open(p, 'rb').read()[16:24]))
