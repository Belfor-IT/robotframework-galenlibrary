*** Settings ***
Documentation       Acceptance tests for the baseline (visual regression) keywords.
...                 The tests build on each other: the first one creates the baselines.

Library             SeleniumLibrary
Library             OperatingSystem
Library             GalenLibrary    baseline_dir=${BASELINES}

Suite Setup         Prepare
Suite Teardown      Close All Browsers
Test Setup          Reload Page


*** Variables ***
${PAGE}         file:///${CURDIR}/resources/page.html
${BROWSER}      headlesschrome
# In Docker: add_argument("--no-sandbox");add_argument("--disable-dev-shm-usage")
${BROWSER_OPTIONS}    ${NONE}
${BASELINES}    ${OUTPUT DIR}/baselines
${PENDING}      ${OUTPUT DIR}/galen-pending


*** Test Cases ***
Missing Baseline Is Created
    ${result} =    Element Should Match Baseline    id:header    name=header
    Should Be True    ${result}[created]
    File Should Exist    ${result}[baseline]
    Should Match    ${result}[baseline]    *?chrome-*-1280x900?header.png

Unchanged Element Matches
    ${result} =    Element Should Match Baseline    id:header    name=header
    Should Be Equal As Integers    ${result}[pixels]    0
    File Should Exist    ${result}[heatmap]

Changed Element Fails
    Paint Box Blue
    Run Keyword And Expect Error    *differs from baseline 'header.png'*max allowed 0%*
    ...    Element Should Match Baseline    id:header    name=header
    File Should Exist    ${PENDING}/chrome-*-1280x900/header.png

Screenshot Of Passed Test Is Not Kept
    [Documentation]    The previous test passed (expected error), so its screenshot is removed.
    File Should Not Exist    ${PENDING}/*/header.png

Small Change Within Max Difference Passes
    Paint Box Blue
    ${result} =    Element Should Match Baseline    id:header    name=header    max_difference=2%
    Should Be True    1 < ${result}[percentage] < 2

Max Difference In Pixels
    Paint Box Blue
    Run Keyword And Expect Error    *max allowed 100px*
    ...    Element Should Match Baseline    id:header    name=header    max_difference=100px
    Element Should Match Baseline    id:header    name=header    max_difference=2000px

Ignored Region Is Not Compared
    Paint Box Blue
    ${result} =    Element Should Match Baseline    id:header    name=header    ignore=id:box
    Should Be Equal As Integers    ${result}[pixels]    0

High Tolerance Accepts Colour Shift
    Execute Javascript    document.getElementById('box').style.background = '#f08a08'
    Element Should Match Baseline    id:header    name=header    tolerance=60

Size Change Is Reported
    Execute Javascript    document.getElementById('header').style.height = '90px'
    Run Keyword And Expect Error    *has size *x90 but baseline 'header.png' is *x80*
    ...    Element Should Match Baseline    id:header    name=header

Page Baseline
    ${result} =    Page Should Match Baseline    page
    Should Be True    ${result}[created]
    ${result} =    Page Should Match Baseline    page
    Should Be Equal As Integers    ${result}[pixels]    0

Default Baseline Name From Test Name
    ${result} =    Element Should Match Baseline    id:menu
    Should End With    ${result}[baseline]    default-baseline-name-from-test-name-id-menu.png

Other Window Size Has Its Own Baselines
    Set Window Size    1024    768
    ${result} =    Element Should Match Baseline    id:header    name=header
    Should Be True    ${result}[created]
    Should Match    ${result}[baseline]    *?chrome-*-1024x768?header.png
    [Teardown]    Set Window Size    1280    900

Missing Baseline Can Fail And Is Kept For Approval
    Set Test Variable    ${GALEN_MISSING_BASELINE}    fail
    Run Keyword And Expect Error    *does not exist. The screenshot is kept for approval*
    ...    Element Should Match Baseline    id:box    name=never-created
    File Should Exist    ${PENDING}/*/never-created.png
    File Should Not Exist    ${BASELINES}/*/never-created.png

Update Baselines With Variable
    Paint Box Blue
    Set Test Variable    ${GALEN_UPDATE_BASELINES}    True
    ${result} =    Element Should Match Baseline    id:header    name=header
    Should Be True    ${result}[created]
    Set Test Variable    ${GALEN_UPDATE_BASELINES}    False
    Element Should Match Baseline    id:header    name=header

Capture Baseline Explicitly
    ${path} =    Capture Baseline    id:box    name=box
    File Should Exist    ${path}
    Element Should Match Baseline    id:box    name=box


*** Keywords ***
Prepare
    Remove Directory    ${BASELINES}    recursive=True
    Open Browser    ${PAGE}    ${BROWSER}    options=${BROWSER_OPTIONS}
    Set Window Size    1280    900

Paint Box Blue
    Execute Javascript    document.getElementById('box').style.background = '#00f'
