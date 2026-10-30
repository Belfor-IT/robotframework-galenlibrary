*** Settings ***
Documentation       Acceptance tests for baseline comparisons on a page that does not scroll the window
...                 but an inner container (div.content-body), with a smaller scrolling panel inside it.

Library             SeleniumLibrary
Library             OperatingSystem
Library             GalenLibrary    baseline_dir=${BASELINES}

Suite Setup         Prepare
Suite Teardown      Close All Browsers
Test Setup          Reload Page


*** Variables ***
${PAGE}         file:///${CURDIR}/resources/inner-scroll.html
${BROWSER}      headlesschrome
# In Docker: add_argument("--no-sandbox");add_argument("--disable-dev-shm-usage")
${BROWSER_OPTIONS}    ${NONE}
${BASELINES}    ${OUTPUT DIR}/baselines-inner-scroll


*** Test Cases ***
Element Below The Fold In A Scroll Container
    [Documentation]    The baseline is taken with the element scrolled into view by hand; the
    ...    comparison has to scroll the container itself and find the same image.
    Execute Javascript    document.getElementById('bottom-box').scrollIntoView({block: 'center'})
    Capture Baseline    id:bottom-box    name=bottom-box
    Execute Javascript    document.getElementById('content').scrollTop = 0
    ${result} =    Element Should Match Baseline    id:bottom-box    name=bottom-box
    Should Be Equal As Integers    ${result}[pixels]    0

Row In The Middle Of A Scroll Container
    Execute Javascript    document.getElementById('row-12').scrollIntoView({block: 'center'})
    Capture Baseline    id:row-12    name=row-12
    Execute Javascript    document.getElementById('content').scrollTop = 0
    ${result} =    Element Should Match Baseline    id:row-12    name=row-12
    Should Be Equal As Integers    ${result}[pixels]    0

Element Hidden By A Smaller Scroll Panel
    [Documentation]    The item lies inside the window, but outside the visible part of #panel.
    Execute Javascript    document.getElementById('panel-item-8').scrollIntoView({block: 'nearest'})
    Capture Baseline    id:panel-item-8    name=panel-item-8
    Execute Javascript    document.getElementById('panel').scrollTop = 0
    ${result} =    Element Should Match Baseline    id:panel-item-8    name=panel-item-8
    Should Be Equal As Integers    ${result}[pixels]    0

Scroll Positions Are Restored
    Execute Javascript    document.getElementById('content').scrollTop = 150
    Execute Javascript    document.getElementById('panel').scrollTop = 40
    Element Should Match Baseline    id:bottom-box    name=bottom-box-restore
    Element Should Match Baseline    id:panel-item-9    name=panel-item-9-restore
    ${content} =    Execute Javascript    return document.getElementById('content').scrollTop
    ${panel} =    Execute Javascript    return document.getElementById('panel').scrollTop
    Should Be Equal As Integers    ${content}    150
    Should Be Equal As Integers    ${panel}    40

Ignored Region In A Scroll Container
    Element Should Match Baseline    id:row-15    name=row-15
    Execute Javascript    document.querySelector('#row-15 .stamp').textContent = '23:59'
    Run Keyword And Expect Error    *differs from baseline 'row-15.png'*
    ...    Element Should Match Baseline    id:row-15    name=row-15
    ${result} =    Element Should Match Baseline    id:row-15    name=row-15    ignore=css:#row-15 .stamp
    Should Be Equal As Integers    ${result}[pixels]    0

Visible Element Is Not Scrolled
    Element Should Match Baseline    id:row-1    name=row-1
    ${content} =    Execute Javascript    return document.getElementById('content').scrollTop
    Should Be Equal As Integers    ${content}    0


*** Keywords ***
Prepare
    Remove Directory    ${BASELINES}    recursive=True
    Open Browser    ${PAGE}    ${BROWSER}    options=${BROWSER_OPTIONS}
    Set Window Size    1280    900
